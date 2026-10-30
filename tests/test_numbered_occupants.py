"""Numbered identities and mouse actions use fake campus snapshots only."""
import collections
import queue
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from campus_lan.client import Client
from campus_lan.cluster_viewer import ClusterViewer
from campus_lan.lobby_view import occupant_hits, lobby_lines
from campus_lan.numbered_occupants import capture, selection


def players():
    return [dict(name='fixture%02d'%number,seat='c1r1s'+str(number)) for number in range(1,13)]+[
        dict(name='fixture13',seat='c2r1s3')]


class NumberedOccupants(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        import os
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name,'XDG_STATE_HOME':self.temp.name})
        env.start();self.addCleanup(env.stop)
        valid=patch('campus_lan.profile_browser.validate_logins',side_effect=lambda values:list(dict.fromkeys(values)))
        valid.start();self.addCleanup(valid.stop)

    def client(self,role='lobby',roster=True):
        c=Client.__new__(Client)
        c.name='fixture-owner';c.role=role;c.lines=collections.deque();c.input='';c.play=False
        c.open_urls=Mock();c.popup_prompts=Mock();c.send=Mock();c.local_api_command=Mock(return_value=False)
        c.secure=True;c.signed_in=True;c.inbox=queue.Queue();c.notify_enabled=False
        if roster:c.cluster_players=players()
        return c

    def viewer(self):
        source=Mock();source.label='Fake authorized source'
        v=ClusterViewer(source,queue.Queue(),owner=None)
        v.players=players();v.stamp=time.time();v.open_urls=Mock()
        return v

    def test_number_is_campus_roster_occupant_not_physical_desk_or_numeric_login(self):
        resolved,captured=capture(['13'],players())
        self.assertEqual(resolved,['fixture13'])
        self.assertEqual(captured,{13:('fixture13',(2,1,3))})
        from campus_lan.profile_browser import resolve
        with self.assertRaisesRegex(ValueError,'Numbers select campus'):resolve(['13'])

    def test_hq_and_game_require_identity_confirmation_before_profile(self):
        for role in ('lobby','game'):
            with self.subTest(role=role):
                c=self.client(role)
                c.settings_command('/profile 13')
                c.open_urls.assert_not_called()
                prompt,accept,decline=c.popup_prompts.return_value.confirm.call_args.args
                self.assertIn('13 = fixture13 (c2r1s3)',prompt)
                accept()
                self.assertEqual(c.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/users/fixture13'])
                c.send.assert_not_called()

    def test_confirmed_login_is_not_reinterpreted_as_an_all_or_cohort_selector(self):
        c=self.client();c.cluster_players[-1]['name']='all'
        with patch('campus_lan.profile_browser.load') as load:
            c.settings_command('/profile 13')
            c.popup_prompts.return_value.confirm.call_args.args[1]()
            load.assert_not_called()
        self.assertEqual(c.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/users/all'])

    def test_absent_number_or_changed_occupant_never_opens_profile(self):
        c=self.client();c.settings_command('/profile 99')
        c.popup_prompts.return_value.confirm.assert_not_called();c.open_urls.assert_not_called()
        c.settings_command('/profile 13')
        accept=c.popup_prompts.return_value.confirm.call_args.args[1]
        c.cluster_players[-1]['name']='changed'
        accept();c.open_urls.assert_not_called()
        self.assertIn('changed',' '.join(c.lines))

    def test_game_loads_campus_roster_without_using_room_players_or_changing_view(self):
        c=self.client('game',False);c.state={'players':[dict(name='wrong-room-player',seat='c1r1s1')]}
        c.show_lobby=False;c.cluster=2
        c.settings_command('/profile 13')
        c.send.assert_called_once_with(dict(type='command',text='/clusters'))
        c.open_urls.assert_not_called()
        c.inbox.put(dict(type='clusters',players=players(),updated_at=time.time(),cluster=0))
        c.consume()
        self.assertFalse(c.show_lobby);self.assertEqual(c.cluster,2)
        self.assertIn('fixture13',c.popup_prompts.return_value.confirm.call_args.args[0])

    def test_signout_invalidates_a_captured_identity_before_confirmation(self):
        c=self.client();c.settings_command('/profile 13')
        accept=c.popup_prompts.return_value.confirm.call_args.args[1]
        c.inbox.put(dict(type='signed_out'))
        with patch('campus_lan.client.auth_client.clear_session'):c.consume()
        accept();c.open_urls.assert_not_called();self.assertFalse(c.signed_in)

    def test_cluster_profile_home_login_number_and_cancel(self):
        v=self.viewer()
        v.command('/profile');self.assertEqual(v.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/'])
        v.command('/profile fixture13');self.assertIn('/users/fixture13',v.open_urls.call_args.args[1][0])
        v.open_urls.reset_mock();v.command('/profile 13')
        self.assertIn('13 = fixture13 (c2r1s3)',v.status)
        v.command('');v.open_urls.assert_not_called();v.source.refresh.assert_not_called()
        v.command('/profile 13');v.command('y')
        self.assertEqual(v.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/users/fixture13'])

    def test_cluster_changed_occupant_and_bare_number(self):
        v=self.viewer();v.command('13');v.players[-1]['name']='changed'
        v.command('y');v.open_urls.assert_not_called();self.assertIn('changed',v.status)

    def test_numeric_message_recipient_preserves_numbers_in_message(self):
        c=self.client();c.group_command('/dm 13 meet at 42 at 13:00')
        prompt,accept,_=c.popup_prompts.return_value.confirm.call_args.args
        self.assertIn('fixture13',prompt);c.send.assert_not_called()
        with patch('campus_lan.tracking.Tracker') as tracker:
            tracker.return_value.load_error=None;tracker.return_value.resolve.return_value=['fixture13']
            accept()
        c.send.assert_called_once_with(dict(type='direct_batch',targets=['fixture13'],text='meet at 42 at 13:00'))

    def test_map_click_handles_cohort_marker_and_shared_occupants(self):
        v=self.viewer();v.cluster=2
        decorated=[dict(p,local_cohort=4,api_presence=True) for p in v.players]
        hits=occupant_hits(decorated,'map',2)
        hit=next(hit for hit in hits if hit[3][0]['name']=='fixture13')
        row,left,right,members=hit
        rendered=''.join(text for text,_ in lobby_lines(decorated,'map',2)[row])
        self.assertEqual(rendered[left:right],'4:13')
        v.hits=[(row,left,right,members)]
        self.assertTrue(v.click(left,row));self.assertEqual(v.focus_location,(2,1,3))
        self.assertIn('fixture13',v.status)
        shared=decorated+[dict(name='shared',seat='c2r1s3')]
        hit=next(hit for hit in occupant_hits(shared,'map',2) if len(hit[3])==2)
        v.players=shared;v.hits=[hit];v.click(hit[1],hit[0])
        self.assertIn('fixture13',v.status);self.assertIn('shared',v.status)

    def test_cluster_curses_mouse_event_reaches_selection_and_draws_highlight(self):
        import curses
        v=self.viewer();v.cluster=1;v.players=[dict(name='clicked',seat='c1r8s2')]
        row,left,_,_=occupant_hits(v.players,'map',1)[0]
        screen=Mock();screen.getmaxyx.return_value=(30,100)
        screen.getch.side_effect=[curses.KEY_MOUSE,3]
        with patch('campus_lan.cluster_viewer.curses.has_colors',return_value=False), \
             patch('campus_lan.cluster_viewer.curses.mousemask'), \
             patch('campus_lan.cluster_viewer.curses.mouseinterval'), \
             patch('campus_lan.cluster_viewer.curses.getmouse',return_value=(0,left,row+3,0,curses.BUTTON1_CLICKED)), \
             patch('campus_lan.cluster_viewer.generation',return_value='fixture'), \
             patch('campus_lan.cohort_display.cohort_index',return_value={}):
            v.run(screen)
        self.assertEqual(v.focus_location,(1,8,2));self.assertIn('clicked',v.status)
        self.assertTrue(any(len(call.args)>4 and call.args[4]&curses.A_REVERSE for call in screen.addnstr.call_args_list))

    def test_numeric_tracking_relationship_and_photo_tool_share_confirmation(self):
        c=self.client();c.get_tracker=Mock()
        c.tracking_command('/track friends 13')
        self.assertIn('fixture13',c.popup_prompts.return_value.confirm.call_args.args[0])
        c.open_admin(['13'])
        self.assertIn('fixture13',c.popup_prompts.return_value.confirm.call_args.args[0])

    def test_cluster_browser_denial_still_applies_after_identity_confirmation(self):
        v=self.viewer();del v.open_urls
        from campus_lan.popup_permissions import Prompts
        permission=Mock();permission.mode.return_value='deny'
        v.consent=Prompts(permission,v.report_profile)
        with patch('webbrowser.open_new_tab') as browser:
            v.command('/profile 13');v.command('y')
            browser.assert_not_called()
        self.assertIn('blocked',v.status)

    def test_empty_desks_have_no_identity_hit_and_both_clusters_keep_geometry(self):
        p=[dict(name='one',seat='c1r1s1'),dict(name='two',seat='c2r1s3')]
        hits=occupant_hits(p,'map',0)
        self.assertEqual({member['name'] for hit in hits for member in hit[3]},{'one','two'})
        # Two occupied map cells plus their two roster rows.
        self.assertEqual(len(hits),4)

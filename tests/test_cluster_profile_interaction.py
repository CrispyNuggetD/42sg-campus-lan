"""Fake terminal/browser only; no real profile is opened."""
import curses
import queue
import unittest
from unittest.mock import Mock,patch
from campus_lan.cluster_viewer import ClusterViewer
from campus_lan.lobby_view import occupant_hits


class ClusterProfileInteraction(unittest.TestCase):
    def viewer(self):
        source=Mock();source.label='Fixture host'
        viewer=ClusterViewer(source,queue.Queue(),cluster=1,owner=None)
        viewer.players=[dict(name='fixture',seat='c1r8s2')];viewer.stamp=100
        viewer.open_urls=Mock()
        return viewer

    def run_screen(self,viewer,keys,mouse=None):
        screen=Mock();screen.getmaxyx.return_value=(30,100);screen.getch.side_effect=keys
        with patch('campus_lan.cluster_viewer.curses.has_colors',return_value=False), \
             patch('campus_lan.cluster_viewer.curses.mousemask'), \
             patch('campus_lan.cluster_viewer.curses.mouseinterval'), \
             patch('campus_lan.cluster_viewer.curses.getmouse',return_value=mouse), \
             patch('campus_lan.cluster_viewer.generation',return_value='fixture'), \
             patch('campus_lan.cohort_display.cohort_index',return_value={}):
            viewer.run(screen)
        return screen

    def test_numeric_confirmation_and_profile_messages_render_above_bottom_input(self):
        v=self.viewer();v.command('/profile 1')
        screen=self.run_screen(v,[3])
        calls=screen.addnstr.call_args_list
        confirmation=[call for call in calls if '1 = fixture' in call.args[2]]
        self.assertTrue(confirmation)
        self.assertGreaterEqual(confirmation[0].args[0],27)
        self.assertFalse(any(call.args[0]<20 and '1 = fixture' in call.args[2] for call in calls))
        self.assertIn((29,0,'> ',99),[call.args for call in calls])
        v.pending_profile_decision=None;v.session_hint_pending=False
        v.report_profile('Profile opened.')
        screen=self.run_screen(v,[3])
        # A source notice/profile completion received during rendering uses the same footer.
        v.events.put(dict(type='local_profile_notice',text='Profile opened.'))
        screen=self.run_screen(v,[3])
        self.assertTrue(any(call.args[0]==28 and call.args[2]=='Profile opened.' for call in screen.addnstr.call_args_list))

    def test_browser_permission_question_also_renders_in_bottom_footer(self):
        v=self.viewer();v.consent=Mock(active=('browser','Open the Intra profile for fixture?',None,'once'))
        screen=self.run_screen(v,[3])
        self.assertTrue(any(call.args[0]==28 and 'Open the Intra profile' in call.args[2] for call in screen.addnstr.call_args_list))

    def test_native_double_click_opens_exact_profile_without_another_numeric_prompt(self):
        v=self.viewer();row,left,_,_=occupant_hits(v.players,'map',1)[0]
        with patch('campus_lan.profile_browser.validate_logins',side_effect=lambda values:values):
            self.run_screen(v,[curses.KEY_MOUSE,3],(0,left,row+2,0,curses.BUTTON1_DOUBLE_CLICKED))
        self.assertIsNone(v.pending_profile_decision)
        self.assertEqual(v.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/users/fixture'])

    def test_single_click_does_not_open_and_shared_cell_requires_specific_occupant(self):
        v=self.viewer();v.hits=occupant_hits(v.players,'map',1)
        row,left,_,_=v.hits[0];v.click(left,row);v.open_urls.assert_not_called()
        v.players.append(dict(name='second',seat='c1r8s2'));v.hits=occupant_hits(v.players,'map',1)
        v.last_click=None
        row,left,_,_=v.hits[0];v.click(left,row,double=True)
        v.open_urls.assert_not_called();self.assertIn('Shared seat',v.status)

    def test_double_click_respects_browser_denial(self):
        from campus_lan.popup_permissions import Prompts
        v=self.viewer();del v.open_urls
        permission=Mock();permission.mode.return_value='deny'
        v.consent=Prompts(permission,v.report_profile)
        v.hits=occupant_hits(v.players,'map',1);row,left,_,_=v.hits[0]
        with patch('campus_lan.profile_browser.validate_logins',side_effect=lambda values:values), patch('webbrowser.open_new_tab') as browser:
            v.click(left,row,double=True);browser.assert_not_called()
        self.assertIn('blocked',v.status)

    def test_stale_hit_never_opens_a_replacement_occupant(self):
        v=self.viewer();v.hits=occupant_hits(v.players,'map',1)
        row,left,_,_=v.hits[0]
        v.players=[dict(name='replacement',seat='c1r8s2')]
        v.click(left,row,double=True);v.open_urls.assert_not_called()
        self.assertIn('changed',v.status)

    def test_enter_cancels_numeric_confirmation_even_with_initial_tip_pending(self):
        v=self.viewer();v.command('/profile 1');v.session_hint_pending=True
        v.command('')
        self.assertIsNone(v.pending_profile_decision);v.open_urls.assert_not_called()

    def test_double_click_cannot_retarget_after_pagination_or_roster_changes(self):
        v=self.viewer();v.hits=occupant_hits(v.players,'map',1)
        row,left,right,_=v.hits[0];v.click(left,row)
        other=dict(name='other',seat='c1r8s4')
        v.players.append(other);v.hits=[(row,left,right,[other])]
        v.click(left,row,double=True);v.open_urls.assert_not_called()
        self.assertIn('changed',v.status)

    def test_hint_is_once_per_viewer_session_and_enter_dismisses_without_refresh(self):
        v=self.viewer();screen=self.run_screen(v,[10,3])
        self.assertTrue(any('Tip: double-click' in call.args[2] for call in screen.addnstr.call_args_list))
        self.assertFalse(v.session_hint_pending)
        self.assertEqual(v.source.refresh.call_count,1)
        screen=self.run_screen(v,[3])
        self.assertFalse(any('Tip: double-click' in call.args[2] for call in screen.addnstr.call_args_list))
        fresh=self.viewer();screen=self.run_screen(fresh,[3])
        self.assertTrue(any('Tip: double-click' in call.args[2] for call in screen.addnstr.call_args_list))

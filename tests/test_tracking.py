import collections
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.tracking import Tracker,describe
from campus_lan.client import Client

class Tracking(unittest.TestCase):
    def setUp(self):
        whitelist=patch('campus_lan.login_whitelist.allowed_logins',return_value={'dthoo','thtay','student'})
        whitelist.start();self.addCleanup(whitelist.stop)

    def test_private_persistence_validation_and_removal(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            tracker=Tracker('owner');tracker.change(['DTHOO','thtay','dthoo'])
            self.assertEqual(Tracker('owner').names,['dthoo','thtay'])
            self.assertEqual(Tracker('other').names,[])
            self.assertEqual(tracker.path.stat().st_mode&0o777,0o600)
            with self.assertRaises(ValueError):tracker.change(['../../bad'])
            tracker.change(['dthoo'],remove=True);self.assertEqual(tracker.names,['thtay'])

    def test_independent_sources_transitions_and_seat_details(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            tracker=Tracker('owner');tracker.change(['dthoo'])
            player=dict(name='dthoo',seat='c2r3s9',verified=True)
            notice=tracker.transitions([player],'campus')[0]
            title,body=describe(notice)
            self.assertIn('on campus',title);self.assertIn('cluster 2, row 3, seat 9',body)
            self.assertFalse(tracker.transitions([player],'campus'))
            self.assertIn('LAN42 lobby',describe(tracker.transitions([player],'lobby')[0])[0])
            tracker.transitions([],'campus');self.assertEqual(len(tracker.transitions([player],'campus')),1)
            self.assertFalse(tracker.transitions([player],'lobby'))

    def test_poll_requests_no_watch_list_and_respects_five_minutes(self):
        c=Client.__new__(Client);c.role='lobby';c.connected=True;c.id='id';c.send=Mock();c.local_api_command=Mock(return_value=False)
        c.tracker=Mock(names=['dthoo','private-target']);c.track_next=0;c.track_pending=0
        c.tracker.path.stat.return_value.st_mtime_ns=0;c.tracker.file_mtime_ns=0
        with patch('campus_lan.client.time.monotonic',return_value=100):c.tracking_tick();c.tracking_tick()
        c.send.assert_called_once_with(dict(type='command',text='/campus-presence'))
        self.assertEqual(c.track_next,400)
        self.assertNotIn('dthoo',json.dumps(c.send.call_args.args))

    def test_hq_reloads_tracking_changes_saved_by_cluster_window(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            c=Client.__new__(Client);c.name='owner';c.role='lobby';c.connected=True;c.id='id'
            c.lines=collections.deque();c.tracker=Tracker('owner');c.tracker.change(['dthoo'])
            c.local_api_command=Mock(return_value=True);c.track_next=1000;c.track_pending=0
            Tracker('owner').change(['student'])
            c.tracker.file_mtime_ns=0
            with patch('campus_lan.client.time.monotonic',return_value=100):c.tracking_tick()
            self.assertEqual(set(c.tracker.names),{'dthoo','student'})
            self.assertIn('updated from another LAN42 window',c.lines[-1])
            c.local_api_command.assert_called_with('/campus-presence')

    def test_offline_seat_and_verification_changes_are_reported_once(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            tracker=Tracker('owner');tracker.change(['student'])
            self.assertEqual(tracker.transitions([],'campus'),[])
            player=dict(name='student',seat='c1r2s3',verified=False)
            self.assertEqual(tracker.transitions([player],'campus')[0]['changes'],['online'])
            moved=dict(player,seat='c2r3s4')
            notice=tracker.transitions([moved],'campus')[0]
            self.assertEqual(notice['changes'],['seat'])
            self.assertIn('moved',describe(notice)[0])
            self.assertIn('c1r2s3',describe(notice)[1]);self.assertIn('c2r3s4',describe(notice)[1])
            self.assertFalse(tracker.transitions([dict(moved,seat='Cluster 2, row 3, seat 4')],'campus'))
            notice=tracker.transitions([],'campus')[0]
            self.assertEqual(notice['changes'],['offline'])
            self.assertIn('offline',describe(notice)[0]);self.assertIn('Last seen',describe(notice)[1])
            self.assertFalse(tracker.transitions([],'campus'))
            tracker.transitions([player],'lobby')
            notice=tracker.transitions([dict(player,verified=True)],'lobby')[0]
            self.assertEqual(notice['changes'],['verification'])
            self.assertIn('42 Verified',describe(notice)[1])
            self.assertIn('left the LAN42 lobby',describe(tracker.transitions([],'lobby')[0])[0])
            self.assertFalse(tracker.transitions([],'lobby'))

    def test_scoped_rules_report_departure_and_moving_out_of_cluster(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            t=Tracker('owner');t.configure_rules('include',['student']);t.configure_rules('scope',['c1']);t.configure_rules('on')
            player=dict(name='student',seat='c1r2s3')
            t.transitions([player],'campus')
            self.assertEqual(t.transitions([],'campus')[0]['changes'],['offline'])
            self.assertFalse(t.transitions([],'campus'))
            t.transitions([player],'campus')
            self.assertEqual(t.transitions([dict(player,seat='c2r2s3')],'campus')[0]['changes'],['seat'])
            self.assertFalse(t.transitions([dict(player,seat='c2r2s3')],'campus'))

    def test_api_failure_preserves_state_and_disabled_popups_keep_terminal_text(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.tracking.config_dir',return_value=Path(tmp)):
            c=Client.__new__(Client);c.lines=collections.deque();c.inbox=queue.Queue()
            c.search_result=Mock(return_value=False);c.announcement_event=Mock(return_value=False)
            c.tracker=Tracker('owner');c.tracker.change(['student'])
            c.notification_allowed=Mock(return_value=False);c.desktop_notice=Mock();c.state={}
            c.tracking_update([dict(name='student',seat='c1r2s3')],'campus')
            c.inbox.put(dict(type='campus_presence',error='API unavailable'))
            c.consume()
            c.inbox.put(dict(type='campus_presence'))
            c.consume()
            self.assertTrue(c.tracker.campus['student'])
            self.assertNotIn('offline',' '.join(c.lines))
            c.tracking_update([],'campus')
            self.assertIn('student is offline on campus',c.lines)
            c.desktop_notice.assert_not_called()

    def test_notification_only_prepares_draft_and_preserves_existing_input(self):
        c=Client.__new__(Client);c.input='';c.lines=collections.deque();c.send=Mock()
        c.notification_action(dict(action='message',login='dthoo'))
        self.assertEqual(c.input,'/dm dthoo ');c.send.assert_not_called()
        c.input='unfinished message'
        c.notification_action(dict(action='message',login='thtay'))
        self.assertEqual(c.input,'unfinished message');self.assertEqual(c.pending_draft,'/dm thtay ')
        c.input='';c.tracking_command('/compose');self.assertEqual(c.input,'/dm thtay ')
        c.notification_action(dict(action='message',login='bad\n/send'));self.assertEqual(c.input,'/dm thtay ')

    def test_numeric_tracking_confirms_occupants_and_rejects_changed_seats(self):
        c=Client.__new__(Client);c.role='lobby';c.lines=collections.deque();c.tracker=Mock()
        c.popup_prompts=Mock();c.cluster_source=True
        c.tracker.resolve.side_effect=lambda values:[value.removeprefix('login:') for value in values]
        c.state={'players':[]};c.tracking_update=Mock()
        c.campus_selection={1:('dthoo',(1,2,3)),2:('thtay',(2,3,4))}
        c.cluster_players=[dict(name='dthoo',seat='c1r2s3'),dict(name='thtay',seat='c2r3s4')]
        c.tracking_command('/track 1 2')
        c.tracker.change.assert_not_called()
        confirm=c.popup_prompts.return_value.confirm
        self.assertIn('dthoo (c1r2s3)',confirm.call_args.args[0])
        confirm.call_args.args[1]()
        c.tracker.change.assert_called_once_with(['dthoo','thtay'])
        c.tracker.change.reset_mock()
        c.tracking_command('/track 1 2');c.cluster_players=[]
        confirm.call_args.args[1]();c.tracker.change.assert_not_called()
        c.popup_prompts.reset_mock();c.tracking_command('/track 999')
        c.popup_prompts.assert_not_called();c.tracker.change.assert_not_called()

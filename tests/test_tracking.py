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
        with patch('campus_lan.client.time.monotonic',return_value=100):c.tracking_tick();c.tracking_tick()
        c.send.assert_called_once_with(dict(type='command',text='/campus-presence'))
        self.assertEqual(c.track_next,400)
        self.assertNotIn('dthoo',json.dumps(c.send.call_args.args))

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
        c.campus_selection={2:('dthoo',(1,2,3)),4:('thtay',(2,3,4))}
        c.cluster_players=[dict(name='dthoo',seat='c1r2s3'),dict(name='thtay',seat='c2r3s4')]
        c.tracking_command('/track 2 4')
        c.tracker.change.assert_not_called()
        confirm=c.popup_prompts.return_value.confirm
        self.assertIn('dthoo (c1r2s3)',confirm.call_args.args[0])
        confirm.call_args.args[1]()
        c.tracker.change.assert_called_once_with(['dthoo','thtay'])
        c.tracker.change.reset_mock()
        c.tracking_command('/track 2 4');c.cluster_players=[]
        confirm.call_args.args[1]();c.tracker.change.assert_not_called()
        c.popup_prompts.reset_mock();c.tracking_command('/track 999')
        c.popup_prompts.assert_not_called();c.tracker.change.assert_not_called()

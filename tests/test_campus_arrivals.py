"""Opt-in campus arrival feed: silent baseline, private transient comparisons."""
import collections
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from campus_lan.tracking import Tracker,describe
from campus_lan.client import Client
from campus_lan.relationship_commands import configure


def person(name,seat='c1r1s1'):
    return dict(name=name,seat=seat,verified=True)

class CampusArrivals(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        p=patch('campus_lan.tracking.config_dir',return_value=Path(self.tmp.name));p.start();self.addCleanup(p.stop)
        self.tracker=Tracker('owner')

    def test_baseline_is_silent_then_new_untracked_people_arrive(self):
        t=self.tracker;t.set_arrivals(True)
        self.assertEqual(t.transitions([person('already-here')],'campus'),[])
        notices=t.transitions([person('already-here'),person('new-person','c2r3s4')],'campus')
        self.assertEqual(len(notices),1)
        self.assertEqual(notices[0]['login'],'new-person')
        self.assertEqual(notices[0]['reason'],'arrivals')
        self.assertIsNone(notices[0]['relationship'])
        self.assertEqual(t.names,[])
        moved=t.transitions([person('new-person','c2r3s5')],'campus')
        self.assertEqual(moved[0]['changes'],['seat'])
        self.assertEqual(moved[0]['previous_seat'],'c2r3s4')
        self.assertIn('Campus seat change',describe(moved[0])[0])
        departed=t.transitions([],'campus')
        self.assertEqual(departed[0]['changes'],['offline'])
        self.assertIn('no active seat',describe(departed[0])[0])
        self.assertEqual(len(t.transitions([person('new-person')],'campus')),1)

    def test_default_off_lobby_ignored_and_restart_rebaselines(self):
        t=self.tracker
        self.assertEqual(t.transitions([person('a')],'campus'),[])
        t.set_arrivals(True)
        self.assertEqual(t.transitions([person('a')],'lobby'),[])
        self.assertEqual(t.transitions([person('a')],'campus'),[])
        restarted=Tracker('owner')
        self.assertTrue(restarted.arrivals_enabled)
        self.assertIsNone(restarted.arrival_seen)
        self.assertEqual(restarted.transitions([person('a'),person('b')],'campus'),[])
        self.assertEqual(restarted.names,[])
        configure(restarted,['arrivals','off'])
        self.assertEqual(restarted.transitions([person('c')],'campus'),[])
        configure(restarted,['arrivals','on'])
        self.assertEqual(restarted.transitions([person('c')],'campus'),[])

    def test_arrivals_polls_without_personal_targets_and_has_no_names_on_wire(self):
        t=self.tracker;t.set_arrivals(True)
        c=Client.__new__(Client);c.name='owner';c.role='lobby';c.connected=True;c.id='id'
        c.tracker=t;c.send=Mock();c.local_api_command=Mock(return_value=False)
        c.track_next=0;c.track_pending=0
        with patch('campus_lan.client.time.monotonic',return_value=100):c.tracking_tick()
        self.assertEqual(c.track_next,130)
        c.send.assert_called_once_with(dict(type='command',text='/campus-presence'))

    def test_known_and_unknown_cohort_details_without_new_api_fetches(self):
        t=self.tracker;t.set_arrivals(True);t.transitions([],'campus')
        c=Client.__new__(Client);c.tracker=t;c.cohorts={'new-person':4};c.lines=collections.deque()
        c.notification_allowed=Mock(return_value=False)
        with patch('campus_lan.student_names.cached_name',return_value='Fixture Name'):
            c.tracking_update([person('new-person')],'campus')
        text=' '.join(c.lines)
        self.assertIn('Campus login: Fixture Name (new-person)',text)
        self.assertIn('Intake 4 (locally inferred)',text)
        self.assertNotIn('Your friend',text)
        notice=dict(login='unknown',reason='arrivals',seat='c1r1s2')
        self.assertIn('Intake unknown',describe(notice)[1])

    def test_failed_snapshot_does_not_reset_baseline(self):
        t=self.tracker;t.set_arrivals(True);t.transitions([person('a')],'campus')
        c=Client.__new__(Client);c.tracker=t;c.lines=collections.deque()
        c.tracking_update(None,'campus')
        self.assertEqual(t.arrival_seen,{'a':('c1r1s1',)})
        self.assertEqual(t.transitions([person('a')],'campus'),[])


    def test_multiple_active_seats_are_reported_as_a_set_not_order_dependent_moves(self):
        t=self.tracker;t.set_arrivals(True)
        a=person('student','c1r1s1');b=person('student','c2r2s2')
        self.assertEqual(t.transitions([a,b],'campus'),[])
        self.assertEqual(t.transitions([b,a],'campus'),[])
        changes=t.transitions([b],'campus')
        self.assertEqual(changes[0]['changes'],['seat'])
        self.assertEqual(changes[0]['previous_seat'],'c1r1s1 / c2r2s2')
        self.assertEqual(changes[0]['seat'],'c2r2s2')
        self.assertIn('active API locations changed',describe(changes[0])[1])

    def test_move_across_multiple_empty_polls_still_reports_new_location(self):
        t=self.tracker;t.set_arrivals(True)
        t.transitions([person('student','c1r1s1')],'campus')
        self.assertEqual(t.transitions([],'campus')[0]['changes'],['offline'])
        for _ in range(4):self.assertEqual(t.transitions([],'campus'),[])
        returned=t.transitions([person('student','c2r4s5')],'campus')
        self.assertEqual(len(returned),1)
        self.assertEqual(returned[0]['seat'],'c2r4s5')
        self.assertIn('Campus login',describe(returned[0])[0])

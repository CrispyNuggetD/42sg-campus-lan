import queue
import unittest
from unittest.mock import Mock,patch
from campus_lan.auth import AuthError
from campus_lan.client import Client
from campus_lan.announcement_client import HostWatch

class GuestHostGuidance(unittest.TestCase):
    def setUp(self):
        budget=patch('campus_lan.release_notices.reserve',return_value=True);budget.start();self.addCleanup(budget.stop)
    def client(self,secure=False,role='lobby'):
        c=Client.__new__(Client);c.lines=[];c.inbox=queue.Queue();c.connected=True;c.id='1';c.role=role;c.secure=secure;c.notify_enabled=True
        return c

    def test_on_campus_guest_is_guided_once_without_starting_signin(self):
        c=self.client();c.start_signin=Mock()
        with patch('campus_lan.auth_daily.current_seat',return_value='10.11.1.1'),patch('campus_lan.announcement_ui.HostWatch') as watch:
            c.announcement_tick();c.announcement_tick()
            self.assertEqual(' '.join(c.lines).count('You are on campus in guest mode'),1)
            self.assertIn('/clusters',' '.join(c.lines));self.assertIn('public trust',' '.join(c.lines))
            watch.assert_called_once();watch.return_value.start.assert_called_once();c.start_signin.assert_not_called()

    def test_offsite_verified_and_game_windows_do_not_get_guest_nudge(self):
        for secure,role,campus in ((False,'lobby',False),(True,'lobby',True),(False,'game',True)):
            c=self.client(secure,role)
            with patch('campus_lan.auth_daily.current_seat',side_effect=None if campus else AuthError('not campus')),patch('campus_lan.announcement_ui.HostWatch'):
                c.announcement_tick()
                self.assertFalse(c.lines)

    def test_initial_offline_status_is_reported_once_and_recovery_is_actionable(self):
        now=[0];inbox=queue.Queue();watch=HostWatch(inbox,clock=lambda:now[0])
        trust={'lobby_host':'10.11.1.1','lobby_port':31417}
        response=dict(owner='hnah',epoch='epoch',announcements=[],statuses=[],pending=[])
        with patch('campus_lan.announcement_client.HostSettings') as settings,patch('campus_lan.announcement_client.auth_client.load_trust',return_value=trust),patch('campus_lan.announcement_client.auth_locator.refresh'),patch('campus_lan.announcement_client.credentials',return_value={}),patch('campus_lan.announcement_client.auth_client.post',side_effect=[AuthError('offline'),AuthError('offline'),response]) as post:
            settings.return_value.data=dict(discovery=True,auto_join=True,interval=120)
            watch.step();first=inbox.get_nowait();self.assertFalse(first['online'])
            now[0]=120;watch.step();self.assertTrue(inbox.empty())
            now[0]=240;watch.step();online=inbox.get_nowait();self.assertTrue(online['recovered'])
            self.assertEqual(post.call_count,3)
        c=self.client();c.link_api_guest_node=Mock();c.desktop_notice=Mock();c.start_signin=Mock()
        online['auto_join']=False
        with patch('campus_lan.announcement_ui.claim',return_value=True):c.announcement_event(online)
        self.assertIn('/signin',' '.join(c.lines));self.assertIn('/clusters',' '.join(c.lines))
        c.desktop_notice.assert_called_once();c.start_signin.assert_not_called()

    def test_missing_trust_is_explained_without_network_or_spam(self):
        now=[0];inbox=queue.Queue();watch=HostWatch(inbox,clock=lambda:now[0])
        with patch('campus_lan.announcement_client.HostSettings') as settings,patch('campus_lan.announcement_client.auth_client.load_trust',side_effect=AuthError('not configured')),patch('campus_lan.announcement_client.auth_client.post') as post:
            settings.return_value.data=dict(discovery=True,auto_join=True,interval=120)
            watch.step();event=inbox.get_nowait();self.assertFalse(event['configured'])
            now[0]=120;watch.step();self.assertTrue(inbox.empty());post.assert_not_called()
        c=self.client();c.announcement_event(event)
        self.assertIn('public trust file/fingerprint',' '.join(c.lines))

    def test_arrival_bypasses_social_mute_and_respects_popup_deduplication(self):
        data=dict(owner='hnah',epoch='epoch',announcements=[],statuses=[],pending=[])
        event=dict(type='local_host_update',online=True,recovered=True,host='10.11.1.1',port=31417,auto_join=False,data=data)
        for enabled,claim_result,expected in ((False,True,1),(True,False,0),(True,True,1)):
            c=self.client();c.notify_enabled=enabled;c.desktop_notice=Mock();c.link_api_guest_node=Mock()
            with patch('campus_lan.announcement_ui.claim',return_value=claim_result):c.announcement_event(event)
            self.assertEqual(c.desktop_notice.call_count,expected)
            self.assertIn('/clusters',' '.join(c.lines))

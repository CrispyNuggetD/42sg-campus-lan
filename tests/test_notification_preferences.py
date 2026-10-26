import json
import os
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan.client import Client
from campus_lan.notification_preferences import Preferences, DEFAULTS
from campus_lan.auth import private_write
from campus_lan.popup_permissions import Permissions


class NotificationChannels(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp.name});env.start();self.addCleanup(env.stop)
        self.c=Client.__new__(Client);self.c.name='test';self.c.lines=[]
        self.c.notify_enabled=True;self.c.inbox=queue.Queue();self.c.tracking_notifier=Mock()
        self.c.link_api_guest_node=Mock();self.c.request_popup=Mock()

    def test_defaults_and_social_mute_keep_host_visible(self):
        c=self.c
        self.assertEqual({k:c.notification_allowed(k) for k in DEFAULTS},DEFAULTS)
        c.notification_command('/notify off')
        self.assertTrue(c.important_notification_allowed('host'))
        self.assertTrue(c.important_notification_allowed('announcements'))
        self.assertFalse(c.notification_allowed('tracking'))
        c.desktop_notice('Host online','ready','host',category='host')
        c.tracking_notifier.announcement.assert_called_once();c.request_popup.assert_not_called()

    def test_all_off_persists_and_is_an_actual_override(self):
        c=self.c;c.notification_command('/notify all off')
        for category in DEFAULTS:self.assertFalse(c.notification_allowed(category))
        c.desktop_notice('Host online','ready','host',category='host')
        c.tracking_notifier.announcement.assert_not_called()
        self.assertFalse(Preferences().allows('announcements'))
        c.notification_command('/notify all on');self.assertTrue(c.notification_allowed('host'))
        self.assertFalse(c.notification_allowed('dms'))
        c.notification_command('/settings notifications dms on')
        self.assertTrue(Preferences().allows('dms'))
        self.assertEqual(os.stat(Preferences().path).st_mode&0o777,0o600)

    def test_popup_denial_and_launch_override_block_important_notices(self):
        c=self.c;Permissions(c.name).set('notifications','deny')
        self.assertFalse(c.important_notification_allowed('host'))
        c.desktop_notice('warning','body','host',category='warnings')
        c.tracking_notifier.announcement.assert_not_called()
        Permissions(c.name).set('notifications','allow');c.notifications_disabled=True
        self.assertFalse(c.important_notification_allowed('announcements'))

    def test_muted_feed_keeps_terminal_but_no_broadcast_or_approval_popup(self):
        c=self.c;c.notification_command('/notify all off')
        data=dict(owner='hnah',epoch='e',statuses=[],pending=[dict(id='r',author='test',text='please')],
                  announcements=[dict(id='a',author='hnah',is_host=True,text='important')])
        with patch('campus_lan.announcement_ui.claim',return_value=True):
            c.announcement_event(dict(type='local_host_update',online=True,recovered=True,host='10.11.1.1',data=data))
        c.tracking_notifier.announcement.assert_not_called();c.tracking_notifier.approval.assert_not_called()
        self.assertIn('important',' '.join(c.lines));self.assertIn('/signin',' '.join(c.lines))

    def test_release_uses_pinned_host_metadata_and_no_first_contact_spam(self):
        c=self.c;c.desktop_notice=Mock();data=dict(version='2.3.0-beta.1',release_date='27 October',owner='hnah')
        now=[1_800_000_000]
        with patch('campus_lan.release_notices.time.time',side_effect=lambda:now[0]),patch('campus_lan.audio_quiet.active',return_value=False):
            c.release_notification(data);c.desktop_notice.assert_not_called()
            data['version']='2.3.1-beta.1';c.release_notification(data);c.release_notification(data)
            c.desktop_notice.assert_not_called()
            now[0]+=1800;c.release_notification(data)
            c.desktop_notice.assert_called_once()
            self.assertEqual(c.desktop_notice.call_args.kwargs['category'],'releases')
            c.notification_command('/notify releases off');data['version']='2.3.2-beta.1'
            c.release_notification(data);now[0]+=90000;c.release_notification(data)
            self.assertEqual(c.desktop_notice.call_count,1)

    def test_disabled_dms_still_arrive_in_terminal(self):
        c=self.c;c.secure=False
        c.inbox.put(dict(type='direct_message',sender='test',text='hello'))
        c.inbox.put(dict(type='direct_message',sender='test',text='uwu',uwu=True))
        c.uwu_notice=Mock();c.consume()
        c.uwu_notice.assert_not_called();c.request_popup.assert_not_called()
        self.assertIn('hello',' '.join(c.lines))

    def test_unreadable_preferences_fail_closed_and_invalid_command_does_not_write(self):
        private_write(Preferences().path,'[]')
        self.assertFalse(Preferences().allows('host'))
        before=Preferences().path.read_text();self.c.notification_command('/notify all maybe')
        self.assertEqual(Preferences().path.read_text(),before)

    def test_offline_warning_is_a_transition_not_a_polling_alert(self):
        c=self.c;c.desktop_notice=Mock();c.announcement_status=dict(online=True,epoch='e')
        event=dict(type='local_host_update',online=False,configured=True)
        with patch('campus_lan.announcement_ui.claim',return_value=True):
            c.announcement_event(event);c.announcement_event(event)
        c.desktop_notice.assert_called_once()
        self.assertEqual(c.desktop_notice.call_args.kwargs['category'],'warnings')

    def test_channel_specific_off_does_not_silence_other_important_channels(self):
        c=self.c;c.notification_command('/notify announcements off')
        self.assertFalse(c.important_notification_allowed('announcements'))
        self.assertTrue(c.important_notification_allowed('host'))
        self.assertTrue(c.important_notification_allowed('warnings'))

    def test_channel_changes_are_seen_by_other_open_windows(self):
        c=self.c
        other=Client.__new__(Client);other.notify_enabled=True;other.lines=[]
        c.notification_command('/notify off')
        self.assertFalse(other.notification_allowed('dms'))
        other.notification_command('/notify dms on')
        self.assertTrue(c.notification_allowed('dms'))
        other.notification_command('/notify all off')
        self.assertFalse(c.important_notification_allowed('host'))

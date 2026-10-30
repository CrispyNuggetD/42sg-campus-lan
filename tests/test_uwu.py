import collections
import os
import tempfile
import queue
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock,patch
from campus_lan import koel_sound
from campus_lan.koel_sound import AutoChoice
from campus_lan.client import Client
from campus_lan.server import Lobby
from campus_lan.desktop_notifications import Notifications

class Uwu(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary.name});env.start();self.addCleanup(env.stop)
        startup=patch('campus_lan.client._uwu_startup_owners',set());startup.start();self.addCleanup(startup.stop)
        config=patch('campus_lan.koel_sound.config_dir',return_value=Path(temporary.name))
        config.start();self.addCleanup(config.stop)
        quiet=patch('campus_lan.audio_quiet.active',return_value=False);quiet.start();self.addCleanup(quiet.stop)
        patcher=patch('campus_lan.volume.Volume');volume=patcher.start();self.addCleanup(patcher.stop)
        volume.return_value.get.return_value=50
        channels=patch('campus_lan.notification_preferences.Preferences.allows',return_value=True)
        channels.start();self.addCleanup(channels.stop)

    def client(self):
        client=Client.__new__(Client);client.name='recipient';client.lines=collections.deque()
        client.notify_enabled=True;client.inbox=queue.Queue();client.send=Mock()
        client.request_popup=Mock();client.tracking_notifier=Mock()
        return client

    def test_auto_defaults_off_reschedules_and_stops_without_sending(self):
        c=self.client()
        with patch('campus_lan.koel_sound.SoundChoice') as choice, patch('campus_lan.koel_sound.play') as play, patch('campus_lan.client.time.monotonic',return_value=100), patch('campus_lan.client.random.uniform',return_value=750) as interval:
            choice.return_value.read.return_value={'enabled':True}
            c.uwu_auto_tick()
            play.assert_not_called()
            c.uwu_command('/uwu auto')
            self.assertTrue(AutoChoice(c.name).read())
            self.assertEqual(c.uwu_auto_due,850)
            interval.assert_called_with(600,900)
            c.uwu_command('/uwu on')
            self.assertEqual(interval.call_count,1)
            c.uwu_auto_due=99
            c.uwu_auto_tick()
            play.assert_called_once_with()
            self.assertEqual(c.uwu_auto_due,850)
            c.uwu_command('/uwu off')
            self.assertIsNone(c.uwu_auto_due)
            self.assertFalse(AutoChoice(c.name).read())
            c.send.assert_not_called()

    def test_auto_requires_sound_consent_and_honors_revocation(self):
        c=self.client();c.popup_prompts=Mock()
        with patch('campus_lan.koel_sound.SoundChoice') as choice, patch('campus_lan.koel_sound.play') as play:
            choice.return_value.read.return_value={'enabled':False}
            c.uwu_command('/uwu on')
            c.popup_prompts.return_value.session_question.assert_called_once()
            self.assertIsNone(getattr(c,'uwu_auto_due',None))
            c.uwu_auto_due=0
            c.uwu_auto_enabled=True
            c.uwu_auto_tick()
            self.assertIsNone(c.uwu_auto_due)
            play.assert_not_called()

    def test_auto_choice_survives_new_window_and_waits_for_sound_consent(self):
        c=self.client();c.popup_prompts=Mock()
        with patch('campus_lan.koel_sound.SoundChoice') as sound,patch('campus_lan.client.time.monotonic',return_value=100),patch('campus_lan.client.random.uniform',return_value=700):
            sound.return_value.read.return_value={'enabled':True}
            c.uwu_command('/uwu auto')
            reopened=self.client();reopened.uwu_auto_enabled=AutoChoice(reopened.name).read()
            reopened.uwu_auto_tick()
            self.assertEqual(reopened.uwu_auto_due,800)
            sound.return_value.read.return_value={'enabled':False}
            reopened.uwu_auto_due=0;reopened.uwu_auto_tick()
            self.assertIsNone(reopened.uwu_auto_due)
            self.assertTrue(AutoChoice(reopened.name).read())

    def test_bare_uwu_invites_koeldrop_once_even_when_silent_without_starting_sharing(self):
        for enabled in (False,True):
            with self.subTest(enabled=enabled):
                c=self.client();c.popup_prompts=Mock();c.koel_command=Mock()
                with patch('campus_lan.koel_sound.SoundChoice') as choice,patch('campus_lan.koel_sound.play') as play:
                    choice.return_value.read.return_value={'enabled':enabled}
                    c.uwu_command('/uwu');c.uwu_command('/uwu')
                    output=' '.join(c.lines)
                    self.assertIn('koel',output);self.assertIn('carrier pigeon',output)
                    self.assertIn('Try /koel',output);self.assertIn('/koel help',output)
                    self.assertIn('separate approval',output)
                    self.assertEqual(output.count('Meet the koel:'),1)
                    c.koel_command.assert_not_called();c.send.assert_not_called()
                    self.assertEqual(play.call_count,2 if enabled else 0)
                    choice.return_value.choose.assert_not_called()

    def test_targeted_uwu_sends_command_without_local_play_or_setting_change(self):
        c=self.client()
        with patch('campus_lan.login_whitelist.allowed_logins',return_value={'dthoo'}),patch('campus_lan.koel_sound.play') as play:
            self.assertTrue(c.uwu_command('/uwu dthoo'))
            c.send.assert_called_once_with(dict(type='command',text='/uwu dthoo'))
            play.assert_not_called()
            c.uwu_command('/uwu bad target')
            self.assertEqual(c.send.call_count,1)
            self.assertNotIn('carrier pigeon',' '.join(c.lines))

    def test_receiver_uses_own_sound_choice_and_notification_permission(self):
        for enabled in (False,True):
            c=self.client();c.tracking_notifier=Mock()
            c.request_popup=Mock(side_effect=lambda category,description,action:action())
            with patch('campus_lan.koel_sound.SoundChoice') as choice:
                choice.return_value.read.return_value={'enabled':enabled}
                c.uwu_notice('sender')
                choice.assert_called_once_with('recipient')
                self.assertEqual(c.tracking_notifier.poke.call_args.kwargs['koel_sound'],enabled)
                self.assertEqual(c.request_popup.call_args.args[0],'notifications')

    def test_incoming_poke_is_private_notice_not_regular_dm(self):
        c=self.client();c.uwu_notice=Mock()
        c.inbox.put(dict(type='direct_message',sender='dthoo',text='uwu!',uwu=True))
        c.consume()
        c.uwu_notice.assert_called_once_with('dthoo')

    def test_mac_poke_uses_two_second_panel_and_no_sound_when_off(self):
        n=Notifications.__new__(Notifications)
        with patch('campus_lan.desktop_notifications.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target)), \
             patch('sys.platform','darwin'),patch('campus_lan.desktop_notifications.subprocess.run') as run, \
             patch('campus_lan.koel_sound.play') as play:
            n.poke('uwu','poke','sender',koel_sound=False)
            play.assert_not_called()
            command=run.call_args.args[0]
            self.assertIn('dateWithTimeIntervalSinceNow(Number(argv[2]))',command[4])
            self.assertEqual(command[-1],'2')
            self.assertIn('panel.close',command[4])

    def test_linux_fallback_expires_and_explicitly_closes_after_two_seconds(self):
        n=Notifications.__new__(Notifications)
        with patch('campus_lan.desktop_notifications.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target)), \
             patch('sys.platform','linux'),patch.dict('sys.modules',{'gi.repository':None}), \
             patch('campus_lan.desktop_notifications.shutil.which',return_value='/bin/tool'), \
             patch('campus_lan.desktop_notifications.subprocess.run',return_value=Mock(stdout='42\n')) as run, \
             patch('time.sleep') as sleep,patch('campus_lan.koel_sound.play') as play:
            n.poke('uwu','poke','sender',koel_sound=True)
            play.assert_called_once()
            self.assertIn('--expire-time=2000',run.call_args_list[0].args[0])
            self.assertIn('org.freedesktop.Notifications.CloseNotification',run.call_args_list[1].args[0])
            sleep.assert_called_once_with(2)

    def test_saved_auto_choice_is_shared_with_games_without_duplicate_playback(self):
        AutoChoice('recipient').set(True)
        c=self.client();c.role='game';c.uwu_auto_owner='old-guest';c.uwu_auto_enabled=False
        c.uwu_auto_due=None
        with patch('campus_lan.koel_sound.play') as play:
            c.uwu_auto_tick()
            self.assertTrue(c.uwu_auto_enabled);self.assertEqual(c.uwu_auto_owner,'recipient')
            self.assertIsNone(c.uwu_auto_due);play.assert_not_called()
            AutoChoice('recipient').set(False);c.sync_uwu_auto_choice(force=True)
            self.assertFalse(c.uwu_auto_enabled)

    def startup_client(self):
        AutoChoice('recipient').set(True)
        c=self.client();c.role='lobby';c.id='ready';c.connected=True
        c.uwu_auto_owner='recipient';c.uwu_auto_enabled=True;c.uwu_auto_due=None
        c.uwu_auto_startup_pending=True
        c.request_popup.side_effect=lambda category,description,action:action()
        return c

    def test_auto_on_chirps_at_hq_start_once_and_preserves_interval(self):
        with patch('campus_lan.koel_sound.SoundChoice') as choice,patch('campus_lan.koel_sound.play') as play, \
             patch('campus_lan.client.time.monotonic',return_value=100),patch('campus_lan.client.random.uniform',return_value=750):
            choice.return_value.read.return_value={'enabled':True}
            c=self.startup_client();c.uwu_auto_tick();c.uwu_auto_tick()
            play.assert_called_once();self.assertEqual(c.uwu_auto_due,850)
            c.tracking_notifier.poke.assert_called_once_with('uwu! · HQ started','Your local koel says hello.','recipient',koel_sound=False)
            reopened=self.startup_client();reopened.uwu_auto_tick()
            play.assert_called_once();self.assertTrue(AutoChoice('recipient').read())

    def test_quiet_startup_stays_on_without_replaying_a_delayed_chirp(self):
        with patch('campus_lan.koel_sound.SoundChoice') as choice,patch('campus_lan.koel_sound.play') as play, \
             patch('campus_lan.audio_quiet.active',return_value=True) as quiet, \
             patch('campus_lan.client.time.monotonic',return_value=100):
            choice.return_value.read.return_value={'enabled':True}
            c=self.startup_client();c.uwu_auto_tick();quiet.return_value=False;c.uwu_auto_tick()
            play.assert_not_called();self.assertTrue(c.uwu_auto_enabled)
            self.assertTrue(AutoChoice('recipient').read())

    def test_local_and_automatic_uwu_have_one_silent_desktop_toast_each(self):
        c=self.client();c.request_popup.side_effect=lambda category,description,action:action()
        with patch('campus_lan.koel_sound.SoundChoice') as choice,patch('campus_lan.koel_sound.play') as play, \
             patch('campus_lan.client.time.monotonic',return_value=100):
            choice.return_value.read.return_value={'enabled':True}
            c.uwu_command('/uwu');play.assert_called_once()
            c.tracking_notifier.poke.assert_called_once_with('uwu!','Your local koel says hello.','recipient',koel_sound=False)
            c.tracking_notifier.reset_mock();play.reset_mock()
            c.uwu_auto_enabled=True;c.uwu_auto_due=99;c.uwu_auto_tick()
            play.assert_called_once()
            c.tracking_notifier.poke.assert_called_once_with('uwu! · automatic call','Your local koel says hello.','recipient',koel_sound=False)

    def test_local_toasts_recheck_channel_and_popup_denial(self):
        from campus_lan.popup_permissions import Permissions
        c=self.client()
        c.local_uwu_notice();action=c.request_popup.call_args.args[2]
        with patch.object(c,'notification_allowed',return_value=False):
            self.assertFalse(action())
        Permissions(c.name).set('notifications','deny')
        self.assertFalse(action());c.tracking_notifier.poke.assert_not_called()


class Routing(unittest.IsolatedAsyncioTestCase):
    async def test_poke_routes_only_to_target_and_has_rate_limit(self):
        lobby=Lobby.__new__(Lobby);lobby.clients={1:dict(name='sender')};lobby.rooms={};lobby.auth_broker=None
        lobby.route_direct=AsyncMock(return_value=True);lobby.send=AsyncMock()
        await lobby.command(1,'/uwu dthoo')
        lobby.route_direct.assert_awaited_once_with(lobby.clients[1],'dthoo','uwu!',uwu=True)
        with self.assertRaisesRegex(ValueError,'two seconds'):await lobby.command(1,'/uwu dthoo')

if __name__=='__main__':unittest.main()

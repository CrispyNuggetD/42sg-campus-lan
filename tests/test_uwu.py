import collections
import queue
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,AsyncMock,patch
from campus_lan import koel_sound
from campus_lan.client import Client
from campus_lan.server import Lobby
from campus_lan.desktop_notifications import Notifications

class Uwu(unittest.TestCase):
    def client(self):
        client=Client.__new__(Client);client.name='recipient';client.lines=collections.deque()
        client.notify_enabled=True;client.inbox=queue.Queue();client.send=Mock()
        return client

    def test_targeted_uwu_sends_command_without_local_play_or_setting_change(self):
        c=self.client()
        with patch('campus_lan.koel_sound.play') as play:
            self.assertTrue(c.uwu_command('/uwu dthoo'))
            c.send.assert_called_once_with(dict(type='command',text='/uwu dthoo'))
            play.assert_not_called()
            c.uwu_command('/uwu bad target')
            self.assertEqual(c.send.call_count,1)

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

class Routing(unittest.IsolatedAsyncioTestCase):
    async def test_poke_routes_only_to_target_and_has_rate_limit(self):
        lobby=Lobby.__new__(Lobby);lobby.clients={1:dict(name='sender')};lobby.rooms={};lobby.auth_broker=None
        lobby.route_direct=AsyncMock(return_value=True);lobby.send=AsyncMock()
        await lobby.command(1,'/uwu dthoo')
        lobby.route_direct.assert_awaited_once_with(lobby.clients[1],'dthoo','uwu!',uwu=True)
        with self.assertRaisesRegex(ValueError,'two seconds'):await lobby.command(1,'/uwu dthoo')

if __name__=='__main__':unittest.main()

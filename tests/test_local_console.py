import collections
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.client import Client
from campus_lan.local_console import History,shell_command
from campus_lan.volume import Volume

class Console(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        patcher=patch('campus_lan.local_console.config_dir',return_value=Path(tmp.name));patcher.start();self.addCleanup(patcher.stop)

    def client(self):
        c=Client.__new__(Client);c.lines=collections.deque();c.popup_prompts=Mock();return c

    def test_history_persists_private_and_restores_draft(self):
        history=History();history.add('/who');history.add('/track 2 4');history.add('/track 2 4')
        self.assertEqual(history.move(-1,'draft'),'/track 2 4')
        self.assertEqual(history.move(-1,''),'/who')
        self.assertEqual(history.move(1,''),'/track 2 4')
        self.assertEqual(history.move(1,''),'draft')
        self.assertEqual(History().items,['/who','/track 2 4'])
        self.assertEqual(history.path.stat().st_mode&0o777,0o600)

    def test_native_backends_read_mute_and_set_slider(self):
        for backend,response in [('pactl',['Mute: yes','Volume: front-left: 32768 / 50%']),('wpctl',['Volume: 0.50 [MUTED]']),('mac',['50, true'])]:
            volume=Volume.__new__(Volume);volume.backend=backend
            with patch('campus_lan.volume.run',side_effect=response):self.assertEqual(volume.get(),0)
            with patch('campus_lan.volume.run') as run:
                self.assertEqual(volume.set(50),50)
                self.assertIn('50',str(run.call_args_list))
            with self.assertRaises(ValueError):volume.set(101)
        volume=Volume.__new__(Volume);volume.get=Mock(return_value=0);volume.set=Mock(side_effect=lambda n:n)
        self.assertEqual(volume.adjust(),50)
        volume.get.return_value=20;self.assertEqual(volume.adjust(),0)
        self.assertEqual(volume.adjust(73),73)

    def test_muted_sound_requires_two_separate_consents_and_off_reprompts(self):
        c=self.client();play=Mock()
        with patch('campus_lan.volume.Volume') as factory:
            volume=factory.return_value;volume.get.return_value=0
            c.with_audio_volume(play)
            volume.set.assert_not_called();play.assert_not_called()
            first=c.popup_prompts.return_value.confirm.call_args
            first.args[1]()
            volume.set.assert_called_once_with(50);play.assert_called_once()
            second=c.popup_prompts.return_value.confirm.call_args
            self.assertIn('Always',second.args[0]);second.args[1]()
            c.with_audio_volume(play);self.assertEqual(play.call_count,2)
            c.volume_command('/settings audio-auto-on off')
            c.with_audio_volume(play);self.assertEqual(play.call_count,2)

    def test_decline_never_changes_volume_or_plays(self):
        c=self.client();play=Mock()
        with patch('campus_lan.volume.Volume') as factory:
            factory.return_value.get.return_value=0;c.with_audio_volume(play)
            c.popup_prompts.return_value.confirm.call_args.args[2]()
            factory.return_value.set.assert_not_called();play.assert_not_called()

    def test_shell_uses_local_shell_and_restores_terminal(self):
        screen=Mock()
        with patch('campus_lan.local_console.curses') as curses,patch('campus_lan.local_console.subprocess.call',return_value=0) as call,patch('builtins.input'),patch.dict('os.environ',{'SHELL':'/bin/zsh'}):
            shell_command(screen,'adjust_volume 40')
            self.assertEqual(call.call_args.args[0],['/bin/zsh','-ic','adjust_volume 40'])
            self.assertEqual(call.call_args.kwargs['env']['LOGIN_STARTUP_SKIP'],'1')
            curses.endwin.assert_called_once();curses.reset_prog_mode.assert_called_once();screen.refresh.assert_called_once()

    def test_playback_error_is_not_retried(self):
        c=self.client();play=Mock(side_effect=OSError('no player'))
        with patch('campus_lan.volume.Volume') as factory:
            factory.return_value.get.return_value=50
            with self.assertRaises(OSError):c.with_audio_volume(play)
            play.assert_called_once()

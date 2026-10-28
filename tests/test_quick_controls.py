import curses
import unittest
from unittest.mock import Mock
from campus_lan.quick_controls import QuickControls


class Canvas:
    def getmaxyx(self):return 28,76


class Controls(QuickControls):
    def __init__(self):
        self.lines=[];self.input='draft';self.line=Mock()
        self.start_signin=Mock();self.settings_command=Mock()
        self.volume_command=Mock();self.uwu_command=Mock()


class QuickControlTests(unittest.TestCase):
    def test_f3_clusters_uses_local_access_or_existing_authenticated_command(self):
        c=Controls();c.local_api_command=Mock(return_value=False);c.send=Mock()
        self.assertTrue(c.quick_key(curses.KEY_F0+3))
        c.local_api_command.assert_called_once_with('/clusters')
        c.send.assert_called_once_with(dict(type='command',text='/clusters'))
        c.send.reset_mock();c.local_api_command.return_value=True
        c.quick_key(curses.KEY_F0+3);c.send.assert_not_called()
        c.role='game';c.local_api_command.reset_mock()
        c.quick_key(curses.KEY_F0+3);c.local_api_command.assert_not_called()

    def test_clickable_guest_prompt_and_signed_out_button(self):
        c=Controls();c.draw_quick_controls(Canvas())
        self.assertTrue(c.quick_click(20,25));c.start_signin.assert_called_once()
        c.secure=True;c.draw_quick_controls(Canvas());c.quick_key(curses.KEY_F2)
        c.settings_command.assert_called_once_with('/settings signout')
        self.assertEqual(c.input,'draft')

    def test_volume_and_uwu_reuse_local_consent_handlers(self):
        c=Controls()
        for key in (curses.KEY_F4,curses.KEY_F5,curses.KEY_F6,curses.KEY_F7):
            self.assertTrue(c.quick_key(key))
        self.assertEqual([x.args[0] for x in c.volume_command.call_args_list],['/volume 0','/volume'])
        self.assertEqual([x.args[0] for x in c.uwu_command.call_args_list],['/uwu','/uwu auto'])
        c.uwu_auto_due=10;c.quick_key(curses.KEY_F7)
        c.uwu_command.assert_called_with('/uwu off')
        self.assertFalse(c.quick_key(ord('a')))

    def test_modal_and_wizard_do_not_trigger_or_leave_click_targets(self):
        for field in ('permission_prompt','wizard'):
            c=Controls();c.draw_quick_controls(Canvas());setattr(c,field,True)
            c.draw_quick_controls(Canvas());self.assertEqual(c.control_hits,[])
            c.quick_key(curses.KEY_F2);c.quick_key(curses.KEY_F5)
            c.start_signin.assert_not_called();c.volume_command.assert_not_called()

    def test_game_account_control_does_not_change_identity(self):
        c=Controls();c.role='game';c.quick_key(curses.KEY_F2)
        c.start_signin.assert_not_called();self.assertIn('HQ',c.lines[-1])

    def test_footer_fits_minimum_width_and_auto_status(self):
        c=Controls();c.uwu_auto_due=0;c.draw_quick_controls(Canvas())
        self.assertEqual(len(c.control_hits),7)
        for row,left,right,action in c.control_hits:self.assertLessEqual(right,75)
        self.assertTrue(any('Auto:on' in call.args[2] for call in c.line.call_args_list))

    def test_shortcut_mute_blocks_automatic_volume_raise(self):
        from campus_lan.local_console import LocalConsole
        c=Controls();c.quick_key(curses.KEY_F4)
        action=Mock()
        LocalConsole.with_audio_volume(c,action)
        action.assert_not_called()
        self.assertTrue(c.shortcut_audio_muted)
        c.quick_key(curses.KEY_F5);self.assertFalse(c.shortcut_audio_muted)

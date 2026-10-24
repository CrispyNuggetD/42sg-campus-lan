import collections
import unittest
from unittest.mock import Mock
from campus_lan.client import Client
from campus_lan.completion import complete


class Settings(unittest.TestCase):
    def client(self,signed=False):
        c=Client.__new__(Client);c.name='hnah';c.secure=signed
        c.lines=collections.deque();c.send=Mock();c.start_signin=Mock()
        return c

    def test_menu_and_signed_out_guest(self):
        c=self.client();self.assertTrue(c.settings_command('/settings'))
        self.assertIn('/settings signout','\n'.join(c.lines))
        c.settings_command('/settings signout');c.send.assert_not_called()

    def test_signin_and_signout(self):
        c=self.client(True);c.settings_command('/settings signout')
        c.send.assert_called_once_with(dict(type='command',text='/signout'))
        c.settings_command('/profile signin');c.start_signin.assert_called_once()
        c.settings_command('/settings notifications off');self.assertFalse(c.notify_enabled)

    def test_completion_keeps_top_level_signin_unambiguous(self):
        self.assertEqual(complete('/sig')[0],'/signin ')
        self.assertEqual(complete('/settings signo')[0],'/settings signout ')
        self.assertEqual(complete('/settings notifications of')[0],'/settings notifications off ')
        self.assertIn('signout',complete('/settings ')[1])

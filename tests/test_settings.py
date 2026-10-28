import collections
import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan.client import Client
from campus_lan.completion import complete
from campus_lan.notification_preferences import Preferences


class Settings(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        whitelist=os.path.join(temporary.name,'singapore_intra.txt')
        with open(whitelist,'w') as output:output.write('fixture-one\n')
        environment=patch.dict(os.environ,{'XDG_CONFIG_HOME':temporary.name,'LAN42_INTRA_WHITELIST':whitelist})
        environment.start();self.addCleanup(environment.stop)

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
        c.settings_command('/settings notifications off')
        self.assertFalse(Preferences().allows('tracking'))
        self.assertTrue(Preferences().allows('host'))

    def test_completion_keeps_top_level_signin_unambiguous(self):
        self.assertEqual(complete('/sig')[0],'/signin ')
        self.assertEqual(complete('/settings signo')[0],'/settings signout ')
        self.assertEqual(complete('/settings notifications of')[0],'/settings notifications off ')
        self.assertIn('signout',complete('/settings ')[1])

    def test_profile_home_is_distinct_from_explicit_public_profile(self):
        c=self.client();c.open_urls=Mock()
        self.assertTrue(c.settings_command('/profile'))
        self.assertEqual(c.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/'])
        c.settings_command('/profile fixture-one')
        self.assertEqual(c.open_urls.call_args.args[1],['https://profile-v3.intra.42.fr/users/fixture-one'])

import unittest
from unittest.mock import Mock, patch
from campus_lan.auth import Broker, AuthError, digest
from campus_lan.forknite import launch


class Forknite(unittest.TestCase):
    def setUp(self):
        self.now = 100
        self.broker = Broker(Mock(), clock=lambda:self.now)
        self.session = 'a'*64
        self.broker.sessions[digest(self.session)] = dict(uid=42, login='hnah', expires=1000)

    @patch('campus_lan.forknite.shutil.which',return_value='/usr/bin/node')
    @patch('campus_lan.forknite.subprocess.Popen')
    def test_launch_uses_bundled_assets(self, popen, which):
        popen.return_value.wait.return_value = 0
        popen.return_value.returncode = 0
        launch(['--pipe','--count','50'])
        args = popen.call_args.args[0]
        self.assertTrue(args[1].endswith('/minigames/forknite/server.js'))
        self.assertEqual(args[2:],['--pipe','--count','50'])

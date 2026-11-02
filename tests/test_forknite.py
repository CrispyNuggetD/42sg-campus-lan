import unittest
import os
import tempfile
from pathlib import Path
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


class BonusLookup(unittest.TestCase):
    def test_configured_bonus_binary_and_missing_build(self):
        from campus_lan.forknite import ensure_binary
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'philo_bonus'
            binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o700)
            with patch.dict(os.environ,{'LAN42_PHILO_BONUS_BINARY':str(binary)}):
                self.assertEqual(ensure_binary('bonus'),str(binary))
                binary.unlink()
                with patch('campus_lan.forknite.subprocess.run') as make:
                    with self.assertRaisesRegex(ValueError,'did not produce'):ensure_binary('bonus')
                    make.assert_called_once_with(['make','-C',tmp],check=True,timeout=120)

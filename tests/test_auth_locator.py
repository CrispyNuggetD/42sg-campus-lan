import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from campus_lan import auth_locator
from campus_lan.auth import AuthError, config_dir, private_write


class Locator(unittest.TestCase):
    def test_discovery_requires_matching_pin_and_checks_live_host(self):
        trust = {'lobby_host': '10.11.1.1'}
        record = dict(version=1, seat='c2r4s14', fingerprint='pin')
        with patch.object(auth_locator, 'load_trust', return_value=trust), \
                patch.object(auth_locator, 'fingerprint', return_value='pin'), \
                patch.object(auth_locator, 'request_json', return_value=record), \
                patch.object(auth_locator, 'change_host') as change:
            auth_locator.refresh()
            change.assert_called_once_with('c2r4s14')
            change.reset_mock()
            for bad in ['wrong-pin', None]:
                record['fingerprint'] = bad
                auth_locator.refresh()
            change.assert_not_called()
            record['fingerprint'] = 'pin'
            record['seat'] = None
            auth_locator.refresh()
            change.assert_not_called()
            record['seat'] = 'c2r4s14'
            change.side_effect = AuthError('Wrong certificate')
            auth_locator.refresh()  # Failed discovery preserves existing trust.

    def test_publish_is_opt_in_and_exports_only_public_fields(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            self.assertFalse(auth_locator.publish('10.12.4.14'))
            remote = Path(directory) / 'remote.git'
            subprocess.run(['git', 'init', '--bare', '--quiet', str(remote)], check=True)
            private_write(config_dir() / 'auth-publish.json', json.dumps({'fingerprint': 'pin'}))
            trust = dict(lobby_host='10.12.4.14', client_secret='DO-NOT-EXPORT')
            with patch.object(auth_locator, 'REMOTE', str(remote)), \
                    patch.object(auth_locator, 'load_trust', return_value=trust), \
                    patch.object(auth_locator, 'fingerprint', return_value='pin'):
                self.assertTrue(auth_locator.publish('10.12.4.14'))
                self.assertFalse(auth_locator.publish('10.12.4.14'))
                trust['lobby_host'] = '10.11.3.2'
                self.assertTrue(auth_locator.publish('10.11.3.2'))
            def git(*args):
                return subprocess.check_output(['git', '--git-dir', str(remote), *args]).decode().strip()
            self.assertEqual(git('ls-tree', '--name-only', 'auth-seat'), 'seat.json')
            self.assertEqual(json.loads(git('show', 'auth-seat:seat.json')),
                             dict(version=1, seat='c1r3s2', fingerprint='pin'))
            self.assertEqual(git('rev-list', '--count', 'auth-seat'), '2')

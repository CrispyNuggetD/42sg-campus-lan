import asyncio
import json
import os
from pathlib import Path
import socket
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan import auth_daily, auth_client
from campus_lan.auth import AuthError, config_dir, private_write, private_read
from campus_lan.auth_server import setup, wait_for_host_move


class DailyAuth(unittest.TestCase):
    def test_student_dailylogin_does_not_start_auth_host(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}), \
                patch.object(auth_daily, 'systemctl') as control:
            self.assertIsNone(auth_daily.start())
            control.assert_not_called()

    def test_detects_and_checks_current_seat_address(self):
        with patch('socket.gethostname', return_value='c2r7s9.42singapore.sg'), \
                patch('socket.socket') as sockets:
            self.assertEqual(auth_daily.current_seat(), '10.12.7.9')
            sockets.return_value.__enter__.return_value.bind.assert_called_once_with(('10.12.7.9', 0))
            sockets.return_value.__enter__.return_value.bind.side_effect = OSError()
            with self.assertRaises(AuthError):
                auth_daily.current_seat()
        with patch('socket.gethostname', return_value='not-a-campus-seat'):
            with self.assertRaises(AuthError):
                auth_daily.current_seat()

    def test_owner_move_preserves_secret_key_and_pin_repeated_runs_keep_generation(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {'XDG_CONFIG_HOME': directory}):
            credentials = Path(directory) / 'app.env'
            private_write(credentials, 'FT42_CLIENT_ID=test-id\nFT42_CLIENT_SECRET=test-secret\n'
                'FT42_REDIRECT_URI=http://localhost:31415/callback\n')
            original = setup(credentials, '10.11.1.1')
            key = private_read(config_dir() / 'auth-key.pem')
            self.assertTrue(auth_daily.prepare('10.12.7.9'))
            settings = json.loads(private_read(config_dir() / 'auth-server.json'))
            moved = auth_client.load_trust()
            self.assertEqual(settings['host'], '10.12.7.9')
            self.assertEqual(settings['client_secret'], 'test-secret')
            self.assertEqual(moved['server_name'], '10.11.1.1')
            self.assertEqual(auth_client.fingerprint(original), auth_client.fingerprint(moved))
            self.assertEqual(key, private_read(config_dir() / 'auth-key.pem'))
            generation = settings['host_generation']
            self.assertFalse(auth_daily.prepare('10.12.7.9'))
            self.assertEqual(json.loads(private_read(config_dir() / 'auth-server.json'))['host_generation'], generation)
            self.assertTrue(auth_daily.install_unit())
            self.assertFalse(auth_daily.install_unit())
            unit = (Path(directory) / 'systemd/user/lan42-auth.service').read_text()
            self.assertIn('--current-seat', unit)
            self.assertNotIn('10.12.7.9', unit)
            self.assertNotIn('test-secret', unit)


class OldSeatRetirement(unittest.IsolatedAsyncioTestCase):
    async def test_old_service_stops_after_owner_moves(self):
        old = dict(host='10.11.1.1', host_generation='old')
        new = dict(host='10.12.7.9', host_generation='new')
        with patch('campus_lan.auth_server.private_read', return_value=json.dumps(new).encode()), \
                patch('campus_lan.auth_server.asyncio.sleep', new=unittest.mock.AsyncMock()):
            await asyncio.wait_for(wait_for_host_move(old), 1)

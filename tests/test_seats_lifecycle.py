import json
import os
from pathlib import Path
import signal
import socket
import tempfile
import time
import unittest
from unittest.mock import patch
from campus_lan.network import seat_address, ask_seat
from campus_lan.__main__ import start_background, probe

class Seats(unittest.TestCase):
    def test_mapping_and_invalid(self):
        self.assertEqual(seat_address('c1r2s3'),'10.11.2.3')
        self.assertEqual(seat_address('c2r4s9'),'10.12.4.9')
        for value in ('c3r2s3','c1r256s3','c1r0s3','10.*.2.3','c1r2s3;echo'):
            with self.assertRaises(ValueError):
                seat_address(value)

    def test_questions(self):
        with patch('builtins.input',side_effect=['2','4','9']):
            self.assertEqual(ask_seat(),'10.12.4.9')

    def test_background_survives_disconnect_and_is_reused(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port = sock.getsockname()[1]
        with tempfile.TemporaryDirectory() as temp:
            pid = None
            with patch.dict(os.environ,{'XDG_STATE_HOME':temp}):
                try:
                    start_background('127.0.0.1',port)
                    pid_path = Path(temp)/'42sg-campus-lan'/f'server-{port}.pid'
                    pid = int(pid_path.read_text())
                    with socket.create_connection(('127.0.0.1',port),timeout=2) as client:
                        client.sendall(b'{"type":"hello","protocol":1,"name":"tester","hostname":"test"}\n')
                        self.assertIn(b'welcome',client.recv(4096))
                    time.sleep(.15)
                    self.assertIsNotNone(probe('127.0.0.1',port))
                    start_background('127.0.0.1',port)
                    self.assertEqual(pid,int(pid_path.read_text()))
                    self.assertIsNotNone(probe('127.0.0.1',port))
                finally:
                    if pid:
                        os.kill(pid,signal.SIGTERM)
                        try:
                            os.waitpid(pid,0)
                        except ChildProcessError:
                            pass

if __name__=='__main__':
    unittest.main()

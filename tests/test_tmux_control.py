import unittest
from types import SimpleNamespace
from unittest.mock import patch
from campus_lan.tmux_control import restart_panes

class Restart(unittest.TestCase):
    def test_only_lan42_clients_receive_literal_restart(self):
        sent=[]
        def run(*args):
            if args[:2]==('tmux','list-panes'):
                return SimpleNamespace(returncode=0,stdout='%1\t101\tpython3\n%2\t102\tzsh\n%3\t103\tpython3\n%4\t104\tpython3\n')
            if args[0]=='ps':
                command={'101':'python3 -m campus_lan lobby','103':'python3 -m campus_lan server --managed','104':'python3 other.py'}[args[2]]
                return SimpleNamespace(returncode=0,stdout=command)
            sent.append(args);return SimpleNamespace(returncode=0,stdout='')
        with patch('campus_lan.tmux_control.run',side_effect=run):
            self.assertEqual(restart_panes(check=True),['%1']);self.assertFalse(sent)
            self.assertEqual(restart_panes(),['%1'])
        self.assertEqual(sent,[('tmux','send-keys','-t','%1','C-u'),('tmux','send-keys','-t','%1','-l','/restart'),('tmux','send-keys','-t','%1','Enter')])

    def test_restart_waits_for_node_lock_after_listener_closes(self):
        import fcntl
        import tempfile
        from pathlib import Path
        from campus_lan.__main__ import local_node_busy
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.__main__.runtime_dir',return_value=Path(tmp)),patch('campus_lan.__main__.probe',return_value=None):
            self.assertFalse(local_node_busy('127.0.0.1',31415))
            with (Path(tmp)/'server-31415.pid').open('w') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                self.assertTrue(local_node_busy('127.0.0.1',31415))
                fcntl.flock(lock,fcntl.LOCK_UN)
                self.assertFalse(local_node_busy('127.0.0.1',31415))

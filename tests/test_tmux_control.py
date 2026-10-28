import unittest
from types import SimpleNamespace
from unittest.mock import patch
from campus_lan.tmux_control import close_miniapp_window,refresh_cluster_window,restart_panes

class Restart(unittest.TestCase):
    def test_focus_refresh_signals_only_verified_clusters_python_process(self):
        import os
        def fake_run(*args):
            if args[1]=='list-windows':return SimpleNamespace(returncode=0,stdout='@7\tlan42-clusters\n')
            if args[1]=='display-message':return SimpleNamespace(returncode=0,stdout='123\tPython\t1\n')
            if args[0]=='ps':return SimpleNamespace(returncode=0,stdout='python3 -m campus_lan clusters --cluster 0\n')
            raise AssertionError(args)
        with patch.dict(os.environ,{'LAN42_TMUX_SESSION':'LAN42'}),patch('campus_lan.tmux_control.run',side_effect=fake_run),patch('campus_lan.tmux_control.os.kill') as kill:
            self.assertTrue(refresh_cluster_window())
            kill.assert_called_once()
        with patch('campus_lan.tmux_control.run',side_effect=lambda *args:SimpleNamespace(returncode=0,stdout='@7\tlan42\n' if args[1]=='list-windows' else '')),patch('campus_lan.tmux_control.os.kill') as kill:
            self.assertFalse(refresh_cluster_window())
            kill.assert_not_called()

    def test_finished_miniapp_closes_only_its_own_single_pane_window(self):
        import os
        for role,allowed in [('lan42-clusters',True),('lan42-game-123',True),('lan42-admin-123',True),('lan42',False),('current-project',False)]:
            calls=[]
            def fake_run(*args):
                calls.append(args)
                if args[1]=='display-message':
                    return SimpleNamespace(returncode=0,stdout='@7\t'+role+'\t'+str(os.getpid())+'\t1\n')
                return SimpleNamespace(returncode=0,stdout='')
            with patch.dict(os.environ,{'TMUX_PANE':'%9'}),patch('campus_lan.tmux_control.run',side_effect=fake_run):
                self.assertEqual(close_miniapp_window(),allowed)
            self.assertEqual(any(call[1]=='kill-window' for call in calls),allowed)
        with patch.dict(os.environ,{'TMUX_PANE':'%9'}),patch('campus_lan.tmux_control.run',return_value=SimpleNamespace(returncode=0,stdout='@7\tlan42-game-123\t999999\t1\n')) as run:
            self.assertFalse(close_miniapp_window())
            run.assert_called_once()

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

    def test_restart_lock_probe_supports_nfs_exclusive_lock_requirements(self):
        import errno
        import fcntl
        import os
        import tempfile
        from pathlib import Path
        from campus_lan.__main__ import local_node_busy
        real_flock=fcntl.flock
        def nfs_flock(handle,operation):
            mode=fcntl.fcntl(handle,fcntl.F_GETFL)&os.O_ACCMODE
            if operation&fcntl.LOCK_EX and mode==os.O_RDONLY:
                raise OSError(errno.EBADF,'NFS exclusive lock needs write access')
            return real_flock(handle,operation)
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.__main__.runtime_dir',return_value=Path(tmp)),patch('campus_lan.__main__.probe',return_value=None):
            path=Path(tmp)/'server-31415.pid';path.write_text('12345')
            with patch('campus_lan.__main__.fcntl.flock',side_effect=nfs_flock):
                self.assertFalse(local_node_busy('127.0.0.1',31415))
            self.assertEqual(path.read_text(),'12345')

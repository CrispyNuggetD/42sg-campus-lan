import importlib.util
from pathlib import Path
import os
import shlex
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('open_terminal', ROOT/'useful-scripts/open_terminal.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class TerminalSetup(unittest.TestCase):
    def test_mac_quotes_path_as_one_argument(self):
        repo = Path("/tmp/a friend's $(echo nope) clone")
        cmd = module.terminal_command(repo, 'darwin')
        self.assertEqual(shlex.split(cmd[-1]), ['sh', str(repo/'lan42.sh')])
        self.assertIn('do script', cmd[2])

    def test_linux_terminal_and_missing_desktop(self):
        with patch.dict(os.environ, {'DAILY_TMUX_HELPER': ''}):
            cmd = module.terminal_command(ROOT, 'linux', lambda n: '/usr/bin/xterm' if n=='xterm' else None)
            self.assertEqual(cmd[-3:], ['-e', 'sh', str(ROOT/'lan42.sh')])
            with self.assertRaises(RuntimeError):
                module.terminal_command(ROOT, 'linux', lambda n: None)

    def test_setup_defaults_to_append_and_opt_out_leaves_rc(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = Path(tmp)/'.zshrc'
            original = '# personal settings without final newline'
            rc.write_text(original)
            env = dict(os.environ, ZDOTDIR=tmp, LAN42_NO_UPDATE='1')
            subprocess.run(['sh', str(ROOT/'setup.sh'), '--no-zsh'], env=env, check=True, capture_output=True)
            self.assertEqual(rc.read_text(), original)
            subprocess.run(['sh', str(ROOT/'setup.sh')], env=env, check=True, capture_output=True)
            self.assertTrue(rc.read_text().startswith(original))
            self.assertIn('campus.zsh', rc.read_text())
            before = rc.read_text()
            subprocess.run(['sh', str(ROOT/'setup.sh')], env=env, check=True, capture_output=True)
            self.assertEqual(rc.read_text(), before)

    def test_dailylogin_requests_window_without_running_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake = Path(tmp)/'python3'
            fake.write_text('#!/bin/sh\nprintf "WINDOW:%s\\n" "$1"\n')
            fake.chmod(0o700)
            env = dict(os.environ, PATH=tmp+os.pathsep+os.environ['PATH'])
            result = subprocess.run(['zsh','-f','-c', '''
# zshenv may prepend pyenv shims even with -f; keep this test off the desktop.
export PATH="$2"
unset DAILY_TMUX_HELPER
source "$1"
lan42_pull() { print MOCK_PULL; }
dailylogin
''', 'test', str(ROOT/'useful-scripts/campus.zsh'), env['PATH']], env=env, check=True, text=True, capture_output=True)
            self.assertIn('MOCK_PULL', result.stdout)
            self.assertIn('WINDOW:'+str(ROOT/'useful-scripts/open_terminal.py'), result.stdout)

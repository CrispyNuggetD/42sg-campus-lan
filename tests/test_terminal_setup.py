import importlib.util
from pathlib import Path
import os
import sys
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
    def test_standalone_uses_bundled_tmux_on_mac_and_linux(self):
        with patch.dict(os.environ, {'DAILY_TMUX_HELPER': ''}):
            for platform in ('darwin', 'linux'):
                command = module.terminal_command(ROOT, platform)
                self.assertEqual(command[1], str(ROOT/'useful-scripts/tmux_workspace.py'))
                self.assertEqual(command[-2:], ['sh', str(ROOT/'lan42.sh')])
                self.assertIn('lan42', command)

    def test_paths_with_shell_metacharacters_are_literal_arguments(self):
        with tempfile.TemporaryDirectory(prefix="friend's $(echo nope) ") as tmp:
            repo = Path(tmp)
            (repo/'useful-scripts').mkdir()
            (repo/'useful-scripts/tmux_workspace.py').touch()
            with patch.dict(os.environ, {'DAILY_TMUX_HELPER': ''}):
                command = module.terminal_command(repo, 'darwin')
            self.assertEqual(command[-1], str(repo/'lan42.sh'))
            self.assertEqual(command[1], str(repo/'useful-scripts/tmux_workspace.py'))

    def test_mac_and_linux_use_shared_tmux_helper_for_games(self):
        with tempfile.TemporaryDirectory() as tmp:
            helper = Path(tmp)/'daily helper.py'
            helper.touch()
            for platform in ('darwin', 'linux'):
                with patch.dict(os.environ, {'DAILY_TMUX_HELPER': str(helper)}):
                    command = module.terminal_command(ROOT, platform, args=('game', 'pong'))
                    self.assertEqual(command[1], str(helper))
                    self.assertIn('lan42-game-' + str(os.getpid()), command)
                    self.assertIn('LAN42_NO_UPDATE=1', command)
                    self.assertNotIn('osascript', command)

    def test_clusters_reuse_a_named_window_in_lan42_tmux_on_both_platforms(self):
        with patch.dict(os.environ,{'DAILY_TMUX_HELPER':''}):
            for platform in ('darwin','linux'):
                command=module.terminal_command(ROOT,platform,args=('clusters','--cluster','2'))
                self.assertIn('lan42-clusters',command)
                self.assertEqual(command[-3:],['clusters','--cluster','2'])
                self.assertIn('LAN42_NO_UPDATE=1',command)

    def test_missing_tmux_has_platform_install_hint(self):
        for platform, hint in [('linux', 'setup.sh'), ('darwin', 'setup.sh')]:
            with patch.object(module.sys, 'platform', platform), patch.object(module.shutil, 'which', return_value=None):
                with self.assertRaisesRegex(RuntimeError, hint):
                    module.main()

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

    def test_declining_optional_tmux_keeps_direct_launcher_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);bin=root/'bin';bin.mkdir()
            (bin/'python3').symlink_to(sys.executable)
            # Use system utilities only; exclude Homebrew's installed tmux.
            env=dict(os.environ,PATH=str(bin)+':/usr/bin:/bin',FORTYTWO_TOOLS_ROOT=str(root/'tools'),ZDOTDIR=tmp)
            if subprocess.run(['sh','-c','command -v tmux'],env=env,capture_output=True).returncode==0:
                self.skipTest('system PATH already provides tmux')
            result=subprocess.run(['sh',str(ROOT/'setup.sh'),'--no-zsh'],env=env,input='n\n',text=True,capture_output=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('Optional: tmux',result.stderr)
            self.assertIn('still ready',result.stdout)
            self.assertFalse((root/'tools').exists())

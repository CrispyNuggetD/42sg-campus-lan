"""Exercise real setup shell control flow with fake iSH files/tools; no downloads."""
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class IshSetup(unittest.TestCase):
    def attempt(self, answer, compatible=False, fail_apk=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'proc/ish').mkdir(parents=True)
            (root/'useful-scripts').mkdir()
            (root/'useful-scripts/setup_python.sh').write_text(
                (ROOT/'useful-scripts/setup_python.sh').read_text())
            binary = root/'bin'; binary.mkdir()
            def tool(name, text):
                path = binary/name
                path.write_text('#!/bin/sh\n'+text+'\n'); path.chmod(0o700)
            tool('apk', 'echo "$*" >> "$TEST_ROOT/apk-calls"\n'
                 'case "$1" in info) exit 1;; add) touch "$TEST_ROOT/ready";; esac\n'
                 + ('exit 1' if fail_apk else 'exit 0'))
            tool('python3', '[ -f "$TEST_ROOT/ready" ]')
            tool('git', 'exit 0')
            if compatible: (root/'ready').touch()
            # Run the bootstrap portion in isolation, using a temporary proc tree.
            source = (ROOT/'setup.sh').read_text().split('setup_python || exit 1')[0]
            source = source.replace('/proc/ish', str(root/'proc/ish')).replace('/proc/version', str(root/'proc/version'))
            (root/'setup.sh').write_text(source+'echo BOOTSTRAP_READY\n')
            result = subprocess.run(['sh', str(root/'setup.sh'), '--no-zsh'],
                input=answer, text=True, capture_output=True,
                env=dict(os.environ, PATH=str(binary)+':/usr/bin:/bin', TEST_ROOT=tmp))
            calls = (root/'apk-calls').read_text()
            return result, calls

    def test_installs_alpine_packages_and_rechecks_python(self):
        result, calls = self.attempt('y\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Detected iSH', result.stdout)
        self.assertIn('update\nadd ', calls)
        self.assertIn('python3', calls)
        self.assertIn('ncurses-terminfo', calls)
        self.assertNotIn('zsh', calls)
        self.assertNotIn('upgrade', calls)

    def test_decline_or_eof_stops_without_python_or_downloads(self):
        for answer in ('n\n', ''):
            result, calls = self.attempt(answer)
            self.assertNotEqual(result.returncode, 0)
            self.assertNotIn('update', calls)
            self.assertIn('no uv runtime', result.stderr)

    def test_decline_optional_packages_keeps_existing_python(self):
        result, calls = self.attempt('n\n', compatible=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('BOOTSTRAP_READY', result.stdout)
        self.assertNotIn('update', calls)

    def test_failed_apk_stops_before_runtime_recovery(self):
        result, calls = self.attempt('y\n', fail_apk=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('package setup failed', result.stderr)
        self.assertNotIn('add ', calls)


class IshZshSetup(unittest.TestCase):
    def attempt(self, answer, no_zsh=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'proc/ish').mkdir(parents=True)
            binary = root/'bin'; binary.mkdir()
            helpers = root/'useful-scripts'; helpers.mkdir()
            for name in ('setup_python.sh', 'install_zsh.py', 'ensure_tmux.py', 'install_ish_shell.py'):
                shutil.copy2(ROOT/'useful-scripts'/name, helpers/name)
            (root/'lan42.sh').touch()
            (helpers/'campus.zsh').touch()
            for name in ('dirname', 'grep'):
                (binary/name).symlink_to(shutil.which(name))
            (binary/'python3').symlink_to(sys.executable)
            def tool(name, source):
                p = binary/name
                p.write_text('#!/bin/sh\n'+source+'\n'); p.chmod(0o700)
            tool('git', 'exit 0')
            tool('tmux', 'echo tmux-test')
            tool('apk', 'echo "$*" >> "$TEST_ROOT/calls"\n'
                 'if [ "$1" = add ] && [ "$2" = zsh ]; then\n'
                 '  printf "#!/bin/sh\\nexit 0\\n" > "$TEST_ROOT/bin/zsh"\n'
                 '  /bin/chmod +x "$TEST_ROOT/bin/zsh"\nfi\nexit 0')
            source = (ROOT/'setup.sh').read_text().replace('/proc/ish', str(root/'proc/ish'))
            (root/'setup.sh').write_text(source)
            result = subprocess.run(['/bin/sh', str(root/'setup.sh'), *(['--no-zsh'] if no_zsh else [])],
                input=answer, text=True, capture_output=True,
                env=dict(os.environ, PATH=str(binary), HOME=tmp, ZDOTDIR=tmp,
                         FORTYTWO_TOOLS_ROOT=str(root/'tools'), TEST_ROOT=tmp))
            rc = (root/'.zshrc').read_text() if (root/'.zshrc').exists() else ''
            return result, (root/'calls').read_text(), rc

    def test_zsh_is_offered_after_basic_dependencies_are_already_installed(self):
        result, calls, rc = self.attempt('y\n')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Install zsh', result.stderr)
        self.assertIn('add zsh', calls)
        self.assertIn('campus.zsh', rc)
        self.assertIn('Fresh iSH main shell: lan42', result.stdout)

    def test_decline_or_no_zsh_preserves_direct_launch(self):
        for answer, optout in [('n\n', False), ('', True)]:
            result, calls, rc = self.attempt(answer, optout)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('add zsh', calls)
            self.assertEqual(rc, '')
            self.assertIn('sh lan42.sh', result.stdout)

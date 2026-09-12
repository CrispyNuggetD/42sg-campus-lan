import importlib.util
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('install_zsh', ROOT/'useful-scripts/install_zsh.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class Installer(unittest.TestCase):
    def test_preserves_config_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(prefix='campus zsh ') as tmp:
            rc = Path(tmp)/'.zshrc'
            original = '# My settings\nexport EDITOR=vim\ndailylogin() { echo mine; }\n'
            rc.write_text(original)
            self.assertTrue(module.install(ROOT,rc))
            self.assertTrue(rc.read_text().startswith(original))
            self.assertFalse(module.install(ROOT,rc))
            self.assertEqual(rc.read_text().count(module.START),1)
            backups = list(Path(tmp).glob('.zshrc.lan42-backup-*'))
            self.assertEqual(len(backups),1)
            self.assertEqual(backups[0].read_text(),original)

    def test_rejects_broken_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc = Path(tmp)/'.zshrc'
            rc.write_text(module.START)
            with self.assertRaises(ValueError):
                module.install(ROOT,rc)
            self.assertEqual(rc.read_text(),module.START)

@unittest.skipUnless(shutil.which('zsh'),'zsh unavailable')
class Helpers(unittest.TestCase):
    def run_zsh(self,script):
        return subprocess.run(['zsh','-f','-c',script,'test',str(ROOT/'useful-scripts/campus.zsh')],
                              text=True,capture_output=True,check=True).stdout

    def test_existing_functions_and_aliases_survive(self):
        result = self.run_zsh("""
dailylogin() { print PERSONAL; }
alias run='echo CUSTOM'
source "$1"
dailylogin
alias run
whence lan42_dailylogin
""")
        self.assertIn('PERSONAL',result)
        self.assertIn('CUSTOM',result)
        self.assertIn('lan42_dailylogin',result)

    def test_default_and_reload(self):
        result = self.run_zsh("""
source "$1"
print "$LAN42_PULL_OTHER_REPOS"
lan42_pull() { print MOCK_PULL; }
dailylogin
whence syncdocs compile
""")
        self.assertIn('0\n',result)
        self.assertEqual(result.count('MOCK_PULL'),1)
        self.assertIn('Campus helpers reloaded',result)

    def test_missing_project_does_not_change_directory(self):
        result = self.run_zsh("""
source "$1"
LAN42_MAIN_REPO_ROOT=''
before="$PWD"
lan42_cdmain
[[ "$before" == "$PWD" ]] || exit 3
print UNCHANGED
""")
        self.assertIn('UNCHANGED',result)

if __name__=='__main__':
    unittest.main()

"""Fresh POSIX shell resolves LAN42 and delegates literal arguments correctly."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('ish_shell',ROOT/'useful-scripts/install_ish_shell.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class IshMainShell(unittest.TestCase):
    def test_fresh_main_shell_launches_zsh_without_manual_shell_switch(self):
        with tempfile.TemporaryDirectory(prefix="lan42 user's ") as tmp:
            root=Path(tmp);repo=root/'repo';(repo/'useful-scripts').mkdir(parents=True)
            (repo/'useful-scripts/campus.zsh').write_text('lan42() { printf "ARG:%s\\n" "$@"; }\n')
            profile=root/'.profile';profile.write_text('# personal setting\n')
            self.assertTrue(module.install(repo,profile))
            self.assertFalse(module.install(repo,profile))
            result=subprocess.run(['sh','-c','. "$1"; lan42 join "$2"','test',str(profile),'name $(touch SHOULD_NOT_EXIST)'],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('ARG:join',result.stdout)
            self.assertIn('ARG:name $(touch SHOULD_NOT_EXIST)',result.stdout)
            self.assertTrue(profile.read_text().startswith('# personal setting\n'))
            self.assertFalse(Path('SHOULD_NOT_EXIST').exists())

    def test_no_zsh_option_provides_direct_command_and_preserves_other_profile_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);repo=root/'repo';repo.mkdir()
            (repo/'lan42.sh').write_text('printf "DIRECT:%s\\n" "$@"\n')
            profile=root/'.profile';profile.write_text('# keep me')
            module.install(repo,profile,use_zsh=False)
            result=subprocess.run(['sh','-c','. "$1"; lan42 --version','test',str(profile)],text=True,capture_output=True)
            self.assertEqual(result.stdout,'DIRECT:--version\n')
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertNotIn('zsh -ic',profile.read_text())

    def test_moved_clone_replaces_only_owned_block_with_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);profile=root/'.profile'
            profile.write_text('# before\n')
            module.install(root/'old',profile)
            profile.write_text(profile.read_text()+'# after\n')
            module.install(root/'new',profile)
            text=profile.read_text()
            self.assertEqual(text.count(module.START),1)
            self.assertTrue(text.startswith('# before\n'))
            self.assertTrue(text.endswith('# after\n'))
            self.assertNotIn(str(root/'old'),text)
            self.assertTrue(list(root.glob('.profile.lan42-backup-*')))

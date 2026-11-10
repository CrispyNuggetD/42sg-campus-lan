"""External launcher checks: no network, browser, real credentials or game builds."""
import io
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import Mock, patch
from campus_lan import core_game as core
from campus_lan.client import Client
from campus_lan.completion import complete


class CoreLauncher(unittest.TestCase):
    def client(self):
        c=Client.__new__(Client)
        c.lines=[];c.open_urls=Mock();c.request_popup=Mock();c.send=Mock()
        return c

    def test_browser_uses_only_fixed_public_urls_and_no_session(self):
        for action,url in [('',core.SITE),('signin',core.SITE),('visualizer',core.VISUALIZER),('source',core.SOURCE)]:
            c=self.client();c.auth_session={'token':'never-send-this'}
            self.assertTrue(c.core_command('/core '+action))
            self.assertEqual(c.open_urls.call_args.args[:2],('browser',[url]))
            c.send.assert_not_called()
            self.assertNotIn('never-send-this',str(c.open_urls.call_args))

    def test_clone_requires_popup_consent_and_uses_argument_list(self):
        c=self.client()
        with patch('campus_lan.client.subprocess.run') as run:
            self.assertTrue(c.core_command('/core clone'))
            run.assert_not_called()
            self.assertEqual(c.request_popup.call_args.args[0],'terminals')
            run.return_value.returncode=0
            c.request_popup.call_args.args[2]()
            args=run.call_args.args[0]
            self.assertEqual(args[-3:],['-m','campus_lan.core_game','clone'])
            self.assertIn('core-source',args)
            self.assertFalse(run.call_args.kwargs.get('shell',False))

    def test_invalid_input_cannot_become_url_or_shell_command(self):
        c=self.client()
        for text in ('/core https://evil.invalid','/core clone ; touch nope','/core signin other'):
            self.assertTrue(c.core_command(text))
        self.assertFalse(c.core_command('/core-other'))
        c.open_urls.assert_not_called();c.request_popup.assert_not_called()

    def test_separate_clone_never_builds_or_recurses_into_submodules(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'LAN42_CORE_CLONE':d+'/CORE Game'}), \
             patch.object(core.shutil,'which',return_value='/usr/bin/git'), \
             patch.object(core.subprocess,'run') as run, redirect_stdout(io.StringIO()):
            core.clone()
            run.assert_called_once_with(['git','clone','--depth','1','--',core.SOURCE+'.git',d+'/CORE Game'],check=True)

    def test_existing_clone_preserved_and_other_origins_rejected(self):
        with tempfile.TemporaryDirectory() as d, patch.dict(os.environ,{'LAN42_CORE_CLONE':d}), \
             patch.object(core.subprocess,'run') as run, redirect_stdout(io.StringIO()):
            (Path(d)/'.git').mkdir()
            run.return_value.stdout=core.SOURCE+'.git\n'
            core.clone()
            run.assert_called_once()
            run.return_value.stdout='https://example.invalid/other.git\n'
            with self.assertRaises(RuntimeError):core.clone()
            self.assertTrue((Path(d)/'.git').is_dir())

    def test_existing_nonrepo_or_symlink_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d, patch.object(core.subprocess,'run') as run:
            dest=Path(d)/'existing';dest.mkdir()
            link=Path(d)/'link';link.symlink_to(dest)
            for path in (dest,link):
                with patch.dict(os.environ,{'LAN42_CORE_CLONE':str(path)}):
                    with self.assertRaises(RuntimeError):core.clone()
            run.assert_not_called()

    def test_cli_browser_failure_and_clone_failure_return_nonzero(self):
        with patch.object(core.webbrowser,'open_new_tab',return_value=False), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(core.main(['signin']),1)
        with patch.object(core,'clone',side_effect=RuntimeError('failed')), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            self.assertEqual(core.main(['clone']),1)

    def test_completion(self):
        self.assertEqual(complete('/cor')[0],'/core ')
        self.assertEqual(complete('/core cl')[0],'/core clone ')


if __name__=='__main__':unittest.main()

import subprocess
import unittest
from unittest.mock import patch, Mock
from campus_lan.updater import update_checkout, restart
from campus_lan import updater


class UpdaterTests(unittest.TestCase):
    @patch('campus_lan.updater.subprocess.run')
    def test_dirty_checkout_never_pulls(self, run):
        run.return_value = Mock(stdout=' M local.py\n')
        self.assertFalse(update_checkout('/example'))
        self.assertEqual(run.call_count, 1)

    @patch('campus_lan.updater.subprocess.run')
    def test_clean_checkout_uses_fast_forward(self, run):
        run.side_effect = [Mock(stdout=''), Mock(stdout='Already up to date.')]
        self.assertTrue(update_checkout('/example'))
        self.assertEqual(run.call_args.args[0][-2:], ['pull', '--ff-only'])
        self.assertEqual(run.call_args.kwargs['env']['GIT_TERMINAL_PROMPT'], '0')

    @patch('campus_lan.updater.subprocess.run', side_effect=subprocess.TimeoutExpired('git', 60))
    def test_pull_failure_preserves_checkout(self, run):
        self.assertFalse(update_checkout('/example'))

    @patch('campus_lan.updater.os.execve')
    @patch('campus_lan.updater.update_checkout')
    def test_restart_retains_arguments_and_skips_second_pull(self, update, execute):
        with patch('campus_lan.updater.sys.argv', ['campus_lan','lobby','--port','31416']):
            restart(True, wait_for_node=lambda: False)
        update.assert_called_once()
        program, args, env = execute.call_args.args
        self.assertEqual(program, '/bin/sh')
        self.assertEqual(args[2:], ['lobby','--port','31416'])
        self.assertEqual(env['LAN42_NO_UPDATE'], '1')

    @patch('campus_lan.updater.os.execve')
    @patch('campus_lan.updater.update_checkout')
    def test_restart_does_not_update(self, update, execute):
        restart(False)
        update.assert_not_called()
        execute.assert_called_once()

    def test_typed_restart_offers_package_reload_but_watcher_does_not(self):
        for ask_all in (False,True):
            with self.subTest(ask_all=ask_all), patch.object(updater,'request_reload') as ask, \
                 patch.object(updater.os,'execve'), patch.object(updater.time,'sleep'), \
                 patch.object(updater,'update_checkout') as update:
                restart(False,ask_all=ask_all)
                self.assertEqual(ask.call_count,int(ask_all))
                update.assert_not_called()

class RevisionWatch(unittest.TestCase):
    def setUp(self):
        updater._revision_cache.clear()

    def test_external_commit_change_detected_and_polls_are_bounded(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater,'reload_path',return_value=Path(tmp)/'marker'), \
             patch.object(updater.time,'monotonic',side_effect=[0,1,6]), \
             patch.object(updater.subprocess,'run',side_effect=[Mock(stdout='a'*40),Mock(stdout='b'*40)]) as run:
            first=updater.checkout_revision(tmp)
            self.assertEqual(updater.checkout_revision(tmp),first)
            self.assertNotEqual(updater.checkout_revision(tmp),first)
            self.assertEqual(run.call_count,2)

    def test_git_failure_keeps_last_revision_and_marker_still_works(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp, patch.object(updater,'reload_path',return_value=Path(tmp)/'marker'), \
             patch.object(updater.time,'monotonic',side_effect=[0,6,7]), \
             patch.object(updater.subprocess,'run',side_effect=[Mock(stdout='a'*40),subprocess.TimeoutExpired('git',3)]):
            revision=updater.checkout_revision(tmp)
            self.assertEqual(updater.checkout_revision(tmp),revision)
            first=updater.generation(tmp)
            (Path(tmp)/'marker').write_text('manual-reload')
            self.assertNotEqual(updater.generation(tmp),first)

    def test_real_git_commit_and_dirty_work_never_publish_reload(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            repo=Path(tmp)
            def git(*args):
                subprocess.run(['git','-C',tmp,*args],check=True,capture_output=True)
            git('init');(repo/'file').write_text('one')
            git('add','.');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','one')
            with patch.object(updater,'reload_path',return_value=repo/'marker'):
                first=updater.generation(repo)
                revision=updater.checkout_revision(repo)
                (repo/'file').write_text('two')
                updater._revision_cache.clear()
                self.assertEqual(updater.generation(repo),first)
                git('add','file');git('-c','user.name=Test','-c','user.email=test@example.invalid','commit','-m','two')
                updater._revision_cache.clear()
                self.assertEqual(updater.generation(repo),first)
                self.assertNotEqual(updater.checkout_revision(repo),revision)

class ReloadConsent(unittest.TestCase):
    def test_only_explicit_yes_publishes_reload(self):
        for answer,allowed in [('y',True),('yes',True),('Y',True),('',False),('n',False),('A',False)]:
            with self.subTest(answer=answer),patch.object(updater.sys.stdin,'isatty',return_value=True),patch('builtins.input',return_value=answer),patch.object(updater,'notify_reload') as notify:
                self.assertEqual(updater.request_reload('/example'),allowed)
                self.assertEqual(notify.call_count,int(allowed))

    def test_unattended_and_eof_never_publish(self):
        with patch.object(updater.sys.stdin,'isatty',return_value=False),patch('builtins.input') as ask,patch.object(updater,'notify_reload') as notify:
            self.assertFalse(updater.request_reload('/example'))
            ask.assert_not_called();notify.assert_not_called()
        with patch.object(updater.sys.stdin,'isatty',return_value=True),patch('builtins.input',side_effect=EOFError),patch.object(updater,'notify_reload') as notify:
            self.assertFalse(updater.request_reload('/example'));notify.assert_not_called()

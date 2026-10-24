import subprocess
import unittest
from unittest.mock import patch, Mock
from campus_lan.updater import update_checkout, restart


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

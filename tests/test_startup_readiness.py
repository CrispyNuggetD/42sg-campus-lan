"""Simulate slow emulated startup without sleeping or starting real processes."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan import __main__ as app

class StartupReadiness(unittest.TestCase):
    def attempt(self, ish, ready_at=None, exited=False):
        clock = [0.0]
        def sleep(seconds): clock[0] += seconds
        def probe(*args, **kwargs):
            return {'version':'test'} if ready_at is not None and clock[0] >= ready_at else None
        child = Mock(pid=123)
        child.poll.return_value = 1 if exited else None
        with tempfile.TemporaryDirectory() as tmp, ExitStack() as stack:
            stack.enter_context(patch.object(app.Path, 'is_dir', return_value=ish))
            stack.enter_context(patch.object(app, 'runtime_dir', return_value=Path(tmp)))
            stack.enter_context(patch.object(app.time, 'monotonic', side_effect=lambda:clock[0]))
            stack.enter_context(patch.object(app.time, 'sleep', side_effect=sleep))
            stack.enter_context(patch.object(app, 'probe', side_effect=probe))
            spawn = stack.enter_context(patch.object(app.subprocess, 'Popen', return_value=child))
            stack.enter_context(patch.object(app.threading, 'Thread'))
            result = error = None
            try: result = app.start_background('127.0.0.1',31415)
            except RuntimeError as exc: error = str(exc)
            return result, error, clock[0], spawn.call_count, child

    def test_ish_waits_for_server_that_becomes_ready_after_desktop_budget(self):
        result, error, elapsed, count, child = self.attempt(True, ready_at=12)
        self.assertEqual(result, '127.0.0.1')
        self.assertIsNone(error)
        self.assertGreaterEqual(elapsed,12)
        self.assertEqual(count,1)
        child.kill.assert_not_called()

    def test_ish_timeout_is_bounded_and_leaves_process_alone(self):
        _, error, elapsed, count, child = self.attempt(True)
        self.assertIn('within 60s',error)
        self.assertLess(elapsed,61)
        self.assertEqual(count,1)
        child.kill.assert_not_called()
        child.terminate.assert_not_called()

    def test_desktop_retains_short_budget(self):
        _, error, elapsed, _, _ = self.attempt(False, ready_at=12)
        self.assertIn('within 5s',error)
        self.assertLess(elapsed,6)

    def test_child_exit_stops_immediately(self):
        _, error, elapsed, _, _ = self.attempt(True, exited=True)
        self.assertIn('could not start',error)
        self.assertEqual(elapsed,0)

    def test_existing_server_is_reused_without_spawning(self):
        result, error, _, count, _ = self.attempt(True,ready_at=0)
        self.assertEqual(result,'127.0.0.1')
        self.assertIsNone(error)
        self.assertEqual(count,0)

"""Version checks use fake Git and release metadata, never real network/auth."""
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan.version_status import check


class VersionStatusTests(unittest.TestCase):
    def report(self, counts='0 0', dirty='', fail=False):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'campus_lan'
            path.mkdir()
            (path/'release.json').write_text(json.dumps(dict(version='2.0.0')))
            def run(args, **kwargs):
                self.assertEqual(kwargs['env']['GIT_TERMINAL_PROMPT'], '0')
                self.assertLessEqual(kwargs['timeout'], 15)
                if 'fetch' in args and fail:
                    raise subprocess.TimeoutExpired(args, 15)
                if 'rev-list' in args: return Mock(stdout=counts)
                if 'status' in args: return Mock(stdout=dirty)
                return Mock(stdout='a'*40)
            with patch('campus_lan.version_status.subprocess.run', side_effect=run) as git:
                lines = check('1.0.0', 'b'*40, '1.0.0', tmp)
                self.assertFalse(any('pull' in c.args[0] or 'reset' in c.args[0] for c in git.call_args_list))
                return '\n'.join(lines)

    def test_current_checkout_does_not_claim_old_processes_are_current(self):
        text = self.report()
        self.assertIn('Checkout is latest', text)
        self.assertIn('Client restart needed', text)
        self.assertIn('Host version differs', text)

    def test_upstream_and_local_branch_states(self):
        for counts, phrase in [('0 3', 'Update available: 3'), ('2 0', 'ahead of origin/main by 2'),
                               ('2 3', 'Branches diverged: 2')]:
            with self.subTest(counts=counts):
                self.assertIn(phrase, self.report(counts))

    def test_dirty_checkout_and_offline_are_not_reported_as_fully_updated(self):
        text = self.report(dirty=' M local.py', fail=True)
        self.assertIn('Local edits present', text)
        self.assertIn('status is unknown', text)
        self.assertNotIn('Checkout is latest', text)

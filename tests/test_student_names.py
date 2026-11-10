"""Name refreshes use fake campus pages and isolated private caches only."""
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch

from campus_lan import student_names
from campus_lan.cluster_photo import photo_caption
from campus_lan.auth import AuthError


class StudentNamesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'student-names.json'
        patcher = patch.object(student_names, 'cache_path', return_value=self.path)
        patcher.start(); self.addCleanup(patcher.stop)

    def directory(self):
        return dict(students=[dict(id=1, login='fixture'), dict(id=2, login='other')])

    @patch('campus_lan.access.Policy')
    @patch('campus_lan.campus_info.load')
    @patch('campus_lan.campus_info.API')
    def test_pages_only_and_minimal_cache_intersect_ids_and_logins(self, API, load, policy):
        load.return_value = self.directory()
        users = [dict(id=1, login='fixture', usual_full_name='Élodie Example', email='discard'),
                 dict(id=2, login='changed-login', displayname='Wrong Person'),
                 dict(id=99, login='outsider', displayname='Not retained')]
        API.return_value.get.side_effect = [users + [dict(id=100+n, login='x') for n in range(97)], []]
        result = student_names.refresh()
        self.assertEqual(result['campus_GET_requests'], 2)
        self.assertEqual(result['missing_logins'], ['other'])
        self.assertEqual(API.return_value.get.call_count, 2)
        for call in API.return_value.get.call_args_list:
            self.assertEqual(call.args, ('campus/64/users',))
        API.return_value.member_profile.assert_not_called()
        policy.return_value.local_operator.assert_called_once()
        data = json.loads(self.path.read_text())
        self.assertEqual(data['names'], {'fixture': 'Élodie Example'})
        self.assertNotIn('discard', self.path.read_text())
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(student_names.cached_name('FIXTURE'), 'Élodie Example')
        self.assertIn('Élodie Example\nfixture', photo_caption('fixture'))
        self.assertEqual(photo_caption('missing'), 'missing · local photo · Esc closes')

    @patch('campus_lan.access.Policy')
    @patch('campus_lan.campus_info.load')
    @patch('campus_lan.campus_info.API')
    def test_rate_limit_stops_immediately_and_preserves_old_cache(self, API, load, policy):
        self.path.write_text('old'); self.path.chmod(0o600)
        load.return_value = self.directory()
        opener = API.return_value.opener
        opener.open.side_effect = urllib.error.HTTPError('https://api.intra.42.fr/v2/campus/64/users',429,'Busy',{'Retry-After':'100'},None)
        API.return_value.get.side_effect = lambda *a, **k: opener.open(Mock())
        with self.assertRaisesRegex(AuthError, '429'):
            student_names.refresh()
        self.assertEqual(API.return_value.get.call_count, 1)
        self.assertEqual(self.path.read_text(), 'old')

    @patch('campus_lan.access.Policy')
    @patch('campus_lan.campus_info.load')
    @patch('campus_lan.campus_info.API')
    def test_page_cap_never_imports_partial_data(self, API, load, policy):
        load.return_value = self.directory()
        API.return_value.get.return_value = [dict(id=1,login='fixture',displayname='Example')] * 100
        with self.assertRaisesRegex(ValueError, '20-page cap'):
            student_names.refresh()
        self.assertEqual(API.return_value.get.call_count, 20)
        self.assertFalse(self.path.exists())

    @patch('campus_lan.access.Policy')
    @patch('campus_lan.campus_info.load')
    @patch('campus_lan.campus_info.API')
    def test_cache_permissions_checked_before_api_initialization(self, API, load, policy):
        load.return_value = self.directory()
        self.path.parent.chmod(0o755)
        try:
            with self.assertRaisesRegex(ValueError, 'no API calls made'):
                student_names.refresh()
        finally:
            self.path.parent.chmod(0o700)
        API.assert_not_called()

    def test_missing_corrupt_or_wrong_scope_cache_is_offline_fallback(self):
        self.assertEqual(student_names.cached_name('fixture'), '')
        self.path.write_text('{');self.path.chmod(0o600)
        self.assertEqual(student_names.cached_name('fixture'), '')
        self.path.write_text(json.dumps(dict(schema=1,campus_id=1,names={'fixture':'Wrong'})))
        self.assertEqual(student_names.cached_name('fixture'), '')
        self.assertEqual(student_names.display_name(dict(login='fixture',displayname='fixture',first_name='First',last_name='Last')), 'First Last')
        self.assertEqual(student_names.clean_name('Name\n\x1b[31m'), 'Name [31m')

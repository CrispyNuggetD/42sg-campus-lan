import collections
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from campus_lan.login_whitelist import allowed_logins,validate_logins
from campus_lan.tracking import Tracker
from campus_lan.relationship_commands import configure
from campus_lan.client import Client


class Whitelist(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)
        for target in ('campus_lan.login_whitelist.directory','campus_lan.tracking.config_dir'):
            p=patch(target,return_value=self.root);p.start();self.addCleanup(p.stop)
        p=patch.dict(os.environ,{'LAN42_INTRA_WHITELIST':''});p.start();self.addCleanup(p.stop)
        self.students=[dict(login='fixture-one',cohort=1),dict(login='fixture-two',cohort=2),dict(login='friends',cohort=1)]
        self.write_directory()
        self.tracker=Tracker('fixture-owner')

    def write_directory(self):
        (self.root/'singapore.json').write_text(json.dumps({'students':self.students}))

    def test_json_whitelist_normalizes_case_deduplicates_and_suggests_without_correcting(self):
        self.assertEqual(validate_logins(['FIXTURE-ONE','fixture-one']),['fixture-one'])
        with self.assertRaisesRegex(ValueError,'Did you mean fixture-one'):
            validate_logins(['fixture-on'])
        for value in ('../fixture-one','fixture-one;echo','fixture-one\n','login:friends','cohort1','@list'):
            with self.assertRaises(ValueError):validate_logins([value])
        self.assertEqual(allowed_logins(),{'fixture-one','fixture-two','friends'})

    def test_photo_cohort_selector_is_one_word_and_a_bare_number_is_literal(self):
        from campus_lan.login_whitelist import expand_photo_targets
        with patch('campus_lan.campus_info.load',return_value={'students':self.students}):
            for selector in ('cohort1','intake1','I1','i1'):
                self.assertEqual(expand_photo_targets([selector]),['fixture-one','friends'])
            for selector in ('all','sg','42sg'):
                self.assertEqual(expand_photo_targets([selector]),['fixture-one','fixture-two','friends'])
        self.assertEqual(expand_photo_targets(['1']),['1'])
        with self.assertRaisesRegex(ValueError,'cohort1'):
            expand_photo_targets(['cohort','1'])

    def test_missing_corrupt_and_explicit_text_sources_fail_closed(self):
        (self.root/'singapore_intra.txt').write_text('FIXTURE-TEXT\nfixture-two fixture-two\n')
        self.assertNotIn('fixture-text',allowed_logins())  # JSON is authoritative.
        (self.root/'singapore.json').write_text('{broken')
        with self.assertRaisesRegex(ValueError,'unavailable or invalid'):allowed_logins()
        (self.root/'singapore.json').unlink()
        self.assertEqual(allowed_logins(),{'fixture-text','fixture-two'})
        custom=self.root/'custom.txt';custom.write_text('custom-user\n')
        with patch.dict(os.environ,{'LAN42_INTRA_WHITELIST':str(custom)}):
            self.assertEqual(allowed_logins(),{'custom-user'})
            custom.write_text('bad/input')
            with self.assertRaises(ValueError):allowed_logins()
        (self.root/'singapore_intra.txt').unlink()
        with self.assertRaises(ValueError):validate_logins(['fixture-one'])

    def test_unknown_member_rejects_entire_change_without_partial_writes(self):
        t=self.tracker;t.change(['fixture-one']);before=t.path.read_bytes()
        for change in (lambda:t.change(['fixture-two','typo']),lambda:t.set_relationship(['fixture-two','typo'],'friends'),lambda:t.change_list('furs',['fixture-two','typo']),lambda:configure(t,['alerts','typo','campus','on']),lambda:t.configure_rules('include',['typo'])):
            with self.assertRaisesRegex(ValueError,'whitelist'):change()
            self.assertEqual(t.path.read_bytes(),before)
            self.assertEqual(t.names,['fixture-one'])

    def test_shortcuts_expand_then_validate_and_legacy_typos_can_be_removed(self):
        t=self.tracker
        configure(t,['list','furs','add','fixture-one','fixture-two'])
        configure(t,['friends','@furs'])
        self.assertEqual(set(t.resolve(['friends'])),{'fixture-one','fixture-two'})
        self.assertEqual(t.resolve(['login:friends']),['friends'])
        with patch('campus_lan.campus_info.load',return_value={'students':self.students}):
            for selector in ('cohort1','intake1','I1','i1'):
                self.assertEqual(set(t.resolve([selector])),{'fixture-one','friends'})
            self.assertEqual(set(t.resolve(['all'])),{'fixture-one','fixture-two','friends'})
            self.assertEqual(t.resolve(['sg']),t.resolve(['all']))
            self.assertEqual(t.resolve(['42sg']),t.resolve(['all']))
        t.data['lists']['legacy']=['typo'];t.data['people']['typo']={'relationship':'tracked','alerts':{}}
        t.save(t.data)
        with self.assertRaises(ValueError):t.resolve(['@legacy'])
        with self.assertRaises(ValueError):t.resolve(['tracked'])
        configure(t,['list','legacy','remove','typo'])
        t.change(t.resolve(['typo'],validate=False),remove=True)
        self.assertNotIn('typo',t.names);self.assertEqual(t.data['lists']['legacy'],[])

    def test_unknown_targets_do_not_send_network_requests(self):
        c=Client.__new__(Client);c.name='fixture-owner';c.lines=collections.deque();c.send=Mock()
        for command in ('/dm typo hello','/sabo typo','/sabo typo history','/alert typo hello'):
            self.assertTrue(c.group_command(command));c.send.assert_not_called()
        c.uwu_command('/uwu typo');c.send.assert_not_called()
        self.assertTrue(c.group_command('/sabo fixture-one'))
        c.send.assert_called_once_with(dict(type='command',text='/sabo fixture-one'))
        self.assertFalse(c.group_command('/sabo 2 random cohort1'))
        self.assertFalse(c.group_command('/sabo history'))
        self.assertFalse(c.group_command('/sabo where level>=2'))
        (self.root/'singapore.json').unlink();c.send.reset_mock()
        self.assertTrue(c.group_command('/dm fixture-one hello'));c.send.assert_not_called()

    def test_profile_browser_rejects_unknown_names_before_opening(self):
        from campus_lan.profile_browser import resolve
        self.assertEqual(resolve(['FIXTURE-ONE']),['https://profile-v3.intra.42.fr/users/fixture-one'])
        with patch('campus_lan.profile_browser.load',return_value={'students':self.students}):
            self.assertEqual(resolve(['sg']),resolve(['all']))
            self.assertEqual(resolve(['42sg']),resolve(['all']))
        with self.assertRaisesRegex(ValueError,'whitelist'):resolve(['fixture-one','typo'])

    def test_numeric_confirmation_handles_whitelist_rejection_without_crashing(self):
        c=Client.__new__(Client);c.role='lobby';c.lines=collections.deque();c.tracker=self.tracker
        c.popup_prompts=Mock();c.cluster_source=True
        c.campus_selection={1:('typo',(1,1,1))}
        c.cluster_players=[dict(name='typo',seat='c1r1s1')]
        self.assertTrue(c.tracking_command('/track 1'))
        c.popup_prompts.return_value.confirm.call_args.args[1]()
        self.assertEqual(self.tracker.names,[])
        self.assertTrue(any('whitelist' in line for line in c.lines))

    def test_presence_words_are_reserved_for_host_not_local_login_or_list_alias(self):
        for word in ('online','verified'):
            with self.assertRaisesRegex(ValueError,'Use /sabo'):self.tracker.resolve([word])
            self.tracker.change_list(word,['fixture-one'])
            self.assertEqual(self.tracker.resolve(['@'+word]),['fixture-one'])

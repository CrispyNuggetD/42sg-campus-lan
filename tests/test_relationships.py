import collections
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.tracking import Tracker,describe
from campus_lan.relationship_commands import configure
from campus_lan.client import Client

class Relationships(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        patcher=patch('campus_lan.tracking.config_dir',return_value=Path(self.tmp.name))
        patcher.start();self.addCleanup(patcher.stop)
        self.tracker=Tracker('owner')

    def test_migration_preserves_acquaintances_and_writes_version_two(self):
        self.tracker.path.write_text(json.dumps(dict(logins=['dthoo','thtay'])))
        self.tracker.path.chmod(0o600)
        migrated=Tracker('owner');self.assertEqual(migrated.resolve(['tracked']),['dthoo','thtay'])
        migrated.set_relationship(['dthoo'],'friends')
        self.assertEqual(Tracker('owner').resolve(['friends']),['dthoo'])
        self.assertEqual(Tracker('owner').resolve(['tracked']),['thtay'])
        self.assertEqual(json.loads(migrated.path.read_text())['schema_version'],2)

    def test_relationship_aliases_union_and_multiple_independent_lists(self):
        t=self.tracker;t.change(['a']);t.set_relationship(['b'],'friends');t.set_relationship(['c'],'moots');t.set_relationship(['d'],'oomf')
        self.assertEqual(t.resolve(['friends']),['b','c','d']);self.assertEqual(t.resolve(['mutuals']),['c'])
        self.assertEqual(t.resolve(['tracked']),['a']);self.assertEqual(len(t.resolve(['alltracked'])),4)
        t.change_list('lunch',['a','b']);t.change_list('study',['b','e'])
        self.assertEqual(t.resolve(['@lunch','@study','friends']),['a','b','e','c','d'])
        self.assertNotIn('e',t.names)
        with self.assertRaises(ValueError):t.change_list('friends',['a'])
        self.assertEqual(t.resolve(['login:friends']),['friends'])

    def test_cohort_rules_exclusions_and_friend_warmth_are_independent(self):
        t=self.tracker;t.set_relationship(['friend'],'friends')
        data=dict(students=[dict(login='friend',cohort=4),dict(login='normal',cohort=4),dict(login='excluded',cohort=4)])
        with patch('campus_lan.campus_info.load',return_value=data):
            t.configure_rules('include',['cohort4']);t.configure_rules('exclude',['excluded','friend']);t.configure_rules('on')
            players=[dict(name=n,seat='c1r2s3') for n in ('friend','normal','excluded')]
            notices=t.transitions(players,'campus');by_name={n['login']:n for n in notices}
            self.assertEqual(set(by_name),{'friend','normal'})
            self.assertTrue(by_name['friend']['warm']);self.assertIn('Your friend',describe(by_name['friend'])[0])
            self.assertFalse(by_name['normal']['warm']);self.assertIn('Campus update',describe(by_name['normal'])[0])
            self.assertEqual(t.names,['friend'])
            self.assertFalse(t.transitions(players,'campus'))
            t.configure_rules('off');t.transitions([],'campus')
            self.assertEqual([n['login'] for n in t.transitions(players,'campus')],['friend'])

    def test_event_preferences_survive_status_changes_and_failures_preserve_friends(self):
        t=self.tracker;t.change(['a']);t.set_alerts(['a'],'campus',False);t.set_relationship(['a'],'oomf')
        self.assertFalse(t.transitions([dict(name='a')],'campus'))
        self.assertEqual(len(t.transitions([dict(name='a')],'lobby')),1)
        t.data['clusters']=dict(enabled=True,include=['cohort4'],exclude=[])
        with patch('campus_lan.campus_info.load',return_value=None):
            t.transitions([],'lobby');self.assertEqual(len(t.transitions([dict(name='a')],'lobby')),1)
            self.assertIn('cache',t.rules_error)

    def test_configuration_commands(self):
        t=self.tracker;configure(t,['dthoo','thtay']);configure(t,['status','moots','dthoo'])
        configure(t,['list','lunch','add','alltracked'])
        self.assertEqual(t.resolve(['@lunch']),['dthoo','thtay'])
        configure(t,['alerts','mutuals','lobby','off']);self.assertFalse(t.data['people']['dthoo']['alerts']['lobby'])
        configure(t,['list','lunch','remove','thtay']);self.assertEqual(t.resolve(['@lunch']),['dthoo'])
        self.assertIn(str(t.path),configure(t,['config'])[0])

    def test_grouped_display_is_sorted_and_does_not_save(self):
        t=self.tracker
        t.set_relationship(['zebra','alpha'],'friends')
        t.set_relationship(['mutual'],'mutuals');t.change(['other'])
        t.change_list('furs',['zebra','alpha'])
        before=t.path.read_bytes()
        with patch.object(t,'save',side_effect=AssertionError('Display must not save')):
            lines=configure(t,[])
            self.assertIn('  Friends (2)',lines)
            self.assertIn('  Mutuals (1)',lines)
            self.assertIn('  Acquaintances (tracked) (1)',lines)
            self.assertIn('  @furs (2)',lines)
            self.assertLess(lines.index('    alpha'),lines.index('    zebra'))
            friends=configure(t,['friends'])
            self.assertIn('    mutual',friends)  # Existing friendly selector union.
            self.assertNotIn('    other',friends)
            self.assertEqual(configure(t,['moots']),['Local relationships','  Mutuals (1)','    mutual'])
            self.assertIn('  Nobody tracked here yet.',configure(t,['oomf']))
        self.assertEqual(t.path.read_bytes(),before)

    def test_relationship_shorthand_tracks_logins_and_list_members(self):
        t=self.tracker;t.change_list('furs',['dthoo','thtay'])
        configure(t,['friends','@furs'])
        self.assertEqual(set(t.resolve(['friends'])),{'dthoo','thtay'})
        t.set_alerts(['dthoo'],'campus',False)
        configure(t,['moots','dthoo'])
        self.assertEqual(t.data['people']['dthoo']['relationship'],'mutuals')
        self.assertFalse(t.data['people']['dthoo']['alerts']['campus'])
        configure(t,['oomf','guolio'])
        self.assertEqual(t.data['people']['guolio']['relationship'],'oomf')
        configure(t,['tracked','guolio'])
        self.assertEqual(t.resolve(['tracked']),['guolio'])

    def client(self):
        c=Client.__new__(Client);c.name='owner';c.lines=collections.deque();c.send=Mock()
        return c

    def test_group_expansion_stays_local_and_quotes_are_removed(self):
        t=self.tracker;t.set_relationship(['dthoo','thtay'],'friends');c=self.client()
        self.assertTrue(c.group_command('/dm friends "do you all want lunch?"'))
        c.send.assert_called_once_with(dict(type='direct_batch',targets=['dthoo','thtay'],text='do you all want lunch?'))
        self.assertNotIn('friends',json.dumps(c.send.call_args.args))
        c.send.reset_mock();c.group_command('/sabo friends')
        c.send.assert_called_once_with(dict(type='command',text='/sabo dthoo thtay'))
        c.send.reset_mock();c.group_command("/dm dthoo don't wait for me")
        self.assertEqual(c.send.call_args.args[0]['text'],"don't wait for me")

    def test_empty_group_and_invalid_quotes_do_not_send(self):
        c=self.client();c.group_command('/dm friends "hello"');c.send.assert_not_called()
        c.group_command('/dm dthoo "unfinished');c.send.assert_not_called()
        c.group_command('/sabo @missing');c.send.assert_not_called()

    def test_invalid_or_newer_config_is_not_overwritten(self):
        for raw in ('{broken',json.dumps(dict(schema_version=99,people={}))):
            self.tracker.path.write_text(raw);self.tracker.path.chmod(0o600)
            tracker=Tracker('owner');self.assertIsNotNone(tracker.load_error)
            with self.assertRaises(ValueError):tracker.change(['new-person'])
            self.assertEqual(tracker.path.read_text(),raw)

    def test_literal_login_escape_expands_before_sabo(self):
        client=self.client();self.assertTrue(client.group_command('/sabo login:friends'))
        client.send.assert_called_once_with(dict(type='command',text='/sabo friends'))

    def test_physical_cluster_scope_applies_to_rules_not_personal_friends(self):
        t=self.tracker;t.set_relationship(['friend'],'friends')
        t.configure_rules('include',['one','two','unknown','friend']);t.configure_rules('scope',['c1']);t.configure_rules('on')
        players=[dict(name='one',seat='c1r2s3'),dict(name='two',seat='Cluster 2, row 3, seat 4'),dict(name='unknown',seat='unknown'),dict(name='friend',seat='c2r4s5')]
        self.assertEqual({n['login'] for n in t.transitions(players,'campus')},{'one','friend'})
        t.configure_rules('scope',['2'])
        self.assertEqual({n['login'] for n in t.transitions(players,'lobby')},{'two','friend'})
        t.configure_rules('scope',['all']);t.transitions([],'lobby')
        self.assertEqual({n['login'] for n in t.transitions(players,'lobby')},{'one','two','unknown','friend'})
        self.assertEqual(Tracker('owner').data['clusters']['scope'],'all')
        with self.assertRaises(ValueError):t.configure_rules('scope',['3'])

    def test_cluster_location_shorthand_is_case_insensitive_and_separate_from_lists(self):
        t=self.tracker
        for spelling in ('c1','C1','cluster1','CLUSTER1'):
            configure(t,['clusters',spelling]);self.assertEqual(t.data['clusters']['scope'],'1')
        for spelling in ('c2','C2','cluster2'):
            configure(t,['clusters',spelling]);self.assertEqual(t.data['clusters']['scope'],'2')
        configure(t,['clusters','include','someone'])
        self.assertEqual(t.data['clusters']['include'],['someone'])
        self.assertEqual(t.data['clusters']['scope'],'2')
        configure(t,['clusters','all']);self.assertEqual(t.data['clusters']['scope'],'all')
        self.assertEqual(t.names,[])

    def test_cluster_location_tokens_can_be_combined_with_include_filters(self):
        t=self.tracker;data=dict(students=[dict(login='one',cohort=4)])
        with patch('campus_lan.campus_info.load',return_value=data):
            configure(t,['clusters','include','cohort4','C1'])
            self.assertEqual(t.data['clusters']['scope'],'1')
            self.assertEqual(t.data['clusters']['include'],['cohort4'])
            configure(t,['clusters','cluster2','exclude','one'])
            self.assertEqual(t.data['clusters']['scope'],'2')
            self.assertEqual(t.data['clusters']['exclude'],['one'])
            before=t.path.read_text()
            with self.assertRaises(ValueError):configure(t,['clusters','include','cohort4','c1','c2'])
            self.assertEqual(t.path.read_text(),before)

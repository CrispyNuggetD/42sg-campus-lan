import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from campus_lan.auth import config_dir, private_write
from campus_lan import preferences
from campus_lan.tracking import Tracker
from campus_lan.login_settings import LoginSettings


class PortablePreferences(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root/'config'), 'XDG_STATE_HOME': str(self.root/'state')})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_link_preserves_friends_and_excludes_all_auth_and_device_files(self):
        tracker = Tracker('hnah')
        tracker.save(dict(tracker.data, people={'fixture': {'relationship':'friends', 'alerts':{}}}))
        LoginSettings().set('close_tab', False)
        for name in ('auth-server.json', 'auth-key.pem', 'auth-trust.json', 'access-policy.json',
                     'campus-owner-host.json', 'session.json', 'notification-channels-device.json'):
            private_write(config_dir()/name, 'PRIVATE TEST SENTINEL')
        target = self.root/'private repo/42/lan42'
        preferences.storage(target)
        self.assertTrue((config_dir()/'preferences').is_symlink())
        self.assertEqual(Tracker('hnah').names, ['fixture'])
        self.assertFalse(LoginSettings().data['close_tab'])
        self.assertTrue(all(preferences.allowed(p.name) for p in target.iterdir()))
        self.assertNotIn('PRIVATE TEST SENTINEL', ''.join(p.read_text() for p in target.iterdir()))
        self.assertEqual(target.stat().st_mode & 0o777, 0o700)
        self.assertTrue(all(p.stat().st_mode & 0o777 == 0o600 for p in target.iterdir()))
        # A different OS config root can use the same preferences and owner login.
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root/'mac-config')}):
            preferences.storage(target)
            self.assertEqual(Tracker('HNAH').names, ['fixture'])
            self.assertFalse(LoginSettings().data['close_tab'])
            self.assertFalse((config_dir()/'auth-server.json').exists())

    def test_export_import_round_trip_and_conflict_preserve_existing(self):
        LoginSettings().set('close_tab', False)
        exported = self.root/'export'
        preferences.perform('export', str(exported))
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root/'fresh-os')}):
            preferences.perform('import', str(exported))
            self.assertFalse(LoginSettings().data['close_tab'])
            LoginSettings().set('close_tab', True)
            with self.assertRaisesRegex(ValueError, 'Different preference'):
                preferences.perform('import', str(exported))
            self.assertTrue(LoginSettings().data['close_tab'])

    def test_git_checkout_permissions_are_restored_when_linking(self):
        target=self.root/'checked-out-preferences'
        target.mkdir(mode=0o755)
        file=target/'login-settings.json'
        file.write_text(json.dumps(dict(close_tab=False)))
        file.chmod(0o644)
        preferences.storage(target)
        self.assertFalse(LoginSettings().data['close_tab'])
        self.assertEqual(target.stat().st_mode&0o777,0o700)
        self.assertEqual(file.stat().st_mode&0o777,0o600)

    def test_account_choices_survive_seat_change_and_separate_accounts(self):
        from campus_lan.local_console import local_path,use_account
        from campus_lan.file_sharing.flock import FlockPreferences
        try:
            use_account('hnah')
            with patch('socket.gethostname',return_value='c1r1s1'):
                first=local_path('notification-channels')
                private_write(first,json.dumps(dict(all=False)))
                flock=FlockPreferences('a'*64,234449);flock.save(mode='always')
            with patch('socket.gethostname',return_value='c2r2s2'):
                self.assertEqual(local_path('notification-channels'),first)
                self.assertEqual(FlockPreferences('a'*64,234449).mode,'always')
            use_account('other-student')
            self.assertNotEqual(local_path('notification-channels'),first)
        finally:use_account(None)

    def test_newly_portable_choices_migrate_after_storage_was_linked(self):
        preferences.storage(self.root/'portable')
        name='popup-permissions-'+'a'*64+'.json'
        private_write(config_dir()/name,json.dumps(dict(browser='deny')))
        path=preferences.settings_path(name)
        self.assertNotEqual(path.parent,config_dir())
        self.assertEqual(json.loads(path.read_text()),dict(browser='deny'))
        self.assertTrue((config_dir()/name).exists())

    def test_storage_rejects_symlinked_files_and_unrelated_folder(self):
        LoginSettings()
        target = self.root/'target'
        target.mkdir(mode=0o700)
        (target/'auth.json').write_text('must not be imported')
        with self.assertRaisesRegex(ValueError, 'dedicated folder'):
            preferences.storage(target)
        (target/'auth.json').unlink()
        (target/'login-settings.json').symlink_to(self.root/'elsewhere')
        with self.assertRaises((OSError, ValueError)):
            preferences.storage(target)
        self.assertFalse((config_dir()/'preferences').exists())

class PreferenceMerge(unittest.TestCase):
    setUp = PortablePreferences.setUp
    def seed(self, folder, people, scalar=False):
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        tracker = Tracker('fixture-owner')
        data = dict(tracker.data, people={n: dict(relationship='friends', alerts={}) for n in people},
                    lists={'lunch': people}, clusters=dict(tracker.data['clusters'], enabled=scalar))
        private_write(folder/tracker.path.name, json.dumps(data))
        return tracker.path.name

    def test_combine_unions_friends_lists_and_keeps_local_scalar(self):
        local = config_dir(); name=self.seed(local, ['a','b'], False)
        incoming=self.root/'incoming';self.seed(incoming, ['b','c','d'], True)
        preferences.perform('import', incoming, 'combine')
        data=json.loads((local/name).read_text())
        self.assertEqual(list(data['people']), ['a','b','c','d'])
        self.assertEqual(data['lists']['lunch'], ['a','b','c','d'])
        self.assertFalse(data['clusters']['enabled'])
        preferences.perform('import', incoming, 'combine')
        self.assertEqual(json.loads((local/name).read_text()), data)

    def test_link_combines_local_with_repo_and_overwrite_uses_repo(self):
        name=self.seed(config_dir(), ['a','b'], False)
        target=self.root/'repo';self.seed(target, ['c','d'], True)
        preferences.storage(target, 'combine')
        data=json.loads((target/name).read_text())
        self.assertEqual(set(data['people']), {'a','b','c','d'})
        self.assertFalse(data['clusters']['enabled'])
        with patch.dict(os.environ, {'XDG_CONFIG_HOME': str(self.root/'new-device')}):
            self.seed(config_dir(), ['e'])
            preferences.storage(target, 'overwrite')
            self.assertEqual(set(Tracker('fixture-owner').names), {'a','b','c','d'})

    def test_overwrite_backs_up_local_and_invalid_later_file_changes_nothing(self):
        from unittest.mock import patch
        name=self.seed(config_dir(), ['a'])
        incoming=self.root/'incoming';self.seed(incoming, ['b'])
        private_write(incoming/'login-settings.json', 'invalid')
        with self.assertRaises(ValueError):preferences.perform('import', incoming, 'overwrite')
        self.assertEqual(Tracker('fixture-owner').names,['a'])
        (incoming/'login-settings.json').unlink()
        with patch.dict(os.environ, {'XDG_STATE_HOME': str(self.root/'state')}):
            preferences.perform('import', incoming, 'overwrite')
        self.assertEqual(Tracker('fixture-owner').names,['b'])
        backups=list((self.root/'state').rglob(name))
        self.assertEqual(len(backups),1)
        self.assertIn('a',json.loads(backups[0].read_text())['people'])
        self.assertEqual(backups[0].stat().st_mode&0o777,0o600)

    def test_git_conflicts_are_combined_and_staged_only_for_preferences(self):
        import subprocess
        repo=self.root/'git';repo.mkdir();folder=repo/'portable'
        name=self.seed(folder,['a'])
        def git(*args,check=True):
            return subprocess.run(['git','-C',str(repo),*args],check=check,capture_output=True)
        git('init','-b','main');git('config','user.email','test@example.invalid');git('config','user.name','Test')
        git('add','.');git('commit','-m','base');git('checkout','-b','incoming')
        self.seed(folder,['a','c','d']);git('add','.');git('commit','-m','incoming')
        git('checkout','main');self.seed(folder,['a','b']);git('add','.');git('commit','-m','local')
        self.assertNotEqual(git('merge','incoming',check=False).returncode,0)
        with self.assertRaises(preferences.PreferenceConflict):preferences.resolve(folder)
        with patch.dict(os.environ, {'XDG_STATE_HOME': str(self.root/'state')}):
            preferences.resolve(folder,'combine')
        self.assertEqual(set(json.loads((folder/name).read_text())['people']),{'a','b','c','d'})
        self.assertEqual(git('diff','--name-only','--diff-filter=U').stdout,b'')


if __name__ == '__main__':
    unittest.main()

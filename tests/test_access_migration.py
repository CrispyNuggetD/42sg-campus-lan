"""Upgrade real-shaped legacy config with mocked identity/network/OS operations."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from campus_lan.access import Policy,DEFAULT,migrate_legacy_host
from campus_lan.auth import AuthError,config_dir,private_write,private_read

HOST='a'*64

class LegacyHostMigration(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name});env.start();self.addCleanup(env.stop)
        self.root=config_dir()
        self.settings=dict(client_id='fixture',client_secret='fixture',host='10.11.1.1',broker_port=31416,lobby_port=31417,host_generation='b'*32)
        self.write_settings()
        private_write(self.root/'auth-trust.json',json.dumps({'certificate':'fixture-cert'}))
        private_write(self.root/'auth-cert.pem','fixture-cert')
        private_write(self.root/'auth-key.pem','fixture-key')
        self.owner=dict(id=234449,login='hnah',campus_users=[{'campus_id':64}])
        for target,value in [('campus_lan.access.host_id',HOST),('pwd.getpwuid',Mock(pw_name='hnah')),('campus_lan.auth_daily.current_seat','10.12.2.2')]:
            p=patch(target,return_value=value);p.start();self.addCleanup(p.stop)
        self.api=patch('campus_lan.campus_info.API').start();self.addCleanup(patch.stopall)
        self.api.return_value.member_profile.return_value=self.owner
        self.trust=patch('campus_lan.auth_client.validate_trust',side_effect=lambda x:x).start()
        self.ssl=patch('ssl.SSLContext').start()

    def write_settings(self):private_write(self.root/'auth-server.json',json.dumps(self.settings))

    def test_migrates_once_and_preserves_credentials_tls_and_revocation(self):
        before=copy.deepcopy(self.settings)
        self.assertTrue(migrate_legacy_host())
        p=Policy();self.assertEqual(p.data['approved_hosts'],[HOST]);self.assertEqual(p.data['admins'],[234449])
        self.assertEqual(p.local_operator(),234449)
        updated=json.loads(private_read(self.root/'auth-server.json'))
        self.assertEqual({k:updated[k] for k in before},before)
        self.assertEqual(updated['access_policy_version'],1)
        self.assertEqual(private_read(self.root/'auth-key.pem'),b'fixture-key')
        self.assertFalse(migrate_legacy_host());self.assertEqual(self.api.call_count,1)
        p.data['approved_hosts']=[];p.save()
        self.assertFalse(migrate_legacy_host());self.assertEqual(Policy().data['approved_hosts'],[])
        self.assertEqual(self.api.call_count,1)

    def test_new_setup_cannot_be_auto_enrolled(self):
        self.settings['access_policy_version']=1;self.write_settings()
        with self.assertRaises(AuthError):migrate_legacy_host()
        self.api.assert_not_called();self.assertFalse((self.root/'access-policy.json').exists())

    def test_other_os_users_and_non_campus_or_unmanaged_hosts_do_not_enroll(self):
        with patch('pwd.getpwuid',return_value=Mock(pw_name='student')):
            self.assertFalse(migrate_legacy_host())
        with patch('campus_lan.auth_daily.current_seat',side_effect=AuthError('offsite')):
            with self.assertRaises(AuthError):migrate_legacy_host()
        self.settings.pop('host_generation');self.write_settings()
        with self.assertRaises(AuthError):migrate_legacy_host()
        self.api.assert_not_called();self.assertFalse((self.root/'access-policy.json').exists())

    def test_bad_owner_or_failed_lookup_does_not_write_approvals(self):
        for response in (dict(id=2,login='hnah',campus_users=[{'campus_id':64}]),dict(id=234449,login='hnah',campus_users=[{'campus_id':1}])):
            self.api.return_value.member_profile.return_value=response
            with self.assertRaises(AuthError):migrate_legacy_host()
            self.assertFalse((self.root/'access-policy.json').exists())
        self.api.return_value.member_profile.side_effect=AuthError('offline')
        with self.assertRaises(AuthError):migrate_legacy_host()
        self.assertFalse((self.root/'local-operator.json').exists())

    def test_interrupted_policy_write_retries_but_missing_completed_policy_does_not(self):
        with patch.object(Policy,'save',side_effect=OSError('interrupted')):
            with self.assertRaises(OSError):migrate_legacy_host()
        self.assertTrue((self.root/'local-operator.json').exists());self.assertFalse((self.root/'access-policy.json').exists())
        self.assertTrue(migrate_legacy_host())
        (self.root/'access-policy.json').unlink()
        with self.assertRaises(AuthError):migrate_legacy_host()

    def test_corrupt_existing_policy_and_mismatched_pins_fail_closed(self):
        private_write(self.root/'access-policy.json','not json')
        with self.assertRaises(ValueError):migrate_legacy_host()
        self.api.assert_not_called();(self.root/'access-policy.json').unlink()
        private_write(self.root/'auth-cert.pem','different cert')
        with self.assertRaises(AuthError):migrate_legacy_host()
        self.api.assert_not_called()

class StartupOrdering(unittest.TestCase):
    def test_normal_linux_start_initializes_owner_and_failure_keeps_guest_available(self):
        from campus_lan.__main__ import initialize_owner_host
        with patch('sys.platform','linux'),patch('campus_lan.auth_daily.start') as start:
            initialize_owner_host();start.assert_called_once()
            start.side_effect=AuthError('private details')
            with patch('sys.stderr') as stderr:initialize_owner_host()
            self.assertNotIn('private details',str(stderr.write.call_args_list))
        with patch('sys.platform','darwin'),patch('campus_lan.auth_daily.start') as start:
            initialize_owner_host();start.assert_not_called()

    def test_owner_init_is_called_before_lobby_connections(self):
        from campus_lan import __main__ as app
        with patch('sys.argv',['lan42','lobby']),patch('campus_lan.auth_daily.current_seat',side_effect=AuthError('not campus')),patch.object(app,'initialize_owner_host',side_effect=RuntimeError('stop before sockets')) as init,patch.object(app,'start_background') as connect:
            with self.assertRaisesRegex(RuntimeError,'stop before sockets'):app.main()
            init.assert_called_once();connect.assert_not_called()

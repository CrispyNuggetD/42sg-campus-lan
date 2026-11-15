"""Standalone owner setup uses private state and existing enrollment, never live API."""
from contextlib import ExitStack
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from campus_lan import local_api_setup as setup
from campus_lan.access import host_id,Policy,DEFAULT
from campus_lan.auth import AuthError,config_dir,private_write

class LocalAPISetup(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.stack=ExitStack();self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ,{'XDG_CONFIG_HOME':self.tmp.name}))
        self.stack.enter_context(patch.object(setup.sys.stdin,'isatty',return_value=True))
        host_id.cache_clear();self.addCleanup(host_id.cache_clear)

    def test_consent_hidden_credentials_private_storage_and_existing_enrollment(self):
        output=io.StringIO()
        with patch('builtins.input',return_value='y'),patch.object(setup.getpass,'getpass',side_effect=['fake-app-uid','fake-app-secret']),patch.object(setup.subprocess,'run') as run,patch.object(Policy,'local_operator',return_value=234449),patch('sys.stdout',output):
            self.assertTrue(setup.setup())
        path=config_dir()/'auth-server.json'
        self.assertEqual(path.stat().st_mode & 0o777,0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777,0o700)
        self.assertTrue(json.loads(path.read_text())['standalone_api'])
        self.assertNotIn('fake-app-secret',output.getvalue())
        self.assertNotIn('fake-app-uid',output.getvalue())
        self.assertEqual(run.call_args.args[0],[setup.sys.executable,'-m','campus_lan.access','enroll-local'])
        self.assertFalse((config_dir()/'auth-key.pem').exists())

    def test_decline_does_not_save_or_enroll(self):
        with patch('builtins.input',return_value=''),patch.object(setup.getpass,'getpass') as password,patch.object(setup.subprocess,'run') as run:
            self.assertFalse(setup.setup())
        password.assert_not_called();run.assert_not_called()
        self.assertFalse(config_dir().exists())

    def test_reuses_existing_config_without_changing_secrets_or_tls_fields(self):
        original=dict(client_id='existing',client_secret='fake-secret',host='existing-host')
        private_write(config_dir()/'auth-server.json',json.dumps(original))
        with patch('builtins.input',return_value='y'),patch.object(setup.getpass,'getpass') as password,patch.object(setup.subprocess,'run'),patch.object(Policy,'local_operator',return_value=234449):
            setup.setup()
        password.assert_not_called()
        self.assertEqual(json.loads((config_dir()/'auth-server.json').read_text()),original)

    def test_ish_identity_is_private_stable_and_malformed_identity_fails_closed(self):
        with patch('campus_lan.access.Path.is_dir',return_value=True):
            first=host_id();host_id.cache_clear()
            self.assertEqual(host_id(),first)
            self.assertEqual((config_dir()/'ish-install-id').stat().st_mode&0o777,0o600)
            host_id.cache_clear()
            private_write(config_dir()/'ish-install-id','invalid')
            with self.assertRaises(AuthError):host_id()

    def test_enrollment_refuses_revoked_install_without_api_calls(self):
        from campus_lan import access
        policy=Policy();policy.save()
        with patch.object(access,'host_id',return_value='a'*64),patch('sys.argv',['access','enroll-local']),patch('campus_lan.campus_info.API') as api:
            with self.assertRaisesRegex(AuthError,'explicitly approve'):access.main()
        api.assert_not_called()
        self.assertFalse((config_dir()/'local-operator.json').exists())

    def test_initial_enrollment_checks_sg_owner_before_granting_local_api(self):
        from campus_lan import access
        person=dict(id=234449,login='hnah',campus_users=[{'campus_id':64}])
        with patch.object(access,'host_id',return_value='b'*64),patch('sys.argv',['access','enroll-local']),patch('campus_lan.campus_info.API') as api:
            api.return_value.member_profile.return_value=person
            access.main()
            api.return_value.member_profile.assert_called_once_with('234449')
            self.assertEqual(Policy().local_operator(),234449)
        self.assertEqual(json.loads((config_dir()/'local-operator.json').read_text()),{'uid':234449})

    def test_noninteractive_setup_rejects_credentials(self):
        with patch.object(setup.sys.stdin,'isatty',return_value=False),patch.object(setup.getpass,'getpass') as password:
            with self.assertRaises(AuthError):setup.setup()
        password.assert_not_called()

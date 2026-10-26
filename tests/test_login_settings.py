import collections
import json
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.login_settings import LoginSettings
from campus_lan.client import Client
from campus_lan import auth_client

class LoginOptions(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        patcher=patch('campus_lan.login_settings.config_dir',return_value=Path(tmp.name));patcher.start();self.addCleanup(patcher.stop)
        pause=patch('campus_lan.login_settings._paused',False);pause.start();self.addCleanup(pause.stop)

    def client(self):
        c=Client.__new__(Client);c.role='lobby';c.connected=True;c.id='1';c.secure=False;c.signing_in=False
        c.name='owner';c.home=c.current=('127.0.0.1',31415);c.lines=collections.deque();c.inbox=queue.Queue()
        c.request_popup=Mock();return c

    def test_defaults_persist_and_bad_config_is_preserved(self):
        settings=LoginSettings();self.assertEqual(settings.data['autologin'],'off')
        settings.set('autologin','saved');settings.set('close_tab',False)
        self.assertEqual(LoginSettings().data,dict(autologin='saved',close_tab=False,autologin_asked=True))
        self.assertEqual(settings.path.stat().st_mode&0o777,0o600)
        settings.path.write_text('{bad')
        broken=LoginSettings();self.assertEqual(broken.data['autologin'],'off')
        with self.assertRaises(ValueError):broken.set('autologin','on')
        self.assertEqual(settings.path.read_text(),'{bad')

    def test_saved_only_reuses_without_browser_and_never_prompts_when_expired(self):
        c=self.client()
        def thread(*args,**kwargs):return Mock(start=kwargs['target'])
        with patch('campus_lan.client.threading.Thread',side_effect=thread),patch.object(auth_client,'resume_session',return_value=('127.0.0.1',31417)):
            c.start_signin(saved_only=True);c.consume()
        self.assertEqual(c.auth_destination,('127.0.0.1',31417));c.request_popup.assert_not_called()
        c=self.client()
        with patch('campus_lan.client.threading.Thread',side_effect=thread),patch.object(auth_client,'resume_session',return_value=None):
            c.start_signin(saved_only=True);c.consume()
        c.request_popup.assert_not_called()
        self.assertIn('Staying in guest mode',' '.join(c.lines))

    def test_on_requests_browser_only_after_saved_reuse_fails(self):
        c=self.client()
        def thread(*args,**kwargs):return Mock(start=kwargs['target'])
        with patch('campus_lan.client.threading.Thread',side_effect=thread),patch.object(auth_client,'resume_session',return_value=None):
            c.start_signin();c.consume()
        self.assertEqual(c.request_popup.call_args.args[0],'signin')

    def test_toggle_attempts_once_and_explicit_logout_pauses_it(self):
        c=self.client();c.start_signin=Mock()
        LoginSettings().set('autologin','saved')
        c.auto_login_tick();c.auto_login_tick();c.start_signin.assert_called_once_with(saved_only=True)
        from campus_lan.login_settings import pause_for_session
        pause_for_session();c=self.client();c.start_signin=Mock();c.auto_login_tick();c.start_signin.assert_not_called()

    def test_first_verified_login_offers_once_and_remembers_yes_or_no(self):
        for answer,expected in ((True,'on'),(False,'off')):
            settings=LoginSettings()
            if settings.path.exists():settings.path.unlink()
            c=self.client();c.secure=True;c.popup_prompts=Mock();c.start_signin=Mock()
            c.auto_login_tick();c.auto_login_tick()
            confirm=c.popup_prompts.return_value.confirm
            confirm.assert_called_once()
            self.assertEqual(LoginSettings().data['autologin'],'off')
            confirm.call_args.args[1 if answer else 2]()
            stored=LoginSettings()
            self.assertEqual(stored.data['autologin'],expected)
            self.assertTrue(stored.data['autologin_asked'])
            c=self.client();c.secure=True;c.popup_prompts=Mock()
            c.auto_login_tick();c.popup_prompts.assert_not_called()

    def test_guest_and_failed_signin_do_not_offer_and_old_settings_migrate(self):
        c=self.client();c.popup_prompts=Mock();c.auto_login_tick()
        c.popup_prompts.assert_not_called()
        settings=LoginSettings();settings.path.write_text('{"autologin":"off","close_tab":true}')
        settings.path.chmod(0o600)
        self.assertFalse(LoginSettings().data['autologin_asked'])
        c=self.client();c.secure=True;c.popup_prompts=Mock();c.auto_login_tick()
        c.popup_prompts.return_value.confirm.assert_called_once()

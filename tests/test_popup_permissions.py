import collections
import queue
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.popup_permissions import Permissions,Prompts
from campus_lan.client import Client

class Consent(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        patcher=patch('campus_lan.popup_permissions.config_dir',return_value=Path(self.tmp.name))
        patcher.start();self.addCleanup(patcher.stop)
        self.settings=Permissions('owner');self.reports=[];self.prompts=Prompts(self.settings,self.reports.append)

    def test_enter_denies_and_once_does_not_persist(self):
        action=Mock();p=self.prompts
        p.request('forknite','Open game?',action);p.activate();action.assert_not_called()
        p.answer('');action.assert_not_called();self.assertEqual(self.settings.persistent_mode('forknite'),'ask')
        p.request('forknite','Open game?',action);p.activate();p.answer('y');action.assert_called_once()
        self.assertEqual(p.activate()[3],'always');p.answer('')
        self.assertEqual(self.settings.persistent_mode('forknite'),'ask')

    def test_always_is_separate_and_help_opens_immediately_afterwards(self):
        action=Mock();p=self.prompts
        p.request('help','Open guide?',action);p.activate();p.answer('y')
        self.assertEqual(self.settings.persistent_mode('help'),'ask')
        p.activate();p.answer('yes');self.assertEqual(Permissions('owner').mode('help'),'allow')
        action.reset_mock();p.request('help','Open guide?',action);action.assert_called_once()
        self.assertEqual(Permissions('other').mode('help'),'ask')
        self.assertEqual(self.settings.path.stat().st_mode&0o777,0o600)

    def test_revocation_and_notification_coalescing(self):
        action=Mock();p=self.prompts
        p.request('profiles','Open?',action);self.settings.set('profiles','deny')
        self.assertIsNone(p.activate());action.assert_not_called()
        for i in range(40):p.request('notifications','Notice '+str(i),action)
        self.assertEqual(len(p.pending),1);self.assertIn('39',p.activate()[1])

    def test_failed_launch_never_offers_always(self):
        p=self.prompts;p.request('help','Open?',lambda:False);p.activate();p.answer('y')
        self.assertIsNone(p.activate());self.assertEqual(self.settings.persistent_mode('help'),'ask')

    def test_prompt_preserves_unfinished_input_and_blocks_room_browser(self):
        c=Client.__new__(Client);c.name='owner';c.lines=collections.deque();c.inbox=queue.Queue()
        c.input='an unfinished message';c.play=False
        with patch('webbrowser.open_new_tab') as browser:
            c.inbox.put(dict(type='browser_game',room='1',url='http://127.0.0.1:4242',ticket='private-ticket'))
            c.consume();browser.assert_not_called();c.permission_tick()
            self.assertEqual(c.input,'');self.assertTrue(c.permission_prompt)
            c.permission_answer('');self.assertEqual(c.input,'an unfinished message');browser.assert_not_called()
        self.assertNotIn('private-ticket',' '.join(c.lines))

    def test_help_keeps_terminal_content_and_uses_local_guide(self):
        c=Client.__new__(Client);c.name='owner';c.lines=collections.deque();c.game={}
        c.open_urls=Mock();c.show_help()
        args=c.open_urls.call_args.args
        self.assertEqual(args[0],'help');self.assertTrue(args[1][0].endswith('/docs/quick-guide.html'))
        self.assertTrue(c.lines)

    def test_global_browser_policy_inherits_with_overrides_and_master_deny(self):
        settings=self.settings;settings.set('browser','allow')
        for category in ('help','forknite','profiles','signin','tools','photos'):
            self.assertEqual(settings.mode(category),'allow')
        self.assertEqual(settings.mode('notifications'),'ask');self.assertEqual(settings.mode('terminals'),'ask')
        settings.set('profiles','ask');self.assertEqual(settings.mode('profiles'),'ask')
        settings.set('profiles','inherit');self.assertEqual(settings.mode('profiles'),'allow')
        settings.set('help','allow');settings.set('browser','deny')
        self.assertEqual(settings.mode('help'),'deny');self.assertEqual(settings.mode('photos'),'deny')
        settings.set('all','inherit');self.assertEqual(settings.mode('help'),'ask')

    def test_forknite_opens_fresh_ticket_only_after_yes_then_asks_always(self):
        c=Client.__new__(Client);c.name='owner';c.lines=collections.deque();c.inbox=queue.Queue();c.input='';c.play=False
        def thread(*args,**kwargs):return Mock(start=lambda:kwargs['target']())
        with patch('webbrowser.open_new_tab',return_value=True) as browser,patch('campus_lan.client.threading.Thread',side_effect=thread):
            c.inbox.put(dict(type='browser_game',room='1',url='http://127.0.0.1:4242',ticket='fresh'))
            c.consume();c.permission_tick();browser.assert_not_called()
            c.permission_answer('y');browser.assert_called_once_with('http://127.0.0.1:4242/#lan42=fresh')
            c.consume();c.permission_tick();self.assertEqual(c.popup_prompts().active[3],'always')
            c.permission_answer('');self.assertEqual(self.settings.persistent_mode('forknite'),'ask')

    def test_one_browser_approval_covers_inherited_children_but_not_overrides(self):
        p=self.prompts;first=Mock();next_action=Mock()
        p.request('help','Open guide?',first);self.assertEqual(p.activate()[0],'browser');p.answer('y')
        first.assert_called_once();self.assertEqual(self.settings.mode('forknite'),'allow')
        self.assertEqual(self.settings.mode('photos'),'allow')
        p.activate();p.answer('')
        p.request('profiles','Open profile?',next_action);next_action.assert_called_once();self.assertIsNone(p.activate())
        self.assertEqual(self.settings.persistent_mode('browser'),'ask')
        self.settings.set('profiles','ask');next_action.reset_mock()
        p.request('profiles','Open profile?',next_action);next_action.assert_not_called()
        self.assertEqual(p.activate()[0],'profiles');p.answer('')
        self.settings.set('browser','ask');self.assertEqual(self.settings.mode('forknite'),'ask')

    def test_browser_session_is_shared_across_windows_and_expires_with_hq(self):
        import os
        with patch.dict(os.environ,{'LAN42_POPUP_SESSION':'a'*32,'LAN42_POPUP_OWNER_PID':str(os.getpid())}):
            settings=Permissions('owner');settings.grant_once('forknite')
            self.assertEqual(Permissions('owner').mode('profiles'),'allow')
            self.assertEqual(Permissions('different-user').mode('profiles'),'ask')
            with patch('campus_lan.popup_permissions.session_alive',return_value=False):
                self.assertEqual(Permissions('owner').mode('profiles'),'ask')
            settings.set('browser','ask');self.assertEqual(Permissions('owner').mode('profiles'),'ask')

    def test_settings_summary_distinguishes_inherit_and_session_from_persistence(self):
        self.assertIn('help=inherit',self.settings.summary('help'))
        self.settings.grant_once('help')
        self.assertIn('allowed this session',self.settings.summary('browser'))
        self.assertEqual(self.settings.persistent_mode('browser'),'ask')
        self.settings.set('browser','allow')
        self.assertIn('browser=allow',self.settings.summary('browser'))

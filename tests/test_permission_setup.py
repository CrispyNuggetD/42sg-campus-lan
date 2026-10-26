import collections
import os
import tempfile
import unittest
from unittest.mock import Mock,patch
from campus_lan.client import Client
from campus_lan.popup_permissions import CATEGORIES

class Setup(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,XDG_CONFIG_HOME=tmp.name);env.start();self.addCleanup(env.stop)
        self.c=Client.__new__(Client);self.c.name='owner';self.c.lines=collections.deque();self.c.input='';self.c.play=False;self.c.wizard=None

    def test_all_requires_confirmation_and_keeps_file_approval_separate(self):
        c=self.c;approval=Mock();approval.popup_category='notifications';c.popup_prompts().confirm('Receive this file?',approval)
        c.permission_setup_command('/allow all')
        self.assertTrue(all(c.popup_prompts().permissions.persistent_mode(k)=='ask' for k in CATEGORIES))
        c.wizard_answer('y')
        self.assertTrue(all(c.popup_prompts().permissions.persistent_mode(k)=='allow' for k in CATEGORIES))
        self.assertEqual(c.popup_prompts().activate()[3],'decision');approval.assert_not_called()
        self.assertIsNone(c.wizard)

    def test_batch_y_n_and_all_choice(self):
        c=self.c;c.permission_setup_command('/setup')
        c.wizard_answer('n');self.assertEqual(c.popup_prompts().permissions.persistent_mode('browser'),'ask')
        c.wizard_answer('y');self.assertEqual(c.popup_prompts().permissions.persistent_mode('help'),'allow')
        c.wizard_answer('n');self.assertEqual(c.popup_prompts().permissions.persistent_mode('forknite'),'deny')
        c.wizard_answer('all')
        self.assertTrue(all(c.popup_prompts().permissions.persistent_mode(k)=='allow' for k in CATEGORIES))

    def test_decline_all_and_cancel_do_not_grant(self):
        c=self.c;c.permission_setup_command('/allow all');c.wizard_answer('')
        self.assertTrue(all(c.popup_prompts().permissions.persistent_mode(k)=='ask' for k in CATEGORIES))
        c.permission_setup_command('/allow batch');c.wizard_answer('/cancel');self.assertIsNone(c.wizard)

    def test_setup_can_interrupt_popup_without_executing_it(self):
        c=self.c;action=Mock();c.popup_prompts().request('help','Open help?',action)
        c.permission_tick();self.assertTrue(c.permission_prompt)
        c.permission_setup_command('/allow all');c.permission_tick();action.assert_not_called()
        c.wizard_answer('y');c.permission_tick();action.assert_called_once()

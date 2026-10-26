import collections
import unittest
from unittest.mock import Mock
from campus_lan.about import NAME,DESCRIPTION,REPOSITORY,lines
from campus_lan.client import Client

class About(unittest.TestCase):
    def test_public_identity_is_canonical_and_terminal_about_never_launches_browser(self):
        self.assertEqual(NAME,"Ryker's 42SG Campus LAN Server")
        self.assertEqual(REPOSITORY,'https://github.com/CrispyNuggetD/42sg-campus-lan')
        self.assertTrue(DESCRIPTION.startswith('Student-built terminal LAN lobby for 42 Singapore:'))
        c=Client.__new__(Client);c.lines=collections.deque();c.open_urls=Mock()
        self.assertTrue(c.about_command('/about'));c.open_urls.assert_not_called()
        self.assertIn(REPOSITORY,' '.join(c.lines));self.assertIn('explicit group',' '.join(c.lines).lower())
        c.about_command('/about repo')
        c.open_urls.assert_called_once_with('browser',[REPOSITORY],'Open the public LAN42 source repository in your browser?')

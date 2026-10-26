"""Keep the README excerpt consumed by external installers honest and readable."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FeatureList(unittest.TestCase):
    def test_exported_features_reference_real_commands_not_disabled_transfers(self):
        text = (ROOT/'README.md').read_text()
        start, end = '<!-- shell-installer-features:start -->', '<!-- shell-installer-features:end -->'
        self.assertEqual(text.count(start), 1)
        self.assertEqual(text.count(end), 1)
        block = text.split(start)[1].split(end)[0].strip()
        self.assertLessEqual(len(block.splitlines()), 8)
        client = (ROOT/'campus_lan/client.py').read_text()
        shell = (ROOT/'useful-scripts/campus.zsh').read_text()
        for command in re.findall(r'`([^`]+)`', block):
            self.assertIn(command, client if command.startswith('/') else shell)
        self.assertNotIn('KoelDrop', block)
        self.assertNotIn('/files', block)

if __name__ == '__main__':
    unittest.main()

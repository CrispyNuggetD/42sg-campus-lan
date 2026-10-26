import html
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lan42_website',ROOT/'website/build.py')
site=importlib.util.module_from_spec(spec);spec.loader.exec_module(site)

class Website(unittest.TestCase):
    def test_current_help_is_shared_with_offline_visual_guide(self):
        guide=(ROOT/'docs/quick-guide.html').read_text()
        self.assertEqual(guide,site.guide())
        for line in site.help_lines():self.assertIn(html.escape(line),guide)
        self.assertIn('git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git',guide)
        self.assertNotIn('Sharing is disabled',guide)
        self.assertIn('/volume',guide)
        self.assertIn('/koel create',guide)

    @unittest.skipUnless(importlib.util.find_spec("markdown"), "Install website/requirements.txt for site build checks")
    def test_site_builds_both_guides_without_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);site.build(output)
            self.assertEqual({p.name for p in output.iterdir()},{'index.html','handbook.html','.nojekyll'})
            index=(output/'index.html').read_text();handbook=(output/'handbook.html').read_text()
            self.assertIn('href="handbook.html"',index)
            self.assertIn('Ryker',handbook)
            self.assertIn('href="index.html"',handbook)
            self.assertNotIn('href="docs/',handbook)
            self.assertNotIn('/home/hnah',index)
            self.assertNotIn('file://',index)

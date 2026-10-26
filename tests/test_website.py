import html
import re
from urllib.parse import urlsplit
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
        self.assertIn('LAN42 BETA',guide)
        self.assertIn('og:title\" content=\"LAN42 BETA',guide)
        self.assertIn('/koel create',guide)

    @unittest.skipUnless(importlib.util.find_spec("markdown"), "Install website/requirements.txt for site build checks")
    def test_site_builds_both_guides_without_private_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp);site.build(output)
            self.assertEqual({p.name for p in output.iterdir()},{'index.html','commands.html','alpha-tester.html','.nojekyll'} | set(site.DOCUMENT_PAGES.values()))
            index=(output/'index.html').read_text();handbook=(output/'handbook.html').read_text()
            self.assertIn('href="handbook.html"',index)
            self.assertIn('Christopher Nah',index)
            self.assertIn('Darren',index)
            self.assertIn('id="contributors"',index)
            self.assertIn('LAN42 user guide',handbook)
            self.assertIn('href="getting-started.html"',handbook)
            getting_started=(output/'getting-started.html').read_text()
            self.assertIn('href="https://api.intra.42.fr/apidoc/guides/getting_started"',getting_started)
            self.assertIn('<code>INTRA_CLIENT_ID</code>',getting_started)
            self.assertNotIn("[42's getting-started guide]",getting_started)
            self.assertIn('<summary>Optional 42 API lookup</summary>',getting_started)

            self.assertNotIn('AI-assisted, human-directed',handbook)
            self.assertNotIn('runtime-help:start',index)
            self.assertIn('runtime-help:start',(output/'commands.html').read_text())
            self.assertIn('Campus seats need an approved host running on campus',index)
            self.assertIn('sh setup.sh',index)
            self.assertIn('class="start-layout"',index)
            self.assertIn('data-copy-source="install-code" hidden',index)
            self.assertIn('data-copy-command="/games" hidden',index)
            self.assertIn('Search needs JavaScript',(output/'commands.html').read_text())
            self.assertIn('api.github.com/user/222878446',(output/'alpha-tester.html').read_text())
            credit=(output/'alpha-tester.html').read_text()
            self.assertIn('Thank you, Darren · LAN42 BETA',credit)
            self.assertIn('class="hero"',credit)
            self.assertIn('background:#13293c',credit)
            self.assertIn('<noscript>',credit)
            self.assertIn('https://github.com/whatisthisbuffoonery',credit)
            self.assertIn('user.id!==222878446',credit)
            self.assertNotIn('{{',credit)

            self.assertIn('href="index.html"',handbook)
            self.assertNotIn('href="docs/',handbook)
            self.assertNotIn('/home/hnah',index)
            self.assertNotIn('file://',index)
            for page in output.glob('*.html'):
                self.assertIn('lan42.pointer-effects',page.read_text())
                self.assertIn('pointer-events:none',page.read_text())
                for href in re.findall(r'href="([^"]+)"',page.read_text()):
                    link=urlsplit(html.unescape(href))
                    if not link.scheme and not link.netloc and link.path:
                        self.assertTrue((page.parent/link.path).exists(),(page.name,href))

            roadmap=(output/'roadmap.html').read_text()
            frontend=(output/'frontend-milestone.html').read_text()
            self.assertIn('Roadmap and collaboration',roadmap)
            self.assertIn('href="frontend-milestone.html"',roadmap)
            self.assertIn('href="roadmap.html"',frontend)
            self.assertIn('appendix-architecture-considerations-and-future-learning',frontend)
            self.assertIn('global 42 Slack',roadmap)
            self.assertIn('/issues/new',roadmap)
            self.assertIn('File-sharing review',roadmap)
            self.assertIn('Reliability and hosting',roadmap)
            for page in (roadmap,frontend):
                self.assertIn('aria-label="Page contents"',page)
                self.assertNotIn('{{',page)
                self.assertNotIn('href="frontend-milestone.md',page)

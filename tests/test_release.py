import collections
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from campus_lan.client import Client
from campus_lan.release import banner, changelog

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('release_tool', ROOT/'tools/release.py')
release=importlib.util.module_from_spec(spec);spec.loader.exec_module(release)

class Release(unittest.TestCase):
    def test_semantic_categories(self):
        for messages, expected in [(['fix: volume default 30'],'patch'),(['feat: API tool'],'minor'),(['fix: a','feat!: protocol'],'major'),(['fix: x\n\nBREAKING CHANGE: wire'],'major')]:
            self.assertEqual(release.classify(messages),expected)
        self.assertEqual(release.bump('2.0.0-beta.1','patch'),'2.0.1-beta.1')
        self.assertEqual(release.bump('2.3.4-beta.1','minor'),'2.4.0-beta.1')
        self.assertEqual(release.bump('2.3.4-beta.1','major'),'3.0.0-beta.1')
    def test_local_history_command(self):
        c=Client.__new__(Client);c.lines=collections.deque()
        self.assertTrue(c.about_command('/changelog'))
        self.assertIn('/changelog',banner())
        self.assertIn('dthoo',' '.join(changelog()))
        self.assertIn('alpha-tester.html',' '.join(c.lines))
    def test_runtime_filter_and_idempotent_release_in_real_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'campus_lan').mkdir();meta=root/'campus_lan/release.json'
            def git(*args):
                return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
            def commit(message):
                git('add','.');git('commit','-qm',message)
            git('init','-q');git('config','user.name','Test');git('config','user.email','test@example.invalid')
            code=root/'campus_lan/volume.py';code.write_text('VOLUME=50\n')
            (root/'README.md').write_text('Words\n');commit('initial')
            with patch.object(release,'ROOT',root),patch.object(release,'META',meta):
                data=dict(version='2.0.0-beta.1',date='2026-10-27T00:48:00+08:00',source=git('rev-parse','HEAD'),runtime_sha256=release.fingerprint(),history=[])
                meta.write_text(json.dumps(data));commit('release baseline')
                (root/'README.md').write_text('Better words\n');commit('feat: document a feature')
                self.assertFalse(release.prepare())
                code.write_text('# comment\nVOLUME = 50\n');commit('docs: clarify source')
                self.assertFalse(release.prepare())
                code.write_text('VOLUME=30\n');commit('fix: lower volume')
                self.assertTrue(release.prepare())
                self.assertEqual(json.loads(meta.read_text())['version'],'2.0.1-beta.1')
                self.assertFalse(release.prepare())
                commit('chore: release')
                code.write_text('VOLUME=30\nNEW_FEATURE=True\n');commit('feat: add feature')
                self.assertTrue(release.prepare())
                self.assertEqual(json.loads(meta.read_text())['version'],'2.1.0-beta.1')

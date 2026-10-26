from pathlib import Path
import tempfile
import unittest
from campus_lan.avatar_cache import AvatarCache
from campus_lan.avatar_imports import BrowserImports


class BrowserSave(unittest.TestCase):
    def test_only_authorized_job_is_imported_then_staging_file_is_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=AvatarCache(Path(tmp)/'cache');imports=BrowserImports(cache,Path(tmp)/'Downloads')
            try:
                job=imports.prepare('hnah')['job']
                unrelated=imports.root/'other.png';unrelated.write_bytes(b'\x89PNG\r\n\x1a\nother')
                target=imports.root/(job+'.png');target.write_bytes(b'\x89PNG\r\n\x1a\nphoto')
                imports.consume(job)
                self.assertEqual(imports.status(job)['status'],'cached')
                self.assertFalse(target.exists());self.assertTrue(unrelated.exists())
                self.assertEqual(cache.read('hnah')[0],b'\x89PNG\r\n\x1a\nphoto')
                self.assertEqual(imports.root.stat().st_mode&0o777,0o700)
            finally:imports.close()

    def test_html_and_symlinks_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=AvatarCache(Path(tmp)/'cache');imports=BrowserImports(cache,Path(tmp)/'Downloads')
            try:
                job=imports.prepare('hnah')['job'];target=imports.root/(job+'.png');target.write_bytes(b'<html>blocked</html>')
                imports.consume(job);self.assertEqual(imports.status(job)['status'],'invalid_image')
                job=imports.prepare('hnah')['job'];(imports.root/(job+'.png')).symlink_to(target)
                imports.consume(job);self.assertEqual(imports.status(job)['status'],'invalid_file')
                with self.assertRaises(FileNotFoundError):cache.read('hnah')
            finally:imports.close()

    def test_completed_imports_do_not_exhaust_batch_pending_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache=AvatarCache(Path(tmp)/'cache');imports=BrowserImports(cache,Path(tmp)/'Downloads')
            try:
                for i in range(25):
                    job=imports.prepare('u'+str(i))['job']
                    (imports.root/(job+'.png')).write_bytes(b'\x89PNG\r\n\x1a\nfixture')
                    imports.consume(job)
                    self.assertEqual(imports.status(job)['status'],'cached')
            finally:imports.close()

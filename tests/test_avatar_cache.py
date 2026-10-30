import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch
from campus_lan.avatar_cache import AvatarCache,PHOTO_FETCHES_PER_HOUR,key,image_type

PNG=b'\x89PNG\r\n\x1a\n'+b'fixture'


class Cache(unittest.TestCase):
    def test_private_store_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=AvatarCache(Path(tmp)/'photos');c.store('hnah',PNG)
            self.assertEqual(c.read('hnah'),(PNG,'image/png'))
            self.assertEqual(c.root.stat().st_mode&0o777,0o700)
            for path in c.root.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertNotIn('hnah',(c.root/(key('hnah')+'.json')).read_text())

    def test_old_or_missing_metadata_reuses_photo_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=AvatarCache(tmp)
            c.store('hnah',PNG)
            meta=c.root/(key('hnah')+'.json')
            for metadata in ({'saved_at':1}, None):
                if metadata is None:meta.unlink()
                else:meta.write_text(json.dumps(metadata))
                with patch('campus_lan.avatar_cache.urllib.request.build_opener') as opener:
                    self.assertEqual(c.fetch('hnah','https://cdn.intra.42.fr/a.jpg')['status'],'cached')
                    opener.assert_not_called()
                self.assertEqual(c.read('hnah')[0],PNG)

    def test_no_html_svg_paths_or_git(self):
        for payload in (b'<html>denied</html>',b'<svg></svg>',b'x'*1048577):
            with self.assertRaises(ValueError):image_type(payload)
        with self.assertRaises(ValueError):key('../secret')
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'.git').mkdir()
            with self.assertRaises(ValueError):AvatarCache(Path(tmp)/'photos')

    def test_blocked_refresh_preserves_previous_image_and_backs_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=AvatarCache(tmp);c.store('hnah',PNG)
            response=urllib.error.HTTPError('https://cdn.intra.42.fr/a.jpg',403,'Forbidden',{},io.BytesIO(b'error code: 1010'))
            opener=Mock();opener.open.side_effect=response
            with patch('campus_lan.avatar_cache.urllib.request.build_opener',return_value=opener):
                result=c.fetch('hnah','https://cdn.intra.42.fr/a.jpg',force=True)
            self.assertEqual(result['http'],403);self.assertEqual(result['cloudflare_code'],'1010')
            self.assertEqual(c.read('hnah')[0],PNG)
            self.assertEqual(c.fetch('hnah','https://cdn.intra.42.fr/a.jpg')['status'],'cached')

    def test_rejects_arbitrary_fetch_destinations(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=AvatarCache(tmp)
            for url in ('http://cdn.intra.42.fr/a','https://localhost/a','https://evil.example/a','https://user:pass@cdn.intra.42.fr/a'):
                self.assertEqual(c.fetch('hnah',url)['status'],'invalid_photo_url')

    def test_direct_photo_budget_allows_six_hundredth_attempt(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(PHOTO_FETCHES_PER_HOUR,600)
            c=AvatarCache(tmp)
            (c.root/'acquisition.json').write_text(json.dumps({'requests':[9000]*599}))
            with patch('campus_lan.avatar_cache.time.time',return_value=10000), \
                 patch('campus_lan.avatar_cache.urllib.request.build_opener') as opener:
                opener.return_value.open.side_effect=OSError('offline')
                self.assertEqual(c.fetch('first','https://cdn.intra.42.fr/one.jpg')['status'],
                                 'invalid_image_or_network_error')
                self.assertEqual(c.fetch('second','https://cdn.intra.42.fr/two.jpg')['status'],
                                 'local_photo_budget_exhausted')
                self.assertEqual(opener.return_value.open.call_count,1)

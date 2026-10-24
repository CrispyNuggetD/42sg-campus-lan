import io
import json
from pathlib import Path
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch
from campus_lan.avatar_cache import AvatarCache,key,image_type

PNG=b'\x89PNG\r\n\x1a\n'+b'fixture'


class Cache(unittest.TestCase):
    def test_private_store_and_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=AvatarCache(Path(tmp)/'photos');c.store('hnah',PNG)
            self.assertEqual(c.read('hnah'),(PNG,'image/png'))
            self.assertEqual(c.root.stat().st_mode&0o777,0o700)
            for path in c.root.iterdir():self.assertEqual(path.stat().st_mode&0o777,0o600)
            self.assertNotIn('hnah',(c.root/(key('hnah')+'.json')).read_text())

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

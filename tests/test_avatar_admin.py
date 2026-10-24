import json
from pathlib import Path
from campus_lan.avatar_imports import BrowserImports
import os
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from http.server import ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs
from campus_lan import avatar_admin


class Admin(unittest.TestCase):
    def test_local_import_requires_owner_token_and_same_origin(self):
        opened=threading.Event();address=[];servers=[]
        def browser(url):address.append(url);opened.set();return True
        def server(*args,**kwargs):
            result=ThreadingHTTPServer(*args,**kwargs);servers.append(result);return result
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CACHE_HOME':tmp}),patch.object(avatar_admin,'private_read',return_value=b'{}'),patch.object(avatar_admin.webbrowser,'open',side_effect=browser),patch.object(avatar_admin,'ThreadingHTTPServer',side_effect=server),patch.object(avatar_admin,'BrowserImports',side_effect=lambda cache:BrowserImports(cache,Path(tmp)/'Downloads')):
            thread=threading.Thread(target=avatar_admin.launch,daemon=True);thread.start()
            self.assertTrue(opened.wait(3))
            url=urlsplit(address[0]);base=url.scheme+'://'+url.netloc;token=parse_qs(url.fragment)['key'][0]
            def post(key,origin):
                req=urllib.request.Request(base+'/import?login=hnah',data=b'\x89PNG\r\n\x1a\nfixture',headers={'Origin':origin,'X-LAN42-Admin':key,'Content-Type':'application/octet-stream'})
                with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
            try:
                for key,origin in [('',base),(token,'http://attacker.example')]:
                    with self.assertRaises(urllib.error.HTTPError) as rejected:post(key,origin)
                    self.assertEqual(rejected.exception.code,403)
                self.assertEqual(post(token,base)['status'],'cached')
                req=urllib.request.Request(base+'/prepare',data=b'{"login":"hnah"}',headers={'Origin':base,'X-LAN42-Admin':token,'Content-Type':'application/json'})
                with urllib.request.urlopen(req) as response:job=json.load(response)
                self.assertEqual(len(job['job']),32)
                with urllib.request.urlopen(base) as response:self.assertIn(b'cannot read your Chrome profile',response.read())
            finally:
                servers[0].shutdown();thread.join(3)
                self.assertFalse(thread.is_alive())

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
from unittest.mock import patch, AsyncMock
from urllib.parse import urlsplit,parse_qs
from campus_lan import avatar_admin


class Admin(unittest.TestCase):
    def test_local_import_requires_owner_token_and_same_origin(self):
        opened=threading.Event();address=[];servers=[]
        def browser(url):address.append(url);opened.set();return True
        def server(*args,**kwargs):
            result=ThreadingHTTPServer(*args,**kwargs);servers.append(result);return result
        with patch('campus_lan.access.Policy.local_operator',return_value=234449),tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CACHE_HOME':tmp}),patch.object(avatar_admin,'private_read',return_value=b'{}'),patch.object(avatar_admin.webbrowser,'open',side_effect=browser),patch.object(avatar_admin,'ThreadingHTTPServer',side_effect=server),patch.object(avatar_admin,'BrowserImports',side_effect=lambda cache:BrowserImports(cache,Path(tmp)/'Downloads')):
            thread=threading.Thread(target=avatar_admin.launch,kwargs={'approved':True,'photos_approved':True,'logins':['fixture-user','fixture-owner']},daemon=True);thread.start()
            self.assertTrue(opened.wait(3))
            url=urlsplit(address[0]);base=url.scheme+'://'+url.netloc;token=parse_qs(url.fragment)['key'][0]
            def post(key,origin):
                req=urllib.request.Request(base+'/import?login=fixture-owner',data=b'\x89PNG\r\n\x1a\nfixture',headers={'Origin':origin,'X-LAN42-Admin':key,'Content-Type':'application/octet-stream'})
                with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
            try:
                self.assertEqual(parse_qs(url.query)['logins'],['fixture-user fixture-owner'])
                with urllib.request.urlopen(base+'/?'+url.query) as response:
                    self.assertEqual(response.status,200)
                    self.assertIn(b'LAN42',response.read())
                with self.assertRaises(urllib.error.HTTPError) as rejected:
                    urllib.request.urlopen(base+'/missing?logins=fixture-user')
                self.assertEqual(rejected.exception.code,404)
                for key,origin in [('',base),(token,'http://attacker.example')]:
                    with self.assertRaises(urllib.error.HTTPError) as rejected:post(key,origin)
                    self.assertEqual(rejected.exception.code,403)
                self.assertEqual(post(token,base)['status'],'cached')
                req=urllib.request.Request(base+'/prepare',data=b'{"login":"fixture-owner"}',headers={'Origin':base,'X-LAN42-Admin':token,'Content-Type':'application/json'})
                with urllib.request.urlopen(req) as response:job=json.load(response)
                self.assertEqual(len(job['job']),32)
                def batch_one(login):
                    request=urllib.request.Request(base+'/batch_one',data=json.dumps({'login':login,'photo_consent':True}).encode(),headers={'Origin':base,'X-LAN42-Admin':token,'Content-Type':'application/json'})
                    with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)
                # A rejected lookup or missing photo is a per-login result, not a
                # batch-ending HTTP error; subsequent cached photos still work.
                with patch.object(avatar_admin.ProfileLookup,'lookup_many',new_callable=AsyncMock) as lookup,patch.object(avatar_admin.AvatarCache,'fetch',return_value={'status':'cached'}) as fetch:
                    lookup.side_effect=[([],['missing']),([{'login':'no-photo','avatar':None}],[]),([{'login':'valid','avatar':'https://cdn.intra.42.fr/photo.jpg'}],[])]
                    self.assertEqual(batch_one('missing')['status'],'failed')
                    self.assertEqual(batch_one('no-photo')['status'],'skipped')
                    self.assertEqual(batch_one('valid')['status'],'cached')
                    fetch.assert_called_once_with('valid','https://cdn.intra.42.fr/photo.jpg')
                with urllib.request.urlopen(base) as response:self.assertIn(b'cannot read your Chrome profile',response.read())
            finally:
                servers[0].shutdown();thread.join(3)
                self.assertFalse(thread.is_alive())

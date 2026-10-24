import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
import urllib.request
from unittest.mock import patch
from campus_lan.forknite_room import ForkniteRoom


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class RoomIdentity(unittest.IsolatedAsyncioTestCase):
    async def test_authoritative_room_identity_and_native_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'philo'
            binary.write_text('#!/bin/sh\nprintf "0 1 is eating\\n130 2 died\\n"\n')
            binary.chmod(0o700)
            with patch.dict(os.environ,{'LAN42_PHILO_BINARY':str(binary),'LAN42_FORKNITE_LOGDIR':tmp,'XDG_CACHE_HOME':tmp}):
                room=await ForkniteRoom.create()
            try:
                result=await room.control(dict(action='members',members=[dict(id='1',name='hnah',verified=True,avatar=None),dict(id='2',name='sillyguest',verified=False,avatar=None)]))
                self.assertEqual([e['slot'] for e in result['entries']],[1,2])
                base='http://127.0.0.1:'+str(room.port)
                image=b'\x89PNG\r\n\x1a\nfixture'
                room.avatar_cache.store('hnah',image)
                def redeem(ticket):
                    req=urllib.request.Request(base+'/auth/lan42',data=json.dumps(dict(ticket=ticket)).encode(),headers={'Content-Type':'application/json','Origin':base})
                    with urllib.request.urlopen(req) as response:cookie=response.headers['Set-Cookie'].split(';')[0]
                    with urllib.request.urlopen(urllib.request.Request(base+'/auth/me',headers={'Cookie':cookie})) as response:return cookie,json.load(response)
                cookie,profile=await asyncio.to_thread(redeem,result['entries'][0]['ticket'])
                self.assertEqual(profile['user']['login'],'hnah');self.assertTrue(profile['user']['verified'])
                def photo(cookie=None):
                    request=urllib.request.Request(base+'/avatars/1',headers={'Cookie':cookie} if cookie else {})
                    with urllib.request.urlopen(request) as response:return response.read(),response.headers['Content-Type']
                self.assertEqual(await asyncio.to_thread(photo,cookie),(image,'image/png'))
                with self.assertRaises(urllib.error.HTTPError) as rejected:await asyncio.to_thread(photo)
                self.assertEqual(rejected.exception.code,403)
                _,guest=await asyncio.to_thread(redeem,result['entries'][1]['ticket'])
                self.assertFalse(guest['user']['verified'])
                added=await room.control(dict(action='sabo_profiles',profiles=[dict(login='thtay',avatar=None)]))
                self.assertEqual(added['added'],['thtay'])
                again=await room.control(dict(action='sabo_profiles',profiles=[dict(login='thtay',avatar=None)]))
                self.assertEqual(again['added'],[])
                await room.control(dict(action='start'))
                await asyncio.sleep(.2)
                def snapshot():
                    with urllib.request.urlopen(base+'/events') as r:return json.loads(r.readline().decode()[6:])
                state=await asyncio.to_thread(snapshot)
                self.assertEqual(state['players'][0]['name'],'hnah')
                self.assertTrue(state['players'][0]['verified']);self.assertFalse(state['players'][1]['verified'])
                self.assertTrue(state['players'][2]['sabo']);self.assertFalse(state['players'][2]['verified'])
                self.assertTrue(any(e.get('action')=='died' for e in state['events']))
                round_event=next(e for e in state['events'] if e['type']=='round')
                self.assertEqual(round_event['args'][0],'3')
                self.assertEqual(round_event['count'],3)
                await room.control(dict(action='members',members=[]))
                def me():
                    with urllib.request.urlopen(urllib.request.Request(base+'/auth/me',headers={'Cookie':cookie})) as r:return json.load(r)
                self.assertIsNone((await asyncio.to_thread(me))['user'])
                with self.assertRaises(urllib.error.HTTPError) as rejected:await asyncio.to_thread(photo,cookie)
                self.assertEqual(rejected.exception.code,403)
            finally:
                await room.close()

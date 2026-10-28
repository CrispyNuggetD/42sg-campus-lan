import asyncio
import json
import os
from pathlib import Path
import shutil
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch, AsyncMock
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
                room.open_tools=AsyncMock()
            try:
                result=await room.control(dict(action='members',members=[dict(id='1',name='hnah',verified=True,avatar=None),dict(id='2',name='sillyguest',verified=False,avatar=None)]))
                self.assertEqual([e['slot'] for e in result['entries']],[1,2])
                base='http://127.0.0.1:'+str(room.port)
                image=b'\x89PNG\r\n\x1a\nfixture'
                room.avatar_cache.store('hnah',image)
                room.avatar_cache.store('sillyguest',b'\x89PNG\r\n\x1a\nguest')
                initial_roster=(await room.control(dict(action='roster')))['players']
                initial_photo_url=initial_roster[0]['avatar']
                def redeem(ticket):
                    req=urllib.request.Request(base+'/auth/lan42',data=json.dumps(dict(ticket=ticket)).encode(),headers={'Content-Type':'application/json','Origin':base})
                    with urllib.request.urlopen(req) as response:cookie=response.headers['Set-Cookie'].split(';')[0]
                    with urllib.request.urlopen(urllib.request.Request(base+'/auth/me',headers={'Cookie':cookie})) as response:return cookie,json.load(response)
                cookie,profile=await asyncio.to_thread(redeem,result['entries'][0]['ticket'])
                self.assertEqual(profile['user']['login'],'hnah');self.assertTrue(profile['user']['verified'])
                def photo(cookie=None,avatar=initial_photo_url):
                    request=urllib.request.Request(base+avatar,headers={'Cookie':cookie} if cookie else {})
                    with urllib.request.urlopen(request) as response:return response.read(),response.headers['Content-Type']
                self.assertEqual(await asyncio.to_thread(photo,cookie),(image,'image/png'))
                with self.assertRaises(urllib.error.HTTPError) as rejected:await asyncio.to_thread(photo)
                self.assertEqual(rejected.exception.code,403)
                _,guest=await asyncio.to_thread(redeem,result['entries'][1]['ticket'])
                self.assertFalse(guest['user']['verified'])
                added=await room.control(dict(action='sabo_profiles',profiles=[dict(login='thtay',avatar=None)]))
                self.assertEqual(added['added'],['thtay'])
                room.avatar_cache.store('thtay',b'\x89PNG\r\n\x1a\nsabo')
                again=await room.control(dict(action='sabo_profiles',profiles=[dict(login='thtay',avatar=None)]))
                self.assertEqual(again['added'],[])
                await room.control(dict(action='start'))
                def snapshot():
                    with urllib.request.urlopen(base+'/events') as r:return json.loads(r.readline().decode()[6:])
                deadline=time.monotonic()+3
                while True:
                    state=await asyncio.to_thread(snapshot)
                    if any(e.get('action')=='died' for e in state['events']) or time.monotonic()>=deadline:break
                    await asyncio.sleep(.05)
                by_name={p['name']:p for p in state['players']}
                self.assertNotEqual(state['players'][0]['name'],'hnah')
                self.assertTrue(by_name['hnah']['verified']);self.assertFalse(by_name['sillyguest']['verified'])
                self.assertTrue(by_name['thtay']['sabo']);self.assertFalse(by_name['thtay']['verified'])
                for name,expected in [('hnah',image),('sillyguest',b'\x89PNG\r\n\x1a\nguest'),('thtay',b'\x89PNG\r\n\x1a\nsabo')]:
                    self.assertEqual((await asyncio.to_thread(photo,cookie,by_name[name]['avatar']))[0],expected)
                with self.assertRaises(urllib.error.HTTPError) as stale:await asyncio.to_thread(photo,cookie,initial_photo_url)
                self.assertEqual(stale.exception.code,404)
                with urllib.request.urlopen(urllib.request.Request(base+'/auth/me',headers={'Cookie':cookie})) as r:updated=json.load(r)
                self.assertEqual(updated['user']['slot'],by_name['hnah']['id'])
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

    async def test_campus_occupancy_header_is_private_current_and_not_logged_in_events(self):
        with tempfile.TemporaryDirectory() as directory:
            tmp=Path(directory).resolve();binary=tmp/'philo'
            binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o700)
            with patch.dict(os.environ,{'LAN42_PHILO_BINARY':str(binary),'LAN42_FORKNITE_LOGDIR':str(tmp),'XDG_CACHE_HOME':str(tmp)}):
                room=await ForkniteRoom.create();room.open_tools=AsyncMock()
            try:
                members=[dict(id='sg',name='fixture-sg',verified=True,campus_access=True),dict(id='remote',name='fixture-remote',verified=True,campus_access=False),dict(id='guest',name='fixture-guest',verified=False,campus_access=True)]
                result=await room.control(dict(action='members',members=members));base='http://127.0.0.1:'+str(room.port)
                def redeem(ticket):
                    request=urllib.request.Request(base+'/auth/lan42',data=json.dumps(dict(ticket=ticket)).encode(),headers={'Content-Type':'application/json','Origin':base})
                    with urllib.request.urlopen(request,timeout=3) as response:return response.headers['Set-Cookie'].split(';')[0]
                cookies=[await asyncio.to_thread(redeem,e['ticket']) for e in result['entries']]
                def status(cookie=None):
                    request=urllib.request.Request(base+'/campus-status',headers={'Cookie':cookie} if cookie else {})
                    with urllib.request.urlopen(request,timeout=3) as response:return json.load(response)
                value=dict(total=17,c1=8,c2=9,updated_at=time.time())
                await room.control(dict(action='campus_status',status=value))
                self.assertEqual((await asyncio.to_thread(status,cookies[0]))['status'],value)
                for cookie in (None,cookies[1],cookies[2]):
                    with self.assertRaises(urllib.error.HTTPError) as denied:await asyncio.to_thread(status,cookie)
                    self.assertEqual(denied.exception.code,403)
                with self.assertRaises(ValueError):await room.control(dict(action='campus_status',status=dict(value,command='invalid-field')))
                def history():
                    with urllib.request.urlopen(base+'/events',timeout=3) as response:return json.loads(response.readline().decode()[6:])
                events=(await asyncio.to_thread(history))['events']
                self.assertFalse(any(e['type']=='campus_status' for e in events))
                members[0]['campus_access']=False
                await room.control(dict(action='members',members=members))
                with self.assertRaises(urllib.error.HTTPError) as denied:await asyncio.to_thread(status,cookies[0])
                self.assertEqual(denied.exception.code,403)
            finally:await room.close()

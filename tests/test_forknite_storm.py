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


@unittest.skipUnless(shutil.which('node'),'Node.js required')
class Storm(unittest.IsolatedAsyncioTestCase):
    async def test_tightens_until_first_death_and_restarts_from_forgiving_base(self):
        with tempfile.TemporaryDirectory() as tmp:
            executable=Path(tmp)/'philo'
            executable.write_text('#!/bin/sh\nprintf "0 1 is eating\\n"\nif [ "$2" -le 550 ]; then printf "1 1 died\\n"; fi\n')
            executable.chmod(0o700)
            with patch.dict(os.environ,{'LAN42_PHILO_BINARY':str(executable),'LAN42_FORKNITE_LOGDIR':tmp,'XDG_CACHE_HOME':tmp}):room=await ForkniteRoom.create()
            try:
                await room.control(dict(action='members',members=[dict(id='1',name='a',verified=False),dict(id='2',name='b',verified=False)]))
                defaults=await room.control(dict(action='status'));self.assertTrue(defaults['settings']['storm']);self.assertEqual(defaults['deadline'],600)
                await room.control(dict(action='configure',patch=dict(pause=10)))
                await room.control(dict(action='start'))
                for _ in range(60):
                    status=await room.control(dict(action='status'))
                    if status['phase']=='finished':break
                    await asyncio.sleep(.02)
                self.assertEqual(status['phase'],'finished')
                def history():
                    with urllib.request.urlopen('http://127.0.0.1:'+str(room.port)+'/events') as r:return json.loads(r.readline().decode()[6:])['events']
                events=await asyncio.to_thread(history)
                self.assertEqual([int(e['args'][1]) for e in events if e['type']=='round'],[600,575,550])
                self.assertTrue(all(e['args'][4]=='3' for e in events if e['type']=='round'))
                await room.control(dict(action='configure',patch=dict(pause=60000)))
                await room.control(dict(action='start'))
                again=await asyncio.to_thread(history)
                self.assertEqual([e for e in again if e['type']=='round'][-1]['args'][1],'600')
                with self.assertRaises(ValueError):await room.control(dict(action='configure',patch=dict(die=1)))
                await room.control(dict(action='stop'));await asyncio.sleep(.05)
                stopped=await room.control(dict(action='status'));self.assertEqual(stopped['phase'],'stopped')
                await room.control(dict(action='configure',patch=dict(storm=False)))
                await room.control(dict(action='members',members=[dict(id='1',name='a',verified=False)]))
                with self.assertRaisesRegex(ValueError,'two diners'):await room.control(dict(action='start'))
            finally:await room.close()

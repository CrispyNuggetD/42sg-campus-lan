import asyncio
import time
import unittest
from campus_lan.server import Lobby
from campus_lan.network import seat_label

class MeshChecks(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.nodes,self.servers,self.events = [],[],[]
        for i in range(3):
            lobby = Lobby()
            lobby.owners['owner'] = dict(name=['hnah','thtay','dthoo'][i],hostname=f'c1r2s{i+1}')
            collected = []
            original = lobby.broadcast
            async def capture(data,ids=None,original=original,collected=collected):
                collected.append(data)
                await original(data,ids)
            lobby.broadcast = capture
            server = await asyncio.start_server(lobby.handle,'127.0.0.1',0,limit=131072)
            lobby.port = server.sockets[0].getsockname()[1]
            self.nodes.append(lobby)
            self.servers.append(server)
            self.events.append(collected)

    async def asyncTearDown(self):
        for server in self.servers:
            server.close()
            await server.wait_closed()

    async def link(self,left,right):
        await self.nodes[left].mesh.connect('127.0.0.1',self.nodes[right].port)

    async def test_peer_discovery_presence_chat_and_survivors(self):
        await self.link(0,1)
        await self.link(1,2)
        self.assertIn(('127.0.0.1',self.nodes[0].port),self.nodes[2].mesh.peers)
        await self.link(2,0)
        await self.link(0,1)
        for node in self.nodes:
            self.assertEqual({p['name'] for p in node.mesh.players()},{'hnah','thtay','dthoo'})
        notices = [e for e in self.events[0] if e['type']=='online' and 'thtay' in e['text']]
        self.assertEqual(len(notices),1)
        self.assertIn('Cluster 1, row 2, seat 2',notices[0]['text'])
        await self.nodes[0].mesh.publish('event','hello mesh')
        await self.link(1,0)
        await self.link(2,1)
        await self.link(0,2)
        await self.link(1,2)
        for events in self.events:
            self.assertEqual(sum(e.get('text')=='hello mesh' for e in events),1)
        # The original bootstrap node leaves; B and C still communicate directly.
        await self.nodes[0].mesh.goodbye()
        self.servers[0].close()
        await self.servers[0].wait_closed()
        await self.nodes[1].mesh.publish('event','still here')
        await self.link(2,1)
        self.assertTrue(any(e.get('text')=='still here' for e in self.events[2]))
        self.assertNotIn('hnah',{p['name'] for p in self.nodes[2].mesh.players()})

    async def test_remote_game_advertisement_and_expired_event(self):
        a,b,_ = self.nodes
        a.clients['p'] = dict(name='hnah')
        a.rooms['7'] = dict(game='tetris',host='p',members={'p'})
        # Avoid fake writer during broadcasts; snapshot needs only room metadata.
        original = a.broadcast
        async def discard(data,ids=None): pass
        a.broadcast = discard
        await self.link(1,0)
        self.assertEqual(b.mesh.rooms()[0]['address'],'127.0.0.1')
        self.assertEqual(b.mesh.rooms()[0]['port'],a.port)
        self.assertEqual(b.mesh.rooms()[0]['id'],'7')
        stale = a.mesh.snapshot()
        stale['events'] = [dict(id='a'*32,kind='event',text='stale',created=time.time()-60)]
        await b.mesh.merge('127.0.0.1',stale)
        self.assertFalse(any(e.get('text')=='stale' for e in self.events[1]))
        a.clients.clear()

    def test_seats_are_local_not_api_polling(self):
        self.assertEqual(seat_label('10.12.4.9'),'Cluster 2, row 4, seat 9')

if __name__=='__main__':
    unittest.main()

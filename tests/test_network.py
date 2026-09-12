import asyncio
import contextlib
import json
import unittest
from campus_lan.server import Lobby
from campus_lan import PROTOCOL

class Network(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.lobby = Lobby(round_seconds=1)
        self.server = await asyncio.start_server(self.lobby.handle,'127.0.0.1',0,limit=8192)
        self.port = self.server.sockets[0].getsockname()[1]
        self.sockets = []
        self.ticker = asyncio.create_task(self.lobby.tick())

    async def asyncTearDown(self):
        for r,w in self.sockets:
            w.close()
            await w.wait_closed()
        await asyncio.sleep(.1)
        self.ticker.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await self.ticker
        self.server.close()
        await self.server.wait_closed()

    async def send(self,peer,**msg):
        peer[1].write((json.dumps(msg)+'\n').encode())
        await peer[1].drain()

    async def receive(self,peer,predicate):
        async def wait():
            while True:
                msg = json.loads(await peer[0].readline())
                if predicate(msg):
                    return msg
        return await asyncio.wait_for(wait(),3)

    async def connect(self,name):
        p = await asyncio.open_connection('127.0.0.1',self.port)
        self.sockets.append(p)
        await self.send(p,type='hello',name=name,hostname='test',protocol=PROTOCOL,verified=True)
        welcome = await self.receive(p,lambda m:m['type'] in ('welcome','error'))
        return p,welcome

    async def cmd(self,p,text):
        await self.send(p,type='command',text=text)

    async def test_five_peers_chat_games_and_disconnect(self):
        peers = []
        for i in range(5):
            p,w = await self.connect('p'+str(i))
            peers.append(p)
            self.assertFalse(w['verified'])
        await self.cmd(peers[0],'hello\x1b[31m')
        event = await self.receive(peers[1],lambda m:m['type']=='event' and 'hello' in m['text'])
        self.assertNotIn('\x1b',event['text'])
        await self.cmd(peers[0],'/host tetris')
        invite = await self.receive(peers[1],lambda m:m['type']=='invite')
        self.assertIn('/join 1',invite['text'])
        await self.cmd(peers[1],'/join 1')
        await self.receive(peers[1],lambda m:m['type']=='game' and m.get('room')=='1')
        await self.cmd(peers[1],'/start')
        await self.receive(peers[1],lambda m:m['type']=='event' and 'Only' in m['text'])
        await self.cmd(peers[0],'/start')
        board = await self.receive(peers[1],lambda m:'board' in m)
        self.assertEqual(len(board['board']),18)
        await self.send(peers[1],type='move',action='drop')
        await self.receive(peers[1],lambda m:'board' in m)
        peers[0][1].close()
        await peers[0][1].wait_closed()
        await asyncio.sleep(.1)
        self.assertEqual(self.lobby.rooms['1']['host'],'2')
        await self.cmd(peers[2],'/host bluff prompt')
        await self.receive(peers[2],lambda m:m['type']=='game' and m.get('room')=='2')
        for p in (peers[3],peers[4]):
            await self.cmd(p,'/join 2')
            await self.receive(p,lambda m:m['type']=='game' and m.get('room')=='2')
        await self.cmd(peers[2],'/start')
        await self.receive(peers[2],lambda m:m.get('phase')=='writing')
        for i,p in enumerate(peers[2:]):
            await self.cmd(p,'/answer secret'+str(i))
        voting = await self.receive(peers[2],lambda m:m.get('phase')=='voting')
        self.assertTrue(all(x['author'] is None for x in voting['options']))
        result = await self.receive(peers[2],lambda m:m.get('phase')=='results')
        self.assertTrue(all(x['author'] for x in result['options']))

    async def test_peer_server_invitation(self):
        p,_ = await self.connect('friend')
        remote = await asyncio.open_connection('127.0.0.1',self.port)
        self.sockets.append(remote)
        await self.send(remote,type='peer_invite',protocol=PROTOCOL,name='host',
                        game='tetris',room='7',port=31416)
        notice = await self.receive(p,lambda m:m['type']=='invite')
        self.assertIn('/connect 127.0.0.1 31416',notice['text'])
        self.assertIn('/join 7',notice['text'])
        ack = await self.receive(remote,lambda m:m['type']=='invite_ack')
        self.assertEqual(ack['clients'],1)
        self.assertEqual(len(self.lobby.clients),1)

    async def test_duplicate_and_signin(self):
        p,_ = await self.connect('alice')
        _,denied = await self.connect('alice')
        self.assertEqual(denied['type'],'error')
        await self.cmd(p,'/signin')
        msg = await self.receive(p,lambda m:m['type']=='event' and 'coming later' in m['text'])
        self.assertIn('Guest',msg['text'])

if __name__=='__main__':
    unittest.main()

import asyncio
import contextlib
import json
import unittest
from unittest.mock import patch
from campus_lan.server import Lobby
from campus_lan import PROTOCOL

class Network(unittest.IsolatedAsyncioTestCase):
    async def test_guest_cannot_open_cluster_viewer_role(self):
        _,response=await self.connect('viewer',role='clusters')
        self.assertEqual(response['type'],'error')
        self.assertIn('verified',response['text'])

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

    async def connect(self,name,role='lobby'):
        p = await asyncio.open_connection('127.0.0.1',self.port)
        self.sockets.append(p)
        await self.send(p,type='hello',name=name,hostname='test',protocol=PROTOCOL,verified=True,role=role)
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
                        game='tetris',room='7',port=31415)
        notice = await self.receive(p,lambda m:m['type']=='invite')
        self.assertIn('/connect 127.0.0.1 31415',notice['text'])
        self.assertIn('/join 7',notice['text'])
        ack = await self.receive(remote,lambda m:m['type']=='invite_ack')
        self.assertEqual(ack['clients'],1)
        self.assertEqual(len(self.lobby.clients),1)

    async def test_two_player_bluff_round(self):
        self.lobby.round_seconds = 30
        a,_ = await self.connect('alice')
        b,_ = await self.connect('bob')
        await self.cmd(a,'/host bluff free')
        await self.receive(a,lambda m:m.get('phase')=='waiting')
        await self.cmd(a,'/start')
        await self.receive(a,lambda m:m['type']=='event' and 'at least 2' in m['text'])
        await self.cmd(b,'/join 1')
        await self.receive(b,lambda m:m.get('phase')=='waiting')
        await self.cmd(a,'/start')
        await self.receive(b,lambda m:m['type']=='event' and 'best with 3+' in m['text'])
        await self.receive(a,lambda m:m.get('phase')=='writing')
        await self.cmd(a,'/answer apples')
        await self.cmd(b,'/answer bananas')
        voting = await self.receive(a,lambda m:m.get('phase')=='voting')
        self.assertEqual(len(voting['options']),2)
        self.assertTrue(all(x['author'] is None for x in voting['options']))
        guesses = ' '.join('alice' if x['text']=='apples' else 'bob' for x in voting['options'])
        for peer in (a,b):
            await self.cmd(peer,'/vote '+guesses)
        result = await self.receive(a,lambda m:m.get('phase')=='results')
        self.assertIn('alice: 2 points',result['result'])
        self.assertIn('bob: 2 points',result['result'])

    async def test_outbound_seat_invitation_is_delimited(self):
        p,_ = await self.connect('host')
        await self.cmd(p,'/host tetris')
        await self.receive(p,lambda m:m.get('phase')=='waiting')
        with patch('campus_lan.server.seat_address',return_value='127.0.0.1'):
            await self.cmd(p,f'/invite-seat c1r2s3 {self.port}')
            await self.receive(p,lambda m:m['type']=='event' and 'Invitation delivered' in m['text'])

    async def test_game_window_keeps_hq_and_single_presence(self):
        self.lobby.owners['local'] = dict(name='alice',hostname='test')
        hq,_ = await self.connect('alice')
        initial = await self.receive(hq,lambda m:m['type']=='state')
        self.assertEqual([p['name'] for p in initial['players']],['alice'])
        game,welcome = await self.connect('alice','game')
        self.assertEqual(welcome['type'],'welcome')
        await self.cmd(game,'/host tetris')
        await self.receive(game,lambda m:m.get('phase')=='waiting')
        self.assertEqual(self.lobby.room_for('1'),(None,None))
        self.assertEqual(len(self.lobby.mesh.players()),1)
        await self.cmd(game,'/start')
        await self.receive(game,lambda m:'board' in m)
        game[1].close()
        await game[1].wait_closed()
        await asyncio.sleep(.1)
        await self.cmd(hq,'still in HQ')
        await self.receive(hq,lambda m:m['type']=='event' and 'still in HQ' in m['text'])
        self.assertFalse(self.lobby.shutdown.is_set())

    async def test_duplicate_and_signin(self):
        p,_ = await self.connect('alice')
        _,denied = await self.connect('alice')
        self.assertEqual(denied['type'],'error')
        await self.cmd(p,'/signin')
        msg = await self.receive(p,lambda m:m['type']=='event' and 'local HQ' in m['text'])
        self.assertIn('/signin',msg['text'])

    async def test_forknite_is_a_normal_room_with_per_player_browser_entry(self):
        import tempfile, os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'philo'
            binary.write_text('#!/bin/sh\nprintf "0 1 is eating\\n130 2 died\\n"\n')
            binary.chmod(0o700)
            with patch.dict(os.environ,{'LAN42_PHILO_BINARY':str(binary),'LAN42_FORKNITE_LOGDIR':tmp}):
                host,_=await self.connect('host')
                friend,_=await self.connect('friend')
                await self.cmd(host,'/game forknite')
                h=await self.receive(host,lambda m:m['type']=='browser_game')
                self.assertEqual(h['room'],'1')
                await self.cmd(friend,'/join 1')
                f=await self.receive(friend,lambda m:m['type']=='browser_game')
                self.assertEqual(f['url'],h['url'])
                self.assertNotEqual(f['ticket'],h['ticket'])
                await self.cmd(friend,'/browser')
                reopened=await self.receive(friend,lambda m:m['type']=='browser_game' and m.get('reopen'))
                self.assertEqual(reopened['room'],f['room'])
                self.assertEqual(reopened['url'],f['url'])
                self.assertNotEqual(reopened['ticket'],f['ticket'])
                self.assertEqual(len(self.lobby.rooms),1)
                await self.cmd(host,'/start')
                await self.receive(host,lambda m:m['type']=='event' and 'native simulation started' in m.get('text',''))
                await self.cmd(friend,'/leave')
                await self.cmd(host,'/leave')
                await self.receive(host,lambda m:m['type']=='game' and not m.get('game'))
                self.assertFalse(self.lobby.rooms)

    async def test_random_sabo_adds_cached_people_and_diners_fills_total(self):
        import tempfile,os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as tmp:
            binary=Path(tmp)/'philo';binary.write_text('#!/bin/sh\nsleep 2\n');binary.chmod(0o700)
            (Path(tmp)/'singapore.json').write_text(json.dumps({'students':[{'login':'student'+str(i)} for i in range(8)]+[{'login':'host'}]}))
            with patch.dict(os.environ,{'LAN42_PHILO_BINARY':str(binary),'LAN42_FORKNITE_LOGDIR':tmp,'LAN42_CAMPUS_DATA':tmp}),patch('campus_lan.forknite_room.ForkniteRoom.open_tools'),patch('campus_lan.auth.config_dir',return_value=Path(tmp)/'config'):
                host,_=await self.connect('host');friend,_=await self.connect('friend')
                await self.cmd(host,'/game forknite')
                await self.receive(host,lambda m:m['type']=='browser_game')
                await self.cmd(friend,'/join 1')
                await self.receive(friend,lambda m:m['type']=='browser_game')
                await self.cmd(friend,'/diners 7')
                await self.receive(friend,lambda m:m['type']=='event' and 'Only the FORKNITE room host' in m.get('text',''))
                await self.cmd(host,'/sabo RANDOM 5')
                await self.receive(host,lambda m:m['type']=='event' and 'Guests' in m.get('text',''))
                room=self.lobby.rooms['1']['web']
                roster=(await room.control(dict(action='roster')))['players']
                self.assertEqual(len(roster),2)
                self.assertEqual(len({p['name'] for p in roster}),2)
                await self.cmd(host,'/diners 9')
                await self.receive(host,lambda m:m['type']=='event' and 'Table set for 9' in m.get('text',''))
                self.assertEqual((await room.control(dict(action='status')))['players'],9)
                await self.cmd(host,'/diners 7')
                await self.receive(host,lambda m:m['type']=='event' and 'Table set for 7' in m.get('text',''))
                self.assertEqual((await room.control(dict(action='status')))['players'],7)
                await self.cmd(host,'/start')
                await self.receive(host,lambda m:m['type']=='event' and 'native simulation started' in m.get('text',''))
                await self.cmd(host,'/diners 8')
                await self.receive(host,lambda m:m['type']=='event' and 'Use /stop' in m.get('text',''))
                await self.cmd(friend,'/leave');await self.cmd(host,'/leave')
                await self.receive(host,lambda m:m['type']=='game' and not m.get('game'))

    async def test_direct_message_is_targeted_and_alert_is_an_alias(self):
        sender,_=await self.connect('sender');target,_=await self.connect('target');other,_=await self.connect('other')
        await self.cmd(sender,'/dm target hello privately')
        message=await self.receive(target,lambda m:m['type']=='direct_message')
        self.assertEqual(message['sender'],'sender');self.assertEqual(message['text'],'hello privately')
        self.assertFalse(message['verified'])
        await self.receive(sender,lambda m:m['type']=='event' and m.get('text','').startswith('DM to target:'))
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(self.receive(other,lambda m:m['type']=='direct_message'),.1)
        await self.cmd(target,'/alert sender hi back')
        reply=await self.receive(sender,lambda m:m['type']=='direct_message')
        self.assertEqual(reply['text'],'hi back')
        self.assertFalse(any(e['text']=='hello privately' for e in self.lobby.mesh.events.values()))

    async def test_guest_campus_tracking_is_denied_before_snapshot(self):
        peer,_=await self.connect('hnah')
        with patch('campus_lan.clusters.snapshot') as snapshot:
            await self.cmd(peer,'/campus-presence')
            result=await self.receive(peer,lambda m:m['type']=='event' and 'Guests' in m.get('text',''))
            self.assertIn('Guests',result['text'])
            snapshot.assert_not_called()

    async def test_group_dm_partial_delivery_deduplication_and_summary(self):
        sender,_=await self.connect('sender');target,_=await self.connect('target');other,_=await self.connect('other')
        await self.send(sender,type='direct_batch',targets=['target','TARGET','missing'],text='Want lunch?')
        message=await self.receive(target,lambda m:m['type']=='direct_message')
        self.assertEqual(message['text'],'Want lunch?')
        summary=await self.receive(sender,lambda m:m['type']=='dm_summary')
        self.assertEqual((summary['delivered'],summary['failed']),(1,1));self.assertEqual(summary['unavailable'],['missing'])
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(self.receive(other,lambda m:m['type']=='direct_message'),.1)
        await self.send(sender,type='direct_batch',targets=['target','bad/name'],text='Do not send any')
        await self.receive(sender,lambda m:m['type']=='event' and 'valid recipients' in m.get('text',''))
        with self.assertRaises(asyncio.TimeoutError):
            await asyncio.wait_for(self.receive(target,lambda m:m['type']=='direct_message'),.1)

    async def test_plain_chat_never_expands_photo_selectors_and_stays_bounded(self):
        sender,_=await self.connect('sender');target,_=await self.connect('target')
        await self.cmd(sender,'42sg cohort1')
        event=await self.receive(target,lambda m:m['type']=='event' and '42sg' in m.get('text',''))
        self.assertEqual(event['text'],'sender [Guest]: 42sg cohort1')
        await self.cmd(sender,'./tool cohort 1')
        event=await self.receive(target,lambda m:m['type']=='event' and './tool' in m.get('text',''))
        self.assertEqual(event['text'],'sender [Guest]: ./tool cohort 1')
        await self.cmd(sender,'42sg '+'x'*500)
        event=await self.receive(target,lambda m:m['type']=='event' and m.get('text','').startswith('sender [Guest]: 42sg x'))
        self.assertLessEqual(len(event['text']),400)
        self.assertNotIn('fixture-',event['text'])

if __name__=='__main__':
    unittest.main()

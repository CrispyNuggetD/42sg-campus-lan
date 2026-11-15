import collections
import os
import queue
import tempfile
import unittest
from unittest.mock import Mock,AsyncMock,patch
from campus_lan.campus_status import summarize,validate_status,format_status,publish_status,local_status
from campus_lan.client import Client
from campus_lan.auth import AuthError
from campus_lan.server import Lobby

STATUS=dict(total=17,c1=8,c2=9,updated_at=100)


class CampusSnapshotBroadcast(unittest.IsolatedAsyncioTestCase):
    async def test_hq_and_clusters_follow_same_snapshot_without_api_reads(self):
        lobby=Lobby(auth_broker=Mock())
        hq=dict(role='lobby',allowed=True)
        viewer=dict(role='clusters',allowed=True)
        denied=dict(role='clusters',allowed=False)
        lobby.clients=dict(hq=hq,viewer=viewer,denied=denied)
        players=[dict(name='fixture',seat='c1r1s1')]
        with patch('campus_lan.access.Policy.require_host'), \
             patch('campus_lan.campus_status.cached_status',return_value=STATUS) as status, \
             patch('campus_lan.clusters.cached_snapshot',return_value=(players,100)) as cached, \
             patch('campus_lan.clusters.snapshot') as api, \
             patch.object(lobby,'campus_allowed',side_effect=lambda c:c['allowed']), \
             patch.object(lobby,'send',new=AsyncMock()) as send:
            await lobby.send_campus_status()
            self.assertEqual(send.call_args_list[0].args,(hq,dict(type='campus_status',status=STATUS)))
            self.assertEqual(send.call_args_list[1].args,(viewer,dict(type='clusters',players=players,updated_at=100)))
            send.reset_mock()
            await lobby.send_campus_status()
            self.assertEqual(send.call_count,1)  # No duplicate roster on each HQ tick.
            self.assertEqual(cached.call_count,1)
            status.return_value=dict(STATUS,updated_at=130)
            cached.return_value=([],130)
            await lobby.send_campus_status()
            self.assertEqual(send.call_args.args,(viewer,dict(type='clusters',players=[],updated_at=130)))
            viewer['allowed']=False
            send.reset_mock();status.return_value=dict(STATUS,updated_at=160)
            await lobby.send_campus_status()
            self.assertEqual(send.call_count,1)
            api.assert_not_called()

    async def test_host_revocation_prevents_cached_roster_delivery(self):
        lobby=Lobby(auth_broker=Mock());lobby.clients={'viewer':dict(role='clusters')}
        with patch('campus_lan.access.Policy.require_host',side_effect=AuthError('revoked')), \
             patch('campus_lan.clusters.cached_snapshot') as cached, \
             patch.object(lobby,'campus_allowed',return_value=True), \
             patch.object(lobby,'send',new=AsyncMock()) as send:
            await lobby.send_campus_status()
            cached.assert_not_called();send.assert_not_called()

    async def test_racing_snapshot_waits_for_next_matching_hq_tick(self):
        lobby=Lobby(auth_broker=Mock());viewer=dict(role='clusters');lobby.clients={'viewer':viewer}
        with patch('campus_lan.access.Policy.require_host'), \
             patch('campus_lan.campus_status.cached_status',return_value=STATUS), \
             patch('campus_lan.clusters.cached_snapshot',return_value=([],130)), \
             patch.object(lobby,'campus_allowed',return_value=True), \
             patch.object(lobby,'send',new=AsyncMock()) as send:
            await lobby.send_campus_status()
            send.assert_not_called();self.assertNotIn('campus_snapshot_sent',viewer)


class CampusStatus(unittest.TestCase):
    def test_unique_logins_are_counted_once_and_split_balances(self):
        status=summarize([dict(id='1',name='fixture-one',seat='c1r1s1'),dict(id='2',name='FIXTURE-ONE',seat='c2r1s1'),dict(id='3',name='fixture-two',seat='c1r1s2'),dict(name='off-campus',seat='unknown')],100)
        self.assertEqual(status,dict(total=2,c1=1,c2=1,updated_at=100))
        self.assertEqual(summarize([],100),dict(total=0,c1=0,c2=0,updated_at=100))
        self.assertIn('17 online (C1:8 | C2:9)',format_status(STATUS,110))
        self.assertIn('stale',format_status(STATUS,230));self.assertIn('unavailable',format_status(None))
        for value in ({},dict(STATUS,total=True),dict(STATUS,c1=-1),dict(STATUS,total=99),dict(STATUS,updated_at=float('nan')),dict(STATUS,command='bad')):
            self.assertIsNone(validate_status(value))

    def test_local_status_file_never_grants_operator_access(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}):
            publish_status(STATUS)
            with patch('campus_lan.access.Policy.local_operator',side_effect=AuthError('denied')):
                with self.assertRaises(AuthError):local_status()
            with patch('campus_lan.access.Policy.local_operator'):
                self.assertEqual(local_status(),STATUS)

    def test_terminal_header_in_hq_and_every_game_at_minimum_width(self):
        from test_lobby_view import Canvas
        for role,game in (('lobby',{}),('game',{}),('game',dict(game='tetris',board=[],score=0,over=False)),('game',dict(game='bluff',phase='waiting',room='1'))):
            c=Client.__new__(Client);c.name='fixture-owner';c.role=role;c.secure=True;c.connected=True;c.input='';c.play=False;c.scroll=0
            c.lines=collections.deque();c.game=game;c.state=dict(players=[]);c.campus_occupancy=STATUS
            screen=Canvas(28,76);c.draw(screen)
            self.assertIn('17 online (C1:8 | C2:9)',''.join(screen.rows[1]))

    def test_guest_wire_messages_cannot_forge_occupancy(self):
        for secure,remote,expected in ((False,False,False),(True,True,False),(True,False,True)):
            c=Client.__new__(Client);c.secure=secure;c.remote_approved=remote;c.inbox=queue.Queue();c.lines=collections.deque()
            c.search_result=Mock(return_value=False);c.announcement_event=Mock(return_value=False)
            c.inbox.put(dict(type='campus_status',status=STATUS));c.consume()
            self.assertEqual(getattr(c,'campus_occupancy',None),STATUS if expected else None)

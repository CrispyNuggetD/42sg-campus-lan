"""Remote approvals are local, ephemeral and never API/campus authority."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,Mock,patch
from campus_lan.remote_access import RemoteGate,eligible
from campus_lan.server import Lobby
from campus_lan.auth import AuthError
from campus_lan.lobby_view import player_style,player_line,seat

class Addresses(unittest.TestCase):
    def test_only_explicit_private_192_network_is_eligible(self):
        for ip in ('192.168.0.1','192.168.42.8','192.168.255.254'):self.assertTrue(eligible(ip))
        for ip in ('192.0.2.1','192.169.1.1','10.8.0.1','10.11.2.3','127.0.0.1','8.8.8.8','::ffff:192.168.1.1','invalid'):self.assertFalse(eligible(ip))

    def test_green_does_not_mean_signed_in_or_seated(self):
        person=dict(name='guest-hnah',remote_approved=True,verified=False,seat='c1r2s3')
        self.assertEqual(player_style(person),1)
        self.assertIsNone(seat(person))
        self.assertIn('Remote approved / unverified',''.join(x for x,_ in player_line(1,person,None)))
        person['verified']=True
        self.assertIn('42 signed in',''.join(x for x,_ in player_line(1,person,None)))

class Gate(unittest.IsolatedAsyncioTestCase):
    async def decide(self,gate,action,request):
        reader=asyncio.StreamReader();reader.feed_data((json.dumps(dict(action=action,id=request))+'\n').encode());reader.feed_eof()
        writer=Mock();writer.drain=AsyncMock()
        await gate.control(reader,writer)
        return json.loads(writer.write.call_args.args[0])

    async def test_one_live_socket_approval_then_revoke(self):
        gate=RemoteGate();writer=Mock()
        task=asyncio.create_task(gate.admit('192.168.42.2','guest',writer))
        await asyncio.sleep(0)
        request=next(iter(gate.pending))
        self.assertFalse(task.done())
        self.assertEqual(await self.decide(gate,'approve',request),{'ok':True})
        self.assertEqual(await task,request)
        self.assertNotIn(request,gate.pending)
        self.assertIn('error',await self.decide(gate,'approve',request))
        await self.decide(gate,'revoke',request);writer.close.assert_called_once()
        self.assertNotIn(request,gate.active)

    async def test_other_ips_never_create_pending_requests(self):
        gate=RemoteGate()
        for ip in ('10.8.2.3','10.11.1.1','8.8.8.8'):
            with self.assertRaises(ValueError):await gate.admit(ip,'hnah',Mock())
        self.assertEqual(gate.pending,{})

    async def test_denied_connection_never_becomes_active(self):
        gate=RemoteGate();task=asyncio.create_task(gate.admit('192.168.1.2','guest',Mock()))
        await asyncio.sleep(0);request=next(iter(gate.pending))
        await self.decide(gate,'deny',request)
        with self.assertRaises(ValueError):await task
        self.assertEqual(gate.active,{})

    async def test_mac_only_control_socket_and_no_implicit_opt_in(self):
        with patch('sys.platform','linux'):
            with self.assertRaises(ValueError):await RemoteGate().start(31417)
        self.assertIsNone(Lobby().remote_gate)

    async def test_remote_is_denied_api_even_if_real_sg_session(self):
        lobby=Lobby(auth_broker=Mock())
        with self.assertRaises(AuthError):lobby.api_identity(dict(uid=234449,remote_approved=True))
        lobby.auth_broker.active.assert_not_called()
        lobby.clients={'1':dict(name='guest',remote_approved=True)}
        for command in ('/clusters','/campus-presence','/info','/sabo hnah','/invite-seat c1r2s3','/broadcast hi'):
            with self.subTest(command=command),self.assertRaises(AuthError):await lobby.command('1',command)

    async def test_tls_guest_needs_host_approval_and_cannot_claim_uid(self):
        from campus_lan import PROTOCOL
        lobby=Lobby(auth_broker=Mock())
        lobby.remote_gate=RemoteGate();lobby.state=AsyncMock();lobby.event=AsyncMock()
        reader=asyncio.StreamReader()
        reader.feed_data((json.dumps(dict(type='hello',protocol=PROTOCOL,name='hnah',hostname='c1r2s3',uid=234449,verified=True,remote_approved=True))+'\n').encode());reader.feed_eof()
        writer=Mock();writer.is_closing.return_value=False;writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
        writer.get_extra_info.side_effect=lambda key:('192.168.2.3',1234) if key=='peername' else object() if key=='ssl_object' else ('192.168.2.1',31417)
        task=asyncio.create_task(lobby.handle(reader,writer))
        for _ in range(20):
            await asyncio.sleep(.001)
            if lobby.remote_gate.pending:break
        self.assertEqual(lobby.clients,{})
        request=next(iter(lobby.remote_gate.pending))
        await self.decide(lobby.remote_gate,'approve',request)
        await task
        messages=[json.loads(call.args[0]) for call in writer.write.call_args_list]
        welcome=next(m for m in messages if m['type']=='welcome')
        self.assertFalse(welcome['verified']);self.assertTrue(welcome['remote_approved'])
        self.assertEqual(welcome['name'],'guest-hnah')
        lobby.auth_broker.authenticate.assert_not_called()
        self.assertEqual(lobby.remote_gate.active,{})

    async def test_remote_http_cannot_reach_koeldrop_before_auth_dispatch(self):
        from campus_lan.auth import AuthHTTP
        broker=Mock();broker.policy_factory=None
        http=AuthHTTP(broker,'192.168.1.1:31416');http.remote_guests=True
        http.koeldrop=Mock();http.koeldrop.handle=AsyncMock()
        reader=asyncio.StreamReader();reader.feed_data(b'GET /v1/group HTTP/1.1\r\n\r\n');reader.feed_eof()
        writer=Mock();writer.drain=AsyncMock();writer.wait_closed=AsyncMock();writer.get_extra_info.return_value=('192.168.1.2',1234)
        await http.handle(reader,writer)
        http.koeldrop.handle.assert_not_called()
        self.assertIn(b'400 Bad Request',writer.write.call_args.args[0])

    async def test_private_local_controller_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp, patch('campus_lan.remote_access.control_path',return_value=Path(tmp)/'control.sock'),patch('sys.platform','darwin'):
            gate=RemoteGate();await gate.start(31417)
            try:
                self.assertEqual(gate.path.stat().st_mode&0o777,0o600)
                reader,writer=await asyncio.open_unix_connection(str(gate.path))
                writer.write(b'{"action":"list"}\n');await writer.drain()
                self.assertEqual(json.loads(await reader.readline()),{'pending':[],'active':[]})
                writer.close();await writer.wait_closed()
            finally:await gate.close()
            self.assertFalse((Path(tmp)/'control.sock').exists())

    async def test_genuine_signin_and_remote_approval_coexist_without_api_grant(self):
        from campus_lan import PROTOCOL
        broker=Mock();broker.authenticate.return_value=dict(uid=234449,login='hnah',session_key='test-session')
        lobby=Lobby(auth_broker=broker);lobby.remote_gate=RemoteGate();lobby.state=AsyncMock();lobby.event=AsyncMock()
        reader=asyncio.StreamReader();reader.feed_data((json.dumps(dict(type='hello',protocol=PROTOCOL,name='ignored',session='test-token'))+'\n').encode());reader.feed_eof()
        writer=Mock();writer.is_closing.return_value=False;writer.drain=AsyncMock();writer.wait_closed=AsyncMock()
        writer.get_extra_info.side_effect=lambda key:('192.168.4.2',1234) if key=='peername' else object() if key=='ssl_object' else ('192.168.4.1',31417)
        task=asyncio.create_task(lobby.handle(reader,writer))
        for _ in range(20):
            await asyncio.sleep(.001)
            if lobby.remote_gate.pending:break
        await self.decide(lobby.remote_gate,'approve',next(iter(lobby.remote_gate.pending)))
        await task
        welcome=next(json.loads(c.args[0]) for c in writer.write.call_args_list if json.loads(c.args[0])['type']=='welcome')
        self.assertTrue(welcome['verified']);self.assertTrue(welcome['remote_approved'])
        self.assertEqual(welcome['name'],'hnah')
        with self.assertRaises(AuthError):lobby.api_identity(dict(remote_approved=True,uid=234449,session_key='test-session'))

class PinnedTransport(unittest.TestCase):
    def test_remote_request_cannot_fall_back_to_plaintext(self):
        from campus_lan import auth_client
        with patch.object(auth_client,'load_trust',side_effect=FileNotFoundError),patch.object(auth_client.socket,'create_connection') as connect:
            with self.assertRaises(AuthError):auth_client.connect_socket('192.168.1.2',31417,remote_guest=True)
            connect.assert_not_called()

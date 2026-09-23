import asyncio
from collections import deque
import json
import os
from pathlib import Path
import queue
import secrets
import socket
import ssl
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from campus_lan import PROTOCOL
from campus_lan.auth import AuthHTTP, Broker, digest, config_dir, private_write, AuthError
from campus_lan import auth_client
from campus_lan.auth_server import setup
from campus_lan.server import Lobby
from campus_lan.client import Client


class TLSFlow(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        discovery = patch('campus_lan.auth_locator.request_json', return_value={})
        discovery.start()
        self.addCleanup(discovery.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.directory.name})
        self.env.start()
        credentials = Path(self.directory.name) / 'app.env'
        private_write(credentials, 'FT42_CLIENT_ID=test-id\nFT42_CLIENT_SECRET=test-secret\n'
                                  'FT42_REDIRECT_URI=http://localhost:31415/callback\n')
        self.trust = setup(credentials, '127.0.0.1')
        root = config_dir()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(root / 'auth-cert.pem', root / 'auth-key.pem')
        self.provider = Mock(client_id='test-id')
        self.provider.identify.return_value = dict(uid=77, login='real-login')
        self.broker = Broker(self.provider)
        self.lobby = Lobby(auth_broker=self.broker)
        self.server = await asyncio.start_server(self.lobby.handle, '127.0.0.1', 0,
                                                ssl=context, limit=65536)
        self.lobby.port = self.server.sockets[0].getsockname()[1]
        self.http = AuthHTTP(self.broker, '')
        self.web = await asyncio.start_server(self.http.handle, '127.0.0.1', 0, ssl=context)
        web_port = self.web.sockets[0].getsockname()[1]
        self.http.authority = f'127.0.0.1:{web_port}'
        self.trust.update(broker_url='https://' + self.http.authority, lobby_port=self.lobby.port)
        private_write(root / 'auth-trust.json', json.dumps(self.trust))
        self.guest = Lobby()
        self.local = await asyncio.start_server(self.guest.handle, '127.0.0.1', 0, limit=65536)
        self.local_port = self.local.sockets[0].getsockname()[1]
        self.ticker = asyncio.create_task(self.lobby.tick())
        self.writers = []

    async def asyncTearDown(self):
        for writer in self.writers:
            writer.close()
        for writer in self.writers:
            try:
                await writer.wait_closed()
            except OSError:
                pass
        self.ticker.cancel()
        await asyncio.gather(self.ticker, return_exceptions=True)
        for server in (self.server, self.web, self.local):
            server.close()
            await server.wait_closed()
        await asyncio.sleep(.05)
        self.env.stop()
        self.directory.cleanup()

    async def read(self, reader, predicate):
        async def receive():
            while True:
                raw = await reader.readline()
                if not raw:
                    raise AssertionError('Disconnected before expected message')
                message = json.loads(raw)
                if predicate(message):
                    return message
        return await asyncio.wait_for(receive(), 3)

    def make_session(self):
        token = secrets.token_hex(32)
        self.broker.sessions[digest(token)] = dict(uid=77, login='real-login', expires=time.time() + 1000)
        return token

    async def hello(self, token, role='lobby', **extra):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.lobby.port,
            ssl=auth_client.tls_context(self.trust), server_hostname='127.0.0.1')
        self.writers.append(writer)
        message = dict(type='hello', protocol=PROTOCOL, session=token, name='forged-name',
                       hostname='test', role=role, verified=True, **extra)
        writer.write((json.dumps(message) + '\n').encode())
        await writer.drain()
        return reader, writer

    async def test_real_tls_identity_override_duplicate_and_signout_all_windows(self):
        token = self.make_session()
        reader, writer = await self.hello(token)
        welcome = await self.read(reader, lambda m: m['type'] == 'welcome')
        self.assertEqual(welcome['name'], 'real-login')
        self.assertTrue(welcome['verified'])
        state = await self.read(reader, lambda m: m['type'] == 'state')
        self.assertEqual([p['name'] for p in state['players']], ['real-login'])
        self.assertNotIn(token, json.dumps(state))
        duplicate, _ = await self.hello(token)
        await self.read(duplicate, lambda m: m['type'] == 'error')
        game, game_writer = await self.hello(token, role='game')
        await self.read(game, lambda m: m['type'] == 'welcome')
        game_writer.write(b'{"type":"command","text":"/host hexwars"}\n')
        await game_writer.drain()
        await self.read(game, lambda m: m.get('game') == 'hexwars')
        writer.write(b'{"type":"command","text":"/signout"}\n')
        await writer.drain()
        await self.read(reader, lambda m: m['type'] == 'signed_out')
        await self.read(game, lambda m: m['type'] == 'signed_out')
        self.assertFalse(self.broker.active(digest(token)))

    async def test_missing_invalid_expired_tokens_and_guest_mesh_are_rejected(self):
        for token in (None, 'forged', secrets.token_hex(32)):
            reader, _ = await self.hello(token)
            await self.read(reader, lambda m: m['type'] == 'error')
        token = self.make_session()
        self.broker.sessions[digest(token)]['expires'] = time.time() - 1
        reader, _ = await self.hello(token)
        await self.read(reader, lambda m: m['type'] == 'error')
        reader, writer = await asyncio.open_connection('127.0.0.1', self.lobby.port,
            ssl=auth_client.tls_context(self.trust), server_hostname='127.0.0.1')
        self.writers.append(writer)
        writer.write((json.dumps(dict(type='mesh', protocol=PROTOCOL, port=1234,
            players=[dict(name='fake', verified=True)])) + '\n').encode())
        await writer.drain()
        await self.read(reader, lambda m: m['type'] == 'error')
        self.assertFalse(self.lobby.mesh.peers)

    async def test_idle_expiry_disconnects(self):
        token = self.make_session()
        reader, _ = await self.hello(token)
        await self.read(reader, lambda m: m['type'] == 'welcome')
        self.broker.sessions[digest(token)]['expires'] = time.time() - 1
        await self.read(reader, lambda m: m['type'] == 'signed_out')

    async def test_default_ca_rejects_unpinned_host(self):
        # Suppress the expected server-side TLS handshake error in the test loop.
        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda *args: None)
        try:
            with self.assertRaises(ssl.SSLCertVerificationError):
                await asyncio.open_connection('127.0.0.1', self.lobby.port,
                    ssl=ssl.create_default_context(), server_hostname='127.0.0.1')
        finally:
            await asyncio.sleep(.01)
            loop.set_exception_handler(previous)

    async def test_full_browser_callback_exchange_and_private_session(self):
        real_connect = socket.create_connection

        def route(address, *args, **kwargs):
            if address == ('127.0.0.1', 31415):
                address = ('127.0.0.1', self.local_port)
            return real_connect(address, *args, **kwargs)

        def browser(url):
            state = parse_qs(urlsplit(url).query)['state'][0]
            with real_connect(('127.0.0.1', self.local_port), timeout=3) as sock:
                sock.sendall((f'GET /callback?state={state}&code=one-time-code HTTP/1.1\r\n'
                    'Host: localhost:31415\r\n\r\n').encode())
                response = sock.recv(8192)
            self.assertIn(b'303 See Other', response)
            self.assertNotIn(b'one-time-code', response)
            return True

        with patch('socket.create_connection', side_effect=route):
            destination = await asyncio.to_thread(auth_client.sign_in, ('127.0.0.1', 31415), browser)
        self.assertEqual(destination, ('127.0.0.1', self.lobby.port))
        saved = auth_client.load_session(self.trust)
        self.assertEqual(saved['login'], 'real-login')
        self.assertEqual(auth_client.session_path().stat().st_mode & 0o777, 0o600)
        self.assertNotIn('access_token', auth_client.session_path().read_text())
        self.assertNotIn('test-secret', auth_client.session_path().read_text())
        self.assertEqual(self.provider.identify.call_args.args[0], 'one-time-code')

    async def test_browser_origin_http_endpoint_is_rejected(self):
        reader, writer = await asyncio.open_connection('127.0.0.1', self.web.sockets[0].getsockname()[1],
            ssl=auth_client.tls_context(self.trust), server_hostname='127.0.0.1')
        self.writers.append(writer)
        body = json.dumps(dict(proof=secrets.token_hex(32))).encode()
        writer.write((f'POST /begin HTTP/1.1\r\nHost: {self.http.authority}\r\n'
            'Origin: https://evil.example\r\nContent-Type: application/json\r\n'
            f'Content-Length: {len(body)}\r\n\r\n').encode() + body)
        await writer.drain()
        reply = await reader.read()
        self.assertIn(b'400 Bad Request', reply)
        self.assertFalse(self.broker.pending)

    async def test_client_never_downgrades_or_sends_token_after_tls_failure(self):
        token = self.make_session()
        auth_client.save_session(self.trust, dict(session=token, expires=time.time() + 1000))
        loop = asyncio.get_running_loop()
        previous = loop.get_exception_handler()
        loop.set_exception_handler(lambda *args: None)
        try:
            with patch('campus_lan.auth_client.tls_context', return_value=ssl.create_default_context()):
                with self.assertRaisesRegex(AuthError, 'certificate verification failed'):
                    await asyncio.to_thread(auth_client.connect_socket, '127.0.0.1', self.lobby.port)
            self.assertFalse(self.lobby.clients)
        finally:
            await asyncio.sleep(.01)
            loop.set_exception_handler(previous)

    def test_old_window_signout_cannot_delete_new_session(self):
        token = self.make_session()
        auth_client.save_session(self.trust, dict(session=token, expires=time.time() + 1000))
        auth_client.clear_session(secrets.token_hex(32))
        self.assertEqual(auth_client.load_session(self.trust)['session'], token)
        auth_client.clear_session(token)
        self.assertIsNone(auth_client.load_session(self.trust))

    async def test_seat_move_preserves_pin_and_checks_identity_for_https_and_lobby(self):
        root = config_dir()
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(root / 'auth-cert.pem', root / 'auth-key.pem')
        new_ip = '127.0.0.2'
        broker_port = self.web.sockets[0].getsockname()[1]
        moved_http = AuthHTTP(self.broker, f'{new_ip}:{broker_port}')
        new_lobby = await asyncio.start_server(self.lobby.handle, new_ip, self.lobby.port, ssl=context)
        new_web = await asyncio.start_server(moved_http.handle, new_ip, broker_port, ssl=context)
        try:
            old_fingerprint = auth_client.fingerprint(self.trust)
            await asyncio.to_thread(auth_client.change_host, new_ip)
            moved = auth_client.load_trust()
            self.assertEqual(moved['lobby_host'], new_ip)
            self.assertEqual(moved['server_name'], '127.0.0.1')
            self.assertEqual(auth_client.fingerprint(moved), old_fingerprint)
            flow = await asyncio.to_thread(auth_client.post, moved, '/begin', dict(proof=secrets.token_hex(32)))
            self.assertIn('authorization_url', flow)
            token = self.make_session()
            auth_client.save_session(moved, dict(session=token, expires=time.time() + 1000))
            sock, session = await asyncio.to_thread(auth_client.connect_socket, new_ip, self.lobby.port)
            sock.close()
            self.assertEqual(session['session'], token)
        finally:
            new_lobby.close()
            new_web.close()
            await new_lobby.wait_closed()
            await new_web.wait_closed()


class BadgeTests(unittest.TestCase):
    def test_untrusted_guest_node_cannot_set_verified_badges(self):
        client = Client.__new__(Client)
        client.secure = False
        client.inbox = queue.Queue()
        client.lines = deque()
        client.state = {}
        client.inbox.put(dict(type='state', players=[dict(name='fake', verified=True)], rooms=[]))
        client.consume()
        self.assertFalse(client.state['players'][0]['verified'])

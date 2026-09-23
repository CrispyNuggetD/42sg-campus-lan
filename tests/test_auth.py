import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import tempfile
import time
import unittest
import ssl
import urllib.error
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from campus_lan.auth import (AuthError, AuthUnavailable, Broker, CallbackRelay, Provider, REDIRECT_URI,
    TOKEN_URL, ME_URL, REVOKE_URL, digest, private_read, private_write, request_json)
from campus_lan.auth_client import save_session, load_session, clear_session


class BrokerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.now = 10000
        self.provider = Mock(client_id='public-app-id')
        self.provider.identify.return_value = dict(uid=42, login='student')
        self.broker = Broker(self.provider, clock=lambda: self.now)

    def begin(self):
        proof = secrets.token_hex(32)
        flow = self.broker.begin(proof, '127.0.0.1')
        return flow, proof

    def test_authorization_state_pkce_minimum_scope_no_secret(self):
        flow, proof = self.begin()
        params = parse_qs(urlsplit(flow['authorization_url']).query)
        self.assertEqual(params['redirect_uri'], [REDIRECT_URI])
        self.assertEqual(params['scope'], ['public'])
        self.assertEqual(params['code_challenge_method'], ['S256'])
        self.assertNotIn(proof, flow['authorization_url'])
        self.assertNotIn('client_secret', params)
        self.assertEqual(len(flow['state']), 64)

    async def test_bad_state_bad_proof_expiry_replay_and_logout(self):
        flow, proof = self.begin()
        for state, candidate in ((secrets.token_hex(32), proof), (flow['state'], secrets.token_hex(32))):
            with self.assertRaises(AuthError):
                await self.broker.exchange(state, candidate, 'authorization-code')
        self.provider.identify.assert_not_called()
        session = await self.broker.exchange(flow['state'], proof, 'authorization-code')
        self.assertEqual(session['login'], 'student')
        self.assertNotIn(session['session'], self.broker.sessions)
        with self.assertRaises(AuthError):
            await self.broker.exchange(flow['state'], proof, 'authorization-code')
        identity = self.broker.authenticate(session['session'])
        self.broker.logout(identity['session_key'])
        with self.assertRaises(AuthError):
            self.broker.authenticate(session['session'])
        flow, proof = self.begin()
        self.now += 301
        with self.assertRaises(AuthError):
            await self.broker.exchange(flow['state'], proof, 'authorization-code')

    async def test_expired_session_and_concurrent_exchange(self):
        flow, proof = self.begin()
        results = await asyncio.gather(self.broker.exchange(flow['state'], proof, 'code'),
            self.broker.exchange(flow['state'], proof, 'code'), return_exceptions=True)
        self.assertEqual(sum(isinstance(r, AuthError) for r in results), 1)
        self.assertEqual(self.provider.identify.call_count, 1)
        session = next(r for r in results if isinstance(r, dict))
        self.now += 3601
        with self.assertRaises(AuthError):
            self.broker.authenticate(session['session'])

    async def test_provider_errors_are_redacted_and_grant_consumed(self):
        self.provider.identify.side_effect = RuntimeError('SECRET code=private-code token=private-token')
        flow, proof = self.begin()
        with self.assertRaises(AuthError) as caught:
            await self.broker.exchange(flow['state'], proof, 'private-code')
        self.assertNotIn('SECRET', str(caught.exception))
        self.assertNotIn('private-', str(caught.exception))
        self.assertFalse(self.broker.sessions)
        self.assertNotIn(flow['state'], self.broker.pending)

    def test_bounded_rate_limit(self):
        for _ in range(5):
            self.begin()
        with self.assertRaises(AuthError):
            self.begin()
        self.now += 61
        self.begin()


class ProviderTests(unittest.TestCase):
    def test_only_me_identity_is_retained_and_tokens_revoked(self):
        provider = Provider('test-id', 'test-secret')
        access = 'test-access-token-12345'
        provider.request = Mock(side_effect=[dict(access_token=access, token_type='bearer',
            refresh_token='do-not-store'), dict(id=99, login='real-student', email='private',
            phone='private', location='private'), {}])
        result = provider.identify('one-time-code', 'verifier')
        self.assertEqual(result, dict(uid=99, login='real-student'))
        calls = provider.request.call_args_list
        self.assertEqual([c.args[0] for c in calls], [TOKEN_URL, ME_URL, REVOKE_URL])
        self.assertEqual(calls[1].kwargs['headers'], {'Authorization': 'Bearer ' + access})
        form = parse_qs(calls[0].args[1].decode())
        self.assertEqual(form['code_verifier'], ['verifier'])
        self.assertEqual(form['redirect_uri'], [REDIRECT_URI])
        self.assertNotIn('access_token', provider.__dict__)

    def test_failed_me_still_revokes_and_invalid_identity_rejected(self):
        provider = Provider('id', 'secret')
        provider.request = Mock(side_effect=[dict(access_token='test-access-token-12345', token_type='bearer'),
            dict(id=True, login='forged'), {}])
        with self.assertRaises(AuthError):
            provider.identify('code', 'verifier')
        self.assertEqual(provider.request.call_args_list[-1].args[0], REVOKE_URL)


class PrivateFiles(unittest.TestCase):
    def test_permissions_ownership_symlinks_and_atomic_private_write(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'session.json'
            private_write(path, 'secret')
            self.assertEqual(private_read(path), b'secret')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            path.chmod(0o644)
            with self.assertRaises(AuthError):
                private_read(path)
            path.chmod(0o600)
            link = root / 'link'
            link.symlink_to(path)
            with self.assertRaises(OSError):
                private_read(link)
            root.chmod(0o755)
            with self.assertRaises(AuthError):
                private_write(path, 'new-secret')
            self.assertEqual(path.read_text(), 'secret')


class TransportErrors(unittest.TestCase):
    def test_offline_host_is_distinct_from_rejection_and_bad_certificate(self):
        failures = [
            (urllib.error.URLError(ConnectionRefusedError()), AuthUnavailable, 'offline'),
            (urllib.error.HTTPError('https://example.invalid/private-code', 400, 'private-token', {}, None),
             AuthError, 'rejected'),
            (urllib.error.URLError(ssl.SSLCertVerificationError(1, 'private-detail')),
             AuthError, 'certificate verification failed'),
        ]
        for failure, expected, message in failures:
            with self.subTest(message=message), patch('campus_lan.auth.urllib.request.build_opener') as build:
                build.return_value.open.side_effect = failure
                with self.assertRaises(expected) as caught:
                    request_json('https://example.invalid/auth')
                self.assertIn(message, str(caught.exception))
                self.assertNotIn('private-', str(caught.exception))


class CallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_state_duplicate_denial_and_one_shot_callback(self):
        relay = CallbackRelay()
        writer = Mock()
        writer.drain = unittest.mock.AsyncMock()
        future = asyncio.get_running_loop().create_future()
        state = secrets.token_hex(32)
        relay.waiters[state] = future

        async def callback(query, host='localhost:31415'):
            reader = asyncio.StreamReader()
            reader.feed_data(f'Host: {host}\r\n\r\n'.encode())
            reader.feed_eof()
            await relay.handle(reader, writer, f'GET /callback?{query} HTTP/1.1\r\n'.encode())

        await callback('state=wrong&code=secret')
        self.assertFalse(future.done())
        await callback(f'state={state}&state={state}&code=secret')
        self.assertFalse(future.done())
        await callback(f'state={state}&code=secret', 'evil.example')
        self.assertFalse(future.done())
        await callback(f'state={state}&code=secret')
        self.assertEqual(future.result(), dict(code='secret'))
        self.assertIn(b'303 See Other', writer.write.call_args.args[0])
        self.assertNotIn(b'secret', writer.write.call_args.args[0])
        await callback(f'state={state}&code=another')
        self.assertIn(b'400 Bad Request', writer.write.call_args.args[0])

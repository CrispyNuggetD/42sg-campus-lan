"""Confidential 42 OAuth broker. Provider credentials never reach LAN clients."""
import asyncio
import base64
from collections import deque
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

AUTHORIZE_URL = 'https://api.intra.42.fr/oauth/authorize'
TOKEN_URL = 'https://api.intra.42.fr/oauth/token'
ME_URL = 'https://api.intra.42.fr/v2/me'
REVOKE_URL = 'https://api.intra.42.fr/oauth/revoke'
REDIRECT_URI = 'http://localhost:31415/callback'
FLOW_TTL = 300
SESSION_TTL = 3600


class AuthError(ValueError):
    """Only fixed, non-sensitive messages cross this exception boundary."""


class AuthUnavailable(AuthError):
    """Transport failure, distinct from rejected credentials or consent."""


def config_dir():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / '42sg-campus-lan'


def private_read(path):
    """No symlink following; never accept another user's/group-readable secret."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as source:
        info = os.fstat(source.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_size > 65536):
            raise AuthError('Private auth file must be owned by you, regular, and mode 600.')
        return source.read(65537)


def private_write(path, data):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise AuthError('Auth directory must be owned by you and mode 700.')
    temporary = path.parent / ('.write-' + secrets.token_hex(16))
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'wb') as output:
            output.write(data if isinstance(data, bytes) else data.encode())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def nonce(value):
    return isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value) is not None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AuthError('Authentication endpoint redirected unexpectedly.')


def request_json(url, data=None, headers=None, context=None, empty_ok=False):
    """TLS verification stays on. Refuse redirects rather than forward secrets."""
    request = urllib.request.Request(url, data=data,
        headers={'User-Agent': 'LAN42/0.6.0', 'Accept': 'application/json', **(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}),
        urllib.request.HTTPSHandler(context=context or ssl.create_default_context()), NoRedirect())
    try:
        with opener.open(request, timeout=10) as response:
            raw = response.read(131073)
            if len(raw) > 131072:
                raise AuthError('Authentication response too large.')
            if empty_ok and not raw.strip():
                return {}
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise AuthError('Invalid authentication response.')
            return result
    except urllib.error.HTTPError:
        raise AuthError('Authentication request was rejected. Start sign-in again or check the service configuration.') from None
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, ssl.SSLCertVerificationError):
            raise AuthError('Authentication certificate verification failed. Connection refused.') from None
        raise AuthUnavailable('Authentication service is offline or unreachable.') from None
    except (OSError, ValueError):
        raise AuthError('Authentication request failed. Check the service or try again.') from None


class Provider:
    def __init__(self, client_id, client_secret):
        self.client_id, self.client_secret = client_id, client_secret
        self.last_request = 0

    def request(self, url, data=None, headers=None):
        time.sleep(max(0, .6 - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        return request_json(url, data, headers, empty_ok=url == REVOKE_URL)

    def form(self, values):
        return urllib.parse.urlencode(dict(client_id=self.client_id,
            client_secret=self.client_secret, **values)).encode()

    def identify(self, code, verifier):
        access_token = None
        try:
            token = self.request(TOKEN_URL, self.form(dict(grant_type='authorization_code',
                code=code, redirect_uri=REDIRECT_URI, code_verifier=verifier)))
            access_token = token.get('access_token')
            if not isinstance(access_token, str) or not 16 <= len(access_token) <= 4096:
                raise AuthError('42 did not return a usable access token.')
            if str(token.get('token_type', '')).lower() != 'bearer':
                raise AuthError('42 returned an unsupported token type.')
            # Never persist refresh_token, profile, email, phone, or raw responses.
            profile = self.request(ME_URL, headers={'Authorization': 'Bearer ' + access_token})
            uid, login = profile.get('id'), profile.get('login')
            if type(uid) is not int or uid <= 0 or not isinstance(login, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,24}', login):
                raise AuthError('42 returned an invalid account identity.')
            return dict(uid=uid, login=login)
        finally:
            if access_token:
                # Best effort: tokens are never retained, even if revocation is down.
                try:
                    self.request(REVOKE_URL, self.form(dict(token=access_token)))
                except AuthError:
                    pass


class Broker:
    def __init__(self, provider, clock=time.time):
        self.provider, self.clock = provider, clock
        self.pending, self.sessions, self.rates = {}, {}, {}
        self.exchanges = deque()
        self.busy = False

    def prune(self):
        now = self.clock()
        self.pending = {k: v for k, v in self.pending.items() if v['expires'] > now}
        self.sessions = {k: v for k, v in self.sessions.items() if v['expires'] > now}
        self.rates = {k: v for k, v in self.rates.items() if v[0] > now - 60}
        while self.exchanges and self.exchanges[0] < now - 3600:
            self.exchanges.popleft()

    def begin(self, proof, source):
        self.prune()
        if not nonce(proof):
            raise AuthError('Invalid sign-in request.')
        now = self.clock()
        started, count = self.rates.get(source, (now, 0))
        if count >= 5 or len(self.pending) >= 64 or len(self.sessions) >= 256 or len(self.rates) >= 512:
            raise AuthError('Sign-in rate limit reached. Try again later.')
        self.rates[source] = (started, count + 1)
        state, verifier = secrets.token_hex(32), secrets.token_urlsafe(48)
        self.pending[state] = dict(proof=digest(proof), verifier=verifier, expires=now + FLOW_TTL)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b'=').decode()
        url = AUTHORIZE_URL + '?' + urllib.parse.urlencode(dict(client_id=self.provider.client_id,
            redirect_uri=REDIRECT_URI, response_type='code', scope='public', state=state,
            code_challenge=challenge, code_challenge_method='S256'))
        return dict(state=state, authorization_url=url, expires=now + FLOW_TTL)

    async def exchange(self, state, proof, code):
        self.prune()
        if not nonce(state) or not nonce(proof) or not isinstance(code, str) or not 1 <= len(code) <= 2048:
            raise AuthError('Invalid or expired sign-in request.')
        flow = self.pending.get(state)
        if not flow or not secrets.compare_digest(flow['proof'], digest(proof)):
            raise AuthError('Invalid or expired sign-in request.')
        if self.busy or len(self.exchanges) >= 100 or (self.exchanges and self.clock() - self.exchanges[-1] < 3):
            raise AuthError('Authentication service is busy. Start sign-in again shortly.')
        # Consume before the first await: concurrent callbacks cannot redeem twice.
        del self.pending[state]
        self.busy = True
        self.exchanges.append(self.clock())
        try:
            identity = await asyncio.to_thread(self.provider.identify, code, flow['verifier'])
        except Exception:
            raise AuthError('42 sign-in failed. Start again; the app secret may need renewal.') from None
        finally:
            self.busy = False
        session = secrets.token_hex(32)
        record = dict(uid=identity['uid'], login=identity['login'], expires=self.clock() + SESSION_TTL)
        self.sessions[digest(session)] = record
        return dict(session=session, **record)

    def authenticate(self, session):
        if not nonce(session):
            raise AuthError('Sign in with 42 to enter this lobby.')
        record = self.sessions.get(digest(session))
        if not record or record['expires'] <= self.clock():
            raise AuthError('Sign-in expired. Use /signin again.')
        return dict(record, session_key=digest(session))

    def active(self, key):
        return key in self.sessions and self.sessions[key]['expires'] > self.clock()

    def logout(self, key):
        self.sessions.pop(key, None)


async def http_request(reader, first=None):
    line = first or await asyncio.wait_for(reader.readline(), 5)
    if len(line) > 8192:
        raise AuthError('HTTP request too large.')
    try:
        method, target, version = line.decode('ascii').strip().split(' ')
    except ValueError:
        raise AuthError('Invalid HTTP request.') from None
    if version != 'HTTP/1.1' or len(target) > 4096:
        raise AuthError('Invalid HTTP request.')
    headers, size = {}, len(line)
    while True:
        raw = await asyncio.wait_for(reader.readline(), 5)
        size += len(raw)
        if size > 12288 or not raw:
            raise AuthError('Invalid HTTP headers.')
        if raw == b'\r\n':
            break
        key, separator, value = raw.decode('ascii').partition(':')
        key = key.lower()
        if not separator or key in headers:
            raise AuthError('Invalid HTTP headers.')
        headers[key] = value.strip()
    if 'transfer-encoding' in headers:
        raise AuthError('Transfer encoding is not supported.')
    return method, target, headers


async def http_response(writer, status, body, extra=''):
    body = body.encode()
    writer.write((f'HTTP/1.1 {status}\r\nContent-Type: application/json; charset=utf-8\r\n'
        f'Content-Length: {len(body)}\r\nConnection: close\r\nCache-Control: no-store\r\n'
        'Referrer-Policy: no-referrer\r\nX-Content-Type-Options: nosniff\r\n'
        "Content-Security-Policy: default-src 'none'; frame-ancestors 'none'\r\n" + extra + '\r\n').encode() + body)
    await asyncio.wait_for(writer.drain(), 3)


class CallbackRelay:
    """Loopback-only, one-shot callback forwarding to the initiating client."""
    def __init__(self):
        self.waiters = {}

    async def wait(self, state, reader, writer):
        if not nonce(state) or state in self.waiters or len(self.waiters) >= 8:
            raise AuthError('Invalid or duplicate callback registration.')
        future = asyncio.get_running_loop().create_future()
        self.waiters[state] = future
        disconnected = asyncio.create_task(reader.read(1))
        try:
            writer.write(b'{"type":"callback_ready"}\n')
            await writer.drain()
            done, _ = await asyncio.wait([future, disconnected], timeout=FLOW_TTL,
                                         return_when=asyncio.FIRST_COMPLETED)
            if future in done:
                writer.write((json.dumps(future.result()) + '\n').encode())
                await writer.drain()
        finally:
            self.waiters.pop(state, None)
            disconnected.cancel()
            await asyncio.gather(disconnected, return_exceptions=True)

    async def handle(self, reader, writer, first):
        try:
            method, target, headers = await asyncio.wait_for(http_request(reader, first), 10)
            if method != 'GET' or headers.get('host') != 'localhost:31415':
                raise AuthError('Invalid callback origin.')
            parsed = urllib.parse.urlsplit(target)
            if parsed.scheme or parsed.netloc or parsed.fragment:
                raise AuthError('Invalid callback target.')
            if parsed.path == '/signin-complete' and not parsed.query:
                await http_response(writer, '200 OK', '{"message":"Return to LAN42 to check sign-in status."}')
                return
            if parsed.path != '/callback':
                raise AuthError('Unknown callback path.')
            params = urllib.parse.parse_qs(parsed.query, strict_parsing=True, max_num_fields=5)
            if any(len(v) != 1 for v in params.values()):
                raise AuthError('Duplicate callback parameters.')
            state = params.get('state', [''])[0]
            future = self.waiters.get(state)
            if not nonce(state) or not future or future.done():
                raise AuthError('Unknown or expired sign-in.')
            code = params.get('code', [''])[0]
            if 'error' in params:
                future.set_result(dict(error='Sign-in was declined or cancelled.'))
            elif 0 < len(code) <= 2048:
                future.set_result(dict(code=code))
            else:
                raise AuthError('Missing authorization code.')
            await http_response(writer, '303 See Other', '{}', 'Location: /signin-complete\r\n')
        except (ValueError, OSError, asyncio.TimeoutError):
            await http_response(writer, '400 Bad Request', '{"error":"Invalid or expired sign-in callback."}')


class AuthHTTP:
    def __init__(self, broker, authority):
        self.broker, self.authority = broker, authority
        self.connections = 0

    async def handle(self, reader, writer):
        self.connections += 1
        try:
            if self.connections > 32:
                raise AuthError('Authentication service busy.')
            method, target, headers = await asyncio.wait_for(http_request(reader), 10)
            if method != 'POST' or headers.get('host') != self.authority or 'origin' in headers:
                raise AuthError('Native client requests only.')
            if headers.get('content-type') != 'application/json':
                raise AuthError('Expected JSON.')
            size = int(headers.get('content-length', '0'))
            if not 0 < size <= 4096:
                raise AuthError('Invalid request size.')
            data = json.loads(await asyncio.wait_for(reader.readexactly(size), 5))
            if not isinstance(data, dict):
                raise AuthError('Expected an object.')
            if target == '/begin':
                result = self.broker.begin(data.get('proof'), writer.get_extra_info('peername')[0])
            elif target == '/exchange':
                result = await self.broker.exchange(data.get('state'), data.get('proof'), data.get('code'))
            else:
                raise AuthError('Unknown authentication endpoint.')
            await http_response(writer, '200 OK', json.dumps(result))
        except (ValueError, OSError, asyncio.TimeoutError, asyncio.IncompleteReadError):
            # Never log requests, query strings, authorization codes or exception reprs.
            try:
                await http_response(writer, '400 Bad Request', '{"error":"Sign-in failed or expired. Try again shortly."}')
            except (OSError, asyncio.TimeoutError):
                pass
        finally:
            self.connections -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

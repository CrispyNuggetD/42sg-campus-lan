"""Pinned TLS, loopback browser handoff, and private LAN42 sessions (not 42 tokens)."""
import hashlib
import http.client
import ipaddress
import json
import os
import secrets
import socket
import ssl
import time
import urllib.parse
import webbrowser
from . import PROTOCOL
from .auth import (AuthError, AuthUnavailable, AUTHORIZE_URL, REDIRECT_URI, FLOW_TTL, config_dir,
                   private_read, private_write, request_json, nonce)


def load_trust():
    path = config_dir() / 'auth-trust.json'
    try:
        return validate_trust(json.loads(private_read(path)))
    except FileNotFoundError:
        raise AuthError('Sign-in host is not configured. Import the host owner\'s public trust file; see docs/sign-in.md.') from None


def validate_trust(data):
    required = {'broker_url', 'lobby_host', 'lobby_port', 'certificate'}
    if not isinstance(data, dict) or not required <= set(data) or set(data) - required - {'server_name'}:
        raise AuthError('Invalid auth trust file.')
    url = urllib.parse.urlsplit(data['broker_url'])
    host, port = data['lobby_host'], data['lobby_port']
    if (url.scheme != 'https' or url.hostname != host or url.username or url.password
            or url.path or url.query or url.fragment or not url.port
            or not isinstance(host, str) or type(port) is not int or not 1 <= port <= 65535):
        raise AuthError('Auth service must use a fixed HTTPS endpoint.')
    if not isinstance(data['certificate'], str) or len(data['certificate']) > 16384:
        raise AuthError('Invalid auth certificate.')
    if 'server_name' in data and (not isinstance(data['server_name'], str)
                                 or not data['server_name'] or len(data['server_name']) > 253):
        raise AuthError('Invalid TLS identity.')
    tls_context(data)
    return data


def tls_context(trust):
    # Only this owner's certificate is trusted, not certificates from the LAN.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_verify_locations(cadata=trust['certificate'])
    return context


def fingerprint(trust):
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(trust['certificate'])).hexdigest()


def endpoint(trust):
    return trust['lobby_host'], trust['lobby_port']


def server_name(trust):
    # The certificate's identity is stable even when its TCP address changes.
    return trust.get('server_name', trust['lobby_host'])


def relocated(trust, host):
    ip = ipaddress.ip_address(host)
    if ip.version != 4 or not (ip.is_private or ip.is_loopback) or ip.is_unspecified or ip.is_multicast:
        raise AuthError('Choose a private LAN IPv4 address or campus seat.')
    broker_port = urllib.parse.urlsplit(trust['broker_url']).port
    return validate_trust(dict(trust, server_name=server_name(trust), lobby_host=str(ip),
                               broker_url=f'https://{ip}:{broker_port}'))


def change_host(seat):
    from .network import address
    trust = relocated(load_trust(), address(seat))
    # Prove the endpoint has the already trusted key before saving it. No tokens.
    with socket.create_connection(endpoint(trust), timeout=5) as raw:
        with tls_context(trust).wrap_socket(raw, server_hostname=server_name(trust)) as sock:
            sock.sendall((json.dumps(dict(type='ping', protocol=PROTOCOL)) + '\n').encode())
            with sock.makefile('rb') as stream:
                message = json.loads(stream.readline(2048))
            if message.get('type') != 'pong' or message.get('protocol') != PROTOCOL:
                raise AuthError('This seat did not confirm the trusted LAN42 service.')
    private_write(config_dir() / 'auth-trust.json', json.dumps(trust))
    clear_session()
    return trust['lobby_host']


def matches(trust, host, port):
    return port == trust['lobby_port'] and host == trust['lobby_host']


def session_path():
    return config_dir() / 'auth-session.json'


def save_session(trust, session):
    if not nonce(session.get('session')) or type(session.get('expires')) not in (int, float):
        raise AuthError('Invalid LAN42 session.')
    private_write(session_path(), json.dumps(dict(session, trust=fingerprint(trust))))


def load_session(trust):
    try:
        result = json.loads(private_read(session_path()))
        if (not isinstance(result, dict) or result.get('trust') != fingerprint(trust)
                or not nonce(result.get('session')) or type(result.get('expires')) not in (int, float)
                or result['expires'] <= time.time()):
            return None
        return result
    except FileNotFoundError:
        return None


def clear_session(expected=None):
    # An old game window must not delete a newly authenticated session.
    if expected is not None:
        try:
            current = json.loads(private_read(session_path()))
        except FileNotFoundError:
            return
        if current.get('session') != expected:
            return
    session_path().unlink(missing_ok=True)


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, trust):
        url = urllib.parse.urlsplit(trust['broker_url'])
        super().__init__(url.hostname, url.port, timeout=10, context=tls_context(trust))
        self.tls_name = server_name(trust)

    def connect(self):
        # Connect to the current seat but verify the original pinned identity.
        # Host headers still name the actual endpoint; no proxy or redirects.
        http.client.HTTPConnection.connect(self)
        self.sock = self._context.wrap_socket(self.sock, server_hostname=self.tls_name)


def post(trust, route, payload):
    connection = PinnedHTTPSConnection(trust)
    try:
        connection.request('POST', route, body=json.dumps(payload).encode(),
            headers={'Content-Type': 'application/json', 'User-Agent': 'LAN42/0.6.0'})
        response = connection.getresponse()
        if response.status != 200:
            raise AuthError('Sign-in was rejected or expired. Start again shortly.')
        raw = response.read(16385)
        if len(raw) > 16384:
            raise AuthError('Sign-in response too large.')
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise AuthError('Invalid sign-in response.')
        return result
    except ssl.SSLCertVerificationError:
        raise AuthError('Authentication certificate verification failed. Connection refused.') from None
    except OSError:
        raise AuthError('Sign-in host is offline or unreachable. Ask its owner to start the sign-in service.') from None
    finally:
        connection.close()


def sign_in(home, open_browser=webbrowser.open):
    if home[0] not in ('127.0.0.1', 'localhost') or home[1] != 31415:
        raise AuthError('42 sign-in needs your local LAN42 node on port 31415 for its registered callback.')
    from .auth_locator import refresh
    refresh()
    trust, proof = load_trust(), secrets.token_hex(32)
    flow = post(trust, '/begin', dict(proof=proof))
    state, url = flow.get('state'), flow.get('authorization_url')
    if not nonce(state) or not isinstance(url, str):
        raise AuthError('Invalid sign-in response.')
    parsed = urllib.parse.urlsplit(url)
    params = urllib.parse.parse_qs(parsed.query)
    if (parsed.scheme + '://' + parsed.netloc + parsed.path != AUTHORIZE_URL
            or parsed.fragment or params.get('state') != [state]
            or params.get('redirect_uri') != [REDIRECT_URI]
            or params.get('response_type') != ['code'] or params.get('scope') != ['public']
            or params.get('code_challenge_method') != ['S256']):
        raise AuthError('Unexpected authorization URL; refusing to open it.')
    with socket.create_connection(home, timeout=5) as sock:
        sock.settimeout(FLOW_TTL + 5)
        sock.sendall((json.dumps(dict(type='oauth_wait', protocol=PROTOCOL, state=state)) + '\n').encode())
        with sock.makefile('rb') as stream:
            ready = json.loads(stream.readline(2048))
            if ready.get('type') != 'callback_ready':
                raise AuthError('Local callback unavailable. Restart your updated LAN42 node.')
            if not open_browser(url):
                raise AuthError('Could not open the browser. Configure your default browser and try /signin again.')
            raw = stream.readline(4097)
            if len(raw) > 4096 or not raw:
                raise AuthError('Sign-in timed out. Use /signin again.')
            callback = json.loads(raw)
    if callback.get('error') or not isinstance(callback.get('code'), str):
        raise AuthError('Sign-in was declined or cancelled.')
    session = post(trust, '/exchange', dict(state=state, proof=proof, code=callback['code']))
    save_session(trust, session)
    return endpoint(trust)


def connect_socket(host, port):
    """Returns (socket, LAN42 session or None). Never downgrades a trusted endpoint."""
    try:
        trust = load_trust()
    except FileNotFoundError:
        trust = None
    except AuthError:
        if (config_dir() / 'auth-trust.json').exists():
            raise
        trust = None
    if trust and matches(trust, host, port):
        session = load_session(trust)
        if not session:
            raise AuthError('Use /signin from your local HQ first.')
        raw = socket.create_connection((host, port), timeout=5)
        try:
            secure = tls_context(trust).wrap_socket(raw, server_hostname=server_name(trust))
        except Exception:
            raw.close()
            raise AuthError('Secure lobby certificate verification failed; connection refused.') from None
        return secure, session
    return socket.create_connection((host, port), timeout=5), None

"""Owner CLI: import the existing app, export PUBLIC trust, serve TLS auth/lobby."""
import argparse
import asyncio
import datetime
import ipaddress
import json
from pathlib import Path
import re
import shlex
import ssl
import sys
from .auth import AuthError, AuthHTTP, Broker, Provider, REDIRECT_URI, config_dir, private_read, private_write
from .auth_client import fingerprint, validate_trust


def setup(credentials, host, broker_port=31416, lobby_port=31417):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
    root = config_dir()
    if (root / 'auth-server.json').exists():
        raise AuthError('Auth host already configured; use renew-credentials to update its secret.')
    if not re.fullmatch(r'[a-zA-Z0-9.-]{1,253}', host) or not 1 <= broker_port <= 65535 or not 1 <= lobby_port <= 65535 or broker_port == lobby_port:
        raise AuthError('Invalid auth host or ports.')
    app = read_credentials(credentials)
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'LAN42 authentication host')])
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        san = x509.IPAddress(ipaddress.ip_address(host))
    except ValueError:
        san = x509.DNSName(host)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
        .public_key(key.public_key()).serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(days=180))
        .add_extension(x509.SubjectAlternativeName([san]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .sign(key, hashes.SHA256()))
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode()
    private_write(root / 'auth-key.pem', key.private_bytes(serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    private_write(root / 'auth-cert.pem', cert_pem)
    private_write(root / 'auth-server.json', json.dumps(dict(app, host=host,
        broker_port=broker_port, lobby_port=lobby_port)))
    trust = dict(broker_url=f'https://{host}:{broker_port}', lobby_host=host,
                 lobby_port=lobby_port, certificate=cert_pem)
    private_write(root / 'auth-trust.json', json.dumps(trust, indent=2))
    return trust


def read_credentials(path):
    values = {}
    for line in private_read(path).decode().splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, separator, raw = line.partition('=')
        words = shlex.split(raw, comments=True)
        if not separator or len(words) != 1 or key.strip() in values:
            raise AuthError('Invalid credential file format.')
        values[key.strip()] = words[0]
    client_id, secret = values.get('FT42_CLIENT_ID'), values.get('FT42_CLIENT_SECRET')
    if not client_id or not secret or values.get('FT42_REDIRECT_URI') != REDIRECT_URI:
        raise AuthError('Credentials need FT42_CLIENT_ID, FT42_CLIENT_SECRET and http://localhost:31415/callback.')
    return dict(client_id=client_id, client_secret=secret)


async def wait_for_host_move(settings):
    generation = settings.get('host_generation')
    while True:
        await asyncio.sleep(1)
        try:
            current = json.loads(private_read(config_dir() / 'auth-server.json'))
        except (OSError, ValueError):
            return
        if current.get('host_generation') != generation or current.get('host') != settings['host']:
            return


async def serve_auth(bind='0.0.0.0', current_seat=False):
    from .server import Lobby
    root = config_dir()
    settings = json.loads(private_read(root / 'auth-server.json'))
    if current_seat:
        from .auth_daily import current_seat as detect_seat
        bind = detect_seat()
        if bind != settings['host']:
            print('Sign-in host belongs to a different seat; this service will stay stopped.', flush=True)
            return
    private_read(root / 'auth-key.pem')  # ownership/mode check before SSL loads it
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(root / 'auth-cert.pem', root / 'auth-key.pem')
    broker = Broker(Provider(settings['client_id'], settings['client_secret']))
    lobby = Lobby(auth_broker=broker)
    lobby.port = settings['lobby_port']
    lobby.mesh.host = settings['host']
    http = AuthHTTP(broker, f"{settings['host']}:{settings['broker_port']}")
    web = await asyncio.start_server(http.handle, bind, settings['broker_port'], ssl=context,
                                     ssl_handshake_timeout=5, limit=16384)
    try:
        server = await asyncio.start_server(lobby.handle, bind, settings['lobby_port'], ssl=context,
                                            ssl_handshake_timeout=5, limit=65536)
    except Exception:
        web.close()
        await web.wait_closed()
        raise
    ticker = asyncio.create_task(lobby.tick())
    print(f"LAN42 secure sign-in host ready: HTTPS {settings['broker_port']}, TLS lobby {settings['lobby_port']}.", flush=True)
    try:
        async with web, server:
            await wait_for_host_move(settings)
    finally:
        ticker.cancel()
        for task in list(lobby.hex_tasks):
            task.cancel()
        await asyncio.gather(ticker, *list(lobby.hex_tasks), return_exceptions=True)
        for client in list(lobby.clients.values()):
            client['writer'].close()
        broker.sessions.clear()


def main():
    parser = argparse.ArgumentParser(description='LAN42 confidential sign-in host and public trust setup')
    sub = parser.add_subparsers(dest='command', required=True)
    create = sub.add_parser('setup')
    create.add_argument('--credentials', required=True, type=Path)
    create.add_argument('--host', required=True, help='Stable LAN IP or hostname reachable by students')
    create.add_argument('--broker-port', type=int, default=31416)
    create.add_argument('--lobby-port', type=int, default=31417)
    run = sub.add_parser('serve')
    run.add_argument('--bind', default='0.0.0.0')
    run.add_argument('--current-seat', action='store_true', help='Bind only the seat prepared by dailylogin')
    export = sub.add_parser('export-trust')
    export.add_argument('output', type=Path)
    install = sub.add_parser('trust')
    install.add_argument('file', type=Path)
    install.add_argument('--fingerprint', required=True, help='SHA256 provided separately by the host owner')
    renew = sub.add_parser('renew-credentials')
    renew.add_argument('--credentials', required=True, type=Path)
    args = parser.parse_args()
    root = config_dir()
    if args.command == 'setup':
        trust = setup(args.credentials, args.host, args.broker_port, args.lobby_port)
        print('Imported existing app into private configuration outside the repository.')
        print('Public trust certificate SHA256:', fingerprint(trust))
    elif args.command == 'serve':
        asyncio.run(serve_auth(args.bind, args.current_seat))
    elif args.command == 'export-trust':
        trust = validate_trust(json.loads(private_read(root / 'auth-trust.json')))
        # This allowlisted file contains ONLY public endpoint/certificate information.
        with args.output.open('x') as out:
            json.dump(trust, out, indent=2)
        print('Exported public trust configuration. SHA256:', fingerprint(trust))
    elif args.command == 'trust':
        if args.file.stat().st_size > 32768:
            raise AuthError('Trust file too large.')
        trust = validate_trust(json.loads(args.file.read_text()))
        if fingerprint(trust) != args.fingerprint.lower().replace(':', ''):
            raise AuthError('Certificate fingerprint mismatch. No trust was installed.')
        private_write(root / 'auth-trust.json', json.dumps(trust))
        print('Pinned the auth host certificate. Use /signin in LAN42.')
    elif args.command == 'renew-credentials':
        settings = json.loads(private_read(root / 'auth-server.json'))
        settings.update(read_credentials(args.credentials))
        private_write(root / 'auth-server.json', json.dumps(settings))
        print('Updated private app credentials. Restart the authentication host.')


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError, ValueError):
        # Configuration parsers can include secret input in their exceptions.
        print('Auth setup/service failed. Check private file permissions, configuration and available ports.', file=sys.stderr)
        sys.exit(1)

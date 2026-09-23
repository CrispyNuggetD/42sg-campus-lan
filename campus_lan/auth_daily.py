"""Owner-only current-seat preparation, called explicitly by dailylogin."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from .auth import AuthError, config_dir, private_read, private_write
from .auth_client import load_trust, relocated
from .network import seat_address


def current_seat():
    name = socket.gethostname().split('.')[0].lower()
    try:
        host = seat_address(name)
    except ValueError:
        raise AuthError('Cannot detect a 42 campus seat from this computer hostname.') from None
    # A hostname alone is not sufficient: this computer must own that address.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind((host, 0))
        except OSError:
            raise AuthError('Detected seat address is not assigned to this computer.') from None
    return host


def prepare(host):
    root = config_dir()
    settings = json.loads(private_read(root / 'auth-server.json'))
    trust = load_trust()
    if trust['certificate'].strip() != private_read(root / 'auth-cert.pem').decode().strip():
        raise AuthError('Owner service and trust certificates disagree; refusing to relocate.')
    changed = settings['host'] != host
    trust = relocated(trust, host)
    settings['host'] = host
    if changed or 'host_generation' not in settings:
        settings['host_generation'] = secrets.token_hex(16)
    # Changing the generation causes an old-seat service to stop gracefully.
    private_write(root / 'auth-server.json', json.dumps(settings))
    private_write(root / 'auth-trust.json', json.dumps(trust, indent=2))
    if changed:
        from .auth_client import clear_session
        clear_session()
    return changed


def unit_quote(value):
    value = str(value)
    if '\n' in value or '\r' in value:
        raise AuthError('Unsupported path in service configuration.')
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%') + '"'


def install_unit():
    root = Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'systemd/user'
    root.mkdir(parents=True, exist_ok=True)
    unit = root / 'lan42-auth.service'
    repo = Path(__file__).resolve().parents[1]
    contents = ('[Unit]\nDescription=LAN42 trusted sign-in on the current owner seat\n'
        'StartLimitIntervalSec=60\nStartLimitBurst=3\n\n[Service]\nType=simple\n'
        f'WorkingDirectory={str(repo).replace("%", "%%")}\n'
        f'ExecStart={unit_quote(sys.executable)} -m campus_lan.auth_server serve --current-seat\n'
        f'Environment={unit_quote("XDG_CONFIG_HOME=" + str(config_dir().parent))}\n'
        'Restart=on-failure\nRestartSec=5\nUMask=0077\nNoNewPrivileges=true\n\n'
        '[Install]\nWantedBy=default.target\n')
    if unit.exists() and unit.read_text() == contents:
        return False
    if unit.is_symlink():
        raise AuthError('Refusing to overwrite a symlinked service definition.')
    fd, name = tempfile.mkstemp(prefix='.lan42-auth-', dir=root)
    try:
        with os.fdopen(fd, 'w') as output:
            output.write(contents)
        os.replace(name, unit)
    finally:
        Path(name).unlink(missing_ok=True)
    return True


def systemctl(*args, check=True):
    result = subprocess.run(['systemctl', '--user', *args], capture_output=True, timeout=15)
    if check and result.returncode:
        raise AuthError('Could not manage the user sign-in service. Check systemctl --user status lan42-auth.')
    return result.returncode == 0


def start():
    root = config_dir()
    if not (root / 'auth-server.json').exists():
        # Ordinary students never receive the app secret or start a broker.
        return None
    host = current_seat()
    fd = os.open(root / 'auth-move.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        moved = prepare(host)
        updated = install_unit()
        # Reload even after a previous failed attempt wrote the unit file.
        systemctl('daemon-reload')
        unit = config_dir().parent / 'systemd/user/lan42-auth.service'
        settings = json.loads(private_read(root / 'auth-server.json'))
        desired = dict(host=host, generation=settings['host_generation'],
                       unit=hashlib.sha256(unit.read_bytes()).hexdigest())
        try:
            applied = json.loads(private_read(root / 'auth-service-applied.json'))
        except FileNotFoundError:
            applied = None
        systemctl('reset-failed', 'lan42-auth.service', check=False)
        running = systemctl('is-active', '--quiet', 'lan42-auth.service', check=False)
        if running and (moved or updated or applied != desired):
            systemctl('restart', 'lan42-auth.service')
        elif not running:
            systemctl('start', 'lan42-auth.service')
        # Starting under systemd is asynchronous. Confirm readiness over TLS.
        from .auth_client import tls_context, server_name, endpoint
        from . import PROTOCOL
        trust = load_trust()
        for _ in range(30):
            try:
                with socket.create_connection(endpoint(trust), timeout=.3) as raw:
                    with tls_context(trust).wrap_socket(raw, server_hostname=server_name(trust)) as sock:
                        sock.sendall((json.dumps(dict(type='ping', protocol=PROTOCOL)) + '\n').encode())
                        with sock.makefile('rb') as stream:
                            reply = json.loads(stream.readline(2048))
                        if reply.get('type') == 'pong' and reply.get('protocol') == PROTOCOL:
                            private_write(root / 'auth-service-applied.json', json.dumps(desired))
                            from .auth_locator import publish
                            try:
                                publish(host)
                            except (OSError, ValueError, subprocess.SubprocessError):
                                print('Sign-in host is ready, but seat publication failed; rerun dailylogin to retry.', file=sys.stderr)
                            return host
            except (OSError, ValueError):
                pass
            time.sleep(.1)
        raise AuthError('The current-seat sign-in service did not become ready.')


def main():
    try:
        host = start()
        if host:
            print(f'42 sign-in host ready on this seat: {host}. Use /signin in LAN42.')
    except (OSError, ValueError, subprocess.SubprocessError):
        # Never include private config/parser errors in shell logs.
        print('Could not start current-seat sign-in. Check the campus address and lan42-auth user service.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

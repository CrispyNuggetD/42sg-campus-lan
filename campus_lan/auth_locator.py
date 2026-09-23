"""Public seat discovery; the existing local certificate remains authoritative."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
from .auth import AuthError, config_dir, private_read, request_json
from .auth_client import change_host, fingerprint, load_trust
from .network import seat_address

REMOTE = 'git@github.com:CrispyNuggetD/42sg-campus-lan.git'
BRANCH = 'auth-seat'
URL = 'https://raw.githubusercontent.com/CrispyNuggetD/42sg-campus-lan/auth-seat/seat.json'


def refresh():
    trust = load_trust()
    try:
        data = request_json(URL, headers={'Cache-Control': 'no-cache'})
        if (set(data) != {'version', 'seat', 'fingerprint'} or data['version'] != 1
                or not isinstance(data['seat'], str)
                or data['fingerprint'] != fingerprint(trust)):
            return
        host = seat_address(data['seat'])
        if host != trust['lobby_host']:
            change_host(data['seat'])
    except (AuthError, OSError, ValueError, TypeError, KeyError):
        # Discovery is optional. Keep the previously verified endpoint on failure.
        return


def publish(host):
    """Use a disposable checkout containing only allowlisted public fields."""
    try:
        enabled = json.loads(private_read(config_dir() / 'auth-publish.json'))
    except FileNotFoundError:
        return False
    trust = load_trust()
    if enabled != {'fingerprint': fingerprint(trust)}:
        raise AuthError('Seat publishing configuration does not match the owner certificate.')
    parts = host.split('.')
    if len(parts) != 4 or parts[0] != '10' or parts[1] not in ('11', '12'):
        raise AuthError('Only a campus seat can be published.')
    seat = f'c{int(parts[1]) - 10}r{int(parts[2])}s{int(parts[3])}'
    if seat_address(seat) != host or host != trust['lobby_host']:
        raise AuthError('Seat publishing address disagrees with the running host.')
    content = json.dumps(dict(version=1, seat=seat, fingerprint=fingerprint(trust)), indent=2) + '\n'
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0',
               GIT_SSH_COMMAND='ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=yes')
    with tempfile.TemporaryDirectory(prefix='lan42-seat-') as directory:
        def git(*args, allowed=(0,)):
            result = subprocess.run(['git', '-C', directory, *args], env=env,
                capture_output=True, timeout=20)
            if result.returncode not in allowed:
                raise AuthError('Seat publication failed. Check GitHub access and rerun dailylogin.')
            return result
        git('init', '--quiet')
        exists = git('ls-remote', '--exit-code', REMOTE, f'refs/heads/{BRANCH}', allowed=(0, 2))
        if exists.returncode == 0:
            git('fetch', '--quiet', '--depth=1', REMOTE, f'refs/heads/{BRANCH}')
            # Only read the locator; never check out remote files or hooks.
            old = git('show', 'FETCH_HEAD:seat.json', allowed=(0, 128))
            if old.returncode == 0 and old.stdout.decode() == content:
                return False
            git('update-ref', 'HEAD', 'FETCH_HEAD')
        path = Path(directory) / 'seat.json'
        path.write_text(content)
        git('add', '--', 'seat.json')
        git('-c', 'user.name=LAN42 seat publisher', '-c', 'user.email=lan42@localhost',
            '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
            'commit', '--quiet', '-m', f'Publish sign-in host seat {seat}')
        git('push', '--quiet', REMOTE, f'HEAD:refs/heads/{BRANCH}')
    return True

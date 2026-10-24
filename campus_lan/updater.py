"""Local terminal maintenance; never accepted as a network command."""
import os
import hashlib
import secrets
from pathlib import Path
import subprocess
import sys
import time


class RestartRequested(Exception):
    def __init__(self, update=False):
        self.update = update


def reload_path(repo=None):
    repo = Path(repo or Path(__file__).resolve().parent.parent).resolve()
    key = hashlib.sha256(str(repo).encode()).hexdigest()[:16]
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))/'42sg-campus-lan'
    return base / ('reload-' + key)


def generation(repo=None):
    try:
        return reload_path(repo).read_text()
    except FileNotFoundError:
        return ''


def notify_reload(repo):
    target = reload_path(repo)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(target.name + '-' + secrets.token_hex(8))
    temporary.write_text(secrets.token_hex(16))
    temporary.replace(target)


def update_checkout(repo):
    """Fast-forward a clean checkout. Preserve all local work on failure."""
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], check=True,
                              capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, GIT_TERMINAL_PROMPT='0'))
    try:
        if git('status', '--porcelain').stdout.strip():
            print('[lan42] Local edits found; update skipped. Restarting this checkout.')
            return False
        result = git('pull', '--ff-only')
        print(result.stdout.strip())
        notify_reload(repo)
        return True
    except (OSError, subprocess.SubprocessError):
        print('[lan42] Update failed; local work preserved. Restarting installed checkout.')
        return False


def restart(update=False, wait_for_node=None):
    # Called only after curses, sockets and the owner's heartbeat have closed.
    repo = Path(__file__).resolve().parent.parent
    if update:
        update_checkout(repo)
    if wait_for_node:
        for _ in range(30):
            if not wait_for_node():
                break
            time.sleep(.1)
        else:
            print('[lan42] Local node is still in use. It will be reused; close other HQ windows to upgrade that node.')
    if not wait_for_node:
        # Let the old game connection and room-owned child finish closing.
        time.sleep(1)
    print('[lan42] Restarting this terminal instance...', flush=True)
    env = dict(os.environ, LAN42_NO_UPDATE='1')
    os.execve('/bin/sh', ['sh', str(repo / 'lan42.sh'), *sys.argv[1:]], env)

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


# Shared by Mac/Linux. Avoid invoking Git on every 80 ms UI tick.
_revision_cache = {}


def checkout_revision(repo):
    key=str(Path(repo).resolve())
    now=time.monotonic()
    previous=_revision_cache.get(key)
    if previous and now-previous[0]<5:
        return previous[1]
    revision=previous[1] if previous else ''
    try:
        result=subprocess.run(['git','-C',key,'rev-parse','--verify','HEAD'],
                              capture_output=True,text=True,check=True,timeout=3,
                              env=dict(os.environ,GIT_OPTIONAL_LOCKS='0'))
        value=result.stdout.strip()
        if len(value) in (40,64) and all(c in '0123456789abcdef' for c in value):
            revision=value
    except (OSError,subprocess.SubprocessError):
        pass  # A transient Git failure must not trigger a restart loop.
    _revision_cache[key]=(now,revision)
    return revision


def generation(repo=None):
    repo=Path(repo or Path(__file__).resolve().parent.parent).resolve()
    try:
        marker=reload_path(repo).read_text()
    except FileNotFoundError:
        marker=''
    # Only an explicitly approved signal reloads running clients/services.
    # A changed checkout is detected by pull entry points, never by the host's
    # watcher: Git activity must not disconnect students without approval.
    return marker


def notify_reload(repo):
    target = reload_path(repo)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = target.with_name(target.name + '-' + secrets.token_hex(8))
    temporary.write_text(secrets.token_hex(16))
    temporary.replace(target)


def request_reload(repo):
    print('[lan42] Reloading ends local matches and disconnects students; Intra sessions may expire.')
    if not sys.stdin.isatty():
        print('[lan42] Reload deferred: run python3 -m campus_lan.updater --request-reload in a terminal.')
        return False
    try:answer=input('Reload LAN42 clients and host now? [y/N]: ').strip().lower()
    except EOFError:answer=''
    if answer not in ('y','yes'):
        print('[lan42] Reload deferred; the host and other connections are kept.')
        return False
    notify_reload(repo)
    return True


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
        request_reload(repo)
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


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Ask before package-wide LAN42 reloads; never a network command.')
    parser.add_argument('--request-reload',action='store_true',required=True)
    parser.add_argument('--previous',help='Before-pull commit; skip prompt if the revision did not change')
    args=parser.parse_args()
    repo=Path(__file__).resolve().parent.parent
    if args.previous is not None and (not args.previous or checkout_revision(repo)==args.previous):return
    request_reload(repo)


if __name__=='__main__':main()

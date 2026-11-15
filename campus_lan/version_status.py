"""Explicit upstream freshness check; never installs code or requests a reload."""
import json
import os
from pathlib import Path
import subprocess


def check(running_version, running_revision='', host_version=None, repo=None):
    repo = Path(repo or Path(__file__).resolve().parent.parent)
    lines = ['Running client: v' + running_version,
             'Connected host: ' + ('v' + host_version if host_version else 'version unavailable')]
    def git(*args):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                              text=True, check=True, timeout=15,
                              env=os.environ | {'GIT_TERMINAL_PROMPT': '0',
                                                           'GIT_SSH_COMMAND': 'ssh -o BatchMode=yes -o ConnectTimeout=5'})
    try:
        head = git('rev-parse', 'HEAD').stdout.strip()
        release = json.loads((repo / 'campus_lan/release.json').read_text()).get('version', 'unknown')
        lines.append('Local checkout: v' + release + ' · ' + head[:8])
        if git('status', '--porcelain').stdout.strip():
            lines.append('Local edits present; a restart loads local code, and /update will skip pulling until they are resolved.')
        if (running_revision and head != running_revision) or release != running_version:
            lines.append('Client restart needed to load the current checkout.')
        if host_version and host_version != release:
            lines.append('Host version differs from checkout; updating files alone does not reload the host.')
        git('fetch', '--quiet', 'origin', 'main')
        upstream = git('rev-parse', 'FETCH_HEAD').stdout.strip()
        counts = git('rev-list', '--left-right', '--count', head + '...' + upstream).stdout.split()
        ahead, behind = map(int, counts)
        if behind and ahead:
            lines.append(f'Branches diverged: {ahead} local-only and {behind} upstream-only commits; reconcile before /update.')
        elif behind:
            lines.append(f'Update available: {behind} upstream commits. Use /update; approve the reload to activate it locally.')
        elif ahead:
            lines.append(f'Checkout ahead of origin/main by {ahead} commits; no upstream update to pull.')
        else:
            lines.append('Checkout is latest on origin/main (checked now). Running processes may still need a reload.')
    except (OSError, ValueError, subprocess.SubprocessError):
        lines.append('Could not verify upstream freshness; latest/update status is unknown. Check connectivity and Git access.')
    return lines

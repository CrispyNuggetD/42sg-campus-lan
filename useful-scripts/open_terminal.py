"""Open LAN42 in another terminal without occupying the dailylogin shell."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def terminal_command(repo, platform=sys.platform, which=shutil.which, args=()):
    launcher = str(repo / 'lan42.sh')
    invocation = ['sh', launcher, *args]
    environment=['LAN42_NO_UPDATE=1'] if args else []
    for name in ('LAN42_POPUP_SESSION','LAN42_POPUP_OWNER_PID'):
        if os.environ.get(name):environment.append(name+'='+os.environ[name])
    if environment:invocation=['env',*environment,*invocation]
    helper = os.environ.get('DAILY_TMUX_HELPER') or str(repo / 'useful-scripts/tmux_workspace.py')
    if not Path(helper).is_file():
        raise RuntimeError('Tmux workspace helper missing: ' + helper)
    role = ('lan42-clusters' if args and args[0]=='clusters' else
            ('lan42-admin-' if args and args[0]=='admin' else 'lan42-game-') + str(os.getpid()) if args else 'lan42')
    return [sys.executable, helper, 'open', '--cwd', str(repo), role, '--', *invocation]


def main():
    if not shutil.which('tmux'):
        install = 'sh '+str(REPO/'setup.sh')
        raise RuntimeError('tmux is required for LAN42 workspaces. Install it: ' + install +
                           '. Use lan42_here to run directly in this terminal meanwhile.')
    result=subprocess.run(terminal_command(REPO, args=sys.argv[1:]), check=True,capture_output=True,text=True)
    if sys.argv[1:2]==['clusters'] and result.stdout.startswith('Already open:'):
        sys.path.insert(0,str(REPO))
        from campus_lan.tmux_control import refresh_cluster_window
        refresh_cluster_window()
    print(result.stdout,end='')
    print('LAN42 is in its tmux workspace; run lan42_window to reconnect.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f'lan42: {exc}')

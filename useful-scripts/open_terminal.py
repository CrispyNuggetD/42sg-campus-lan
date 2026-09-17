"""Open LAN42 in another terminal without occupying the dailylogin shell."""
from pathlib import Path
import os
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def terminal_command(repo, platform=sys.platform, which=shutil.which, args=()):
    launcher = str(repo / 'lan42.sh')
    invocation = ['sh', launcher, *args]
    if args:
        invocation = ['env', 'LAN42_NO_UPDATE=1', *invocation]
    helper = os.environ.get('DAILY_TMUX_HELPER')
    if helper and platform != 'darwin':
        if not Path(helper).is_file():
            raise RuntimeError('Daily tmux helper missing: ' + helper)
        # Separate game launches must not steal the lobby's window.
        role = 'lan42-game-' + str(os.getpid()) if args else 'lan42'
        return [sys.executable, helper, 'open', '--cwd', str(repo), role, '--', *invocation]
    if platform == 'darwin':
        script = '''on run argv
    tell application "Terminal"
        do script (item 1 of argv)
        activate
    end tell
end run'''
        return ['osascript', '-e', script, shlex.join(invocation)]
    for name, flags in (
        ('gnome-terminal', ['--window', '--title=LAN42', '--']),
        ('konsole', ['--separate', '-e']),
        ('xfce4-terminal', ['--disable-server', '-x']),
        ('xterm', ['-T', 'LAN42', '-e']),
    ):
        program = which(name)
        if program:
            return [program, *flags, *invocation]
    raise RuntimeError('No supported desktop terminal found. Open a terminal and run lan42.')


def main():
    command = terminal_command(REPO, args=sys.argv[1:])
    if sys.platform == 'darwin' or os.environ.get('DAILY_TMUX_HELPER'):
        subprocess.run(command, check=True)
    else:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    print('LAN42 is in tmux; use dailyterm to return.' if os.environ.get('DAILY_TMUX_HELPER') else
          'Requested a LAN42 terminal window. Leave it open while playing.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f'lan42: {exc}')

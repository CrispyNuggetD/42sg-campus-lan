"""Open LAN42 in another terminal without occupying the dailylogin shell."""
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]


def terminal_command(repo, platform=sys.platform, which=shutil.which):
    launcher = str(repo / 'lan42.sh')
    if platform == 'darwin':
        script = '''on run argv
    tell application "Terminal"
        do script (item 1 of argv)
        activate
    end tell
end run'''
        return ['osascript', '-e', script, 'sh ' + shlex.quote(launcher)]
    for name, flags in (
        ('gnome-terminal', ['--window', '--title=LAN42', '--']),
        ('konsole', ['--separate', '-e']),
        ('xfce4-terminal', ['--disable-server', '-x']),
        ('xterm', ['-T', 'LAN42', '-e']),
    ):
        program = which(name)
        if program:
            return [program, *flags, 'sh', launcher]
    raise RuntimeError('No supported desktop terminal found. Open a terminal and run lan42.')


def main():
    command = terminal_command(REPO)
    if sys.platform == 'darwin':
        subprocess.run(command, check=True)
    else:
        subprocess.Popen(command, stdin=subprocess.DEVNULL, start_new_session=True)
    print('Requested a LAN42 terminal window. Leave it open while playing.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        raise SystemExit(f'lan42: {exc}')

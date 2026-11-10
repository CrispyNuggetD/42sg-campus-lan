"""Small launcher for upstream CORE Game; no game code or credentials bundled."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import webbrowser

SITE = 'https://coregame.sh'
SOURCE = 'https://github.com/42core-team/monorepo'
VISUALIZER = 'https://visualizer.coregame.sh'
CREDIT = 'CORE Game by 42core-team. LAN42 provides launch helpers only.'


def clone_path():
    return Path(os.environ.get('LAN42_CORE_CLONE', str(Path.home() / 'Documents/CORE Game'))).expanduser().absolute()


def clone():
    """Fetch upstream separately; never pull, overwrite or execute an existing clone."""
    destination = clone_path()
    if destination.exists() or destination.is_symlink():
        if destination.is_symlink() or not (destination / '.git').is_dir():
            raise RuntimeError('Destination already exists and is not a separate Git clone: ' + str(destination))
        result = subprocess.run(['git', '-C', str(destination), 'remote', 'get-url', 'origin'],
                                capture_output=True, text=True, check=True)
        if result.stdout.strip().removesuffix('.git') != SOURCE:
            raise RuntimeError('Existing clone has a different origin; left unchanged.')
        print('Existing CORE clone left unchanged: ' + str(destination))
    else:
        if not shutil.which('git'):
            raise RuntimeError('Install Git before cloning CORE Game.')
        destination.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '--depth', '1', '--', SOURCE + '.git', str(destination)], check=True)
        print('CORE cloned separately: ' + str(destination))
    print('Follow its README for the upstream devcontainer/build workflow.')
    print('No build, package installation or game process was started.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=CREDIT)
    parser.add_argument('action', nargs='?', default='open', choices=('open', 'signin', 'visualizer', 'source', 'clone'))
    args = parser.parse_args(argv)
    print(CREDIT)
    try:
        if args.action == 'clone':
            clone()
        else:
            url = {'source': SOURCE, 'visualizer': VISUALIZER}.get(args.action, SITE)
            print(url)
            if not webbrowser.open_new_tab(url):
                raise RuntimeError('Browser did not open; use the URL above.')
    except (OSError, RuntimeError, subprocess.SubprocessError) as error:
        print('CORE launcher: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())

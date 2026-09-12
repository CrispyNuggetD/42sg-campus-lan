#!/bin/sh
set -eu
if [ "$#" -gt 0 ]; then
    if [ "$#" -eq 1 ] && [ "$1" = --zsh ]; then
        exec sh "$(dirname -- "$0")/useful-scripts/setup-zsh.sh"
    fi
    echo 'Usage: sh setup.sh [--zsh]' >&2
    exit 1
fi
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v git >/dev/null || { echo "Git is required."; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.9+ is required."; exit 1; }
python3 - "$repo_dir" <<'PYSETUP'
import sys
from pathlib import Path
if sys.version_info < (3,9):
    raise SystemExit('Python 3.9+ is required; no packages will be installed.')
repo = Path(sys.argv[1])
launcher = repo / 'launch.sh'
launcher.chmod(launcher.stat().st_mode | 0o100)
print(f'Ready: {launcher}')
print(f'Host: "{launcher}"')
print(f'Join: "{launcher}" join')
print('Everything stays in this clone. No bin directory or PATH changes.')
print('Optional zsh shortcut: sh setup.sh --zsh')
PYSETUP

#!/bin/sh
set -eu
install_zsh=1
case "${1:-}" in
    ""|--zsh) ;;
    --no-zsh) install_zsh=0 ;;
    *) echo 'Usage: sh setup.sh [--no-zsh]' >&2; exit 1 ;;
esac
[ "$#" -le 1 ] || { echo 'Usage: sh setup.sh [--no-zsh]' >&2; exit 1; }
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v git >/dev/null || { echo "Git is required."; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.9+ is required."; exit 1; }
python3 - "$repo_dir" <<'PYSETUP'
import sys
from pathlib import Path
if sys.version_info < (3,9):
    raise SystemExit('Python 3.9+ is required; no packages will be installed.')
repo = Path(sys.argv[1])
launcher = repo / 'lan42.sh'
launcher.chmod(launcher.stat().st_mode | 0o100)
print(f'Ready: {launcher}')
print(f'Host: "{launcher}"')
print(f'Join: "{launcher}" join')
print('Everything stays in this clone. No bin directory or PATH changes.')

PYSETUP
if [ "$install_zsh" = 1 ]; then
    if command -v zsh >/dev/null; then
        python3 "$repo_dir/useful-scripts/install_zsh.py" "$repo_dir"
    else
        echo 'zsh is unavailable; launcher is ready. Install zsh and rerun setup for shell helpers.'
    fi
fi

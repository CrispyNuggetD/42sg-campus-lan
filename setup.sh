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
. "$repo_dir/useful-scripts/setup_python.sh"
setup_python || exit 1
python3 - "$repo_dir" <<'PYSETUP'
import sys
from pathlib import Path
if sys.version_info < (3,9):
    raise SystemExit('The selected Python is too old. Rerun setup to select or install a compatible runtime.')
try:
    import curses
except ImportError:
    raise SystemExit('The selected Python lacks curses. Rerun setup for Python recovery; curses is not a pip dependency.')
repo = Path(sys.argv[1])
launcher = repo / 'lan42.sh'
launcher.chmod(launcher.stat().st_mode | 0o100)
print(f'Ready: {launcher}')
print(f'Lobby: "{launcher}"')
print('Inside your lobby, /join links a friend and exchanges peers.')
print('Core guest mode uses the Python standard library; no pip packages or staff/API credentials are needed.')

PYSETUP
if tmux_bin=$(python3 "$repo_dir/useful-scripts/ensure_tmux.py"); then
    echo "Workspace tmux ready: $tmux_bin"
else
    echo 'Workspace setup unavailable; use ./lan42.sh in this terminal. Rerun sh setup.sh after resolving the message above.'
fi
if [ "$install_zsh" = 1 ]; then
    if command -v zsh >/dev/null; then
        python3 "$repo_dir/useful-scripts/install_zsh.py" "$repo_dir"
    else
        echo 'zsh is unavailable; launcher is ready. Install zsh and rerun setup for shell helpers.'
    fi
fi

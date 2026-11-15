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
. "$repo_dir/useful-scripts/setup_python.sh"
# iSH exposes its emulated Linux environment through /proc/ish.
# Keep the same entry point; do not infer iSH from Alpine or a root account alone.
setup_ish=0
if [ -d /proc/ish ] || { [ -r /proc/version ] && grep -qi 'ish' /proc/version; }; then
    setup_ish=1
    echo 'Detected iSH: using its configured Alpine packages (no repository upgrades).'
    command -v apk >/dev/null 2>&1 || { echo 'iSH apk is unavailable; restore its package manager and rerun setup.' >&2; exit 1; }
    ish_packages=''
    command -v git >/dev/null 2>&1 || ish_packages="$ish_packages git"
    if ! command -v python3 >/dev/null 2>&1 || ! python_works python3; then
        ish_packages="$ish_packages python3"
    fi
    command -v tmux >/dev/null 2>&1 || ish_packages="$ish_packages tmux"
    if [ "$install_zsh" = 1 ] && ! command -v zsh >/dev/null 2>&1; then
        ish_packages="$ish_packages zsh"
    fi
    apk info -e ncurses-terminfo >/dev/null 2>&1 || ish_packages="$ish_packages ncurses-terminfo"
    if [ -n "$ish_packages" ]; then
        echo "iSH packages:$ish_packages" >&2
        echo 'Python/curses runs LAN42; Git updates it; terminfo describes the terminal. tmux and zsh helpers are optional.' >&2
        echo 'This uses apk update and apk add inside iSH, not on iOS or a campus computer. No apk upgrade or repository changes.' >&2
        if setup_install_choice; then
            # Fixed package names above; splitting this list is intentional.
            apk update && apk add $ish_packages || { echo 'iSH package setup failed; check its configured repositories and rerun setup.' >&2; exit 1; }
        fi
    fi
    if ! command -v python3 >/dev/null 2>&1 || ! python_works python3; then
        echo 'iSH needs Alpine Python 3.9+ with curses. Run apk add python3; no uv runtime will be downloaded.' >&2
        exit 1
    fi
    echo 'iSH: launch here with sh lan42.sh; keep the app open. Desktop integrations and on-device compatibility are not verified.'
fi
command -v git >/dev/null || { echo "Git is required."; exit 1; }
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
tmux_allowed=1
if [ "$setup_ish" = 1 ] && ! command -v tmux >/dev/null 2>&1; then tmux_allowed=0; fi
if [ "$setup_ish" != 1 ] && ! command -v tmux >/dev/null 2>&1 && [ ! -x "${FORTYTWO_TOOLS_ROOT:-$HOME/.local/share/42-tools}/tmux/bin/tmux" ]; then
    echo 'Optional: tmux keeps LAN42 windows/jobs running when you detach and provides the lobby/game workspace.' >&2
    echo 'Without it, LAN42 still launches with ./lan42.sh (or lan42_here), but has no managed tmux workspace or detach/reconnect support; keep its terminal open.' >&2
    case "$(uname -s)" in
        Darwin) echo 'Installation uses your existing Homebrew. Homebrew itself will not be installed.' >&2 ;;
        *) echo 'Installation downloads/extracts tmux and direct libraries into your account; no sudo or system package changes.' >&2 ;;
    esac
    setup_install_choice || tmux_allowed=0
fi
if [ "$tmux_allowed" = 1 ]; then
    if tmux_bin=$(python3 "$repo_dir/useful-scripts/ensure_tmux.py" --approved); then
        echo "Workspace tmux ready: $tmux_bin"
    else
        echo 'Workspace setup unavailable; use ./lan42.sh in this terminal. Rerun sh setup.sh after resolving the message above.'
    fi
else
    echo 'tmux skipped. LAN42 is still ready in this terminal: ./lan42.sh (or lan42_here after loading helpers).'
fi
if [ "$install_zsh" = 1 ]; then
    if command -v zsh >/dev/null; then
        python3 "$repo_dir/useful-scripts/install_zsh.py" "$repo_dir"
    else
        echo 'zsh is unavailable; launcher is ready. Install zsh and rerun setup for shell helpers.'
    fi
fi

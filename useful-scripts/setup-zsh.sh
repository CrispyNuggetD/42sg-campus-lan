#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
command -v zsh >/dev/null || { echo 'zsh is required for these optional helpers.'; exit 1; }
if [ "${LAN42_NO_UPDATE:-0}" != 1 ]; then
    if [ -n "$(git -C "$repo_dir" status --porcelain)" ]; then
        echo 'Local edits found. Installing the current helper copy without pulling.'
    else
        GIT_TERMINAL_PROMPT=0 git -C "$repo_dir" pull --ff-only || {
            echo 'Could not get the latest version. Retry or use LAN42_NO_UPDATE=1 explicitly.'
            exit 1
        }
    fi
fi
sh "$repo_dir/setup.sh"
python3 "$repo_dir/useful-scripts/install_zsh.py" "$repo_dir"

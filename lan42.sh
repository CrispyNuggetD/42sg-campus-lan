#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_dir"
if [ "${LAN42_NO_UPDATE:-0}" != 1 ]; then
    echo "[lan42] Updating checkout with git pull --ff-only..."
    if [ -n "$(git status --porcelain)" ]; then
        echo "[lan42] Local edits found; skipping update and using this checkout."
    elif ! GIT_TERMINAL_PROMPT=0 git pull --ff-only; then
        echo "[lan42] Update failed; continuing with installed checkout."
    fi
fi
echo "[lan42] Version $(python3 -c 'from campus_lan import VERSION; print(VERSION)') | commit $(git rev-parse --short HEAD) | $(git log -1 --format=%cs)"
echo "[lan42] Guest mode. Intra sign-in is not implemented."
if [ "$#" -eq 0 ]; then
    set -- host
fi
exec python3 -m campus_lan "$@"

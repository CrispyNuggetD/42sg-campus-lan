#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$repo_dir"
if [ -x "${FORTYTWO_TOOLS_ROOT:-$HOME/.local/share/42-tools}/python/bin/python3" ]; then
    PATH="${FORTYTWO_TOOLS_ROOT:-$HOME/.local/share/42-tools}/python/bin:$PATH"; export PATH
fi
if [ "${LAN42_NO_UPDATE:-0}" != 1 ]; then
    before_revision=$(git rev-parse HEAD)
    echo "[lan42] Updating checkout with git pull --ff-only..."
    if [ -n "$(git status --porcelain)" ]; then
        echo "[lan42] Local edits found; skipping update and using this checkout."
    elif GIT_TERMINAL_PROMPT=0 git pull --ff-only; then
        python3 -m campus_lan.updater --request-reload --previous "$before_revision"
    else
        echo "[lan42] Update failed; continuing with installed checkout."
    fi
fi
echo "[lan42] Version $(python3 -c 'from campus_lan import VERSION; print(VERSION)') | commit $(git rev-parse --short HEAD) | $(git log -1 --format=%cs)"
echo "[lan42] Guest mesh ready. /signin opens 42 sign-in when a trusted auth host is configured."
if [ "$#" -eq 0 ]; then
    set -- lobby
fi
exec python3 -m campus_lan "$@"

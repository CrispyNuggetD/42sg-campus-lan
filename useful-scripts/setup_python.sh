# Sourced by setup.sh; downloading requires an explicit yes.
python_works() {
    "$1" -c 'import sys, curses; sys.exit(0 if sys.version_info >= (3,9) else 1)' >/dev/null 2>&1
}
setup_python() {
    tools_root=${FORTYTWO_TOOLS_ROOT:-$HOME/.local/share/42-tools}
    if command -v python3 >/dev/null 2>&1 && python_works python3; then return 0; fi
    if [ -x "$tools_root/python/bin/python3" ] && python_works "$tools_root/python/bin/python3"; then
        PATH="$tools_root/python/bin:$PATH"; export PATH; return 0
    fi
    if [ -x /usr/bin/python3 ] && python_works /usr/bin/python3; then
        echo 'A compatible system Python is available; LAN42 can bind it in your account.' >&2
        selected_python=/usr/bin/python3
    else
        echo 'Python 3.9+ with curses is missing. Help install it in your account?' >&2
        echo 'This downloads uv from astral.sh (if needed) and a managed Python 3.11 runtime. No sudo or system packages.' >&2
        printf 'Allow this Python installation? [y/N]: ' >&2
        answer=''; IFS= read -r answer || :
        case "$answer" in y|Y|yes|YES) ;; *) echo 'Python installation skipped. Load a compatible school Python and rerun sh setup.sh.' >&2; return 1 ;; esac
        uv_bin=$(command -v uv || :)
        if [ -z "$uv_bin" ] && [ -x "$tools_root/uv/uv" ]; then uv_bin="$tools_root/uv/uv"; fi
        if [ -z "$uv_bin" ]; then
            command -v curl >/dev/null 2>&1 || { echo 'curl is unavailable; load school-provided curl or Python and rerun setup.' >&2; return 1; }
            installer=$(mktemp "${TMPDIR:-/tmp}/lan42-uv.XXXXXXXX") || return 1
            if ! curl -fsSL https://astral.sh/uv/install.sh -o "$installer"; then rm -f "$installer"; return 1; fi
            if ! UV_INSTALL_DIR="$tools_root/uv" UV_NO_MODIFY_PATH=1 sh "$installer" >&2; then rm -f "$installer"; return 1; fi
            rm -f "$installer"
            uv_bin="$tools_root/uv/uv"
        fi
        export UV_PYTHON_INSTALL_DIR="$tools_root/python/runtime"
        "$uv_bin" python install 3.11 >&2 || return 1
        selected_python=$("$uv_bin" python find --managed-python 3.11) || return 1
        python_works "$selected_python" || { echo 'Downloaded Python failed the version/curses check; setup stopped.' >&2; return 1; }
    fi
    mkdir -p "$tools_root/python/bin" || return 1
    ln -sf "$selected_python" "$tools_root/python/bin/python3" || return 1
    PATH="$tools_root/python/bin:$PATH"; export PATH
    echo 'LAN42 Python is ready; its shell helper and launcher reuse this private binding.' >&2
}

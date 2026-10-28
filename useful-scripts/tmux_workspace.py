#!/usr/bin/env python3
"""Named tmux windows for dailylogin and standalone terminal helpers."""
import argparse
from contextlib import contextmanager
import fcntl
import os
from pathlib import Path
import re
import shutil
import shlex
import subprocess
import sys
import time

# An explicit socket path is useful for isolated tests or a separate workspace.
def tmux(*args, check=True):
    command = ["tmux"]
    if os.environ.get("DAILY_TMUX_SOCKET"):
        command += ["-S", os.environ["DAILY_TMUX_SOCKET"]]
    return subprocess.run(command + list(args), check=check, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def session_name(role=None):
    name = (os.environ.get("LAN42_TMUX_SESSION", "lan42") if role and role.startswith("lan42")
            else os.environ.get("DAILY_TMUX_SESSION", "daily"))
    if not re.fullmatch(r"[A-Za-z0-9_-]+", name):
        raise ValueError("DAILY_TMUX_SESSION must use letters, digits, underscores or hyphens.")
    return name

@contextmanager
def launch_lock():
    directory = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "daily-tmux"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "launch.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield lock

def exists(session):
    return tmux("has-session", "-t", "=" + session, check=False).returncode == 0

def find_window(session, role):
    if not exists(session):
        return None
    rows = tmux("list-windows", "-t", "=" + session, "-F",
                "#{window_id}\t#{@daily_role}").stdout.splitlines()
    return next((row.split("\t")[0] for row in rows
                 if row.partition("\t")[2] == role), None)

def migrate_layout():
    """Move managed legacy tabs without restarting their processes."""
    work, lan = session_name(), session_name("lan42")
    with launch_lock():
        if not exists(work):
            return
        rows = tmux("list-windows", "-t", "=" + work, "-F",
                    "#{window_id}\t#{@daily_role}").stdout.splitlines()
        for row in rows:
            window, _, role = row.partition("\t")
            if role == "zsh" and not find_window(work, "current-project"):
                tmux("set-option", "-w", "-t", window, "@daily_role", "current-project")
                tmux("rename-window", "-t", window, "Current Project")
            if role.startswith("lan42") and work != lan:
                placeholder = None
                if not exists(lan):
                    placeholder = tmux("new-session", "-d", "-P", "-F", "#{window_id}",
                                       "-s", lan, "-n", "migration", "/bin/sh").stdout.strip()
                tmux("move-window", "-s", window, "-t", lan + ":")
                if placeholder:
                    tmux("kill-window", "-t", placeholder)


def open_window(session, role, cwd, command):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", role):
        raise ValueError("Window role must use letters, digits, underscores or hyphens.")
    if not Path(cwd).is_dir():
        raise ValueError("Working directory missing: " + cwd)
    with launch_lock():
        window = find_window(session, role)
        if window:
            states = tmux("list-panes", "-t", window, "-F", "#{pane_dead}").stdout.splitlines()
            if any(state == "0" for state in states):
                print("Already open: " + session + " / " + role)
                return window
        else:
            # Start a waiting shell, set retention first, then replace our shell.
            # This also retains errors from commands that fail immediately.
            if exists(session):
                window = tmux("new-window", "-d", "-P", "-F", "#{window_id}",
                              "-t", session + ":", "-n", "Current Project" if role == "current-project" else role, "-c", cwd,
                              "/bin/sh").stdout.strip()
            else:
                window = tmux("new-session", "-d", "-P", "-F", "#{window_id}",
                              "-s", session, "-n", "Current Project" if role == "current-project" else role, "-c", cwd,
                              "/bin/sh").stdout.strip()
            tmux("set-option", "-w", "-t", window, "@daily_role", role)
        tmux("set-option", "-w", "-t", window, "remain-on-exit", "on")
        tmux("set-option", "-w", "-t", window, "automatic-rename", "off")
        # Refresh desktop connection details rather than using the server's old ones.
        invocation = ["env"]
        for key in ("DAILY_TMUX_BATCH", "GNOME_TERMINAL_SCREEN", "GNOME_TERMINAL_SERVICE",
                    "GIO_LAUNCHED_DESKTOP_FILE", "GIO_LAUNCHED_DESKTOP_FILE_PID"):
            invocation += ["-u", key]
        for key in ("PATH", "DISPLAY", "WAYLAND_DISPLAY", "XAUTHORITY",
                    "DBUS_SESSION_BUS_ADDRESS", "SSH_AUTH_SOCK", "DAILY_TMUX_HELPER",
                    "DAILY_TMUX_SESSION", "LAN42_TMUX_SESSION", "DAILY_TMUX_MAXIMIZE", "ZSHRC_PORTABLE_SETTINGS_FILE",
                    "ZSHRC_RUNTIME_ROOT", "ZSHRC_SETTINGS_FILE", "PROJECTS_ROOT", "current_proj",
                    "LOGIN_ITEMS_SCRIPT", "LOGIN_ITEMS_TESTER", "LOGIN_ITEMS_TMUX_ROLE",
                    "MAIN_REPO_ROOT", "MAC_REMOTE_ROOT",
                    "STAYON_ROOT", "LAN42_CLONE"):
            if key in os.environ:
                invocation.append(key + "=" + os.environ[key])
        tmux("set-option", "-t", session, "history-limit", "50000")
        tmux("respawn-window", "-k", "-t", window, "-c", cwd, *invocation, *command)
        print("Opened: " + session + " / " + role)
        return window

def attached(session):
    rows = tmux("list-sessions", "-F", "#{session_name}\t#{session_attached}", check=False).stdout.splitlines()
    for row in rows:
        name, _, count = row.partition("\t")
        if name == session:
            # A vanished session or incomplete format result is not an
            # attachment. Keep waiting instead of crashing the GUI launch.
            return int(count) if count.isdecimal() else 0
    return 0

def gnome_parent(session):
    """Recover only GNOME's two routing values from an attached tmux client.

    tmux panes deliberately discard these stale values, but the outer client
    still has the correct desktop tab identity. Never expose its environment.
    """
    rows = tmux("list-clients", "-F", "#{client_pid}\t#{client_session}", check=False).stdout.splitlines()
    for row in rows:
        pid, _, name = row.partition("\t")
        if name != session or not pid.isdecimal():continue
        try:
            entries = (Path('/proc')/pid/'environ').read_bytes().split(b'\0')
            values = {}
            for entry in entries:
                key, _, value = entry.partition(b'=')
                if key in (b'GNOME_TERMINAL_SCREEN', b'GNOME_TERMINAL_SERVICE'):
                    values[key.decode()] = value.decode()
            if (re.fullmatch(r'/org/gnome/Terminal/screen/[A-Za-z0-9_]+', values.get('GNOME_TERMINAL_SCREEN', ''))
                    and re.fullmatch(r':[0-9]+\.[0-9]+', values.get('GNOME_TERMINAL_SERVICE', ''))):
                return values
        except (OSError, UnicodeError):continue
    return {key: os.environ[key] for key in ('GNOME_TERMINAL_SCREEN', 'GNOME_TERMINAL_SERVICE')
            if key in os.environ}


def maximize_enabled():
    return os.environ.get("DAILY_TMUX_MAXIMIZE", "TRUE").lower() in ("1", "true", "yes", "on")


def maximize_current_terminal():
    if not maximize_enabled():
        return
    if sys.platform == "darwin":
        subprocess.run(["osascript", "-e", 'tell application "Terminal" to set zoomed of front window to true'],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    elif sys.stdout.isatty():
        print("\033[9;1t", end="", flush=True)


def mac_work_tty(reuse_terminal=False):
    """Identify the Terminal tab that hosts (or will host) the Work client."""
    rows = tmux("list-clients", "-F", "#{client_session}\t#{client_tty}",
                check=False).stdout.splitlines()
    work = session_name()
    attached_tty = next((tty for row in rows for name, _, tty in [row.partition("\t")]
                         if name == work and tty.startswith("/dev/")), None)
    if attached_tty:
        return attached_tty
    if reuse_terminal and sys.stdin.isatty() and not os.environ.get("TMUX"):
        return os.ttyname(sys.stdin.fileno())
    return None


def mac_terminal_script(tab=False):
    if not tab:
        return ('on run argv\n tell application "Terminal"\n'
                ' do script (item 1 of argv)\n' +
                (' set zoomed of front window to true\n' if maximize_enabled() else '') +
                ' activate\n end tell\nend run')
    # Terminal cannot create a tab through its AppleScript dictionary. Route the
    # standard New Tab shortcut to the window containing Work's exact TTY, then
    # address the newly selected tab explicitly. No shell command is typed into
    # Work's running tab.
    return ('on run argv\n'
            ' set shellCommand to item 1 of argv\n'
            ' set parentTTY to item 2 of argv\n'
            ' tell application "Terminal"\n'
            '  set targetWindow to missing value\n'
            '  repeat with candidateWindow in windows\n'
            '   repeat with candidateTab in tabs of candidateWindow\n'
            '    if tty of candidateTab is parentTTY then\n'
            '     set targetWindow to candidateWindow\n'
            '     exit repeat\n'
            '    end if\n'
            '   end repeat\n'
            '   if targetWindow is not missing value then exit repeat\n'
            '  end repeat\n'
            '  if targetWindow is missing value then error "Work Terminal tab not found"\n'
            '  activate\n'
            '  set index of targetWindow to 1\n'
            '  set parentWindowID to id of targetWindow\n'
            ' end tell\n'
            ' tell application "System Events" to keystroke "t" using command down\n'
            ' tell application "Terminal"\n'
            '  repeat 30 times\n'
            '   if (id of front window) is not parentWindowID then exit repeat\n'
            '   delay 0.1\n'
            '  end repeat\n'
            '  if (id of front window) is parentWindowID then error "New Terminal tab did not open"\n'
            ' end tell\n'
            ' tell application "System Events" to tell application process "Terminal"\n'
            '  if (count radio buttons of tab group 1 of front window) < 2 then error "Terminal opened another window instead of a tab"\n'
            ' end tell\n'
            ' tell application "Terminal"\n'
            '  do script shellCommand in selected tab of front window\n' +
            ('  set zoomed of front window to true\n' if maximize_enabled() else '') +
            ' end tell\nend run')


def show(session, window=None, reuse_terminal=False, mac_parent_tty=None):
    if not exists(session):
        print("No daily windows yet. Run start_codex, start_lan42, or dailylogin.")
        return
    # A standalone launch from tmux switches its existing client; never nest tmux.
    if (os.environ.get("TMUX") and
            tmux("display-message", "-p", "#S").stdout.strip() == session):
        tmux("switch-client", "-t", "=" + session)
        if window:
            tmux("select-window", "-t", window)
        return
    with launch_lock() as lock_file:
        if attached(session):
            print("Already visible in a terminal. Use Prefix → w to choose a window.")
            return
        attach = ["tmux"]
        if os.environ.get("DAILY_TMUX_SOCKET"):
            attach += ["-S", os.environ["DAILY_TMUX_SOCKET"]]
        attach += ["attach-session", "-t", "=" + session]
        if window:
            tmux("select-window", "-t", window)
        if sys.platform != "darwin" and not (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")):
            print("Session is running. Reconnect: tmux attach -t " + session)
            return
        if reuse_terminal and sys.stdin.isatty() and not os.environ.get("TMUX"):
            maximize_current_terminal()
            # Release the launch lock before the blocking attachment.
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            subprocess.run(attach, check=True)
            return
        if sys.platform == "darwin":
            if mac_parent_tty is None and session == session_name("lan42"):
                mac_parent_tty = mac_work_tty()
            # zsh expands unquoted =NAME as a command path, unlike POSIX sh.
            # shlex.join considers '=' safe, so quote the exact-session target.
            shell_command = shlex.join(attach[:-1]) + " '=" + session + "'"
            desktop = ["osascript", "-e", mac_terminal_script(bool(mac_parent_tty)),
                       shell_command, *([mac_parent_tty] if mac_parent_tty else [])]
        elif shutil.which("gnome-terminal"):
            # A terminal tab is a separate tmux client/session, not nested tmux.
            # The parent screen below explicitly selects the Work terminal window.
            lan_tab = session == session_name("lan42")
            desktop = ["gnome-terminal", "--tab" if lan_tab else "--window", "--title=" + ("LAN42" if lan_tab else "Work workspace"),
                       *(["--maximize"] if maximize_enabled() else []), "--", *attach]
        elif shutil.which("xterm"):
            desktop = ["xterm", *(["-maximized"] if maximize_enabled() else []), "-T", "Daily workspace", "-e", *attach]
        else:
            print("No desktop terminal found. Reconnect: tmux attach -t " + session)
            return
        env = dict(os.environ)
        for key in ("DAILY_TMUX_BATCH", "GNOME_TERMINAL_SCREEN", "GNOME_TERMINAL_SERVICE",
                    "GIO_LAUNCHED_DESKTOP_FILE", "GIO_LAUNCHED_DESKTOP_FILE_PID"):
            env.pop(key, None)
        if sys.platform != "darwin" and desktop[0] == "gnome-terminal" and "--tab" in desktop:
            # --tab alone creates another window when the parent identity is
            # absent. Explicitly target Work's outer terminal, not a tmux pane.
            env.update(gnome_parent(session_name()))
        # Hold the launch lock until attached, preventing simultaneous GUI requests.
        process = subprocess.Popen(desktop, env=env, start_new_session=True,
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.PIPE if sys.platform == "darwin" else subprocess.DEVNULL,
                                   text=True)
        for _ in range(40):
            if attached(session):
                return
            if process.poll() not in (None, 0):
                detail = (process.stderr.read().strip() if process.stderr else "")
                raise RuntimeError("Terminal launch failed" + (": " + detail if detail else ".")
                                   + " Reconnect: tmux attach -t " + session)
            time.sleep(0.1)
        raise RuntimeError("Terminal did not attach. Session is running; use: tmux attach -t " + session)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    opener = actions.add_parser("open")
    opener.add_argument("role")
    opener.add_argument("--cwd", default=os.getcwd())
    opener.add_argument("command", nargs=argparse.REMAINDER)
    actions.add_parser("show")
    actions.add_parser("show-all")
    actions.add_parser("list")
    args = parser.parse_args()
    if not shutil.which("tmux"):
        if sys.platform == "darwin":
            solution = ("Run: brew install tmux" if shutil.which("brew") else
                        "Install Homebrew from https://brew.sh, then run: brew install tmux")
        else:
            solution = "Run dailylogin or LAN42 setup.sh for user-level tmux setup without sudo."
        raise RuntimeError("tmux is missing. " + solution + " Then rerun dailylogin.")
    migrate_layout()
    session = session_name(args.role if args.action == "open" else None)
    if args.action == "list":
        if exists(session):
            print(tmux("list-windows", "-t", "=" + session, "-F",
                       "#{window_index}: #{window_name} | panes: #{window_panes} | active: #{window_active}").stdout, end="")
        else:
            print("No daily windows yet.")
    elif args.action == "show-all":
        lan = session_name("lan42")
        if sys.platform == "darwin":
            # A foreground dli may attach Work in its original Terminal tab.
            # Otherwise establish Work first and locate its actual GUI tab by TTY.
            reuse = sys.stdin.isatty() and not os.environ.get("TMUX")
            if not reuse:
                show(session)
            if lan != session and exists(lan):
                show(lan, mac_parent_tty=mac_work_tty(reuse_terminal=reuse))
            if reuse:
                show(session, reuse_terminal=True)
            return
        desktop_batch = (sys.platform != "darwin" and shutil.which("gnome-terminal")
                         and (os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
                         and (not sys.stdin.isatty() or os.environ.get("TMUX")))
        if desktop_batch:
            # Establish Work first so LAN42's --tab joins that terminal window.
            show(session)
            if lan != session and exists(lan):show(lan)
        else:
            # Open LAN42's second tab before the blocking Work attachment in
            # the caller's original terminal tab.
            if lan != session and exists(lan):show(lan)
            show(session, reuse_terminal=True)
    elif args.action == "show":
        show(session)
    else:
        command = args.command
        if command[:1] == ["--"]:
            command = command[1:]
        if not command:
            parser.error("open requires a command after --")
        window = open_window(session, args.role, args.cwd, command)
        if os.environ.get("DAILY_TMUX_BATCH") != "1":
            show(session, window)

if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as error:
        detail = error.stderr.strip() if isinstance(error, subprocess.CalledProcessError) else str(error)
        sys.exit("daily tmux: " + detail)

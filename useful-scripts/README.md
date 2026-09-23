# Public zsh helpers

Adapted from [Ryker's public SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).

The original combines general helpers with Ryker's own settings and daily routine.
This copy keeps the reusable compile/run, project navigation, repository pulls and
dailylogin ideas. It does not copy his email, project selection, brightness changes,
attendance scripts, mailbox/stayon startup, application launches or automatic cleanup.
Public syncproj pulls only; commit and push your own work explicitly.

## Setup (included by default)

From your clone, run:

```sh
sh setup.sh
```

Setup prepares `lan42.sh`, backs up your `.zshrc`, and appends a guarded source
block. Existing text is never truncated or rewritten. It honours `ZDOTDIR`.
An identical block is skipped on repeat installs. A changed clone path adds a
new block at the end; old blocks remain, and missing helper files are skipped
by the new guarded blocks. You can remove stale blocks manually later.

Use `sh setup.sh --no-zsh` to opt out. The older `--zsh` flag still works.
Open a new zsh terminal afterward, or run `source "${ZDOTDIR:-$HOME}/.zshrc"`.
A setup subprocess cannot define functions in the shell that launched it.

The block loads `campus.zsh` directly from this clone, so Git updates also update
the helpers. `dailylogin` (or `lan42_dailylogin` if you already have a personal
command) pulls the repo, reloads the helpers and opens LAN42 in a separate
terminal window. `lan42` opens it in the current terminal instead.

macOS uses Terminal; Linux supports GNOME Terminal, Konsole, Xfce Terminal and
xterm. Without a supported desktop terminal, run `lan42` yourself. Repeating
`dailylogin` requests another window, so close an existing LAN42 window first
if you want to restart it. Other personal daily-login tasks are not installed.

## Manual installation

Add this to ~/.zshrc, adjusting the clone path:

    source "$HOME/Documents/42sg-campus-lan/useful-scripts/campus.zsh"

Settings go **before** the source line. For example, using your own paths:

    export LAN42_MAIN_REPO_ROOT="$HOME/Documents/my-school-repo"
    export LAN42_PROJECT_PATH="Core Curriculum/Projects/my-project"
    export LAN42_DOCUMENTS_ROOT="$HOME/Documents"
    export LAN42_PULL_OTHER_REPOS=0
    export LAN42_OPEN_ON_LOGIN=1

Set LAN42_PULL_OTHER_REPOS=1 if you want dailylogin to pull **all** working Git
repositories beneath that directory. This is optional; the default only updates
the campus LAN clone. It preserves dirty worktrees and reports failures.

Set `LAN42_OPEN_ON_LOGIN=0` to update without opening a lobby window.

## Commands

| Command | Behaviour |
| --- | --- |
| lan42 | Launch the lobby; launcher checks for updates |
| lan42_dailylogin | Pull, reload helpers and open LAN42 in another window |
| lan42_window | Open LAN42 in another terminal window |
| lan42_syncdocs | Explicitly pull working repositories beneath Documents |
| lan42_syncproj | Pull your configured main repository |
| lan42_cdmain | Change into your configured main repository |
| lan42_curproj | Change into your configured project and show its latest commit |
| lan42_compile | cc with -Wall -Wextra -Werror |
| lan42_run | Run a supplied program under valgrind |

If you do not already have a function or alias with the name, setup also provides
dailylogin, syncdocs, syncproj, cdmain, curproj, compile and run as short wrappers.
Existing functions and aliases remain intact — especially Ryker's personal
dailylogin. Use the lan42_ names to access these helpers unambiguously.
Put any existing personal definitions before the source line.

Compiler and valgrind commands require those tools already installed. No packages
are installed. Sourcing the helper file performs no network calls or background work.
Repository updates are fast-forward only: no resets, staging, commits or pushes.

To uninstall the shell helpers, remove the marked 42sg-campus-lan block from
.zshrc and open a new terminal. The backed-up configuration is also available.


When private sign-in-host configuration exists, `lan42_dailylogin` also runs
`campus_lan.auth_daily` before opening HQ. It detects the current campus seat
and starts/reuses the owner-only authentication service. Ordinary students
without that private configuration do not start a service. See
[the sign-in guide](../docs/sign-in.md) for host moves and `/authhost SEAT`.

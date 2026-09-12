# Public zsh helpers

Adapted from [Ryker's public SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).

The original combines general helpers with Ryker's own settings and daily routine.
This copy keeps the reusable compile/run, project navigation, repository pulls and
dailylogin ideas. It does not copy his email, project selection, brightness changes,
attendance scripts, mailbox/stayon startup, application launches or automatic cleanup.
Public syncproj pulls only; commit and push your own work explicitly.

## Recommended setup

From your clone:

    sh setup.sh --zsh

This attempts a fast-forward pull for the latest version, prepares the launcher inside your clone,
backs up your existing .zshrc, and adds one marked source block. The lan42 shortcut is a zsh function pointing to
`lan42.sh` in this clone; nothing is installed into a bin directory. It honours ZDOTDIR.
It never replaces your shell configuration or executes it during installation.
Open a new terminal afterward, or source your .zshrc yourself.

The block loads campus.zsh directly from this clone. You do not have to copy the
functions again after a Git update. Run lan42_dailylogin to pull and reload them
in your current shell, or open a new shell after another command pulls the repo.
Rerunning setup updates the managed block without duplicating it.

If the clone has local edits, setup installs that local version and says so.
If a clean clone cannot pull, setup stops; retry or explicitly use:

    LAN42_NO_UPDATE=1 sh setup.sh --zsh

## Manual installation

Add this to ~/.zshrc, adjusting the clone path:

    source "$HOME/Documents/42sg-campus-lan/useful-scripts/campus.zsh"

Settings go **before** the source line. For example, using your own paths:

    export LAN42_MAIN_REPO_ROOT="$HOME/Documents/my-school-repo"
    export LAN42_PROJECT_PATH="Core Curriculum/Projects/my-project"
    export LAN42_DOCUMENTS_ROOT="$HOME/Documents"
    export LAN42_PULL_OTHER_REPOS=0

Set LAN42_PULL_OTHER_REPOS=1 if you want dailylogin to pull **all** working Git
repositories beneath that directory. This is optional; the default only updates
the campus LAN clone. It preserves dirty worktrees and reports failures.

## Commands

| Command | Behaviour |
| --- | --- |
| lan42 | Launch the lobby; launcher checks for updates |
| lan42_dailylogin | Pull and reload helpers; no lobby or other apps launched |
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

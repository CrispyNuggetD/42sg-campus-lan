# Public adaptation of CrispyNuggetD/42_Singapore_SUTD:
# "Useful .zshrc edits (addition)". Source this file from zsh; do not execute it.
# Personal settings belong BEFORE the source line in ~/.zshrc.
[[ -n "$ZSH_VERSION" ]] || return 1
typeset -g LAN42_REPO_ROOT="${${(%):-%N}:A:h:h}"
: ${LAN42_DOCUMENTS_ROOT:=$HOME/Documents}
: ${LAN42_PULL_OTHER_REPOS:=0}
: ${LAN42_OPEN_ON_LOGIN:=1}
: ${LAN42_MAIN_REPO_ROOT:=}
: ${LAN42_PROJECT_PATH:=}

lan42() { command sh "$LAN42_REPO_ROOT/lan42.sh" "$@"; }
lan42_window() { command python3 "$LAN42_REPO_ROOT/useful-scripts/open_terminal.py"; }
lan42_compile() { command cc -Wall -Wextra -Werror "$@"; }
lan42_run() { command valgrind --leak-check=full --show-leak-kinds=all "$@"; }

lan42_cdmain() {
  [[ -n "$LAN42_MAIN_REPO_ROOT" ]] || {
    print -u2 -- 'Set LAN42_MAIN_REPO_ROOT in ~/.zshrc to your own repository.'
    return 1
  }
  builtin cd -- "$LAN42_MAIN_REPO_ROOT"
}

lan42_curproj() {
  [[ -n "$LAN42_MAIN_REPO_ROOT" && -n "$LAN42_PROJECT_PATH" ]] || {
    print -u2 -- 'Set LAN42_MAIN_REPO_ROOT and LAN42_PROJECT_PATH in ~/.zshrc.'
    return 1
  }
  builtin cd -- "$LAN42_MAIN_REPO_ROOT/$LAN42_PROJECT_PATH" || return
  print -r -- "Project: $PWD"
  git log -1 --format='%h %s (%cr)' 2>/dev/null
}

# Pull only: no automatic staging, commits, pushes, cleanup or app launches.
lan42_pull() {
  local repo="$1"
  [[ -d "$repo" ]] || { print -u2 -- "Missing directory: $repo"; return 1; }
  git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1 || return 1
  if [[ -n "$(git -C "$repo" status --porcelain)" ]]; then
    print -u2 -- "Skipped local edits: $repo"
    return 1
  fi
  print -r -- "Pulling: $repo"
  GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=10" \
    git -C "$repo" -c merge.autostash=false -c rebase.autostash=false pull --no-rebase --ff-only
}

lan42_syncproj() {
  [[ -n "$LAN42_MAIN_REPO_ROOT" ]] || {
    print -u2 -- 'Set LAN42_MAIN_REPO_ROOT to your own repo first.'
    return 1
  }
  lan42_pull "$LAN42_MAIN_REPO_ROOT"
}

# Adapted from the original recursive syncdocs. Handles .git directories/files,
# nested clones and worktrees; does not follow symlinked subdirectories.
lan42_syncdocs() (
  local root="$LAN42_DOCUMENTS_ROOT" listing marker repo
  local total=0 failed=0 scan_failed=0
  [[ -d "$root" ]] || { print -u2 -- "Missing directory: $root"; return 1; }
  listing=$(mktemp "${TMPDIR:-/tmp}/lan42-syncdocs.XXXXXXXX") || return 1
  trap 'rm -f -- "$listing"' EXIT
  find -H "$root" -name .git \( -type d -o -type f \) -prune -print0 > "$listing" || scan_failed=1
  while IFS= read -r -d '' marker; do
    repo="${marker%/.git}"
    (( total += 1 ))
    lan42_pull "$repo" || (( failed += 1 ))
  done < "$listing"
  print -r -- "Documents sync: $total repositories; $failed need attention."
  (( failed == 0 && scan_failed == 0 ))
)

lan42_dailylogin() {
  local result=0
  if [[ "$LAN42_PULL_OTHER_REPOS" == 1 ]]; then
    lan42_syncdocs || result=1
    # The clone may be outside Documents; ensure it is updated in that case.
    if [[ "$LAN42_REPO_ROOT" != "${LAN42_DOCUMENTS_ROOT:A}"/* ]]; then
      lan42_pull "$LAN42_REPO_ROOT" || result=1
    fi
  else
    lan42_pull "$LAN42_REPO_ROOT" || result=1
  fi
  source "$LAN42_REPO_ROOT/useful-scripts/campus.zsh"
  print -- 'Campus helpers reloaded.'
  if [[ "$LAN42_OPEN_ON_LOGIN" == 1 ]]; then
    lan42_window || result=1
  fi
  return $result
}

# Keep all personal aliases/functions intact. Prefixed names always remain usable.
(( $+functions[dailylogin] || $+aliases[dailylogin] )) || functions[dailylogin]='lan42_dailylogin "$@"'
(( $+functions[syncdocs] || $+aliases[syncdocs] )) || functions[syncdocs]='lan42_syncdocs "$@"'
(( $+functions[syncproj] || $+aliases[syncproj] )) || functions[syncproj]='lan42_syncproj "$@"'
(( $+functions[cdmain] || $+aliases[cdmain] )) || functions[cdmain]='lan42_cdmain "$@"'
(( $+functions[curproj] || $+aliases[curproj] )) || functions[curproj]='lan42_curproj "$@"'
(( $+functions[compile] || $+aliases[compile] )) || functions[compile]='lan42_compile "$@"'
(( $+functions[run] || $+aliases[run] )) || functions[run]='lan42_run "$@"'

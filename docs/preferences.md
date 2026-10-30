# Shortcuts, notifications and consent

[← LAN42](../README.md) · [All guides](README.md)

- [Notification channels](#notification-channels)
- [Web search and the impact counter](#web-search-and-the-impact-counter)
- [Exam quiet and release digests](#exam-quiet-and-release-digests)
- [Keyboard and clickable controls](#keyboard-and-clickable-controls)
- [Account settings](#account-settings)
- [Visual guide and popup permissions](#visual-guide-and-popup-permissions)
- [Batch popup setup](#batch-popup-setup)
- [Automatic login and closing the sign-in tab](#automatic-login-and-closing-the-sign-in-tab)
- [Local command history, shell and output volume](#local-command-history-shell-and-output-volume)

## Notification channels

Notification channels are private **per computer** and shared by its LAN42
windows. Important channels default to on: **host** (API host online),
**announcements** (approved broadcasts and moderator approval requests),
**releases** (a changed trusted-host version, including patches), **warnings**
(host going offline), and **flock** (42 Singapore flock invitations). **Files**
(offers inside a deliberately joined group) also defaults to on. **Tracking** alerts also default to on for people/rules you
explicitly track; **chat**, **dms** and **pokes** default to off.

Use `/notify` to inspect them, `/notify dms on` or `/notify host off` for one
channel, and `/notify all off` to silence everything—even important alerts.
`/notify all on` restores your individual choices. `/notify on|off` controls the
ordinary chat/DM/poke/tracking channels together; it leaves important channels
alone. `/settings notifications CATEGORY on|off` is an alias. `--no-notify`
silences every desktop category for that launch. Sound/output controls are
separate from notification visibility.

Important alerts display without a new consent question by default, while an
existing `/settings permissions notifications deny` blocks them. To restore
those popups, use `/settings permissions notifications allow`. Social and tracking
popups retain the existing consent flow. Host changes and broadcasts are deduplicated
per computer. Initial offline startup stays quiet; a live host going offline
produces one warning. Release notices compare the pinned host's advertised server
version with the last observed version; first contact establishes a baseline.
They add no 42 API requests, never install updates, and do not announce unrelated
GitHub/README changes. Guest chat/games work without the API host; sign-in and
fresh campus views need it. In-app status and message history remain visible
regardless of desktop preferences.

## Web search and the impact counter

`/search TERMS` opens Ecosia in your default browser. Choose Google or a custom
HTTPS engine in `/settings search`, and inspect the permanent host aggregate with
`/search stats`. Counting defaults to on; `/settings search counting off` opts out.
Only a total and estimated uniqueness sketch persist, with no query history,
identity records or result tracking. [Search, privacy and counter details](web-search.md).

## Exam quiet and release digests

Built-in SGT quiet hours are **Wednesday 15:00–18:00** and **every Saturday
13:00–16:00**, including cancelled-exam days. The trusted host can add visible
API exam dates or bounded admin mute windows. This silences LAN42, not your system
or other apps. `/quiet status` explains the active policy; `/exams` reads the
shared calendar cache. [Scheduling, privacy and trust boundaries](exam-quiet.md).

Release desktop alerts wait for 30 minutes without another version change, then
show at most once per 24 hours per computer. New versions replace the pending
digest. Exam quiet defers these popups; `/changelog` and terminal version messages
remain available. First contact is a silent baseline. Rapid host restarts suppress
repeat arrival popups; meaningful outages still get an availability notification.

## Keyboard and clickable controls

The persistent footer buttons are clickable. **F2** signs in or out (use HQ for
account changes), **F4** mutes system output, **F5** toggles system output
between 0% and 30%, **F6** tries `/uwu` once, and **F7** toggles automatic uwu
for this window. The guest prompt also supports “click here”. Some terminals
require Fn with function keys; the clickable buttons work without them. F4 also pauses uwu output in this window until F5, so automatic uwu cannot
raise the volume behind your back. These controls preserve your typed draft and wait while a consent/setup question is
active. Sound permission remains separate; output mute does not disable desktop
popups (`/notify off` controls ordinary notifications). Tab still switches the
roster/map or game mode; PgUp/PgDn scroll chat.

## Account settings

`/settings` (alias `/profile`) shows your identity status, sign-in/sign-out
actions, notification controls and session lifetime. Use `/settings signout` to
end your session explicitly. Tab offers sign-out inside settings; `/sig` + Tab
continues to complete `/signin` directly. The old `/signout` command remains a
compatibility alias without appearing in top-level completion suggestions.

## Visual guide and popup permissions

Open the [LAN42 command cheat sheet](quick-guide.html) in your browser for a
searchable, printable guide with copy buttons. `/help` keeps the terminal guide
and asks whether to open this HTML version. The page is self-contained: no
external fonts, scripts, analytics or network requests.

Browser categories inherit the global browser permission by default. On the
first browser request, one approval covers inherited browser pages for the
current LAN42 session, including app-opened game/photo-tool windows. It does not
permanently save approval. Explicit category `ask`/`deny` settings still apply;
notifications and new game terminals have separate permissions. **Enter means No.** Type `y` then Enter to allow once.
After a successful launch, a separate **Always allow? [y/N]** question lets you
save that category for your local login. Enter there keeps browser approval for this session only (other categories remain allow-once).
If help is always allowed, `/help` immediately opens the visual guide without
another prompt. Your existing input is preserved while a permission question is
shown; it is not treated as a yes. Remote events cannot grant permission.

```text
/settings permissions
/settings permissions browser allow
/settings permissions help allow
/settings permissions forknite ask
/settings permissions notifications deny
/settings permissions all ask
```

Categories: `browser` (global), `help`, `forknite`, `profiles`, `signin`, `tools`, `photos`,
`notifications`, `terminals`, and `search`. Modes: `ask`, `allow` (always), `deny`, and `inherit` (remove an override).
Browser actions inherit the global `browser` setting unless their category has
an explicit override. A global `browser deny` blocks all browser actions even
when a child category was previously allowed. Notifications and game terminals
are separate. For example, set `browser allow` and `profiles ask` to open other
browser pages immediately while still asking before profile tabs. Set
`profiles inherit` to remove that exception. To reset older category settings
and then allow all browser actions, use `all inherit` followed by `browser allow`.

These settings are private to the current local login and are re-read before an
action. `/notify off` mutes ordinary notifications; `/notify all off` silences
all channels, including host status and approved broadcasts. An explicit
`/settings permissions notifications deny` also blocks important desktop alerts.
Queued notifications stay in terminal history; the popup queue keeps only the
latest waiting notice to avoid a flood of permission questions.

## Batch popup setup

For faster popup setup, use `/setup` or `/allow batch` to choose each category
with y/n. `/allow all` lists every category and asks once before allowing them
all permanently; `all` during batch setup also grants the full list. Categories
cover browser pages, help, FORKNITE, profiles, sign-in, tools, photos,
notifications and terminals. No for the general browser fallback keeps asking;
No for a specific category blocks it. `/cancel` stops the batch, keeping choices
already saved. `/settings permissions all ask` resets the policies. File receives,
group joins, announcement approval, sound and system-volume permission remain
separate decisions. You can invoke setup while another popup prompt is waiting.


## Automatic login and closing the sign-in tab

```text
/settings autologin saved
/settings autologin on
/settings autologin off
/settings signin-close on
/settings signin-close off
```

Automatic login is **off by default**. `saved` attempts to reuse a valid LAN42
session when HQ connects, without ever opening a browser. `on` tries the same
reuse first, then requests normal browser authorization when no session can be
reused. Browser sign-in still obeys the inherited browser/`signin` permissions.
`off` leaves login manual. `/signin` also checks for a reusable session before
requesting a browser. Explicit sign-out pauses automatic login for the rest of
that app process, so logging out does not immediately log you back in.

The client validates a saved session with the pinned TLS broker before joining.
This does not read Chrome cookies or store new 42 credentials. LAN42 sessions
still expire after one hour and are invalidated if the broker restarts; there
is no automatic extension of their lifetime. These local preferences live in
private `login-settings.json` alongside the existing LAN42 configuration.

`signin-close` defaults to on. After OAuth returns, the local completion page
tries to close only itself. Browser rules may reject `window.close()` for tabs
opened through an external application; a manual-close message then remains.
The page says to check LAN42 for the final result because exchanging the
returned authorization code can still fail. Turning this setting off leaves
the completion tab open.

For reliable Chrome tab closing, reload version 1.2 of the optional
[browser helper](../browser-tools/avatar-saver/README.md). Its completion-page
script runs only at `http://localhost:31415/signin-complete` and requests closing
only when the local callback explicitly opted in. The background worker closes
that sending tab ID; it never lists or reads other tabs. Without the extension,
the normal best-effort page behaviour is retained.

## Local command history, shell and output volume

Up/Down recalls submitted commands and chat in the input field, restoring an
unfinished draft when you return past the newest entry. History is private to
this computer (last 200 entries); prompt answers are excluded. Game arrow controls
still apply while actively playing.

Type `!COMMAND` to run a local shell command, for example `!pwd` or
`!adjust_volume 35`. LAN42 hands over the terminal, then Enter returns to the app.
Only your typed input executes commands; server messages cannot execute them.

`/volume` (alias `/adjust_volume`) toggles desktop output between 0 and 30 percent.
`/volume 0` through `/volume 100` sets a level explicitly. The Zsh shell helper is
`adjust_volume [0–100]`, available after sourcing `useful-scripts/campus.zsh`.
The controls use the same output device as the GNOME/macOS slider (PulseAudio,
PipeWire or macOS); Bluetooth/device-specific volume remains up to that device.

Sound-enabled `/uwu`, received pokes, due alarms/timers and automatic calls check system output.
If muted/zero, they ask before raising it to 30 percent. A second confirmation
can remember permission to do this automatically on this device. This remains
separate from permission to play the koel sound. Manage it with
`/settings audio-auto-on on|off`. `/volume` itself applies your explicit request
without a permission prompt.

`/settings audio-startup-volume on` separately opts this device into setting
system output to 30 percent when a LAN42 HQ window starts, if it is at another
level. Game windows do not change it. Use `off` to stop this startup adjustment.

Press **F3** in HQ to open or focus the separate campus-clusters tmux window, using the same sign-in and local-operator checks as `/clusters`. In that window, `r` or Enter refreshes from the host; `/c1` and `/c2` select one cluster. The snapshot age remains visible while you browse.
`/settings clusters-auto-open on|off` separately controls whether HQ opens that
window at launch. Enabling it explicitly approves this one startup window; it
does not grant general game or tool terminal permission, and explicit terminal
denial still applies. HQ waits for sign-in/operator access and retries failed
launches. The account-scoped choice follows a linked portable preferences folder;
separate unlinked installations keep their own saved copies.

Local uwu toasts have their own `/notify uwu on|off` channel (default on), separate
from received pokes. Automatic uwu stays account-scoped across HQ/game windows;
HQ alone schedules calls and gives one consent-controlled startup chirp. The
saved clusters auto-open choice waits for access and retries failed launches.


## Portable settings on Mac and campus

Friends, named lists and account preferences can live in a dedicated folder in
**your own private repository**. Keep the entire authentication/config directory
outside Git. The portable folder accepts only the named preference JSON files;
credentials, sessions, keys, host grants, device-only consent and command history
stay local. Sign in separately on each computer with the same Intra login.

Inside LAN42, quote paths containing spaces:

```text
/settings storage "/path/to/private-repo/42/lan42"
/settings import "/path/to/portable-folder"
/settings export "/path/to/portable-folder"
```

Different existing files stop the operation and ask you to choose `combine` or
`overwrite`. Repeat the command with that final word:

```text
/settings storage "/path/to/private-repo/42/lan42" combine
/settings import "/path/to/incoming-folder" combine
/settings import "/path/to/incoming-folder" overwrite
```

`combine` (append) recursively unions friends, list members and other collections,
without duplicates. Your current local scalar choices win when values disagree
(for example, the relationship for an existing friend or a notification switch).
When exporting, existing destination scalar choices win. Combining does not infer
deletions; choose overwrite to adopt an incoming removal. Tracking limits still
apply; an oversized union stops before changing any files.

`overwrite` uses the incoming folder's version for matching files; files absent
from that folder remain. With `storage`, the selected folder is incoming and its
matching files win over local versions. Replaced files get private local backups
under `${XDG_STATE_HOME:-~/.local/state}/42sg-campus-lan/backups/`.

`storage` creates a **directory symlink**, so atomic JSON saves continue to write
into the private checkout. A symlink saves locally; commit and push that checkout
to back it up remotely. Stop/reopen other LAN42 windows after importing or changing
storage so cached preferences reload. The CLI works while LAN42 is stopped:

```sh
cd /path/to/42sg-campus-lan
python3 -m campus_lan.preferences storage /path/to/private-repo/42/lan42
python3 -m campus_lan.preferences import /path/to/incoming-folder --mode combine
```

The CLI asks interactively on conflict. Noninteractive invocations require an
explicit `--mode combine` or `--mode overwrite` when files differ; EOF/cancel
keeps conflicting preferences unchanged.

Before pulling a checkout containing active settings, commit your local settings.
Use a normal Git merge rather than rebase when both computers have commits. For
JSON merge conflicts in the portable folder, choose through settings or CLI:

```text
/settings resolve "/path/to/private-repo/42/lan42" combine
```

```sh
python3 -m campus_lan.preferences resolve /path/to/private-repo/42/lan42 --mode combine
```

This combines Git's local and incoming JSON versions and stages only those
preference files. `overwrite` selects the incoming Git version. Review and commit
the merge, then push it yourself. Delete/modify conflicts require manual review;
unrelated conflicts remain untouched. Conflict markers are never loaded as valid
preferences. This explicit `/settings` flow does not run Git operations at startup.

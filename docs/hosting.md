# Hosting, updates and maintenance

[← LAN42](../README.md) · [All guides](README.md)

- [Access, API scope and trusted hosts](#access-api-scope-and-trusted-hosts)
- [Announcements and the API host coming online](#announcements-and-the-api-host-coming-online)
- [Testing on a Mac or another LAN](#testing-on-a-mac-or-another-lan)
- [Updates and troubleshooting](#updates-and-troubleshooting)
- [Update the whole LAN42 package](#update-the-whole-lan42-package)
- [Local API-owner avatar tools](#local-api-owner-avatar-tools)
- [Recover a terminal or restart local clients](#recover-a-terminal-or-restart-local-clients)
- [What's in the repo?](#whats-in-the-repo)

## Access, API scope and trusted hosts

Approved on-campus host startup also starts/resumes the [42 Singapore KoelDrop
flock](file-sharing.md#the-host-started-42-singapore-flock). Its local service
identity is independent of owner OAuth and cannot be used as a student bearer
login. No startup scripts erase existing folders; retained copies survive restart.

**Campus LAN features, with read-only Singapore-scoped API tools available to the
API owner offsite.** This is the owner's application-form promise, not a narrower
permission automatically enforced by the upstream student API credential.

Guests may host games and chat, but cannot read API-backed data or trigger API
calls through the guest lobby. OAuth-verified SG members receive selected seats,
tracking and game-profile views. hnah (numeric 42 ID 234449) is initially the only
admin and API operator. API operators may explicitly cache, export and download
SG-scoped data; ordinary students cannot trigger bulk directory refreshes.
Admins, API operators and approved service machines are independent allowlists.
A game host does not become an official authentication/API host.

**Existing school API host upgrade:** the next normal LAN42 start after updating
migrates hnah’s existing managed campus host automatically. `dailylogin` delegates
to LAN42 after its update; no manual enrollment command or temporary script is
needed for that legacy host. Existing policies and revocations are never replaced.
New hosts still need explicit approval/enrollment. This Mac's operator can use local
`/clusters` and tracking offsite without opening internet ports. Offsite defaults
are localhost; existing listeners change binding only on restart. KoelDrop keeps
its separate physical-campus checks, consent and pinned transport. Tailscale is
not installed or treated as campus-presence proof.

See [access policy, role management and enrollment](access-policy.md) for
permissions, adding/revoking admins/operators/hosts, API limits and private export
locations. Modifying a downloaded client does not override server permissions;
stealing the upstream credential can bypass application policy and requires
credential revocation. No API credential or private policy file belongs in Git.

## Announcements and the API host coming online

`/announce TEXT` and `/broadcast TEXT` are aliases. The trusted API host/admin
publishes directly after a local confirmation and an anti-spam warning; recipients
see `hnah (host)` (or the configured owner's actual Intra login). A signed-in
student sees a confirmation to **ask the host**; the host gets a desktop request
with **Approve / Reject** buttons. Approval makes the host server publish the
original text quoting that student's verified Intra login. Rejection/expiry is
reported back to the requester. Desktop action support varies; the host can also
use `/announce approve REQUEST_ID` or `/announce reject REQUEST_ID` in HQ.

This is server-side privilege control. A guest called `hnah`, a client-provided
`host=true`, or another student's local guest server cannot grant approval.
Numeric admin IDs in the private access policy control moderation. A configured display login grants no permissions; a local moderation capability also requires an enrolled admin.
Ordinary chat mute does not hide trusted approved announcements. The
announcements channel, all-off override and explicit popup denial are respected;
OS display/notification availability still applies. Each window gets terminal history and
each local computer gets one desktop alert, avoiding duplicate game-window popups.
Announcement text never executes commands, installs an update, or changes trust.

Without the API host, guest nodes still run discovery/chat/games on their own.
They are **guest nodes**, not replacement API administrators. No app-wide 404
occurs: sign-in/API-backed operations wait for the trusted service. Existing
public certificate trust is required before a client can recognize that host;
see [one-time trust and owner setup](sign-in.md).

On-campus guest HQs explain this at startup: use `/signin` and `/clusters` when
the approved host is available. The initial offline state is shown too, rather
than silently waiting. Missing/invalid public trust gets a setup message; LAN42
cannot securely recognize or watch an arriving host until that trust is installed.

When the trusted host comes online, waiting clients show its login/seat and an
invitation to `/signin` for `/clusters`. Arrival desktop alerts respect the
recipient’s notification settings and are deduplicated per computer for that host
session. No automatic OAuth browser or unsolicited sound is triggered. A valid
saved session may resume according to the existing auto-join setting; guest HQs
and ongoing games are preserved.

While offline, clients retry the pinned endpoint and opt-in public seat locator
every **120 seconds**, configurable within **60–300 seconds**. This uses LAN42's
own endpoint/cache, not a new 42 API call per poll. On recovery they report the
API host's login and current seat, link to its ordinary guest node, and reuse a
valid saved sign-in session for the secure lobby. An expired/missing session still
needs `/signin`; no OAuth browser is opened automatically by this recovery path.
Other students' local servers and ongoing guest rooms are not overwritten.

```
/announce status
/announce refresh
/settings host-poll 120
/settings host-discovery on
/settings auto-host-join on
```

Public-seat discovery needs the owner's existing opt-in locator publication.
Disabling host discovery stops seat relocation/automatic guest linking; trusted
announcements from the configured endpoint remain available. Approved messages
are cached in host memory for 15 minutes (latest ten); pending requests expire in
five minutes. A host-service restart resets that queue and may require resubmission.

After your first successful `/signin`, LAN42 asks whether to sign in automatically
next time. Yes reuses a valid saved session and asks before opening 42 when it
expires; No keeps automatic login off. The choice is remembered on this device.
Change it later with `/settings autologin off|saved|on`.

## Testing on a Mac or another LAN

Campus seat shortcuts are optional. You can connect using a private IPv4 address
(such as `192.168.1.50` or `10.0.0.20`), a hostname resolving to one, or localhost.
Choose any available TCP port with `--port`; no campus-specific port is required.
Public internet IPs are currently rejected. Outside campus, seats show as unknown.

See [the local test walkthrough](local-testing.md) for exact commands to run
two or three players in separate terminals on one Mac or Ubuntu computer.

## Updates and troubleshooting

The launcher uses `git pull --ff-only`. If you have local edits, it skips the
update; if pulling fails, it warns you and runs the existing copy. Set
`LAN42_NO_UPDATE=1` to skip updating deliberately.

**Updating?** Use the current beta on all devices (protocol 5); quit existing apps and restart. API hosts must complete the explicit enrollment below.
The legacy `host` and `join` startup commands remain as compatibility aliases.
Normal startup is simply `lan42`, with `/join` inside HQ.

**Moving from v0.1?** The old version left a
background server running after you quit. Check its PID and process, stop that
old server, then reopen the app. Updating the source doesn't kill existing
servers automatically.

Logs and PID files are in `~/.local/state/42sg-campus-lan/`, or under
`$XDG_STATE_HOME/42sg-campus-lan` if configured. For the default port, look for
`server-31415.log` and `server-31415.pid`.

To test multiple nodes on one computer, use `lan42 --port 32101 --guest-name hnah`
and `lan42 --port 32102 --guest-name thtay` in separate terminals, then type
`/join 127.0.0.1 32101` in the second HQ. An explicitly started `./lan42.sh server` runs in
the foreground until you stop it.

With five nodes, the mesh makes about **20 small exchanges every five seconds
across the group**, plus chat and game traffic. Each node is capped at 16 peers.
Campus network rules and client isolation still determine whether connections
are allowed and can reach each other; this needs testing on campus.

The guest mesh uses plaintext TCP; the separate authenticated lobby requires
pinned TLS. Neither keeps a persistent chat or account database. It has no internet discovery or NAT traversal. Games share their
hosting node's process and port. macOS can run it, with terminal notifications
as the fallback when Linux `notify-send` isn't available.

## Update the whole LAN42 package

`/update` (alias `/upgrade`) is LAN42's global package update: it fast-forwards
this checkout and notifies all updated local HQ/game clients, managed lobby
nodes and supervised FORKNITE servers to reload. Active local matches end.
Each computer updates its own checkout; no command restarts a friend's machine.
`/restart` restarts only the current terminal without pulling. Local changes skip
the pull and preserve your work; failed pulls retain the installed code. No reset,
stash, commit or push is performed. The trusted authentication/room service also reloads on a successful package update;
its in-memory sign-ins expire, so use `/signin` again after an upgrade.

Old processes need one manual restart to gain the update watcher. After that,
all bundled minigames share the same LAN42 package update mechanism. Browser
clients reconnect after the FORKNITE server reloads and reclaim their slots.

## Local API-owner avatar tools

`/admin` opens the master computer's private avatar importer in the normal local
browser. It supports profile-link lookup, a bounded ordinary download attempt,
and manual file selection/drop after opening the photo in the user's browser.
Nothing reads or exports Chrome cookies/profiles. Cache files are kept outside
Git at `~/.cache/42sg-campus-lan/avatars` with private permissions. Joined players
receive same-origin image responses from the game server; see the game README
for access control, HTTP transport limits, cache lifetime and import commands.

## Recover a terminal or restart local clients

Terminal display recovery: Ctrl-L forces a full LAN42 redraw. Resizing a tmux
pane also redraws the screen; API queue notices stay in the chat log.

`lan42_restart` restarts LAN42 tmux client panes by injecting `/restart` into the
app. It skips shells, servers and unrelated Python programs, and clears unfinished
app input. `lan42_restart --check` lists matching panes without sending anything.
It works on Linux and macOS. Source the installed shell helpers or run
`useful-scripts/lan42_restart` directly. It does not restart the API host service.

## What's in the repo?

| Directory | Contents |
| --- | --- |
| [`campus_lan/`](../campus_lan/) | Terminal client, servers, game rules and optional API adapter. |
| [`minigames/`](../minigames/) | Game directory and guide. |
| [`useful-scripts/`](../useful-scripts/) | Zsh helpers, installer and setup guide. |
| [`docs/`]() | Protocol notes and campus deployment task. |
| [`tests/`](../tests/) | Game rules, networking, server lifecycle and helper installation checks. |

To run the tests:

```sh
python3 -m unittest discover -s tests -v
```

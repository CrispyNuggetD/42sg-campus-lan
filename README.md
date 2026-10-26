# LAN42 BETA

Beta entry **2.0.0-beta.1** · Beta since Tuesday **27 October 2026, 00:48 SGT**.

Alpha testing: dthoo and [whatisthisbuffoonery](https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html). Thank you for testing LAN42 before beta.

Use `/changelog` for full server release history. See [release policy](docs/versioning.md) and [system evidence](docs/runtime-environment.md).

# Ryker's 42SG Campus LAN Server

**[Open the visual guide & quick start ↗](https://CrispyNuggetD.github.io/42sg-campus-lan/)** · [Source repository](https://github.com/CrispyNuggetD/42sg-campus-lan)

Student-built terminal LAN lobby for 42 Singapore: discover online peers and
campus seats via read-only 42 API data, chat, invite players, and coordinate
locally hosted minigames and useful scripts.

Hi, I’m **Christopher Hui-Kang Nah** (**hnah** on Intra), a student at **42 Singapore**. Questions, ideas, or just saying hi? Find me on the **global 42 Slack**, or [here on GitHub](https://github.com/CrispyNuggetD).

**Source, issues and contributions:** https://github.com/CrispyNuggetD/42sg-campus-lan

In the terminal, `/about` shows this purpose and source link. `/about repo` or
`/repo` requests opening the public repository using your browser permissions.
`/help` opens the same [visual guide](docs/quick-guide.html) used by the website; `/koel help` describes file sharing.

## LAN42 in your daily workspace

<!-- shell-installer-features:start -->
- `lan42` / `lan42_window`: BETA campus HQ in tmux; startup version/date and `/changelog`.
- `/who` / `/join`: discover peers, link campus seats and chat across lobbies.
- `/map` / `/track`: read-only campus seating maps and your own local people lists.
- `/dm` / `/uwu LOGIN`: messages and sound pokes; `/volume` for audio; `/koel` for approved group file sharing.
- `/games`: Tetris, Bluff, Hex Wars and FORKNITE; Up/Down history and !COMMAND for the local shell.
- `/signin`: SG API views; guests keep chat/games; legacy owner-host approval migrates on startup.
- `/announce` / `/broadcast`: API host broadcasts; signed-in students request approval, credited to their Intra login.
- Pinned host discovery: keep guest nodes running offline, then discover and reconnect when the API host returns.
<!-- shell-installer-features:end -->

The public dailylogin shell installer reads this block directly from this README
when recommending LAN42. Maintainers: update it when commands or availability
change; see [the contribution workflow](AGENTS.md).

## Available features

| Area | State in this checkout |
| --- | --- |
| Guest peer discovery, chat and rooms | Implemented |
| Verified 42 sign-in and TLS lobby | Implemented; requires owner setup |
| Read-only campus maps and local relationships/lists | Implemented |
| Direct messages, local notifications and browser consent | Implemented |
| API-host moderated announcements and online discovery | Implemented; initial public host trust required |
| Tetris, Bluff, Hex Wars and FORKNITE | Implemented; game requirements apply |
| KoelDrop: session-scoped LAN file sharing | Available through the verified host; explicit group/folder consent |

**KoelDrop — the uwu bird, but it brings files.** A little campus file courier
inside LAN42: files in your nest, only if you say yes. Its scope is small,
invited groups on campus. `/koel status` (also `/files status`) is
available without an experimental flag. Create/join a group to start its dedicated
folder uploads; incoming files require approval. See the [design, boundaries and test plan](docs/file-sharing-design.md).

The public repository contains code, tests, diagrams and instructions. Private
API credentials, certificate keys, sessions, campus directory exports, photos,
file contents and activity databases are not public project assets.

The current server version/date are shown at startup and in `/changelog`. Start as a guest for chat/games, or use `/signin` to enter the approved TLS host with verified **42 Singapore membership**. [Owner setup and student sign-in](docs/sign-in.md).

`/uwu auto` (or `/uwu on`) enables local koel calls at a fresh random interval
of 10–15 minutes. It asks for sound permission if needed. `/uwu off` stops
the timer; disabling koel sound also stops it at the next scheduled call.
The timer applies only to this window and stops when it closes; it never pokes
other students. Repeating the command does not reset an active timer.

`/uwu` plays one short koel call (0.85 seconds, no repeated calls) on your own computer for the running joke
or an audio test. If sound is off, it asks first; Enter keeps it off. `a` offers
always-on with the existing second confirmation. Change it with
`/settings koel-sound on|off|always`. `/uwu LOGIN` sends a private poke to a
connected person. Their notification permission and their own sound choice apply;
the toast closes after two seconds and is not resident in notification history.
Only a poke message crosses the network; each client plays its own local asset.
Pokes share the two-second direct-message rate limit.

## Visual guide and popup permissions

Open the [LAN42 command cheat sheet](docs/quick-guide.html) in your browser for a
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
`notifications`, and `terminals`. Modes: `ask`, `allow` (always), `deny`, and `inherit` (remove an override).
Browser actions inherit the global `browser` setting unless their category has
an explicit override. A global `browser deny` blocks all browser actions even
when a child category was previously allowed. Notifications and game terminals
are separate. For example, set `browser allow` and `profiles ask` to open other
browser pages immediately while still asking before profile tabs. Set
`profiles inherit` to remove that exception. To reset older category settings
and then allow all browser actions, use `all inherit` followed by `browser allow`.

These settings are private to the current local login and are re-read before an
action. `/notify off` still mutes desktop notices even when permission is allowed.
Queued notifications stay in terminal history; the popup queue keeps only the
latest waiting notice to avoid a flood of permission questions.

FORKNITE room creation itself can proceed while browser consent waits. Each
participant approves their own browser. Declining leaves the room available;
`/browser` requests opening it later. Missing photos request the host's local
photo tool rather than launching a browser from the room server. Tool panels
and photo-tab/save batches have separate permissions. The extension still needs
its normal one-time installation. LAN42 only opens requested new pages; these
permissions do not give it access to existing Chrome tabs, profiles or cookies.

## Get started

You'll need Git, tmux, Python 3.9 or newer with curses support, and a terminal at least
**76 columns × 28 rows**. LAN42 asks compatible terminals to grow to that size
when needed; terminals that do not support resize requests show a manual resize
message instead. There are no pip packages to install.

Install tmux with `sudo apt install tmux` on Ubuntu or `brew install tmux` on Mac.
`lan42` uses a separate tmux workspace for HQ, games and tools, even without the
larger dailylogin shell setup. Terminals default to maximized rather than OS
fullscreen; set `DAILY_TMUX_MAXIMIZE=FALSE` to disable maximizing.
`lan42_here` (or the direct `lan42.sh` launcher) runs in your current terminal.

Each person clones the repo into their Documents folder:

```sh
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
cd 42sg-campus-lan
sh setup.sh
```

Setup backs up your existing `.zshrc` and appends the LAN42 shell helper.
Open a new zsh terminal, then start the lobby at school with:

```sh
lan42
```

To use it immediately in the current terminal, reload your shell configuration
first:

```sh
source "${ZDOTDIR:-$HOME}/.zshrc"
lan42
```

If you skipped the zsh helper with `sh setup.sh --no-zsh`, use the launcher
directly instead:

```sh
~/Documents/42sg-campus-lan/lan42.sh
```

The launcher checks for updates and prints the version, commit and date before
starting. Everything runs from this clone; setup needs no sudo and installs
nothing in `/bin` or `~/.local/bin`.

## Find your friends

Everyone starts the same way: run `lan42` (or `lan42.sh`). Your HQ starts on
TCP **31415** and shows **1 online: you** once it connects to its local node.
There is no choice between hosting and joining a lobby.

In HQ, type `/join` for seat questions, `/join c1r2s3` for a known seat, or
`/join 192.168.1.50 31415` for a custom address and port. That links the nodes
and shares known peers while your HQ stays in its own terminal.

The campus address mapping is:

| Seat | IP address |
| --- | --- |
| Cluster 1, row 2, seat 3 (`c1r2s3`) | `10.11.2.3` |
| Cluster 2, row 4, seat 9 (`c2r4s9`) | `10.12.4.9` |

In general, cluster 1 uses `10.11.row.seat` and cluster 2 uses `10.12.row.seat`.
You can check [the Intra cluster map](https://meta.intra.42.fr/clusters) to see
where people are sitting. You'll need to sign in to Intra to view it.

Joining tries that one address. Your friend must have the app running, and the
network must allow the connection. You can also enter an IP address directly,
such as `/join 10.11.2.3` inside HQ.

### How the lobbies stay connected

Each app runs its own local server, or **node**. Connecting to one friend
exchanges the addresses of other known nodes. From there, the nodes check in
with each other every **5 seconds**, sharing who's online, chat, rooms and
invitations. There's no central server or campus-wide scan: you need one live
friend's address to join an existing group.

When someone comes online, you can get a notification like:

> thtay came online! Cluster 1, row 2, seat 3. Go say hi! [Guest]

Seats come from the LAN address or a matching cluster hostname. This does not
poll the 42 API every five seconds. If a seat can't be determined, it is shown
as unknown.

The first node is only the initial meeting point. After discovery, nodes talk
to one another directly. When the first quits, the remaining nodes keep the
shared lobby alive without electing a replacement. When everyone quits, it ends.
A crashed or unreachable peer drops out after roughly 16 seconds.

**HQ and games have separate terminal windows.** HQ has a cyan banner; game
windows have a magenta banner naming the game and room. Window/tab titles also
show `HQ LOBBY` or, for example, `GAME | TETRIS | ROOM 1`. This uses standard
terminal title sequences; terminal settings may override the displayed title.
 `/host tetris` or `/host bluff
free` opens a game window on your node; `/join NUMBER` opens a game on the peer
you last linked. `/home` resets that game target to your own node. Closing a
game window leaves HQ and your presence running. Closing HQ stops your node.

Each game still runs on one node. If that node quits, its games end; other nodes
and their games continue. Migrating a running game's state is not implemented.
Keep HQ open while playing. One guest can have one HQ connection and one game
connection on each server, without appearing twice in the mesh roster.

## Testing on a Mac or another LAN

Campus seat shortcuts are optional. You can connect using a private IPv4 address
(such as `192.168.1.50` or `10.0.0.20`), a hostname resolving to one, or localhost.
Choose any available TCP port with `--port`; no campus-specific port is required.
Public internet IPs are currently rejected. Outside campus, seats show as unknown.

See [the local test walkthrough](docs/local-testing.md) for exact commands to run
two or three players in separate terminals on one Mac or Ubuntu computer.

## The lobby: who's online?

The main screen shows a numbered roster grouped into **Cluster 1**, **Cluster 2**
and **off campus / seat unknown**. Guests get consistent colours, while the
Guest label stays visible: colour isn't verification. Presence refreshes about
every five seconds. The list covers connected LAN42 users, not everyone on Intra.

Press **Tab** to switch between the roster and an ASCII seat map. `/map 1` and
`/map 2` select a cluster; `/roster` or `/who` returns to the list. The maps follow
the supplied floor plans, with higher rows at the top and staggered even/odd
seat boxes. Coloured boxes refer to the numbered roster below the map. Unmarked
desks don't prove vacancy; they simply have no reported LAN42 peer.

Use `/next` and `/prev` to page through longer rosters or maps in a small terminal.
Chat and invitations stay in their own panel below. During a game, `/lobby`
opens the roster without leaving the room, and `/game` returns to play. Tab
retains its play/chat function when you're viewing Tetris.

## Chat, invitations and commands

Type a message and press **Enter** to chat. **Page Up/Down** scrolls through the
last 500 event lines. Text input currently supports ASCII.

| Command | What it does |
| --- | --- |
| `/who` or `/lobby` | Open the grouped online roster. |
| `/map 1` or `/map 2` | Show a cluster seat map. |
| `/next` or `/prev` | Page through the lobby panel. |
| `/game` | Return from the lobby panel to your game. |
| `/rooms` | Show game rooms. |
| `/games` | List the available games. |
| `/join` | Ask for a friend's cluster, row and seat. |
| `/connect c1r2s3` | Alias for linking a peer; HQ stays local. |
| `/home` | Select your own node for the next game join. |
| `/host hexwars` | Open the C bot arena; `/bot` opens its upload menu. |
| `/host tetris` | Open a Tetris terminal and advertise its room. |
| `/host bluff free` | Open a bluff terminal without a prompt. |
| `/host bluff prompt` | Open a bluff terminal with a random prompt. |
| `/join NUMBER` | Open a game terminal on the last linked peer. |
| `/start` | Start your room's game, or play another round. |
| `/leave` | Leave the game room. |
| `/invite` | Ask for a friend's seat and invite their running lobby to your room. |
| `/invite-room` | Share your room invitation across the connected nodes. |
| `/notify off` | Mute your desktop notifications. |
| `/signin` | Open 42 in your browser, then join the configured secure lobby. |
| `/authhost SEAT` | Verify the trusted sign-in host at its new seat. |
| `/settings signout` | Revoke this device's session and return to guest HQ. |
| `/quit` | Close the app and stop your node. |

To invite someone, first create or join a room. They receive its server address
and room number, then use `/connect IP PORT` followed by `/join NUMBER` to join.
Invitations don't move anyone automatically.

Lobby windows also notify for each chat message from another sender, including
messages received across the mesh. Your own messages and game windows do not
produce chat notifications. Use `/notify off` to mute them.

Desktop notifications use `notify-send` on the recipient's computer, so they
need their client open. If notifications aren't available, the terminal beeps
and the message stays in the log. Invitations have a 10-second cooldown; those
sent across the mesh arrive on the next exchange.

## The games

### Hex Wars: code your conquest

Upload your own **C bot** and compete with 2–6 armies on a live 61-cell hex map.
Program expansion, reinforcement and attacks; allocate nine attribute points
between growth, attack and armor. Every bot sees the same board each turn,
and the host resolves all moves simultaneously.

From HQ run `/host hexwars`. In its game window, `/bot` opens a menu to upload
a C file, create a starter, choose a demo bot, or read the API guide. Friends
join your room and submit their bots; the host runs `/start`. Try it solo with
`/bot demo`, `/practice`, `/start`. No compiler is required for demo bots.

Custom C bots require Clang + LLVM wasm-ld on the submitting computer and
Node.js on the host. Bots execute as bounded, import-free WebAssembly. The
guest mesh remains unverified; `/signin` joins the separate verified TLS lobby.

Read the **[C API, structs, exact rules and setup guide](minigames/hexwars/README.md)**.
Use the [header](minigames/hexwars/hexwars.h) and
[example strategies](minigames/hexwars/examples/) to build your player.

### Co-op Tetris

Everyone controls **the same falling piece on the same board**. Coordinate your
moves—or enjoy the chaos. Use the arrow keys or WASD to move and rotate, and
**Space** to hard-drop. **Tab** switches between playing and typing chat or
commands.

Clearing 1, 2, 3 or 4 lines scores 100, 300, 500 or 800 points. After game over,
the room host can type `/start` to try again.

### Who Said That?

For **two or more players**, though three or more makes guessing much more fun.
With two, recognising your own message gives away the other author.
Write a message that your friends won't recognise as
yours, using `/answer YOUR TEXT`.

**Free mode** lets you write anything. **Prompt mode** gives everyone a random
prompt and asks them to respond as the current leader. The leader rotates each
round, and prompts are bundled with the game—no external service is needed.

Once everyone submits, or after 45 seconds, the messages are shuffled and all
appear under the leader's name. Guess who really wrote each numbered message:

```text
/vote hnah thtay dthoo
```

That guesses hnah for message 1, thtay for message 2 and dthoo for message 3.
Your own message is ignored when scoring your guesses. You earn **2 points per
correct guess** and **1 point for each opponent your message fools**.

Voting lasts up to 45 seconds, then the real authors and scores are revealed.
The host can `/start` another round. Scores reset each round. A round is
cancelled if the leader doesn't submit or fewer than two answers arrive.

## Zsh commands and daily login

`sh setup.sh` includes the zsh helpers by default. It backs up your `.zshrc` and
**appends** a guarded source block pointing to this clone. It never truncates or
rewrites your existing settings. Rerunning setup skips an identical block; if
you move the clone, a new block is appended and the old one is left alone.

To skip shell setup:

```sh
sh setup.sh --no-zsh
```

After setup, open a new zsh terminal or run `source "${ZDOTDIR:-$HOME}/.zshrc"`.
You can then use:

- `lan42` to open the lobby in your current terminal. It passes arguments through,
  so `lan42 join c1r2s3` works too.
- `dailylogin` to update the repo, reload its helpers and open LAN42 in another
  terminal window, leaving your current shell free.
- `lan42_window` to open that separate window directly.

`dailylogin` is a helper from this project, adapted from
[Christopher's SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).
If you already have your own `dailylogin`, it is preserved; use
`lan42_dailylogin` for this repo's version. Christopher's personal version also opens
LAN42 alongside his existing tasks.

Future Git pulls update the sourced helpers. To make `dailylogin` update without
opening a window, set `LAN42_OPEN_ON_LOGIN=0` before the source block in your
`.zshrc`. Sourcing the file alone never launches anything. If zsh isn't installed,
setup prepares the launcher and explains how to enable the helpers later.

See [the zsh helper guide](useful-scripts/README.md) for manual setup, project
paths, compile/run helpers and optional Documents syncing.

## Guest names and 42 sign-in

The guest mesh uses unverified OS usernames. A guest node cannot assign verified
status. `/signin` in your local HQ opens 42's website; after browser consent,
the trusted host verifies `/v2/me` and moves HQ into its TLS-protected lobby.
Your canonical 42 login appears in green as **42 Verified**. The verified lobby
hosts its own games and does not forward identities or messages to the guest mesh.

Students never provide passwords or personal API credentials to LAN42. Only the
trusted host holds the app secret. Authentication uses HTTPS 31416, the secure
lobby uses TLS 31417, and the registered localhost:31415 callback stays on each
student's own machine. Students pin the owner's public certificate before use. The owner's `dailylogin`
starts the sign-in service on their current campus seat; after the owner moves,
students can use `/authhost SEAT` to verify and select its new address without
changing their certificate pin.

Sessions expire after one hour. `/signout` revokes the session across your HQ
and game windows and returns to guests. Read the **[setup, privacy, and security
guide](docs/sign-in.md)** for importing the existing app, distributing public
trust information, and handling secret rotation.

<details>
<summary>Optional 42 API lookup</summary>

The API adapter is optional and doesn't block startup. A trusted host can set
`INTRA_CLIENT_ID` and `INTRA_CLIENT_SECRET` in its environment. The adapter uses
client credentials and `GET /v2/users/:login` to look up connected guest names
every two minutes.

The current mesh uses address-based seats. The API adapter remains a separate
fallback for legacy local clients; it doesn't list the whole campus or verify
that someone owns the username they supplied. Keep the secret on the trusted
host, out of Git and other clients.

Live API permissions and campus data still need testing. See
[42's getting-started guide](https://api.intra.42.fr/apidoc/guides/getting_started)
and [the user endpoint](https://api.intra.42.fr/apidoc/2.0/users/show.html).

</details>

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

## What's in the repo?

| Directory | Contents |
| --- | --- |
| [`campus_lan/`](campus_lan/) | Terminal client, servers, game rules and optional API adapter. |
| [`minigames/`](minigames/) | Game directory and guide. |
| [`useful-scripts/`](useful-scripts/) | Zsh helpers, installer and setup guide. |
| [`docs/`](docs/) | Protocol notes and campus deployment task. |
| [`tests/`](tests/) | Game rules, networking, server lifecycle and helper installation checks. |

To run the tests:

```sh
python3 -m unittest discover -s tests -v
```

### Update the whole LAN42 package

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

### FORKNITE (bundled browser minigame)

Use `/game forknite` in HQ and `/join ROOM_NUMBER`, exactly like the other games.
The room server launches the bundled Node wrapper and opens each participant's
browser only after that participant's local permission allows it. Their philosopher slot, name, photo (when available) and
verified/guest status come from their existing LAN42 connection. Sign in once
with `/signin` in LAN42; FORKNITE has no separate OAuth login or URL handoff command.
Guests retain their LAN42 pseudonym and a silly avatar. The host uses `/start` in
the game terminal. `/leave` releases the slot, invalidates that member's browser
session and closes the wrapper when the last member leaves. Opening a bare browser
URL is guest spectator mode, not proof of a LAN42 identity.

The room host machine needs Node.js 12+ and its compiled philo binary at
`minigames/forknite/philo` (local symlink), `LAN42_PHILO_BINARY`, or on PATH.
The C project is untouched. The LAN42 room server owns process lifecycle,
match logs, and automatic shutdown/reload. Public browser ports must be reachable
from participants on the LAN; each room advertises its own port.

Room identity goes through a single-use 60-second browser ticket delivered only
to that player's existing LAN42 connection. Node's control channel is loopback-only
and requires a random per-room secret. No 42 OAuth tokens, app secrets or LAN42
session credentials enter browser URLs. Browser sessions expire after an hour;
leaving the room revokes them immediately. Verified names cannot be claimed by
supplying a nickname. Guests may still visit the game directly and use free slots.
See [the game README](minigames/forknite/README.md) for developer pipe mode and logs.

### Game launcher and Tab completion

Use `/game tetris`, `/game bluff free`, `/game hexwars`, or `/game forknite`.
`/host` remains a compatibility alias. Bare `/game` still returns to the current
terminal game view. While typing a slash command, Tab completes commands, game
names, bluff modes and a few simple options. `/sig` + Tab completes `/signin` directly;
`/signout` is available when typed explicitly but is omitted from completion suggestions. Ambiguous matches expand their
common prefix and print choices. With no slash input, Tab keeps its existing
lobby-map / Tetris-control behavior.

FORKNITE can use `minigames/forknite/philo`, a machine-local executable or symlink
(ignored by Git), as its default native binary. `LAN42_PHILO_BINARY` overrides it;
otherwise the launcher tries that local path then `philo` on PATH. Explicit
`--exec` still works. On this workstation the symlink targets your existing
Philosophers executable, so rebuilding that executable updates what FORKNITE runs.

### Personal settings

`/settings` (alias `/profile`) shows your identity status, sign-in/sign-out
actions, notification controls and session lifetime. Use `/settings signout` to
end your session explicitly. Tab offers sign-out inside settings; `/sig` + Tab
continues to complete `/signin` directly. The old `/signout` command remains a
compatibility alias without appearing in top-level completion suggestions.

FORKNITE renders only joined players and explicitly requested `/sabo` stand-ins.
At match start, the native philosopher count is the seated-player count; no
synthetic diners are added. tmux game windows use `GAME-ROOM`, such as `forknite-1`.
Profile URLs come from 42; if its image CDN denies a fetch, the card explicitly
shows “42 photo unavailable” and keeps the silly fallback face.

### Local API-owner avatar tools

`/admin` opens the master computer's private avatar importer in the normal local
browser. It supports profile-link lookup, a bounded ordinary download attempt,
and manual file selection/drop after opening the photo in the user's browser.
Nothing reads or exports Chrome cookies/profiles. Cache files are kept outside
Git at `~/.cache/42sg-campus-lan/avatars` with private permissions. Joined players
receive same-origin image responses from the game server; see the game README
for access control, HTTP transport limits, cache lifetime and import commands.

`/clusters [1|2]` shows active Singapore campus API locations using the existing
ASCII floor plan (even seats above odd seats), including the snapshot timestamp.
Snapshots are fetched on demand, shared for 30 seconds, and are separate from
LAN42 peers shown by `/map` or `/roster`. This represents reported logged-in
computers, not everyone physically present. `/clusters` refreshes; `/next` and
`/prev` page through the map and numbered login roster. The API host needs private credentials and explicit host enrollment. Guest sockets cannot request these views; verified SG members and enrolled local API operators can. API reference:
https://api.intra.42.fr/apidoc/2.0/locations/index.html

`/profile thtay hnah` requests permission to open both Intra profiles in local browser tabs. `all` and
`cohort4` expand from the local private campus cache. Selections above ten tabs
show the count first; `/profile --open-many cohort4` explicitly opens a large
selection. Parsing validates every login and deduplicates names before opening
any tabs. Existing `/profile signin`/`signout` settings aliases remain available.

The campus map overlays connected LAN42 peers: verified peers use green, guests
keep their LAN42 name colour, and API-only students use white with an “API login”
label. Matching a guest name never grants verified status. API seats remain the
source of location information. Click a numbered login in the roster (or an
occupied map marker) to switch to its cluster and page and blink its seat.
`/locate LOGIN` provides the same action when terminal mouse reporting is not
available. `Shift` plus mouse can still be used for ordinary terminal selection.
Help/table rows stay together, with one blank line between separate messages,
room changes and presence notifications.

`/track dthoo thtay` saves a watch list privately on this computer, separately
for your local LAN42 login. `/track` lists it; `/untrack dthoo` or `/untrack all`
removes entries. Keep your HQ window running: it checks the shared campus API
snapshot immediately and then every five minutes. The watch list is never sent
to the lobby, other peers or Git. Campus API requests still share the global
owner-machine pacing limit. An unavailable API leaves the last known state
intact and reports a retry; it does not mark everybody offline.

Campus notifications say “dthoo is online on campus” with cluster, row and seat
on a separate line. LAN42 arrivals produce a separate “has joined the LAN42
lobby — say hi!” notification immediately from normal lobby state updates.
Each source notifies on an offline-to-online transition, including the first
online observation after starting HQ. Repeated polling does not repeat a notice.
Campus presence means an active reported computer login, rather than physical
attendance. Tracking resumes from the saved list when HQ starts again.

Notifications use an existing local cached photo when available. On desktops
supporting notification actions, “Open Intra profile” opens the profile and
“Say hi / write message” prepares `/dm LOGIN ` in your LAN42 input. Type the
message and press Enter yourself. An unfinished input is preserved: `/compose`
loads the waiting draft after you finish it. Desktop action support uses optional
PyGObject/GIO; plain `notify-send` is the fallback. `/notify off` suppresses
popups while keeping tracking text in the terminal.

`/dm LOGIN MESSAGE` and `/alert LOGIN MESSAGE` deliver a targeted message and a
desktop notification to that online user. They work within the current lobby
and directly between known guest-mesh nodes. DMs are never broadcast as public
chat or included in mesh gossip; verified lobbies refuse guest-mesh delivery.
Guest sender names remain explicitly unverified. Multiple matching guest nodes
require connecting to the intended node first. Message sends are limited to one
per two seconds. Notification buttons prepare drafts only; they do not send.

Relationships, lists and independent arrival rules are configured locally:

```text
/track dthoo thtay
/track status friends dthoo
/track status moots thtay
/track status oomf another-login
/track list lunch add dthoo thtay
/track list lunch remove thtay
/track alerts friends campus off
/settings clusters include cohort4 cohort5
/settings clusters exclude excluded-login
/settings clusters c1
/settings clusters on
```

Newly tracked people are acquaintances (`tracked`). A relationship is one local
label: `tracked`, `friends`, `mutuals` (alias `moots`), or `oomf`. Labels do not
claim reciprocal friendship or send requests to anyone. `friends` selects the
friendly relationships (friends, mutuals and oomf); `tracked` selects only
acquaintances; `alltracked` selects everyone in your relationship registry.
`mutuals`/`moots` and `oomf` can also be selected individually. `login:friends`
addresses a literal login that collides with a reserved selector name.

Custom named lists can overlap and do not automatically track their members.
Use `@lunch` to select a list explicitly; its bare name also works. Lists accept
`add`, `remove` and `delete`. `/track help` shows the command guide and `/track
config` shows the private, mode-600 JSON configuration. Existing watch lists
migrate to schema version 2 as tracked acquaintances on the first edit. Invalid
or newer configurations are preserved and must be repaired before changes save.

```text
/sabo friends
/sabo @lunch
/dm friends "do you all want lunch?"
/dm @lunch "meet at noon?"
/alert mutuals "game later?"
```

Selectors expand entirely on the sending computer. Only the resulting logins
and the requested message reach LAN42; relationship labels, lists and rules are
never uploaded. Group DMs send individual messages, spaced at least two seconds
apart, and report delivered/unavailable recipients. There is no shared group
thread and no offline mailbox. Quoted messages have their outer quotes removed;
unquoted apostrophes are preserved. SABO accepts at most 50 selected people and
DMs at most 100. A game terminal reloads the saved local selectors for each
command, so changes in HQ take effect there immediately.

Cluster arrival rules are a separate subscription system. Includes form a union
of logins, relationship selectors, named lists and/or cohort selectors; excludes
subtract from that union. Cohort rules use the local private campus cache and
remain dynamic as that cache changes. `/settings clusters off` disables these
rules without affecting personal relationship alerts. `/settings clusters clear
[include|exclude]` clears selectors. Rule exclusions do not mute personally
tracked friends; use `/track alerts LOGIN campus|lobby off` for personal alerts.

A friend/mutual/oomf arrival has a warmer message. Someone matched only by a rule
has a normal “Campus update” or “LAN42 update”. If both apply, only the personal
notification is emitted. Per-person `alerts` preferences are keyed by event
(`campus`, `lobby`) to allow future event types without conflating relationship
labels, list membership and subscriptions. Game activity and friend-request
workflows are not enabled by these labels.

Tracking and DM popups use Python GIO over the desktop's
`org.freedesktop.Notifications` D-Bus service. This supports cached-image hints
and action buttons. `notify-send` is only the fallback for desktops without the
GIO/service path; desktop support determines whether buttons are displayed.

Use `/settings clusters c1`, `c2`, or `all` to limit arrival rules
to a physical campus cluster. `C1`, `C2`, `cluster1` and `cluster2` are also accepted. The default is
`all`, including for older saved configurations. This scope applies to both
campus API and LAN42 lobby arrival rules and does not mute personal friend alerts.
An unknown seat cannot match a single-cluster scope. `/settings clusters` shows
the current location alongside includes, exclusions and the on/off switch.

Cluster names can also appear alongside rule filters:
`/settings clusters include cohort4 c1` or `/settings clusters C1 include cohort4`.
In cluster settings, `c1`/`cluster1` and `c2`/`cluster2` select the location rather
than being added as logins. The include/exclude lists still contain people or
cohort selectors. `login:c1` addresses a literal login with that spelling.

Bare `/profile` opens your personal Intra home at
`https://profile-v3.intra.42.fr/`, using the account already signed in to that
browser. Explicit `/profile hnah` opens the public page at
`https://profile-v3.intra.42.fr/users/hnah`; multiple explicit names still open
multiple public profiles. Both inherit the same browser permission by default.
Once approved, inherited browser actions do not repeat the consent or
always-allow question during that LAN42 session. Closing HQ ends its session
grant. `/settings permissions browser ask` revokes a current session grant;
`browser allow` makes it permanent, and `browser deny` blocks all browser pages.

### Automatic login and closing the sign-in tab

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
[browser helper](browser-tools/avatar-saver/README.md). Its completion-page
script runs only at `http://localhost:31415/signin-complete` and requests closing
only when the local callback explicitly opted in. The background worker closes
that sending tab ID; it never lists or reads other tabs. Without the extension,
the normal best-effort page behaviour is retained.

## KoelDrop — the uwu bird, but it brings files

A little campus file courier inside LAN42. **Files in your nest, only if you say
yes.** The receive notice is `🔊 uwu, dthoo sent you funny.txt`.

KoelDrop is a standard feature. There is no experimental toggle. From your
signed-in HQ, `/koel help` lists commands (`/files` and `/koeldrop` are aliases).
The on-campus API service owner starts a group with `/koel create`, then uses
`/koel invite dthoo` (or `friends` / `@LIST`). Recipients accept or decline their
numbered invitation. Accepting creates a dedicated folder whose added files
upload to that group; unrelated folders are never scanned.

`/koel pending` lists offers; `/koel receive NUMBER` approves a file and
`/koel reject NUMBER` declines it. `/koel trust LOGIN...` separately confirms an
automatic-receive whitelist for the current group. Deletions still require
approval. `/koel dir "EMPTY PATH"` chooses a folder; `/koel sync` syncs now;
`/koel leave` stops group uploads and preserves local copies.

Transfers use the existing pinned HTTPS broker, current verified sessions,
fresh campus seat/source-IP evidence, recipient-bound expiring invites, private
storage, file ownership, version conflicts and bounded polling. No files transfer
merely because LAN42 starts or a legacy experimental setting says `on`.
See [the design and permissions](docs/file-sharing-design.md).

The project name and public Intra description remain **Ryker's 42SG Campus LAN
Server** and the student-built campus LAN purpose at the top of this README.
KoelDrop is a sub-feature of that project.

### Optional uwu bird

The licensed `koel.ogg` recording is included with [attribution](assets/sounds/ATTRIBUTION.md).
Sound is **off by default**. At each fresh LAN42 launch, `y` enables it for this
session, `a` requests always-on, and Enter leaves it off. Always-on requires:

```text
Always uwu? Are you SURE? ಠ_ಠ [y/N]
```

You can also use `/settings koel-sound on|off|always`. `off` clears any saved
always-on choice. Enabling sound never enables file sharing. D-Bus sound hints
respect desktop support and sound settings; no separate player is started.

## Access, API scope and trusted hosts

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

See [access policy, role management and enrollment](docs/access-policy.md) for
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
Ordinary chat mute does not hide trusted approved announcements; OS display/
notification availability still applies. Each window gets terminal history and
each local computer gets one desktop alert, avoiding duplicate game-window popups.
Announcement text never executes commands, installs an update, or changes trust.

Without the API host, guest nodes still run discovery/chat/games on their own.
They are **guest nodes**, not replacement API administrators. No app-wide 404
occurs: sign-in/API-backed operations wait for the trusted service. Existing
public certificate trust is required before a client can recognize that host;
see [one-time trust and owner setup](docs/sign-in.md).

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

Sound-enabled `/uwu`, received pokes and automatic calls check system output.
If muted/zero, they ask before raising it to 30 percent. A second confirmation
can remember permission to do this automatically on this device. This remains
separate from permission to play the koel sound. Manage it with
`/settings audio-auto-on on|off`. `/volume` itself applies your explicit request
without a permission prompt.

In `/clusters`, `/track 2 4` uses the **displayed online roster numbers** (also
shown on map markers), not physical desk numbers. LAN42 lists the current Intra
names and seats for confirmation before adding them to your private tracking.
It captures those people, never future desk occupants; a changed seat snapshot
cancels the pending request. `/track LOGIN LOGIN` still works normally.

Terminal display recovery: Ctrl-L forces a full LAN42 redraw. Resizing a tmux
pane also redraws the screen; API queue notices stay in the chat log.

`lan42_restart` restarts LAN42 tmux client panes by injecting `/restart` into the
app. It skips shells, servers and unrelated Python programs, and clears unfinished
app input. `lan42_restart --check` lists matching panes without sending anything.
It works on Linux and macOS. Source the installed shell helpers or run
`useful-scripts/lan42_restart` directly. It does not restart the API host service.

For faster popup setup, use `/setup` or `/allow batch` to choose each category
with y/n. `/allow all` lists every category and asks once before allowing them
all permanently; `all` during batch setup also grants the full list. Categories
cover browser pages, help, FORKNITE, profiles, sign-in, tools, photos,
notifications and terminals. No for the general browser fallback keeps asking;
No for a specific category blocks it. `/cancel` stops the batch, keeping choices
already saved. `/settings permissions all ask` resets the policies. File receives,
group joins, announcement approval, sound and system-volume permission remain
separate decisions. You can invoke setup while another popup prompt is waiting.

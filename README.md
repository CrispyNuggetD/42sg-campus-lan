# Ryker's 42SG Campus LAN Server

A terminal hangout for a few friends at 42 Singapore. See who's online and where
they're sitting, chat, and invite each other to co-op Tetris or a round of
**Who Said That?**, or program a C army for **Hex Wars**.

This is version **0.5.0**, a small LAN prototype. Everyone joins as a guest;
Intra sign-in is planned for later.

## Get started

You'll need Git, Python 3.9 or newer with curses support, and a terminal at least
**76 columns × 28 rows**. LAN42 asks compatible terminals to grow to that size
when needed; terminals that do not support resize requests show a manual resize
message instead. There are no pip packages to install.

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
| `/signin` | Show the placeholder for future Intra sign-in. |
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
lobby still uses guest identities; Intra verification is not implemented.

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
[Ryker's SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).
If you already have your own `dailylogin`, it is preserved; use
`lan42_dailylogin` for this repo's version. Ryker's personal version also opens
LAN42 alongside his existing tasks.

Future Git pulls update the sourced helpers. To make `dailylogin` update without
opening a window, set `LAN42_OPEN_ON_LOGIN=0` before the source block in your
`.zshrc`. Sourcing the file alone never launches anything. If zsh isn't installed,
setup prepares the launcher and explains how to enable the helpers later.

See [the zsh helper guide](useful-scripts/README.md) for manual setup, project
paths, compile/run helpers and optional Documents syncing.

## Guest names and future Intra sign-in

The app uses your OS username and hostname, both marked **Guest**. These aren't
verified identities: a modified client could impersonate someone. This version
is meant for a few friends who trust each other. Green is reserved for future
verified users; nobody gets verified status yet.

The planned callback, `http://localhost:31416/callback`, is an unused
placeholder for future OAuth sign-in. There is no callback web server in this
version. The lobby uses a separate TCP port, **31415**.

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

**Updating?** Everyone needs v0.5.0 (protocol 4); quit existing apps and restart.
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

This prototype uses plaintext TCP and keeps no persistent chat or account
database. It has no internet discovery or NAT traversal. Games share their
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

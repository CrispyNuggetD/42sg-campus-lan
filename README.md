# Ryker's 42SG Campus LAN Server

A terminal hangout for a few friends at 42 Singapore. See who's online and where
they're sitting, chat, and invite each other to co-op Tetris or a round of
**Who Said That?**

This is version **0.2.2**, a small LAN prototype. Everyone joins as a guest;
Intra sign-in is planned for later.

## Get started

You'll need Git, Python 3.9 or newer with curses support, and a terminal at least
**76 columns × 28 rows**. There are no pip packages to install.

Each person clones the repo into their Documents folder:

```sh
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
cd 42sg-campus-lan
sh setup.sh
```

Then open the lobby:

```sh
~/Documents/42sg-campus-lan/lan42.sh
```

The launcher checks for updates and prints the version, commit and date before
starting. Everything runs from this clone; setup needs no sudo and installs
nothing in `/bin` or `~/.local/bin`.

## Find your friends

Ask a friend to open their lobby. In yours, type `/join` and answer the questions
about their **cluster, row and seat**. You can also connect when launching:

```sh
~/Documents/42sg-campus-lan/lan42.sh join
# Or, if you already know their seat:
~/Documents/42sg-campus-lan/lan42.sh join c1r2s3
```

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
such as `./lan42.sh join 10.11.2.3`.

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

Your own node keeps running while you visit a friend's lobby or game. Use
`/home` to return to it. **Quitting the app or closing its terminal stops your
node.** Everyone else's nodes keep going; when everyone quits, the network is
gone. A crashed or unreachable peer drops out of the online list after roughly
16 seconds.

Games live on the node hosting them. If that node quits, its games end and
visiting clients return to their own nodes. Leaving just a game room transfers
room control to another player; it doesn't stop the server.

## Testing on a Mac or another LAN

Campus seat shortcuts are optional. You can connect using a private IPv4 address
(such as `192.168.1.50` or `10.0.0.20`), a hostname resolving to one, or localhost.
Choose any available TCP port with `--port`; no campus-specific port is required.
Public internet IPs are currently rejected. Outside campus, seats show as unknown.

See [the local test walkthrough](docs/local-testing.md) for exact commands to run
two or three players in separate terminals on one Mac or Ubuntu computer.

## Chat, invitations and commands

Type a message and press **Enter** to chat. **Page Up/Down** scrolls through the
last 500 event lines. Text input currently supports ASCII.

| Command | What it does |
| --- | --- |
| `/who` | Show online players. |
| `/rooms` | Show game rooms. |
| `/games` | List the available games. |
| `/join` | Ask for a friend's cluster, row and seat. |
| `/connect c1r2s3` | Go straight to that friend's server. `/connect IP PORT` also works. |
| `/home` | Return to your own lobby. |
| `/host tetris` | Create a co-op Tetris room and send an invitation. |
| `/host bluff free` | Create a Who Said That? room without a prompt. |
| `/host bluff prompt` | Create a Who Said That? room with a random prompt. |
| `/join NUMBER` | Join a room on the server you're currently visiting. |
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

Desktop notifications use `notify-send` on the recipient's computer, so they
need their client open. If notifications aren't available, the terminal beeps
and the message stays in the log. Invitations have a 10-second cooldown; those
sent across the mesh arrive on the next exchange.

## The games

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

The registered callback, `http://localhost:31415/callback`, is an unused
placeholder for future OAuth sign-in. There is no callback web server in this
version. The lobby uses a separate TCP port, **31416**.

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

**Moving from v0.1?** Everyone needs v0.2.0 (protocol 2). The old version left a
background server running after you quit. Check its PID and process, stop that
old server, then reopen the app. Updating the source doesn't kill existing
servers automatically.

Logs and PID files are in `~/.local/state/42sg-campus-lan/`, or under
`$XDG_STATE_HOME/42sg-campus-lan` if configured. For the default port, look for
`server-31416.log` and `server-31416.pid`.

To test multiple nodes on one computer, give each a different port. `--port`
sets the host port, or the friend's port when joining; `join --local-port`
sets your own node's port. An explicitly started `./lan42.sh server` runs in
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

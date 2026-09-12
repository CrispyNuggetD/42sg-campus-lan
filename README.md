# Ryker's 42SG Campus LAN Server

A small **guest-mode terminal lobby for friends on the same LAN**, with chat,
desktop invitations, co-op Tetris and an anonymous-message bluffing game.
Version **0.2.0**. Python 3.9+ standard library, Git, and a terminal with curses.
No pip dependencies, sudo, external prompt service, or account setup.

## Install and play

Clone once on each computer:

    cd ~/Documents
    git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
    cd 42sg-campus-lan
    sh setup.sh

Run the launcher directly from your Documents clone:

    ~/Documents/42sg-campus-lan/launch.sh

With no arguments, launch.sh opens your guest lobby and starts its host server.
The explicit equivalent is ./launch.sh host. The optional zsh setup below provides\nthe lan42 shortcut; otherwise use the full launcher path for the lan42 commands\nin this guide. Setup writes nothing to /bin or ~/.local/bin and needs no PATH edit.

Friends connect to that computer's LAN address:

    ~/Documents/42sg-campus-lan/launch.sh join

It asks for the friend server's **cluster, row and seat**, then attempts that
one address. Your friend must already have lan42 running. You can also use:

    ~/Documents/42sg-campus-lan/launch.sh join c1r2s3
    ~/Documents/42sg-campus-lan/launch.sh join 10.11.2.3

Campus address layout (provided by the project owner):

| Seat | Address |
| --- | --- |
| c1r2s3 | 10.11.2.3 |
| c2r4s9 | 10.12.4.9 |

Cluster 1 uses 10.11.row.seat; cluster 2 uses 10.12.row.seat.
See [the Intra cluster map](https://meta.intra.42.fr/clusters) to find where
people are seated (Intra login required). A seat's address is not proof that a
lobby is running there. No wildcard scan is performed; an unreachable server
produces a connection error. TCP **31416** is the default; --port overrides it.

### Peer nodes: no central lobby

Each running app owns a local node. Entering one friend's seat performs a
handshake and exchanges known peer addresses. Nodes then contact known peers
directly every **5 seconds**. There is no campus scan or central directory.
Online students, chat, game advertisements and invitations spread across these
linked nodes. A new isolated node needs one live friend's address to join them.

Peers receive notices such as **“thtay came online! Cluster 1, row 2, seat 3.
Go say hi!”** The seat comes from the LAN address (or a matching cluster hostname),
not a five-second API query. Unknown seats are labelled rather than invented.
All identities remain Guest. /notify off disables your desktop notices.

Your local node stays alive while you visit another node's game; /home returns
to your own lobby. **Quitting the app or closing its terminal ends your local
node**, announces your departure, and leaves other nodes running independently.
Unexpected failures expire from peer presence after approximately 16 seconds.
A game ends if its hosting node quits. If you were visiting that node, your client
returns to your own node. No game-state migration is attempted.

This replaces the old v0.1 behaviour where a background host remained after quit.
There is still a helper server process, but its lifetime now follows the app's
local control connection. Heartbeats cover crashes and lost control connections.
With normal app usage, when everyone quits, no network remains. An explicitly
started foreground launch.sh server remains until its operator stops it.

Logs and PID files remain under ~/.local/state/42sg-campus-lan/
(or XDG_STATE_HOME/42sg-campus-lan), named server-31416.log and server-31416.pid
for the default port. No executable is installed there.
Updating source does not forcibly terminate an existing server. **All friends
must update to v0.2.0 (protocol 2)**. Stop any old v0.1 server deliberately after
checking its PID/process, then reopen the app; old servers are not auto-killed.
For multiple test nodes on one computer, choose distinct ports; join supports
--local-port for your own node separately from the friend's --port.

For five nodes, the full mesh makes roughly **20 small exchanges every five
seconds across the group** while healthy (plus client/game traffic).
Peers are capped at 16 per node. This is modest traffic, but campus policy and
network isolation still determine whether it is permitted and reachable.

Every launch attempts git pull --ff-only, then prints version, commit and date.
Local edits skip updating; failed updates use the local version with a warning.
LAN42_NO_UPDATE=1 explicitly skips the pull.
Use a terminal at least **76 columns × 28 rows**. ASCII text input in this version.

## Lobby

- Plain text + Enter sends chat. Page Up/Down scrolls the last 500 event lines.
- /who, /rooms, /games show current peers, rooms and games.
- /host tetris, /host bluff free, or /host bluff prompt opens a room and invites connected clients.
- /join with no argument asks which cluster/row/seat server to connect to.
- /join NUMBER joins a game room on the current server; /start starts the room
  host's game; /leave leaves that game.
- /connect c1r2s3 (or /connect IP PORT) switches directly to a friend server.
- /invite asks for a friend's cluster/row/seat and sends a server-to-server
  invitation to their running lobby. First host or join a game room.
- The friend sees the source address, then uses /connect IP PORT and /join NUMBER.
  An invitation never automatically moves a player or runs a game.
- /invite-room shares the invitation across linked nodes. Invitations have a
  10-second cooldown. /notify off mutes your desktop notices.
- /signin explains that Intra sign-in is **coming later**. /quit exits.

Notifications run on the recipient's own client using notify-send, if installed;
otherwise the terminal beeps and the notice stays in the event log. Desktop
notification settings may suppress popups. No unsolicited commands execute on
other desktops. Recipients need an open client to see desktop notifications. Direct seat invitations\nacknowledge the receiving server's connected-client count. Mesh invitations reach\nlinked peers on the next exchange; they never auto-launch or switch a game.

### Co-op Tetris

All room members control **the same falling piece and shared board**. Clear lines
together; score 100/300/500/800 for 1/2/3/4 lines. Gravity runs on the server.
Arrow keys or WASD move/rotate, Space hard-drops. Tab switches between play and
chat/commands. After game over, the room host can /start again.

### Who Said That?

Three or more players. Everyone writes a message with /answer YOUR TEXT.
Free mode has no prompt; prompt mode asks everyone to respond as the current
leader. The leader rotates each round. Prompts are bundled and randomly selected.

After all submissions (or 45 seconds), entries are shuffled and **all display
the leader's name**. Guess the real author of every numbered entry, in order:

    /vote hnah thtay dthoo

Use each entry's actual suspected author, not the displayed leader label.
Your own entry is ignored for scoring. Earn 2 points for each correct guess;
authors earn 1 per opponent fooled. Voting ends after everyone votes or 45 seconds,
then real authors and round scores appear in the event log. /start plays again.
If the leader times out without an answer or fewer than two submit, cancel the
round. Leaving players can delay completion until timeout, but cannot hang it.
Scores are per round, not persisted.

## Guest identity and optional campus seats

By default, identity is the OS account name plus hostname. Both are **unverified**.
Duplicate connected usernames are rejected, but this is not authentication:
a modified client can impersonate a friend. --guest-name NAME supports local
multi-client testing and remains explicitly Guest. Green is reserved in the UI
palette for future Verified status; nobody receives it in this release.

42 API lookup is optional and never blocks lobby/game startup. On a trusted host,
set INTRA_CLIENT_ID and INTRA_CLIENT_SECRET in its environment before starting.
The host uses client credentials and GET /v2/users/:login to fetch the location\nof connected guest names every two minutes. Mesh presence uses the address-based\nseat mapping; the optional API remains a separate fallback for legacy local clients.\nUnknown/unavailable seats are labelled;
a guest claiming a name is not proof that the API seat belongs to that connection.
It does not list the whole campus. No API credentials go to clients or Git.
Do not distribute the host secret to friends. Real API credentials have not been
used in automated tests; permissions and campus data need a live check.

The registered http://localhost:31415/callback is an **unused future OAuth
placeholder**, separate from LAN TCP port 31416. It starts no HTTP server.
See [42's client-credentials guide](https://api.intra.42.fr/apidoc/guides/getting_started)
and [user endpoint](https://api.intra.42.fr/apidoc/2.0/users/show.html).

## Optional zsh helpers and daily login

The dailylogin command is **not a standard campus command**. It originally came
from Ryker's personal [SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).
A public-friendly adaptation is now included in this repository.

To get the latest copy and install it without replacing your .zshrc:

    cd ~/Documents/42sg-campus-lan
    sh setup.sh --zsh

Then open a new terminal (or source your .zshrc). Setup backs up the file and
adds a source line pointing to this clone, so future Git pulls update the helpers.
Existing personal functions and aliases are preserved.

Run **lan42_dailylogin** to update this repo and reload its helpers in your
current shell. If you do not already define dailylogin, that shorter name is
provided too. By default it only pulls the LAN repo; pulling all your Documents
repos is an opt-in setting. It does not open the lobby or launch other applications.

See [the zsh helper guide](useful-scripts/README.md) for manual installation,
your own project paths, optional Documents syncing, and compile/run helpers.
Plain sh setup.sh checks prerequisites and prepares launch.sh inside the clone,\nwithout editing shell configuration or installing a command elsewhere.

### Repository layout

- campus_lan/: client, host, game rules and optional API adapter.
- minigames/: game directory/guide.
- useful-scripts/: public zsh helpers, installer and configuration guide.
- docs/: protocol and campus deployment task.
- tests/: rules, networking, lifecycle and helper installation checks.

## Scope and checks

    python3 -m unittest discover -s tests -v

This is a trusted-friends LAN prototype: plaintext TCP, guests, no persistent
chat/account database, no internet discovery or NAT traversal. Game rooms share
the lobby server process/port to keep setup small. The lobby coordinates rooms
without needing a separate process per minigame. A room creator leaving a room\ntransfers room control; the hosting node quitting ends that node's games. Other\nnodes and their games keep running.

Campus firewall/client isolation may prevent peer connections. Test on campus
rather than changing firewall settings blindly. macOS can run the prototype,
but desktop popups target Linux notify-send (terminal fallback elsewhere).

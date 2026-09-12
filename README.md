# Ryker's 42SG Campus LAN Server

A small **guest-mode terminal lobby for friends on the same LAN**, with chat,
desktop invitations, co-op Tetris and an anonymous-message bluffing game.
Version **0.1.0**. Python 3.9+ standard library, Git, and a terminal with curses.
No pip dependencies, sudo, external prompt service, or account setup.

## Install and play

Clone once on each computer:

    cd ~/Documents
    git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
    cd 42sg-campus-lan
    sh setup.sh

Run the installed command (or add ~/.local/bin to PATH):

    ~/.local/bin/lan42 host

Friends connect to that computer's LAN address:

    ~/.local/bin/lan42 join HOST_IP

On Linux, hostname -I shows candidate addresses; use the campus LAN address
reachable by your friends. TCP port **31416** is configurable with --port.
A lobby host listens until its terminal closes. Everyone else disconnects then.
To keep the lobby independently running, use lan42 server in one terminal
and lan42 join 127.0.0.1 in another.

Every launch attempts git pull --ff-only, then prints version, commit and date.
Local edits skip updating; failed updates use the local version with a warning.
LAN42_NO_UPDATE=1 explicitly skips the pull.
Use a terminal at least **76 columns × 28 rows**. ASCII text input in this version.

## Lobby

- Plain text + Enter sends chat. Page Up/Down scrolls the last 500 event lines.
- /who, /rooms, /games show current peers, rooms and games.
- /host tetris, /host bluff free, or /host bluff prompt opens a room and invites connected clients.
- /join NUMBER joins; /start starts the room host's game; /leave returns.
- /invite repeats an invitation (10-second cooldown). /notify off mutes yours.
- /signin explains that Intra sign-in is **coming later**. /quit exits.

Notifications run on the recipient's own client using notify-send, if installed;
otherwise the terminal beeps and the invitation stays in the event log. Desktop
notification settings may suppress popups. No unsolicited commands execute on
other desktops. Clients must already be connected to receive invitations.

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
The host uses client credentials and GET /v2/users/:login to fetch the location
of connected guest names every two minutes. Unknown/unavailable seats are labelled;
a guest claiming a name is not proof that the API seat belongs to that connection.
It does not list the whole campus. No API credentials go to clients or Git.
Do not distribute the host secret to friends. Real API credentials have not been
used in automated tests; permissions and campus data need a live check.

The registered http://localhost:31415/callback is an **unused future OAuth
placeholder**, separate from LAN TCP port 31416. It starts no HTTP server.
See [42's client-credentials guide](https://api.intra.42.fr/apidoc/guides/getting_started)
and [user endpoint](https://api.intra.42.fr/apidoc/2.0/users/show.html).

## Daily login and repository layout

Your SUTD dailylogin already calls syncdocs when pullotherrepos=1.
Its recursive Documents scan will pull this normal clone at
~/Documents/42sg-campus-lan; no second updater needs to be added.
Run setup once for the lan42 command. Daily login updates source; it does not
automatically host a lobby or notify friends.

- campus_lan/: client, host, game rules and optional API adapter.
- minigames/: game directory/guide.
- useful-scripts/: intentionally empty apart from Git's tracking placeholder.
- docs/: protocol and campus deployment task.
- tests/: deterministic rules and real localhost multi-client tests.

## Scope and checks

    python3 -m unittest discover -s tests -v

This is a trusted-friends LAN prototype: plaintext TCP, guests, no persistent
chat/account database, no internet discovery or NAT traversal. Game rooms share
the lobby server process/port to keep setup small. The lobby coordinates rooms
without needing a separate process per minigame. Host departure ends its server;
a room creator disconnecting transfers room control to another member.

Campus firewall/client isolation may prevent peer connections. Test on campus
rather than changing firewall settings blindly. macOS can run the prototype,
but desktop popups target Linux notify-send (terminal fallback elsewhere).

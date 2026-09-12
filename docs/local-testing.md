# Test HQ and games on one Mac or Ubuntu computer

Update your Documents clone with `git pull --ff-only` and run `sh setup.sh`.
Quit old LAN42 apps before testing v0.4.0 (protocol 3). Resize each terminal to
at least 76 columns by 28 rows. Guest names below simulate different students.

## Two equal HQ nodes

Terminal A:

```sh
~/Documents/42sg-campus-lan/lan42.sh --port 32101 --guest-name hnah
```

Terminal B:

```sh
~/Documents/42sg-campus-lan/lan42.sh --port 32102 --guest-name thtay
```

Each starts with itself online. In B, type:

```text
/join 127.0.0.1 32101
```

Both HQs stay in their own windows. Within about five seconds they should show
both players. Try chat, `/who`, and `/map 1`. Home computers usually have unknown
campus seats. No API sign-in is needed.

## Co-op Tetris opens separate game windows

1. In A's HQ, type `/host tetris`. A new terminal opens, creates the room and
   advertises it. HQ remains online.
2. In B's HQ, type `/join 1` (use the invitation's actual room number).
   Another game terminal opens and joins A's room.
3. In A's **game terminal**, type `/start`.
4. Use arrows/WASD and Space in either game terminal to control the shared piece.
   Tab switches between play and chat.
5. `/quit` or close each game window. Both HQ windows should remain connected,
   with two online users. Use `/leave` if you want to leave the room but keep
   that game terminal open; close it before opening another game on that node.

## Two-player bluff

1. In A's HQ, type `/host bluff free`.
2. In B's HQ, `/join NUMBER` using the new room number.
3. In A's game window, `/start`.
4. In A's game window, `/answer wow I blackholed!`.
5. In B's game window, `/answer fishy`.
6. When shuffled entries appear, both vote using `/vote hnah thtay` or
   `/vote thtay hnah`, matching guesses for entries 1 and 2.

Both phases time out after 45 seconds. Results reveal authors and scores.
Two players are allowed, though three makes guessing less obvious.
For prompts, create a new room using `/host bluff prompt`.

## Third node and survival after the first quits

Terminal C:

```sh
~/Documents/42sg-campus-lan/lan42.sh --port 32103 --guest-name dthoo
```

In C, `/join 127.0.0.1 32101`. Wait for all three HQ rosters to agree.
Quit A's HQ. B and C should remain online and able to chat. No replacement-host
command is needed. Games hosted on A end, but games on B or C can continue.
To join a game on B from C, `/join 127.0.0.1 32102` then `/join NUMBER`.

## Separate computers

Each person runs `lan42` using the default port 31416. Inside HQ, join a friend's
private IPv4 address with `/join 192.168.1.50`, or a campus seat with
`/join c1r2s3`. Add the port if they use a different one.

Linux supports GNOME Terminal, Konsole, Xfce Terminal and xterm; macOS uses
Terminal. If a new window cannot open, HQ prints a command you can run in a
second terminal manually. macOS notifications fall back to a terminal beep/log;
Ubuntu uses `notify-send` when available. Public internet IPs are rejected.

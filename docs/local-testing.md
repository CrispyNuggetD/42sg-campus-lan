# Try the games on one Mac or Ubuntu computer

Use a normal terminal with Python 3.9+ and curses support. Resize each window to
at least 76 columns by 28 rows. These commands use three different local ports
and guest names to simulate separate computers. No Intra account is needed.

## Prepare the repo

If you haven't cloned it to Documents yet:

```sh
mkdir -p ~/Documents
git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git ~/Documents/42sg-campus-lan
```

Then update and prepare it:

```sh
cd ~/Documents/42sg-campus-lan
git pull --ff-only
sh setup.sh
```

Quit any running test apps before testing a new version, so their servers restart
with the updated code. Version 0.2.1 allows two-player bluff rounds.

## Open two terminal windows

In terminal A:

```sh
~/Documents/42sg-campus-lan/lan42.sh host --port 32101 --guest-name hnah
```

In terminal B:

```sh
~/Documents/42sg-campus-lan/lan42.sh join 127.0.0.1 --port 32101 --local-port 32102 --guest-name thtay
```

Both clients are now visiting A's server, while each has its own local node.
B's `--port` is the server it visits; `--local-port` is its own server.
Type a chat message in either window and check it appears in the other.
Use `/who` to see both guest names. Allow about five seconds for peer updates.
Seats will usually be unknown on a home computer.

## Test co-op Tetris

1. In A, type `/host tetris`.
2. In B, type `/join 1` (or use the room number shown in the invitation).
3. In A, type `/start`.
4. Use arrows or WASD in either window. Both should control the same piece.
   Space drops it; Tab switches between play and chat.
5. Type `/leave` in each window when done. Press Tab first if needed.

## Test Who Said That?

1. In A, type `/host bluff free`.
2. In B, join the new room with `/join NUMBER`, using the actual room number.
3. In A, type `/start`. With two players, a recommendation for 3+ appears,
   but the round starts anyway.
4. In A, type `/answer wow I blackholed!`; in B, type `/answer fishy`.
5. When the shuffled entries appear, use `/vote hnah thtay` or
   `/vote thtay hnah` in each window, matching your guess for entry 1 then entry 2.
6. Check that the authors and scores appear after both votes. You have 45 seconds
   for answers and another 45 for votes. `/start` plays another round.

With two players you can deduce the other author from your own entry. It's useful
for testing, but adding a third makes the guessing game more interesting.
To test prompts, leave the room and create one with `/host bluff prompt`.

## Add an optional third player

In terminal C:

```sh
~/Documents/42sg-campus-lan/lan42.sh join 127.0.0.1 --port 32101 --local-port 32103 --guest-name dthoo
```

Use `/join NUMBER` before the next round starts. Votes now need three names,
one for each entry—for example, `/vote hnah dthoo thtay`.

## Test independent nodes and invitations

After leaving the games, type `/home` in B and C to visit their own nodes.
Chat should still reach the other windows through the mesh. In A, create a game
room and use `/invite-room` to advertise it. The invitation gives the address,
port and room number; visitors connect and join explicitly.

Use `/quit` in A. B and C should keep running and chatting after their initial
peer discovery has completed. If either was still visiting A, it should return
home. Quitting each remaining app should stop its own node.

On macOS, expect a terminal beep and log entry instead of a Linux desktop popup.
On Ubuntu, desktop popups use `notify-send` when installed and permitted by the
desktop notification settings. Keep the receiving client open.

## Use separate computers on a home LAN

On the host:

```sh
~/Documents/42sg-campus-lan/lan42.sh host --port 32101
```

On a friend’s computer, substitute the host's actual private IPv4 address:

```sh
~/Documents/42sg-campus-lan/lan42.sh join 192.168.1.50 --port 32101
```

Different computers can use the same local port. The `--local-port` distinction
above is needed because the simulated players share one Mac. Choose unused,
unprivileged ports; there is no requirement to use 31416 or a campus address.
Public internet addresses are currently rejected, and router/firewall isolation
can prevent LAN connections. IPv6 and native Windows are not covered by this
walkthrough: the current launcher uses IPv4 resolution and Unix modules.

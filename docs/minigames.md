# LAN42 minigames

[← LAN42](../README.md) · [All guides](README.md)

- [Game launcher and Tab completion](#game-launcher-and-tab-completion)
- [Co-op Tetris](#co-op-tetris)
- [Who Said That?](#who-said-that)
- [Hex Wars: code your conquest](#hex-wars-code-your-conquest)
- [FORKNITE (multiplayer Philosophers visualiser/game)](#forknite-multiplayer-philosophers-visualisergame)

## Game launcher and Tab completion

Use `/game tetris`, `/game bluff free`, `/game hexwars`, or `/game forknite`.
`/host` remains a compatibility alias. Bare `/game` still returns to the current
terminal game view. While typing a slash command, Tab completes commands, game
names, bluff modes and a few simple options. `/sig` + Tab completes `/signin` directly;
`/signout` is available when typed explicitly but is omitted from completion suggestions. Ambiguous matches expand their
common prefix and print choices. With no slash input, Tab keeps its existing
lobby-map / Tetris-control behavior.

## Co-op Tetris

Everyone controls **the same falling piece on the same board**. Coordinate your
moves—or enjoy the chaos. Use the arrow keys or WASD to move and rotate, and
**Space** to hard-drop. **Tab** switches between playing and typing chat or
commands.

Clearing 1, 2, 3 or 4 lines scores 100, 300, 500 or 800 points. After game over,
the room host can type `/start` to try again.

## Who Said That?

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

## Hex Wars: code your conquest

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

Read the **[C API, structs, exact rules and setup guide](../minigames/hexwars/README.md)**.
Use the [header](../minigames/hexwars/hexwars.h) and
[example strategies](../minigames/hexwars/examples/) to build your player.

## FORKNITE (multiplayer Philosophers visualiser/game)

FORKNITE turns my **legacy 42 C Philosophers project**
into a multiplayer browser visualiser/game. It runs the host’s actual C `philo`
executable: friends become diners, the timer tightens each round, and the first
real philosopher death ends the tournament.

Philosophers belongs to the [older C/C++ Common Core](https://www.42berlin.de/curriculum-42-berlin-pre-2026).
FORKNITE gives my implementation of that legacy project a playful multiplayer life.
For the newer curriculum, see [42 Singapore’s #42Next announcement](https://www.linkedin.com/posts/42singapore_42next-42singapore-futureready-activity-7426471159656763393-Z4wm).

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
See [the game README](../minigames/forknite/README.md) for developer pipe mode and logs.

FORKNITE renders only joined players and explicitly requested `/sabo` stand-ins.
At match start, the native philosopher count is the seated-player count; no
synthetic diners are added. tmux game windows use `GAME-ROOM`, such as `forknite-1`.
Profile URLs come from 42; if its image CDN denies a fetch, the card explicitly
shows “42 photo unavailable” and keeps the silly fallback face.

FORKNITE can use `minigames/forknite/philo`, a machine-local executable or symlink
(ignored by Git), as its default native binary. `LAN42_PHILO_BINARY` overrides it;
otherwise the launcher tries that local path then `philo` on PATH. Explicit
`--exec` still works. On this workstation the symlink targets your existing
Philosophers executable, so rebuilding that executable updates what FORKNITE runs.

FORKNITE room creation itself can proceed while browser consent waits. Each
participant approves their own browser. Declining leaves the room available;
`/browser` requests opening it later. Missing photos request the host's local
photo tool rather than launching a browser from the room server. Tool panels
and photo-tab/save batches have separate permissions. The extension still needs
its normal one-time installation. LAN42 only opens requested new pages; these
permissions do not give it access to existing Chrome tabs, profiles or cookies.

### FORKNITE meal timing colors

Purple highlights the last diner to start each numbered meal wave in an odd
table, only while that diner is eating. This extra odd-table turn can be normal;
it is separate from a genuinely overdue wait. The next meal wave can highlight
a different diner.

Lime/cyan/pink show the first, second and third-or-later meal starts. Orange
marks an overdue wait or a meal that started late; the next on-time meal clears
it. The full start-to-start estimate includes eating, sleeping and the table's
fork-wait allowance: `max(eat + sleep, 2 * eat)` for even tables, or
`max(eat + sleep, 3 * eat)` for odd tables, plus `max(2ms, 5% of eat)` grace.
For five diners with 100ms eat and 100ms sleep, orange begins beyond 305ms,
not after one 100ms eating slot. The card labels distinguish waiting overdue
from an already late meal. This is a display estimate, not a native scheduler
verdict; the starvation countdown still uses `time_to_die`. Completed rounds
freeze their timing display.

### Select online campus users

In a FORKNITE room, the signed-in room host can use `/sabo online [COUNT]` for
stand-ins from the host's last campus API presence snapshot. These users need
not run LAN42. The snapshot age is reported; this command does not refresh it.
The approved host seeds it at startup and refreshes every minute; if the crawl
is still pending or has failed, `/clusters` retries it. A missing or
empty snapshot never selects the whole directory or substitutes sign-ins.

`/sabo verified [COUNT]` instead selects active verified SG users connected to
this LAN42 host; it makes no campus-presence claim. Both selectors exclude
already seated people, use alphabetical order up to the free 50-seat capacity,
and retain whitelist, membership and API-budget checks. Stand-ins are not
contacted. See [campus selectors](campus-guide.md#select-campus-online-people-for-forknite).

`/sabo online cluster 1` and `/sabo online cluster 2` filter the cached campus
seats. Add a separate count, for example `/sabo online 5 c1`. Cluster filters
apply to `online`, not `verified` sign-ins.

The terminal and FORKNITE browser headers show campus totals and C1/C2 counts
with snapshot age, independent of game/replay time. Data older than two minutes
is marked stale; unavailable data is not displayed as zero. Existing SG sign-in
or local-operator permission is required. Guests do not receive the API counts.

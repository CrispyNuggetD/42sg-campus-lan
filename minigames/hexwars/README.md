# Hex Wars — program your army in C

Write an algorithm, submit your bot, and watch 2–6 armies compete on a 61-cell
hexagon. This is LAN42's own ruleset inspired by the requested hex-conquest
concept, not an exact recreation of the reference video.

## Play now

Restart LAN42 after updating; all peers need **v0.6.0 / protocol 5**.
From HQ, `/host hexwars` opens a game window. Friends connect to your node and
`/join ROOM_NUMBER`, just like the other games.

In the game window:

| Command | Result |
| --- | --- |
| `/bot` | Menu: upload C, select demo, read API help, create starter. |
| `/bot starter ~/my_player.c` | Copy the Expander starter; refuses to overwrite a file. |
| `/bot upload ~/my_player.c` | Compile your local C file, then submit the compiled bot to the host. |
| `/bot demo` | Select the built-in Expander without installing a compiler. |
| `/bot guide` | Show the API summary and paths to this guide and the header. |
| `/practice` | Host toggles one computer opponent; it occupies a player slot. |
| `/start` | Host starts when every human has a bot and there are 2–6 armies. |
| `/leave` | Forfeit your army and leave the room. |

Quick solo trial: `/host hexwars`, then `/bot demo`, `/practice`, `/start`.
For your own strategy, create the starter, edit it in your editor, then upload.
Paths with spaces must be quoted. The menu performs these same actions.

Each tile shows `<A24>`: army A with 24 units; `.` is neutral. The scoreboard
shows territory, total units, and bot faults. Everyone in the room sees the
same live board. A match lasts at most 300 turns, roughly 4 minutes depending
on bot runtime and host load. Between matches you can replace your bot and
the host can `/start` again. Joining mid-match is disabled. There is no replay
archive, persistent ladder, or separate spectator role yet.

LAN42 supports the **guest mesh** and a separate **verified 42 lobby**. Use
`/signin` in local HQ before hosting to play over TLS under your verified login.
See [42 sign-in setup](../../docs/sign-in.md). Verification proves 42 account
ownership, not campus enrollment or honest code. This is not a graded or
cheat-proof competition.

## C toolchain

The lobby and built-in practice bots still require only Python 3.9+.
Uploading C additionally requires **Clang with the wasm32 target and LLVM's
wasm-ld linker on the student's computer**. A host running uploaded bots needs
**Node.js**. Use a maintained Node.js release for shared hosting.

On Ubuntu, the packages are `clang`, `lld`, and `nodejs`; install through your
normal approved package manager. On a managed campus machine, ask staff for
missing packages or use a user-local LLVM installation. No sudo is needed by
the game itself. On macOS, use upstream LLVM (Apple's bundled Clang may lack
the Wasm linker) and Node.js. If LLVM is not on PATH, set these **before
launching LAN42**:

```sh
export LAN42_CLANG=/path/to/llvm/bin/clang
export LAN42_WASM_LD=/path/to/llvm/bin/wasm-ld
```

Versioned `wasm-ld-11` through `wasm-ld-22` are also detected. No compiler is
downloaded automatically by LAN42. Compilation failures appear in game chat;
your previous working bot remains selected if an upload fails.

## API v1

Include [`hexwars.h`](hexwars.h). Implement these **two functions**, with no
`main()`:

```c
#include "hexwars.h"

void bot_config(t_hw_attributes *attributes)
{
    attributes->growth = 4;
    attributes->attack = 3;
    attributes->armor = 2;
}

void bot_turn(const t_hw_state *state, t_hw_action *action)
{
    int i;
    int d;
    int n;

    i = -1;
    while (++i < state->cell_count)
    {
        if (state->cells[i].owner != state->me)
            continue;
        d = -1;
        while (++d < 6)
        {
            n = state->cells[i].neighbors[d];
            if (n >= 0 && state->cells[n].owner != state->me
                && state->cells[i].units > 2 * state->cells[n].units + 1)
            {
                action->from = i;
                action->to = n;
                action->units = state->cells[i].units - 1;
                return;
            }
        }
    }
    /* The action starts as a pass: units = 0. */
}
```

`bot_config` starts with 3/3/3. Each attribute must be **1–5** and their sum
must be **9**. The host freezes these attributes at upload time. Changing
attributes inside `bot_turn` has no effect on the rules.

| Structure / field | Meaning |
| --- | --- |
| `t_hw_state.api_version` | Always `HW_API_VERSION` (1). |
| `turn` | Completed turns; first decision sees 0. |
| `me` | Your army index, `0..player_count-1`. Not a login or network ID. |
| `player_count` | Initial number of armies, including eliminated armies. |
| `cell_count`, `max_turns` | 61 and 300 in this version. |
| `cells[HW_MAX_CELLS]` | Full public board; there is no fog of war. |
| `t_hw_cell.q`, `r` | Axial hex coordinates, radius 4; `abs(q+r) <= 4`. |
| `owner` | Army index or `HW_NEUTRAL` (-1). |
| `units` | 0–99; neutral cells do not produce units. |
| `neighbors[6]` | Cell indices in E, NE, NW, W, SW, SE order; -1 at an edge. |
| `t_hw_attributes.growth` | Units produced per owned cell after each turn. |
| `attack`, `armor` | Attack and defense strength modifiers, respectively. |
| `t_hw_action.from`, `to` | Source and neighboring destination cell indices. |
| `units` | Units to send; 0 passes, otherwise `1 <= units < source.units`. |

Coordinates use neighbor offsets `(1,0), (1,-1), (0,-1), (-1,0), (-1,1), (0,1)`.
Cells are ordered by increasing `r`, then increasing `q`; use `neighbors`
rather than assuming adjacent array indices are adjacent hexes.

All ABI fields are signed 32-bit integers. The state is 616 integers / 2464
bytes: six header fields followed by 61 cells of ten integers each. The
three-`int` attribute and action structs are 12 bytes each. The SDK's
[`bridge.c`](bridge.c) exports `hw_state()`, `hw_config()`, and `hw_step()`,
which return pointers into the module's exported memory. The uploader links
this bridge automatically; students only write the two `bot_*` functions.

Code is freestanding C99, compiled with `-Wall -Wextra -Werror`. There is no
libc, malloc, printf, filesystem, sockets, clock, or external library. Use
arrays, loops, arithmetic and your own helper functions. The SDK file is the
only supplied include. A **fresh module instance runs every decision**:
globals, static variables and memory do not persist between turns. Base your
strategy on the board and turn number. Source files are limited to 64 KiB;
compiled bots to 32 KiB; linear memory including the stack to 1 MiB.

[`examples/expander.c`](examples/expander.c) prioritizes weaker targets and
reinforces the frontier. [`examples/sentinel.c`](examples/sentinel.c) trades
growth and attack for armor. Both are intentionally beatable starting points.

## Exact rules

1. Each army starts at a map corner with 24 units; other cells have 8 neutral
   units. Two armies occupy opposite corners; three alternate corners; four
   occupy two opposite pairs. Five use five consecutive corners, so spacing
   is unequal. Six occupy every corner. Slots follow the room's connection-ID
   order; there is no randomized tournament seeding in this version.
2. Every living bot reads the **same pre-turn board** and chooses at most one
   move. All legal source deductions happen before battles. You must own the
   source, use a neighboring destination, and leave at least one unit behind.
   A friendly destination reinforces it; an enemy/neutral destination attacks.
   Opposing armies that cross along an edge do not fight until they reach
   their respective destinations.
3. At each destination, combine arrivals by army. The existing owner's
   garrison **and friendly arrivals** use `units * (5 + armor)`. Other arrivals
   use `units * (5 + attack)`. Neutral defenders use `units * 8`.
4. The strongest army wins only if its power exceeds the **sum of all other
   armies' power**. Otherwise the tile becomes empty and neutral. A winner
   keeps `ceil((winner_power - other_power) / winner_multiplier)` units,
   capped at 99. This resolves multi-army fights without submission-order
   advantage. With no opposing arrival, reinforcement simply adds units.
5. All owned cells then receive their owner's `growth` units, capped at 99.
   An army with no cells is eliminated. The last army standing wins; neutral
   cells need not be captured once all opponents are gone. At turn 300, most
   territory wins, then most units; an exact tie is a draw.

Example: 10 units with attack 5 have 100 power. Against 5 defenders with armor
3 (40 power), they capture the tile with 6 units, then receive growth income.

Illegal orders, runtime traps, and timeouts count as passes and add a fault.
Three accumulated faults disqualify a bot and make its territory empty neutral.
Leaving the room immediately forfeits it. Bot faults never authorize changes
to another army's orders. Closing the hosting HQ ends its rooms, as for other
LAN42 games.

## Execution and network contract

The client compiles only the C file explicitly chosen on that computer. C
source and paths are **not sent to the host**. The host receives compiled Wasm,
checks its size and memory/table bounds, rejects imports and start functions,
then validates the three SDK exports and attributes in a separate Node.js
process. There is no native-executable fallback. Each instance gets 50 ms for
instantiation/configuration/decision, and a batch has a 2-second outer timeout.
At most two batches run concurrently per node. Runtime failure is reported
as a bot fault; it does not run on the lobby event loop. Timing limits depend
on host performance and are not deterministic instruction budgets.

Only Wasm is untrusted executable input. The runner's JavaScript is shipped
with LAN42; Node's `vm` supplies interruption, not a general JavaScript
security boundary. Keep the host runtime updated. See LLVM's official
[Wasm linker documentation](https://lld.llvm.org/WebAssembly.html) and Node's
[execution timeout documentation](https://nodejs.org/api/vm.html).

After the normal protocol-5 `hello`, a room member uploads:

```json
{"type":"hex_bot","room":"1","wasm":"BASE64_WASM_BYTES"}
```

Maximum client message: 48 KiB, newline-delimited JSON. One upload per client
per three seconds; only before/after matches. Rejection preserves the old bot.
Acceptance sends an `event` containing `Bot ready`, a hash, and the attributes,
then a `game` snapshot with each member's readiness. Runtime snapshots contain
`game: "hexwars"`, `room`, `phase` (`waiting`, `running`, `results`), `bots`,
and `practice`; after start they also contain `turn`, `max_turns`, `cells`,
`scores`, `over`, and `result`. Source and compiled bytes are never broadcast.
Room bots live in memory until their player leaves or the host shuts down.
There is no HTTP API: the C structs are the player API, and this JSON contract
is for alternative LAN clients.

## Tests

```sh
python3 -m unittest discover -s tests -p 'test_hex*.py' -v
```

Compiler/runtime tests skip with an explanation if their tools are absent.
They cover real C uploads over TCP, battle resolution, turn limits, bot traps,
infinite loops, memory/import rejection, readiness and forfeits, and rendering
all 61 cells at the minimum 76 × 28 terminal size.

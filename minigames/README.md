# 42SG LAN minigames — v0.5.0

Implemented in campus_lan/games.py, coordinated by campus_lan/server.py.

- **Co-op Tetris:** one shared board and falling piece; host-authoritative gravity,
  rotation, line clearing and scoring. /host tetris, friends /join NUMBER,
  room host /start.
- **Who Said That?:** timed anonymous-message guessing. /host bluff free or
  /host bluff prompt. Two players minimum; three or more recommended. /answer TEXT, then
  /vote USER1 USER2 ... assigns an author to each shuffled entry.
  Reveal authors and round scores after voting. Built-in prompts; no external AI.

- **Hex Wars:** 2–6 programmable armies on a 61-cell hex board. `/host hexwars`,
  `/bot` for the C upload menu, `/practice` for a computer opponent, `/start`
  when ready. [C structs, examples and exact rules](hexwars/README.md).

See the main README for controls and limitations.

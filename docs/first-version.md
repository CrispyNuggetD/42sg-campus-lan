# Current proof of concept: v0.2.0

The original guest lobby and games now have a bounded peer mesh. Seat handshakes
discover peers; five-second exchanges share online presence, chat and game rooms.
Each app owns its local node, retains it while visiting games, and stops it on exit.
Other nodes continue if the original bootstrap node leaves.

Game logic remains intentionally simple: shared-board co-op Tetris, timed bluff
rounds, built-in prompts, per-round scoring. Authentication remains a placeholder.
See README.md and protocol.md for installation, controls, lifecycle and limits.

The public zsh helper installer keeps executables in the Documents clone and
preserves personal dailylogin functions.

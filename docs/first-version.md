# First version delivered

The guest-mode prototype is implemented. See README.md for installation,
game controls, limitations and optional API setup.

Deliberate small-version choices: one server multiplexes game rooms; shared-board
co-op Tetris; bundled prompts; round-local bluff scoring; seat-based LAN address prompts;
no authentication or persistent database. Intra sign-in remains a coming-later
placeholder; a green palette entry is reserved for verified identity.

Optional public zsh helpers now provide dailylogin; existing personal functions are preserved.
Campus deployment and desktop notification verification are delegated separately
through the enrolled mac-remote device, not inferred from localhost tests.

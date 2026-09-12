# First version delivered

The guest-mode prototype is implemented. See README.md for installation,
game controls, limitations and optional API setup.

Deliberate small-version choices: one server multiplexes game rooms; shared-board
co-op Tetris; bundled prompts; round-local bluff scoring; manual LAN address;
no authentication or persistent database. Intra sign-in remains a coming-later
placeholder; a green palette entry is reserved for verified identity.

The existing SUTD syncdocs integration already covers a clone under Documents.
Campus deployment and desktop notification verification are delegated separately
through the enrolled mac-remote device, not inferred from localhost tests.

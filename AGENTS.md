# LAN42 development and cross-repository shell integration

## Keep the installer's feature list current

The canonical short feature list is the section between
`<!-- shell-installer-features:start -->` and
`<!-- shell-installer-features:end -->` in `README.md`.
The public `CrispyNuggetD/42_Singapore_SUTD` shell installer consumes this block
when LAN42 is missing. It is separate from this repository's dailylogin helper.

- When a feature, command, requirement or availability changes, update that
  README block in the same change. Advertise implemented features only; never
  claim transfers occur before explicit group/folder consent. Keep the list short.
- Run `python3 -m unittest discover -s tests -p test_shell_features.py`.
- Online installers read the current upstream README; publishing the README
  update makes it available without a separate hard-coded feature list.
- For the offline installer snapshot, if the shell helpers clone is available,
  run `python3 /path/to/42_Singapore_SUTD/lan42_recommend.py --refresh-features
  --clone /path/to/42sg-campus-lan`. Review and commit the changed snapshot in
  that public shell repository. Otherwise mention the offline snapshot update
  in the handoff. Never copy private settings or credentials across repositories.

These repository instructions, not a particular model, account or API key,
carry the workflow to fresh agent sessions.

## Standalone tmux launcher

`useful-scripts/tmux_workspace.py` is a vendored copy of the canonical
`daily_terminal.py` in `CrispyNuggetD/42_Singapore_SUTD`. It lets standalone LAN42
users get the same desktop/tmux behavior without installing the full shell suite.
Do not maintain separate fixes in the generated copy: edit the canonical helper,
run its `test_daily_terminal.py`, then copy it here and run
`python3 -m unittest discover -s tests -p test_terminal_setup.py`.
`open_terminal.py` prefers an explicitly configured shared helper and otherwise
uses this bundled copy. Preserve separate LAN42 sessions and normal Mac/Linux
maximizing; never nest tmux or inject commands into existing user shells.

## Local uwu command

`/uwu` is a local opt-in sound test; `/uwu LOGIN` is a private, rate-limited poke.
A recipient controls notification permission and sound. Never let a sender enable
another user's sound, and never make the poke resident/persistent: expiry is two
seconds with explicit close on Linux and an app-owned transient panel on Mac.
Tests must mock notifications/audio/network delivery; never poke a real student
as a test. Keep the exported README feature excerpt current.

## Trusted announcements and host discovery

`announcements.py` owns server-side moderation. Only the API host's local
capability or verified configured owner login may approve/publish; never infer
privilege from guest names, mesh gossip or client-supplied role fields. Student
requests quote the authenticated Intra login and immutable submitted text.
`announcement_client.py` polls only pinned TLS and the existing fingerprint-
checked seat locator. Do not promote arbitrary peers, replace certificate pins,
open OAuth automatically, or overwrite students' guest nodes on host recovery.

Desktop approval and broadcast paths are privileged, separate from ordinary
chat mute. Never turn an announcement into executable update/shell instructions.
Keep queue/rate/expiry bounds and per-machine popup deduplication. Tests must
mock GUI actions/network outside loopback; use temporary config roots and fake
OAuth identities. Run test_announcements.py plus auth/TLS, client, notification,
and mesh tests. Update the exported README feature list and external offline
snapshot in the same change. Do not send a real campus announcement as a test.

## Local terminal commands and audio controls

`local_console.py` handles typed `!` commands and private per-computer input
history. Shell execution must stay in the keyboard-input path, never in server
message handlers. Preserve terminal restoration and interactive stdin. History
must exclude consent/wizard answers and stay bounded in private mode-600 files.
`volume.py` is shared by `/volume` and the shell's `adjust_volume`; keep native
GNOME/PulseAudio/PipeWire and macOS controls consistent. Uwu sound permission and
permission to raise muted system output are separate. Do not test with real
shell execution, audio playback, volume changes or notifications: mock them.
Numeric `/track` refers to the displayed campus roster, with explicit confirmation
of captured identities/seats. Never silently retarget a changed desk occupant.

KoelDrop is a standard feature: do not restore experimental.json gates. Keep
signed-in campus admission, pinned transport, group/folder consent and per-file
receive/delete permissions. Tests use controlled campus evidence and temporary
folders, never real students or live transfers. `lan42_restart` may send the
literal `/restart` only to verified LAN42 client processes in tmux, never shells.


## Public website and the /help guide

`docs/quick-guide.html` is the canonical self-contained visual guide opened by
`/help` and published as the GitHub Pages homepage. `website/build.py` generates
its runtime HELP section from the AST of `client.py` and a full handbook from
README.md. Keep curated guide cards aligned when commands change. Run
`python3 website/build.py --refresh-guide` after editing HELP; do not hand-edit
the generated runtime-help block. Update README and guide together. Run
`test_website.py` with `website/requirements.txt` installed. `_site` is generated
and ignored; never copy configs, caches or credentials into it. Pages rebuilds
from main via `.github/workflows/pages.yml`; owner must enable Pages with
Source: GitHub Actions once. Do not claim a deployment is live before verifying.

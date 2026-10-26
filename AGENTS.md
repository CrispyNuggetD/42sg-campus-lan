# LAN42 development and cross-repository shell integration

## Keep the installer's feature list current

The canonical short feature list is the section between
`<!-- shell-installer-features:start -->` and
`<!-- shell-installer-features:end -->` in `README.md`.
The public `CrispyNuggetD/42_Singapore_SUTD` shell installer consumes this block
when LAN42 is missing. It is separate from this repository's dailylogin helper.

- When a feature, command, requirement or availability changes, update that
  README block in the same change. Advertise implemented features only; never
  list disabled KoelDrop transfers as available. Keep the list short.
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

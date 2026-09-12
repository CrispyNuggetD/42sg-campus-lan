# Campus deployment task

On the owner's enrolled campus device:

1. Clone https://github.com/CrispyNuggetD/42sg-campus-lan.git into
   ~/Documents/42sg-campus-lan, or git pull --ff-only an existing clean clone.
   Preserve local edits; do not reset or overwrite another repository.
2. Run sh setup.sh. Launch directly from ~/Documents/42sg-campus-lan/lan42.sh.
   Do not install anything into /bin or ~/.local/bin or add a bin path to PATH.
   Setup appends the lan42 zsh helpers by default; --no-zsh opts out; it preserves the
   user's existing shell configuration and sources the file inside this clone.
3. Inspect the active dailylogin/syncdocs functions. The current public SUTD
   additions already scan Documents when pullotherrepos=1. Verify the LAN clone
   is included. If the active functions are older, add a minimal fast-forward-only
   LAN pull and a call to lan42_window to dailylogin without replacing unrelated customizations. Do not run
   the whole dailylogin workflow just to test this (it opens other applications).
4. Run tests and lan42 --version. Verify Python/curses and whether notify-send is
   available; do not install system packages or change firewall settings.
5. Verify version 0.2.2 or newer. Check seat-based joining: c1r2s3 maps to
   10.11.2.3; c2r4s9 maps to 10.12.4.9. Plain lan42 join asks seat questions.
   Check that visiting another node keeps the local node alive, and quitting the app
   stops only its own node. Old protocol-1 servers need a deliberate restart; report
   them rather than stopping a pre-existing server without checking its ownership.
   Report the LAN address and exact host/join commands. If a graphical session is
   available, perform a local notification test and terminal smoke test, closing
   only processes created for the test. Do not message/invite other students.
6. Leave Intra sign-in as the guest-mode placeholder. Do not copy API secrets,
   browser state or credentials into the repository or task report.

Return a concise deployment report, including blockers and whether actual
multi-computer LAN play still needs testing. No feature expansion is requested.

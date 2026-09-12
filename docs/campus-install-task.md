# Campus deployment task

On the owner's enrolled campus device:

1. Clone https://github.com/CrispyNuggetD/42sg-campus-lan.git into
   ~/Documents/42sg-campus-lan, or git pull --ff-only an existing clean clone.
   Preserve local edits; do not reset or overwrite another repository.
2. Run sh setup.sh and ensure ~/.local/bin is on PATH, adding a small idempotent
   block to ~/.zshrc only if needed. Do not replace the user's shell configuration.
3. Inspect the active dailylogin/syncdocs functions. The current public SUTD
   additions already scan Documents when pullotherrepos=1. Verify the LAN clone
   is included. If the active functions are older, add a minimal fast-forward-only
   LAN pull to dailylogin without replacing unrelated customizations. Do not run
   the whole dailylogin workflow just to test this (it opens other applications).
4. Run tests and lan42 --version. Verify Python/curses and whether notify-send is
   available; do not install system packages or change firewall settings.
5. Report the LAN address and exact host/join commands. If a graphical session is
   available, perform a local notification test and terminal smoke test, closing
   only processes created for the test. Do not message/invite other students.
6. Leave Intra sign-in as the guest-mode placeholder. Do not copy API secrets,
   browser state or credentials into the repository or task report.

Return a concise deployment report, including blockers and whether actual
multi-computer LAN play still needs testing. No feature expansion is requested.

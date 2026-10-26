# Server releases

The first public beta is **2.0.0-beta.1**, effective 27 October 2026 at 00:48 SGT.
V2 honours the API-backed product milestone. V1 describes the early connectivity,
navigation and games concept; it does not invent a released 1.0.0 tag. Historical
notes are reconstructed from Git commits and marked accordingly.

`campus_lan/release.json` is the single version/date/history source. The server
advertises VERSION independently of PROTOCOL; change PROTOCOL separately when
wire compatibility changes. Startup and `/changelog` use the same metadata.

On each main push, the Pages workflow compares a fingerprint of shipped runtime
files to the last release. README, docs, tests, website and workflow-only changes
cannot bump the server. Python whitespace/comments/docstrings are ignored.
Runtime scripts, sounds/assets, dependencies, game code and configuration defaults
count. A volume default change from 50 to 30 therefore produces a patch release.

For commits that touch runtime files:

- `feat: ...` / `feat(scope): ...` means an additive feature: minor increment.
- `fix: ...`, parameter changes and otherwise unclassified changes: patch increment.
- `feat!: ...`, `fix(scope)!: ...` or a `BREAKING CHANGE:` footer: major increment.
- The highest applicable category wins for a batch. A net unchanged runtime has no release.

Examples after the initial beta: a fix yields `2.0.1-beta.1`; a feature yields
`2.1.0-beta.1`; a breaking change yields `3.0.0-beta.1`. Beta remains explicit until
an intentional stable graduation. Semantic intent cannot be inferred reliably
from code alone: agents must use accurate commit subjects. Never label functional
work as docs-only. Non-Python source-only comment changes may conservatively count
as patches; keep these out of runtime commits when practical.

CI prepares metadata, validates it, then commits the generated changelog and
creates an immutable `vVERSION` tag. A failed check prevents publication. It builds
Pages from that same checkout. GitHub's workflow token must be allowed to write
repository contents. Existing tags must never be moved. Release-only commits are
idempotent and workflow-token pushes do not recursively start workflows.

For local review: `python3 tools/release.py` after committing runtime changes.
Do not manually edit version strings throughout the repo. README shows the beta
entry milestone; current version comes from startup, `--version`, or `/changelog`.

## Release popups and calendar updates

Server versioning and desktop alert frequency are independent. Clients coalesce
changed host versions for 30 minutes and allow one release popup per rolling
24 hours per computer, shared by HQ/game windows and preserved over restarts.
Exam quiet defers popups; first contact only establishes a baseline.

A newly fetched exam date is an expiring calendar-setting update, not a software
patch or security update. It changes the queued audio window without a Git pull,
server-version increment or executable update message. See [exam quiet](exam-quiet.md).


## Website design milestones

Meaningful public-site interaction and design changes are recorded in
[Website design history](website-changelog.md). A design milestone can establish
a direction for the future TUI without being a server release or claiming the
TUI work has shipped. Site-only work remains excluded from the server fingerprint.

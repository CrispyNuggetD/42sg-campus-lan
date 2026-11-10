# Last observed and checked systems

Snapshots are observations of the labelled computer, never a compatibility claim.
They include OS version/build/kernel, CPU, logical CPU count, RAM and filesystem
capacity/free space for system, home, goinfre/sgoinfre and NAS where present.
Filesystem free space does not establish a user's quota. NAS may be mounted under
another path; unavailable means not observed by the collector.

## 42 campus terminal

Observed on the actual hnah Ubuntu campus terminal on 28 October 2026 SGT,
LAN42 2.8.8-beta.1. See `system-snapshots/42-campus.json` for the current
Ubuntu/kernel, CPU/RAM and filesystem observations. The collector includes
system, home, local goinfre and shared sgoinfre/NFS capacity/free space. The
separate NAS label was not found; sgoinfre is the observed shared NFS mount.
These are filesystem capacities, not disk hardware or individual user quotas.
No server addresses, hardware identifiers, credentials or private paths are
included. This snapshot supersedes the earlier Mac-prepared placeholder.

Campus validation on Python 3.10.12:

- 138 targeted local/mocked tests passed: access policy, legacy migration,
  auth startup/TLS/locator/diagnostics, announcements, client, notification
  preferences, profile lookup, tracking, mesh, KoelDrop flock/file-sharing and
  shell feature checks. Tests used isolated config roots/fake provider data.
- Separately from tests, normal owner-host initialization verified the existing
  legacy hnah SG owner identity, preserved TLS trust/credentials and initialized
  its access policy. The user service became active and its pinned TLS lobby
  answered a protocol ping. No student notifications or announcements were sent.
- Root cause: Python 3.10 rejects an empty query passed to strict `parse_qs`.
  Skipping query parsing when no query exists restores allowed campus metadata
  and membership-proven profile reads, including owner startup migration.
  Nonempty queries still use strict parsing and the existing SG-only allowlist.
- This confirms host startup and secure endpoint availability, not completion
  of a fresh browser OAuth authorization by the owner.

## Maintainer Mac

See `system-snapshots/maintainer-mac.json` for the observed OS and hardware.
Beta checks on 27 October 2026 (SGT), version 2.0.0-beta.1:

- Release integration tests (real temporary Git repository), semantic classification,
  local `/changelog`, completion, client, about, website build and exported shell
  feature tests passed. Offline shell feature snapshot tests also passed.
- Full Python suite: 258 tests, six skipped; one failure and one error. FORKNITE
  native-death assertion also fails on untouched main at 51eda1d. TLS relocation
  test cannot bind 127.0.0.2 on this Mac. These checks do not certify Linux campus
  behavior; the campus follow-up should record its own results.
- KoelDrop tests use a physical temporary directory because macOS /var is a
  symlink and the path safety checks intentionally refuse symlink traversal.
  Tests use isolated config/temp state; no students were poked.
- Dependency environment: Python 3.14, website requirements and auth requirements.

## Access-policy implementation validation — 27 October 2026 SGT

The credential-owning maintainer Mac was explicitly enrolled using hnah's verified
Singapore identity (UID 234449, campus 64); the private approval files remain
outside Git. No campus machine was automatically enrolled, and no VPN or public
forwarding was installed. At this initial implementation stage, existing campus API hosts required manual
enrollment. The subsequent startup-migration update below supersedes that step
for the legacy managed hnah campus host.

The access-policy change passed 110 targeted tests (one platform skip), including
real loopback/TLS announcement checks, guest socket denials before API/cache
access, forged-role rejection, SG profile scope checks, independent admin/operator
roles, host revocation, local owner views, and existing mesh/KoelDrop behavior.
The broader suite before the final two administration tests ran 268 tests with
six skips and the same two previously documented Mac failures: 127.0.0.2 binding
and the native FORKNITE death assertion. Provider responses were mocked in tests;
config/temp roots were isolated from owner credentials. Bootstrap verification
was a separate explicit live owner lookup, not a test of the campus deployment.

## Legacy startup migration — 27 October 2026 SGT

LAN42 now initializes the owner host after launcher updates. The shell no longer
runs a potentially stale auth module before the launcher can pull. The legacy
managed school host can initialize policy automatically under the real hnah OS
account and verified campus/TLS/SG conditions; existing or revoked policies and
new installations are never automatically approved. Migration/startup tests use
isolated configs with fake credentials and mocked provider/system operations;
this Mac is not evidence that migration ran on the school terminal.

## macOS short-call playback — 27–29 October 2026 SGT

The Mac playback path uses the official `uwu.wav` PCM edition of the unchanged 0.85-second call,
with 200 ms lead-in and 250 ms tail silence. All 29 targeted sound, uwu and exam
quiet tests passed with playback mocked. The PCM call samples match the published
decoded Ogg digest exactly. Native afconvert also decoded the original Ogg to
all 37,485 frames, so inspection did not establish an Ogg decoding failure.
Audible playback and the reported device-specific truncation still require
user confirmation; no real sound or student notification was triggered by tests.

## Own-operator login-hour API — 27 October 2026 SGT

The maintainer Mac completed a live, explicitly requested hours fetch as the
configured API login hnah, independent of its OS username. Both hours and
before-noon reports rendered verified API intervals. The new route uses
operator-only campus-64 locations with bounded range/pagination, not a guest
route. No credentials or raw location records are published here.

The 162-test policy/auth/profile/client/network/tracking/mesh/KoelDrop/website
selection had 160 passes, one skip and the previously documented Mac failure
binding 127.0.0.2. Website build passed. The shell's 14 login-hour tests pass,
including Linux hnah fallback and nonfatal skips on Mac/other accounts.

## No-sudo dependency setup — 28 October 2026 SGT

Setup now checks the active Python 3.9+ and curses, reuses existing tmux, or
attempts user-level package extraction on Ubuntu/Debian. The rootless installer
tests use fake package tools; terminal setup, exported feature and website tests
passed on the maintainer Mac, and the website build passed. These checks do not
prove the package mirrors, execution permissions or dependency availability on
today's school terminal. No sudo, system package install, maintainer scripts or
new campus snapshot was run. Python itself and optional host/game dependencies
are not silently installed by the lobby setup.

## Prompted dependency assistance — 28 October 2026 SGT

Missing Python/curses now offers explicit [y/N] user-level Python recovery via
uv, and missing tmux asks separately before downloads. Blank/no/EOF declines.
Python recovery and consent tests use fake uv/package tools; terminal setup,
feature and website checks plus the website build passed on Mac. No runtime
was downloaded in tests and current campus network/permissions remain unverified.

## Mac remote-approval test mode — 28 October 2026 SGT

Opt-in remote guest admission is Mac-only and requires an explicit private
192.168.x.x listener bind on an existing approved host. Grants are per live
socket, with a private local controller and separate genuine Intra session state.
Tests use fake identities/source addresses, temporary configuration and local
Unix/loopback sockets. No Ignis/VPN connection, real remote invite, live listener
or host/firewall configuration change was made. Twelve focused remote tests pass.
The broader 193-test selection had 191 passes, one skip and the previously
documented Mac 127.0.0.2 bind error. Website tests/build pass. End-to-end VPN
routing, extra browser-game ports and actual user operation are unverified.

## Host reload consent — 28 October 2026 SGT

Revision changes alone no longer feed the package reload generation. The Mac
and Linux dailylogin/standalone pull paths ask [y/N] before publishing a reload
marker; No, blank input, EOF and unattended execution defer it. Installation
Allow all is not accepted as reload permission. Existing /update requests ask
before restarting other clients/services; its initiating terminal can reopen.
Updater/consent, terminal, shell handoff, feature and website tests/build passed.
No live host or student connection was restarted during validation.

## Campus account roaming — 30 October 2026 SGT

On the actual Ubuntu campus terminal, the explicit hnah account hosting grant
restored current-seat auth startup without adding a machine fingerprint. The
managed service became active and its pinned TLS protocol readiness check passed.
The 189-test access/auth/announcements/profile/client/network/tracking/mesh/
KoelDrop/notification/shell-feature/website selection passed with one skip.
The added regression covers roaming without machine enrollment, wrong OS account,
unassigned campus address, administrator revocation and removal of the grant.
This validates service readiness; interactive browser OAuth was not exercised.
The campus system snapshot was refreshed separately from these test results.

## Cluster identity colors and portable preferences — 30 October 2026 SGT

The campus Linux selection of 214 policy/auth/TLS/client/network/tracking/mesh/
KoelDrop/notifications/preferences/cluster/settings/website checks passed.
Website build and guide refresh passed. Cluster 1/2 use cyan/amber labels and
trusted self entries have a contrasting You badge. Portable preference tests
cover Linux/macOS config roots, Git permission restoration, export/import,
conflict preservation and exclusion of credentials/device consent. The local
private settings folder was linked successfully. Existing running curses
windows require reopening to load the new rendering code.

The managed host's public flock was already ready and starts automatically;
its normal retry loop remains enabled. At the owner's explicit request, the
previous saved always-join preference and sgoinfre directory were restored on
the current seat. The existing HQ then reported a successful flock join.
KoelDrop sharing is not a backup of its local folder contents.

Account-scope follow-up: notification/search/audio choices and KoelDrop join
preferences no longer use a seat hostname. Existing private choices migrate to
the account namespace, preserving their originals. Regression checks cover seat
changes and distinct account keys. Self-upload replay notices are filtered by
numeric author UID; manual recovery remains available without automatic download.

The final expanded 281-test selection (including file sharing, popup, local
console and web-search cases) passed on this terminal. Own-upload replay tests
confirm numeric UID filtering while retaining pending offers and explicit manual
recovery; another UID with the same display name is still notified. The owner's
HQ was reloaded through its verified /restart path to activate the changes.

Clock tools use account-scoped portable schedules, GMT+8 viewing by default and
explicit UTC-view metadata. UTC timestamp storage is ISO 8601 uppercase Z;
Z/z/+Z/+z aliases and decimal/colon offsets have deterministic tests. Timers
support pause/resume, alarms support daily/weekday/weekly/interval/date schedules,
and the stopwatch uses a monotonic clock with session-only laps. Schedules fire
only while HQ runs; reopening surfaces overdue schedules once without replaying
a recurring backlog. Desktop delivery uses the existing notification opt-outs.
No live alarm, notification, sound or timed file transfer was generated by tests.

Final validation: the 290-test expanded selection passed. The final timezone
view/alias refinements also passed all nine clock tests and the website build.
Timestamp display supports arbitrary explicit offsets, including decimal hours;
UTC storage is independent of the default GMT+8 presentation.

Completion validation: all 293 selected LAN42 checks passed, including combined
friend/cohort patterns and conflicting-cache handling. Cohort decoration uses
only local cache data, with no additional API request or network payload field.
The current local cache supplies the owner's inferred cohort for live rendering.

## Cluster automatic refresh — 2 November 2026 SGT

On the actual Ubuntu campus terminal, 25 cluster tests and the exported shell
feature check passed with mocked sources; no live student notifications or API
requests were sent. The cluster window polls every 30 seconds, retains its page,
waits during commands/confirmations and backs off pending requests to 120 seconds.
Sign-out and disconnect stop polling. The campus observation snapshot was refreshed;
interactive arrival detection still depends on upstream API freshness.

## FORKNITE bonus launcher — 2 November 2026 SGT

On this Ubuntu terminal, 10 FORKNITE Python tests, nine client tests, exported
shell-feature checks and JavaScript auth/sabo checks passed with fake binaries
and isolated configuration. Website tests passed with one dependency-related
skip. Bonus-to-mandatory switching preserved native stdout in round logs.
A loopback pipe check delivered native-format meal/death lines to browser events;
its teardown timed out while stdin remained open and exited after the test closed
stdin. No real student room, notification or live C project was used for testing.


## CORE external launcher — 10 November 2026 SGT

On the actual Ubuntu campus terminal, the small CORE launcher uses fixed public
upstream links and an optional separate source clone. Launcher tests mock
browsers, Git and terminal startup; checks cover popup consent, no session
forwarding, destination preservation and Linux/macOS-neutral command arguments.
The existing separate upstream clone was recognized without updating it. This
is not a validation of upstream builds, real competition sign-in or macOS GUI
launching. No live browser, game, student session or container was started.

All 24 launcher/client/completion/shell-feature/website checks passed, including
the full site build with its pinned Markdown dependency installed in a temporary
virtual environment. Four external installer snapshot checks also passed.

## Cached cluster photo preview — 10 November 2026 SGT

On this Ubuntu campus terminal, 27 cluster checks, three website checks, the
exported shell-feature check and the full site build passed. Photo tests mock
the cache and desktop process; no student photo, API, browser or notification
was used. Tk and Pillow imports succeeded locally. Desktop popup placement and
focus behavior have not been interactively validated; macOS is untested.

## Cached cluster display names — 10 November 2026 SGT

On this Ubuntu campus terminal, 56 selected checks passed: five isolated name-cache
checks, 28 cluster checks, 15 access-policy checks, one exported feature check,
three website checks and four external installer checks. The full site build
also passed. A live explicit name-only campus-list refresh completed, storing
only directory-matched display names privately outside Git. The first cache
write was refused due to parent permissions; a dedicated private directory and
a preflight check were added before the successful repeat. Total live work was
32 campus-list GETs and two OAuth requests, no individual profiles or images.
Name caption placement has not been visually checked on the desktop; macOS
remains untested. No student names or raw responses are included in this repo.

## Copyable cluster photo details — 10 November 2026 SGT

The popup has selectable read-only text and explicit Copy name, Copy Intra
and Copy details buttons. Details contain the available name, login and Intra
profile URL; missing names disable only Copy name. No automatic clipboard writes
or API calls were added. All 37 selected cluster/name/shell-feature/website
checks and the full site build passed. A hidden Tk smoke check confirmed
read-only Unicode selection and copy payloads without writing the clipboard;
visible desktop interaction and macOS have not been validated.

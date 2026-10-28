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

## macOS short-call playback — 27 October 2026 SGT

The Mac playback path now uses a PCM WAV copy of the unchanged 0.85-second call,
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

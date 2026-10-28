# Last observed and checked systems

Snapshots are observations of the labelled computer, never a compatibility claim.
They include OS version/build/kernel, CPU, logical CPU count, RAM and filesystem
capacity/free space for system, home, goinfre/sgoinfre and NAS where present.
Filesystem free space does not establish a user's quota. NAS may be mounted under
another path; unavailable means not observed by the collector.

## 42 campus terminal

**Current snapshot: to be updated by the 42 terminal.** This beta preparation ran on the maintainer's Mac.
The current 42 terminal's CPU, RAM, Linux distribution/version and home/NAS storage
have not been verified in this checkout. Do not invent these from general 42 lab
specifications or call the Mac campus hardware. No beta-on-campus validation is
claimed. Archived private terminal command outputs show Ubuntu 22.04.5 LTS on
12 September 2026; storage observations show about 186 GiB for the root
filesystem, a separate 4.7 GiB home filesystem, and a shared 13 TiB sgoinfre
NAS filesystem. These are historical filesystem capacities, not disk hardware
or individual quotas. Free space is deliberately not carried forward.
CPU, RAM, current OS build and beta validation: **to be updated**.
Only these non-sensitive facts were transcribed; private logs stay private.

From the actual terminal, run the collector described in AGENTS.md, review its
output, and record command/test result, server version and date here. Refresh the
snapshot after any OS update. To collect a differently mounted NAS, extend the
explicit paths in the collector; do not include server addresses, account names,
serial numbers, credentials or private file listings.

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

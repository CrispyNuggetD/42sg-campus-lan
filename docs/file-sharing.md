# KoelDrop and the uwu bird

[← LAN42](../README.md) · [All guides](README.md)

- [KoelDrop — the uwu bird, but it brings files](#koeldrop--the-uwu-bird-but-it-brings-files)
- [The host-started 42 Singapore flock](#the-host-started-42-singapore-flock)
- [Private invitation groups](#private-invitation-groups)
- [Optional uwu bird](#optional-uwu-bird)
- [Sound tests and private pokes](#sound-tests-and-private-pokes)

## KoelDrop — the uwu bird, but it brings files

A little campus file courier inside LAN42. **Files in your nest, only if you say
yes.** The receive notice is `🔊 uwu, dthoo sent you funny.txt`.

## The host-started 42 Singapore flock

The approved API host starts its public **42 Singapore flock** automatically on
normal startup. No dailylogin one-off or manual `/koel create` is needed. “Public”
means discoverable through the configured pinned host—not anonymous access.
Joining requires the existing verified SG account, active primary Singapore
membership, fresh workstation login and a real connection from that campus seat.
An invitation on an anonymous campus HQ says sign-in is required; clicking it
starts the normal sign-in flow and confirms joining only after verification.
Offsite users cannot join.

The invitation offers **Join once**, **Always join** and **Never show again**.
Native buttons depend on desktop support; the same choices are always available
in HQ:

```text
/koel flock once
/koel flock always
/koel flock never
/koel flock ask
/koel flock status
/koel flock-dir "~/KoelDrop"
```

Once/always shows the service directory and explains uploads before joining.
Always remembers consent for this trusted host and verified account on this
computer; later sign-ins and host returns can rejoin without asking again.
It never forces a browser sign-in, silently replaces another active/joining group,
or grants automatic file receipt/deletion. `/koel flock ask` stops future automatic
joins; `/koel leave` stops current uploads. Never suppresses future invitations
but does not leave a group you already joined.

On campus, the default setup offers **[y/N]** to put KoelDrop in your existing
personal `sgoinfre` storage and create `~/KoelDrop` as a convenience symlink.
Yes saves home quota; No keeps home storage. This choice is remembered.
Existing paths are never replaced. Workers use the approved real target directly;
other symlinks inside shared folders remain refused. If personal sgoinfre is not
available, normal home/custom-directory setup remains available. Campus storage
availability and retention follow campus policy; these copies are not backups.

The chosen service root can already contain files: those files are not scanned.
The first join each Singapore calendar day creates a dedicated subdirectory:

```text
~/KoelDrop/42-singapore/2026-10-27/
```

Same-day reconnects, including after lunch or a host restart, reuse that folder.
Files left there remain eligible for upload while joined. Only LAN42-created,
privately owned folders with a matching host/student/group marker are reused.
An unrecognized existing destination blocks joining rather than importing it or
creating more folders. LAN42 never renames folders, follows symlinks, or recursively removes them. A
configured root must support private directories, be non-hidden and outside Git.
Changing `flock-dir` affects future joins; it does not move the active folder.

**Shutdown retention:** sharing pauses when the host/flock becomes unavailable.
Uploads stop; your folder, downloads and unuploaded work stay on disk. On return,
Always can rejoin the same daily folder; a new day gets a new folder. Previous
days’ copies are not automatically uploaded into the new day. **Local copies have no expiry or automatic cleanup: you
remove them yourself when finished.** Uploaded host copies and audit history are
also retained across host restarts, subject to existing quotas. Fresh session
membership is required before anyone can read those retained files again. The
host operator must deliberately manage retained storage; startup never erases it.
The current limits remain 16 active members (including the service host), 64
reserved member namespaces, 8 MiB per file and 128 MiB retained per group. A full
quota rejects new work rather than deleting old copies.

Files added to your joined folder upload to the flock, where admitted members
can request them. Incoming files still need `/koel receive NUMBER` or a separate
explicit `/koel trust ...` whitelist. Always join never grants those permissions.
Deletions always need separate approval and keep a recoverable local backup.
`/notify flock off` hides flock invitations; `/notify files off` hides file-offer
popups; `/notify all off` also silences them. These are notification choices,
not commands to stop a previously approved transfer or leave the group.

## Private invitation groups

The owner can still create a separate group with `/koel create`, then use
`/koel invite dthoo` (or `friends` / `@LIST`). Recipients accept or decline their
numbered invitation. Accepting starts uploads from its dedicated empty folder.
Only one KoelDrop group runs in each HQ at a time.

`/koel pending` lists offers; `/koel receive NUMBER` approves a file and
`/koel reject NUMBER` declines it. `/koel trust LOGIN...` separately confirms an
automatic-receive whitelist for the current group. `/koel dir "EMPTY PATH"`
chooses a different empty folder; `/koel sync` syncs now; `/koel leave` stops
uploads and preserves copies. Group membership and file acceptance remain
separate decisions.

Transfers use the existing pinned HTTPS broker, private storage, file ownership,
version conflicts and bounded polling. Private invitation groups additionally
use recipient-bound expiring invites. [Design and permissions](file-sharing-design.md).

## Optional uwu bird

The licensed `uwu.ogg` recording is included with [attribution](../assets/sounds/ATTRIBUTION.md).
Sound is **off by default**. At each fresh LAN42 launch, `y` enables it for this
session, `a` requests always-on, and Enter leaves it off. Always-on requires:

```text
Always uwu? Are you SURE? ಠ_ಠ [y/N]
```

You can also use `/settings koel-sound on|off|always`. `off` clears any saved
always-on choice. Enabling sound never enables file sharing. D-Bus sound hints
respect desktop support and sound settings; no separate player is started.

## Sound tests and private pokes

`/uwu auto` (or `/uwu on`) enables local koel calls at a fresh random interval
of 10–15 minutes. It asks for sound permission if needed. `/uwu off` stops
the timer; disabling koel sound also stops it at the next scheduled call.
The timer applies only to this window and stops when it closes; it never pokes
other students. Repeating the command does not reset an active timer.

`/uwu` introduces the **koel**, the familiar “uwu” bird and KoelDrop’s Singapore
take on a carrier pigeon: this bird delivers your files. Once per window, it
invites you to try `/koel` or read `/koel help`; it never starts sharing itself.
It also plays one short koel call (0.85 seconds, no repeated calls) on your own computer for the running joke
or an audio test. macOS uses a native PCM copy with 200 ms of silence before
and 250 ms after the unchanged call, allowing audio hardware to start and drain.
If sound is off, it asks first; Enter keeps it off. `a` offers
always-on with the existing second confirmation. Change it with
`/settings koel-sound on|off|always`. `/uwu LOGIN` sends a private poke to a
connected person. Their notification permission and their own sound choice apply;
the toast closes after two seconds and is not resident in notification history.
Only a poke message crosses the network; each client plays its own local asset.
Pokes share the two-second direct-message rate limit.

## Add-only sharing and upload limits

The host names additions `report_dthoo_1.pdf`, `report_dthoo_2.pdf`, and so on using the verified uploader. Edits and renames add files; they do not replace or remove shared copies. The uploader sees the assigned name in HQ and gets a matching local copy; the original is kept. Other group members see receive offers through the existing pinned connection.

Shared locations allow 6 additions/minute (24 MiB); your own member folder allows 30/minute (96 MiB). These rolling limits survive reconnects/restarts. HQ explains throttling and retries. Shared deletion is disabled.

## Ubuntu desktop shortcuts

Startup asks separately about a **dock launcher** and a **Files sidebar bookmark**, skipping existing entries. Enter declines. `/koel dock` asks to pin the launcher; `/koel bookmark` (or `/koel sidebar`) asks to pin `~/KoelDrop` inside GNOME Files. `/koel favorite` remains a legacy alias for the dock launcher. Neither shortcut joins a flock or approves transfers.

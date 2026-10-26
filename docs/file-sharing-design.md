# KoelDrop — the uwu bird, but it brings files

A little campus file courier inside **LAN42**.
Files in your nest, only if you say yes.

**State: available as a standard LAN42 feature.** No experimental setting is
required. The runtime is wired to the existing pinned HTTPS broker, with verified
session and live campus-seat evidence checks. Importing modules or constructing
`start(broker, host, port)` does not bind a socket or begin folder scans.

`/koel help` describes create/invite/accept, dedicated folders, per-file receives,
explicit receive whitelists, sync and leave. `/files` and `/koeldrop` are aliases.
Only deliberate group creation/acceptance starts dedicated-folder upload polling;
recipient approval is separate. Normal approved-host startup also creates/resumes
the public 42 Singapore flock without scanning a personal folder. Members
must be signed in to that same trusted service.

The core and transport tests use temporary stores and controlled identities,
campus evidence and HTTPS request adapters. Real campus transfers and real
notifications are not used as automated tests. Cross-machine campus behaviour
still needs verification on actual participating computers.

## Host-started public flock

The normal approved auth host runs `Runtime.maintain_public`, retries unavailable
campus/storage evidence every 30 seconds, and advertises only safe flock metadata
through its existing pinned announcement poll. No new port or public forwarding
is opened. The service uses an in-process identity with a random key that is
**never inserted into Broker.sessions or delivered as a login token**. Every
service check revalidates local admin/operator/host enrollment and the same fresh
SG membership/campus-seat proof used by participants. Ordinary user sessions
remain one-hour broker sessions; owner OAuth sign-out does not impersonate or
terminate the independently running service.

`POST /v1/flock/join` accepts only the current host-selected group and epoch.
No client-supplied UID, login, scope, invitation wildcard or remote folder path
can grant membership. Campus admission still uses the real TLS socket source.
Only this recorded service flock has open campus admission; private groups keep
recipient-bound invitation admission. The existing 16-member/64-namespace,
request, file and storage bounds remain in force.

Host restart rotates the service epoch and clears membership/invites, while
retaining the same owned flock's files and audit history. It never deletes the
host's retained objects or clients' copies. Local always-join/never preferences
are scoped to the pinned certificate, verified UID and computer. An anonymous
campus client can receive a conditional invitation but must sign in and confirm
the directory/upload disclosure before any first join. Notification grants alone
cannot approve joining, receiving files, deleting or trusting new hosts.

Each join allocates a new private, empty session directory beneath the configured
service root using exclusive creation and no-follow traversal. Existing siblings
are never scanned, renamed, reused or recursively deleted. An unavailable host
stops the public courier and keeps all copies; rejoin starts fresh, without
silently re-publishing earlier local files. There is no scheduled directory
expiry/deletion. See the [user flow and retention policy](file-sharing.md).

## A group session

The group flow is:

1. The host creates a group while signed into a trusted, verified LAN42 service.
2. `/koel invite dthoo`, `friends`, or `@lunch` resolves selectors locally. Only
   the resulting recipients go to the service, not personal relationship lists.
3. An invitation notice goes to the verified recipient. Accepting a group is a
   separate decision from accepting its files.
4. The recipient chooses an empty dedicated sync folder. Its default is
   `~/KoelDrop/<host-login>/<group-id>/`. Accepting creates that dedicated folder.
5. The joined Courier polls only that dedicated folder every five seconds. File
   changes become offers; incoming bytes still need separate approval.
6. The receiving notice is `🔊 uwu, dthoo sent you funny.txt`, with the file size,
   destination and Accept/Decline controls. Enter declines. Bytes are fetched
   only after approval, unless the recipient explicitly whitelisted that user
   or a local list such as friends.
7. Changing the folder pointer requires another empty dedicated folder. Old
   copies stay where they are; the application does not silently move or erase
   existing personal files.

Native invitation delivery must use the verified TLS lobby and recipient user
ID. It must not publish invitation tokens as public chat, guest-mesh events,
URLs in logs or relationship-list metadata.

## Who gets in

A bearer invitation alone is insufficient. Admission requires all of:

- A current verified LAN42 session from the trusted broker.
- An active 42 account whose **primary** campus matches the configured Singapore
  campus. Unknown or incomplete evidence is rejected. The first prototype is
  deliberately narrower than every possible visiting/secondary-campus account.
- A fresh active Singapore computer-location record for that identity.
- A real socket source IP matching that reported seat, in `10.11.*.*` or
  `10.12.*.*`, with valid workstation row/seat components.
- TLS and an exact campus-interface binding. No wildcard, localhost, arbitrary
  private-network address or public interface is accepted by the request policy.

Evidence is cached for at most 20 seconds and rejected when older than 120
seconds. The API adapter uses the existing owner API client, including its global
request pacing. API errors fail closed. It retains only a membership decision,
seat names and the evidence timestamp, not the full fetched user profile.

Private group hosts' verified sessions and campus presence are checked too.
Their sign-out/expiry or group closure ends access. The public service flock
instead ends/pauses on service stop, revoked local host/operator authority or
loss of acceptable campus presence; no ordinary guest or owner client sign-out
can masquerade as its service identity.
Invites expire in at most five minutes and never outlive the host session. They
are stored as hashes, bound to one recipient ID/login and consumed once.
Accepted membership is tied to the recipient's current session: signing in again
requires a fresh admission (another recipient-bound invite for private groups,
or the explicit/saved public-flock choice). Invitation links must never establish new certificate
trust automatically.

Initial deployment must keep the file service with the trusted broker/operator
and use its pinned TLS identity. Do not forward the general LAN42 bearer session
to an arbitrary student's server. Delegated/multiple-host operation would require
separate audience-restricted credentials and a further review.

## What the folders mean

The visible layout is logical; remote paths do not map directly to arbitrary
paths on the host computer.

```text
<chosen group folder>/
  hnah/                 hnah writes; accepted members read/copy
  dthoo/                dthoo writes; accepted members read/copy
  funny.txt             shared root file; all members may edit/delete
  shared/               optional shared nested files
  welcome.md            generated, read-only explanation
  logs/activity.json    generated, read-only audit snapshot
```

Member namespaces remain reserved even after someone leaves, so they cannot
turn into another member's writable shared directory. Only the host issues
invitations. Hosting a group does not grant API permission to modify another
member's folder. `welcome.md`, `logs` and namespace directories cannot be
replaced or deleted through ordinary file operations.

“Execute” on a directory means traversal. Uploaded files are never given
executable permissions or automatically opened, previewed, extracted or run.
Server objects and the database are private to the OS account. Local replicas of
other people's files are marked read-only as a convenience, while ownership is
actually enforced by the service. The local OS user can still edit their own
copies or change their permissions; the service refuses publishing those edits
to another member's namespace.

## Writes, deletes and history

A new file uses an explicit create condition. Replacing or deleting a file needs
its current version; stale writers receive a conflict. SQLite transactions
serialize changes so simultaneous writes have one winner.

Every version has an immutable generated object name, SHA-256, byte count and
verified author. Deletes create tombstones, rather than destroying old content.
History records actor, time, operation, logical path, previous version and digest.
There are no tokens, private broker configuration or file contents in audit
records. The hash chain helps detect accidental audit damage; a malicious host
can rewrite its own database, so it is not proof against the operator.

A receive operation checks the current local file against its known baseline.
A local edit becomes a conflict. Replaced/deleted copies are retained privately
under `.lan42-file-backups`. Incoming installation uses an atomic no-overwrite
link, so a new file created by an editor during receive is not clobbered.
Automatic receive permissions for friends do **not** automatically approve
remote deletion. Restoring old contents uses an ordinary version-checked write.
A Git-style text diff viewer is future UI work; retained versions already make
comparison possible. File bytes and logs are not committed to Git.

## Request and storage boundaries

This is a purpose-built native HTTP dispatcher, not `SimpleHTTPRequestHandler`
pointed at a home directory. It rejects browser origins/cookies, forwarding
headers, protocol upgrades, ambiguous body lengths and transfer encoding. It has
no CORS grant, proxy route, arbitrary filesystem download, shell invocation,
remote command execution, archive extractor or automatic browser file preview.
Downloads are attachments with `application/octet-stream`, `nosniff` and a
restrictive content security policy.

Current bounds include:

- 8 MiB per file; 128 MiB retained versions per group; 512 MiB across host groups.
- 512 logical files and 4,096 write versions per group, plus bounded audit events.
- 16 accepted members; 32 pending invites; 64 reserved member namespaces.
- Eight live groups and 32 retained groups before operator cleanup is needed.
- 90 admitted core operations per user per minute and four concurrent HTTP handlers.
- Bounded headers, bodies, metadata and history pages; timed request reads.

Relative names reject traversal, hidden names, control characters, ambiguous
encoding and excessive nesting/length. Local roots are explicit, private,
non-symlink directories outside Git. Local file reads reject symlinks, hardlinks,
devices and oversized files. Credentials and unrelated home directories are not
implicitly scanned or shared.

No antivirus or content-safety guarantee is claimed. Members deliberately share
ordinary data files; accepting a file does not mean it is safe to open in another
application. There is no automatic execution to turn a received script or archive
into a command.

## Limits the app cannot enforce alone

Campus-IP checks do not prove a human is physically present. API records can lag,
and an on-campus machine can be remotely controlled or used as a TCP proxy.
Rejecting forwarding headers does not detect every transparent tunnel. The app
will not create forwarding rules or tunnels, but cannot prevent the OS user from
running another forwarding program. Strong external-access restrictions need
campus network/firewall controls.

The host is trusted with group contents. File sharing is not end-to-end
encrypted against its operator. No file service can revoke a copy somebody
already downloaded. Short sessions stop future access, not existing local copies.
Pinned TLS, current eligibility, timeouts and recipient actions remain enforced;
automated tests do not replace checking a transfer on two actual computers.

## The uwu option

`koel.ogg` is bundled with attribution in `assets/sounds/ATTRIBUTION.md`.
The sound starts **off**. A fresh LAN42 launch asks: `y=once, a=always, Enter=off`.
The always-on choice has a second prompt: `Always uwu? Are you SURE? ಠ_ಠ [y/N]`.
Only confirming that prompt saves always-on. `/settings koel-sound off` clears
it; `on` enables only this session; `always` requests the confirmation.

KoelDrop notices include 🔊 to hint that the optional sound exists. The
native notifier uses the D-Bus `sound-file` hint only for an enabled notice;
disabled ones request `suppress-sound`. It does not start a second audio player.
Desktop support and system sound settings still apply. The sound option does
not join a group or authorize incoming files.

## Review references

- [OWASP file upload guidance](https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html)
- [Python HTTP server limitations](https://docs.python.org/3/library/http.server.html)
- [Desktop notification sound hints](https://specifications.freedesktop.org/notification/latest/hints.html)
- `tests/test_file_sharing.py`: admission, invitations, ownership, path escapes,
  expiry, quota, HTTP boundaries, concurrent writes and receive conflicts.

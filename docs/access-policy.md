# LAN42 access policy

LAN42's read-only, Singapore-only API scope is the owner's application-form
commitment. The upstream student application's credentials may permit more.
LAN42 enforces the narrower policy on the credential-holding server. A modified
client cannot grant itself privileges; compromise of that server/account or the
credential itself is outside that application boundary. Never distribute the
app secret to students or game hosts.

## Roles and hosts

| Role | Admission | Permissions |
| --- | --- | --- |
| Guest | Unverified nickname | Guest chat, games and game hosting; no API-backed student data, including cached views |
| SG member | OAuth identity with Singapore campus membership | Selected views: active campus seats/tracking and bounded SG-only game profiles; ordinary room hosting |
| Admin | Numeric 42 user ID in private allowlist | Policy administration and announcement moderation; not automatically an API operator |
| API operator | Independent numeric user-ID allowlist | Read-only Singapore cache, export/download and academic directory access |
| Trusted service host | Explicit machine fingerprint enrollment | Run the official credential-bearing service; host approval is not user admin status |

Initially hnah (42 user ID **234449**) is the only admin and API operator.
Singapore campus ID is fixed at **64**. Names, guest `hnah` identities, client
`role`/`admin` flags, IP geolocation, and merely holding a 42 login do not grant
roles. Admin privileges are rechecked against the current private policy.
Membership is attested at sign-in and bounded by the existing one-hour session;
KoelDrop separately requires fresh active membership/presence and a real campus
socket address. A verified SG member may be offsite. Tailscale does not constitute
campus-presence evidence or grant extra permissions.

A game host is not an authentication/API host. Anyone can fork the software or
run a separate guest/game server. Clients recognise the official service through
the existing explicitly pinned TLS certificate, not a self-proclaimed role or
mesh advertisement. Signing in never automatically trusts another service host.

## Upgrade / enroll an existing owner machine

An old credential file alone no longer starts the official service. On the
owner-controlled machine that already holds the existing protected credentials:

```sh
python3 -m campus_lan.access enroll-local
```

This verifies hnah through the scoped Singapore campus endpoint, approves this
machine, and writes private policy/operator files outside Git. It does not start
a server, open ports, install a VPN, copy secrets, or change firewall settings.
The first enrollment assumes the local account already holding the app secret
is trusted. Possession of that secret is a powerful authority; this cannot
constrain an attacker who has compromised the credential-owning account.

The default policy file starts with **no approved hosts**. Once a policy exists,
`enroll-local` cannot reapprove a revoked machine; an existing approved admin must
approve it. The machine fingerprint hashes a local OS device identifier; raw
hardware identifiers never enter policy exports or the public repository.

```sh
python3 -m campus_lan.access show
python3 -m campus_lan.access host-id
python3 -m campus_lan.access grant admin NUMERIC_UID
python3 -m campus_lan.access grant api-operator NUMERIC_UID
python3 -m campus_lan.access revoke admin NUMERIC_UID
python3 -m campus_lan.access revoke api-operator NUMERIC_UID
python3 -m campus_lan.access approve-host HOST_FINGERPRINT
python3 -m campus_lan.access revoke-host HOST_FINGERPRINT
```

These are local policy-owner operations, not network endpoints. Grants first
verify the target's Singapore membership. The last admin cannot be removed.
Roles stay independent. Revocation is checked on subsequent requests, including
already connected secure sessions. Already delivered data cannot be recalled.
For an additional host, an admin approves its fingerprint and transfers only the
reviewed private policy through a secure administrative route; on that approved
machine, an allowed admin or API operator runs `enroll-local --uid NUMERIC_UID`. Provision
credentials separately only if required. Trusting its certificate is still an
explicit client decision. Do not use Git or the mailbox to transfer credentials.
Policy files must be owned by the service user and mode 600 in a mode-700 config
folder. Other OS users must not receive that folder. Administrators must retain
a recovery copy before revoking the last usable administration host.

## Local owner usage offsite

After enrollment, the owner can use `/clusters` and campus tracking in their
local HQ without making the Mac reachable from campus. These operations execute
locally with private operator authority; they are not API commands accepted from
a guest socket. `/info` reads the owner's private cache locally.

```sh
python3 -m campus_lan.campus_info refresh
python3 -m campus_lan.campus_info info
```

`refresh` is an explicit operator-only export/download action. It writes private
`singapore.json` and `singapore.md` files at the configured campus-data location.
Games cannot initiate that download. Cached random-game selections are checked
again through scoped profile lookup before being returned. Offsite guest nodes
and foreground auth hosts default to localhost. On-campus guest nodes retain
LAN binding; the managed auth service binds the detected approved campus seat.
An existing listener only changes binding on restart. No public forwarding or
Tailscale setup is performed by this change.

## API boundary and data handling

There is no client-supplied upstream URL, method or campus override. Student-data
operations are GET only, through an allowlist: campus 64 metadata, campus 64 users,
active campus 64 locations, and an individual profile only after the scoped campus
endpoint confirms its ID. The returned detailed profile must also confirm SG
membership. Global users/cursus enumeration, arbitrary paths, duplicate query
parameters, writes and non-SG campus IDs are refused before requesting a token.
OAuth token issuance/exchange/revocation may use POST; these are authentication
operations, not writes to student records. OAuth `/me` is used only to identify
the consenting account and check SG admission; its raw profile is not retained.

Queries are paginated with 100 records/page and at most 50 pages/5,000 records per
operation. The existing cross-process two-request/second pacing and retry bounds
remain; game profiles allow 300 uncached lookups/hour per server and a 60-second
minimal-profile cache. Seat snapshots use the existing 30-second shared cache;
client tracking polls about every five minutes. These are limits, not permission
to collect everything the upstream credential can access.

Students receive only login/seat or login/avatar views. Bulk academic exports and academic game filters are
operator-only. Legacy environment-secret guest presence polling is removed.
The local avatar download panel and API image fetch CLI also require operator
permission. Existing private academic exports remain until the operator removes
or refreshes them; no historical directory is silently deleted during upgrade.
Cache/export permission does not authorise indefinite retention, redistribution,
or future use outside the stated purpose. This implements the application policy;
it is not a certification of PDPA compliance or of 42's terms.

# Remote guest approval on the owner Mac

[All guides](README.md) · [Access policy](access-policy.md)

This is an opt-in test/guest mode for an already approved API host on macOS.
It does not pretend that a VPN is campus presence. Default startup is unchanged;
Ubuntu/campus activation is deliberately refused for this first version.

## Three independent facts

| Connection | Display | Permissions in this mode |
| --- | --- | --- |
| 192.168.x.x, not yet approved | Waiting request, expires after 60 seconds | No lobby admission |
| Host approved, no Intra session | Green, **Remote approved / unverified** | Chat, DMs and ordinary games |
| Host approved, genuine Intra session | Green, **Remote approved / 42 signed in** | Same remote chat/game scope; sign-in does not unlock campus services |
| Any other non-loopback source, including 10.8.x.x and campus seat ranges | Rejected by this remote listener | None |

Loopback remains available to the local authenticated host. Ordinary campus-mode
startup keeps its existing rules. This does not redefine school networks:
the current seat-address mapping uses 10.11/10.12; no 192.168 connection gets a
campus seat even if its client supplies a campus-looking hostname. Source IP is
read from the actual socket; client-supplied approval/identity fields are ignored.

Green means host-approved, not Intra-verified. Unauthenticated names receive a
`guest-` prefix; genuine Intra names come only from validated sessions. Remote
approval does not grant API access, campus rosters/tracking, API-backed game
profiles, academic exports, announcements control, or KoelDrop/flock access.
Remote HTTP access is limited to sign-in lifecycle endpoints, not campus data.
File sharing remains separate and is not part of this first guest mode.

## Host: explicitly enable for this run

Keep existing host approval and TLS configuration. From the clone, on the owner
Mac, choose the Mac's actual VPN/private address (replace the example):

```sh
python3 -m campus_lan.auth_server serve --bind 192.168.42.10 --remote-guests
```

Do not combine this with `--current-seat`. The bind address must be an actual
192.168.x.x address assigned to this Mac. No firewall, VPN, routing, certificate
pin or private configuration is changed by this command. It fails if another
host process already owns the configured ports; stop that existing instance
locally before starting this explicitly enabled mode. Default broker/lobby ports
are 31416/31417; use your configured lobby port in management commands.

The host prints a request ID when an eligible connection arrives. In another
terminal under the same host OS account:

```sh
python3 -m campus_lan.remote_access --port 31417 list
python3 -m campus_lan.remote_access --port 31417 approve REQUEST_ID
python3 -m campus_lan.remote_access --port 31417 deny REQUEST_ID
python3 -m campus_lan.remote_access --port 31417 revoke REQUEST_ID
```

Approve/deny resolves one pending request. Revoke closes that active connection.
Approval is consumed by one live socket, not saved as an IP rule. Another lobby
or game window requests approval separately; reconnects and service restarts need
new approval. Pending requests expire in 60 seconds. There are pending/active
capacity limits and a per-source request cooldown.

Management uses a mode-600 local Unix socket in a mode-700 private configuration
subdirectory. There is no network guest approval endpoint. Host restart removes
in-memory grants. After an unclean crash, a stale control socket may need local
removal after checking that its old host is no longer running; setup never
silently replaces another host's controller.

## Guest: connect without sharing a secret

First import the host's **public** trust file and confirm its certificate
fingerprint through the existing trust workflow. If its private address changed,
relocate the existing pinned endpoint using the normal host-selection workflow;
never replace certificate trust because an IP is allowlisted.

Then, replacing the example with the matching pinned host address:

```sh
python3 -m campus_lan.remote_access --port 31417 join 192.168.42.10
```

This explicitly requests guest entry over pinned TLS; it cannot fall back to a
plaintext or untrusted server. If a valid saved Intra session exists, the host
validates it separately. Otherwise entry is unverified until real sign-in.
For real OAuth sign-in, use `/signin` in your normal local HQ first, then request
remote entry again. Opening a game window creates a separate connection and
therefore requires another host approval. Games using extra browser ports also
need normal reachability over the VPN; approval does not create routes or open
ports. Permissions cannot guarantee network reachability.

## Validation and rollout

Tests use fake identities and socket sources, temporary configuration and local
Unix/loopback connections only. No real student was invited, no live host was
started, and no VPN was configured. Current Ignis routing and end-to-end remote
use still need a deliberate test. Permanent grants, broader subnets, Ubuntu
activation and additional feature permissions need a future policy change.

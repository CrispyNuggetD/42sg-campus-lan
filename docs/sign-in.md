# 42 sign-in: owner setup and student use

LAN42 v0.6.0 has a TLS-protected shared lobby for verified 42 accounts. The
existing guest mesh remains available. Only the protected lobby displays
green **42 Verified** identities. A guest node's claims are never sufficient
to authenticate a player.

Students sign in on **42's website in their usual browser**. LAN42 does not
collect student passwords, authentication cookies, MFA codes, or student API
keys. The host uses the owner's **existing OAuth application**, not a new app.
One trusted host holds the app client secret; students receive only public
endpoint/certificate information and a short-lived LAN42 session.

## Host owner: configure once

Use an owner-controlled campus login that remains online while students play.
The owner's `dailylogin` moves the host to the current seat automatically.
Its private configuration directory is
`~/.config/42sg-campus-lan/` (or `$XDG_CONFIG_HOME/42sg-campus-lan/`). The directory
must be owned by the running user and mode **700**; private files must be **600**.
Do not put that directory, app secrets, sessions or TLS private keys in Git,
mailboxes, shared folders, or student installations.

The app must have this exact registered redirect, which is already used by
the owner's existing app:

```text
http://localhost:31415/callback
```

The localhost address refers to **each signing-in student's own computer**.
It is not an HTTP endpoint on the shared auth host. The host's HTTPS broker
exchanges authorization codes using the app secret.

The owner needs Python 3.9+ and `cryptography` to generate the TLS certificate
(`python3 -m pip install -r requirements-auth.txt` in your chosen environment).
Guest clients, student sign-in, and the running broker use the standard library.

Import an existing, private credential file with these variable names:
`FT42_CLIENT_ID`, `FT42_CLIENT_SECRET`, `FT42_REDIRECT_URI`. The parser reads the
file as data; it never sources or executes it. No secret belongs in command
arguments or terminal output.

```sh
cd ~/Documents/42sg-campus-lan
python3 -m campus_lan.auth_server setup \
  --credentials '/absolute/path/to/private/credentials.env' \
  --host 10.12.4.14
```

For initial setup, use the owner's current campus seat IP. Later `dailylogin`
runs detect `c1rXsY`/`c2rXsY` and verify that its mapped IP belongs to the local
computer before starting the service.
The command generates a TLS key/certificate, imports the app into private
configuration, and prints only the public certificate fingerprint. The
certificate is valid for 180 days; there is no automatic certificate trust
or renewal. Seat moves keep this same certificate and key. The trust file
records `server_name` as the stable TLS identity, separately from the current
TCP address. Both pinned-certificate and hostname verification remain enabled.
Replacing an expired certificate still requires owner-approved trust distribution.

Start it on the current seat (also done by the owner's `dailylogin`):

```sh
python3 -m campus_lan.auth_daily
```

This installs/reuses `lan42-auth.service` under the user's service manager.
Only an account with private `auth-server.json` starts a host; other students
skip this step. The service binds the detected campus IP. Repeated runs on
one seat reuse a running service and preserve matches. A move updates the
endpoint and starts a fresh service; existing sessions and hosted matches do
not migrate. With the shared home directory, the old host notices the generation
change within about a second and exits normally. A service started on the wrong
seat exits rather than bind or advertise another seat's address. This requires
the private configuration to follow the owner between seats; no credentials
are copied through Git, a mailbox, or to another student's account.

For a foreground service or non-campus testing, the explicit command remains
`python3 -m campus_lan.auth_server serve --bind ADDRESS`. Automatic seat detection
is deliberately limited to 42 campus hostnames, and fails if the address is not
assigned to the computer. `dailylogin` must reach its enabled LAN42 step; startup
failures earlier in the shell workflow still stop it as documented there.

It uses **HTTPS 31416** for authentication and **TLS 31417** for the verified
lobby and games. Foreground `serve --bind 127.0.0.1` is available for a
single-computer trial; the dailylogin-managed service binds only the detected
campus address. The broker has no public internet
discovery or port-forwarding setup. Stopping the service or logging out of its
host ends hosted games and invalidates LAN42 sessions. The owner must remain
logged in while others use that host. No user-service lingering is enabled.

Export only the public trust file:

```sh
python3 -m campus_lan.auth_server export-trust /path/to/lan42-public-trust.json
```

This explicitly allowlisted export contains a certificate and two endpoints.
It contains **no app secret, TLS private key, or session token**. Give students
the file, and convey its printed SHA-256 fingerprint independently in person
or through an already trusted channel. Never distribute `auth-server.json`,
`auth-key.pem`, `auth-session.json`, or the original credential archive.

## Students: sign in

Update and restart LAN42. All participants need **v0.6.0 / protocol 5**.
Import the owner's public file and compare its fingerprint with the one the
owner provided independently:

```sh
cd ~/Documents/42sg-campus-lan
python3 -m campus_lan.auth_server trust /path/to/lan42-public-trust.json \
  --fingerprint OWNER_PROVIDED_SHA256
lan42
```

Before each `/signin`, LAN42 checks the public `auth-seat` branch for the owner’s
current seat. It accepts a changed address only after matching your existing
certificate fingerprint and successfully verifying the live host over TLS.
GitHub does not grant trust or receive credentials. If discovery is unavailable,
the previously verified address is retained. GitHub caching may briefly delay an update.

To change the address manually, run
`/authhost c2r4s14` in local HQ, substituting their current seat. This connects
to that seat, verifies the existing pinned certificate and TLS identity, and
checks the LAN42 protocol **before saving the new address**. It never sends a
session token during this check, never replaces the certificate pin, and clears
the old local session after a successful move. The owner does not need this
command: their `dailylogin` updates their own trust file automatically. Addresses
are not silently accepted from guest gossip and there is no campus-wide scan.

In the local HQ window, type `/signin`. The browser opens the fixed
`https://api.intra.42.fr/oauth/authorize` endpoint; 42 may direct you to its
own sign-in provider. Enter your password/MFA **only on 42's website**. Approve
the application's `public` scope. Return to LAN42; the window connects to the
verified lobby and uses the login returned by **`GET /v2/me`**, regardless of
the guest name supplied by the client.

Use `/host hexwars`, `/host tetris`, or `/host bluff free`; `/join NUMBER`
opens another game in this same secure lobby. Game windows load the short-lived
LAN42 session from a private file, not a command-line argument. Signed-in
players share this host's rooms and invitations. Their verified identities,
chat and room state are not forwarded into the unauthenticated guest mesh.

`/signout` revokes this device's session, closes its verified HQ/game
connections, removes the matching local session file, and returns HQ to the
guest lobby. An idle session expires after **one hour**, with no refresh token
or automatic renewal. `/quit` closes that window but is not a global sign-out;
use `/signout` before leaving a shared machine. The browser's 42 login is
separate; LAN42 cannot log the browser out of 42.

Sign-in requires the local node on **31415**, matching the app registration.
Custom local testing ports can still play as guests. `/signin` must start from
the local HQ, not a remote or game window. The browser flow expires after five
minutes. Denial, timeout, missing host, or a certificate mismatch fails closed;
there is no fallback that sends a session or authorization code over plain LAN
TCP/HTTP.

## What is protected and retained

| Data | Handling |
| --- | --- |
| App client secret | Only the owner's mode-600 `auth-server.json`; sent over verified HTTPS only to fixed 42 OAuth endpoints. |
| Student passwords, MFA and cookies | Handled exclusively by the external 42 browser login; never requested or read by LAN42. |
| OAuth authorization code | One-shot, five-minute transaction; loopback callback to the originating client, then pinned HTTPS to the broker. Never logged or saved. |
| OAuth access/refresh tokens | Access token used in broker memory for `/v2/me`; best-effort revocation immediately afterward. Neither access nor refresh tokens are saved or sent to students. |
| Student profile | Only numeric account ID and login retained. Email, phone, full profile, grades, campus membership and location are not persisted by sign-in. |
| LAN42 session | Random 256-bit token, one-hour absolute expiry. Hash stored in broker memory; token stored in student's mode-600 file for game windows. Sent only to the pinned TLS lobby. |
| TLS private key | Owner's mode-600 file; public trust exports exclude it. |

Verification means ownership of a 42 account. It does **not** prove current
enrollment, Singapore campus membership, physical seat occupancy, or trustworthy
bot code. The Hex Wars WebAssembly limits remain in force for signed-in bots.

Each sign-in uses random OAuth `state`, an independently held broker redemption
proof, and an S256 PKCE challenge/verifier. The pending grant is consumed before
calling 42, preventing concurrent redemption/replay. PKCE parameters are always
sent; there is no retry that silently removes them. Actual PKCE enforcement
depends on 42's provider. State and broker-proof checks are enforced locally.

Callback HTTP requests are accepted only from loopback, for the exact host/path
and pending state, with duplicate parameters rejected. Responses never echo
codes and set no-store, no-referrer and restrictive content-security headers.
The callback redirects to a clean completion URL. Browser-origin requests to
the broker API are rejected. Broker traffic and game traffic use certificate-
verified TLS 1.2+; the owner certificate is explicitly pinned. Requests to 42
use the system CA store with hostname verification; redirects and environment
HTTP proxies are disabled for token/profile requests so credentials cannot be
forwarded to a different endpoint.

The broker permits five flow starts per source IP per minute, at most 64 pending
flows and 256 active sessions. At most one provider exchange runs at a time,
with a minimum three-second gap and 100 attempts/hour (at most 300 provider
requests/hour for token, profile and revocation). Provider calls are paced at
least 600 ms apart. HTTP size/time/connection limits bound request handling.
The service does not log HTTP bodies, query strings, OAuth tokens or raw
provider exceptions. Revocation failures do not make credentials available to
clients; the unsaved provider token expires under 42's own policy.

The trusted host can see live lobby traffic and the student ID/login needed to
run the service. A compromised host, root, or another process running as the
same OS user can access process memory/private files; this design does not
claim protection against those threats. It does protect against an ordinary
LAN peer copying a guest name, advertising `verified: true`, replaying a
callback, or presenting a different TLS certificate.

## Secret rotation and operations

When 42 rotates the app secret, obtain its new value locally from the app owner
page and update the private credential source. Then run:

```sh
python3 -m campus_lan.auth_server renew-credentials \
  --credentials '/absolute/path/to/private/credentials.env'
```

Restart the auth service. This preserves its TLS key and students' certificate
pin. Existing sessions end because the session store is deliberately in memory.
No student needs the new secret. To recover from suspected session exposure,
stop/restart the service; to recover from an exposed app secret, rotate it on
42 locally as well. Do not share secrets through chat, Git, or a remote mailbox.

## Verification

```sh
python3 -m unittest discover -s tests -v
```

Tests cover real TLS connections, a complete simulated browser callback and
broker exchange, identity overwrite prevention, certificate rejection, OAuth
state/proof expiry and replay, concurrent redemption, sign-out of all windows,
idle expiry, secret-file permissions, response redaction, and false verification
claims from guest nodes. They use fake provider credentials and a temporary
certificate. An actual 42 browser consent/login remains an owner/student action;
automated tests do not access student browser sessions.

Design references: [42's OAuth strategy](https://github.com/42school/omniauth-42),
[OAuth for native apps (RFC 8252)](https://www.rfc-editor.org/rfc/rfc8252.html),
[OAuth security BCP (RFC 9700)](https://www.rfc-editor.org/rfc/rfc9700.html).

## Publishing the owner’s changing seat

Seat publication is enabled only on the owner account with a private
`auth-publish.json` containing `{"fingerprint": "OWNER_CERTIFICATE_SHA256"}`
in the same private config directory, with mode 600. Other installations skip
publication. The fingerprint must match the configured host certificate.

After `dailylogin` confirms the local TLS service is ready, it pushes only
`seat.json` to the `auth-seat` branch of `CrispyNuggetD/42sg-campus-lan`.
The announcement contains a version, campus seat and public certificate
fingerprint. It uses an isolated temporary Git directory and existing GitHub
authentication; it never stages your working tree or copies private config.
An unchanged seat produces no commit. Pushes are never forced. A failed push
prints a warning while leaving the local service available; rerun dailylogin
to retry. Initial student trust import is still required.

The public branch history reveals previously published seats. An announcement
is a location, not proof of uptime: students still need the owner’s host online.

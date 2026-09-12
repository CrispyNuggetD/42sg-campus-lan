# Protocol 2 — v0.2.0

One UTF-8 JSON object per newline, TCP 31416 by default. Ordinary client commands
remain command/text and move/action. Hello includes protocol:3, name, hostname and role (lobby or game).
Game rules and game payloads are unchanged; bluff identities stay hidden until reveal.

## Peer exchange

A mesh handshake exchanges the node's owner presence, local rooms, known live
peer endpoints, and recent event IDs/text. TCP source address is authoritative
for that connection's node address; supplied guest names are not authenticated.
Only literal private/loopback IP peers are accepted. No wildcard scanning.
Each node polls known peers concurrently every five seconds; after about 16 seconds
without a successful exchange, presence and advertisements expire.
Graceful shutdown sends a final empty-owner/empty-room snapshot.

Known endpoints are exchanged so a bootstrap peer is not a single point of failure.
There are at most 16 peers per node, 32 owners in a snapshot, 10 rooms per node,
32 recent events per exchange and a 64 KiB snapshot limit. Event IDs suppress
forwarding loops; creation timestamps expire events after 45 seconds. Hosts need
reasonably synchronized clocks for ephemeral chat forwarding. History is not durable.

Online notices are generated only when a direct peer snapshot adds an owner.
Seat text uses 10.11.row.seat / 10.12.row.seat, with cluster hostname fallback.
Client notify controls apply to online notices and invitations.

## App lifetime

A loopback-only owner control connection registers the local student and sends
five-second heartbeats. Its loss (or 16-second timeout) removes that owner.
When the last owner leaves, the node announces departure and shuts down.
The HQ app retains this connection; separate game clients do not own a node.
A separately launched foreground server without an owner waits for explicit stop.

Loopback connect_peer control performs the handshake before a UI switches server.
Game rooms stay hosted on their original node; game advertisements include IP,
port and room number. HQ stays local while game terminals connect to those addresses.
Closing a game leaves HQ online. Duplicate names are allowed across HQ/game roles
but rejected within a role. The roster comes from node owners, not game sockets. No host migration, authentication or encryption.

The older direct peer_invite request remains supported with protocol 3.
Its receiving node returns a client count and sends a local notice. The mesh
also forwards normal room invitations, so direct seat invitations are optional.

All users must update together. v0.1 servers use protocol 1 and must be stopped
deliberately before starting v0.2 on the same port.

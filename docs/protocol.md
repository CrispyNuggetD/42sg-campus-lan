# v1 wire protocol

TCP 31416 by default. One JSON object per newline, UTF-8. Handshake within 10 seconds:

    {"type":"hello","protocol":1,"name":"hnah","hostname":"cluster-host"}

Names and hostnames are guest claims, not authenticated identity.
The server ignores any client-provided verified flag.

Client messages:

    {"type":"command","text":"/host tetris"}
    {"type":"move","action":"left"}

Movement actions: left, right, rotate, down, drop. Only room members control
that room's board. Commands are parsed as strings, never shell-evaluated.
Commands and hello are bounded by an 8192-byte stream limit; clients are capped
at 32, rooms at 10. Each client is limited to 30 messages/second.

Server messages: welcome, state (players/rooms/API status), event, invite, game,
error. The game payload contains only the visible board or bluff phase/options.
Bluff author IDs are omitted until results; submission text goes only to the host
until voting. A malicious host still sees everything — this is a friends' game.
Client messages cannot claim room IDs for movement; membership is server-owned.

No compatibility guarantees before v1.0. Update all friends when protocol changes.

## Seat addressing and persistent hosts (0.1.1)

c1r2s3 maps to 10.11.2.3; c2r4s9 maps to 10.12.4.9. Client seat prompts
resolve exactly one target. Room joins still use numeric IDs on the current server.

A ping handshake returns pong with protocol and loaded server version, allowing
the launcher to reuse a running compatible background server. Normal client exit
does not terminate the server. A per-user, per-port advisory lock prevents duplicate
local processes. No restart happens during repository updates.

A peer_invite handshake includes name, game, room and sender port. The recipient
uses the TCP peer address (not a supplied address) when constructing the invitation.
It broadcasts an ordinary invitation to connected clients and acknowledges with
their count. Guest names remain unverified. Recipients explicitly choose to connect.

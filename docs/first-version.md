# First playable version — pending approval

## Launcher and lobby

- Inspect the existing syncproj setup in the owner's SUTD repository before implementation.
- Setup installs a runnable command. On launch, fast-forward pull this repository, print semantic version and commit ID, and launch the client; explain update failures and allow a known local version.
- A live terminal lobby provides a scrollable message/event buffer, chat, presence and slash commands including `/games`.
- A host coordinates lobby connections and advertises separately hosted minigames.
- Use read-only 42 API data to enrich campus presence with login and workstation/seat. Distinguish campus presence from connected lobby members.
- Invitations go to connected, consenting clients; their own client calls notify-send (with terminal fallback). A host does not remotely execute notify-send on arbitrary desktops.

## Identity

A local username alone is spoofable by a modified client. Bind identity to a server-verified 42 login before describing it as authenticated. Keep application secrets on the trusted server and out of distributed clients and Git. Any development identity mode must be visibly unverified.

## Games

See ../minigames/README.md. Use built-in random prompts for the bluffing game so no paid or external prompt service is needed. Anonymous labels apply only inside game rounds; reveal authors afterward.

## Scope

Small, playable LAN proof of concept; no production polish or large framework. Test multi-client lobby, invitations, disconnect handling, round timeouts, scoring, and basic game play. Campus-network connectivity and live API authentication require on-campus validation.

# 42SG LAN minigames

Planned proof of concept; games are not implemented yet.

- **Tetris:** minimal terminal falling-block game with a host lobby and join invitations.
- **Who Said That?:** anonymous authorship bluffing game. Players submit a short message, vote for the real author, then see the reveal and scores. Two modes: free-form messages and built-in random prompts asking everyone to respond as the current leader. Display the leader's name during the round while retaining authenticated authors privately. Include submission/voting timeouts.

The terminal lobby will list available games with `/games` and coordinate connections to a host's game server. Invitations reach connected clients, which show local desktop notifications when supported.

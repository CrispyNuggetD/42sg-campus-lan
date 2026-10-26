# LAN42 server changelog

Generated from `campus_lan/release.json`, also used by `/changelog`. Alpha is summarized here; its detailed source log is linked below.

[Read alpha logs](docs/alpha-history.md) · [Read from the beginning ↓](#beginning)

## 2.8.1-beta.1 · 2026-10-27T05:18:59+08:00

- fix: align public LAN42 identity with Christopher Nah

## 2.8.0-beta.1 · 2026-10-27T04:50:24+08:00

- feat: offer consented sgoinfre storage for campus flock

## 2.7.1-beta.1 · 2026-10-27T04:49:00+08:00

- fix: reuse scoped daily flock folder across reconnects

## 2.7.0-beta.1 · 2026-10-27T04:42:59+08:00

- feat: add bounded exam audio quiet and coalesced release alerts

## 2.6.0-beta.1 · 2026-10-27T04:02:33+08:00

- feat: add configurable web search and permanent anonymous impact aggregates

## 2.5.0-beta.1 · 2026-10-27T03:41:54+08:00

- feat: start an opt-in Singapore KoelDrop flock with the campus host

## 2.4.1-beta.1 · 2026-10-27T03:15:26+08:00

- fix: share notification preference changes across open windows

## 2.4.0-beta.1 · 2026-10-27T03:14:08+08:00

- feat: separate important notifications from social alerts

## 2.3.1-beta.1 · 2026-10-27T03:08:54+08:00

- fix: keep automatic uwu quiet after shortcut mute

## 2.3.0-beta.1 · 2026-10-27T03:08:08+08:00

- feat: add clickable account and audio shortcut bar

## 2.2.4-beta.1 · 2026-10-27T03:00:35+08:00

- fix(host): guide on-campus guests and report the initial waiting state

## 2.2.3-beta.1 · 2026-10-27T02:42:32+08:00

- fix(about): identify dthoo and his GitHub account as one alpha tester

## 2.2.2-beta.1 · 2026-10-27T02:37:27+08:00

- fix(uwu): introduce the koel file courier and invite users to try KoelDrop

## 2.2.1-beta.1 · 2026-10-27T02:32:15+08:00

- fix(startup): migrate the legacy campus owner host during normal initialization

## 2.2.0-beta.1 · 2026-10-27T02:17:21+08:00

- feat(access): enforce Singapore API scope and independent user and host permissions

## 2.1.0-beta.1 · 2026-10-27T01:27:38+08:00

- Administrative release: the first CI run misclassified Python 3.12 versus 3.14 AST formatting as a runtime change. No server functionality changed from 2.0.0-beta.1. The existing 2.1.0-beta.1 tag is retained for traceability; fingerprints now use interpreter-independent serialization.

## 2.0.0-beta.1 · 2026-10-27T00:48:00+08:00

- API-backed campus tools, verified sign-in, tracking, announcements and consent-controlled KoelDrop graduate from alpha.
- Beta began Tuesday 27 October 2026 at 00:48 SGT (+08:00).
- Alpha testing: [Darren (dthoo)](https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html) · GitHub: [whatisthisbuffoonery](https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html). Thank you for testing LAN42 before beta.

## Alpha · 2026-09-13 – 2026-10-26

Development milestones reconstructed from Git; these were not separately published releases.

- 2026-10-26: expanded API tools, private pokes, announcements, automatic login, volume controls, KoelDrop and batch permissions (through 51eda1d).
- 2026-10-24: FORKNITE rooms and avatar tools (bec14a8).
- 2026-09-23: secure 42 sign-in and daily host seat publication (c8de0ae).

<a id="beginning"></a>

- 2026-09-13: guest lobby, chat, connectivity, navigation, Tetris and Bluff (15c0240); peer mesh followed in 3f0e0b3. Initial commit 84ec75c contained only the project README.

[Full alpha commit log](docs/alpha-history.md) · [Original README / earliest entry](docs/alpha-history.md#beginning)

# LAN42 server changelog

Generated from `campus_lan/release.json`; `/changelog` shows the same history.

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
- Alpha testing: dthoo (GitHub: whatisthisbuffoonery — https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html). Thank you for testing LAN42 before beta.

## Alpha history (reconstructed; not retroactive releases) · 2026-09-13 – 2026-10-26

- 2026-09-13: guest mesh, chat, connectivity, navigation, Tetris and Bluff (V1 concept; initial commit 84ec75c).
- 2026-09-23: secure 42 sign-in and daily host seat publication (c8de0ae).
- 2026-10-24: FORKNITE rooms and avatar tools (bec14a8).
- 2026-10-26: expanded API tools, private pokes, announcements, automatic login, volume controls, KoelDrop and batch permissions (through 51eda1d).
- Previous checkout reported 0.6.0. V1 was a product milestone, not a published 1.0.0 release.
- Detailed runtime commit history follows (commit dates in SGT; no retroactive version tags):
- 7f2ddc4 · 2026-09-13T03:32:03+08:00 · Reserve useful scripts directory
- 15c0240 · 2026-09-13T04:01:10+08:00 · Add guest LAN lobby, co-op Tetris and timed bluff game
- d5c57f9 · 2026-09-13T04:01:37+08:00 · Open guest host lobby by default
- 7db8719 · 2026-09-13T04:17:52+08:00 · Add seat-based joins, peer invitations and persistent background host
- f06dcbd · 2026-09-13T04:23:23+08:00 · Add public zsh helpers and optional non-destructive setup
- 5d46481 · 2026-09-13T04:36:07+08:00 · Keep launcher in Documents clone instead of user bin
- 3f0e0b3 · 2026-09-13T04:47:28+08:00 · Link independent lobby nodes with five-second peer presence
- 8b50041 · 2026-09-13T04:55:44+08:00 · Rename launcher to lan42.sh and align zsh shortcut
- 354d2a9 · 2026-09-13T04:59:08+08:00 · Allow two-player bluff and document local Mac and LAN testing
- 11e46e4 · 2026-09-13T05:04:07+08:00 · Install append-only zsh helpers by default and launch lobby from dailylogin
- 8988424 · 2026-09-13T05:17:47+08:00 · Make online roster central and add coloured cluster seat maps
- 6326be2 · 2026-09-13T05:34:39+08:00 · Keep peer HQ local and open games in separate terminals
- 4f4bd1a · 2026-09-13T05:42:04+08:00 · Use 31415 for LAN lobby and 31416 for future OAuth callback
- 0742a8e · 2026-09-13T05:53:20+08:00 · Distinguish HQ and game windows with colours and terminal titles
- f378ff3 · 2026-09-13T16:00:09+08:00 · feat: request minimum terminal dimensions
- 82e6ee9 · 2026-09-17T23:14:24+08:00 · leaveschool: save work 2026-09-17T23:14:24+08:00
- f641fdb · 2026-09-21T23:10:25+08:00 · leaveschool: save work 2026-09-21T23:10:25+08:00
- c8de0ae · 2026-09-23T18:11:04+08:00 · Add secure 42 sign-in and publish the dailylogin host seat
- bfeb783 · 2026-09-23T18:11:35+08:00 · Use existing SSH authentication for unattended seat publication
- 8d028df · 2026-09-25T23:20:36+08:00 · leaveschool: save work 2026-09-25T23:20:36+08:00
- bec14a8 · 2026-10-24T23:24:24+08:00 · EOD OCT 24: add FORKNITE rooms and avatar tools
- ba0899a · 2026-10-26T09:56:40+08:00 · WIP: break checkpoint 2026-10-26T09:56:40+08:00
- e85938c · 2026-10-26T14:46:02+08:00 · WIP: checkpoint 2026-10-26T14:46:02+08:00
- c749076 · 2026-10-26T15:22:27+08:00 · EOD: checkpoint 2026-10-26T15:22:27+08:00
- b6dc235 · 2026-10-26T16:56:04+08:00 · Use shared tmux routing for LAN42 tools on macOS too
- cea8ab1 · 2026-10-26T17:19:24+08:00 · Give standalone LAN42 a tmux workspace and publish installer feature workflow
- 8482b27 · 2026-10-26T17:19:36+08:00 · Keep bundled tmux helper identical to canonical source
- 6e957e4 · 2026-10-26T18:12:55+08:00 · Add opt-in uwu sound tests and private two-second poke notifications
- 7a4e738 · 2026-10-26T18:19:34+08:00 · Keep poke audio and desktop toasts in HQ rather than duplicate game windows
- 51b6811 · 2026-10-26T19:07:15+08:00 · Enforce API-host approval for credited campus announcements
- b933263 · 2026-10-26T19:13:26+08:00 · Add opt-in automatic local koel calls every ten to fifteen minutes
- f850de3 · 2026-10-26T19:25:15+08:00 · Offer remembered automatic login choice after first successful sign-in
- 1a34253 · 2026-10-26T19:31:00+08:00 · Shorten koel notification sound to one 850 ms call
- aac08f7 · 2026-10-26T22:50:48+08:00 · Add local shell history, desktop volume consent and numbered tracking
- 8e920e2 · 2026-10-26T23:07:11+08:00 · Keep background API notices out of curses and redraw tmux cleanly
- 7341987 · 2026-10-26T23:17:59+08:00 · Promote KoelDrop to standard feature and add LAN42 pane restart helper
- fe7a755 · 2026-10-26T23:19:16+08:00 · Wait for managed node lock release during app restart
- 51eda1d · 2026-10-26T23:32:50+08:00 · Add batch popup permission setup and one-confirmation allow-all

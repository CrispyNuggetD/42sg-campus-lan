# LAN42 BETA

**Good company. A few good commands.**

A student-built terminal HQ for **42 Singapore**: find your people, see campus
seats, send a file with a koel, or turn your Philosophers project into dinner
with friends.

[Visual command guide ↗](https://crispynuggetd.github.io/42sg-campus-lan/) ·
[All guides](docs/README.md) · [Release history](CHANGELOG.md)

[Highlights](#highlights) · [Quick start](#quick-start) · [Games](#games) ·
[Guides](#guides) · [About](#about)

<a id="lan42-in-your-daily-workspace"></a>

## Highlights

<!-- shell-installer-features:start -->
- **Campus HQ:** `lan42` opens a separate tmux workspace for your lobby, games and tools.
- **Find your people:** `/who`, `/join`, private DMs and `/track` lists; `/clusters` shows current SG seats while the approved campus host is online.
- **KoelDrop:** `/koel flock` joins the host’s 42 Singapore flock: once, always or never. Daily folders survive reconnects; optional sgoinfre link saves home quota. Upload/receive consent stays separate. `/uwu` introduces your courier.
- **Four games:** `/games` offers Tetris, Bluff, Hex Wars and FORKNITE, a multiplayer visualiser/game for the legacy 42 C Philosophers project.
- **Easy controls:** clickable footer or F2 sign in/out; F3 mute, F4 output 0/30%, F5 uwu once, F6 automatic uwu; Up/Down history and !COMMAND for your local shell.
- **Useful alerts:** moderated `/broadcast`, pinned host arrival and exam-time LAN42-only audio quiet. `/notify` separates alerts from DMs/pokes; release popups are coalesced and daily-limited.
- **Versioned server:** startup shows version/date; `/changelog` explains releases. README-only edits do not bump the server.
- **Web search:** `/search` defaults to Ecosia; Google/custom engines are optional. Permanent aggregate impact totals and estimated unique searches have a counting opt-out.
<!-- shell-installer-features:end -->

**Campus API features need a running approved host on campus (currently hnah’s).**
With that host online and its public trust configured, Singapore students can
sign in and run `/clusters` or `/clusters 2` for API-reported occupied seats.
The host shares a 30-second cache across clients. Installing this repo alone does
not provide sign-in/API access. Guest chat and games remain available while the
host is offline; stable, always-on hosting is future work.
[Sign-in and host setup →](docs/sign-in.md)

## Quick start

You need Git, tmux, Python 3.9+ with curses, and a terminal at least **76 × 28**.
Install tmux with `sudo apt install tmux` (Ubuntu) or `brew install tmux` (Mac).

```sh
git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
cd 42sg-campus-lan
sh setup.sh
```

Open a new zsh terminal and run `lan42`, or use `./lan42.sh` directly.
Setup backs up and appends to your `.zshrc`; it needs no sudo.
[Installation, dailylogin and shell helpers →](docs/getting-started.md)

Try `/who`, `/join` to connect to a friend, `/games`, or `/help`.
Click **Sign in** / press **F2** in HQ when the approved campus host is online.
`/uwu` tries the koel call with your sound permission; `/koel help` explains
file sharing. Nothing starts sharing just because you try the bird.

## Games

All four launch from HQ with `/game NAME`; friends use `/join ROOM_NUMBER`.

| Game | The idea | Launch |
| --- | --- | --- |
| **Co-op Tetris** | Share one board and one falling piece. | `/game tetris` |
| **Bluff / Who Said That?** | Write anonymous answers, then guess who wrote each one. | `/game bluff free` |
| **Hex Wars** | Program a C army and battle on a hex board. | `/game hexwars` |
| **FORKNITE** | A multiplayer browser visualiser/game powered by the host’s real legacy C Philosophers executable. Survive dinner. | `/game forknite` |

[Controls, rules, requirements and all four games →](docs/minigames.md)

## Guides

| I want to… | Read |
| --- | --- |
| Install, launch or use dailylogin | [Getting started](docs/getting-started.md) |
| Find people, see clusters, track friends or chat | [Campus and social guide](docs/campus-guide.md) |
| Play or host a game | [Minigames](docs/minigames.md) |
| Share files or understand the uwu bird | [KoelDrop](docs/file-sharing.md) |
| Change shortcuts, search, notifications or consent | [Personal preferences](docs/preferences.md) |
| Sign in or configure the approved API host | [Sign-in setup](docs/sign-in.md) |
| Host, update or troubleshoot LAN42 | [Hosting and maintenance](docs/hosting.md) |

[Full documentation contents →](docs/README.md) ·
[Searchable command cheat sheet →](docs/quick-guide.html)

## About

Hi, I’m **Christopher Nah** (**hnah** on Intra), a student at **42 Singapore**.
Questions or ideas? Find me on the **global 42 Slack**, or [here on GitHub](https://github.com/CrispyNuggetD).

Beta since **Tuesday 27 October 2026, 00:48 SGT**, starting at **2.0.0-beta.1**.
Alpha testing: **dthoo** (GitHub: [whatisthisbuffoonery](https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html)). Thank you for testing LAN42 before beta.

[Issues and contributions](https://github.com/CrispyNuggetD/42sg-campus-lan/issues) ·
[Contributor workflow](AGENTS.md) · [Versioning](docs/versioning.md) ·
[Last observed/tested systems](docs/runtime-environment.md) ·
[API access and privacy boundaries](docs/access-policy.md)

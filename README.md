# LAN42 BETA

**Good company. A few good commands.**

A student-built terminal HQ for **42 Singapore**: find your people, see campus
seats, send a file with a koel, or turn your Philosophers project into dinner
with friends.

[Start in one minute ↗](https://crispynuggetd.github.io/42sg-campus-lan/) ·
[All guides](docs/README.md) · [Release history](CHANGELOG.md) ·
[Roadmap & collaboration](https://crispynuggetd.github.io/42sg-campus-lan/roadmap.html)

The website supports mobile browsers; desktop with a mouse or trackpad gives the full cursor experience. LAN42 itself runs in a terminal.

[Highlights](#highlights) · [Quick start](#quick-start) · [Games](#games) ·
[Guides](#guides) · [About](#about) · [Contributors](#contributors)

<a id="lan42-in-your-daily-workspace"></a>

## Highlights

<!-- shell-installer-features:start -->
- **Campus HQ:** no-sudo setup checks Python/curses and prepares missing tmux in your account on Ubuntu; `lan42` opens a separate workspace.
- **Find your people:** `/who`, `/join`, private DMs and `/track` lists; `/clusters` shows current SG seats while the approved campus host is online.
- **KoelDrop:** `/koel flock` joins the host’s 42 Singapore flock: once, always or never. Daily folders survive reconnects; optional sgoinfre link saves home quota. Upload/receive consent stays separate. `/uwu` introduces your courier.
- **Four games:** `/games` offers Tetris, Bluff, Hex Wars and FORKNITE, a multiplayer visualiser/game for the legacy 42 C Philosophers project.
- **Easy controls:** clickable footer or F2 sign in/out; F3 mute, F4 output 0/30%, F5 uwu once, F6 automatic uwu; Up/Down history and !COMMAND for your local shell.
- **Useful alerts:** moderated `/broadcast`, pinned host arrival and exam-time LAN42-only audio quiet. `/notify` separates alerts from DMs/pokes; release popups are coalesced and daily-limited.
- **Versioned server:** startup shows version/date; `/changelog` explains releases. Enrolled local operators can read their own SG login hours through shell helpers.
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

On school Ubuntu, clone and run setup in your normal account: **no sudo**.
Setup checks your existing Python **3.9+ with curses**; it does not install Python.
Core guest chat/games need no pip packages or API credentials. Setup reuses tmux
or attempts a user-level package download/extraction if it is missing; no system
packages are installed. Use a terminal at least **76 × 28**.
[What setup configures and what must already exist →](docs/getting-started.md#dependencies-without-sudo)

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
file sharing. Nothing starts sharing just because you try the bird. Mac playback
uses the same call in a native WAV copy with brief silent padding; see the
[audio controls](docs/file-sharing.md).

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
Explore my [42 portfolio](https://crispynuggetd.github.io/42_Singapore_SUTD/) or the [main 42 repository & README](https://github.com/CrispyNuggetD/42_Singapore_SUTD) for my projects and learning notes.
Questions or ideas? Find me on the **global 42 Slack**, or [here on GitHub](https://github.com/CrispyNuggetD).

**AI-assisted, human-directed.** I build these projects through reading, design experiments and repeated testing, drawing on textbooks, research papers, documentation and peer discussion. I use AI to learn unfamiliar concepts, challenge ideas and help implement them—including substantial new code, refactoring, build files, header maintenance and repetitive formatting.

I set the questions and engineering goals, investigate algorithms and trade-offs, and review and test the resulting implementation. Correctness, input validation, error handling and understanding the code are part of the work, beyond meeting the minimum requirements. AI assistance reduces manual work; it also needs checking. I remain responsible for what I publish, explaining its limitations and fixing mistakes.

My [42 project notes](https://github.com/CrispyNuggetD/42_Singapore_SUTD) document the wider learning process, including algorithm investigations and project-specific AI contributions. LAN42 is part of that ongoing practice: design, implementation, testing and revision.

Beta since **Tuesday 27 October 2026, 00:48 SGT**, starting at **2.0.0-beta.1**.

## Contributors

- [Darren (dthoo · GitHub: whatisthisbuffoonery)](https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html) — LAN42 alpha testing. Thank you for helping the project reach beta.

GitHub profile links resolve using the contributor’s permanent account ID, with a last-known-profile fallback.

**Want to help?** Design, testing, code and feedback are welcome. See the
[roadmap and collaboration page](https://crispynuggetd.github.io/42sg-campus-lan/roadmap.html)
for small starting points. 42 students: message **hnah on global 42 Slack**.
Otherwise, [open a GitHub issue](https://github.com/CrispyNuggetD/42sg-campus-lan/issues/new)
with your idea or question.



[Issues and contributions](https://github.com/CrispyNuggetD/42sg-campus-lan/issues) ·
[Contributor workflow](AGENTS.md) · [Versioning](docs/versioning.md) ·
[Last observed/tested systems](docs/runtime-environment.md) ·
[API access and privacy boundaries](docs/access-policy.md)

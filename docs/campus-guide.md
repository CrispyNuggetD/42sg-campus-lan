# Find people, campus seats and chat

[← LAN42](../README.md) · [All guides](README.md)

- [Find your friends](#find-your-friends)
- [How the lobbies stay connected](#how-the-lobbies-stay-connected)
- [The lobby: who's online?](#the-lobby-whos-online)
- [Chat, invitations and commands](#chat-invitations-and-commands)
- [Live Singapore campus seats](#live-singapore-campus-seats)
- [Profile browsing](#profile-browsing)
- [Personal tracking and lists](#personal-tracking-and-lists)
- [Track from the displayed roster](#track-from-the-displayed-roster)
- [Relationships and named lists](#relationships-and-named-lists)
- [Cluster arrival rules](#cluster-arrival-rules)

## Find your friends

Everyone starts the same way: run `lan42` (or `lan42.sh`). Your HQ starts on
TCP **31415** and shows **1 online: you** once it connects to its local node.
There is no choice between hosting and joining a lobby.

In HQ, type `/join` for seat questions, `/join c1r2s3` for a known seat, or
`/join 192.168.1.50 31415` for a custom address and port. That links the nodes
and shares known peers while your HQ stays in its own terminal.

The campus address mapping is:

| Seat | IP address |
| --- | --- |
| Cluster 1, row 2, seat 3 (`c1r2s3`) | `10.11.2.3` |
| Cluster 2, row 4, seat 9 (`c2r4s9`) | `10.12.4.9` |

In general, cluster 1 uses `10.11.row.seat` and cluster 2 uses `10.12.row.seat`.
You can check [the Intra cluster map](https://meta.intra.42.fr/clusters) to see
where people are sitting. You'll need to sign in to Intra to view it.

Joining tries that one address. Your friend must have the app running, and the
network must allow the connection. You can also enter an IP address directly,
such as `/join 10.11.2.3` inside HQ.

## How the lobbies stay connected

Each app runs its own local server, or **node**. Connecting to one friend
exchanges the addresses of other known nodes. From there, the nodes check in
with each other every **5 seconds**, sharing who's online, chat, rooms and
invitations. There's no central server or campus-wide scan: you need one live
friend's address to join an existing group.

When someone comes online, you can get a notification like:

> thtay came online! Cluster 1, row 2, seat 3. Go say hi! [Guest]

Seats come from the LAN address or a matching cluster hostname. This does not
poll the 42 API every five seconds. If a seat can't be determined, it is shown
as unknown.

The first node is only the initial meeting point. After discovery, nodes talk
to one another directly. When the first quits, the remaining nodes keep the
shared lobby alive without electing a replacement. When everyone quits, it ends.
A crashed or unreachable peer drops out after roughly 16 seconds.

**HQ, clusters and games have separate terminal windows in the LAN42 tmux session.** HQ has a cyan banner; game
windows have a magenta banner naming the game and room. Window/tab titles also
show `HQ LOBBY` or, for example, `GAME | TETRIS | ROOM 1`. This uses standard
terminal title sequences; terminal settings may override the displayed title.
 `/host tetris` or `/host bluff
free` opens a game window on your node; `/join NUMBER` opens a game on the peer
you last linked. `/home` resets that game target to your own node. Closing a
game window leaves HQ and your presence running. `/quit` in a game or clusters
miniapp closes its tmux window; `/quit` in HQ stops your node.

Each game still runs on one node. If that node quits, its games end; other nodes
and their games continue. Migrating a running game's state is not implemented.
Keep HQ open while playing. One guest can have one HQ connection and one game
connection on each server, without appearing twice in the mesh roster.

## The lobby: who's online?

The main screen shows a numbered roster grouped into **Cluster 1**, **Cluster 2**
and **off campus / seat unknown**. Guests get consistent colours, while the
Guest label stays visible: colour isn't verification. Presence refreshes about
every five seconds. The list covers connected LAN42 users, not everyone on Intra.

Press **Tab** to switch between the roster and an ASCII seat map. `/map 1` and
`/map 2` select a cluster; `/roster` or `/who` returns to the list. The maps follow
the supplied floor plans, with higher rows at the top and staggered even/odd
seat boxes. Coloured boxes refer to the numbered roster below the map. Unmarked
desks don't prove vacancy; they simply have no reported LAN42 peer.

Use `/next` and `/prev` to page through longer rosters or maps in a small terminal.
Chat and invitations stay in their own panel below. During a game, `/lobby`
opens the roster without leaving the room, and `/game` returns to play. Tab
retains its play/chat function when you're viewing Tetris.

## Chat, invitations and commands

Type a message and press **Enter** to chat. **Page Up/Down** scrolls through the
last 500 event lines. Text input currently supports ASCII.

| Command | What it does |
| --- | --- |
| `/who` or `/lobby` | Open the grouped online roster. |
| `/map 1` or `/map 2` | Show a cluster seat map. |
| `/next` or `/prev` | Page through the lobby panel. |
| `/game` | Return from the lobby panel to your game. |
| `/rooms` | Show game rooms. |
| `/games` | List the available games. |
| `/join` | Ask for a friend's cluster, row and seat. |
| `/connect c1r2s3` | Alias for linking a peer; HQ stays local. |
| `/home` | Select your own node for the next game join. |
| `/host hexwars` | Open the C bot arena; `/bot` opens its upload menu. |
| `/host tetris` | Open a Tetris terminal and advertise its room. |
| `/host bluff free` | Open a bluff terminal without a prompt. |
| `/host bluff prompt` | Open a bluff terminal with a random prompt. |
| `/join NUMBER` | Open a game terminal on the last linked peer. |
| `/start` | Start your room's game, or play another round. |
| `/leave` | Leave the game room. |
| `/invite` | Ask for a friend's seat and invite their running lobby to your room. |
| `/invite-room` | Share your room invitation across the connected nodes. |
| `/notify` | View channels; `/notify dms on`, `/notify host off`, or `/notify all off`. |
| `/signin` | When the approved on-campus host is online, SG students can sign in and use `/clusters`. |
| `F3` | Open or focus the dedicated clusters miniapp without replacing HQ chat. |
| `/clusters [1|2]` | Open the clusters miniapp for both clusters or one cluster. Needs sign-in and the running campus host, or approved local-operator access. Aliases: `/cluster 1`, `/cluster1`, `/c1` (and `2` equivalents); `./clusters` shows both. |
| `/authhost SEAT` | Verify the trusted sign-in host at its new seat. |
| `/settings signout` | Revoke this device's session and return to guest HQ. |
| `/quit` | Close this miniapp's tmux window, or close HQ and stop your node. |

To invite someone, first create or join a room. They receive its server address
and room number, then use `/connect IP PORT` followed by `/join NUMBER` to join.
Invitations don't move anyone automatically.

Lobby chat popups, DMs and uwu pokes default to **off**. Enable them separately
with `/notify chat on`, `/notify dms on` or `/notify pokes on`. Your own messages
and game windows do not produce chat notifications. Messages remain in the
terminal even with desktop alerts off.

Desktop notifications use `notify-send` on the recipient's computer, so they
need their client open. If notifications aren't available, the terminal beeps
and the message stays in the log. Invitations have a 10-second cooldown; those
sent across the mesh arrive on the next exchange.

## Live Singapore campus seats

**Singapore students: you can see the clusters after signing in—while an approved
API host is running on campus.** Someone must keep that host server running on a
campus workstation (currently hnah’s). Installing or pulling this repo alone
does not provide the shared sign-in/API service. If the host is offline, shared
sign-in and fresh cluster views are unavailable; guest chat/games remain available.
**Stable, always-on hosting is future work**, not an existing service guarantee.

With the campus host online, run
`/signin`, then `/clusters` (both clusters), `/cluster 1` or `/cluster 2` (one cluster); `/cluster1` and `/c1` are aliases for cluster 1, with matching aliases for cluster 2. `./clusters` also selects both clusters. Each command opens or focuses a separate miniapp in the LAN42 tmux session, leaving HQ chat visible. In that window, press `r`, `F3`, or Enter to request another snapshot from the pinned host; use `/c1`, `/c2`, or `/clusters` to change scope and refresh. The header updates its snapshot age every second and marks data over two minutes old as stale. Tab switches map/roster, `/next` and `/prev` page, and `/quit` closes that tmux window. The ASCII floor plan is
the layout; occupied seats and student logins are fetched from the 42 API. This is reported workstation login activity, rather
than a guarantee of physical attendance or instantaneous updates.

`/settings clusters-auto-open on` saves a local choice to open this miniapp when
HQ connects. It is off by default. This explicit setting permits the clusters
terminal at startup; manual openings still use the terminal permission prompt.
If sign-in is needed, the miniapp opens after the new signed-in HQ connects.
Use `/settings clusters-auto-open off` to stop automatic opening. Mac and 42
computers keep separate local choices.

Your client asks the configured approved API host (currently hnah’s), not 42
directly. That server process shares one snapshot across `/clusters` and campus
tracking for **30 seconds**. Ten students requesting it together share **one
refresh**, including the first concurrent requests on an empty cache. A refresh
may require several API pages and an OAuth token request—it is not necessarily
one HTTP call. After the cache expires, the next request refreshes it for everyone.
There is no continuous fetch just to redraw the map or use `/next` and `/prev`.
Separate server processes, including the owner’s optional local offsite view,
have separate caches; the cache is not shared across different machines.

`/map` and `/roster` in HQ show LAN42 peers; the separate `/clusters` window shows API-reported campus seats.
Guest sockets cannot request API-backed views. Verified SG members and enrolled
local API operators can. API reference:
https://api.intra.42.fr/apidoc/2.0/locations/index.html

## Profile browsing

`/profile thtay hnah` requests permission to open both Intra profiles in local browser tabs. `all`, `sg`, `42sg` and
`cohort4` expand from the local private campus cache. Selections above ten tabs
show the count first; `/profile --open-many cohort4` explicitly opens a large
selection. Parsing validates every login and deduplicates names before opening
any tabs. Existing `/profile signin`/`signout` settings aliases remain available.

The campus map overlays connected LAN42 peers: verified peers use green, guests
keep their LAN42 name colour, and API-only students use white with an “API login”
label. Matching a guest name never grants verified status. API seats remain the
source of location information. Click a numbered login in the roster (or an
occupied map marker) to switch to its cluster and page and blink its seat.
`/locate LOGIN` provides the same action when terminal mouse reporting is not
available. `Shift` plus mouse can still be used for ordinary terminal selection.
Help/table rows stay together, with one blank line between separate messages,
room changes and presence notifications.

Bare `/profile` opens your personal Intra home at
`https://profile-v3.intra.42.fr/`, using the account already signed in to that
browser. Explicit `/profile hnah` opens the public page at
`https://profile-v3.intra.42.fr/users/hnah`; multiple explicit names still open
multiple public profiles. Both inherit the same browser permission by default.
Once approved, inherited browser actions do not repeat the consent or
always-allow question during that LAN42 session. Closing HQ ends its session
grant. `/settings permissions browser ask` revokes a current session grant;
`browser allow` makes it permanent, and `browser deny` blocks all browser pages.

## Personal tracking and lists

`/track dthoo thtay` saves a watch list privately on this computer, separately
for your local LAN42 login. `/track` lists it; `/untrack dthoo` or `/untrack all`
removes entries. Keep your HQ window running: it checks the shared campus API
snapshot immediately and then every five minutes. The watch list is never sent
to the lobby, other peers or Git. Campus API requests still share the global
owner-machine pacing limit. An unavailable API leaves the last known state
intact and reports a retry; it does not mark everybody offline.

Campus notifications say “dthoo is online on campus” with cluster, row and seat
on a separate line. LAN42 arrivals produce a separate “has joined the LAN42
lobby — say hi!” notification immediately from normal lobby state updates.
Each source reports online/offline and seat changes once, including the first
online observation after starting HQ. Lobby notices also report changes between
Guest and 42 Verified. Departures include the last observed seat. An initially
offline person produces no departure notice; repeated polling does not repeat
a notice. API errors keep the previous state rather than reporting departures.
Campus presence means an active reported computer login, rather than physical
attendance. Tracking resumes from the saved list when HQ starts again.

Notifications use an existing local cached photo when available. On desktops
supporting notification actions, “Open Intra profile” opens the profile and
“Say hi / write message” prepares `/dm LOGIN ` in your LAN42 input. Type the
message and press Enter yourself. An unfinished input is preserved: `/compose`
loads the waiting draft after you finish it. Desktop action support uses optional
PyGObject/GIO; plain `notify-send` is the fallback. `/notify off` suppresses
popups while keeping tracking text in the terminal.

`/dm LOGIN MESSAGE` and `/alert LOGIN MESSAGE` deliver a targeted message and a
desktop notification if the recipient enables the DMs channel. `/alert` remains
a personal message; it cannot promote itself to an important system channel.
They work within the current lobby
and directly between known guest-mesh nodes. DMs are never broadcast as public
chat or included in mesh gossip; verified lobbies refuse guest-mesh delivery.
Guest sender names remain explicitly unverified. Multiple matching guest nodes
require connecting to the intended node first. Message sends are limited to one
per two seconds. Notification buttons prepare drafts only; they do not send.

## Track from the displayed roster

In the clusters miniapp, `/track 2 4` uses the **displayed online roster numbers** (also
shown on map markers), not physical desk numbers. LAN42 lists the current Intra
names and seats for confirmation before adding them to your private tracking.
It captures those people, never future desk occupants; a changed seat snapshot
cancels the pending request. `/track LOGIN LOGIN` still works in HQ.

## Relationships and named lists

Relationships, lists and independent arrival rules are configured locally:

```text
/track dthoo thtay
/track
/track friends
/track friends dthoo
/track moots thtay
/track oomf another-login
/track list lunch add dthoo thtay
/track list lunch remove thtay
/track alerts friends campus off
/settings clusters include cohort4 cohort5
/settings clusters exclude excluded-login
/settings clusters c1
/settings clusters on
```

`/track` displays sorted names under relationship headings and named lists.
`/track friends`, `/track mutuals` (or `/track moots`), `/track oomf` and
`/track tracked` display a group without changing it. Add logins or an `@list`
after a relationship label to assign it, for example `/track friends @furs`.
The existing `/track status friends LOGIN...` syntax also works.

Login targets are checked locally against the private Singapore directory before
adding people/lists, changing relationships or sending person-targeted commands.
Unknown logins are rejected (with a possible spelling suggestion); LAN42 never
automatically substitutes the suggested person. Supported selectors expand first
and their resulting logins are checked too. A mixed valid/invalid tracking edit
makes no changes. You can still view and remove old typos even without a whitelist.

The default source is `singapore.json` in the campus-data folder. LAN42 first
looks for a sibling `42_Singapore_SUTD_hnah_private/42/data/campus` folder beside
its checkout, then uses the legacy `~/Documents` location. If absent,
LAN42 uses `singapore_intra.txt` there (whitespace-separated logins). To choose a
specific private whitelist file, set `LAN42_INTRA_WHITELIST` to its absolute path
before launching LAN42. Missing or invalid whitelist files block new targets;
there is no automatic API lookup or directory download. Cohort selectors still
need JSON cohort metadata. This validates input only; API membership and operator
permissions remain independently enforced. Never commit the directory or text
whitelist to the public repository.

Newly tracked people are acquaintances (`tracked`). A relationship is one local
label: `tracked`, `friends`, `mutuals` (alias `moots`), or `oomf`. Labels do not
claim reciprocal friendship or send requests to anyone. `friends` selects the
friendly relationships (friends, mutuals and oomf); `tracked` selects only
acquaintances; `alltracked` selects everyone in your relationship registry.
`mutuals`/`moots` and `oomf` can also be selected individually. `login:friends`
addresses a literal login that collides with a reserved selector name.

Custom named lists can overlap and do not automatically track their members.
Use `@lunch` to select a list explicitly; its bare name also works. Lists accept
`add`, `remove` and `delete`. `/track help` shows the command guide and `/track
config` shows the private, mode-600 JSON configuration. Existing watch lists
migrate to schema version 2 as tracked acquaintances on the first edit. Invalid
or newer configurations are preserved and must be repaired before changes save.

```text
/sabo friends
/sabo @lunch
/dm friends "do you all want lunch?"
/dm @lunch "meet at noon?"
/alert mutuals "game later?"
```

Selectors expand entirely on the sending computer. Only the resulting logins
and the requested message reach LAN42; relationship labels, lists and rules are
never uploaded. Group DMs send individual messages, spaced at least two seconds
apart, and report delivered/unavailable recipients. There is no shared group
thread and no offline mailbox. Quoted messages have their outer quotes removed;
unquoted apostrophes are preserved. SABO accepts at most 50 selected people and
DMs at most 100. A game terminal reloads the saved local selectors for each
command, so changes in HQ take effect there immediately.

## Cluster arrival rules

Cluster arrival rules are a separate subscription system. Includes form a union
of logins, relationship selectors, named lists and/or cohort selectors; excludes
subtract from that union. Cohort rules use the local private campus cache and
remain dynamic as that cache changes. `/settings clusters off` disables these
rules without affecting personal relationship alerts. `/settings clusters clear
[include|exclude]` clears selectors. Rule exclusions do not mute personally
tracked friends; use `/track alerts LOGIN campus|lobby off` for personal alerts.

A friend/mutual/oomf arrival has a warmer message. Someone matched only by a rule
has a normal “Campus update” or “LAN42 update”. If both apply, only the personal
notification is emitted. Per-person `alerts` preferences are keyed by event
(`campus`, `lobby`) to allow future event types without conflating relationship
labels, list membership and subscriptions. Game activity and friend-request
workflows are not enabled by these labels.

Tracking and DM popups use Python GIO over the desktop's
`org.freedesktop.Notifications` D-Bus service. This supports cached-image hints
and action buttons. `notify-send` is only the fallback for desktops without the
GIO/service path; desktop support determines whether buttons are displayed.

Use `/settings clusters c1`, `c2`, or `all` to limit arrival rules
to a physical campus cluster. `C1`, `C2`, `cluster1` and `cluster2` are also accepted. The default is
`all`, including for older saved configurations. This scope applies to both
campus API and LAN42 lobby arrival rules and does not mute personal friend alerts.
An unknown seat cannot match a single-cluster scope. `/settings clusters` shows
the current location alongside includes, exclusions and the on/off switch.

Cluster names can also appear alongside rule filters:
`/settings clusters include cohort4 c1` or `/settings clusters C1 include cohort4`.
In cluster settings, `c1`/`cluster1` and `c2`/`cluster2` select the location rather
than being added as logins. The include/exclude lists still contain people or
cohort selectors. `login:c1` addresses a literal login with that spelling.

Cluster map colors: **magenta** friends/mutuals/oomf; **cyan** members of your named lists; **green** signed-in or explicitly remote-approved LAN42 connections (the roster distinguishes approval from Intra sign-in); **yellow** guests; **blue** API-only logins; **dim** desks with no reported occupant. Friend coloring takes priority over list coloring. Local relationship/list labels stay on your computer; unverified guest names cannot claim friend/list colors. The map legend and roster labels explain the colors. An unreported desk is not proof that it is physically empty.

## Select campus-online people for FORKNITE

`/sabo online` means the Intra logins in the API host's **last completed campus
presence crawl**, including people who have never opened or signed into LAN42.
It does not mean LAN42 peers or verified sign-ins. The command uses that snapshot
without starting a fresh crawl; its response reports the snapshot age. The approved API host seeds presence after TLS startup and refreshes once a
minute. If that crawl is still loading or has failed, `/clusters` retries it. An empty snapshot
selects nobody; it never falls back to the directory or LAN42 sign-ins.

`/sabo verified` is separate: active verified Singapore users currently connected
to this LAN42 host, using their authenticated Intra login rather than a claimed
nickname or verification flag. It does not claim those users are on campus.
Expired, guest and remote-approval-only connections are excluded.

```text
/sabo online
/sabo online 5
/sabo online cluster 1
/sabo online cluster 2
/sabo online 5 c1
/sabo verified
```

These bare words are host-resolved `/sabo` selectors. Use `@online` or
`@verified` explicitly if an existing local list has the same name.
Use them as the signed-in FORKNITE room host. Already seated people are excluded;
remaining unique logins are sorted and capped at the requested count and free
seats in the 50-seat table. The usual private whitelist, SG profile membership
checks and API budgets still apply. These are stand-ins: nobody is contacted or
actually joins your game. Use `login:online` or `login:verified` if you explicitly
mean a whitelisted literal login that collides with a selector.

`cluster 1` / `cluster 2` (also `c1`, `c2`, `cluster1`, `cluster2`) filter only
`online` by the API seat location; the cluster number is not a requested count.
`/sabo online 5 cluster 1` selects up to five unseated people in Cluster 1.
`verified` does not accept a cluster filter because it describes sign-ins.
`/sabo all`, `/sabo sg`, and `/sabo 42sg` use the local private Singapore cache
and the table's 50-seat limit. `/sabo cohort1` selects a cohort; `cohort 1`
is two arguments and is rejected. These selectors apply to commands that accept
people, never to ordinary chat text. `c1` continues to mean physical Cluster 1.

## Campus occupancy in window headers

HQ and every terminal game show `Campus: 17 online (C1:8 | C2:9)` with snapshot
age. These are campus API logins, not LAN42 participants. The approved host
loads presence in the background at startup and refreshes every minute through
the existing global API pacing; headers receive cached counts about every five
seconds. Each login counts once; if multiple active records exist, the highest
location-record ID chooses its cluster. Empty successful crawls show zero;
missing data shows unavailable, and snapshots older than two minutes show stale.

Counts follow existing API access: active signed-in SG clients and the approved
local operator can view them. Guest/remote-approval-only windows prompt for
sign-in instead. FORKNITE has the same private browser header. No names are sent
in the status payload. One mode-600 current-count file outside Git serves local
operator windows; it overwrites the previous count and is not a history log.


## Cluster colors and portable preferences

Cluster 1 uses cyan headings and row/seat labels; cluster 2 uses amber. Your own
signed-in entry has a contrasting white **You** badge in the map and roster,
including when you also belong to a friend/list category. The local operator
hnah is recognized in the dedicated clusters window too. Text labels remain
available without color. Friend/list/status colors retain their meanings.

Friends, relationships, named lists, campus arrival rules, cluster auto-open and
login, notification, search, audio and saved popup preferences are portable JSON preferences, keyed by your login rather than
your Linux/macOS username. Use your own private repository and a dedicated folder:

```text
/settings storage "/path/to/private-repo/42/lan42"
/settings storage
/settings export "/path/to/local-backup"
/settings import "/path/to/local-backup"
```

`storage FOLDER` copies the existing portable preferences and creates the local
`~/.config/42sg-campus-lan/preferences` symlink to that folder. The actual local
root follows XDG_CONFIG_HOME when set. Existing local files are retained; a
conflicting destination is reported rather than overwritten. Git checkouts lose
private mode bits, so explicitly choosing a dedicated preferences folder restores
mode 700 on that folder and mode 600 on its files. A symlinked file is refused.

On another Mac/Linux computer, clone your private repository and run the same
storage command using that computer's path. Alternatively, export and import the
folder. Imports preserve existing conflicting settings for manual reconciliation.
The equivalent terminal command is:

```sh
python3 -m campus_lan.preferences storage "/path/to/private-repo/42/lan42"
python3 -m campus_lan.preferences export "/path/to/local-backup"
python3 -m campus_lan.preferences import "/path/to/local-backup"
```

The folder contains private relationship information: keep it in a private repo.
Selecting a folder does not commit or push it. Authentication credentials, TLS
keys/trust, bearer sessions, host approvals, one-time popup grants, command
history, file-sharing receive approvals and local directory paths stay local.
Saved popup/audio/search/notification choices follow the account as requested.
KoelDrop always-join is scoped to the verified numeric account and pinned host;
its directory choice remains in the local account configuration, without a
seat/hostname key. Existing seat-specific choices migrate once, retaining the
originals and using the most recent saved choice. Copying preferences never signs you in or authorizes a
host. Reopen LAN42 after switching storage/importing so all windows use it.


## Clock, alarms, timers and stopwatch

The HQ header shows the clock, plus a running stopwatch and nearest timer.
The default is **GMT+8**, independent of the computer's timezone. UTC is **Z**
(Zulu). A decimal offset is hours: `+4.5` means **GMT+4:30**.

```text
/clock
/clock zone +8
/clock zone Z
/clock display utc
/clock display +8
/clock display +4.5
/clock display local
/alarm 30m Take a break
/alarm 8
/alarm 162532
/alarm 162121+4.5
/alarm 162121Z
/alarm daily 8pm Dinner
/alarm weekdays 08:00
/alarm weekly mon,wed 16:25
/alarm every 30m Stretch
/alarm on 2026-12-01 8pm
/alarm list
/alarm cancel ID
/alarm snooze ID 5m
/alarm clear
/timer 5m Tea
/timer pause ID
/timer resume ID
/timer status
/timer cancel ID
/stopwatch start
/stopwatch lap
/stopwatch pause
/stopwatch status
/stopwatch reset
```

Timer completions and due alarms play the uwu clip when koel sound is enabled.
They respect `/notify alarms off`, `/notify all off`, `--no-notify`, explicit
notification denial, F4 mute, exam/manual quiet windows, and the existing
permission before raising muted output. Quiet alarms still appear in-app; sounds
are not replayed when quiet ends. Clock and stopwatch displays do not chime.

`/alarm` shows schedules and setup examples. `/alarm 8` asks **am or pm**;
nothing is scheduled until you answer. `162532` is **16:25:32**.
`162121+4.5` is **16:21:21 at GMT+4:30**, not 16:21:21 GMT+8.
Offsets may also use `+4:30` or `+0430`; `Z`, `z`, `+Z` and `+z` mean UTC.
Saved due timestamps use canonical ISO 8601 UTC strings ending in uppercase `Z`;
the original scheduling offset is retained separately for wall-clock recurrence.
Internal UTC storage does not force UTC viewing: timestamps display in GMT+8
unless the schedule explicitly chose UTC, or `/clock display utc` is enabled.
`/clock display +8`, `+4`, `+4.5`, `+04:30`, `UTC` or `Z` explicitly converts
all timestamp views to that offset. `/clock display local` restores automatic
GMT+8 viewing, keeping explicitly UTC schedules in UTC. Thus the
`162121+4.5` example displays as **19:51:21 GMT+8**, while `162121Z` displays
as **16:21:21 UTC**. A clock-only time uses
its next occurrence. Daily, weekday and weekly alarms retain the timezone used
when created. `/clock zone` changes the default for future wall-clock schedules.
Relative durations support seconds/minutes/hours/days, such as `1h30m`.
Bare numbers are seconds for timers, hours (with AM/PM clarification) for alarms.

**HQ must be running for alarms to fire.** Saved alarms/timers follow the account
and portable preferences; an overdue schedule is shown once when HQ reopens.
Missed recurring occurrences are not replayed as a burst. Multiple HQ windows
claim each due alarm once. There is no separate background clock service.
A stopwatch uses a monotonic clock and is **session-only**. Restarting HQ loses
its running state and laps. No test starts a real alarm or plays audio.

Alarms always appear inside HQ. Desktop delivery respects `--no-notify`, saved
popup denial and `/notify all off`; `/notify alarms on|off` controls that channel.
Clock tools never raise system volume or enable sound permissions automatically.


## Cohorts alongside friends and lists

Cluster maps and rosters decorate each existing person **once**. The color
priority is **You → friend → named list → cohort → sign-in/API status**. The
cohort stays visible as a separate text/pattern marker, so a friend in your own
cohort is `friend / C4~` and a friend in cohort 5 is `friend / C5~`; neither gets
a duplicate seat or roster entry. A map token such as `4:09` means **cohort 4,
roster number 9**. Shared seats keep `[++]`, with each occupant listed below.
Cohorts with two-digit numbers retain the usual numbered map token and appear
in the roster badge.

`~` means the cohort comes from the existing local Singapore cache's inferred
intake numbering, not official membership metadata. Missing or conflicting
cohort data stays unknown. No extra API requests or private directory broadcasts
are added; only the minimal login-to-cohort mapping is used locally. A computer
without that private cache still shows friend/list/self markers and ordinary
presence, but cannot guess a cohort. Refresh the private cache through the
existing operator workflow and reopen the window to update cohort decoration.

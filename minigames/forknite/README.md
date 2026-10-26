# FORKNITE · a multiplayer Philosophers visualiser/game

A playful browser visualiser/game powered by the actual C `philo` executable from
42’s classic **Philosophers** project (the Dining Philosophers concurrency
problem). Friends take seats as philosophers while successive rounds tighten
the timing until the first real death. The C program supplies the simulation;
FORKNITE supplies the visualisation and multiplayer tournament.

See the [LAN42 handbook](../../README.md#forknite-multiplayer-philosophers-visualisergame)
for the classic curriculum context and the newer #42Next/Python additions.

## Play

1. Optionally `/signin` once in LAN42 HQ.
2. `/game forknite` creates a room; friends use `/join ROOM_NUMBER`.
3. Each browser opens automatically, already identified as the corresponding LAN42 room member. No separate 42 login, nickname claim, URL-copy step or credentials are required from players.
   Use `/browser` in the game terminal to reopen the current room with a fresh entry ticket. The terminal also shows the plain room URL, which works in the same browser while its room cookie is valid.
4. The host types `/start` in the LAN42 game terminal. `/leave` leaves the room.

LAN42 guests keep their pseudonyms and silly avatars. Verified users get their Intra login, available profile photo, and `✓42`. Missing photos use silly faces. Player identities and slots are assigned by the room server, not by browser form fields. Direct URL visitors can spectate or claim an available guest slot. The last room member leaving shuts down the native process and wrapper. Browser sessions are revoked on room departure.

## Host setup

Node.js 12+ and a compiled philo binary are required on the LAN42 room server. Room mode starts with `philo N 600 100 100 3`, where N is the number of joined players and explicitly requested sabo stand-ins. After a successful three-meal round, it reduces time_to_die by 25ms and launches a new native process after two seconds. The first real death ends the tournament. It adds no synthetic diners. Standalone development keeps its supplied argument count. The launcher checks `LAN42_PHILO_BINARY`, then the local `minigames/forknite/philo` executable/symlink, then PATH. The local symlink is gitignored. Nothing edits your C source or timing logic.

Each room gets a browser port, a local control secret and its own Node process. LAN42 passes identity from its existing connections and delivers one-use browser-entry tickets over those same connections. Room tickets expire after 60 seconds and never contain OAuth tokens or LAN42 session credentials. A browser refresh uses its existing room cookie. Rejoin the room if entry expires. The browser game cannot perform a second 42 OAuth flow.

`/update` updates the LAN42 package and reloads local room servers. Active matches end. No standalone server management is needed for normal room play.

The room host can request `/sabo thtay dthoo guoliu`. These offline stand-ins show `[SABO]`, not a verified-player badge, and real room members take priority over them. In LAN42 rooms, profile lookup uses the API owner's existing private `~/.config/42sg-campus-lan/auth-server.json`. Secrets and app tokens stay in LAN42's Python process; the game receives only the login and photo URL. No extra environment variables are needed. Only the room host can request lookup; batches allow 1–10 names, requests are spaced by at least one second with a 300-request/hour budget per lobby process, and profiles are cached for an hour. The host sees success/failure in the game terminal. Standalone developer mode still supports its optional environment settings.

## Replay and logs

Browser playback can be slower than C time. Pause and replay never control C. Events preserve original timestamps and order. Hunger bars are inferred from meal starts, and counters count observed starts rather than completed meals. Pipes, terminal output, logging and system load can still affect scheduling.

`.logs/*.jsonl` contains event history, `*-round-N.log` contains native stdout, and `room-PORT.log` contains room-server output, including echoed moves. Logs are eligible for Git; they are not automatically pruned. The latest roughly 100,000 events are retained in browser history; complete history remains on disk. Control secrets, ownership cookies and browser-entry tickets are never logged.

## Standalone development / piping

From this folder:

```sh
node server.js --exec /path/to/philo -- 50 130 60 60
stdbuf -oL /path/to/philo 50 130 60 60 | node server.js --pipe --count 50
```

Standalone mode permits guest play only. Managed development can use `sh lan42.sh forknite ...` from the repository root. Native stdout is line-buffered with Linux `stdbuf`; `--buffered` disables it. Pipe mode starts immediately; EOF leaves the web server open for replay. Redirect `2>&1` into the pipe to capture stderr too.

Standalone `--storm` runs complete finite rounds (default three meals), reducing `time_to_die` by 10ms between rounds until an actual death. Configure `--meals` and `--shrink` before `--`. This never changes parameters inside a running C simulation. Normal LAN42 room mode uses the exact default `50 130 60 60` and stops naturally when C exits.

## Checks

```sh
node auth.test.js
node sabo.test.js
python3 smoke.py
```

The repository's Python test suite also exercises real room creation, member identity, browser ticket redemption, native output, joining, leaving and process cleanup. Live 42 OAuth remains LAN42's responsibility.

## Private avatar cache and local admin

On the API owner's computer, `/admin` in LAN42 opens a loopback-only avatar tool.
You can also run `sh lan42.sh admin` from the repository root. It looks up the
photo URL, opens it in your normal browser, and accepts an explicitly selected or
dropped image. This is a semi-automated import: the page cannot inspect browser
cookies, your Chrome profile or your downloads folder. The local admin requires
a private host configuration, a random per-run session key and same-origin
requests. Close its terminal to stop it.

Photos are stored at `$XDG_CACHE_HOME/42sg-campus-lan/avatars`, defaulting to
`~/.cache/42sg-campus-lan/avatars`, outside all Git repositories (enforced). The
directory is mode 700 and entries mode 600. Only raster image bytes up to 1 MiB
and minimal cache timestamps/type/source metadata are stored. No app credentials,
browser state or 42 access tokens enter the cache.

Room wrappers read that cache locally on the master. Browsers fetch
`/avatars/SLOT` from their own game origin using their room cookie, avoiding an
external CDN request and CORB. A room session is required; spectators cannot read
photos. Leaving invalidates server access. Already displayed or downloaded bytes
cannot be recalled from a player's browser. No remote cache-sharing endpoint or
public directory listing is provided. Existing game transport remains HTTP on the
LAN: access checks do not provide TLS encryption; use a trusted LAN or SSH tunnel.

Automatic public-CDN acquisition is best effort, with a 24-hour freshness target,
one photo acquisition at a time across local processes, one-second spacing,
a shared 300-download/hour budget and a persistent 15-minute failure
backoff. A failed refresh retains the previous image. Imports appear immediately
when the player clicks Reload cached photo. Empty caches show a silly face and
an explicit cache-missing message. CDN HTML/error responses are never cached or
served as images. For terminal import:

```sh
python3 -m campus_lan.avatar_cache import hnah /path/to/downloaded/photo.jpg
python3 -m campus_lan.avatar_cache fetch hnah
```

The second command reports acquisition status without exposing tokens. Current
observed failures include HTTP 403 / Cloudflare 1010. A cache cannot make an
upstream denial disappear; import from a browser that is legitimately allowed to
open the image, or request a supported image-access method from 42.

### Optional one-click browser save

The local admin panel also supports **Prepare one-click save**. Install the
small [avatar-saver extension](../../browser-tools/avatar-saver/README.md) once,
then open the prepared photo link in your normal Chrome and click its extension
icon. It exports the already-displayed image without another CDN request. The
admin tool imports only the exact one-use job filename into the private cache
and removes its temporary download. No cookies, browser profiles or unrelated
downloads are read. Chrome extension installation remains an explicit user action.

## Host controls in the FORKNITE tmux tab

`/help` prints game-specific help. The game header permanently shows controls and
the native phase/round/timings. Only this room's host can change settings.

| Command | Behavior |
| --- | --- |
| `/start` | Start a fresh tournament at the configured initial deadline |
| `/stop` | Stop the native process and cancel pending rounds |
| `/status` | Show native phase, diner count and current settings |
| `/timings 600 100 100` | Set initial die/eat/sleep durations in milliseconds |
| `/storm on` or `/storm off` | Progressive finite rounds or one continuous native simulation |
| `/storm step 25` | Reduce the death deadline by 25ms after each successful round |
| `/storm pause 2000` | Wait 2000ms between native rounds |
| `/meals 3` | Complete three meals per diner per storm round |
| `/preset chill` | 600/100/100ms, -25ms, three meals, two-second gaps |
| `/preset chaos` | 250/60/60ms, -10ms, three meals, one-second gaps |

Stop before changing settings or adding sabo diners. At least two diners are
required for a room tournament; add real friends or explicit `/sabo` stand-ins.
Room membership changes stop the tournament, since the running C process cannot
change its philosopher count. `/start` then uses the updated roster. No live
thread timing or C logic is modified. Browser replay can lag behind the native
phase displayed in tmux. Loose timings reduce accidental early deaths but cannot
guarantee survival under arbitrary OS load.

## Fox eating noises

Click **Sounds: off** in the browser to enable Minecraft fox eating sounds.
There are three locally bundled eating variants; each observed meal start has a 45%
chance to play one. Playback follows browser replay time, respects pause/mute,
limits overlap to two sounds with a 200ms minimum gap, and starts at 20% volume.
Use the volume slider to adjust it. No sound is generated by the C process, and
no third-party audio requests occur during play. Audio is embedded in the page so
existing servers need only a browser refresh. Original Mojang asset URLs and
verified SHA-1 source identifiers are recorded in `public/sounds/SOURCES.txt`.

An actual `died` replay event plays one of two separate fox death clips when Sounds is enabled. The death cue cuts off eating clips so it is audible, and follows the same volume and mute controls.

## Round table, diners, and campus directory

Each native room round shuffles the mapping from people to C philosopher IDs;
seat 1 changes identity between consecutive rounds. IDs remain adjacent around
the circular table, preserving the C fork topology. Random seating distributes
scheduling bias; it does not alter the C scheduler or guarantee survival.
Round stats display the exact arguments supplied to C. The hunger time remaining
is a replay-time estimate from the last observed eating start. Meal-start colors
are lime (first), cyan (second), and pink (third or later); they do not prove a
completed meal. Every round resets counters.

- `/diners 7`: fill to seven total diners with fictional random stand-ins.
  Repeating the command replaces its generated stand-ins; joined users and
  explicitly named students remain. Use `/stop` before changing the table.
- `/sabo RANDOM 5`: add five distinct students from the cached campus directory,
  excluding everyone seated. These are labelled SABO, never verified players.
  No API call is needed; no student is contacted or actually joins the room.
- `/info` or `/info_campus`: read the API host's cached campus summary in LAN42.
  `/info hnah`, `/info 2025-04`, or `/info 2` filter or paginate the table.

The API owner refreshes with `python3 -m campus_lan.campus_info refresh`.
Requests are sequential, spaced at least 1.1 seconds apart, with bounded retries
and backoff. Pagination uses bulk enrollments rather than one lookup per student.
The selected academic data and Markdown tables go to the owner's private workspace
(`LAN42_CAMPUS_DATA` overrides the directory). They must stay out of public Git.
Only students with a 42cursus enrollment are included. Intake dates come from
cursus begin_at and are not certified cohort numbers. Missing status information
is UNKNOWN; account activity and a blackhole deadline do not prove ACTIVE,
BLACKHOLED or FREEZE enrollment status. The export keeps those API facts separate.

### Local build, batch photos and directory selections

`LAN42_PHILO_DIR` selects the C project directory; `LAN42_PHILO_BINARY` selects
an executable explicitly and takes precedence. If it is missing, launching a
room runs `make -C` in that directory, checks the executable, then launches the
normal browser game automatically. `/make` also performs this check/build from
the local terminal. Build failures leave the room unopened so it can be retried.

`/tool thtay hnah` (also `/tools`) opens the local owner photo panel and starts a
sequential batch, with “Saving X of Y” progress. Missing room photos open this
same panel automatically, coalesced into a batch. Install/reload the unpacked
avatar-saver extension once and configure Chrome's download folder in the panel.
The extension now automatically exports a loaded CDN image only when its URL
contains an explicit, short-lived LAN42 import job. No extension click is needed
per photo. Browser challenges or download-policy restrictions still need local
attention; the panel waits and reports timeout instead of caching a challenge.

Supported selections include `/sabo RANDOM 5`, `/sabo 4 random cohort4`,
`/sabo cohort4 cohort5`, and `/sabo 4 random cohort4 level>=2 active=true`.
Cohort shortcuts form a union; comparisons form an AND. Optional WHERE and AND
words are accepted. Whitelisted fields are cohort, level, status, active and login;
operators are =, !=, >, <, >= and <=, written without spaces. SQL is never executed.
Room capacity is 50; seated students are excluded. Cohorts remain inferred from
shared cursus start dates, rather than official cohort labels. Explicit login
batches accept up to 50 names, processed ten at a time.

The directory source is exactly `$LAN42_CAMPUS_DATA/singapore.json`, defaulting to
`~/Documents/42_Singapore_SUTD_hnah_private/42/data/campus/singapore.json`.
Missing directories refresh on demand using the owner's private API settings.
Only selected logins/photo URLs enter the game. `/sabo history` lists this room's
selections; the last 500 selection events are also saved privately under the
LAN42 config directory as `sabo-history.json`, never in this repository.

All Python 42 API clients share an owner-local, cross-process file lock and space
request starts by at least 0.51 seconds, including token requests. Queue delays
are reported to the executing terminal/log. This limit spans this machine's
LAN42 processes; it cannot coordinate other machines or unrelated applications.

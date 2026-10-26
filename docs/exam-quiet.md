# Exam quiet and restrained release notices

[← LAN42](../README.md) · [All guides](README.md) · [Notification preferences](preferences.md)

- [Offline defaults](#offline-defaults)
- [Shared API schedule](#shared-api-schedule)
- [Admin control and trust boundary](#admin-control-and-trust-boundary)
- [Release notification budget](#release-notification-budget)

## Offline defaults

Every updated LAN42 instance has these precautionary **Singapore-time** windows:

| Day | LAN42 audio quiet |
| --- | --- |
| Wednesday | 15:00–18:00 SGT |
| Every Saturday | 13:00–16:00 SGT |

The owner chose every Saturday as the safe fallback, including Saturdays without
an exam and cancelled-exam days. These defaults do not depend on a host, API,
login or network connection. Updated FORKNITE pages keep the fallback if their
server disconnects. Refresh older tabs once after upgrading.
All times use UTC+8, independent of the computer's display timezone.

The server/client prints a heads-up in the 30-minute lead-in, then prints when
quiet starts. Clients print the end/resume notice when their LAN42 sound choice
is enabled; the server logs the transition. Overlapping windows keep quiet active
until the last one ends. Repeated ticks do not repeat the same message.

Quiet suppresses uwu tests, automatic calls, incoming poke/file sound, native
notification sound, terminal beeps and FORKNITE chewing/death cues. It preserves
your sound consent, game sound toggle, mute preferences and slider values.
**System output and other applications are unaffected.** Audio resumes according
to your existing choices, without a forced sound, replay burst or volume change.
An already delivered external OS sound/short clip may finish before the next
quiet check; the feature does not terminate unrelated processes.

## Shared API schedule

`/quiet status` shows the policy. Signed-in SG users can run `/exams` to read the
trusted host's shared cache; it does not fetch once per student.

An approved campus API operator checks the next seven days hourly using only
`GET /v2/campus/64/exams` and `/v2/campus/64/events`. Requests include a bounded
date range and at most three pages per endpoint, using existing API pacing.
The scan includes recently started exams. Visible exam records and exam-labelled
events contribute their dated start/end times; missing ends default to **three
hours**. Prep workshops are excluded. Wrong-campus, malformed and overlong
entries are rejected. A shifted 15:50 exam can extend quiet past the normal
18:00 fallback; a special exam outside the fallback adds its own window.

API visibility is not complete coverage: unpublished/private entries or failed
calendar access may hide exams. The fallback still applies. Each source keeps
its still-valid last-known windows when that source fails. The shared queue is
bounded to the earliest 16 current/upcoming windows; API/private-calendar gaps
still require an admin to add a bounded manual window.

Dated additions travel in the existing pinned host poll as a **non-security
calendar settings update**. They update the queue without changing server
versions, installing code or opening a shell. Clients can honour already queued
special windows if the host disconnects before the exam begins.

Only numeric times and fixed reason codes are cached. Completed windows are
removed from the live host cache and the clients' owned queue when active clients
next check it, including after restart; there is no exam-history database or
attendee/name archive. Normal requested terminal messages may remain in terminal
scrollback or existing process logs. An app that is closed cannot perform expiry
cleanup until it runs again. The fixed weekly fallback is recurring configuration,
not a historical calendar archive.

## Admin control and trust boundary

```text
/quiet status
/exams
/quiet 180
/quiet off
```

`/quiet MINUTES` asks for confirmation and requires a configured numeric admin or
the approved host's existing private local capability. Allowed values are 1–720
minutes. `off` clears only a manual window; scheduled/default quiet and personal
sound-off choices remain in force. Ordinary student/guest nicknames and claimed
admin flags grant nothing.

The remote schema accepts only a version, fixed LAN42-audio scope/campus ID,
issuance time, and a small list of bounded start/end times plus reason enums.
Unknown fields, commands, paths, process IDs, wrong types, stale issuance,
foreign scopes and replayed older state are rejected. Raw event titles and
broadcast text are never passed to terminal-command handlers. Windows last at
most 12 hours and the queue looks ahead at most eight days.

The existing TLS certificate pin authenticates host updates. Untrusted guest
mesh messages cannot create local host-control events. FORKNITE reads a fixed,
owned, no-follow local state file and exposes only validated audio deadlines and upcoming windows;
HTTP callers cannot supply a file path or write a quiet state. This endpoint
selects no executable or shell command. A compromised trusted host can still
misstate mute times within the schema; the authority granted here is app-audio
suppression, not remote execution or system control.

## Release notification budget

Release desktop notices coalesce for **30 minutes after the latest version
change**, then allow at most **one popup per rolling 24 hours per computer**.
Changes during the wait replace the pending version. The budget is shared by
HQ/game windows and persists across restarts. First contact is a silent baseline.
During exam quiet, a due popup waits; `/changelog` and terminal release text stay
available. `/notify releases off` disables the category entirely.

Quick host restarts also suppress repeat arrival popups, with a per-computer
15-minute budget. A real observed outage of a minute or more uses a shorter
availability budget, so students can still learn when sign-in/API views return.
These budgets do not automatically turn an exam date change into a release or
moderated broadcast.

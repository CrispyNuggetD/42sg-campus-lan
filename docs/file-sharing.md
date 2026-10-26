# KoelDrop and the uwu bird

[← LAN42](../README.md) · [All guides](README.md)

- [KoelDrop — the uwu bird, but it brings files](#koeldrop--the-uwu-bird-but-it-brings-files)
- [Optional uwu bird](#optional-uwu-bird)
- [Sound tests and private pokes](#sound-tests-and-private-pokes)

## KoelDrop — the uwu bird, but it brings files

A little campus file courier inside LAN42. **Files in your nest, only if you say
yes.** The receive notice is `🔊 uwu, dthoo sent you funny.txt`.

KoelDrop is a standard feature. There is no experimental toggle. From your
signed-in HQ, `/koel help` lists commands (`/files` and `/koeldrop` are aliases).
The on-campus API service owner starts a group with `/koel create`, then uses
`/koel invite dthoo` (or `friends` / `@LIST`). Recipients accept or decline their
numbered invitation. Accepting creates a dedicated folder whose added files
upload to that group; unrelated folders are never scanned.

`/koel pending` lists offers; `/koel receive NUMBER` approves a file and
`/koel reject NUMBER` declines it. `/koel trust LOGIN...` separately confirms an
automatic-receive whitelist for the current group. Deletions still require
approval. `/koel dir "EMPTY PATH"` chooses a folder; `/koel sync` syncs now;
`/koel leave` stops group uploads and preserves local copies.

Transfers use the existing pinned HTTPS broker, current verified sessions,
fresh campus seat/source-IP evidence, recipient-bound expiring invites, private
storage, file ownership, version conflicts and bounded polling. No files transfer
merely because LAN42 starts or a legacy experimental setting says `on`.
See [the design and permissions](file-sharing-design.md).

The project name and public Intra description remain **Ryker's 42SG Campus LAN
Server** and the student-built campus LAN purpose at the top of this README.
KoelDrop is a sub-feature of that project.

## Optional uwu bird

The licensed `koel.ogg` recording is included with [attribution](../assets/sounds/ATTRIBUTION.md).
Sound is **off by default**. At each fresh LAN42 launch, `y` enables it for this
session, `a` requests always-on, and Enter leaves it off. Always-on requires:

```text
Always uwu? Are you SURE? ಠ_ಠ [y/N]
```

You can also use `/settings koel-sound on|off|always`. `off` clears any saved
always-on choice. Enabling sound never enables file sharing. D-Bus sound hints
respect desktop support and sound settings; no separate player is started.

## Sound tests and private pokes

`/uwu auto` (or `/uwu on`) enables local koel calls at a fresh random interval
of 10–15 minutes. It asks for sound permission if needed. `/uwu off` stops
the timer; disabling koel sound also stops it at the next scheduled call.
The timer applies only to this window and stops when it closes; it never pokes
other students. Repeating the command does not reset an active timer.

`/uwu` introduces the **koel**, the familiar “uwu” bird and KoelDrop’s Singapore
take on a carrier pigeon: this bird delivers your files. Once per window, it
invites you to try `/koel` or read `/koel help`; it never starts sharing itself.
It also plays one short koel call (0.85 seconds, no repeated calls) on your own computer for the running joke
or an audio test. If sound is off, it asks first; Enter keeps it off. `a` offers
always-on with the existing second confirmation. Change it with
`/settings koel-sound on|off|always`. `/uwu LOGIN` sends a private poke to a
connected person. Their notification permission and their own sound choice apply;
the toast closes after two seconds and is not resident in notification history.
Only a poke message crosses the network; each client plays its own local asset.
Pokes share the two-second direct-message rate limit.

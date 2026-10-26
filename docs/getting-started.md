# Install and get started

[← LAN42](../README.md) · [All guides](README.md)

- [Get started](#get-started)
- [Zsh commands and daily login](#zsh-commands-and-daily-login)
- [Guest names and 42 sign-in](#guest-names-and-42-sign-in)

## Get started

You'll need Git, tmux, Python 3.9 or newer with curses support, and a terminal at least
**76 columns × 28 rows**. LAN42 asks compatible terminals to grow to that size
when needed; terminals that do not support resize requests show a manual resize
message instead. There are no pip packages to install.

Install tmux with `sudo apt install tmux` on Ubuntu or `brew install tmux` on Mac.
`lan42` uses a separate tmux workspace for HQ, games and tools, even without the
larger dailylogin shell setup. Terminals default to maximized rather than OS
fullscreen; set `DAILY_TMUX_MAXIMIZE=FALSE` to disable maximizing.
`lan42_here` (or the direct `lan42.sh` launcher) runs in your current terminal.

Each person clones the repo into their Documents folder:

```sh
mkdir -p ~/Documents
cd ~/Documents
git clone https://github.com/CrispyNuggetD/42sg-campus-lan.git
cd 42sg-campus-lan
sh setup.sh
```

Setup backs up your existing `.zshrc` and appends the LAN42 shell helper.
Open a new zsh terminal, then start the lobby at school with:

```sh
lan42
```

To use it immediately in the current terminal, reload your shell configuration
first:

```sh
source "${ZDOTDIR:-$HOME}/.zshrc"
lan42
```

If you skipped the zsh helper with `sh setup.sh --no-zsh`, use the launcher
directly instead:

```sh
~/Documents/42sg-campus-lan/lan42.sh
```

The launcher checks for updates and prints the version, commit and date before
starting. Everything runs from this clone; setup needs no sudo and installs
nothing in `/bin` or `~/.local/bin`.

## Zsh commands and daily login

`sh setup.sh` includes the zsh helpers by default. It backs up your `.zshrc` and
**appends** a guarded source block pointing to this clone. It never truncates or
rewrites your existing settings. Rerunning setup skips an identical block; if
you move the clone, a new block is appended and the old one is left alone.

To skip shell setup:

```sh
sh setup.sh --no-zsh
```

After setup, open a new zsh terminal or run `source "${ZDOTDIR:-$HOME}/.zshrc"`.
You can then use:

- `lan42` to open the separate tmux workspace. It passes arguments through,
  so `lan42 join c1r2s3` works too.
- `dailylogin` to update the repo, reload its helpers and open LAN42 in another
  terminal window, leaving your current shell free.
- `lan42_window` to open that separate window directly.

`dailylogin` is a helper from this project, adapted from
[Christopher's SUTD zsh additions](https://github.com/CrispyNuggetD/42_Singapore_SUTD/blob/main/Useful%20.zshrc%20edits%20%28addition%29).
If you already have your own `dailylogin`, it is preserved; use
`lan42_dailylogin` for this repo's version. Christopher's personal version also opens
LAN42 alongside his existing tasks.

Future Git pulls update the sourced helpers. To make `dailylogin` update without
opening a window, set `LAN42_OPEN_ON_LOGIN=0` before the source block in your
`.zshrc`. Sourcing the file alone never launches anything. If zsh isn't installed,
setup prepares the launcher and explains how to enable the helpers later.

See [the zsh helper guide](../useful-scripts/README.md) for manual setup, project
paths, compile/run helpers and optional Documents syncing.

## Guest names and 42 sign-in

The guest mesh uses unverified OS usernames. A guest node cannot assign verified
status. `/signin` in your local HQ opens 42's website; after browser consent,
the trusted host verifies `/v2/me` and moves HQ into its TLS-protected lobby.
Your canonical 42 login appears in green as **42 Verified**. The verified lobby
hosts its own games and does not forward identities or messages to the guest mesh.

Students never provide passwords or personal API credentials to LAN42. Only the
trusted host holds the app secret. Authentication uses HTTPS 31416, the secure
lobby uses TLS 31417, and the registered localhost:31415 callback stays on each
student's own machine. Students pin the owner's public certificate before use. The owner's `dailylogin`
starts the sign-in service on their current campus seat; after the owner moves,
students can use `/authhost SEAT` to verify and select its new address without
changing their certificate pin.

Sessions expire after one hour. `/signout` revokes the session across your HQ
and game windows and returns to guests. Read the **[setup, privacy, and security
guide](sign-in.md)** for importing the existing app, distributing public
trust information, and handling secret rotation.

<details markdown="1">
<summary>Optional 42 API lookup</summary>

The API adapter is optional and doesn't block startup. A trusted host can set
`INTRA_CLIENT_ID` and `INTRA_CLIENT_SECRET` in its environment. The adapter uses
client credentials and `GET /v2/users/:login` to look up connected guest names
every two minutes.

The current mesh uses address-based seats. The API adapter remains a separate
fallback for legacy local clients; it doesn't list the whole campus or verify
that someone owns the username they supplied. Keep the secret on the trusted
host, out of Git and other clients.

Live API permissions and campus data still need testing. See
[42's getting-started guide](https://api.intra.42.fr/apidoc/guides/getting_started)
and [the user endpoint](https://api.intra.42.fr/apidoc/2.0/users/show.html).

</details>

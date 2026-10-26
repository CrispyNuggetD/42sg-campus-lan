"""Public project identity; no host credentials, directory exports or user state."""
from . import VERSION

NAME="Ryker's 42SG Campus LAN Server"
REPOSITORY='https://github.com/CrispyNuggetD/42sg-campus-lan'
DESCRIPTION=('Student-built terminal LAN lobby for 42 Singapore: discover online peers and campus seats via read-only 42 API data, '
             'chat, invite players, and coordinate locally hosted minigames and useful scripts.')


def lines():
    return [NAME+' · '+VERSION,DESCRIPTION,
            'Built by Ryker (hnah) as a public learning and portfolio project. The repo is the source for setup, scope and implementation notes.',
            'Source / issues / contributions: '+REPOSITORY,
            'Working features in this checkout: guest mesh, verified TLS lobby, campus maps, relationships/lists, DMs, minigames and consent-controlled local tools.',
            'Experimental: KoelDrop — the uwu bird, but it brings files. Offline prototype only; no listener, watcher, invitations or transfers are enabled.',
            '/roadmap koeldrop — progress and review milestones | /help — visual guide | /about repo — request opening the source repository',
            'Private credentials, sessions, campus caches, photos, shared file contents and audit databases stay outside the public repository.']

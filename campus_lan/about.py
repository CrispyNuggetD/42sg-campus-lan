"""Public project identity; no host credentials, directory exports or user state."""
from . import VERSION

NAME='LAN42 — 42 Singapore Campus HQ (Beta)'
REPOSITORY='https://github.com/CrispyNuggetD/42sg-campus-lan'
DESCRIPTION=('Student-built, AI-assisted terminal community app for 42 Singapore: read-only public 42 API data for campus seats and information, '
             'LAN chat, moderated announcements, consent-based file sharing and locally hosted minigames. API-backed campus services require an approved host.')


def lines():
    from .release import banner
    return [banner(),NAME+' · '+VERSION,DESCRIPTION,
            'Built by Christopher Nah (hnah), a student at 42 Singapore, as a public learning and portfolio project. The repo is the source for setup, scope and implementation notes.',
            'Source / issues / contributions: '+REPOSITORY,
            'Working features in this checkout: guest mesh, verified TLS lobby, campus maps, relationships/lists, DMs, minigames and consent-controlled local tools.',
            'KoelDrop — campus file sharing with explicit group, folder and per-file consent.','Alpha testing: dthoo (GitHub: whatisthisbuffoonery — https://crispynuggetd.github.io/42sg-campus-lan/alpha-tester.html). Thank you for testing LAN42 before beta.',
            '/roadmap koeldrop — progress and review milestones | /help — visual guide | /about repo — request opening the source repository',
            'Private credentials, sessions, campus caches, photos, shared file contents and audit databases stay outside the public repository.']

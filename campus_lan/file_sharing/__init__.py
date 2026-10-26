"""Session-scoped KoelDrop file sharing on the existing pinned HTTPS service."""


def start(*args,**kwargs):
    """Construct a runtime without opening sockets or starting folder sync."""
    from .runtime import Runtime
    return Runtime(*args,**kwargs)


def roadmap():
    return [
        'KoelDrop — the uwu bird, but it brings files. Available in your signed-in HQ.',
        'The bird is a koel: our Singapore take on a carrier pigeon, delivering your files around campus.',
        '/koel flock once|always|never|ask: join the host-started 42 Singapore flock or change future invitations.',
        '/koel flock-dir PATH: configure the service root. Each join creates a fresh subfolder; copies are kept on shutdown.',
        '/koel create: the on-campus API service owner creates a group after confirmation.',
        '/koel invite LOGIN...|friends|@LIST: invite verified recipients; /koel accept NUMBER or decline NUMBER.',
        '/koel dir "EMPTY PATH": choose a dedicated folder; create/accept starts its upload polling.',
        '/koel pending | receive NUMBER | reject NUMBER: incoming files need approval.',
        '/koel trust LOGIN...|friends|@LIST|off: explicitly allow automatic receives in this group.',
        '/koel sync | leave: sync now, or leave while keeping local copies. Deletions always need approval.',
        'Pinned HTTPS, fresh 42SG session/seat checks, expiring invitations, ownership and conflict checks apply.',
        'No experimental setting is needed. No personal folders are scanned; uploads start only in a freshly chosen/created group folder after consent.',
    ]

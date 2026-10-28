"""Session-scoped KoelDrop file sharing on the existing pinned HTTPS service."""


def start(*args,**kwargs):
    """Construct a runtime without opening sockets or starting folder sync."""
    from .runtime import Runtime
    return Runtime(*args,**kwargs)


def roadmap():
    return [
        'KoelDrop — the uwu bird, but it brings files. Available in your signed-in HQ.',
        'The bird is a koel: our Singapore take on a carrier pigeon, delivering your files around campus.',
        '/koel dock: ask to pin a KoelDrop launcher to the Ubuntu dock (/koel favorite is a legacy alias).',
        '/koel bookmark (or /koel sidebar): ask to pin ~/KoelDrop in the GNOME Files sidebar.',
        '/koel flock once|always|never|ask: join the host-started 42 Singapore flock or change future invitations.',
        '/koel flock-dir PATH: configure the service root. Flock files use 42-singapore/YYYY-MM-DD; same-day reconnects reuse them and copies are kept.',
        '/koel create: the on-campus API service owner creates a group after confirmation.',
        '/koel invite LOGIN...|friends|@LIST: invite verified recipients; /koel accept NUMBER or decline NUMBER.',
        '/koel dir "EMPTY PATH": choose a dedicated folder; create/accept starts its upload polling.',
        '/koel pending | receive NUMBER | reject NUMBER: incoming files need approval.',
        '/koel resolve NUMBER: confirm keeping both conflicting files; publish your copy in your member folder, then receive the shared version.',
        '/koel trust LOGIN...|friends|@LIST|off: explicitly allow automatic receives in this group.',
        '/koel sync | leave: sync now, or leave while keeping local copies. Shared files are add-only; deletion is disabled.',
        'Host-assigned names: report_<intra>_1.pdf, _2.pdf. Edits/renames add files; originals remain. Shared: 6 additions/minute; own folder: 30/minute.',
        'Pinned HTTPS, fresh 42SG session/seat checks, expiring invitations, ownership and conflict checks apply.',
        'No experimental setting is needed. No personal folders are scanned; uploads start only in a freshly chosen/created group folder after consent.',
    ]

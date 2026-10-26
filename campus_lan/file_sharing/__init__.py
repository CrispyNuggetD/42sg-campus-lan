"""File sharing is an offline experiment. No runtime listener or watcher is registered."""
class DisabledFeature(ValueError):pass


def start(*args,**kwargs):
    raise DisabledFeature('File sharing is parked for review. No listener, watcher, invite delivery or sync is enabled. See /roadmap files.')


def roadmap():
    return [
        'KoelDrop — the uwu bird, but it brings files. EXPERIMENTAL / DISABLED',
        'Implemented for offline tests: admission policy, session-bound invitations, ownership, versioned files, audit history and receive approval.',
        'Implemented for offline tests: bounded native HTTPS dispatcher, dedicated-folder scans and explicit sync passes.',
        'No listener, background watcher, notification delivery or activation setting exists in the running app.',
        'Before activation: Bocal review; pinned-TLS transport wiring; live campus proof validation; end-to-end review of invite/receive UI.',
        'Planned commands: /koel create | invite LOGIN|friends|@LIST | accept LINK | dir PATH | sync | leave.',
        'Implemented now: /koel status or /roadmap koeldrop. All creation, invitation and sync commands stay blocked.',
        'Scope: 42SG verified sessions + fresh campus-seat/source-IP match; recipient-bound, one-use invites expire with the host session.',
        'Files: private storage, group reads, owner-only member folders, version-checked shared-root edits, no automatic execution/extraction.',
        'Limits: app checks cannot prohibit OS-level port forwarding or make an untrusted host trustworthy.',
        'Receive notice planned: uwu, dthoo sent you funny.txt | Review: docs/file-sharing-design.md',
    ]

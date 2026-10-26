"""KoelDrop's local UI plans. No desktop delivery, downloads or watcher starts here."""
from dataclasses import dataclass
from pathlib import Path
import re
from .paths import logical_path
from .security import Denied,login
from .sync import ReceivePolicy

NAME='KoelDrop'
TAGLINE='The uwu bird, but it brings files.'
DESCRIPTION='A little campus file courier inside LAN42. Files in your nest, only if you say yes.'


@dataclass(frozen=True)
class Notice:
    title:str
    body:str
    actions:tuple=('accept','decline')
    koel_sound:bool=False


def file_notice(offer,destination,sound_enabled=False):
    name=logical_path(offer.path).rsplit('/',1)[-1];sender=login(offer.author)
    if offer.deleted:return Notice(sender+' requested deleting '+name,'Explicit approval required. A recoverable local backup is kept.')
    return Notice('🔊 uwu, '+sender+' sent you '+name,
                  'Sender: '+sender+' · '+str(offer.size)+' bytes\nDestination: '+str(destination)+'\nAccept to receive; Enter means no. Files are never opened or executed automatically. Optional uwu bird: /settings koel-sound on',koel_sound=sound_enabled is True)


def invitation_notice(host):
    return Notice('uwu, '+login(host)+' invited you to a KoelDrop group',
                  'Accepting the group does not accept its files. Your verified account and current campus seat will be checked.')


def default_folder(host,gid):
    host=login(host)
    if not isinstance(gid,str) or not re.fullmatch(r'[a-f0-9]{32}',gid):raise Denied('Invalid group identifier.')
    return Path.home()/'KoelDrop'/host/gid


def invite_targets(tracker,selectors,own_login):
    # Local lists expand here; relationships and group labels are never transmitted.
    names=[name for name in tracker.resolve(selectors) if name!=own_login]
    if not names or len(names)>15:raise Denied('Choose 1–15 invitees; the host makes at most 16 members.')
    return names


def receive_policy(tracker,allowed_uids=(),selectors=()):
    if any(type(uid) is not int or uid<=0 for uid in allowed_uids):raise Denied('Whitelist verified user IDs.')
    names=tracker.resolve(selectors) if selectors else ()
    return ReceivePolicy(frozenset(allowed_uids),frozenset(names))

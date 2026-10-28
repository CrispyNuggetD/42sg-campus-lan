"""A host-owned campus flock. Its local service identity is never a login token."""
import json
import getpass
import os
from pathlib import Path
import re
import stat
import secrets
from datetime import datetime
from zoneinfo import ZoneInfo
import time
from ..auth import private_read, private_write
from ..local_console import local_path
from .paths import private_directory
from .security import Gate, Identity, Denied, campus_ip

LABEL = '42 Singapore flock'
SCOPE = '42-singapore'


class ServiceGate(Gate):
    def __init__(self,broker,proofs,host,policy_factory,clock=time.time):
        super().__init__(broker,proofs,clock)
        self.host=host;self.policy_factory=policy_factory;self.running=True

    def check(self,identity):
        if not isinstance(identity,Identity):raise Denied('Invalid service identity.')
        if identity.session_key != self.host.session_key:return super().check(identity)
        if not self.running or identity != self.host:raise Denied('The flock host has stopped.')
        policy=self.policy_factory()
        if policy.local_operator(admin=True)!=self.host.uid:raise Denied('The flock host is no longer approved.')
        # Reuse the same fresh membership and real campus-seat checks as members.
        try:
            proof=self.proofs.identity(identity.uid,identity.login)
            from ..network import seat_address
            age=self.clock()-proof.observed_at
            allowed=(proof.member is True and 0<=age<=self.max_age and identity.expires>self.clock()
                     and identity.peer_ip in {seat_address(s) for s in proof.seats})
        except Exception:raise Denied('Fresh flock host evidence is unavailable.') from None
        if not allowed:raise Denied('The flock host needs fresh campus membership and presence.')



def service_identity(uid,name,peer,clock=time.time):
    # This key is never inserted into Broker.sessions or sent to any client.
    from .security import login
    if type(uid) is not int or uid<=0:raise Denied('A numeric approved local operator is required.')
    return Identity(uid,login(name),secrets.token_hex(32),clock()+365*86400,campus_ip(peer))


class FlockPreferences:
    def __init__(self,fingerprint,uid):
        if not re.fullmatch('[a-f0-9]{64}',fingerprint) or type(uid) is not int or uid<0:raise Denied('Invalid flock preference scope.')
        self.fingerprint=fingerprint;self.uid=uid
        self.path=local_path('flock-'+fingerprint+'-'+str(uid))
        self.mode='ask';self.base=str(Path.home()/'KoelDrop');self.storage_chosen=False
        if uid:
            guest=FlockPreferences(fingerprint,0)
            self.base=guest.base
            if guest.mode=='never':self.mode='never'
        try:
            data=json.loads(private_read(self.path))
            if not isinstance(data,dict) or data.get('mode') not in ('ask','always','never') or not isinstance(data.get('base'),str):raise ValueError()
            self.mode=data['mode'];self.base=data['base'];self.storage_chosen=data.get('storage_chosen') is True
        except FileNotFoundError:pass
        except (OSError,ValueError):self.mode='never'

    def save(self,mode=None,base=None):
        if mode is not None:
            if mode not in ('ask','always','never'):raise Denied('Use ask, always or never.')
            self.mode=mode
        if base is not None:
            path=Path(base).expanduser().absolute()
            if path==Path('/') or path==Path.home() or '..' in path.parts or any(p.startswith('.') for p in path.parts[1:]):raise Denied('Choose a dedicated KoelDrop service directory.')
            self.base=str(path)
        private_write(self.path,json.dumps(dict(mode=self.mode,base=self.base,storage_chosen=self.storage_chosen)))


def sgoinfre_target():
    """Offer only an existing local user's campus storage, never create a NAS mount."""
    name=getpass.getuser()
    if not re.fullmatch(r'[a-zA-Z0-9_-]+',name):return None
    for parent in (Path('/sgoinfre/goinfre/Perso')/name,Path('/sgoinfre')/name):
        try:
            info=parent.lstat()
            if stat.S_ISDIR(info.st_mode) and info.st_uid==os.getuid():return parent/'KoelDrop'
        except OSError:pass
    return None


def link_sgoinfre(preferences,target):
    """Create a convenience link only after local consent; workers use its real target."""
    alias=Path(preferences.base)
    if alias!=Path.home()/'KoelDrop' or os.path.lexists(alias):raise Denied('KoelDrop already exists; it was left unchanged. Choose storage manually.')
    if target!=sgoinfre_target():raise Denied('Campus storage changed; choose storage again.')
    fd=private_directory(target,create=True)
    os.close(fd)
    os.symlink(str(target),alias,target_is_directory=True)
    preferences.storage_chosen=True
    preferences.save(base=str(target))


def fresh_folder(base,fingerprint,epoch,uid=0,group=''):
    """Reuse only our marked daily folder, scoped to host, student and group."""
    if not re.fullmatch('[a-f0-9]{64}',fingerprint) or not re.fullmatch('[a-f0-9]{32}',epoch):raise Denied('Invalid flock session.')
    if type(uid) is not int or uid<0 or not isinstance(group,str):raise Denied('Invalid flock folder scope.')
    base=Path(base).expanduser().absolute()
    if base in (Path('/'),Path.home()) or '..' in base.parts or any(p.startswith('.') for p in base.parts[1:]):raise Denied('Choose a dedicated service directory.')
    root=base/SCOPE
    if any((p/'.git').exists() for p in (root,*root.parents)):raise Denied('Flock folders must be outside Git.')
    fd=private_directory(root,create=True)
    name=datetime.now(ZoneInfo('Asia/Singapore')).date().isoformat()
    expected=json.dumps(dict(host=fingerprint,uid=uid,group=group,day=name),sort_keys=True).encode()
    try:
        try:os.mkdir(name,0o700,dir_fd=fd);created=True
        except FileExistsError:created=False
        folder=root/name
        daily=private_directory(folder)
        try:
            marker='.lan42-flock'
            if created:
                entry=os.open(marker,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=daily)
                with os.fdopen(entry,'wb') as output:output.write(expected)
            else:
                try:entry=os.open(marker,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=daily)
                except OSError:raise Denied('Daily flock folder is unrecognized; choose another service root or review it manually.') from None
                with os.fdopen(entry,'rb') as source:
                    info=os.fstat(source.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_uid!=os.getuid()
                            or stat.S_IMODE(info.st_mode)&0o077 or source.read(4097)!=expected):
                        raise Denied('Daily flock folder belongs to another scope or has changed; no files imported.')
            return folder
        finally:os.close(daily)
    finally:os.close(fd)

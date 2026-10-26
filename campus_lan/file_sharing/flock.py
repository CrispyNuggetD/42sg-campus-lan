"""A host-owned campus flock. Its local service identity is never a login token."""
import json
import os
from pathlib import Path
import re
import secrets
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
        self.mode='ask';self.base=str(Path.home()/'KoelDrop')
        if uid:
            guest=FlockPreferences(fingerprint,0)
            self.base=guest.base
            if guest.mode=='never':self.mode='never'
        try:
            data=json.loads(private_read(self.path))
            if not isinstance(data,dict) or data.get('mode') not in ('ask','always','never') or not isinstance(data.get('base'),str):raise ValueError()
            self.mode=data['mode'];self.base=data['base']
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
        private_write(self.path,json.dumps(dict(mode=self.mode,base=self.base)))


def fresh_folder(base,fingerprint,epoch):
    if not re.fullmatch('[a-f0-9]{64}',fingerprint) or not re.fullmatch('[a-f0-9]{32}',epoch):raise Denied('Invalid flock session.')
    base=Path(base).expanduser().absolute()
    if base in (Path('/'),Path.home()) or '..' in base.parts or any(p.startswith('.') for p in base.parts[1:]):raise Denied('Choose a dedicated service directory.')
    root=base/SCOPE/fingerprint[:16]
    if any((p/'.git').exists() for p in (root,*root.parents)):raise Denied('Flock folders must be outside Git.')
    fd=private_directory(root,create=True)
    try:
        for _ in range(10):
            name=time.strftime('%Y-%m-%d_%H-%M-%S')+'-'+epoch[:8]+'-'+secrets.token_hex(4)
            try:os.mkdir(name,0o700,dir_fd=fd);return root/name
            except FileExistsError:continue
        raise Denied('Could not allocate a fresh flock directory.')
    finally:os.close(fd)

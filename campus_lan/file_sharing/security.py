"""Admission checks use the real socket peer and trusted broker/API callbacks."""
from dataclasses import dataclass,field
import ipaddress
import re
import time
import threading
from ..network import seat_address

class Denied(ValueError):pass
class Conflict(ValueError):pass
class Limit(ValueError):pass


def campus_ip(value):
    try:address=ipaddress.IPv4Address(value)
    except (ValueError,TypeError):raise Denied('A campus workstation address is required.') from None
    parts=str(address).split('.')
    if parts[:2] not in (['10','11'],['10','12']) or not all(1<=int(v)<=254 for v in parts[2:]):
        raise Denied('A campus workstation address is required.')
    return str(address)


def login(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9_.-]{1,24}',value):raise Denied('Invalid verified login.')
    return value


@dataclass(frozen=True)
class Identity:
    uid:int
    login:str
    session_key:str=field(repr=False)
    expires:float
    peer_ip:str


class Gate:
    def __init__(self,broker,proofs,clock=time.time,max_age=120,enabled=None):
        self.broker=broker;self.proofs=proofs;self.clock=clock;self.max_age=max_age;self.enabled=enabled

    def admit(self,token,peer_ip,tls):
        if tls is not True:raise Denied('File sharing requires TLS.')
        peer_ip=campus_ip(peer_ip)
        try:record=self.broker.authenticate(token)
        except ValueError:raise Denied('A current verified LAN42 session is required.') from None
        identity=Identity(record['uid'],login(record['login']),record['session_key'],record['expires'],peer_ip)
        self.check(identity)
        return identity

    def check(self,identity):
        if self.enabled is not None and not self.enabled():raise Denied('Experimental features are off.')
        if (not isinstance(identity,Identity) or type(identity.uid) is not int or identity.uid<=0
                or identity.expires<=self.clock() or not self.broker.active(identity.session_key)):
            raise Denied('The verified session has ended.')
        campus_ip(identity.peer_ip)
        try:proof=self.proofs.identity(identity.uid,identity.login)
        except Exception:raise Denied('Fresh campus eligibility could not be verified.') from None
        age=self.clock()-proof.observed_at
        if proof.member is not True or not 0<=age<=self.max_age:raise Denied('Fresh 42SG membership and presence are required.')
        try:addresses={seat_address(seat) for seat in proof.seats}
        except (ValueError,TypeError):raise Denied('Invalid campus presence evidence.') from None
        if identity.peer_ip not in addresses:raise Denied('Connection does not match the active campus seat.')


@dataclass(frozen=True)
class Proof:
    member:bool
    seats:tuple
    observed_at:float


class CampusProofs:
    """Explicitly constructed adapter; imports do not read credentials or call APIs.

    api is the owner's existing campus_info.API (which uses global API pacing).
    Only a primary Singapore campus membership and active account are accepted.
    """
    def __init__(self,api,campus_id,clock=time.time):
        if type(campus_id) is not int or campus_id<=0:raise Denied('Configure the Singapore campus ID.')
        self.api=api;self.campus_id=campus_id;self.clock=clock;self.cache={};self.campus_checked=False;self.lock=threading.RLock()

    def _profile(self,identifier):
        if not self.campus_checked:
            campus=self.api.get('campus/'+str(self.campus_id))
            if campus.get('id')!=self.campus_id or 'singapore' not in (str(campus.get('name',''))+' '+str(campus.get('slug',''))).lower():
                raise Denied('Configured campus is not Singapore.')
            self.campus_checked=True
        return self.api.get('users/'+str(identifier))

    def _member(self,user):
        return user.get('active?') is True and any(c.get('campus_id')==self.campus_id and c.get('is_primary') is True for c in user.get('campus_users',[]))

    def target(self,name):
        with self.lock:return self._target(name)

    def _target(self,name):
        name=login(name);user=self._profile(name)
        if user.get('login')!=name or type(user.get('id')) is not int or not self._member(user):raise Denied('Recipient is not an eligible 42SG account.')
        return user['id'],name

    def identity(self,uid,name):
        with self.lock:return self._identity(uid,name)

    def _identity(self,uid,name):
        key=(uid,name);now=self.clock()
        self.cache={k:v for k,v in self.cache.items() if 0<=now-v.observed_at<20}
        cached=self.cache.get(key)
        if cached and 0<=now-cached.observed_at<20:return cached
        user=self._profile(uid)
        member=user.get('id')==uid and user.get('login')==name and self._member(user)
        locations=self.api.pages('campus/'+str(self.campus_id)+'/locations',**{'filter[user_id]':uid,'filter[active]':'true'}) if member else []
        seats=[]
        for location in locations:
            person=location.get('user') or {}
            if location.get('end_at') is None and person.get('id')==uid and person.get('login')==name:
                host=location.get('host','')
                if re.fullmatch(r'c[12]r\d{1,3}s\d{1,3}',host):
                    campus_ip(seat_address(host));seats.append(host)
        proof=Proof(member,tuple(seats),self.clock());self.cache[key]=proof
        return proof

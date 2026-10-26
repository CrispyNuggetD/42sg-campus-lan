"""API-host moderated announcements. Authority comes from TLS and server-side identity."""
import hmac
import re
import secrets
import time
from .auth import AuthError,nonce

LOGIN=re.compile(r'[A-Za-z0-9_.-]{1,32}')


def message(value):
    if not isinstance(value,str) or not 1<=len(value.strip())<=400 or len(value.encode('utf-8'))>400 or any(ord(c)<32 for c in value):
        raise AuthError('Announcements need 1–400 printable characters.')
    return value.strip()


class Announcements:
    def __init__(self,broker,owner,admin_token=None,clock=time.time,on_request=None,policy=None):
        if not isinstance(owner,str) or not LOGIN.fullmatch(owner):raise AuthError('Configure a valid announcement owner login.')
        from .access import Policy
        self._policy=policy
        self.broker,self.owner,self.clock=broker,owner.lower(),clock
        self.admin_token=admin_token or secrets.token_hex(32)
        self.epoch=secrets.token_hex(16);self.sequence=0
        self.requests={};self.feed=[];self.last={};self.on_request=on_request
        self.flock_status=lambda:None
        self.search_summary=lambda:None

    @property
    def policy(self):
        from .access import Policy
        return self._policy if self._policy is not None else Policy()

    def identity(self,data,required=False):
        token=data.get('admin')
        if nonce(token) and hmac.compare_digest(token,self.admin_token):
            uid=self.policy.local_operator(admin=True)
            return dict(login=self.owner,uid=uid),True
        try:
            person=self.broker.authenticate(data.get('session'))
            self.policy.require_member(person)
            return person,self.policy.is_admin(person['uid'])
        except (AuthError,ValueError):
            if required:raise AuthError('42 sign-in or local host authority is required.') from None
            return None,False

    def prune(self):
        now=self.clock()
        for request in self.requests.values():
            if request['status']=='pending' and now>=request['expires']:request['status']='expired'
        self.requests={key:r for key,r in self.requests.items() if now-r['created']<900}
        self.feed=[event for event in self.feed if now-event['created']<900][-10:]
        self.last={key:stamp for key,stamp in self.last.items() if now-stamp<60}

    def publish(self,request,is_host,approved_by=None):
        self.sequence+=1
        event=dict(seq=self.sequence,id=request['id'],author=request['author'],is_host=is_host,
                   approved_by=approved_by or self.owner,text=request['text'],created=self.clock())
        self.feed.append(event);self.feed=self.feed[-10:]
        return event

    def submit(self,data):
        self.prune();person,host=self.identity(data,True);text=message(data.get('text'))
        now=self.clock();uid=person['uid'];cooldown=5 if host else 30
        if now-self.last.get(uid,-10000)<cooldown:raise AuthError('Announcement cooldown; do not spam.')
        if not host and any(r['uid']==uid and r['status']=='pending' for r in self.requests.values()):
            raise AuthError('An announcement is already waiting for host approval.')
        if not host and len(self.requests)>=64:
            completed=next((key for key,item in self.requests.items() if item['status']!='pending'),None)
            if completed:self.requests.pop(completed)
            else:raise AuthError('Announcement queue is full.')
        self.last[uid]=now;ident=secrets.token_hex(16)
        request=dict(id=ident,uid=uid,author=person['login'].lower(),text=text,created=now,
                     expires=now+300,status='approved' if host else 'pending')
        if host:self.publish(request,True,person['login'])
        else:self.requests[ident]=request
        if not host and self.on_request:
            try:self.on_request(dict(request))
            except (OSError,RuntimeError):pass
        return dict(id=ident,status=request['status'],owner=self.owner,author=request['author'],is_host=host)

    def decide(self,data):
        self.prune();moderator,host=self.identity(data,True)
        if not host:raise AuthError('Only the API host can approve or reject announcements.')
        ident=data.get('id')
        if not isinstance(ident,str) or not re.fullmatch('[a-f0-9]{32}',ident):raise AuthError('Invalid announcement ID.')
        request=self.requests.get(ident);decision=data.get('decision')
        if not request or decision not in ('approve','reject'):raise AuthError('Invalid announcement decision.')
        if request['status']=='pending':
            request['status']='approved' if decision=='approve' else 'rejected'
            if decision=='approve':self.publish(request,False,moderator['login'])
        return dict(id=request['id'],status=request['status'])

    def poll(self,data):
        self.prune();person,host=self.identity(data)
        cursor=data.get('cursor',0)
        if type(cursor) is not int or cursor<0:raise AuthError('Invalid announcement cursor.')
        pending=[{k:r[k] for k in ('id','author','text','expires')} for r in self.requests.values() if r['status']=='pending'] if host else []
        statuses=[{k:r[k] for k in ('id','status','author')} for r in self.requests.values() if person and r['uid']==person['uid']]
        from .release import VERSION, RELEASE_DATE
        return dict(epoch=self.epoch,owner=self.owner,host=host,sequence=self.sequence,
                    version=VERSION,release_date=RELEASE_DATE,flock=self.flock_status(),search_impact=self.search_summary(),
                    announcements=[e for e in self.feed if e['seq']>cursor],pending=pending[:8],statuses=statuses[-16:])

    def dispatch(self,route,data):
        if route=='/announcements/poll':return self.poll(data)
        if route=='/announcements/request':return self.submit(data)
        if route=='/announcements/decide':return self.decide(data)
        raise AuthError('Unknown announcement operation.')

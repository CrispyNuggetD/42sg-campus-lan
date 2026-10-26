"""Campus file service on the existing broker listener; participants opt in."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import time
from ..auth import http_request,http_response
from .security import Gate,Identity,CampusProofs,Denied,campus_ip
from .store import Store
from .http import Requests


class Runtime:
    def __init__(self,broker,host,port,api_factory=None,root=None,owner=None):
        self.broker=broker;self.host=host;self.port=port;self.requests=None
        self.owner=owner or pwd.getpwuid(os.getuid()).pw_name
        self.root=root or Path.home()/'KoelDrop-server'
        self.api_factory=api_factory;self.lock=asyncio.Lock()
        self.public_available=False

    def start_public(self):
        """Explicit normal-host startup, not an import/constructor side effect."""
        from ..access import Policy,SG_CAMPUS_ID
        from .flock import ServiceGate,service_identity,LABEL,SCOPE
        policy_factory=self.broker.policy_factory or Policy
        campus_ip(self.host)
        uid=policy_factory().local_operator(admin=True)
        if self.api_factory:api,campus_id=self.api_factory()
        else:
            from ..campus_info import API
            api=API();campus_id=SG_CAMPUS_ID
        proofs=CampusProofs(api,campus_id)
        user=proofs._profile(uid)
        if user.get('id')!=uid or user.get('login')!=self.owner:raise Denied('The local operator and flock owner disagree.')
        actor=service_identity(uid,self.owner,self.host)
        gate=ServiceGate(self.broker,proofs,actor,policy_factory)
        gate.check(actor)
        fresh=self.requests is None
        store=Store(self.root,gate) if fresh else self.requests.store
        old_gate=store.gate
        try:
            store.gate=gate
            gid=store.start_flock(actor,self.host)
            if fresh:self.requests=Requests(store,actor,self.port)
            else:self.requests.host=actor
            import secrets
            self.requests.flock=dict(group=gid,epoch=secrets.token_hex(16),host=self.owner,
                                     scope=SCOPE,label=LABEL,campus_id=SG_CAMPUS_ID)
            self.public_available=True
        except Exception:
            store.gate=old_gate
            if fresh:store.close()
            raise

    def public_status(self):
        return dict(self.requests.flock) if self.public_available and self.requests and self.requests.flock else None

    def check_public(self):
        try:
            if not self.requests or not self.requests.flock:self.start_public()
            else:self.requests.store.gate.check(self.requests.host);self.public_available=True
        except (OSError,ValueError):
            self.public_available=False
            raise

    async def maintain_public(self):
        reported=None
        while True:
            async with self.lock:
                operation=asyncio.create_task(asyncio.to_thread(self.check_public))
                try:await asyncio.shield(operation)
                except asyncio.CancelledError:
                    await asyncio.gather(operation,return_exceptions=True)
                    raise
                except (OSError,ValueError):self.public_available=False
            if reported is not self.public_available:
                print('LAN42 42 Singapore flock '+('ready; verified campus members may opt in. Local and host copies are retained.' if self.public_available else 'waiting for approved campus host, fresh presence or private storage. Retrying in 30 seconds; local files are kept.'),flush=True)
                reported=self.public_available
            await asyncio.sleep(30)

    def _initialize(self,token,peer):
        campus_ip(self.host)
        record=self.broker.authenticate(token)
        if peer!=self.host or record['login']!=self.owner:raise Denied('The on-campus service owner must create the first group.')
        if self.api_factory:api,campus_id=self.api_factory()
        else:
            from ..campus_info import API,load
            from ..access import SG_CAMPUS_ID
            api=API();campus={'id':SG_CAMPUS_ID}
            campus_id=campus['id']
        gate=Gate(self.broker,CampusProofs(api,campus_id))
        actor=gate.admit(token,peer,True)
        store=Store(self.root,gate)
        try:self.requests=Requests(store,actor,self.port)
        except Exception:store.close();raise

    async def handle(self,reader,writer,first):
        try:
            method,target,headers=await asyncio.wait_for(http_request(reader,first),10)
            authorization=headers.get('authorization','')
            if (not writer.get_extra_info('ssl_object') or headers.get('host')!=self.host+':'+str(self.port)
                    or any(key in headers for key in ('origin','cookie','forwarded','x-forwarded-for','x-real-ip','upgrade'))
                    or not re.fullmatch(r'Bearer [a-f0-9]{64}',authorization)):raise Denied('Native pinned HTTPS required.')
            token=authorization[7:];self.broker.authenticate(token)
            peer=writer.get_extra_info('peername')[0]
            async with self.lock:
                if self.requests is None:
                    if method!='POST' or target!='/v1/groups':raise Denied('The host must create a group first.')
                    await asyncio.to_thread(self._initialize,token,peer)
                elif method=='POST' and target=='/v1/groups' and not self.requests.flock and not self.broker.active(self.requests.host.session_key):
                    record=self.broker.authenticate(token)
                    if peer!=self.host or record['login']!=self.owner:raise Denied('The host must sign in again.')
                    self.requests.host=await asyncio.to_thread(self.requests.store.gate.admit,token,peer,True)
            await self.requests.handle(reader,writer,parsed=(method,target,headers))
        except (ValueError,OSError,KeyError,TypeError,asyncio.TimeoutError):
            try:await http_response(writer,'403 Forbidden',json.dumps(dict(error='KoelDrop unavailable. Check owner group creation, current sign-in and campus eligibility.')))
            except (ValueError,OSError,asyncio.TimeoutError):pass

    async def deliver_invite(self,lobby,pid,message):
        if self.requests is None:raise Denied('KoelDrop is not active on this host.')
        sender=lobby.clients[pid]
        group=message.get('group');token=message.get('invite')
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise Denied('Invalid invitation.')
        record=self.broker.sessions.get(sender.get('session_key'))
        if not record:raise Denied('Sign in first.')
        actor=Identity(record['uid'],record['login'],sender['session_key'],record['expires'],sender['writer'].get_extra_info('peername')[0])
        def verify():
            store=self.requests.store
            with store.lock:
                row=store._group(actor,group)
                if row['host_uid']!=actor.uid:raise Denied('Only the group host can deliver invitations.')
                invite=store.db.execute('SELECT * FROM invites WHERE gid=? AND digest=?',(group,hashlib.sha256(token.encode()).hexdigest())).fetchone()
                if not invite or invite['used'] or invite['expires']<=time.time():raise Denied('Invitation has ended.')
                return dict(invite)
        invite=await asyncio.to_thread(verify)
        recipients={key for key,c in lobby.clients.items() if c.get('uid')==invite['uid'] and c.get('role')=='lobby'}
        if not recipients:raise Denied('Recipient must sign into this verified lobby first; invitation was not delivered.')
        await lobby.broadcast(dict(type='koel_invite',group=group,invite=token,host=actor.login,expires=invite['expires']),recipients)
        await lobby.event('KoelDrop invitation delivered to '+invite['login']+'.',{pid})

    def close(self):
        self.public_available=False
        if self.requests:
            gate=self.requests.store.gate
            if hasattr(gate,'running'):gate.running=False
            self.requests.store.close();self.requests=None

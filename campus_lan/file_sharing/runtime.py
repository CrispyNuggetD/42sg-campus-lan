"""Opt-in service on the existing broker HTTPS listener; no second port is opened."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import time
from ..auth import http_request,http_response
from .settings import ExperimentalSettings
from .security import Gate,Identity,CampusProofs,Denied,campus_ip
from .store import Store
from .http import Requests


class Runtime:
    def __init__(self,broker,host,port,api_factory=None,root=None,owner=None):
        self.broker=broker;self.host=host;self.port=port;self.requests=None
        self.owner=owner or pwd.getpwuid(os.getuid()).pw_name
        self.root=root or Path.home()/'KoelDrop-server'
        self.api_factory=api_factory;self.lock=asyncio.Lock();self.was_enabled=False

    def _initialize(self,token,peer):
        campus_ip(self.host)
        record=self.broker.authenticate(token)
        if peer!=self.host or record['login']!=self.owner:raise Denied('The on-campus service owner must create the first group.')
        if self.api_factory:api,campus_id=self.api_factory()
        else:
            from ..campus_info import API,load
            api=API();data=load();campus=(data or {}).get('campus')
            if not campus:
                campus=next((c for c in api.pages('campus') if 'singapore' in (str(c.get('name',''))+' '+str(c.get('slug',''))).lower()),None)
            if not campus:raise Denied('Singapore campus could not be resolved.')
            campus_id=campus['id']
        gate=Gate(self.broker,CampusProofs(api,campus_id),enabled=lambda:ExperimentalSettings().enabled)
        actor=gate.admit(token,peer,True)
        store=Store(self.root,gate)
        try:self.requests=Requests(store,actor,self.port)
        except Exception:store.close();raise

    async def handle(self,reader,writer,first):
        try:
            if not ExperimentalSettings().enabled:raise Denied('Host experimental features are off.')
            method,target,headers=await http_request(reader,first)
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
                elif method=='POST' and target=='/v1/groups' and not self.broker.active(self.requests.host.session_key):
                    record=self.broker.authenticate(token)
                    if peer!=self.host or record['login']!=self.owner:raise Denied('The host must sign in again.')
                    self.requests.host=await asyncio.to_thread(self.requests.store.gate.admit,token,peer,True)
            await self.requests.handle(reader,writer,parsed=(method,target,headers))
        except (ValueError,OSError,KeyError,TypeError,asyncio.TimeoutError):
            try:await http_response(writer,'403 Forbidden',json.dumps(dict(error='KoelDrop unavailable. Check experimental settings, owner group creation, current sign-in and campus eligibility.')))
            except (ValueError,OSError,asyncio.TimeoutError):pass

    async def deliver_invite(self,lobby,pid,message):
        if not ExperimentalSettings().enabled or self.requests is None:raise Denied('KoelDrop is not active on this host.')
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

    async def monitor(self):
        try:
            while True:
                enabled=ExperimentalSettings().enabled
                if self.was_enabled and not enabled and self.requests:
                    store=self.requests.store
                    def close_groups():
                        with store.transaction():store.db.execute('UPDATE groups SET closed=1')
                    await asyncio.to_thread(close_groups)
                self.was_enabled=enabled
                await asyncio.sleep(1)
        finally:pass

    def close(self):
        if self.requests:self.requests.store.close();self.requests=None

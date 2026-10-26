"""Pinned-host polling and native-client announcement operations; no mesh authority."""
import hashlib
import json
import os
from pathlib import Path
import queue
import socket
import threading
import time
from . import auth_client,auth_locator
from .auth import config_dir,private_read,private_write,AuthError


class HostSettings:
    def __init__(self):
        self.path=config_dir()/'host-settings.json'
        self.data=dict(discovery=True,auto_join=True,interval=120)
        try:
            data=json.loads(private_read(self.path))
            if (not isinstance(data,dict) or set(data)-set(self.data) or
                any(type(data.get(k,self.data[k])) is not bool for k in ('discovery','auto_join')) or
                type(data.get('interval',120)) is not int or not 60<=data.get('interval',120)<=300):raise ValueError()
            self.data.update(data)
        except FileNotFoundError:pass
        except (OSError,ValueError):self.data.update(discovery=False,auto_join=False)

    def set(self,key,value):
        candidate=dict(self.data);candidate[key]=value
        if key not in self.data or (key=='interval' and (type(value) is not int or not 60<=value<=300)) or (key!='interval' and type(value) is not bool):
            raise ValueError('Host polling uses 60–300 seconds; discovery/auto-join use on|off.')
        private_write(self.path,json.dumps(candidate));self.data=candidate


def credentials(trust):
    result={}
    try:session=auth_client.load_session(trust)
    except (OSError,ValueError):session=None
    if session:result['session']=session['session']
    try:
        admin=json.loads(private_read(config_dir()/'announcement-admin.json'))
        if admin.get('fingerprint')==auth_client.fingerprint(trust) and isinstance(admin.get('token'),str):result['admin']=admin['token']
    except (OSError,ValueError,AttributeError):pass
    return result


def act(route,**values):
    trust=auth_client.load_trust();payload=credentials(trust)
    payload.update(values)
    return auth_client.post(trust,'/announcements/'+route,payload)


def claim(ident):
    """One desktop popup per local account, even with HQ/game windows open."""
    directory=config_dir()/'announcement-notices';directory.mkdir(parents=True,exist_ok=True,mode=0o700)
    scope=socket.gethostname()+':'+str(os.getuid())+':'+ident
    path=directory/hashlib.sha256(scope.encode()).hexdigest()
    try:
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        os.close(fd)
    except OSError:return False
    for old in list(directory.iterdir())[:256]:
        try:
            if time.time()-old.stat().st_mtime>86400:old.unlink()
        except OSError:pass
    return True


class HostWatch:
    def __init__(self,inbox,clock=time.monotonic):
        self.inbox,self.clock=inbox,clock
        self.closed=threading.Event();self.online=False;self.cursor=0;self.epoch=None
        self.next_locator=0;self.next_poll=0;self.reported_offline=None;self.offline_since=None
        self.thread=threading.Thread(target=self.run,daemon=True)

    def start(self):self.thread.start()
    def close(self):self.closed.set()

    def put(self,**message):
        try:self.inbox.put_nowait(dict(type='local_host_update',**message))
        except queue.Full:pass

    def step(self):
        settings=HostSettings().data;now=self.clock()
        if now<self.next_poll:return
        configured=False
        try:
            trust=auth_client.load_trust();configured=True
            if settings['discovery'] and now>=self.next_locator:
                self.next_locator=now+settings['interval'];auth_locator.refresh();trust=auth_client.load_trust()
            payload=credentials(trust);payload['cursor']=self.cursor
            data=auth_client.post(trust,'/announcements/poll',payload)
            if not isinstance(data.get('owner'),str) or not isinstance(data.get('epoch'),str):raise ValueError()
            changed=self.epoch!=data['epoch']
            outage=now-self.offline_since if self.offline_since is not None else 0
            notify_arrival=self.epoch is None or outage>=60
            if changed:self.cursor=0
            recovered=not self.online or changed
            self.online=True;self.offline_since=None;self.reported_offline=None;self.epoch=data['epoch'];self.next_poll=now+5
            entries=data.get('announcements',[])
            if not isinstance(entries,list):raise ValueError()
            valid=[]
            for event in entries[:10]:
                if (isinstance(event,dict) and type(event.get('seq')) is int and event['seq']>self.cursor
                        and isinstance(event.get('id'),str) and len(event['id'])==32
                        and isinstance(event.get('author'),str) and isinstance(event.get('text'),str)
                        and len(event['text'].encode())<=400 and type(event.get('is_host')) is bool):
                    valid.append(event);self.cursor=max(self.cursor,event['seq'])
            self.put(online=True,recovered=recovered,notify_arrival=notify_arrival,outage_seconds=outage,host=trust['lobby_host'],port=trust['lobby_port'],
                     auto_join=settings['auto_join'],auto_connect=settings['discovery'],retry_interval=settings['interval'],
                     data=dict(data,announcements=valid))
        except (OSError,ValueError,TypeError,KeyError):
            if self.offline_since is None:self.offline_since=now
            if self.online or self.reported_offline is not configured:
                self.put(online=False,configured=configured,retry_interval=settings['interval'])
            self.reported_offline=configured;self.online=False;self.next_poll=now+settings['interval']

    def run(self):
        while not self.closed.is_set():
            self.step()
            self.closed.wait(1)

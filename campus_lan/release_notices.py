"""Per-computer persistent notice budgeting, shared by HQ and games."""
from contextlib import contextmanager
import fcntl
import json
import os
import time
from .auth import private_read,private_write,config_dir
from .local_console import local_path

COALESCE=30*60
COOLDOWN=24*3600


@contextmanager
def state_file(name,per_computer=True):
    path=local_path(name) if per_computer else config_dir()/(name+'.json');path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    lock=path.with_suffix('.lock')
    fd=os.open(lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as guard:
        private_read(lock);fcntl.flock(guard,fcntl.LOCK_EX)
        try:data=json.loads(private_read(path))
        except FileNotFoundError:data={}
        if not isinstance(data,dict):raise ValueError('Invalid notice budget.')
        yield path,data


def reserve(name,cooldown,clock=None):
    with state_file(name) as (path,data):
        now=(clock or time.time)();last=data.get('last')
        if last is not None and (type(last) not in (int,float) or now-last<cooldown):return False
        private_write(path,json.dumps(dict(last=now)));return True


def release(version,date,silenced=False,clock=None):
    """Returns (version changed, popup due). New versions replace pending digests."""
    with state_file('last-host-release') as (path,data):
        now=(clock or time.time)();previous=data.get('version');changed=previous!=version
        if not previous:
            private_write(path,json.dumps(dict(version=version,date=date,changed=now,last=0,pending=False)))
            return False,False
        original=dict(data)
        if changed:data.update(version=version,date=date,changed=now,pending=True)
        due=(data.get('pending') is True and not silenced and now-data.get('changed',now)>=COALESCE
             and (not data.get('last') or now-data['last']>=COOLDOWN))
        if due:data.update(last=now,pending=False)
        if data!=original:private_write(path,json.dumps(data))
        return changed,due

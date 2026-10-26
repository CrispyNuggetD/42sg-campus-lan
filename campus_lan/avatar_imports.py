"""Import only owner-created, one-use browser-save jobs; never scan downloads."""
import os
import json
from pathlib import Path
import re
import secrets
import stat
import subprocess
import threading
import time
from .avatar_cache import key,MAX_IMAGE
from .auth import config_dir,private_read,private_write


def downloads_directory():
    try:
        settings=json.loads(private_read(config_dir()/'avatar-downloads.json'))
        path=Path(settings['directory'])
        if path.is_absolute():return path
    except (OSError,ValueError,KeyError,TypeError):pass
    try:
        result=subprocess.run(['xdg-user-dir','DOWNLOAD'],capture_output=True,text=True,timeout=2,check=True)
        path=Path(result.stdout.strip())
        if path.is_absolute():return path
    except (OSError,subprocess.SubprocessError):pass
    return Path.home()/'Downloads'


def configure_downloads(directory):
    path=Path(directory).expanduser()
    if not path.is_absolute() or not path.is_dir() or path.stat().st_uid!=os.getuid():
        raise ValueError('Choose your existing absolute Chrome download directory')
    path=path.resolve()
    if any((p/'.git').exists() for p in [path,*path.parents]):raise ValueError('Download staging must be outside Git')
    private_write(config_dir()/'avatar-downloads.json',json.dumps(dict(directory=str(path))))
    return path


class BrowserImports:
    def __init__(self,cache,downloads=None):
        self.cache=cache
        self.root=Path(downloads or downloads_directory()).resolve()/'lan42-avatar-imports'
        if self.root.is_symlink() or any((p/'.git').exists() for p in [self.root,*self.root.parents]):
            raise ValueError('Browser import folder must be private and outside Git')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700);self.root.chmod(0o700)
        if self.root.stat().st_uid!=os.getuid():raise ValueError('Import folder belongs to another user')
        self.jobs={};self.lock=threading.Lock();self.stop=threading.Event()
        self.thread=threading.Thread(target=self.watch,daemon=True);self.thread.start()

    def set_directory(self,directory):
        path=configure_downloads(directory)/'lan42-avatar-imports'
        if path.is_symlink():raise ValueError('Import folder must not be a symlink')
        path.mkdir(parents=True,exist_ok=True,mode=0o700);path.chmod(0o700)
        with self.lock:self.root=path
        return dict(directory=str(path.parent),expected_directory=str(path))

    def prepare(self,login):
        key(login)
        with self.lock:
            now=time.time()
            self.jobs={k:v for k,v in self.jobs.items() if now-v['created']<600}
            if sum(v['status']=='waiting_for_browser_save' for v in self.jobs.values())>=20:raise ValueError('Too many pending imports')
            job=secrets.token_hex(16);self.jobs[job]=dict(login=login,created=now,status='waiting_for_browser_save')
            return dict(job=job,expected_directory=str(self.root))

    def status(self,job):
        with self.lock:
            record=self.jobs.get(job)
            if not record:return dict(status='expired')
            if time.time()-record['created']>=600:return dict(status='expired')
            return dict(status=record['status'])

    def consume(self,job):
        with self.lock:
            record=self.jobs.get(job)
            if not record or record['status']!='waiting_for_browser_save' or time.time()-record['created']>=600:return
            path=self.root/(job+'.png')
            try:fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
            except FileNotFoundError:return
            except OSError:record['status']='invalid_file';return
            try:
                with os.fdopen(fd,'rb') as source:
                    info=os.fstat(source.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_uid!=os.getuid() or info.st_size>MAX_IMAGE:raise ValueError()
                    data=source.read(MAX_IMAGE+1)
                self.cache.store(record['login'],data,'browser-user-action')
                record['status']='cached';path.unlink()
            except (OSError,ValueError):record['status']='invalid_image'

    def watch(self):
        while not self.stop.wait(.5):
            with self.lock:jobs=list(self.jobs)
            for job in jobs:self.consume(job)

    def close(self):
        self.stop.set();self.thread.join(timeout=2)

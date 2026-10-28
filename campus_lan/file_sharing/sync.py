"""Explicit, offline-testable mirror operations. No polling or filesystem watcher."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import stat
from .paths import logical_path,private_directory
from .security import Denied,Conflict,Limit
from .store import MAX_FILE,MAX_FILES


@dataclass(frozen=True)
class Offer:
    path:str
    version:str
    digest:str
    size:int
    author_uid:int
    author:str
    deleted:bool


@dataclass(frozen=True)
class ReceivePolicy:
    allowed_uids:frozenset=frozenset()
    friend_names:frozenset=frozenset()

    def allows(self,offer):
        # File approvals never implicitly approve deleting existing files.
        return not offer.deleted and (offer.author_uid in self.allowed_uids or offer.author in self.friend_names)


class Mirror:
    def __init__(self,path,uid,login,policy=None,*,resume=False):
        path=Path(path).expanduser()
        if path==Path.home() or path==Path('/') or any(p.startswith('.') for p in path.parts[1:]):raise Denied('Choose a dedicated non-hidden empty folder.')
        self.fd=private_directory(path,create=True)
        if os.listdir(self.fd) and not resume:os.close(self.fd);raise Denied('Choose an empty folder; existing personal files are never imported implicitly.')
        if any((p/'.git').exists() for p in (path,*path.parents)):os.close(self.fd);raise Denied('Sync folders must be outside Git.')
        self.resume=resume
        self.path=path;self.uid=uid;self.login=login;self.policy=policy or ReceivePolicy()
        self.known={};self.members=set();self.backup_bytes=0

    def close(self):os.close(self.fd)

    def relocate(self,path):
        # Leaves old copies intact; no silent move/delete of personal files.
        new=Mirror(path,self.uid,self.login,self.policy);self.close();return new

    def initialize_info(self,welcome,events):
        """Install generated read-only information once; never overwrite a user file."""
        if not isinstance(welcome,str) or len(welcome.encode())>4096 or not isinstance(events,list) or len(events)>200:raise Limit('Generated information is too large.')
        log=json.dumps(events,sort_keys=True,indent=2).encode()
        if len(log)>256*1024:raise Limit('Audit snapshot is too large.')
        for path,data in (('welcome.md',welcome.encode()),('logs/activity.json',log)):
            parent,name=self._parent(path,True)
            try:
                try:fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o400,dir_fd=parent)
                except FileExistsError:
                    if self.resume:continue
                    raise
                with os.fdopen(fd,'wb') as output:output.write(data)
            finally:os.close(parent)

    def _parent(self,path,create=False):
        parts=logical_path(path).split('/');fd=os.dup(self.fd)
        try:
            for component in parts[:-1]:
                if create:
                    try:os.mkdir(component,0o700,dir_fd=fd)
                    except FileExistsError:pass
                next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
                os.close(fd);fd=next_fd
            return fd,parts[-1]
        except Exception:os.close(fd);raise

    def _read(self,path):
        try:parent,name=self._parent(path)
        except FileNotFoundError:return None
        try:
            try:fd=os.open(name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=parent)
            except FileNotFoundError:return None
            with os.fdopen(fd,'rb') as source:
                info=os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_FILE:raise Denied('Only bounded regular files with no links may sync.')
                return source.read(MAX_FILE+1)
        finally:os.close(parent)

    def offers(self,manifest):
        files=manifest.get('files',[])
        if not isinstance(files,list) or len(files)>MAX_FILES:raise Limit('Manifest is too large.')
        self.append_only=manifest.get('append_only') is True
        members=manifest.get('members',[])
        if not isinstance(members,list) or len(members)>64 or any(not isinstance(n,str) or not re.fullmatch(r'[a-z0-9_.-]{1,24}',n) for n in members):raise Denied('Invalid member manifest.')
        self.members=set(members);offers=[]
        for record in files:
            path=logical_path(record['path']);version=record['version'];deleted=record['deleted']
            if (path.split('/')[0] in ('logs','welcome.md') or not re.fullmatch(r'[a-f0-9]{32}',version)
                    or type(record['size']) is not int or not 0<=record['size']<=MAX_FILE
                    or type(record['author_uid']) is not int or record['author_uid']<=0
                    or not re.fullmatch(r'[a-z0-9_.-]{1,24}',record['author'])
                    or deleted not in (0,1,False,True)
                    or (not deleted and not re.fullmatch(r'[a-f0-9]{64}',record['digest']))):raise Denied('Invalid file metadata.')
            if self.append_only and deleted:continue
            if self.known.get(path,{}).get('version')!=version:
                offers.append(Offer(path,version,record['digest'],record['size'],record['author_uid'],record['author'],bool(deleted)))
        return offers

    def _backup(self,parent,name,baseline):
        if self.backup_bytes+MAX_FILE>128*1024*1024:raise Limit('Local backup quota reached.')
        try:os.mkdir('.lan42-file-backups',0o700,dir_fd=self.fd)
        except FileExistsError:pass
        backups=os.open('.lan42-file-backups',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.fd)
        backup=secrets.token_hex(16)+'.bak'
        try:
            os.rename(name,backup,src_dir_fd=parent,dst_dir_fd=backups)
            fd=os.open(backup,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=backups)
            with os.fdopen(fd,'rb') as source:
                info=os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>MAX_FILE:raise Conflict('Changed local entry preserved in .lan42-file-backups; no incoming file installed.')
                data=source.read(MAX_FILE+1)
            self.backup_bytes+=len(data)
            if hashlib.sha256(data).hexdigest()!=baseline:
                # Restore only if the original name is still vacant; never clobber an editor's new file.
                try:
                    os.link(backup,name,src_dir_fd=backups,dst_dir_fd=parent,follow_symlinks=False)
                    os.unlink(backup,dir_fd=backups);self.backup_bytes-=len(data)
                except FileExistsError:pass
                raise Conflict('Concurrent local edits preserved; no incoming file installed.')
        finally:os.close(backups)

    def receive(self,offer,fetch,approved=False):
        if not isinstance(offer,Offer):raise Denied('A validated offer is required.')
        logical_path(offer.path)
        if self.known.get(offer.path,{}).get('version')==offer.version:return 'unchanged'
        if not approved and not self.policy.allows(offer):raise Denied('User approval is required before receiving this change.')
        current=self._read(offer.path);baseline=self.known.get(offer.path,{}).get('digest')
        current_hash=hashlib.sha256(current).hexdigest() if current is not None else None
        if current_hash!=baseline:raise Conflict('Local file changed; no incoming overwrite or deletion was performed.')
        if offer.deleted:
            if current is not None:
                parent,name=self._parent(offer.path)
                try:self._backup(parent,name,baseline)
                finally:os.close(parent)
            self.known[offer.path]=dict(version=offer.version,digest=None)
            return 'deleted'
        data=fetch(offer.version)
        if not isinstance(data,bytes) or len(data)!=offer.size or hashlib.sha256(data).hexdigest()!=offer.digest:raise Denied('Downloaded file integrity failed.')
        parent,name=self._parent(offer.path,True);temporary='.lan42-transfer-'+secrets.token_hex(16)
        try:
            # Recheck immediately before installation; no symlink is followed.
            after=self._read(offer.path)
            if (hashlib.sha256(after).hexdigest() if after is not None else None)!=baseline:raise Conflict('Local file changed while receiving.')
            mode=0o400 if offer.path.split('/')[0] in self.members-{self.login} else 0o600
            fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,mode,dir_fd=parent)
            try:
                with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
                if current is not None:self._backup(parent,name,baseline)
                try:os.link(temporary,name,src_dir_fd=parent,dst_dir_fd=parent,follow_symlinks=False)
                except FileExistsError:raise Conflict('A local file appeared during receive; it was not overwritten. Previous copy remains in .lan42-file-backups.')
            finally:
                try:os.unlink(temporary,dir_fd=parent)
                except FileNotFoundError:pass
        finally:os.close(parent)
        self.known[offer.path]=dict(version=offer.version,digest=offer.digest)
        return 'received'

    def upload(self,path,publish,approved=False):
        path=logical_path(path)
        if not approved:raise Denied('Publishing a local file requires an explicit action.')
        first=path.split('/')[0]
        if first in ('logs','welcome.md') or (first in self.members and first!=self.login):raise Denied('Other members’ folders and audit history are read-only.')
        data=self._read(path)
        if data is None:raise Denied('Local file does not exist.')
        expected=self.known.get(path,{}).get('version')
        result=publish(path,data,expected)
        if result.get('digest')!=hashlib.sha256(data).hexdigest():raise Denied('Server upload acknowledgement did not match.')
        assigned=logical_path(result.get('path',path))
        if 'path' in result:
            if (result.get('author')!=self.login or type(result.get('number')) is not int or result['number']<1
                    or Path(assigned).parent!=Path(path).parent
                    or assigned.split('/')[0] in {'logs','welcome.md'}
                    or assigned.split('/')[0] in self.members-{self.login}):
                raise Denied('Invalid host-assigned upload receipt.')
        if assigned!=path:
            # Install the host-assigned name from our own verified bytes. Never
            # rename/remove the source or overwrite a pre-existing local entry.
            parent,name=self._parent(assigned,True)
            try:
                try:fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
                except FileExistsError:fd=None
                if fd is not None:
                    with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
            finally:os.close(parent)
            if self._read(assigned)==data:
                self.known[assigned]=dict(version=result['version'],digest=result['digest'])
        self.known[path]=dict(version=result['version'],digest=result['digest'])
        return result

    def scan_writable(self):
        """Explicit bounded scan of the chosen root; never follow links or run a watcher."""
        result={};total=0
        for directory,subdirs,files,fd in os.fwalk('.',dir_fd=self.fd,follow_symlinks=False):
            prefix='' if directory=='.' else directory[2:]
            kept=[]
            for name in subdirs:
                if name.startswith('.') or (not prefix and (name=='logs' or name in self.members-{self.login})):continue
                if stat.S_ISLNK(os.stat(name,dir_fd=fd,follow_symlinks=False).st_mode):raise Denied('Symlink directories cannot be synced.')
                path=logical_path(prefix+'/'+name if prefix else name)
                kept.append(name)
            subdirs[:]=kept
            for name in files:
                if name.startswith('.') or (not prefix and name=='welcome.md'):continue
                path=logical_path(prefix+'/'+name if prefix else name)
                if len(result)>=MAX_FILES:raise Limit('Too many local files.')
                data=self._read(path)
                if data is None:continue
                total+=len(data)
                if total>128*1024*1024:raise Limit('Local sync content quota reached.')
                result[path]=hashlib.sha256(data).hexdigest()
        return result

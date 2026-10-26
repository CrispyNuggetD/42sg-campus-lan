"""Offline-testable File-sharing core. No sockets, directory watcher or auto execution."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import threading
import time
from .paths import logical_path,private_directory
from .security import Denied,Conflict,Limit,Identity

MAX_FILE=8*1024*1024
MAX_STORAGE=128*1024*1024
MAX_FILES=512
MAX_MEMBERS=16
WELCOME=b'# LAN42 file sharing\n\nCampus-only group. Files are data; nothing is executed or extracted.\nMember folders are owner-writable and group-readable. Shared root files are collaborative.\nLocal copies remain on leave or host shutdown. No directory expiry or automatic cleanup; manage retained copies yourself.\n'


class Store:
    def __init__(self,root,gate,clock=time.time):
        self.root=Path(root).expanduser();self.gate=gate;self.clock=clock
        self.root_fd=private_directory(self.root,create=True)
        if any((p/'.git').exists() for p in (self.root,*self.root.parents)):
            os.close(self.root_fd);raise Denied('File storage must be outside Git.')
        try:
            try:os.mkdir('objects',0o700,dir_fd=self.root_fd)
            except FileExistsError:pass
            self.objects=os.open('objects',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=self.root_fd)
            info=os.fstat(self.objects)
            if info.st_uid!=os.getuid() or info.st_mode&0o077:raise Denied('Object directory must be private.')
            fd=os.open('files.sqlite',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600,dir_fd=self.root_fd)
            info=os.fstat(fd);os.close(fd)
            if info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1 or not stat.S_ISREG(info.st_mode):raise Denied('Database must be a private regular file.')
            self.db=sqlite3.connect(str(self.root/'files.sqlite'),check_same_thread=False,timeout=5)
            self.db.row_factory=sqlite3.Row
            self.db.executescript('''
                PRAGMA foreign_keys=ON;
                CREATE TABLE IF NOT EXISTS groups(gid TEXT PRIMARY KEY,host_uid INTEGER,host_login TEXT,host_key TEXT,expires REAL,peer TEXT,closed INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS service_flocks(scope TEXT PRIMARY KEY,gid TEXT);
                CREATE TABLE IF NOT EXISTS members(gid TEXT,uid INTEGER,login TEXT,session_key TEXT,expires REAL,PRIMARY KEY(gid,uid),UNIQUE(gid,login));
                CREATE TABLE IF NOT EXISTS identities(gid TEXT,uid INTEGER,login TEXT,PRIMARY KEY(gid,uid),UNIQUE(gid,login));
                CREATE TABLE IF NOT EXISTS invites(digest TEXT PRIMARY KEY,gid TEXT,uid INTEGER,login TEXT,expires REAL,used INTEGER DEFAULT 0);
                CREATE TABLE IF NOT EXISTS files(gid TEXT,path TEXT,version TEXT,deleted INTEGER,PRIMARY KEY(gid,path));
                CREATE TABLE IF NOT EXISTS versions(version TEXT PRIMARY KEY,gid TEXT,path TEXT,digest TEXT,size INTEGER,author_uid INTEGER,author TEXT,deleted INTEGER);
                CREATE TABLE IF NOT EXISTS audit(seq INTEGER PRIMARY KEY AUTOINCREMENT,gid TEXT,payload TEXT,previous TEXT,hash TEXT);
            ''')
            self.lock=threading.RLock();self.rates={}
        except Exception:
            if hasattr(self,'objects'):os.close(self.objects)
            os.close(self.root_fd);raise

    def close(self):
        with self.lock:
            self.db.close();os.close(self.objects);os.close(self.root_fd)

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:yield;self.db.commit()
            except Exception:self.db.rollback();raise

    def _rate(self,actor):
        now=self.clock();self.rates={uid:v for uid,v in self.rates.items() if now-v[0]<60}
        start,count=self.rates.get(actor.uid,(now,0))
        if count>=90:raise Limit('File request budget reached; wait a minute.')
        self.rates[actor.uid]=(start,count+1)

    def _event(self,gid,actor,operation,**fields):
        if self.db.execute('SELECT count(*) FROM audit WHERE gid=?',(gid,)).fetchone()[0]>=5000:raise Limit('Audit event quota reached.')
        row=self.db.execute('SELECT hash FROM audit WHERE gid=? ORDER BY seq DESC LIMIT 1',(gid,)).fetchone()
        previous=row['hash'] if row else '0'*64
        payload=json.dumps(dict(at=self.clock(),actor=actor.login,uid=actor.uid,operation=operation,**fields),sort_keys=True,separators=(',',':'))
        digest=hashlib.sha256((previous+payload).encode()).hexdigest()
        self.db.execute('INSERT INTO audit(gid,payload,previous,hash) VALUES(?,?,?,?)',(gid,payload,previous,digest))

    def _group(self,actor,gid,member=True):
        self.gate.check(actor);self._rate(actor)
        if not isinstance(gid,str) or not re.fullmatch(r'[a-f0-9]{32}',gid):raise Denied('Unknown group.')
        group=self.db.execute('SELECT * FROM groups WHERE gid=?',(gid,)).fetchone()
        if not group or group['closed'] or group['expires']<=self.clock():raise Denied('Group session has ended.')
        host=Identity(group['host_uid'],group['host_login'],group['host_key'],group['expires'],group['peer'])
        self.gate.check(host)
        if member:
            record=self.db.execute('SELECT * FROM members WHERE gid=? AND uid=?',(gid,actor.uid)).fetchone()
            if not record or record['session_key']!=actor.session_key or record['expires']<=self.clock():raise Denied('Accept a new invitation for this session.')
        return group

    def _write_allowed(self,actor,gid,path):
        path=logical_path(path);parts=path.split('/')
        if parts[0] in ('welcome.md','logs'):raise Denied('Welcome and audit history are read-only.')
        owner=self.db.execute('SELECT uid FROM identities WHERE gid=? AND login=?',(gid,parts[0])).fetchone()
        if owner:
            if len(parts)<2 or owner['uid']!=actor.uid:raise Denied('Only the member may write their folder.')
        elif len(parts)>1 and parts[0]!='shared':raise Denied('Use your member folder, shared/, or a file at the shared root.')
        elif parts[0]=='shared' and len(parts)==1:raise Denied('Shared is a reserved directory.')
        return path

    def create(self,host,bind_ip):
        self.gate.check(host)
        if bind_ip!=host.peer_ip:raise Denied('Bind exactly to the verified host campus interface.')
        if host.login in ('welcome.md','logs','shared'):raise Denied('Login conflicts with a reserved namespace.')
        gid=secrets.token_hex(16)
        with self.transaction():
            count=self.db.execute('SELECT count(*) FROM groups WHERE closed=0 AND expires>?',(self.clock(),)).fetchone()[0]
            if count>=8 or self.db.execute('SELECT count(*) FROM groups').fetchone()[0]>=32:raise Limit('Group quota reached.')
            self.db.execute('INSERT INTO groups VALUES(?,?,?,?,?,?,0)',(gid,host.uid,host.login,host.session_key,host.expires,bind_ip))
            self.db.execute('INSERT INTO members VALUES(?,?,?,?,?)',(gid,host.uid,host.login,host.session_key,host.expires))
            self.db.execute('INSERT INTO identities VALUES(?,?,?)',(gid,host.uid,host.login))
            self._event(gid,host,'group_created')
        return gid

    def start_flock(self,host,bind_ip):
        """Resume host-retained files, but never carry memberships across starts."""
        self.gate.check(host)
        if bind_ip!=host.peer_ip:raise Denied('The flock must use its campus interface.')
        with self.lock:
            existing=self.db.execute("SELECT g.* FROM service_flocks f JOIN groups g ON g.gid=f.gid WHERE f.scope='42-singapore'").fetchone()
            if existing:
                if existing['host_uid']!=host.uid or existing['host_login']!=host.login:raise Denied('Flock owner changed; review retained storage.')
                gid=existing['gid']
                with self.transaction():
                    self.db.execute('UPDATE groups SET host_key=?,expires=?,peer=?,closed=0 WHERE gid=?',(host.session_key,host.expires,bind_ip,gid))
                    self.db.execute('DELETE FROM members WHERE gid=?',(gid,))
                    self.db.execute('DELETE FROM invites WHERE gid=?',(gid,))
                    self.db.execute('INSERT INTO members VALUES(?,?,?,?,?)',(gid,host.uid,host.login,host.session_key,host.expires))
                    self._event(gid,host,'flock_restarted')
                return gid
            gid=self.create(host,bind_ip)
            with self.transaction():self.db.execute("INSERT INTO service_flocks VALUES('42-singapore',?)",(gid,))
            return gid

    def join_flock(self,actor,gid):
        # This entry point is used only by the host-selected /v1/flock/join route.
        with self.transaction():
            group=self._group(actor,gid,member=False)
            if not self.db.execute('SELECT 1 FROM service_flocks WHERE gid=?',(gid,)).fetchone():raise Denied('Not a public campus flock.')
            if actor.login in ('welcome.md','logs','shared'):raise Denied('Reserved member namespace.')
            if self.db.execute('SELECT 1 FROM files WHERE gid=? AND path=? AND deleted=0',(gid,actor.login)).fetchone():raise Conflict('A file occupies the member namespace.')
            for row in self.db.execute('SELECT uid,session_key,expires FROM members WHERE gid=?',(gid,)).fetchall():
                if row['uid']!=group['host_uid'] and (row['expires']<=self.clock() or not self.gate.broker.active(row['session_key'])):
                    self.db.execute('DELETE FROM members WHERE gid=? AND uid=?',(gid,row['uid']))
            active=self.db.execute('SELECT count(*) FROM members WHERE gid=?',(gid,)).fetchone()[0]
            if active>=MAX_MEMBERS and not self.db.execute('SELECT 1 FROM members WHERE gid=? AND uid=?',(gid,actor.uid)).fetchone():raise Limit('The flock is full (16 active members); try after someone leaves.')
            count=self.db.execute('SELECT count(*) FROM identities WHERE gid=?',(gid,)).fetchone()[0]
            if count>=64 and not self.db.execute('SELECT 1 FROM identities WHERE gid=? AND uid=?',(gid,actor.uid)).fetchone():raise Limit('Flock namespace capacity reached (64 people).')
            named=self.db.execute('SELECT uid FROM identities WHERE gid=? AND login=?',(gid,actor.login)).fetchone()
            if named and named['uid']!=actor.uid:raise Denied('Member namespace belongs to another identity.')
            self.db.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?)',(gid,actor.uid,actor.login))
            self.db.execute('INSERT OR REPLACE INTO members VALUES(?,?,?,?,?)',(gid,actor.uid,actor.login,actor.session_key,actor.expires))
            self._event(gid,actor,'flock_joined')

    def invite(self,actor,gid,target_login):
        with self.transaction():
            group=self._group(actor,gid)
            if actor.uid!=group['host_uid']:raise Denied('Only the host may invite members.')
            uid,name=self.gate.proofs.target(target_login)
            if name in ('welcome.md','logs','shared'):raise Denied('Reserved member namespace.')
            if self.db.execute('SELECT 1 FROM files WHERE gid=? AND path=? AND deleted=0',(gid,name)).fetchone():raise Conflict('A shared root file occupies that member name.')
            if self.db.execute('SELECT count(*) FROM invites WHERE gid=? AND used=0 AND expires>?',(gid,self.clock())).fetchone()[0]>=32:raise Limit('Too many outstanding invitations.')
            if self.db.execute('SELECT count(*) FROM identities WHERE gid=?',(gid,)).fetchone()[0]>=64 and not self.db.execute('SELECT 1 FROM identities WHERE gid=? AND uid=?',(gid,uid)).fetchone():raise Limit('Member namespace quota reached.')
            self.db.execute('INSERT OR IGNORE INTO identities VALUES(?,?,?)',(gid,uid,name))
            token=secrets.token_urlsafe(32);digest=hashlib.sha256(token.encode()).hexdigest()
            expiry=min(group['expires'],self.clock()+300)
            self.db.execute('INSERT INTO invites VALUES(?,?,?,?,?,0)',(digest,gid,uid,name,expiry))
            self._event(gid,actor,'invite_created',recipient=name)
        return dict(invite=token,expires=expiry,recipient=name)

    def accept(self,actor,gid,token):
        if not isinstance(token,str) or not re.fullmatch(r'[A-Za-z0-9_-]{43}',token):raise Denied('Invalid invitation.')
        with self.transaction():
            self._group(actor,gid,member=False)
            invite=self.db.execute('SELECT * FROM invites WHERE digest=? AND gid=?',(hashlib.sha256(token.encode()).hexdigest(),gid)).fetchone()
            if not invite or invite['used'] or invite['expires']<=self.clock() or invite['uid']!=actor.uid or invite['login']!=actor.login:raise Denied('Invitation is expired, used, or for another account.')
            if self.db.execute('SELECT count(*) FROM members WHERE gid=?',(gid,)).fetchone()[0]>=MAX_MEMBERS:raise Limit('Group is full.')
            self.db.execute('INSERT OR REPLACE INTO members VALUES(?,?,?,?,?)',(gid,actor.uid,actor.login,actor.session_key,actor.expires))
            self.db.execute('UPDATE invites SET used=1 WHERE digest=?',(invite['digest'],))
            self._event(gid,actor,'invite_accepted')

    def leave(self,actor,gid):
        with self.transaction():
            group=self._group(actor,gid)
            if actor.uid==group['host_uid'] and actor.session_key==group['host_key']:self.db.execute('UPDATE groups SET closed=1 WHERE gid=?',(gid,))
            else:self.db.execute('DELETE FROM members WHERE gid=? AND uid=?',(gid,actor.uid))
            self._event(gid,actor,'group_closed' if actor.uid==group['host_uid'] and actor.session_key==group['host_key'] else 'member_left')

    def manifest(self,actor,gid):
        with self.lock:
            self._group(actor,gid)
            files=[dict(row) for row in self.db.execute('SELECT f.path,f.version,f.deleted,v.digest,v.size,v.author_uid,v.author FROM files f JOIN versions v ON f.version=v.version WHERE f.gid=? ORDER BY f.path',(gid,))]
            members=[row['login'] for row in self.db.execute('SELECT login FROM identities WHERE gid=?',(gid,))]
            return dict(files=files,members=members,welcome=WELCOME.decode(),limits=dict(file_bytes=MAX_FILE,retained_bytes=MAX_STORAGE))

    def put(self,actor,gid,path,data,expected=None):
        if not isinstance(data,bytes) or len(data)>MAX_FILE:raise Limit('A file must be at most 8 MiB.')
        version=secrets.token_hex(16);written=False
        try:
            with self.transaction():
                self._group(actor,gid);path=self._write_allowed(actor,gid,path)
                parts=path.split('/')
                for i in range(1,len(parts)):
                    if self.db.execute('SELECT 1 FROM files WHERE gid=? AND path=? AND deleted=0',(gid,'/'.join(parts[:i]))).fetchone():raise Conflict('A file occupies a parent directory.')
                prefix=path+'/'
                if self.db.execute('SELECT 1 FROM files WHERE gid=? AND substr(path,1,?)=? AND deleted=0',(gid,len(prefix),prefix)).fetchone():raise Conflict('A directory occupies that file name.')
                old=self.db.execute('SELECT version FROM files WHERE gid=? AND path=?',(gid,path)).fetchone()
                if (old['version'] if old else None)!=expected:raise Conflict('File changed; fetch the new version before writing.')
                used=self.db.execute('SELECT coalesce(sum(size),0) FROM versions WHERE gid=?',(gid,)).fetchone()[0]
                total=self.db.execute('SELECT coalesce(sum(size),0) FROM versions').fetchone()[0]
                if total+len(data)>512*1024*1024:raise Limit('Host retained-storage quota reached.')
                count=self.db.execute('SELECT count(*) FROM versions WHERE gid=?',(gid,)).fetchone()[0]
                if used+len(data)>MAX_STORAGE or count>=4096:raise Limit('Retained history quota reached.')
                if not old and self.db.execute('SELECT count(*) FROM files WHERE gid=?',(gid,)).fetchone()[0]>=MAX_FILES:raise Limit('File count quota reached.')
                fd=os.open(version+'.blob',os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=self.objects)
                written=True
                with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
                digest=hashlib.sha256(data).hexdigest()
                self.db.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?,0)',(version,gid,path,digest,len(data),actor.uid,actor.login))
                self.db.execute('INSERT OR REPLACE INTO files VALUES(?,?,?,0)',(gid,path,version))
                self._event(gid,actor,'write',path=path,version=version,previous=expected,digest=digest,size=len(data))
            return dict(version=version,digest=digest,size=len(data))
        except Exception:
            if written:os.unlink(version+'.blob',dir_fd=self.objects)
            raise

    def delete(self,actor,gid,path,expected):
        with self.transaction():
            self._group(actor,gid);path=self._write_allowed(actor,gid,path)
            old=self.db.execute('SELECT * FROM files WHERE gid=? AND path=?',(gid,path)).fetchone()
            if not old or old['deleted'] or old['version']!=expected:raise Conflict('Delete requires the current file version.')
            version=secrets.token_hex(16)
            self.db.execute('INSERT INTO versions VALUES(?,?,?,?,?,?,?,1)',(version,gid,path,'',0,actor.uid,actor.login))
            self.db.execute('UPDATE files SET version=?,deleted=1 WHERE gid=? AND path=?',(version,gid,path))
            self._event(gid,actor,'delete',path=path,version=version,previous=expected)
            return dict(version=version,deleted=True)

    def read(self,actor,gid,version):
        with self.lock:
            self._group(actor,gid)
            if not isinstance(version,str) or not re.fullmatch(r'[a-f0-9]{32}',version):raise Denied('Unknown version.')
            row=self.db.execute('SELECT * FROM versions WHERE gid=? AND version=? AND deleted=0',(gid,version)).fetchone()
            if not row:raise Denied('Unknown file version.')
            fd=os.open(version+'.blob',os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=self.objects)
            with os.fdopen(fd,'rb') as source:
                info=os.fstat(source.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size!=row['size']:raise Denied('Stored object is invalid.')
                data=source.read(MAX_FILE+1)
            if hashlib.sha256(data).hexdigest()!=row['digest']:raise Denied('Stored file integrity check failed.')
            return dict(row),data

    def history(self,actor,gid,after=0):
        if type(after) is not int or after<0:raise Denied('Invalid audit cursor.')
        with self.lock:
            self._group(actor,gid)
            return [dict(seq=r['seq'],event=json.loads(r['payload']),previous=r['previous'],hash=r['hash']) for r in self.db.execute('SELECT * FROM audit WHERE gid=? AND seq>? ORDER BY seq LIMIT 200',(gid,after))]

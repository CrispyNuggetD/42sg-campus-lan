"""Opt-in KoelDrop worker. Only a deliberately joined, empty folder is polled."""
import queue
import re
import threading
import time
from pathlib import Path
from .controller import SyncSession
from .remote import RemoteStore
from .security import Denied
from .sync import Mirror,ReceivePolicy
from .workflow import default_folder


class Courier:
    def __init__(self,token,uid,login,inbox,remote=None,interval=5):
        if type(uid) is not int or uid<=0:raise Denied('A verified sign-in is required.')
        self.uid=uid;self.login=login;self.inbox=inbox;self.interval=interval
        self.stopped=threading.Event();self.jobs=queue.Queue(maxsize=32)
        self.remote=remote or RemoteStore(token)
        self.remote.cancelled=lambda:self.stopped.is_set()
        self.sync=None;self.folder=None;self.thread=None
        self.flock_epoch=None;self.join_pending=None

    def submit(self,operation,*args):
        if self.stopped.is_set():raise Denied('KoelDrop stopped; run the command again.')
        joining=operation in ('create','accept','flock')
        if joining and (self.sync or self.join_pending):raise Denied('A group is active or joining; leave it or wait first.')
        if joining:self.join_pending=operation
        try:self.jobs.put_nowait((operation,args))
        except queue.Full:
            if joining:self.join_pending=None
            raise Denied('KoelDrop is busy; wait for pending operations.') from None
        if self.thread is None:
            self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def emit(self,**values):
        try:self.inbox.put_nowait(dict(type='local_koel',courier=id(self),**values))
        except queue.Full:pass  # /koel pending always lists outstanding offers again.

    def stop(self):
        self.stopped.set()
        try:self.jobs.put_nowait(('stop',()))
        except queue.Full:pass

    def _join(self,gid,host,invite=None,flock_epoch=None):
        if self.sync:raise Denied('Leave the current KoelDrop group before joining another.')
        mirror=Mirror(self.folder or default_folder(host,gid),self.uid,self.login)
        try:
            if flock_epoch:self.remote.join_flock(gid,flock_epoch)
            elif invite:self.remote.accept(gid,invite)
            manifest=self.remote.manifest(None,gid)
            mirror.offers(manifest)
            mirror.initialize_info(manifest['welcome'],self.remote.history(None,gid)[:200])
            self.sync=SyncSession(self.remote,None,gid,mirror)
        except Exception:
            mirror.close()
            try:self.remote.leave(None,gid)
            except (ValueError,OSError):pass
            raise
        self.emit(lines=['KoelDrop joined. Folder: '+str(mirror.path),
                         'Files added to this dedicated folder upload to this group every '+str(self.interval)+' seconds. Incoming files need approval.',
                         'Root files are shared; '+self.login+'/ is yours. /koel pending | receive NUMBER | trust LOGIN | leave. Local deletions are not synced.'])

    def _step(self):
        if not self.sync:return
        before=set(self.sync.pending)
        result=self.sync.step(publish=True)
        lines=[]
        for path in result['uploaded']:lines.append('KoelDrop uploaded: '+path)
        for path in result['received']:lines.append('KoelDrop received: '+path)
        for path in result['conflicts']:lines.append('KoelDrop conflict; review the local file: '+path)
        pending=list(self.sync.pending.values())
        # Stable file IDs are the immutable server versions, never arbitrary paths or URLs.
        self.emit(lines=lines,offers=[dict(version=o.version,path=o.path,author=o.author,deleted=o.deleted,size=o.size) for o in pending],
                  notices=[dict(version=o.version,path=o.path,author=o.author,deleted=o.deleted,size=o.size) for o in pending
                           if o.version not in before])

    def perform(self,operation,args):
        if operation=='create':
            if self.sync:raise Denied('Leave the current group first.')
            self._join(self.remote.create(),self.login)
        elif operation=='flock':
            if self.sync:raise Denied('Leave the current group first; no group is replaced automatically.')
            gid,host,epoch,base,fingerprint=args
            self.flock_epoch=epoch
            from .flock import fresh_folder
            self.folder=fresh_folder(base,fingerprint,epoch)
            self._join(gid,host,flock_epoch=epoch)
            self.flock_epoch=epoch
            self.emit(flock_joined=True,lines=['Joined the 42 Singapore flock. This folder is kept on leave/shutdown. No automatic local cleanup or deletion.'])
        elif operation=='accept':self._join(*args)
        elif operation=='dir':
            path=Path(args[0]).expanduser().absolute()
            if self.sync:self.sync.relocate(path)
            self.folder=path;self.emit(lines=['KoelDrop folder: '+str(path)+'. Previous copies stay where they were.'])
        elif operation=='status':
            self.emit(lines=['KoelDrop '+('group '+self.sync.group+' | '+str(self.sync.mirror.path) if self.sync else 'not joined. /koel create or accept NUMBER.')])
        elif operation=='leave':
            if not self.sync:raise Denied('No KoelDrop group is joined.')
            self.remote.leave(None,self.sync.group);self.sync.mirror.close();self.sync=None;self.flock_epoch=None
            self.emit(lines=['Left KoelDrop; local copies were kept.'],offers=[])
        elif operation=='invite':
            if not self.sync:raise Denied('Create a group before inviting someone.')
            for name in args[0]:
                invitation=self.remote.invite(None,self.sync.group,name)
                self.emit(deliver=dict(type='koel_deliver',group=self.sync.group,invite=invitation['invite']))
        elif operation in ('receive','decline'):
            if not self.sync:raise Denied('No KoelDrop group is joined.')
            offer=self.sync.pending.get(args[0])
            if not offer:raise Denied('This offer changed. Use /koel pending.')
            if operation=='receive':
                self.sync.accept(args[0]);self.emit(lines=['KoelDrop '+('deleted with backup: ' if offer.deleted else 'received: ')+offer.path])
            else:self.sync.decline(args[0]);self.emit(lines=['Declined: '+offer.path])
        elif operation=='trust':
            if not self.sync:raise Denied('Join a group before setting its receive policy.')
            self.sync.mirror.policy=ReceivePolicy(friend_names=frozenset(args[0]))
            self.emit(lines=['KoelDrop automatically receives files from: '+(', '.join(args[0]) or 'nobody')+'. Deletions still require approval.'])
        elif operation!='sync':raise Denied('Unknown KoelDrop operation.')
        self._step()

    def run(self):
        next_poll=0;failed=False
        try:
            while not self.stopped.is_set():
                try:operation,args=self.jobs.get(timeout=max(.05,min(.5,next_poll-time.monotonic())))
                except queue.Empty:
                    if not self.sync or time.monotonic()<next_poll:continue
                    operation,args='sync',()
                if operation=='stop':break
                try:
                    self.perform(operation,args);failed=False
                except (OSError,ValueError,KeyError,TypeError):
                    if not failed or operation!='sync':
                        self.emit(lines=['KoelDrop could not complete '+operation+'. Sharing is paused; local copies are kept. Check sign-in/campus seat, membership, folder permissions and quotas; /koel pending'])
                    failed=True
                finally:
                    if operation in ('create','accept','flock'):self.join_pending=None
                next_poll=time.monotonic()+self.interval
        finally:
            self.stopped.set()
            if self.sync:self.sync.mirror.close();self.sync=None

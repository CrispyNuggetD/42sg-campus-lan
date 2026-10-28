"""One explicit sync pass, not a daemon. No sockets or background tasks start here."""
from .security import Denied,Conflict,Limit
from .workflow import file_notice


class SyncSession:
    def __init__(self,store,identity,group,mirror):
        self.store=store;self.identity=identity;self.group=group;self.mirror=mirror
        self.pending={};self.declined=set()

    def _fetch(self,version):return self.store.read(self.identity,self.group,version)[1]

    def step(self,publish=False,publish_deletes=False,sound_enabled=False):
        manifest=self.store.manifest(self.identity,self.group)
        self.mirror.offers(manifest)  # Validate and install namespace metadata before scanning.
        conflicts=[];uploaded=[];received=[];limited=[]
        if publish:
            local=self.mirror.scan_writable()
            for path,digest in local.items():
                if self.mirror.known.get(path,{}).get('digest')==digest:continue
                try:
                    receipt=self.mirror.upload(path,lambda p,d,v:self.store.put(self.identity,self.group,p,d,v),approved=True)
                    uploaded.append(receipt.get('path',path))
                except Limit:limited.append(path)
                except (Conflict,Denied):conflicts.append(path)
            if publish_deletes and not manifest.get('append_only'):
                for path,known in list(self.mirror.known.items()):
                    first=path.split('/')[0]
                    if path in local or known.get('digest') is None or first in self.mirror.members-{self.mirror.login}:continue
                    try:
                        result=self.store.delete(self.identity,self.group,path,known['version'])
                        self.mirror.known[path]=dict(version=result['version'],digest=None)
                        uploaded.append(path)
                    except (Conflict,Denied,Limit):conflicts.append(path)
        offers=self.mirror.offers(self.store.manifest(self.identity,self.group))
        current={offer.version for offer in offers}
        self.pending={key:value for key,value in self.pending.items() if key in current}
        notices=[]
        for offer in offers:
            if offer.version in self.declined:continue
            if self.mirror.policy.allows(offer):
                try:self.mirror.receive(offer,self._fetch);received.append(offer.path);continue
                except Conflict:conflicts.append(offer.path)
            if offer.version not in self.pending:
                self.pending[offer.version]=offer
                notices.append(file_notice(offer,self.mirror.path/offer.path,sound_enabled))
        return dict(uploaded=uploaded,received=received,conflicts=conflicts,notices=notices,limited=limited)

    def accept(self,version):
        offer=self.pending.get(version)
        if not offer:raise Denied('No pending offer with that version.')
        heads=self.store.manifest(self.identity,self.group)['files']
        if not any(row['path']==offer.path and row['version']==version for row in heads):raise Conflict('Offer changed; rescan before accepting.')
        result=self.mirror.receive(offer,self._fetch,approved=True)
        self.pending.pop(version,None);return result

    def keep_both(self,version):
        """Explicit resolution: preserve/publish local bytes, then receive shared head."""
        import hashlib
        import os
        import secrets
        from pathlib import PurePosixPath
        offer=self.pending.get(version)
        if not offer or offer.deleted:raise Denied('Choose a current incoming file conflict.')
        heads=self.store.manifest(self.identity,self.group)['files']
        if not any(row['path']==offer.path and row['version']==version for row in heads):
            raise Conflict('Shared file changed; refresh before resolving.')
        data=self.mirror._read(offer.path)
        if data is None:raise Conflict('Local file is missing; receive the shared file instead.')
        filename=PurePosixPath(offer.path).name
        suffix=PurePosixPath(filename).suffix
        stem=filename[:-len(suffix)] if suffix else filename
        # A short unique suffix avoids collisions without replacing either copy.
        path=self.mirror.login+'/'+stem[:48]+'_'+self.mirror.login+'_'+secrets.token_hex(6)+suffix[:16]
        parent,name=self.mirror._parent(path,True)
        try:
            fd=os.open(name,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=parent)
            with os.fdopen(fd,'wb') as output:output.write(data);output.flush();os.fsync(output.fileno())
        finally:os.close(parent)
        # If upload fails, the original remains intact and the local copy is kept.
        receipt=self.mirror.upload(path,lambda p,d,v:self.store.put(self.identity,self.group,p,d,v),approved=True)
        path=receipt.get('path',path)
        baseline=hashlib.sha256(data).hexdigest()
        parent,name=self.mirror._parent(offer.path)
        try:self.mirror._backup(parent,name,baseline)
        finally:os.close(parent)
        self.mirror.known[offer.path]=dict(version=None,digest=None)
        # accept rechecks the server head and receive checks local concurrent edits.
        self.accept(version)
        return path

    def decline(self,version):
        if version not in self.pending:raise Denied('No pending offer with that version.')
        self.pending.pop(version);self.declined.add(version)

    def relocate(self,path):
        self.mirror=self.mirror.relocate(path);self.pending={};self.declined=set()

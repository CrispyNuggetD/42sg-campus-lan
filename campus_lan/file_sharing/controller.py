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
        conflicts=[];uploaded=[];received=[]
        if publish:
            local=self.mirror.scan_writable()
            for path,digest in local.items():
                if self.mirror.known.get(path,{}).get('digest')==digest:continue
                try:
                    self.mirror.upload(path,lambda p,d,v:self.store.put(self.identity,self.group,p,d,v),approved=True)
                    uploaded.append(path)
                except (Conflict,Denied,Limit):conflicts.append(path)
            if publish_deletes:
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
        return dict(uploaded=uploaded,received=received,conflicts=conflicts,notices=notices)

    def accept(self,version):
        offer=self.pending.get(version)
        if not offer:raise Denied('No pending offer with that version.')
        heads=self.store.manifest(self.identity,self.group)['files']
        if not any(row['path']==offer.path and row['version']==version for row in heads):raise Conflict('Offer changed; rescan before accepting.')
        result=self.mirror.receive(offer,self._fetch,approved=True)
        self.pending.pop(version,None);return result

    def decline(self,version):
        if version not in self.pending:raise Denied('No pending offer with that version.')
        self.pending.pop(version);self.declined.add(version)

    def relocate(self,path):
        self.mirror=self.mirror.relocate(path);self.pending={};self.declined=set()

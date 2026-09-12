"""Small full mesh: direct snapshots every 5s, bounded peer/event exchange."""
import asyncio
import ipaddress
import json
import time
import uuid
from . import VERSION, PROTOCOL
from .network import seat_label

INTERVAL = 5
EXPIRE = 16
MAX_PEERS = 16

def endpoint(host, port):
    ip = ipaddress.ip_address(host)
    if not (ip.is_private or ip.is_loopback) or ip.is_multicast or ip.is_unspecified:
        raise ValueError('Peers must use a LAN IP address.')
    if type(port) is not int or not 1 <= port <= 65535:
        raise ValueError('Invalid peer port.')
    return str(ip), port

def text(value,limit=400):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]

class Mesh:
    def __init__(self,lobby):
        self.lobby = lobby
        self.host = '127.0.0.1'
        self.peers = {}
        self.events = {}
        self.running = True
        self.lock = asyncio.Lock()

    def local_players(self):
        return [dict(id='local:'+key,name=p['name'],hostname=p['hostname'],
                     verified=False,seat=seat_label(self.host,p['hostname']))
                for key,p in self.lobby.owners.items()]

    def local_rooms(self):
        return [dict(id=rid,name=r['game'],host=self.lobby.clients[r['host']]['name'],
                     members=len(r['members']),address=self.host,port=self.lobby.port)
                for rid,r in self.lobby.rooms.items() if r['host'] in self.lobby.clients]

    def snapshot(self):
        now = time.monotonic()
        self.events = {key:e for key,e in self.events.items() if now-e['received']<45}
        return dict(type='mesh',protocol=PROTOCOL,version=VERSION,port=self.lobby.port,
                    players=self.local_players(),rooms=self.local_rooms(),
                    peers=[dict(host=h,port=p) for (h,p),v in self.peers.items() if v['seen'] and now-v['seen']<EXPIRE],
                    events=[dict(id=k,kind=e['kind'],text=e['text'],created=e['created']) for k,e in list(self.events.items())[-32:]])

    async def publish(self,kind,message):
        key = uuid.uuid4().hex
        self.events[key] = dict(kind=kind,text=text(message),received=time.monotonic(),created=time.time())
        await self.lobby.broadcast(dict(type=kind,text=text(message)))

    async def merge(self,host,data):
        if not isinstance(data,dict) or data.get('type')!='mesh' or data.get('protocol')!=PROTOCOL:
            raise ValueError('Peer needs the same protocol version.')
        key = endpoint(host,data.get('port'))
        if key == (self.host,self.lobby.port):
            return
        if key not in self.peers and len(self.peers)>=MAX_PEERS:
            raise ValueError('Peer limit reached.')
        old = self.peers.get(key,{})
        old_names = {p['name'] for p in old.get('players',[])}
        players = []
        for p in data.get('players',[])[:32]:
            if isinstance(p,dict):
                name = text(p.get('name','guest'),24)
                hostname = text(p.get('hostname','unknown'),50)
                players.append(dict(id=f'{host}:{key[1]}:{name}',name=name,hostname=hostname,
                                    verified=False,seat=seat_label(host,hostname)))
        rooms = []
        for r in data.get('rooms',[])[:10]:
            if isinstance(r,dict):
                rooms.append(dict(id=text(r.get('id',''),12),name=text(r.get('name',''),20),
                                  host=text(r.get('host',''),24),members=text(r.get('members',0),3),
                                  address=host,port=key[1]))
        self.peers[key] = dict(seen=time.monotonic(),players=players,rooms=rooms,failures=0)
        for player in players:
            if player['name'] not in old_names:
                await self.lobby.broadcast(dict(type='online',text=
                    f"{player['name']} came online! {player['seat']}. Go say hi! [Guest]"))
        for name in old_names-{p['name'] for p in players}:
            await self.lobby.event(f'{name} went offline.')
        for p in data.get('peers',[])[:MAX_PEERS]:
            try:
                discovered = endpoint(p['host'],p['port'])
            except (ValueError,KeyError,TypeError):
                continue
            if discovered != (self.host,self.lobby.port) and len(self.peers)<MAX_PEERS:
                self.peers.setdefault(discovered,dict(seen=0,players=[],rooms=[],failures=0))
        # IDs prevent loops. Retain seen IDs longer than forwarding lifetime.
        for event in data.get('events',[])[:32]:
            if not isinstance(event,dict):
                continue
            eid = text(event.get('id',''),40)
            kind = event.get('kind')
            created = event.get('created')
            if not isinstance(created,(int,float)) or not 0<=time.time()-created<45:
                continue
            if len(eid)!=32 or kind not in ('event','invite') or eid in self.events:
                continue
            self.events[eid] = dict(kind=kind,text=text(event.get('text','')),received=time.monotonic(),created=created)
            await self.lobby.broadcast(dict(type=kind,text=self.events[eid]['text']))
        # Never let incoming gossip grow an unbounded event cache.
        while len(self.events)>128:
            self.events.pop(next(iter(self.events)))

    async def contact(self,host,port):
        host,port = endpoint(host,port)
        reader,writer = await asyncio.wait_for(asyncio.open_connection(host,port,limit=131072),2)
        try:
            self.host = writer.get_extra_info('sockname')[0]
            writer.write((json.dumps(self.snapshot())+'\n').encode())
            await asyncio.wait_for(writer.drain(),2)
            raw = await asyncio.wait_for(reader.readline(),2)
            if len(raw)>65536:
                raise ValueError('Peer snapshot too large.')
            await self.merge(host,json.loads(raw))
        finally:
            writer.close()
            await writer.wait_closed()

    async def connect(self,host,port):
        async with self.lock:
            await self.contact(host,port)
        await self.lobby.state()

    async def poll(self,key):
        try:
            await self.contact(*key)
        except (OSError,ValueError,TypeError,asyncio.TimeoutError):
            if key in self.peers:
                self.peers[key]['failures'] += 1

    async def loop(self):
        while self.running:
            started = time.monotonic()
            async with self.lock:
                await asyncio.gather(*(self.poll(key) for key in list(self.peers)))
                now = time.monotonic()
                for key,peer in list(self.peers.items()):
                    if peer['seen'] and now-peer['seen']>EXPIRE:
                        for p in peer['players']:
                            await self.lobby.event(f"{p['name']} went offline.")
                        peer['players'],peer['rooms'],peer['seen'] = [],[],0
                    if not peer['seen'] and peer['failures']>=4:
                        del self.peers[key]
                await self.lobby.state()
            await asyncio.sleep(max(.1,INTERVAL-(time.monotonic()-started)))

    def players(self):
        return self.local_players()+[p for peer in self.peers.values() for p in peer['players']]

    def rooms(self):
        return self.local_rooms()+[r for peer in self.peers.values() for r in peer['rooms']]

    async def goodbye(self):
        self.lobby.owners.clear()
        await asyncio.gather(*(self.poll(key) for key in list(self.peers)))

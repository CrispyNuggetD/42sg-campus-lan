"""Newline-delimited JSON; the lobby host also coordinates lightweight game rooms."""
import asyncio
import json
import re
import time
from . import VERSION, PROTOCOL
from .games import Tetris, Bluff
from .network import seat_address
from .mesh import Mesh
import ipaddress

def clean(value, limit=400):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]

class Lobby:
    def __init__(self, round_seconds=45):
        self.clients, self.rooms = {}, {}
        self.sequence = self.room_sequence = 0
        self.round_seconds = round_seconds
        self.seats = {}
        self.api_status = 'API disabled; seats unknown'
        self.port = 31415
        self.peer_invites = {}
        self.owners = {}
        self.shutdown = asyncio.Event()
        self.owner_started = asyncio.Event()
        self.mesh = Mesh(self)

    async def send(self, client, data):
        if client['writer'].is_closing():
            return
        try:
            client['writer'].write((json.dumps(data)+'\n').encode())
            await asyncio.wait_for(client['writer'].drain(), 2)
        except (ConnectionError, asyncio.TimeoutError, OSError):
            client['writer'].close()

    async def broadcast(self, data, ids=None):
        clients = [c for p,c in list(self.clients.items()) if ids is None or p in ids]
        await asyncio.gather(*(self.send(c,data) for c in clients))

    async def event(self, text, ids=None):
        await self.broadcast(dict(type='event',text=text), ids)

    async def state(self):
        await self.broadcast(dict(type='state',version=VERSION,api=self.api_status,
            nodes=len(self.mesh.peers)+1,
            players=self.mesh.players() or [dict(id=p,name=c['name'],hostname=c['hostname'],verified=False,
                          seat=self.seats.get(c['name'],'unknown')) for p,c in self.clients.items()],
            rooms=self.mesh.rooms()))

    async def room_state(self, rid):
        if rid not in self.rooms:
            return
        room = self.rooms[rid]
        data = dict(type='game',room=rid,game=room['game'],host=room['host'],
                    members=[self.clients[p]['name'] for p in room['members'] if p in self.clients])
        if room['engine']:
            data.update(room['engine'].view())
        else:
            data['phase'] = 'waiting'
        await self.broadcast(data,room['members'])

    def room_for(self, pid):
        return next(((r,x) for r,x in self.rooms.items() if pid in x['members']), (None,None))

    async def leave(self, pid):
        rid,room = self.room_for(pid)
        if room:
            room['members'].remove(pid)
            if not room['members']:
                del self.rooms[rid]
            else:
                if room['host']==pid:
                    room['host'] = min(room['members'])
                await self.event('A player left; host transfers if needed. Timed rounds continue.',room['members'])
                await self.room_state(rid)
        if pid in self.clients:
            await self.send(self.clients[pid],dict(type='game',game=None))

    async def command(self, pid, raw):
        c = self.clients[pid]
        text = clean(raw)
        if not text:
            return
        if not text.startswith('/'):
            await self.mesh.publish('event',f"{c['name']} [Guest]: {text}")
            return
        cmd,_,arg = text.partition(' ')
        arg = arg.strip()
        rid, room = self.room_for(pid)
        if not room and cmd in ('/invite','/invite-room','/invite-seat'):
            for other,peer in self.clients.items():
                if peer['name']==c['name'] and peer.get('role')=='game':
                    candidate,active = self.room_for(other)
                    if active:
                        pid,rid,room = other,candidate,active
                        break
        if cmd == '/games':
            await self.send(c,dict(type='event',text='Games: tetris (shared-board co-op), bluff (free or prompt). /host tetris | /host bluff prompt | /join ROOM'))
        elif cmd == '/signin':
            await self.send(c,dict(type='event',text='Sign in with Intra — coming later. You are a Guest (unverified).'))
        elif cmd == '/host':
            bits = arg.split()
            if not bits or bits[0] not in ('tetris','bluff'):
                raise ValueError('Use /host tetris or /host bluff [free|prompt].')
            if len(self.rooms)>=10:
                raise ValueError('Room limit reached.')
            mode = bits[1] if len(bits)>1 else 'free'
            if bits[0]=='bluff' and mode not in ('free','prompt'):
                raise ValueError('Bluff mode: free or prompt.')
            if time.monotonic()-c.get('invite',-100)<10:
                raise ValueError('Wait 10 seconds between hosting/invitations.')
            await self.leave(pid)
            self.room_sequence += 1
            rid = str(self.room_sequence)
            self.rooms[rid] = dict(game=bits[0],mode=mode,host=pid,members={pid},engine=None,last=0)
            await self.event(f"{c['name']} opened {bits[0]} room {rid}; /join {rid}")
            await self.room_state(rid)
            await self.invite(pid,rid)
            await self.state()
        elif cmd == '/join':
            if arg == rid:
                return
            if arg not in self.rooms:
                raise ValueError('Unknown room; see /rooms.')
            target = self.rooms[arg]
            if target['game']=='bluff' and target['engine'] and target['engine'].phase!='results':
                raise ValueError('Round running. Join after the reveal.')
            await self.leave(pid)
            if arg not in self.rooms:
                raise ValueError('Room closed; try another.')
            target['members'].add(pid)
            await self.room_state(arg)
            await self.state()
        elif cmd == '/leave':
            await self.leave(pid)
            await self.state()
        elif cmd == '/invite-seat':
            if not room:
                raise ValueError('Host or join a game room first.')
            bits = arg.split()
            if len(bits) not in (1,2):
                raise ValueError('Use /invite-seat c1r2s3 [port].')
            target = seat_address(bits[0])
            port = int(bits[1]) if len(bits)==2 else self.port
            if not 1<=port<=65535:
                raise ValueError('Invalid port.')
            if time.monotonic()-c.get('peer_invite',-100)<10:
                raise ValueError('Wait 10 seconds between seat invitations.')
            c['peer_invite'] = time.monotonic()
            try:
                reader,writer = await asyncio.wait_for(asyncio.open_connection(target,port),3)
                try:
                    writer.write((json.dumps(dict(type='peer_invite',protocol=PROTOCOL,
                        name=c['name'],game=room['game'],room=rid,port=self.port))+'\n').encode())
                    await writer.drain()
                    reply = json.loads(await asyncio.wait_for(reader.readline(),3))
                    if reply.get('type')!='invite_ack':
                        raise ValueError('Friend server did not accept the invitation; update it.')
                    await self.send(c,dict(type='event',text=f"Invitation delivered to {bits[0]} ({target}); {reply['clients']} connected clients."))
                finally:
                    writer.close()
                    await writer.wait_closed()
            except (OSError,asyncio.TimeoutError):
                raise ValueError(f'Cannot reach {target}:{port}. Friend must run lan42 first; check seat and network.')
        elif cmd in ('/invite','/invite-room'):
            if not room:
                raise ValueError('Host or join a room first.')
            await self.invite(pid,rid)
        elif cmd == '/start':
            if not room or room['host']!=pid:
                raise ValueError('Only this room host can start a game.')
            if room['engine'] and ((room['game']=='tetris' and not room['engine'].over) or
                                   (room['game']=='bluff' and room['engine'].phase!='results')):
                raise ValueError('Game already running.')
            if room['game']=='tetris':
                room['engine'] = Tetris()
            else:
                if len(room['members'])<2:
                    raise ValueError('Bluff needs at least 2 players.')
                if len(room['members'])==2:
                    await self.event('Bluff works with two, but is best with 3+ players: with two, the other author is easy to deduce.',room['members'])
                names = {p:self.clients[p]['name'] for p in sorted(room['members'])}
                turn = room.get('turn',0)
                leader = list(names)[turn%len(names)]
                room['turn'] = turn+1
                room['engine'] = Bluff(names,leader,room['mode'],time.time(),self.round_seconds)
            room['last'] = time.monotonic()
            await self.room_state(rid)
        elif cmd in ('/answer','/vote'):
            if not room or room['game']!='bluff' or not room['engine']:
                raise ValueError('Start a bluff round first.')
            if cmd=='/answer':
                room['engine'].answer(pid,arg,time.time())
                await self.send(c,dict(type='event',text='Answer saved privately.'))
            else:
                room['engine'].vote(pid,arg.split(),time.time())
                await self.send(c,dict(type='event',text='Vote saved.'))
            room['engine'].tick(time.time())
            await self.room_state(rid)
        elif cmd in ('/who','/rooms'):
            await self.state()
        else:
            raise ValueError('Unknown command. /help lists commands locally.')

    async def invite(self,pid,rid):
        now = time.monotonic()
        c = self.clients[pid]
        if now-c.get('invite',-100)<10:
            raise ValueError('Wait 10 seconds between invitations.')
        c['invite'] = now
        await self.mesh.publish('invite',f"{c['name']} invites you to {self.rooms[rid]['game']}; server {self.mesh.host}:{self.port}, /join {rid}. Use /connect {self.mesh.host} {self.port} if on another node.")

    async def handle(self,reader,writer):
        pid = None
        owner_key = None
        try:
            line = await asyncio.wait_for(reader.readline(),10)
            if len(line)>65536:
                raise ValueError('Handshake too large.')
            hello = json.loads(line)
            source = writer.get_extra_info('peername')[0]
            if isinstance(hello,dict) and hello.get('protocol')==PROTOCOL:
                if hello.get('type')=='mesh':
                    self.mesh.host = writer.get_extra_info('sockname')[0]
                    await self.mesh.merge(source,hello)
                    await self.send(dict(writer=writer),self.mesh.snapshot())
                    await self.state()
                    return
                if hello.get('type') in ('owner','connect_peer'):
                    if not ipaddress.ip_address(source).is_loopback:
                        raise ValueError('Local control only.')
                    if hello['type']=='connect_peer':
                        await self.mesh.connect(hello.get('host'),hello.get('port'))
                        await self.send(dict(writer=writer),dict(type='peer_connected'))
                        return
                    owner_key = str(id(writer))
                    self.owners[owner_key] = dict(name=clean(hello.get('name','guest'),24),
                                                  hostname=clean(hello.get('hostname','unknown'),50))
                    self.owner_started.set()
                    await self.send(dict(writer=writer),dict(type='owner_ready'))
                    await self.state()
                    while await asyncio.wait_for(reader.readline(),16):
                        pass
                    return
            if isinstance(hello,dict) and hello.get('protocol')==PROTOCOL:
                if hello.get('type')=='ping':
                    await self.send(dict(writer=writer),dict(type='pong',protocol=PROTOCOL,version=VERSION))
                    return
                if hello.get('type')=='peer_invite':
                    source = writer.get_extra_info('peername')[0]
                    port = hello.get('port',31415)
                    if not isinstance(port,int) or not 1<=port<=65535:
                        raise ValueError('Invalid invitation port.')
                    now = time.monotonic()
                    self.peer_invites = {ip:t for ip,t in self.peer_invites.items() if now-t<10}
                    if source in self.peer_invites:
                        raise ValueError('Invitation cooldown.')
                    self.peer_invites[source] = now
                    name,game,room = (clean(hello.get(k,''),32) for k in ('name','game','room'))
                    await self.broadcast(dict(type='invite',text=
                        f'{name} [Guest] invites you to {game} at {source}:{port}. Use /connect {source} {port}, then /join {room}.'))
                    await self.send(dict(writer=writer),dict(type='invite_ack',clients=len(self.clients)))
                    return
            if not isinstance(hello,dict) or hello.get('type')!='hello' or hello.get('protocol')!=PROTOCOL:
                raise ValueError('Protocol mismatch; update your client.')
            name = clean(hello.get('name','guest'),24)
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,24}',name):
                raise ValueError('Invalid guest username.')
            role = hello.get('role','lobby')
            if role not in ('lobby','game'):
                raise ValueError('Unknown client role.')
            if len(self.clients)>=32 or any(c['name']==name and c.get('role','lobby')==role for c in self.clients.values()):
                raise ValueError('Lobby full or this guest name is already connected.')
            self.sequence += 1
            pid = str(self.sequence)
            c = dict(writer=writer,name=name,role=role,hostname=clean(hello.get('hostname','unknown'),50),
                     window=time.monotonic(),count=0)
            self.clients[pid] = c
            await self.send(c,dict(type='welcome',id=pid,version=VERSION,verified=False))
            if role=='lobby':
                await self.event(f'{name} joined as Guest.')
            await self.state()
            while True:
                line = await reader.readline()
                if not line:
                    break
                if len(line)>8192:
                    raise ValueError('Message too large.')
                msg = json.loads(line)
                if not isinstance(msg,dict):
                    raise ValueError('Expected an object.')
                now = time.monotonic()
                if now-c['window']>=1:
                    c['window'],c['count'] = now,0
                c['count'] += 1
                if c['count']>30:
                    continue
                try:
                    if msg.get('type')=='command':
                        await self.command(pid,msg.get('text',''))
                    elif msg.get('type')=='move':
                        rid,room = self.room_for(pid)
                        if room and room['game']=='tetris' and room['engine']:
                            room['engine'].move(msg.get('action'))
                            await self.room_state(rid)
                except ValueError as e:
                    await self.send(c,dict(type='event',text=str(e)))
        except (ValueError,TypeError,ConnectionError,asyncio.TimeoutError,OSError) as e:
            await self.send(dict(writer=writer),dict(type='error',text=clean(e)))
        finally:
            if owner_key is not None:
                self.owners.pop(owner_key,None)
                if not self.owners:
                    self.shutdown.set()
            if pid is not None:
                name = self.clients[pid]['name']
                role = self.clients[pid].get('role','lobby')
                await self.leave(pid)
                del self.clients[pid]
                await self.state()
                if role=='lobby':
                    await self.event(f'{name} disconnected.')
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass

    async def tick(self):
        while True:
            await asyncio.sleep(.2)
            for rid,room in list(self.rooms.items()):
                engine = room['engine']
                if not engine:
                    continue
                if room['game']=='tetris' and not engine.over and time.monotonic()-room['last']>=.65:
                    engine.move('down')
                    room['last'] = time.monotonic()
                    await self.room_state(rid)
                elif room['game']=='bluff':
                    old = engine.phase
                    engine.tick(time.time())
                    if old!=engine.phase:
                        await self.room_state(rid)

async def serve(host,port,ready=None,managed=False):
    lobby = Lobby()
    lobby.port = port
    server = await asyncio.start_server(lobby.handle,host,port,limit=131072)
    print(f'42SG LAN {VERSION} listening on {host}:{port} — guest mode',flush=True)
    ticker = asyncio.create_task(lobby.tick())
    mesh_task = asyncio.create_task(lobby.mesh.loop())
    from .presence import refresh
    presence = asyncio.create_task(refresh(lobby))
    if ready:
        ready.set()
    try:
        async with server:
            if managed:
                try:
                    await asyncio.wait_for(lobby.owner_started.wait(),30)
                except asyncio.TimeoutError:
                    return
            await lobby.shutdown.wait()
    finally:
        ticker.cancel()
        presence.cancel()
        mesh_task.cancel()
        await asyncio.gather(ticker,presence,mesh_task,return_exceptions=True)
        lobby.rooms.clear()
        await lobby.mesh.goodbye()
        for client in list(lobby.clients.values()):
            client['writer'].close()

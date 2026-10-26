"""Newline-delimited JSON; the lobby host also coordinates lightweight game rooms."""
import asyncio
import base64
import binascii
import contextlib
import shlex
import hashlib
import json
import re
import time
from . import VERSION, PROTOCOL
from .games import Tetris, Bluff
from .hexwars import HexWars, demo_action
from .hexbot import MAX_WASM, inspect_bot, run_bots
from .network import seat_address
from .mesh import Mesh
from .auth import CallbackRelay, AuthError
import ipaddress

def clean(value, limit=400):
    return ''.join(c for c in str(value) if c.isprintable())[:limit]

class Lobby:
    def __init__(self, round_seconds=45, auth_broker=None):
        self.clients, self.rooms = {}, {}
        self.auth_broker = auth_broker
        self.koeldrop=None
        self.callbacks = CallbackRelay()
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
        self.bot_slots = asyncio.Semaphore(2)
        self.hex_tasks = set()
        from .profile_lookup import ProfileLookup
        self.profile_lookup = ProfileLookup()

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

    async def deliver_direct(self,sender,target,message,verified=False):
        recipients={pid for pid,c in self.clients.items() if c['name'].lower()==target.lower()}
        if not recipients:return False
        await self.broadcast(dict(type='direct_message',sender=clean(sender,32),verified=verified,
                                  text=clean(message,400)),recipients)
        return True

    async def route_direct(self,client,target,message):
        delivered=await self.deliver_direct(client['name'],target,message,bool(self.auth_broker))
        if not delivered and not self.auth_broker:delivered=await self.mesh.direct(client['name'],target,message)
        return delivered

    def start_direct_batch(self,pid,message):
        client=self.clients[pid];targets=message.get('targets');body=message.get('text')
        if (not isinstance(targets,list) or not 1<=len(targets)<=100
                or any(not isinstance(n,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',n) for n in targets)
                or not isinstance(body,str) or not 1<=len(body)<=400 or not clean(body).strip()):
            raise ValueError('Use 1–100 valid recipients and a message of 1–400 characters.')
        if client.get('dm_task') and not client['dm_task'].done():raise ValueError('A message batch is already running; wait for its delivery summary.')
        client['dm_task']=asyncio.create_task(self.direct_batch(client,list(dict.fromkeys(n.lower() for n in targets)),clean(body)))

    async def direct_batch(self,client,targets,body):
        unavailable=[];delivered_count=0
        for index,target in enumerate(targets):
            await asyncio.sleep(max(0,2.05-(time.monotonic()-client.get('last_dm',-1000))))
            if self.auth_broker and not self.auth_broker.active(client['session_key']):
                unavailable.extend(targets[index:]);break
            client['last_dm']=time.monotonic()
            error=''
            try:delivered=await self.route_direct(client,target,body)
            except (OSError,ValueError,asyncio.TimeoutError) as failure:
                delivered=False;error=str(failure) if isinstance(failure,ValueError) else 'Recipient unavailable.'
            if delivered:delivered_count+=1
            else:unavailable.append(target)
            await self.send(client,dict(type='dm_delivery',target=target,delivered=delivered,error=error))
        await self.send(client,dict(type='dm_summary',delivered=delivered_count,failed=len(unavailable),unavailable=unavailable))

    async def state(self):
        if self.auth_broker:
            people = {}
            for c in self.clients.values():
                people[c['uid']] = dict(id=str(c['uid']), name=c['name'], hostname=c['hostname'],
                    verified=True, seat=c.get('seat', 'unknown'))
            players = list(people.values())
        else:
            players = self.mesh.players() or [dict(id=p,name=c['name'],hostname=c['hostname'],verified=False,
                          seat=self.seats.get(c['name'],'unknown')) for p,c in self.clients.items()]
        await self.broadcast(dict(type='state',version=VERSION,api=self.api_status,
            secure=bool(self.auth_broker), nodes=1 if self.auth_broker else len(self.mesh.peers)+1,
            players=players, rooms=self.mesh.local_rooms() if self.auth_broker else self.mesh.rooms()))

    async def room_state(self, rid, reopen=None):
        if rid not in self.rooms:
            return
        room = self.rooms[rid]
        data = dict(type='game',room=rid,game=room['game'],host=room['host'],
                    members=[self.clients[p]['name'] for p in room['members'] if p in self.clients])
        if room['game'] == 'forknite':
            data['forknite'] = await room['web'].control(dict(action='status'))
        if room['game'] == 'hexwars':
            data['bots'] = [dict(name=self.clients[p]['name'], ready=p in room.get('bots', {}))
                            for p in sorted(room['members']) if p in self.clients]
            data['practice'] = room.get('practice', False)
        if room['engine']:
            data.update(room['engine'].view())
        else:
            data['phase'] = 'waiting'
        await self.broadcast(data,room['members'])
        if room['game']=='forknite':
            members=[]
            for pid in sorted(room['members']):
                c=self.clients.get(pid)
                if not c:continue
                identity=self.auth_broker.sessions.get(c.get('session_key'),{}) if self.auth_broker else {}
                members.append(dict(id=pid,name=c['name'],verified=bool(self.auth_broker),avatar=identity.get('avatar')))
            try:
                result=await room['web'].control(dict(action='members',members=members))
                for entry in result['entries']:
                    c=self.clients.get(entry['id'])
                    if not c or (reopen is not None and entry['id'] != reopen):continue
                    host=c['writer'].get_extra_info('sockname')[0]
                    if ipaddress.ip_address(host).is_loopback:
                        import socket
                        host=socket.gethostbyname(socket.gethostname())
                    await self.send(c,dict(type='browser_game',room=rid,url='http://'+host+':'+str(room['web'].port),ticket=entry['ticket'],reopen=entry['id']==reopen))
            except (OSError,ValueError):
                await self.event('FORKNITE browser unavailable. Leave and recreate the room.',room['members'])

    def room_for(self, pid):
        return next(((r,x) for r,x in self.rooms.items() if pid in x['members']), (None,None))

    async def leave(self, pid):
        rid,room = self.room_for(pid)
        if room:
            room['members'].remove(pid)
            if room['game'] == 'hexwars':
                room.get('bots', {}).pop(pid, None)
                if room['engine'] and not room['engine'].over:
                    room['engine'].forfeit(pid)
            if not room['members']:
                if room.get('web'):await room['web'].close()
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
            await self.mesh.publish('event',f"{c['name']} [{'42 Verified' if self.auth_broker else 'Guest'}]: {text}")
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
        if cmd in ('/info','/info_campus'):
            from .campus_info import info_lines
            await self.event('\n'.join(info_lines(arg)),{pid})
        elif cmd == '/campus-presence':
            from .clusters import snapshot
            now=time.monotonic()
            if now-c.get('presence_check',-1000)<60 and c.get('presence_snapshot'):
                await self.send(c,c['presence_snapshot'])
                return
            c['presence_check']=now
            try:players,stamp=await asyncio.to_thread(snapshot)
            except (OSError,ValueError,KeyError):
                await self.send(c,dict(type='campus_presence',error='Campus tracking unavailable; retrying in five minutes.'))
                return
            c['presence_snapshot']=dict(type='campus_presence',players=players,updated_at=stamp)
            await self.send(c,c['presence_snapshot'])
        elif cmd in ('/dm','/alert'):
            target,separator,message=arg.partition(' ')
            if not separator or not message.strip() or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',target):raise ValueError('Use /dm LOGIN MESSAGE (or /alert LOGIN MESSAGE).')
            if message.lstrip().startswith(('\"',"'")):message=' '.join(shlex.split(message))
            if not message.strip():raise ValueError('A direct message cannot be empty.')
            if c.get('dm_task') and not c['dm_task'].done():raise ValueError('Wait for the current group message to finish.')
            if time.monotonic()-c.get('last_dm',-1000)<2:raise ValueError('Wait two seconds before sending another message.')
            c['last_dm']=time.monotonic()
            delivered=await self.route_direct(c,target,message)
            if not delivered:raise ValueError('That user is not reachable in this LAN42 lobby/mesh.')
            await self.send(c,dict(type='event',text='DM to '+target+': '+message))
        elif cmd == '/clusters':
            if arg not in ('','1','2'):raise ValueError('Use /clusters [1|2].')
            from .clusters import snapshot
            await self.event('Loading campus API seats (cached for 30 seconds); API calls may queue.',{pid})
            try:players,stamp=await asyncio.to_thread(snapshot)
            except (OSError,ValueError,KeyError):raise ValueError('Campus seats unavailable. Check the API host configuration; retry later.') from None
            await self.send(c,dict(type='clusters',players=players,updated_at=stamp,cluster=int(arg or '1')))
        elif cmd == '/browser':
            if not room or room['game'] != 'forknite':
                raise ValueError('Join a FORKNITE room first with /game forknite or /join ROOM.')
            await self.room_state(rid, reopen=pid)
        elif cmd == '/games':
            await self.send(c,dict(type='event',text='Games: tetris, bluff (free|prompt), hexwars (C bot arena), forknite (browser). /game NAME | /join ROOM'))
        elif cmd == '/signin':
            await self.send(c,dict(type='event',text='Use /signin in your local HQ client to open 42 in your browser.'))
        elif cmd == '/signout':
            if not self.auth_broker:
                raise ValueError('You are using the guest lobby.')
            key = c['session_key']
            self.auth_broker.logout(key)
            for peer in list(self.clients.values()):
                if peer.get('session_key') == key:
                    await self.send(peer, dict(type='signed_out'))
                    peer['writer'].close()
        elif cmd in ('/host','/game'):
            bits = arg.split()
            if not bits or bits[0] not in ('tetris','bluff','hexwars','forknite'):
                raise ValueError('Use /game tetris, /game bluff [free|prompt], or /game hexwars. FORKNITE launches locally with /game forknite.')
            if len(self.rooms)>=10:
                raise ValueError('Room limit reached.')
            mode = bits[1] if len(bits)>1 else 'free'
            if bits[0]=='bluff' and mode not in ('free','prompt'):
                raise ValueError('Bluff mode: free or prompt.')
            if time.monotonic()-c.get('invite',-100)<10:
                raise ValueError('Wait 10 seconds between hosting/invitations.')
            web=None
            if bits[0]=='forknite':
                from .forknite_room import ForkniteRoom
                web=await ForkniteRoom.create()
            await self.leave(pid)
            self.room_sequence += 1
            rid = str(self.room_sequence)
            self.rooms[rid] = dict(game=bits[0],mode=mode,host=pid,members={pid},engine=None,last=0,web=web)
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
            if target['game'] == 'hexwars':
                self.hex_joinable(target)
            await self.leave(pid)
            if arg not in self.rooms:
                raise ValueError('Room closed; try another.')
            if target['game'] == 'hexwars':
                # leave() yields to other joins and to the host's /start.
                self.hex_joinable(target)
            target['members'].add(pid)
            await self.room_state(arg)
            await self.state()
        elif cmd in ('/stop','/status','/timings','/storm','/meals','/preset') and room and room['game']=='forknite':
            from .forknite_controls import parse,summary
            if cmd!='/status' and room['host']!=pid:raise ValueError('Only this room host can change the game.')
            if cmd=='/status':result=await room['web'].control(dict(action='status'))
            elif cmd=='/stop':
                await room['web'].control(dict(action='stop'))
                result=await room['web'].control(dict(action='status'))
            else:result=await room['web'].control(parse(cmd,arg))
            await self.event(summary(result),room['members'])
            await self.broadcast(dict(type='forknite_status',status=result),room['members'])
        elif cmd == '/diners':
            if not room or room['game']!='forknite' or room['host']!=pid:
                raise ValueError('Only the FORKNITE room host can use /diners TOTAL.')
            if not arg.isdecimal():raise ValueError('Use /diners TOTAL, e.g. /diners 7.')
            result=await room['web'].control(dict(action='diners',count=int(arg)))
            await self.event('Table set for '+str(result['count'])+' diners; random seats assigned on /start.',room['members'])
        elif cmd == '/sabo':
            if not room or room['game']!='forknite' or room['host']!=pid:
                raise ValueError('Only the FORKNITE room host can use /sabo LOGIN...')
            if arg.lower()=='history':
                await self.event('SABO this room: '+', '.join(room.get('sabo_history',[])),{pid})
                return
            bits=arg.split()
            cohorts=[];counts=[];filters=[];random_selection=False
            for bit in bits:
                if bit.lower().startswith('cohort') and bit[6:].isdecimal():cohorts.append(int(bit[6:]))
                elif bit.lower()=='random':random_selection=True
                elif bit.isdecimal():counts.append(int(bit))
                elif any(op in bit for op in ('=','>','<')):filters.append(bit)
            if cohorts or random_selection or filters:
                if len(counts)>1 or any(not (x.lower() in ('random','where','and') or x in filters or x.isdecimal() or (x.lower().startswith('cohort') and x[6:].isdecimal())) for x in bits):
                    raise ValueError('Use /sabo [COUNT] random [cohort4 cohort5] or /sabo cohort4 cohort5.')
                from .campus_info import random_profiles,load,refresh
                if not load():
                    await self.event('Campus cache missing; fetching private campus directory. Please wait.',{pid})
                    await asyncio.to_thread(refresh)
                seated=await room['web'].control(dict(action='roster'))
                requested=counts[0] if counts else None
                available=50-len(seated['players'])
                if requested is not None and requested>available:raise ValueError('Not enough empty seats (50 maximum).')
                profiles=random_profiles(requested,[p['name'] for p in seated['players']],cohorts,filters)[:available]
                errors=[]
            else:
                if not 1<=len(bits)<=50 or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',bit) for bit in bits):
                    raise ValueError('Use /sabo LOGIN... (1–50), or /sabo [COUNT] random cohort4.')
                profiles=[];errors=[]
                for offset in range(0,len(bits),10):
                    await self.event('Loading profiles '+str(offset+1)+'–'+str(min(offset+10,len(bits)))+' of '+str(len(bits))+'; API requests may queue.',{pid})
                    batch,failed=await self.profile_lookup.lookup_many(bits[offset:offset+10])
                    profiles.extend(batch);errors.extend(failed)
            if profiles:
                if rid not in self.rooms or self.rooms[rid] is not room:
                    raise ValueError('Room closed while profiles were loading.')
                result = await room['web'].control(dict(action='sabo_profiles',profiles=profiles))
                room.setdefault('sabo_history',[]).extend(result.get('added',[]))
                from .auth import config_dir,private_read,private_write
                history_path=config_dir()/'sabo-history.json'
                try:history=json.loads(private_read(history_path))
                except (OSError,ValueError):history=[]
                history.append(dict(at=time.time(),room=rid,added=result.get('added',[])))
                private_write(history_path,json.dumps(history[-500:]))
                await self.event('SABO: '+', '.join(result.get('added',[])) if result.get('added') else 'No new sabo slots added (already present or room full).',room['members'])
            if errors:
                await self.event('Could not load: '+', '.join(errors)+'. Check logins, credentials or API rate limits.',{pid})
        elif cmd == '/leave':
            await self.leave(pid)
            await self.state()
        elif cmd == '/invite-seat':
            if self.auth_broker:
                raise ValueError('Verified invitations stay inside this TLS lobby. Use /invite-room.')
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
                                   (room['game']=='bluff' and room['engine'].phase!='results') or
                                   (room['game']=='hexwars' and not room['engine'].over)):
                raise ValueError('Game already running.')
            if room['game']=='forknite':
                await room['web'].control(dict(action='start'))
                await self.event('FORKNITE native simulation started; watch your browser.',room['members'])
                await self.broadcast(dict(type='forknite_status',status=await room['web'].control(dict(action='status'))),room['members'])
                return
            if room['game']=='tetris':
                room['engine'] = Tetris()
            elif room['game'] == 'hexwars':
                bots = room.get('bots', {})
                if any(p not in bots for p in room['members']):
                    raise ValueError('Every player must upload a bot or choose /bot demo first.')
                selected = {p: bots[p] for p in sorted(room['members'])}
                if room.get('practice'):
                    selected['practice'] = dict(name='Practice bot', attributes=[4, 3, 2], wasm=None)
                room['engine'] = HexWars(selected)
                room['match_bots'] = selected
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
        elif cmd in ('/bot', '/practice'):
            self.hex_waiting(room)
            if cmd == '/practice':
                if room['host'] != pid:
                    raise ValueError('Only the host can toggle the practice opponent.')
                if not room.get('practice') and len(room['members']) >= 6:
                    raise ValueError('Room is full.')
                room['practice'] = not room.get('practice', False)
            elif arg == 'demo':
                room.setdefault('bots', {})[pid] = dict(name=c['name'], attributes=[4, 3, 2], wasm=None)
                await self.send(c, dict(type='event', text='Built-in Expander selected. Ready for /start.'))
            else:
                raise ValueError('Use /bot demo, or /bot upload PATH.c in the game client.')
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

    @staticmethod
    def hex_joinable(room):
        if room['engine'] and not room['engine'].over:
            raise ValueError('Match running. Join after results.')
        if len(room['members']) + int(room.get('practice', False)) >= 6:
            raise ValueError('Hex Wars has at most 6 players, including the practice bot.')

    @staticmethod
    def hex_waiting(room):
        if not room or room['game'] != 'hexwars':
            raise ValueError('Host or join a Hex Wars room first: /host hexwars.')
        if room['engine'] and not room['engine'].over:
            raise ValueError('Wait until the match ends before changing bots.')

    async def upload_bot(self, pid, msg):
        rid, room = self.room_for(pid)
        self.hex_waiting(room)
        if msg.get('room') != rid:
            raise ValueError('Bot upload targets a different room.')
        client = self.clients[pid]
        now = time.monotonic()
        if now - client.get('bot_upload', -100) < 3:
            raise ValueError('Wait 3 seconds between bot uploads.')
        client['bot_upload'] = now
        encoded = msg.get('wasm')
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_WASM + 2) // 3):
            raise ValueError('Bot upload exceeds 32 KiB.')
        try:
            data = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError('Malformed bot upload.') from exc
        async with self.bot_slots:
            attributes = await asyncio.to_thread(inspect_bot, data)
        # Compilation checks yield: the host may have started or closed the room.
        if self.rooms.get(rid) is not room or pid not in room['members']:
            raise ValueError('Room changed during bot validation; upload again.')
        self.hex_waiting(room)
        digest = hashlib.sha256(data).hexdigest()[:12]
        room.setdefault('bots', {})[pid] = dict(name=client['name'], attributes=attributes, wasm=data)
        await self.send(client, dict(type='event', text=f'Bot ready [{digest}]. Growth/attack/armor: {attributes}.'))
        await self.room_state(rid)

    async def hex_turn(self, rid, room, engine):
        try:
            replies, jobs, ids = {}, [], []
            for i, player in enumerate(engine.players):
                if not engine.alive(i):
                    continue
                pid = player['pid']
                bot = room['match_bots'][pid]
                if bot['wasm'] is None:
                    replies[pid] = dict(action=demo_action(engine, i))
                else:
                    ids.append(pid)
                    jobs.append((bot['wasm'], engine.snapshot(i)))
            if jobs:
                try:
                    async with self.bot_slots:
                        results = await asyncio.to_thread(run_bots, jobs)
                    replies.update(zip(ids, results))
                except ValueError:
                    replies.update((pid, dict(error='runtime failed')) for pid in ids)
            if self.rooms.get(rid) is room and room['engine'] is engine:
                engine.step(replies)
                await self.room_state(rid)
        finally:
            room['busy'] = False
            room['last'] = time.monotonic()

    async def invite(self,pid,rid):
        now = time.monotonic()
        c = self.clients[pid]
        if now-c.get('invite',-100)<10:
            raise ValueError('Wait 10 seconds between invitations.')
        c['invite'] = now
        if self.auth_broker:
            await self.broadcast(dict(type='invite', text=f"{c['name']} [42 Verified] invites you to {self.rooms[rid]['game']}; /join {rid}."))
            return
        await self.mesh.publish('invite',f"{c['name']} invites you to {self.rooms[rid]['game']}; server {self.mesh.host}:{self.port}, /join {rid}. Use /connect {self.mesh.host} {self.port} if on another node.")

    async def handle(self,reader,writer):
        pid = None
        owner_key = None
        try:
            line = await asyncio.wait_for(reader.readline(),10)
            if len(line)>65536:
                raise ValueError('Handshake too large.')
            source = writer.get_extra_info('peername')[0]
            if not self.auth_broker and line.startswith(b'GET '):
                if not ipaddress.ip_address(source).is_loopback:
                    raise ValueError('Callback is loopback-only.')
                await self.callbacks.handle(reader, writer, line)
                return
            hello = json.loads(line)
            if self.auth_broker and (not isinstance(hello, dict) or hello.get('type') not in ('hello', 'ping')):
                raise ValueError('Guest mesh and local control are not accepted by the secure lobby.')
            if isinstance(hello, dict) and hello.get('type') == 'oauth_wait' and hello.get('protocol') == PROTOCOL:
                if self.auth_broker or not ipaddress.ip_address(source).is_loopback:
                    raise ValueError('Callback registration is loopback-only.')
                await self.callbacks.wait(hello.get('state'), reader, writer,close_tab=hello.get('close_tab') is True)
                return
            if isinstance(hello,dict) and hello.get('protocol')==PROTOCOL:
                if hello.get('type')=='mesh':
                    self.mesh.host = writer.get_extra_info('sockname')[0]
                    await self.mesh.merge(source,hello)
                    await self.send(dict(writer=writer),self.mesh.snapshot())
                    await self.state()
                    return
                if hello.get('type')=='direct_message':
                    if self.auth_broker:raise ValueError('Guest mesh messages cannot enter a verified lobby.')
                    from .mesh import endpoint
                    peer=self.mesh.peers.get(endpoint(source,hello.get('port')))
                    sender=hello.get('sender');target=hello.get('target');message=hello.get('text')
                    if (not peer or not peer.get('seen') or not isinstance(sender,str)
                            or not any(p['name']==sender for p in peer.get('players',[]))
                            or not isinstance(target,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',target)
                            or not isinstance(message,str) or not message.strip() or len(message)>400):
                        raise ValueError('Known LAN42 peer and valid direct message required.')
                    now=time.monotonic()
                    if now-peer.get('last_dm',-1000)<2:raise ValueError('Wait two seconds before sending another message.')
                    peer['last_dm']=now
                    delivered=await self.deliver_direct(sender,target,message)
                    await self.send(dict(writer=writer),dict(type='direct_ack',delivered=delivered))
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
            identity = None
            if self.auth_broker:
                if not writer.get_extra_info('ssl_object'):
                    raise ValueError('Authentication requires TLS.')
                identity = self.auth_broker.authenticate(hello.get('session'))
            name = identity['login'] if identity else clean(hello.get('name','guest'),24)
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,24}',name):
                raise ValueError('Invalid guest username.')
            role = hello.get('role','lobby')
            if role not in ('lobby','game'):
                raise ValueError('Unknown client role.')
            if len(self.clients)>=32 or any((c['name']==name or (identity and c.get('uid')==identity['uid']))
                                           and c.get('role','lobby')==role for c in self.clients.values()):
                raise ValueError('Lobby full or this guest name is already connected.')
            self.sequence += 1
            pid = str(self.sequence)
            c = dict(writer=writer,name=name,role=role,hostname=clean(hello.get('hostname','unknown'),50),
                     window=time.monotonic(),count=0)
            if identity:
                from .network import seat_label
                c.update(uid=identity['uid'], session_key=identity['session_key'], seat=seat_label(source))
            self.clients[pid] = c
            await self.send(c,dict(type='welcome',id=pid,version=VERSION,name=name,verified=bool(identity)))
            if role=='lobby':
                await self.event(f"{name} joined as {'42 Verified' if identity else 'Guest'}.")
            await self.state()
            while True:
                line = await reader.readline()
                if not line:
                    break
                if len(line)>49152:
                    raise ValueError('Message too large.')
                msg = json.loads(line)
                if not isinstance(msg,dict):
                    raise ValueError('Expected an object.')
                if self.auth_broker and not self.auth_broker.active(c['session_key']):
                    raise ValueError('Sign-in expired. Use /signin again.')
                now = time.monotonic()
                if now-c['window']>=1:
                    c['window'],c['count'] = now,0
                c['count'] += 1
                if c['count']>30:
                    continue
                try:
                    if msg.get('type')=='command':
                        await self.command(pid,msg.get('text',''))
                    elif msg.get('type')=='koel_deliver':
                        if not self.auth_broker or not self.koeldrop:raise ValueError('KoelDrop requires the verified host service.')
                        await self.koeldrop.deliver_invite(self,pid,msg)
                    elif msg.get('type')=='direct_batch':
                        self.start_direct_batch(pid,msg)
                    elif msg.get('type') == 'hex_bot':
                        await self.upload_bot(pid, msg)
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
                task=self.clients[pid].get('dm_task')
                if task:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):await task
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
            if self.auth_broker:
                for c in list(self.clients.values()):
                    if not self.auth_broker.active(c['session_key']):
                        await self.send(c, dict(type='signed_out'))
                        c['writer'].close()
            for rid,room in list(self.rooms.items()):
                engine = room['engine']
                if room['game']=='forknite' and time.monotonic()-room.get('status_at',0)>.5:
                    room['status_at']=time.monotonic()
                    try:
                        status=await room['web'].control(dict(action='status'))
                        if status!=room.get('last_status'):
                            room['last_status']=status
                            await self.broadcast(dict(type='forknite_status',status=status),room['members'])
                    except (OSError,ValueError):pass
                if room['game']=='forknite' and getattr(room['web'],'tool_ready',[]):
                    names=room['web'].tool_ready;room['web'].tool_ready=[]
                    host=self.clients.get(room['host'])
                    if host:await self.send(host,dict(type='tools_required',logins=names))
                if not engine:
                    continue
                if room['game']=='tetris' and not engine.over and time.monotonic()-room['last']>=.65:
                    engine.move('down')
                    room['last'] = time.monotonic()
                    await self.room_state(rid)
                elif room['game'] == 'hexwars' and not engine.over and not room.get('busy') and time.monotonic()-room['last'] >= .65:
                    room['busy'] = True
                    task = asyncio.create_task(self.hex_turn(rid, room, engine))
                    self.hex_tasks.add(task)
                    task.add_done_callback(self.hex_tasks.discard)
                elif room['game']=='bluff':
                    old = engine.phase
                    engine.tick(time.time())
                    if old!=engine.phase:
                        await self.room_state(rid)

async def serve(host,port,ready=None,managed=False):
    from .updater import generation
    installed_generation = generation()
    lobby = Lobby()
    async def watch_updates():
        while True:
            await asyncio.sleep(.2)
            if generation() != installed_generation:
                lobby.shutdown.set()
                return
    watcher = asyncio.create_task(watch_updates()) if managed else None
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
        if watcher:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)
        ticker.cancel()
        presence.cancel()
        mesh_task.cancel()
        await asyncio.gather(ticker,presence,mesh_task,return_exceptions=True)
        for task in list(lobby.hex_tasks):
            task.cancel()
        await asyncio.gather(*list(lobby.hex_tasks), return_exceptions=True)
        for room in list(lobby.rooms.values()):
            if room.get('web'):await room['web'].close()
        lobby.rooms.clear()
        await lobby.mesh.goodbye()
        for client in list(lobby.clients.values()):
            client['writer'].close()

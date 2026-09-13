"""Curses frontend. All invites execute notifications on this client only."""
import collections
import curses
import json
import os
import pwd
import queue
import shutil
import socket
import subprocess
import threading
import time
import textwrap
import shlex
import sys
from pathlib import Path
from . import VERSION, PROTOCOL
from .network import seat_address, address
from .lobby_view import lobby_lines, guest_style

HELP = [
    '/lobby or /who: roster | /map 1 or /map 2: seats | /next /prev: lobby pages',
    '/who /rooms /games | /host tetris | /host bluff free | /host bluff prompt',
    '/join (seat questions) | /join ROOM | /invite (friend seat) | /invite-room',
    '/start /leave | /answer TEXT | /vote USER1 USER2 ... | /connect IP [PORT]',
    '/signin (coming later) | /notify on|off | /home (your node) | /help | /quit',
    'Chat: type and Enter. PgUp/PgDn scroll. Tetris: Tab toggles play/chat.',
    'Tetris play: arrows or WASD move/rotate, Space drops. Shared board!',
    'Bluff: identify each entry author in order; own entry is ignored in scoring.',
]

MIN_COLUMNS = 76
MIN_ROWS = 28


def request_terminal_resize(stream=sys.stdout, get_size=shutil.get_terminal_size):
    """Ask compatible terminals to grow to the minimum UI dimensions."""
    if not stream.isatty():
        return False
    size = get_size((MIN_COLUMNS, MIN_ROWS))
    columns = max(size.columns, MIN_COLUMNS)
    rows = max(size.lines, MIN_ROWS)
    if (columns, rows) == (size.columns, size.lines):
        return False
    stream.write(f'\033[8;{rows};{columns}t')
    stream.flush()
    return True

def safe(value):
    return ''.join(c for c in str(value) if c.isprintable())

class Client:
    def __init__(self, sock, name, hostname, notify=True, role='lobby', initial_command=None):
        self.sock, self.name = sock, name
        self.role, self.initial_command = role, initial_command
        self.inbox = queue.Queue(maxsize=256)
        self.lines = collections.deque(HELP,maxlen=500)
        self.state, self.game = {}, {}
        self.input, self.scroll = '', 0
        self.play = False
        self.lobby_view, self.cluster, self.lobby_page = 'roster', 1, 0
        self.show_lobby = False
        self.colors = False
        self.connected = True
        self.notify_enabled, self.last_notice = notify, 0
        self.id = None
        self.wizard = None
        self.next_server = None
        self.send(dict(type='hello',protocol=PROTOCOL,name=name,hostname=hostname,role=role))
        threading.Thread(target=self.receive,daemon=True).start()

    def send(self,data):
        try:
            self.sock.sendall((json.dumps(data)+'\n').encode())
        except OSError:
            self.connected = False

    def receive(self):
        try:
            with self.sock.makefile('rb') as stream:
                while True:
                    line = stream.readline(65537)
                    if not line:
                        break
                    if len(line)>65536:
                        raise ValueError('Oversized server response')
                    msg = json.loads(line)
                    if not isinstance(msg,dict):
                        raise ValueError('Invalid response')
                    self.inbox.put(msg,timeout=2)
        except (OSError,ValueError,queue.Full):
            pass
        finally:
            self.connected = False

    def notify(self,text):
        now = time.monotonic()
        if not self.notify_enabled or now-self.last_notice<3:
            return
        self.last_notice = now
        if shutil.which('notify-send'):
            # Positional args only, never invoke a shell with received text.
            def show():
                try:
                    subprocess.run(['notify-send','--app-name=42SG LAN','--expire-time=7000',
                                    '--','42SG LAN',safe(text)],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
                except (OSError,subprocess.TimeoutExpired):
                    pass
            threading.Thread(target=show,daemon=True).start()
        else:
            try:
                curses.beep()
            except curses.error:
                pass

    def consume(self):
        while True:
            try:
                msg = self.inbox.get_nowait()
            except queue.Empty:
                break
            kind = msg.get('type')
            if kind in ('event','error','invite','online'):
                self.lines.append(safe(msg.get('text','')))
                if kind in ('invite','online'):
                    self.notify(msg.get('text',''))
            elif kind=='welcome':
                self.id = msg['id']
                if getattr(self,'initial_command',None):
                    self.send(dict(type='command',text=self.initial_command))
                    self.initial_command = None
                self.lines.append(f"Connected. Server {msg['version']}; Guest (unverified).")
            elif kind=='state':
                old_rooms = {(r.get('address'),r.get('port'),r['id']) for r in self.state.get('rooms',[])}
                self.state = msg
                for room in msg.get('rooms',[]):
                    if (room.get('address'),room.get('port'),room['id']) not in old_rooms:
                        self.lines.append(f"Game {room['name']} hosted by {room['host']}: /connect {room.get('address')} {room.get('port')}, then /join {room['id']}")

            elif kind=='game':
                new = msg.get('room') != self.game.get('room')
                if new:
                    self.show_lobby = False
                self.game = msg
                if not msg.get('game'):
                    self.play = False
                elif msg.get('game')=='tetris' and 'board' in msg and (new or 'board' not in getattr(self,'previous_game',{})):
                    self.play = True
                self.previous_game = msg
                signature = (msg.get('room'),msg.get('phase'))
                if msg.get('game')=='bluff' and signature!=getattr(self,'round_signature',None):
                    self.lines.append('BLUFF '+msg.get('phase','')+': '+msg.get('prompt',''))
                    for option in msg.get('options',[]):
                        self.lines.append(f"{option['number']}. {msg.get('leader')} (author: {option.get('author') or 'hidden'}): {option['text']}")
                    if msg.get('result'):
                        self.lines.append(msg['result'])
                    self.round_signature = signature

    def line(self,screen,y,text,attr=0,x=0):
        h,w = screen.getmaxyx()
        if 0<=y<h and x<w-1:
            try:
                screen.addnstr(y,x,safe(text),w-x-1,attr)
            except curses.error:
                pass

    def link_friend(self, target, port):
        try:
            if self.peer_callback:
                self.peer_callback(target,port)
            self.game_target = (target,port)
            self.lines.append(f'Linked {target}:{port}. HQ stays here; /join NUMBER opens their game in another window.')
        except (OSError,RuntimeError,ValueError) as exc:
            self.lines.append('Could not link friend: '+str(exc))

    def open_game(self, text):
        parts = text.split()
        if parts[0]=='/host':
            if len(parts) not in (2,3) or parts[1] not in ('tetris','bluff') or (len(parts)==3 and parts[2] not in ('free','prompt')):
                self.lines.append('Use /host tetris or /host bluff free|prompt.')
                return
            target,port = self.home
            action = ['--create',parts[1],'--game-mode',parts[2] if len(parts)==3 else 'free']
        else:
            if len(parts)!=2 or not parts[1].isdigit():
                self.lines.append('Use /join ROOM_NUMBER.')
                return
            target,port = self.game_target
            action = ['--room',parts[1]]
        args = ['game',target,'--port',str(port),'--guest-name',self.name,*action]
        opener = Path(__file__).resolve().parents[1]/'useful-scripts/open_terminal.py'
        try:
            result = subprocess.run([sys.executable,str(opener),*args],capture_output=True,text=True,timeout=10)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())
            self.lines.append('Requested a game terminal. Your HQ stays online here.')
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
            self.lines.append('Could not open game window: '+str(exc))
            self.lines.append('Open another terminal and run: '+shlex.join(['sh',str(opener.parents[1]/'lan42.sh'),*args]))

    def lobby_command(self, text):
        if text in ('/lobby','/who','/roster'):
            self.lobby_view, self.lobby_page = 'roster', 0
            self.show_lobby, self.play = True, False
        elif text in ('/map','/map 1','/map 2'):
            self.lobby_view, self.lobby_page = 'map', 0
            if text != '/map':
                self.cluster = int(text[-1])
            self.show_lobby, self.play = True, False
        elif text in ('/next','/prev'):
            self.lobby_page = max(0,getattr(self,'lobby_page',0)+(1 if text=='/next' else -1))
        elif text == '/game':
            self.show_lobby = False
            self.play = self.game.get('game')=='tetris' and 'board' in self.game
        else:
            return False
        return True

    def draw_lobby(self, screen, players):
        h,w = screen.getmaxyx()
        content = lobby_lines(players,getattr(self,'lobby_view','roster'),getattr(self,'cluster',1))
        capacity = min(max(1,h-13),max(10,len(content)))
        pages = max(1,(len(content)+capacity-1)//capacity)
        self.lobby_page = min(getattr(self,'lobby_page',0),pages-1)
        self.line(screen,3,f'CURRENTLY ONLINE: {len(players)} | Guest names are unverified',curses.A_BOLD)
        self.line(screen,4,f'/roster | /map 1 | /map 2 | /next /prev (page {self.lobby_page+1}/{pages})')
        for y,segments in enumerate(content[self.lobby_page*capacity:(self.lobby_page+1)*capacity],5):
            x = 0
            for text,style in segments:
                attr = curses.A_BOLD if style else 0
                if style and getattr(self,'colors',False):
                    attr |= curses.color_pair(style)
                self.line(screen,y,text,attr,x)
                x += len(text)
        bottom = 5+capacity
        self.line(screen,bottom,'-'*(w-1),curses.A_DIM)
        self.line(screen,bottom+1,'CHAT & INVITATIONS  | /host tetris | /host bluff free | /rooms',curses.A_BOLD)
        return bottom+2

    def window_label(self):
        if getattr(self,'role','lobby')!='game':
            return 'HQ LOBBY'
        names = {'tetris':'TETRIS', 'bluff':'WHO SAID THAT?'}
        game = self.game
        if game.get('game'):
            return f"GAME | {names.get(game['game'],safe(game['game']).upper())} | ROOM {safe(game.get('room','?'))}"
        return 'GAME WINDOW | NO ROOM'

    def terminal_title(self):
        return safe(f'LAN42 | {self.window_label()} | {self.name}')

    def update_title(self):
        title = self.terminal_title()
        if title!=getattr(self,'last_title',None) and sys.stdout.isatty():
            sys.stdout.write('\033]0;'+title+'\007')
            sys.stdout.flush()
            self.last_title = title

    def draw(self,screen):
        screen.erase()
        h,w = screen.getmaxyx()
        if h<28 or w<76:
            self.line(screen,0,'Please resize terminal to at least 76 columns x 28 rows.')
            self.line(screen,1,'Ctrl-C exits.')
            screen.refresh()
            return
        game_window = getattr(self,'role','lobby')=='game'
        banner = curses.A_BOLD | curses.A_REVERSE
        if getattr(self,'colors',False):
            banner |= curses.color_pair(4 if game_window else 2)
        label = f" LAN42 | {self.window_label()} | {self.name} [Guest] | "+('ONLINE' if self.connected else 'DISCONNECTED')
        self.line(screen,0,label.ljust(w-1),banner)
        hint = ('GAME CONTROLS: /start /leave /quit | /lobby /game | HQ stays in its other window'
                if game_window else 'HQ: /join IP [PORT] | /host tetris /host bluff free: new game window | /who /map 1')
        self.line(screen,1,hint)
        players = self.state.get('players',[])
        if not self.state:
            self.line(screen,2,'Connecting; waiting for presence...')
            self.line(screen,3,'Loading online roster...')
            screen.refresh()
            return
        self.line(screen,2,f"{len(players)} online across {self.state.get('nodes',1)} nodes | refresh ~5s | "+
                  str(getattr(self,'current', 'Connecting...')),curses.A_BOLD)
        game = self.game
        logs_x,logs_y = 0,6
        if not game.get('game') or getattr(self,'show_lobby',False):
            logs_y = self.draw_lobby(screen,players)
        elif game.get('game')=='tetris' and 'board' in game:
            self.line(screen,6,f"CO-OP TETRIS  {game['score']} pts")
            for y,row in enumerate(game['board']):
                self.line(screen,7+y,'|' + ''.join('[]' if c else ' .' for c in row)+'|')
            self.line(screen,25,'GAME OVER /start' if game['over'] else ('PLAY: arrows/space' if self.play else 'CHAT: Tab to play'))
            logs_x = 25
        elif game.get('game')=='bluff' and game.get('phase')!='waiting':
            phase = game['phase']
            self.line(screen,6,f"WHO SAID THAT? {phase.upper()} | leader: {game['leader']} | {max(0,int(game['deadline']-time.time()))}s")
            self.line(screen,7,game['prompt'])
            self.line(screen,8,f"Answers {game['submitted']}/{game['total']}; votes {game['voted']}/{game['total']}")
            self.line(screen,9,'/answer TEXT' if phase=='writing' else '/vote USER1 USER2 ... (one per entry; see history)')
            self.line(screen,10,'Players: '+', '.join(game.get('players',[])))
            logs_y = 12
        elif game.get('game'):
            self.line(screen,6,f"Room {game['room']} {game['game']} | waiting; host uses /start")
            logs_y = 8
        log_h = max(1,h-logs_y-3)
        lines = [part for line in self.lines for part in (textwrap.wrap(line,max(10,w-logs_x-2)) or [''])]
        self.scroll = min(self.scroll,max(0,len(lines)-log_h))
        end = len(lines)-self.scroll
        shown = lines[max(0,end-log_h):end]
        for y,line in enumerate(shown,logs_y):
            self.line(screen,y,line,x=logs_x)
        self.line(screen,h-2,'Tab: roster/map (game: play/chat) | PgUp/PgDn: chat | /quit',curses.A_DIM)
        self.line(screen,h-1,('PLAY > ' if self.play else '> ')+self.input[-(w-10):])
        screen.refresh()

    def seat_question(self, intent):
        self.wizard = (intent, [])
        self.lines.append('Find seats: https://meta.intra.42.fr/clusters')
        self.lines.append('Friend server cluster (1 or 2)? /cancel to cancel.')

    def wizard_answer(self, text):
        intent, values = self.wizard
        if text=='/cancel':
            self.wizard = None
            self.lines.append('Cancelled.')
            return
        try:
            value = int(text)
            if (not values and value not in (1,2)) or not 1<=value<=254:
                raise ValueError()
        except ValueError:
            self.lines.append('Enter 1 or 2.' if not values else 'Enter a number from 1 to 254.')
            return
        values.append(value)
        if len(values)<3:
            self.lines.append('Row number?' if len(values)==1 else 'Seat number?')
            return
        self.wizard = None
        seat = f'c{values[0]}r{values[1]}s{values[2]}'
        target = seat_address(seat)
        if intent=='join':
            self.next_server = (target,self.port)
        else:
            self.send(dict(type='command',text='/invite-seat '+seat))
            self.lines.append(f'Trying friend server at {seat} = {target}...')

    def run(self,screen):
        screen.timeout(80)
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1,curses.COLOR_GREEN,curses.COLOR_BLACK)
            for pair,color in enumerate((curses.COLOR_CYAN,curses.COLOR_YELLOW,curses.COLOR_MAGENTA,
                                         curses.COLOR_BLUE,curses.COLOR_RED,curses.COLOR_WHITE),2):
                curses.init_pair(pair,color,curses.COLOR_BLACK)
            self.colors = True
        while True:
            self.consume()
            self.update_title()
            if not self.connected and self.home != self.current:
                return self.home
            self.draw(screen)
            key = screen.getch()
            if key in (3,4):
                break
            if key==curses.KEY_PPAGE:
                self.scroll += 8
            elif key==curses.KEY_NPAGE:
                self.scroll = max(0,self.scroll-8)
            elif key==9 and (not self.game.get('game') or self.show_lobby):
                self.lobby_view = 'map' if self.lobby_view=='roster' else 'roster'
                self.lobby_page = 0
            elif key==9 and self.game.get('game')=='tetris':
                self.play = not self.play
            elif self.play:
                action = {curses.KEY_LEFT:'left',ord('a'):'left',
                          curses.KEY_RIGHT:'right',ord('d'):'right',
                          curses.KEY_UP:'rotate',ord('w'):'rotate',
                          curses.KEY_DOWN:'down',ord('s'):'down',32:'drop'}.get(key)
                if action:
                    self.send(dict(type='move',action=action))
                elif key==ord('/'):
                    self.play,self.input = False,'/'
            elif key in (10,13):
                text,self.input = self.input.strip(),''
                self.scroll = 0
                if self.wizard:
                    self.wizard_answer(text)
                    if self.next_server:
                        if self.role=='lobby':
                            self.link_friend(*self.next_server)
                            self.next_server = None
                        else:
                            return self.next_server
                elif self.role=='lobby' and text.startswith('/join ') and not text.split()[1].isdigit():
                    parts = text.split()
                    try:
                        if len(parts) not in (2,3):
                            raise ValueError('Use /join IP_OR_SEAT [PORT].')
                        self.link_friend(address(parts[1]),int(parts[2]) if len(parts)==3 else self.port)
                    except ValueError as exc:
                        self.lines.append(str(exc))
                elif getattr(self,'role','lobby')=='lobby' and (text.startswith('/host ') or text.startswith('/join ')):
                    self.open_game(text)
                elif self.lobby_command(text):
                    pass
                elif text in ('/join','/connect'):
                    self.seat_question('join')
                elif text=='/invite':
                    self.seat_question('invite')
                elif text.startswith('/connect '):
                    parts = text.split()
                    try:
                        target = address(parts[1])
                        port = int(parts[2]) if len(parts)==3 else self.port
                        if len(parts)>3 or not 1<=port<=65535:
                            raise ValueError()
                        if self.role=='lobby':
                            self.link_friend(target,port)
                        else:
                            return target,port
                    except ValueError:
                        self.lines.append('Use /connect IP_OR_SEAT [PORT].')
                elif text=='/home':
                    if self.role=='lobby':
                        self.game_target = self.home
                        self.lobby_command('/lobby')
                        self.lines.append('Game target reset to your own node.')
                    else:
                        break
                elif text=='/quit':
                    break
                elif text=='/help':
                    self.lines.extend(HELP)
                elif text.startswith('/notify'):
                    self.notify_enabled = text=='/notify on'
                    self.lines.append('Notifications '+('on' if self.notify_enabled else 'off'))
                elif text:
                    if self.connected:
                        self.send(dict(type='command',text=text))
                    else:
                        self.lines.append('Disconnected. /quit and reconnect using lan42 join HOST.')
            elif key in (127,8,curses.KEY_BACKSPACE):
                self.input = self.input[:-1]
            elif 32<=key<=126 and len(self.input)<400:
                self.input += chr(key)

def connect(host,port,name=None,notify=True,peer_callback=None,home=None,role='lobby',initial_command=None,game_target=None):
    username = name or pwd.getpwuid(os.getuid()).pw_name
    if request_terminal_resize():
        # Window managers apply the request asynchronously; give curses a moment
        # to observe the new dimensions. Unsupported terminals safely ignore it.
        time.sleep(.15)
    while True:
        print(f'Connecting to {host}:{port} as Guest...')
        try:
            sock = socket.create_connection((host,port),timeout=5)
        except OSError as e:
            if home and (host,port)!=home:
                print(f'Peer unavailable; returning to your node. {e}')
                host,port = home
                continue
            raise OSError(f'Cannot connect to {host}:{port}. Friend must run lan42; check seat/network. {e}')
        with sock:
            sock.settimeout(None)
            client = Client(sock,username,socket.gethostname(),notify,role,initial_command)
            client.peer_callback = peer_callback
            client.game_target = game_target or (host,port)
            client.port = port
            client.home = home or (host,port)
            client.current = (host,port)
            # xterm-style title stack: restore the shell title when supported.
            title_terminal = sys.stdout.isatty()
            if title_terminal:
                sys.stdout.write('\033[22;0t')
                sys.stdout.flush()
            try:
                destination = curses.wrapper(client.run)
            finally:
                if title_terminal:
                    sys.stdout.write('\033[23;0t')
                    sys.stdout.flush()
            # Explicitly shutdown: the receive thread's file object also owns the socket.
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
        if not destination:
            return
        host,port = destination
        if peer_callback:
            try:
                peer_callback(host,port)
            except (OSError,RuntimeError,ValueError) as e:
                print(f'Peer unavailable: {e}. Returning to your node.')
                host,port = home

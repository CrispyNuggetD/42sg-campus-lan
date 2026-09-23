"""Curses frontend. Desktop notifications execute on this client only."""
import collections
import base64
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
from .hexbot import SDK, compile_bot
from . import auth_client

HELP = [
    '/lobby or /who: roster | /map 1 or /map 2: seats | /next /prev: lobby pages',
    '/who /rooms /games | /host tetris | /host bluff free|prompt | /host hexwars',
    'Hex Wars: /bot (menu) | /bot upload PATH.c | /bot demo | /practice | /start',
    '/join (seat questions) | /join ROOM | /invite (friend seat) | /invite-room',
    '/start /leave | /answer TEXT | /vote USER1 USER2 ... | /connect IP [PORT]',
    '/signin /signout | /authhost SEAT | /notify on|off | /home | /help | /quit',
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
    def __init__(self, sock, name, hostname, notify=True, role='lobby', initial_command=None, auth_session=None):
        self.secure = auth_session is not None
        self.session_token = auth_session['session'] if auth_session else None
        self.signing_in = False
        self.auth_destination = None
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
        hello = dict(type='hello',protocol=PROTOCOL,name=name,hostname=hostname,role=role)
        if auth_session:
            hello['session'] = auth_session['session']
        self.send(hello)
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

    def notify(self,text,throttle=True):
        now = time.monotonic()
        if not self.notify_enabled or (throttle and now-self.last_notice<3):
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
            if kind == 'local_signin':
                self.signing_in = False
                if msg.get('error'):
                    self.lines.append(safe(msg['error']))
                else:
                    self.auth_destination = tuple(msg['destination'])
            elif kind == 'signed_out':
                if getattr(self, 'secure', False):
                    auth_client.clear_session(getattr(self, 'session_token', None))
                    self.lines.append('Signed out or session expired. Use /signin from local HQ.')
            elif kind == 'local_bot':
                self.bot_compiling = False
                if msg.get('error'):
                    self.lines.append('Bot compile: ' + safe(msg['error']))
                elif self.game.get('room') != msg['room'] or self.game.get('game') != 'hexwars':
                    self.lines.append('Room changed during compilation; upload again.')
                else:
                    self.send(dict(type='hex_bot', room=msg['room'], wasm=msg['wasm']))
                    self.lines.append('Compiled; host is validating your bot...')
            elif kind in ('event','error','invite','online'):
                self.lines.append(safe(msg.get('text','')))
                if kind in ('invite','online'):
                    self.notify(msg.get('text',''))
                elif kind=='event' and getattr(self,'role','lobby')=='lobby':
                    # Existing local and mesh chat events use this wire format.
                    delimiter = ' [42 Verified]: ' if getattr(self, 'secure', False) else ' [Guest]: '
                    sender,separator,_ = msg.get('text','').partition(delimiter)
                    if separator and sender!=self.name:
                        self.notify(msg['text'],throttle=False)
            elif kind=='welcome':
                self.id = msg['id']
                if getattr(self, 'secure', False):
                    self.name = msg['name']
                if getattr(self,'initial_command',None):
                    self.send(dict(type='command',text=self.initial_command))
                    self.initial_command = None
                self.lines.append(f"Connected. Server {msg['version']}; " + ('42 Verified over TLS.' if getattr(self, 'secure', False) else 'Guest (unverified).'))
            elif kind=='state':
                old_rooms = {(r.get('address'),r.get('port'),r['id']) for r in self.state.get('rooms',[])}
                if not getattr(self, 'secure', False):
                    for player in msg.get('players', []):
                        player['verified'] = False
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
                if msg.get('game') == 'hexwars' and msg.get('result') and msg.get('result') != getattr(self, 'hex_result', None):
                    self.lines.append(msg['result'])
                if msg.get('game') == 'hexwars':
                    self.hex_result = msg.get('result')
                    old_faults = getattr(self, 'hex_faults', {}) if not new and msg.get('turn', 0) else {}
                    for score in msg.get('scores', []):
                        if score['faults'] > old_faults.get(score['symbol'], 0):
                            self.lines.append(safe(f"{score['name']}: {score['status']} ({score['faults']}/3 faults)"))
                    self.hex_faults = {score['symbol']: score['faults'] for score in msg.get('scores', [])}
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
        if getattr(self, 'secure', False):
            self.lines.append('Verified players share this TLS lobby. /signout returns to the guest mesh.')
            return
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
            if len(parts) not in (2,3) or parts[1] not in ('tetris','bluff','hexwars') or (len(parts)==3 and parts[2] not in ('free','prompt')):
                self.lines.append('Use /host tetris, /host bluff free|prompt, or /host hexwars.')
                return
            target,port = self.current if getattr(self, 'secure', False) else self.home
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
        self.line(screen,3,f"CURRENTLY ONLINE: {len(players)} | " + ('42 identities verified over TLS' if getattr(self, 'secure', False) else 'Guest names are unverified'),curses.A_BOLD)
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
        self.line(screen,bottom+1,'CHAT & INVITATIONS | /host hexwars | /host tetris | /rooms',curses.A_BOLD)
        return bottom+2

    def window_label(self):
        if getattr(self,'role','lobby')!='game':
            return 'HQ LOBBY'
        names = {'tetris':'TETRIS', 'bluff':'WHO SAID THAT?', 'hexwars':'HEX WARS'}
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
        label = f" LAN42 | {self.window_label()} | {self.name} [{'42 Verified' if getattr(self, 'secure', False) else 'Guest'}] | "+('ONLINE' if self.connected else 'DISCONNECTED')
        self.line(screen,0,label.ljust(w-1),banner)
        hint = ('GAME CONTROLS: /start /leave /quit | /lobby /game | HQ stays in its other window'
                if game_window else 'HQ: /join IP [PORT] | /host hexwars | /host tetris | /games | /who')
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
        elif game.get('game') == 'hexwars':
            logs_y = self.draw_hexwars(screen)
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

    def start_signin(self):
        if getattr(self, 'secure', False):
            self.lines.append('Already signed in with 42. /signout ends this session.')
            return
        if self.role != 'lobby' or self.current != self.home:
            self.lines.append('Use /signin in your local HQ window.')
            return
        if self.signing_in:
            self.lines.append('Sign-in is already waiting in your browser (five-minute limit).')
            return
        self.signing_in = True
        self.lines.append("Opening 42 in your browser. Enter credentials only on 42's website.")
        def authenticate():
            try:
                destination = auth_client.sign_in(self.home)
                message = dict(type='local_signin', destination=destination)
            except Exception as exc:
                # Only explicitly safe AuthError strings are exposed to the UI.
                message = dict(type='local_signin', error=str(exc) if isinstance(exc, auth_client.AuthError)
                               else 'Sign-in failed or timed out. Check the auth host and try again.')
            try:
                self.inbox.put(message, timeout=2)
            except queue.Full:
                self.signing_in = False
        threading.Thread(target=authenticate, daemon=True).start()

    def draw_hexwars(self, screen):
        game = self.game
        self.line(screen, 4, 'HEX WARS | CODE YOUR CONQUEST', curses.A_BOLD)
        if 'cells' not in game:
            self.line(screen, 6, 'BOT WORKSHOP  /bot opens the upload menu', curses.A_BOLD)
            self.line(screen, 7, '/bot upload PATH.c | /bot demo | /bot guide | /practice')
            self.line(screen, 8, 'Write C -> upload -> everyone ready -> host /start')
            for y, bot in enumerate(game.get('bots', []), 10):
                self.line(screen, y, ('[READY] ' if bot['ready'] else '[EMPTY] ') + bot['name'])
            self.line(screen, 17, 'Practice opponent: ' + ('ON' if game.get('practice') else 'OFF') + ' | 2-6 armies')
            self.line(screen, 18, 'Growth + attack + armor = 9. Capture hexes; eliminate rival armies.')
            return 20
        self.line(screen, 5, f"Turn {game['turn']}/{game['max_turns']} | . neutral | letter=army, number=units")
        for r in range(-4, 5):
            cells = [c for c in game['cells'] if c['r'] == r]
            for column, cell in enumerate(cells):
                owner = cell['owner']
                symbol = '.' if owner < 0 else chr(65 + owner)
                attr = curses.A_BOLD if owner >= 0 else curses.A_DIM
                if owner >= 0 and getattr(self, 'colors', False):
                    attr |= curses.color_pair(owner + 2)
                self.line(screen, 7 + r + 4, f"<{symbol}{cell['units']:02}>", attr,
                          x=2 + abs(r) * 2 + column * 5)
        self.line(screen, 17, 'ARMY / TILES / UNITS / FAULTS (3 = out)', curses.A_BOLD)
        for index, score in enumerate(game.get('scores', [])):
            text = f"{score['symbol']} {score['name'][:12]:12} {score['tiles']:2}h {score['units']:4}u !{score['faults']}"
            self.line(screen, 18 + index // 2, text, x=(index % 2) * 37)
        self.line(screen, 21, game.get('result') or 'Bots act simultaneously. /leave forfeits your army.')
        return 22

    def bot_command(self, text):
        if self.game.get('game') != 'hexwars':
            self.lines.append('Open /host hexwars or join a Hex Wars room first.')
            return
        if text == '/bot':
            self.wizard = ('bot_menu', [])
            self.lines.extend(['BOT MENU: 1 Upload C file | 2 Use demo bot | 3 API guide | 4 Create starter',
                               'Choose 1-4, or /cancel.'])
        elif text == '/bot demo':
            self.send(dict(type='command', text=text))
        elif text == '/bot guide':
            self.lines.extend(['C API: bot_config(t_hw_attributes *a); bot_turn(const t_hw_state *s, t_hw_action *a);',
                               'Attributes: growth/attack/armor each 1..5, total 9. Action: from, to, units.',
                               'State: me, turn, cells[]. Each cell: owner, units, q/r, neighbors[6].',
                               'Move to a neighbor; leave one unit behind. units=0 passes. No libc/main().',
                               'Guide: ' + str(SDK / 'README.md'), 'Header: ' + str(SDK / 'hexwars.h')])
        elif text.startswith('/bot starter '):
            try:
                path = self.bot_path(text[len('/bot starter '):])
                with path.open('x') as output:
                    output.write((SDK / 'examples' / 'expander.c').read_text())
                self.lines.append('Starter saved: ' + str(path) + '. Edit it, then /bot upload PATH.c')
            except (OSError, ValueError) as exc:
                self.lines.append('Starter: ' + safe(exc))
        elif text.startswith('/bot upload '):
            if self.game.get('phase') == 'running':
                self.lines.append('Wait until the match ends before uploading.')
                return
            if getattr(self, 'bot_compiling', False):
                self.lines.append('A bot is already compiling.')
                return
            try:
                path = self.bot_path(text[len('/bot upload '):])
            except ValueError as exc:
                self.lines.append(str(exc))
                return
            self.bot_compiling = True
            room = self.game.get('room')
            self.lines.append('Compiling ' + path.name + '...')
            def compile_upload():
                try:
                    data = compile_bot(path)
                    message = dict(type='local_bot', room=room, wasm=base64.b64encode(data).decode('ascii'))
                except (ValueError, OSError) as exc:
                    message = dict(type='local_bot', error=str(exc))
                try:
                    self.inbox.put(message, timeout=2)
                except queue.Full:
                    self.bot_compiling = False
            threading.Thread(target=compile_upload, daemon=True).start()
        else:
            self.lines.append('/bot | /bot upload PATH.c | /bot starter PATH.c | /bot demo | /bot guide')

    @staticmethod
    def bot_path(text):
        parts = shlex.split(text)
        if len(parts) != 1:
            raise ValueError('Provide one path; quote it if it contains spaces.')
        return Path(parts[0]).expanduser().resolve()

    def bot_wizard_answer(self, intent, text):
        if text == '/cancel':
            self.wizard = None
        elif intent == 'bot_menu':
            if text in ('1', '4'):
                self.wizard = ('bot_upload' if text == '1' else 'bot_starter', [])
                self.lines.append('Enter a .c file path (quote spaces), or /cancel:')
            elif text in ('2', '3'):
                self.wizard = None
                self.bot_command('/bot demo' if text == '2' else '/bot guide')
            else:
                self.lines.append('Choose 1, 2, 3, or 4; /cancel exits.')
        else:
            self.wizard = None
            self.bot_command('/bot ' + ('upload ' if intent == 'bot_upload' else 'starter ') + text)

    def seat_question(self, intent):
        self.wizard = (intent, [])
        self.lines.append('Find seats: https://meta.intra.42.fr/clusters')
        self.lines.append('Friend server cluster (1 or 2)? /cancel to cancel.')

    def wizard_answer(self, text):
        intent, values = self.wizard
        if intent.startswith('bot'):
            self.bot_wizard_answer(intent, text)
            return
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
            if self.auth_destination:
                return self.auth_destination
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
                    if getattr(self, 'secure', False):
                        self.lines.append('Use /signout to return to your local guest HQ.')
                    elif self.role=='lobby':
                        self.game_target = self.home
                        self.lobby_command('/lobby')
                        self.lines.append('Game target reset to your own node.')
                    else:
                        break
                elif text=='/quit':
                    break
                elif text == '/signin':
                    self.start_signin()
                elif text.startswith('/authhost '):
                    if getattr(self, 'secure', False) or self.signing_in:
                        self.lines.append('Sign out or finish the pending sign-in before changing the auth host.')
                    else:
                        try:
                            host = auth_client.change_host(text.split(maxsplit=1)[1])
                            self.lines.append(f'Trusted sign-in host verified at {host}. Use /signin.')
                        except (OSError, ValueError):
                            self.lines.append('Could not verify the trusted host at that seat. Settings unchanged.')
                elif text == '/signout':
                    if getattr(self, 'secure', False):
                        self.send(dict(type='command', text='/signout'))
                    else:
                        self.lines.append('You are using the guest lobby. /signin opens 42 sign-in.')
                elif text == '/bot' or text.startswith('/bot '):
                    self.bot_command(text)
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
        print(f'Connecting to {host}:{port}...')
        try:
            sock, auth_session = auth_client.connect_socket(host, port)
        except (OSError, ValueError) as e:
            if home and (host,port)!=home:
                print(f'Peer unavailable; returning to your node. {e}')
                host,port = home
                continue
            raise OSError(f'Cannot connect to {host}:{port}. Friend must run lan42; check seat/network. {e}')
        with sock:
            sock.settimeout(None)
            client = Client(sock,username,socket.gethostname(),notify,role,initial_command,auth_session)
            client.peer_callback = peer_callback
            client.game_target = (host,port) if auth_session else game_target or (host,port)
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
        if peer_callback and (host, port) == home:
            try:
                peer_callback(host,port)
            except (OSError,RuntimeError,ValueError) as e:
                print(f'Peer unavailable: {e}. Returning to your node.')
                host,port = home

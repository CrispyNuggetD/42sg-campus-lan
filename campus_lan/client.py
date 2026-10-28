"""Curses frontend. Desktop notifications execute on this client only."""
import collections
import base64
import curses
import json
import os
import pwd
import queue
import random
import re
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
from .lobby_view import lobby_lines, guest_style, overlay_campus, roster, seat, LAYOUT
from .hexbot import SDK, compile_bot
from . import auth_client
from .updater import RestartRequested, generation
from .completion import complete
from .local_console import LocalConsole,History,shell_command
from .notification_preferences import NotificationControls,IMPORTANT
from .quiet_ui import QuietUI
from .web_search import SearchControls
from .quick_controls import QuickControls
from .permission_setup import PermissionSetup
from .announcement_ui import AnnouncementUI
from .forknite_controls import HELP as FORKNITE_HELP, summary as forknite_summary

HELP = [
    "/quiet status: LAN42-only exam audio mute | /exams: cached SG schedule | admin /quiet MINUTES | release popups: max once/24h",
    "/search TERMS: chosen engine in your browser | /settings search: engine + aggregate counting opt-out | /search stats",
    "/notify: channel preferences | /notify dms on | /notify host off | /notify all off: silence every desktop alert",
    "Click footer buttons or use F2 sign in/out | F3 system mute | F4 output 0/30% | F5 uwu | F6 auto uwu",
    '/changelog: server release history and alpha testing credits',
    'API views: verified Singapore sign-in; enrolled API operators may use local /clusters and /info offsite.',
    '/announce TEXT / /broadcast TEXT: host broadcasts; students request host approval | /announce status',
    'Up/Down: local command history | !COMMAND: local shell | /volume [0–100]: output volume',
    '/uwu: meet the koel file courier + local sound test | /uwu auto|on|off: local calls every 10–15 min | /uwu LOGIN: poke',
    '/about: project purpose + public source | /repo: request browser link | /roadmap files: file-sharing help',
    '/lobby or /who: roster | /map 1 or /map 2: seats | /next /prev: lobby pages',
    '/who /rooms /games | /game tetris | /game bluff free|prompt | /game hexwars | /game forknite',
    'Hex Wars: /bot (menu) | /bot upload PATH.c | /bot demo | /practice | /start',
    '/join (seat questions) | /join ROOM | /invite (friend seat) | /invite-room',
    '/start /leave | /answer TEXT | /vote USER1 USER2 ... | /connect IP [PORT]',
    '/tool LOGIN...: batch private photos | /info [FILTER] [PAGE]: API-operator campus directory',
    '/clusters [1|2]: campus seats | /locate LOGIN: highlight | /profile LOGIN...: browser tabs | /make: build philo',
    '/track help: relationships/lists | /settings clusters: include/exclude arrival rules',
    '/sabo friends | /dm friends "want lunch?" | /untrack LOGIN...|all | /alert LOGIN MESSAGE',
    '/setup or /allow batch: choose popup categories y/n | /allow all: approve the whole list',
    '/signin | /settings (profile, sign out, notifications) | /authhost SEAT | /notify on|off | /home | /help | /quit',
    '/game forknite: browser game room | /browser: reopen current FORKNITE website',
    '/koel flock once|always|never|ask: host-started 42SG flock | /koel flock-dir PATH: service root; local copies are kept',
    '/roadmap koeldrop | /koel help: campus file sharing; /koel create | /koel pending',
    '/update (or /upgrade): update package + reload local instances | /restart: reload installed code',
    'Chat: type and Enter. Tab completes /commands and games. PgUp/PgDn scroll. Tetris: Tab toggles play/chat.',
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

class SectionLog(collections.deque):
    """Append individual events separately; extend keeps a help/table block together."""
    def append(self, text):
        if self and self[-1]!='':super().append('')
        super().append(text)
    def extend(self, lines):
        lines=list(lines)
        if not lines:return
        if self and self[-1]!='':super().append('')
        for line in lines:super().append(line)

from .file_sharing.ui import KoelUI

class Client(QuietUI,SearchControls,NotificationControls,QuickControls,PermissionSetup,LocalConsole,AnnouncementUI,KoelUI):
    def __init__(self, sock, name, hostname, notify=True, role='lobby', initial_command=None, auth_session=None):
        from .popup_permissions import ensure_session
        ensure_session()
        self.uid = auth_session.get('uid') if auth_session else None
        self.secure = auth_session is not None
        self.signed_in = bool(auth_session and auth_session.get('uid'))
        self.remote_approved = False
        self.session_token = auth_session['session'] if auth_session else None
        self.signing_in = False
        self.auto_login_checked=False
        self.auth_destination = None
        self.sock, self.name = sock, name
        self.role, self.initial_command = role, initial_command
        self.requested_game=initial_command.split()[1] if initial_command and initial_command.startswith(('/host ','/game ')) else None
        self.inbox = queue.Queue(maxsize=256)
        from .release import banner
        self.lines = SectionLog([banner()]+HELP,maxlen=500)
        self.state, self.game = {}, {}
        self.input, self.scroll = '', 0
        self.play = False
        self.lobby_view, self.cluster, self.lobby_page = 'roster', 1, 0
        self.show_lobby = False
        self.colors = False
        self.connected = True
        self.notify_enabled, self.last_notice = notify, 0
        self.notifications_disabled = not notify
        self.id = None
        self.tracker=None
        self.track_next=0
        self.track_pending=0
        self.tracking_notifier=None
        self.wizard = None
        self.next_server = None
        hello = dict(type='hello',protocol=PROTOCOL,name=name,hostname=hostname,role=role)
        if auth_session:
            hello['session'] = auth_session['session']
        self.send(hello)
        threading.Thread(target=self.receive,daemon=True).start()

    def sound_tick(self):
        from .audio_quiet import active
        if active():return
        if getattr(self,'role','lobby')!='lobby' or not self.connected or not self.id or getattr(self,'sound_prompt_queued',False):return
        from .koel_sound import SoundChoice
        choice=SoundChoice(self.name)
        self.sound_prompt_queued=True
        if choice.read()['asked']:return
        def accept():choice.choose(True)
        self.popup_prompts().session_question('Enable the uwu bird? y=once, a=always, Enter=off',accept,
                                             lambda:choice.choose(False),lambda:not choice.read()['asked'],
                                             always=lambda:self.confirm_always_koel(choice))

    def confirm_always_koel(self,choice,after_accept=None):
        def accept():
            choice.set_always(True)
            self.lines.append('uwu has been given permanent residency. /settings koel-sound off evicts it.')
            if after_accept:after_accept()
        enabled_before=choice.read()['enabled']
        self.popup_prompts().session_question('Always uwu? Are you SURE? ಠ_ಠ [y/N]',accept,lambda:choice.choose(enabled_before))

    def uwu_auto_tick(self):
        due=getattr(self,'uwu_auto_due',None)
        if due is None or time.monotonic()<due:return
        from .koel_sound import SoundChoice,play
        if not SoundChoice(self.name).read()['enabled']:
            self.uwu_auto_due=None
            self.lines.append('Automatic uwu stopped: koel sound is off.')
            return
        self.uwu_auto_due=time.monotonic()+random.uniform(600,900)
        try:self.with_audio_volume(lambda:play() if SoundChoice(self.name).read()['enabled'] else None)
        except OSError as error:
            self.uwu_auto_due=None
            self.lines.append(str(error)+' Automatic uwu stopped.')

    def uwu_command(self,text):
        if text.strip() in ('/uwu auto','/uwu on','/uwu off'):
            if text.strip()=='/uwu off':
                self.uwu_auto_due=None
                self.lines.append('Automatic uwu off.')
                return True
            from .koel_sound import SoundChoice
            choice=SoundChoice(self.name)
            def start():
                if getattr(self,'uwu_auto_due',None) is None:
                    self.uwu_auto_due=time.monotonic()+random.uniform(600,900)
                self.lines.append('Automatic local uwu on: every 10–15 minutes until /uwu off or this window closes.')
            if choice.read()['enabled']:start()
            else:
                def accept():choice.choose(True);start()
                self.popup_prompts().session_question(
                    'Enable koel sound for automatic local uwu? y=once, a=always, Enter=off',accept,
                    lambda:choice.choose(False),lambda:not choice.read()['enabled'],
                    always=lambda:self.confirm_always_koel(choice,start))
            return True
        if text.startswith('/uwu '):
            target=text.split(maxsplit=1)[1].strip()
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',target):self.lines.append('Use /uwu LOGIN')
            else:self.send(dict(type='command',text='/uwu '+target))
            return True
        if text!='/uwu':return False
        if not getattr(self,'uwu_courier_introduced',False):
            self.lines.extend([
                'Meet the koel: the familiar "uwu" bird, and our Singapore take on a carrier pigeon.',
                'With KoelDrop, this bird delivers files! Try /koel, or /koel help to get started.',
                'File sharing needs a signed-in campus group and separate approval; this sound test sends no files.',
            ])
            self.uwu_courier_introduced=True
        from .koel_sound import SoundChoice,play
        choice=SoundChoice(self.name)
        def chirp():
            if not choice.read()['enabled']:return
            def emit():
                if choice.read()['enabled']:play();self.lines.append('uwu!')
            try:self.with_audio_volume(emit)
            except OSError as error:self.lines.append(str(error))
        if choice.read()['enabled']:
            chirp()
        else:
            self.sound_prompt_queued=True
            def accept():choice.choose(True);chirp()
            self.popup_prompts().session_question(
                'Enable koel sound and uwu? y=once, a=always, Enter=off',accept,
                lambda:choice.choose(False),lambda:not choice.read()['enabled'],
                always=lambda:self.confirm_always_koel(choice,chirp))
        return True

    def uwu_notice(self,sender):
        if not self.notification_allowed('pokes'):return
        def show():
            if not self.notification_allowed('pokes'):return False
            from .koel_sound import SoundChoice
            if not getattr(self,'tracking_notifier',None):
                from .desktop_notifications import Notifications
                self.tracking_notifier=Notifications(self.inbox)
            choice=SoundChoice(self.name)
            def notify():
                if not self.notification_allowed('pokes'):return
                self.tracking_notifier.poke(sender+' says uwu!', 'You have been poked.',sender,
                                            koel_sound=choice.read()['enabled'])
            if choice.read()['enabled']:self.with_audio_volume(notify)
            else:notify()
        self.request_popup('notifications','Show uwu poke from '+sender+'?',show)

    def auto_login_tick(self):
        if getattr(self,'auto_login_checked',False) or getattr(self,'role','lobby')!='lobby':return
        if not self.connected or not self.id:return
        self.auto_login_checked=True
        if getattr(self,'secure',False):
            self.offer_auto_login()
            return
        from .login_settings import LoginSettings,auto_login_paused
        if auto_login_paused():return
        settings=LoginSettings()
        if settings.error:self.lines.append(settings.error);return
        mode=settings.data['autologin']
        if mode!='off':self.start_signin(saved_only=mode=='saved')

    def offer_auto_login(self):
        from .login_settings import LoginSettings
        settings=LoginSettings()
        if settings.error:
            self.lines.append(settings.error)
            return
        if settings.data['autologin_asked'] or settings.data['autologin']!='off':return
        def choose(mode):
            # Read again: a queued prompt must not overwrite newer settings.
            current=LoginSettings()
            if current.data['autologin_asked'] or current.data['autologin']!='off':return
            current.set('autologin',mode)
            self.lines.append('Automatic sign-in '+('enabled. Reuse saved sessions; expired sessions still ask before opening 42.' if mode=='on' else 'off. Use /settings autologin on to enable it later.'))
        self.popup_prompts().confirm(
            'Sign in automatically next time? Reuse your saved session; if expired, ask to open 42 sign-in.',
            lambda:choose('on'),lambda:choose('off'))

    def popup_prompts(self):
        if not getattr(self,'consent',None):
            from .popup_permissions import Permissions,Prompts
            self.consent=Prompts(Permissions(self.name),self.lines.append)
        return self.consent

    def request_popup(self,category,description,action):
        self.popup_prompts().request(category,description,action)

    def permission_tick(self):
        if getattr(self,'wizard',None) and self.wizard[0].startswith('permissions-'):return
        prompts=getattr(self,'consent',None)
        if not prompts:return
        active=prompts.activate()
        if active and not getattr(self,'permission_prompt',False):
            self.permission_prompt=True
            self.permission_saved_input=self.input
            self.permission_saved_play=self.play
            self.input='';self.play=False

    def permission_answer(self,value):
        self.permission_prompt=False
        self.input=self.permission_saved_input;self.play=self.permission_saved_play
        self.popup_prompts().answer(value)

    def open_urls(self,category,urls,description):
        def launch():
            def work():
                import webbrowser
                opened=True
                for url in urls:
                    if self.popup_prompts().permissions.mode(category)=='deny':opened=False;break
                    try:opened=bool(webbrowser.open_new_tab(url)) and opened
                    except Exception:opened=False
                try:self.inbox.put_nowait(dict(type='popup_opened',category=category,opened=opened))
                except queue.Full:pass
            threading.Thread(target=work,daemon=True).start()
            return False  # Remember only after the browser reports launch success.
        self.request_popup(category,description,launch)

    def show_help(self):
        self.lines.extend(FORKNITE_HELP if self.game.get('game')=='forknite' else HELP)
        guide=Path(__file__).resolve().parents[1]/'docs/quick-guide.html'
        self.open_urls('help',[guide.as_uri()],'Open the LAN42 visual command guide in your browser?')

    def desktop_notice(self,title,body,name,icon='',can_message=False,category='tracking'):
        important=category in IMPORTANT
        allowed=lambda:self.important_notification_allowed(category) if important else self.notification_allowed(category)
        if not allowed():return
        def show():
            if not allowed():return False
            if not getattr(self,'tracking_notifier',None):
                from .desktop_notifications import Notifications
                self.tracking_notifier=Notifications(self.inbox)
            if important:self.tracking_notifier.announcement(title,body,name)
            else:self.tracking_notifier.show(title,body,name,icon,can_message)
        if important:show()
        else:self.request_popup('notifications','Show desktop notification: '+safe(title)+'?',show)

    def get_tracker(self):
        if not getattr(self,'tracker',None):
            from .tracking import Tracker
            self.tracker=Tracker(self.name)
            if self.tracker.load_error:self.lines.append(self.tracker.load_error)
            self.tracking_update(self.state.get('players',[]),'lobby')
        return self.tracker

    def tracking_command(self,text):
        parts=text.split()
        if not parts or parts[0] not in ('/track','/untrack','/compose'):return False
        if parts[0]=='/compose':
            if getattr(self,'pending_draft',None) and not self.input:
                self.input=self.pending_draft;self.pending_draft=None
            else:self.lines.append('No waiting draft, or finish the current input first.')
            return True
        if getattr(self,'role','lobby')!='lobby':
            self.lines.append('Use /track in your HQ window; tracking stays local to your login.')
            return True
        tracker=self.get_tracker()
        try:
            if parts[0]=='/track' and parts[1:] and any(value.isdecimal() for value in parts[1:]):
                if not all(value.isdecimal() for value in parts[1:]):raise ValueError('Use either /track NUMBERS or /track LOGINS, separately.')
                shown=getattr(self,'campus_selection',{})
                if not getattr(self,'cluster_source',False) or not shown:raise ValueError('Load /clusters first; numbers refer to its displayed online roster.')
                selected=[]
                for value in dict.fromkeys(parts[1:]):
                    entry=shown.get(int(value))
                    if not entry:raise ValueError('No online campus entry '+value+'. Refresh /clusters and check the displayed numbers.')
                    selected.append(entry)
                description=', '.join(name+' ('+'c%dr%ds%d'%location+')' for name,location in selected)
                def accept():
                    current={(p.get('name','').lower(),seat(p)) for p in getattr(self,'cluster_players',[])}
                    if any(entry not in current for entry in selected):
                        self.lines.append('Campus seats changed; refresh /clusters and select again. Nobody added.')
                        return
                    tracker.change([name for name,_ in selected])
                    self.track_next=0
                    self.lines.append('Added to tracking: '+', '.join(name for name,_ in selected))
                self.popup_prompts().confirm('Track these current occupants? '+description,accept)
                return True
            if parts[0]=='/untrack':
                names=tracker.names[:] if parts[1:]==['all'] else tracker.resolve(parts[1:])
                tracker.change(names,remove=True)
                self.lines.append('Removed from tracking: '+(', '.join(names) or 'nobody'))
            else:
                from .relationship_commands import configure
                self.lines.extend(configure(tracker,parts[1:]))
            self.track_next=0
            self.tracking_update(self.state.get('players',[]),'lobby')
        except (OSError,ValueError) as error:self.lines.append(safe(str(error)))
        return True

    def local_api_command(self, text):
        """Keyboard/local tracking path only; never dispatch this from wire messages."""
        command,_,argument=text.partition(' ')
        if command not in ('/clusters','/campus-presence','/info','/info_campus') or getattr(self,'secure',False):return False
        from .auth import config_dir
        if not (config_dir()/'local-operator.json').exists():return False
        from .access import Policy
        try:Policy().local_operator()
        except (OSError,ValueError):
            self.lines.append('Local API access denied; check approved-host/operator enrollment.')
            return True
        if getattr(self,'local_api_busy',False):return True
        if command=='/clusters' and argument not in ('','1','2'):
            self.lines.append('Use /clusters [1|2].');return True
        self.local_api_busy=True
        def work():
            try:
                Policy().local_operator()
                if command in ('/info','/info_campus'):
                    from .campus_info import info_lines
                    self.inbox.put(dict(type='event',text='\n'.join(info_lines(argument))))
                else:
                    from .clusters import snapshot
                    players,stamp=snapshot()
                    kind='clusters' if command=='/clusters' else 'campus_presence'
                    self.inbox.put(dict(type=kind,players=players,updated_at=stamp,cluster=int(argument or '1')))
            except (OSError,ValueError,KeyError,TypeError):
                self.inbox.put(dict(type='campus_presence',error='Local Singapore API view unavailable; check enrollment, credentials or API budget.'))
            finally:self.local_api_busy=False
        threading.Thread(target=work,daemon=True).start()
        return True

    def tracking_tick(self):
        if getattr(self,'role','lobby')!='lobby' or not self.connected or not self.id:return
        tracker=self.get_tracker()
        now=time.monotonic()
        if (not tracker.names and not tracker.rules_enabled) or now<getattr(self,'track_next',0):return
        if getattr(self,'track_pending',0) and now-self.track_pending<90:return
        from .tracking import INTERVAL
        self.track_next=now+INTERVAL;self.track_pending=now
        # No names/watch list cross the network; request the shared campus view.
        if not self.local_api_command('/campus-presence'):
            self.send(dict(type='command',text='/campus-presence'))

    def tracking_update(self,players,source):
        tracker=getattr(self,'tracker',None)
        if not tracker:return
        if not isinstance(players,list) or any(not isinstance(p,dict) or not isinstance(p.get('name'),str) for p in players):
            self.lines.append('Tracking snapshot unavailable; keeping the last known state.')
            return
        from .tracking import describe
        for notice in tracker.transitions(players,source):
            title,body=describe(notice)
            self.lines.extend([title,body])
            if not self.notification_allowed('tracking'):continue
            icon=''
            try:
                from .avatar_cache import AvatarCache,key
                cache=AvatarCache();cache.read(notice['login'])
                icon=str(cache.root/(key(notice['login'])+'.img'))
            except (OSError,ValueError):pass
            online=(source=='lobby' and 'offline' not in notice.get('changes',[])) or any(p.get('name','').lower()==notice['login'] for p in self.state.get('players',[]))
            self.desktop_notice(title,body,notice['login'],icon,online)

        error=getattr(tracker,'rules_error',None)
        if error and error!=getattr(self,'last_rule_error',None):self.lines.append('Cluster rules: '+error)
        self.last_rule_error=error

    def about_command(self,text):
        if text == '/changelog':
            from .release import changelog
            self.lines.extend(changelog())
            return True
        if text not in ('/about','/about repo','/repo'):return False
        from .about import lines,REPOSITORY
        self.lines.extend(lines())
        if text in ('/about repo','/repo'):
            self.open_urls('browser',[REPOSITORY],'Open the public LAN42 source repository in your browser?')
        return True

    def group_command(self,text):
        command=text.split(maxsplit=1)[0] if text else ''
        if command not in ('/sabo','/dm','/alert'):return False
        try:
            if command=='/sabo':parts=shlex.split(text)
            else:
                _,_,arguments=text.partition(' ')
                selector,separator,body=arguments.strip().partition(' ')
                message=' '.join(shlex.split(body)) if body.lstrip().startswith(('\"',"'")) else body.strip()
                parts=[command,selector,message] if separator else [command,selector]
            if len(parts)<2:return False
            # Re-read local settings so the game window sees HQ relationship edits.
            from .tracking import Tracker
            tracker=Tracker(self.name)
            if tracker.load_error:raise ValueError(tracker.load_error)
            if command=='/sabo':
                if not any(tracker.is_variable(p) for p in parts[1:]):return False
                names=tracker.resolve(parts[1:])
                if not names:raise ValueError('That local selector is empty. /track status friends LOGIN')
                if len(names)>50:raise ValueError('SABO selectors may expand to at most 50 people.')
                self.send(dict(type='command',text='/sabo '+' '.join(names)))
                self.lines.append('SABO selected locally: '+', '.join(names))
            else:
                if len(parts)<3:raise ValueError('Use /dm friends "do you all want lunch?" or /dm LOGIN MESSAGE')
                names=tracker.resolve([parts[1]])
                if not names:raise ValueError('That local selector is empty.')
                if len(names)>100:raise ValueError('Group DMs are limited to 100 recipients.')
                message=' '.join(parts[2:])
                if not message.strip() or len(message)>400:raise ValueError('Messages must contain 1–400 characters.')
                self.send(dict(type='direct_batch',targets=names,text=message))
                self.lines.append('Queued message to '+str(len(names))+' recipient(s): '+', '.join(names))
        except (OSError,ValueError) as error:self.lines.append(safe(str(error)))
        return True

    def notification_action(self,message):
        if self.flock_notification_action(message):return
        if self.announcement_action(message):return
        if message.get('action') in ('koel_accept','koel_decline'):
            self.koel_notification_action(message);return
        from .tracking import login
        try:name=login(message.get('login'))
        except ValueError:return
        if message.get('action')=='message':
            draft='/dm '+name+' '
            if self.input:
                self.pending_draft=draft
                self.lines.append('Message draft waiting for '+name+'. Finish your input, then /compose.')
            else:self.input=draft
            self.show_lobby=True;self.play=False
            self.lines.append('Write your message to '+name+' and press Enter to send.')
        elif message.get('action')=='profile':
            self.open_urls('profiles',['https://profile-v3.intra.42.fr/users/'+name],'Open the Intra profile for '+name+' in your browser?')

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
                    kind=msg.get('type')
                    if not isinstance(kind,str) or kind.startswith('local_') or kind in ('notification_action','popup_opened','signin_resume'):continue
                    self.inbox.put(msg,timeout=2)
        except (OSError,ValueError,queue.Full):
            pass
        finally:
            self.connected = False

    def notify(self,text,throttle=True):
        if not self.notification_allowed('chat'):return
        self.request_popup('notifications','Show desktop notification: '+safe(text)+'?',lambda:self._notify(text,throttle))

    def _notify(self,text,throttle=True):
        from .audio_quiet import active
        now = time.monotonic()
        if not self.notification_allowed('chat') or (throttle and now-self.last_notice<3):
            return
        self.last_notice = now
        if shutil.which('notify-send'):
            # Positional args only, never invoke a shell with received text.
            def show():
                try:
                    subprocess.run(['notify-send',*(['--hint=boolean:suppress-sound:true'] if active() else []),'--app-name=42SG LAN','--expire-time=7000',
                                    '--','42SG LAN',safe(text)],
                                   stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=3)
                except (OSError,subprocess.TimeoutExpired):
                    pass
            threading.Thread(target=show,daemon=True).start()
        else:
            try:
                if not active():curses.beep()
            except curses.error:
                pass

    def consume(self):
        while True:
            try:
                msg = self.inbox.get_nowait()
            except queue.Empty:
                break
            kind = msg.get('type')
            if self.search_result(msg):continue
            if self.announcement_event(msg):
                continue
            if kind == 'local_api_notice':
                self.lines.append(safe(msg.get('text','')))
            elif kind == 'local_koel':
                self.koel_local(msg)
            elif kind == 'koel_invite':
                self.koel_invitation(msg)
            elif kind == 'popup_opened':
                if msg.get('opened'):self.popup_prompts().remember(msg['category'])
                else:self.lines.append('Browser launch failed; no always-allow preference was saved.')
            elif kind == 'tools_required':
                names=msg.get('logins',[])
                from .tracking import login
                try:
                    if not isinstance(names,list) or len(names)>50:raise ValueError()
                    names=[login(n) for n in names]
                    self.open_admin(names)
                except ValueError:self.lines.append('Invalid photo-tool request ignored.')
            elif kind == 'notification_action':
                self.notification_action(msg)
            elif kind == 'campus_presence':
                self.track_pending=0
                if msg.get('error'):self.lines.append(safe(msg['error']))
                else:self.tracking_update(msg.get('players'),'campus')
            elif kind == 'dm_delivery':
                self.lines.append('DM '+('delivered to ' if msg.get('delivered') else 'not delivered to ')+safe(msg.get('target',''))+(': '+safe(msg['error']) if msg.get('error') else ''))
            elif kind == 'dm_summary':
                self.lines.extend(['Group DM: '+str(msg.get('delivered',0))+' delivered, '+str(msg.get('failed',0))+' unavailable.',
                                   'Unavailable: '+(', '.join(safe(n) for n in msg.get('unavailable',[])) or 'none')])
            elif kind == 'direct_message':
                sender=safe(msg.get('sender','unknown'))
                if msg.get('uwu') is True:
                    self.lines.append(sender+' poked you: uwu!')
                    if self.notification_allowed('pokes') and getattr(self,'role','lobby')=='lobby':self.uwu_notice(sender)
                    continue
                title='DM from '+sender+(' [42 Verified]' if self.secure and msg.get('verified') else ' [Guest]')
                self.lines.extend([title,safe(msg.get('text',''))])
                if self.notification_allowed('dms'):
                    from .tracking import login
                    try:
                        login(sender)
                        self.desktop_notice(title,safe(msg.get('text','')),sender,can_message=True,category='dms')
                    except ValueError:pass
            elif kind == 'signin_resume':
                self.signing_in=False
                if msg.get('destination'):
                    self.lines.append('Reused your saved LAN42 sign-in; no browser tab opened.')
                    self.auth_destination=tuple(msg['destination'])
                elif msg.get('saved_only'):
                    self.lines.append('No reusable LAN42 session. Staying in guest mode; /signin can authorize a new session.')
                else:self.request_popup('signin','Open 42 sign-in in your browser?',lambda:self.start_signin(True))
            elif kind == 'local_signin':
                self.signing_in = False
                if msg.get('error'):
                    self.lines.append(safe(msg['error']))
                else:
                    self.auth_destination = tuple(msg['destination'])
            elif kind == 'clusters':
                self.cluster_players=msg.get('players',[])
                self.cluster_stamp=msg.get('updated_at',0)
                self.cluster=msg.get('cluster',1)
                self.cluster_source=True
                self.lobby_view,self.lobby_page='map',0
                self.show_lobby,self.play=True,False
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
                self.lines.extend(safe(line) for line in str(msg.get('text','')).splitlines())
                if kind in ('invite','online'):
                    tracker=getattr(self,'tracker',None)
                    tracked=list(getattr(tracker,'names',[]))+list(getattr(tracker,'targets',{}).get('lobby',set()))
                    if kind!='online' or not any(msg.get('text','').lower().startswith(n+' ') for n in tracked):
                        self.notify(msg.get('text',''))
                elif kind=='event' and getattr(self,'role','lobby')=='lobby':
                    # Existing local and mesh chat events use this wire format.
                    delimiter = ' [42 Verified]: ' if getattr(self, 'secure', False) else ' [Guest]: '
                    sender,separator,_ = msg.get('text','').partition(delimiter)
                    if separator and sender!=self.name:
                        self.notify(msg['text'],throttle=False)
            elif kind=='browser_game':
                signature=(msg.get('room'),msg.get('url'))
                if msg.get('reopen') or signature != getattr(self,'browser_room',None):
                    self.browser_room=signature
                    import urllib.parse
                    parsed=urllib.parse.urlsplit(msg.get('url',''))
                    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
                        self.lines.append('Invalid FORKNITE browser URL from room.')
                        continue
                    url=msg['url']+'/#lan42='+urllib.parse.quote(msg['ticket'])
                    self.open_urls('forknite',[url],'Open this FORKNITE room in your browser?')
                    self.lines.append('FORKNITE: '+msg['url']+' | /browser reopens this room. Host uses /start here.')
            elif kind=='welcome':
                self.signed_in=bool(getattr(self,'secure',False) and msg.get('verified'))
                self.remote_approved=bool(getattr(self,'secure',False) and msg.get('remote_approved'))
                self.id = msg['id']
                if getattr(self, 'secure', False):
                    self.name = msg['name']
                if getattr(self,'initial_command',None):
                    self.send(dict(type='command',text=self.initial_command))
                    self.initial_command = None
                self.lines.append(f"Connected. Server {msg['version']}; " + ('Remote approved; ' if self.remote_approved else '')+('42 signed in over TLS.' if self.signed_in else 'Guest (unverified).'))
            elif kind=='state':
                old_rooms = {(r.get('address'),r.get('port'),r['id']) for r in self.state.get('rooms',[])}
                if not getattr(self, 'secure', False):
                    for player in msg.get('players', []):
                        player['verified'] = False
                self.state = msg
                self.tracking_update(msg.get('players',[]),'lobby')
                for room in msg.get('rooms',[]):
                    if (room.get('address'),room.get('port'),room['id']) not in old_rooms:
                        self.lines.append(f"Game {room['name']} hosted by {room['host']}: /connect {room.get('address')} {room.get('port')}, then /join {room['id']}")

            elif kind=='forknite_status':
                self.game['forknite']=msg['status']
            elif kind=='game':
                new = msg.get('room') != self.game.get('room')
                if new:
                    self.show_lobby = False
                    if msg.get('game')=='forknite':self.lines.extend(FORKNITE_HELP)
                self.game = msg
                if msg.get('game'):self.requested_game=msg['game']
                if not msg.get('game'):
                    self.browser_room = None
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

    def open_game(self, text, approved=False):
        parts = text.split()
        if parts[0] in ('/host','/game'):
            if len(parts) not in (2,3) or parts[1] not in ('tetris','bluff','hexwars','forknite') or (len(parts)==3 and parts[2] not in ('free','prompt')):
                self.lines.append('Use /game tetris, /game bluff free|prompt, /game hexwars, or /game forknite.')
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
        if getattr(self,'remote_approved',False):args.append('--remote-guest')
        opener = Path(__file__).resolve().parents[1]/'useful-scripts/open_terminal.py'
        if not approved:
            self.request_popup('terminals','Open a LAN42 game terminal?',lambda:self.open_game(text,True))
            return False
        try:
            result = subprocess.run([sys.executable,str(opener),*args],capture_output=True,text=True,timeout=10)
            if result.returncode:
                raise RuntimeError(result.stderr.strip() or result.stdout.strip())
            self.lines.append('Requested a game terminal. Your HQ stays online here.')
            return True
        except (OSError,RuntimeError,subprocess.TimeoutExpired) as exc:
            self.lines.append('Could not open game window: '+str(exc))
            self.lines.append('Open another terminal and run: '+shlex.join(['sh',str(opener.parents[1]/'lan42.sh'),*args]))
            return False

    def focus_player(self, player):
        location=seat(player)
        if not location:
            self.lines.append('No reported seat for '+player.get('name','unknown'))
            return
        self.focus_location=location
        self.focus_name=player.get('name','')
        self.cluster=location[0]
        self.lobby_view,self.lobby_page='map',0
        self.focus_pending=True
        self.show_lobby,self.play=True,False

    def lobby_command(self, text):
        if text in ('/lobby','/who','/roster'):
            self.focus_name=None
            self.focus_location=None
            self.cluster_source=False
            self.lobby_view, self.lobby_page = 'roster', 0
            self.show_lobby, self.play = True, False
        elif text in ('/map','/map 1','/map 2'):
            self.focus_name=None
            self.focus_location=None
            self.cluster_source=False
            self.lobby_view, self.lobby_page = 'map', 0
            if text != '/map':
                self.cluster = int(text[-1])
            self.show_lobby, self.play = True, False
        elif text.startswith('/locate '):
            name=text.split(maxsplit=1)[1].lower()
            players=getattr(self,'cluster_players',[]) if getattr(self,'cluster_source',False) else self.state.get('players',[])
            player=next((p for p in players if p.get('name','').lower()==name),None)
            if player:self.focus_player(player)
            else:self.lines.append('Login absent from this view. Load /clusters first.')
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
        campus=getattr(self,'cluster_source',False)
        if campus:players=overlay_campus(getattr(self,'cluster_players',[]),players)
        content = lobby_lines(players,getattr(self,'lobby_view','roster'),getattr(self,'cluster',1))
        if campus:
            content[-1]=[('API seat snapshot; unmarked desks have no active reported login. /clusters refreshes.',0)]
        capacity = min(max(1,h-13),max(10,len(content)))
        pages = max(1,(len(content)+capacity-1)//capacity)
        if getattr(self,'focus_pending',False):
            location=self.focus_location
            row_index=list(LAYOUT[self.cluster]).index(location[1]) if location[1] in LAYOUT[self.cluster] else 0
            self.lobby_page=(2+row_index*2+(location[2]%2))//capacity
            self.focus_pending=False
        self.lobby_page = min(getattr(self,'lobby_page',0),pages-1)
        self.lobby_hits=[]
        ordered={n:p for n,p,_ in roster(players)}
        self.campus_selection={n:(p.get('name','').lower(),location) for n,p,location in roster(players) if location} if campus else {}
        if campus:
            heading='CAMPUS API: '+str(len(players))+' logged-in seats | snapshot '+time.strftime('%H:%M:%S',time.localtime(self.cluster_stamp))
        else:
            heading=f"CURRENTLY ONLINE: {len(players)} | " + ('TLS lobby: sign-in and remote approval are separate' if getattr(self, 'secure', False) else 'Guest names are unverified')
        self.line(screen,3,heading,curses.A_BOLD)
        controls=f'/clusters 1|2 | Tab: map/roster | /next /prev | page {self.lobby_page+1}/{pages}'
        if getattr(self,'focus_name',None):controls='SELECTED '+self.focus_name+' | c%dr%ds%d'%self.focus_location+' | /next /prev'
        self.line(screen,4,controls)
        for y,segments in enumerate(content[self.lobby_page*capacity:(self.lobby_page+1)*capacity],5):
            x = 0
            for text,style in segments:
                attr = curses.A_BOLD if style else 0
                if style and getattr(self,'colors',False):
                    attr |= curses.color_pair(style)
                match=re.match(r'\s*(\d+)\. ',text)
                player=ordered.get(int(match[1])) if match else None
                marker=re.fullmatch(r'\[(?:#)?(\d+)\]',text)
                if marker and style:player=ordered.get(int(marker[1]))
                if player:
                    self.lobby_hits.append((y,x,x+len(text),player))
                    if seat(player)==getattr(self,'focus_location',None) and int(time.monotonic()*2)%2==0:
                        attr|=curses.A_REVERSE|curses.A_BOLD
                self.line(screen,y,text,attr,x)
                x += len(text)
        bottom = 5+capacity
        self.line(screen,bottom,'-'*(w-1),curses.A_DIM)
        self.line(screen,bottom+1,'CHAT & INVITATIONS | /game hexwars | /game forknite | /rooms',curses.A_BOLD)
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
        if os.environ.get('TMUX_PANE') and shutil.which('tmux'):
            game=self.game.get('game') or getattr(self,'requested_game',None)
            label=(str(game)+'-'+str(self.game.get('room','waiting'))) if game else ('lan42' if getattr(self,'role','lobby')=='lobby' else 'game-waiting')
            label=''.join(c for c in label if c.isalnum() or c in '-_')[:64]
            if label!=getattr(self,'last_tmux_label',None):
                subprocess.run(['tmux','rename-window','-t',os.environ['TMUX_PANE'],label],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=2)
                self.last_tmux_label=label
        if title!=getattr(self,'last_title',None) and sys.stdout.isatty():
            sys.stdout.write('\033]0;'+title+'\007')
            sys.stdout.flush()
            self.last_title = title

    def draw_permission_prompt(self,screen):
        if not getattr(self,'permission_prompt',False):return
        h,w=screen.getmaxyx()
        category,description,action,stage=self.popup_prompts().active
        rows=textwrap.wrap(description,max(10,w-2)) or ['']
        rows=rows[:max(1,h-5)]
        for y,part in enumerate(rows,h-2-len(rows)):
            self.line(screen,y,part.ljust(w-1),curses.A_BOLD|curses.A_REVERSE)
        self.line(screen,h-2,('y=once, a=always, Enter=off | /settings koel-sound off' if stage=='session' and getattr(action,'always_action',None) else '[y/N] Enter = no | /settings koel-sound off' if stage=='session' else '[y/N] Enter = no' if stage=='decision' else '[y/N] Enter = no | always-allow comes next | /settings permissions browser allow'))

    def draw(self,screen):
        screen.erase()
        self.control_hits=[]
        self.lobby_hits=[]
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
        label = f" LAN42 | {self.window_label()} | {self.name} [{'42 signed in' if getattr(self,'signed_in',getattr(self,'secure',False)) else 'Guest'}] | "+('ONLINE' if self.connected else 'DISCONNECTED')
        self.line(screen,0,label.ljust(w-1),banner)
        hint = ('GAME CONTROLS: /start /leave /quit | /lobby /game | HQ stays in its other window'
                if game_window else 'HQ: /join IP [PORT] | /game NAME | /games | /who')
        self.line(screen,1,hint)
        players = self.state.get('players',[])
        if not self.state:
            self.line(screen,2,'Connecting; waiting for presence...')
            self.line(screen,3,'Loading online roster...' if self.connected else 'Connection failed; see details below. /restart retries.')
            for y,message in enumerate(list(getattr(self,'lines',[]))[-min(8,h-7):],5):
                self.line(screen,y,message)
            self.draw_quick_controls(screen)
            self.draw_permission_prompt(screen)
            self.line(screen,h-1,('[y/N] > ' if getattr(self,'permission_prompt',False) else '> ')+getattr(self,'input','')[-(w-12):])
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
        elif game.get('game')=='forknite':
            status=game.get('forknite')
            self.line(screen,4,forknite_summary(status) if status else 'FORKNITE | waiting for status',curses.A_BOLD)
            self.line(screen,5,'HOST: /start /stop | /status | /help | stop before changing settings')
            self.line(screen,6,'/timings DIE EAT SLEEP | /storm on|off | /storm step MS | /storm pause MS')
            self.line(screen,7,'/meals N | /preset chill|chaos | /sabo LOGIN... | /admin (owner photos)')
            self.line(screen,8,'Defaults: 600/100/100ms, 3 meals, deadline -25ms per round, gap 2000ms')
            logs_y=10
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
        self.draw_quick_controls(screen)
        self.draw_permission_prompt(screen)
        self.line(screen,h-1,('[y/N] > ' if getattr(self,'permission_prompt',False) else 'PLAY > ' if self.play else '> ')+self.input[-(w-12):])
        screen.refresh()

    def open_admin(self, logins=(), approved=False, photos_approved=False):
        if not approved:
            self.request_popup('tools','Open the local photo-tool terminal and browser panel?',lambda:self.open_admin(logins,True,photos_approved))
            return False
        if logins and not photos_approved:
            self.request_popup('photos','Allow photo tabs and extension saves for this batch of '+str(len(logins))+' logins?',lambda:self.open_admin(logins,True,True))
            return False
        try:
            from .auth import private_read, config_dir
            private_read(config_dir()/'auth-server.json')
            opener=Path(__file__).resolve().parents[1]/'useful-scripts/open_terminal.py'
            result=subprocess.run([sys.executable,str(opener),'admin','--approved','--owner',self.name,*(['--photos-approved'] if photos_approved else []),*logins],capture_output=True,text=True,timeout=10)
            if result.returncode:raise RuntimeError()
            self.lines.append('Local avatar admin opened. Photos stay in the private master cache.')
            self.popup_prompts().remember('tools')
            return True
        except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired):
            self.lines.append('Avatar admin is local to the API owner computer; run sh lan42.sh admin there.')
            return False

    def settings_command(self, text):
        if self.quiet_command(text):return True
        if self.search_command(text):return True
        if self.notification_command(text):return True
        if self.host_settings_command(text):return True
        parts = text.split()
        if not parts or parts[0] not in ('/settings','/profile'):
            return False
        if len(parts)==1 and parts[0]=='/profile':
            self.open_urls('profiles',['https://profile-v3.intra.42.fr/'],'Open your personal Intra home in your browser?')
        elif len(parts) == 1:
            signed = getattr(self,'signed_in',getattr(self,'secure',False))
            self.lines.extend([
                'SETTINGS | '+self.name+(' | signed in with 42' if signed else ' | guest'),
                '/settings signin  — open 42 sign-in (local HQ)',
                '/settings signout — end the LAN42 session on this device',
                '/notify — notification channels; /notify all off — silence everything',
                '/settings search — Ecosia/Google/custom; permanent aggregate impact counter and opt-out',
                '/volume [0–100] — desktop output; /settings audio-auto-on on|off — uwu unmute',
                '/settings host-discovery on|off | auto-host-join on|off | host-poll 60–300',
                '/settings permissions — browser, popup and notification consent',
                '/settings autologin off|saved|on — reuse login, optionally request OAuth',
                '/settings signin-close on|off — try to close the completed sign-in tab',
                '/koel help — file sharing; /koel leave — stop group uploads',
                '/settings clusters — separate include/exclude arrival rules; /track help — relationships/lists',
                'Sign-in sessions expire automatically after one hour.',
            ])
        elif parts[0]=='/settings' and parts[1]=='koel-sound':
            from .koel_sound import SoundChoice
            choice=SoundChoice(self.name)
            try:
                if len(parts)>2:
                    if len(parts)!=3 or parts[2] not in ('on','off','always'):raise ValueError('Use /settings koel-sound on|off|always')
                    if parts[2]=='always':self.confirm_always_koel(choice)
                    else:choice.set_always(False);choice.choose(parts[2]=='on')
                self.lines.append('Koel sound: '+('always on' if choice.always_on() else 'on for this session' if choice.read()['enabled'] else 'off')+'. Sound does not enable file sharing.')
            except (OSError,ValueError) as error:self.lines.append(str(error))
        elif parts[0]=='/settings' and parts[1] in ('experimental','files','koel','koeldrop'):
            self.lines.append('KoelDrop is a standard feature; no experimental switch is needed. /koel help | /koel leave stops group uploads.')
        elif parts[0]=='/settings' and parts[1] in ('autologin','signin-close'):
            from .login_settings import LoginSettings
            settings=LoginSettings()
            try:
                key='autologin' if parts[1]=='autologin' else 'close_tab'
                if len(parts)>2:
                    if len(parts)!=3:raise ValueError('Use /settings autologin off|saved|on or /settings signin-close on|off')
                    value=parts[2]
                    if key=='close_tab':
                        if value not in ('on','off'):raise ValueError('Use /settings signin-close on|off')
                        value=value=='on'
                    settings.set(key,value)
                    if key=='autologin':self.auto_login_checked=parts[2]=='off'
                self.lines.extend(['Auto-login: '+settings.data['autologin']+' · close sign-in tab: '+('on' if settings.data['close_tab'] else 'off'),
                                   'saved: reuse an unexpired session without browser; on: request browser sign-in if reuse fails; off: manual.',
                                   'Tab closing is best effort; browser rules may require you to close the sign-in tab yourself.'])
            except (OSError,ValueError) as error:self.lines.append(str(error))
        elif parts[0]=='/settings' and parts[1]=='permissions':
            from .popup_permissions import CATEGORIES
            settings=self.popup_prompts().permissions
            try:
                if len(parts)>2:
                    if len(parts)!=4:raise ValueError('Use /settings permissions CATEGORY ask|allow|deny|inherit')
                    settings.set(parts[2],parts[3])
                self.lines.extend(['Popup permissions (local): '+', '.join(settings.summary(k) for k in CATEGORIES),
                                   '/settings permissions CATEGORY ask|allow|deny|inherit · browser controls browser categories; all controls everything',
                                   'Browser categories inherit browser unless explicitly overridden; browser deny blocks all browser launches.',
                                   'Allow once: y at the first prompt, then Enter at Always allow. Enter always means no.'])
            except (OSError,ValueError) as error:self.lines.append(str(error))
        elif parts[0]=='/settings' and parts[1]=='clusters':
            self.tracking_command('/track clusters '+' '.join(parts[2:]))
        elif parts[0]=='/profile' and parts[1] not in ('signin','signout','notifications'):
            try:
                from .profile_browser import resolve
                urls=resolve(parts[1:])
                self.open_urls('profiles',urls,'Open '+str(len(urls))+' Intra profile tab(s) in your browser?')
            except ValueError as error:self.lines.append(str(error))
        elif parts[1:] == ['signin']:
            self.start_signin()
        elif parts[1:] == ['signout']:
            from .login_settings import pause_for_session
            pause_for_session()
            if getattr(self,'signed_in',getattr(self,'secure',False)):
                self.send(dict(type='command',text='/signout'))
            else:
                self.lines.append('Already a guest. Use /signin to sign in.')
        else:
            self.lines.append('Use /settings, /settings signin, /settings signout, or /settings notifications on|off.')
        return True

    def start_signin(self, approved=False,saved_only=False):
        if getattr(self,'signed_in',getattr(self,'secure',False)):
            self.lines.append('Already signed in with 42. /settings signout ends this session.')
            return
        if self.role != 'lobby' or self.current != self.home:
            self.lines.append('Use /signin in your local HQ window.')
            return
        if self.signing_in:
            self.lines.append('Sign-in is already waiting in your browser (five-minute limit).')
            return
        if not approved:
            self.signing_in=True
            self.lines.append('Checking for a reusable LAN42 sign-in…')
            def resume():
                try:destination=auth_client.resume_session()
                except (OSError,ValueError):destination=None
                try:self.inbox.put(dict(type='signin_resume',destination=destination,saved_only=saved_only),timeout=2)
                except queue.Full:self.signing_in=False
            threading.Thread(target=resume,daemon=True).start()
            return False
        self.signing_in = True
        self.lines.append("Opening 42 in your browser. Enter credentials only on 42's website.")
        def authenticate():
            try:
                def browser(url):
                    import webbrowser
                    opened=bool(webbrowser.open(url))
                    self.inbox.put(dict(type='popup_opened',category='signin',opened=opened),timeout=2)
                    return opened
                from .login_settings import LoginSettings
                destination = auth_client.sign_in(self.home,open_browser=browser,close_tab=LoginSettings().data['close_tab'])
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
        return False

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
            self.lines.append('Open /game hexwars or join a Hex Wars room first.')
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
        if intent.startswith('permissions-'):
            self.permission_setup_answer(text)
            return
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
        history=History()
        installed_generation = generation()
        screen.timeout(80)
        try:
            curses.mousemask(curses.BUTTON1_CLICKED|curses.BUTTON1_RELEASED)
            curses.mouseinterval(150)
        except curses.error:pass
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
            if generation() != installed_generation:
                raise RestartRequested()
            self.consume()
            self.tracking_tick()
            self.announcement_tick()
            self.quiet_tick()
            self.uwu_auto_tick()
            self.permission_tick()
            self.auto_login_tick()
            self.sound_tick()
            if self.auth_destination and not getattr(self,'permission_prompt',False):
                return self.auth_destination
            self.update_title()
            if not self.connected and self.home != self.current:
                return self.home
            self.draw(screen)
            key = screen.getch()
            if key in (curses.KEY_RESIZE,12):
                screen.clearok(True)
                continue
            if key==curses.KEY_MOUSE:
                try:
                    _,mouse_x,mouse_y,_,buttons=curses.getmouse()
                    if buttons&(curses.BUTTON1_CLICKED|curses.BUTTON1_RELEASED):
                        if self.quick_click(mouse_x,mouse_y):continue
                        if getattr(self,'permission_prompt',False) or getattr(self,'wizard',None):continue
                        for y,left,right,player in getattr(self,'lobby_hits',[]):
                            if mouse_y==y and left<=mouse_x<right:self.focus_player(player);break
                except curses.error:pass
                continue
            if self.quick_key(key):continue
            if key==21:
                self.input='';self.play=False
                continue
            if key in (3,4):
                break
            if key==curses.KEY_PPAGE:
                self.scroll += 8
            elif key==curses.KEY_NPAGE:
                self.scroll = max(0,self.scroll-8)
            elif key==9 and self.input.startswith('/') and not self.wizard:
                self.input, matches = complete(self.input)
                if len(matches)>1:
                    self.lines.append('Complete: '+'  '.join(matches))
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
            elif key in (curses.KEY_UP,curses.KEY_DOWN) and not getattr(self,'permission_prompt',False) and not self.wizard:
                self.input=history.move(-1 if key==curses.KEY_UP else 1,self.input)
            elif key in (10,13):
                text,self.input = self.input.strip(),''
                self.scroll = 0
                if text=='/restart':raise RestartRequested()
                if self.permission_setup_command(text):continue
                if getattr(self,'permission_prompt',False):
                    self.permission_answer(text)
                    continue
                if not self.wizard:
                    try:history.add(text)
                    except (OSError,ValueError):self.lines.append('Could not save local command history.')
                if not self.wizard and text.startswith('!'):
                    if text[1:].strip():shell_command(screen,text[1:].strip())
                    continue
                if not self.wizard and self.volume_command(text):continue
                if not self.wizard and self.search_command(text):continue
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
                elif text=='/forknite' or text.startswith('/forknite '):
                    self.open_game('/game forknite')
                elif text.startswith('/game ') or (getattr(self,'role','lobby')=='lobby' and (text.startswith('/host ') or text.startswith('/join '))):
                    self.open_game(text)
                elif self.announcement_command(text):
                    pass
                elif self.uwu_command(text):
                    pass
                elif self.about_command(text):
                    pass
                elif self.koel_command(text):
                    pass
                elif self.group_command(text):
                    pass
                elif self.tracking_command(text):
                    pass
                elif self.local_api_command(text):
                    pass
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
                elif text in ('/update','/upgrade','/restart'):
                    raise RestartRequested(update=text!='/restart')
                elif text=='/quit':
                    break
                elif text == '/make':
                    try:
                        from .forknite import ensure_binary
                        self.lines.append('Building configured philo; please wait.')
                        ensure_binary()
                        self.lines.append('philo ready. Host FORKNITE to open the browser.')
                    except (OSError,ValueError,subprocess.SubprocessError) as error:
                        self.lines.append('Build failed: '+str(error))
                elif text.split()[0] in ('/admin','/tool','/tools'):
                    self.open_admin(text.split()[1:])
                elif self.settings_command(text):
                    pass
                elif text == '/signin':
                    self.start_signin()
                elif text.startswith('/authhost '):
                    if getattr(self,'signed_in',getattr(self,'secure',False)) or self.signing_in:
                        self.lines.append('Sign out or finish the pending sign-in before changing the auth host.')
                    else:
                        try:
                            host = auth_client.change_host(text.split(maxsplit=1)[1])
                            self.lines.append(f'Trusted sign-in host verified at {host}. Use /signin.')
                        except (OSError, ValueError):
                            self.lines.append('Could not verify the trusted host at that seat. Settings unchanged.')
                elif text == '/signout':
                    from .login_settings import pause_for_session
                    pause_for_session()
                    if getattr(self, 'secure', False):
                        self.send(dict(type='command', text='/signout'))
                    else:
                        self.lines.append('You are using the guest lobby. /signin opens 42 sign-in.')
                elif text == '/bot' or text.startswith('/bot '):
                    self.bot_command(text)
                elif text=='/help':
                    self.show_help()
                elif text.split()[:1]==['/notify']:
                    self.notification_command(text)
                elif text:
                    if self.connected:
                        self.send(dict(type='command',text=text))
                    else:
                        self.lines.append('Disconnected. /quit and reconnect using lan42 join HOST.')
            elif key in (127,8,curses.KEY_BACKSPACE):
                self.input = self.input[:-1]
            elif 32<=key<=126 and len(self.input)<400:
                self.input += chr(key)

def connect(host,port,name=None,notify=True,peer_callback=None,home=None,role='lobby',initial_command=None,game_target=None,remote_guest=False):
    username = name or pwd.getpwuid(os.getuid()).pw_name
    if request_terminal_resize():
        # Window managers apply the request asynchronously; give curses a moment
        # to observe the new dimensions. Unsupported terminals safely ignore it.
        time.sleep(.15)
    flock_choice=None
    while True:
        print(f'Connecting to {host}:{port}...')
        try:
            sock, auth_session = auth_client.connect_socket(host, port,remote_guest=True) if remote_guest else auth_client.connect_socket(host, port)
        except (OSError, ValueError) as e:
            if home and (host,port)!=home:
                print(f'Peer unavailable; returning to your node. {e}')
                host,port = home
                continue
            raise OSError(f'Cannot connect to {host}:{port}. Friend must run lan42; check seat/network. {e}')
        with sock:
            sock.settimeout(None)
            client = Client(sock,username,socket.gethostname(),notify,role,initial_command,auth_session)
            client.pending_flock_choice=flock_choice
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
                from .api_pacing import ui_notices
                with ui_notices(lambda text:client.inbox.put_nowait(dict(type='local_api_notice',text=text))):
                    destination = curses.wrapper(client.run)
                    flock_choice=getattr(client,'pending_flock_choice',None)
            finally:
                if getattr(client,'courier',None):client.courier.stop()
                if getattr(client,'host_watch',None):client.host_watch.close()
                if client.tracking_notifier:client.tracking_notifier.close()
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
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

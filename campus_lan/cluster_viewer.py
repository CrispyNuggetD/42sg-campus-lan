"""Dedicated read-only cluster window; HQ keeps its chat and game state."""
import curses
import json
import os
import pwd
import queue
import re
import signal
import socket
import threading
import time

from . import PROTOCOL,auth_client
from .access import Policy
from .api_pacing import ui_notices
from .cluster_commands import normalize_cluster_command
from .lobby_view import lobby_lines,overlay_campus,relationship_overlay,roster,seat
from .updater import RestartRequested,generation


def age_label(stamp,now=None):
    if not isinstance(stamp,(int,float)) or stamp<=0:return 'no snapshot yet'
    age=max(0,int((time.time() if now is None else now)-stamp))
    value=f'{age}s ago' if age<60 else f'{age//60}m {age%60}s ago'
    return 'stale · '+value if age>120 else value


class HostSource:
    label='Pinned host API'

    def __init__(self,events,owner):
        trust=auth_client.load_trust()
        host,port=auth_client.endpoint(trust)
        self.sock,session=auth_client.connect_socket(host,port)
        if not session or not session.get('uid'):
            self.sock.close()
            raise ValueError('Sign in from HQ before opening campus clusters.')
        self.events=events
        self.lock=threading.Lock()
        self.sock.sendall((json.dumps(dict(type='hello',protocol=PROTOCOL,name=owner,
                                          hostname=socket.gethostname(),role='clusters',session=session['session']))+'\n').encode())
        self.sock.settimeout(5)
        self.stream=self.sock.makefile('rb')
        try:
            first=json.loads(self.stream.readline(65537))
            if first.get('type')!='welcome':raise ValueError(str(first.get('text','Cluster host rejected this window.')))
        except (OSError,ValueError,AttributeError):
            self.stream.close();self.sock.close()
            raise
        self.sock.settimeout(None)
        threading.Thread(target=self.receive,daemon=True).start()

    def receive(self):
        try:
            with self.stream:
                while True:
                    raw=self.stream.readline(65537)
                    if not raw:break
                    if len(raw)>65536:raise ValueError('Cluster response too large.')
                    message=json.loads(raw)
                    if isinstance(message,dict) and message.get('type') in ('welcome','clusters','error','event','signed_out'):
                        self.events.put(message)
        except (OSError,ValueError) as error:
            self.events.put(dict(type='error',text=str(error)))
        finally:self.events.put(dict(type='closed'))

    def refresh(self,cluster):
        message=json.dumps(dict(type='command',text='/clusters'+(' '+str(cluster) if cluster else '')))+'\n'
        with self.lock:self.sock.sendall(message.encode())

    def close(self):
        try:self.sock.shutdown(socket.SHUT_RDWR)
        except OSError:pass
        self.sock.close()


class LocalSource:
    label='Local approved API'

    def __init__(self,events):
        Policy().local_operator()
        self.events=events
        self.busy=False

    def refresh(self,cluster):
        if self.busy:return
        self.busy=True
        def work():
            try:
                Policy().local_operator()
                from .clusters import snapshot
                players,stamp=snapshot()
                self.events.put(dict(type='clusters',players=players,updated_at=stamp,cluster=cluster))
            except (OSError,ValueError,KeyError,TypeError):
                self.events.put(dict(type='error',text='Local Singapore API seats unavailable. Retry later.'))
            finally:self.busy=False
        threading.Thread(target=work,daemon=True).start()

    def close(self):pass


def source_for(events,owner):
    try:return HostSource(events,owner)
    except (OSError,ValueError) as host_error:
        try:return LocalSource(events)
        except (OSError,ValueError):raise host_error


class ClusterViewer:
    def __init__(self,source,events,cluster=0,owner=None):
        self.source,self.events=source,events
        self.cluster=cluster
        self.view='map'
        self.page=0
        self.players=[]
        self.stamp=0
        self.status='Loading campus seats from '+source.label+'…'
        self.input=''
        self.connected=True
        self.last_request=0
        self.owner=owner
        self.pending_track=None
        self.tracker_data={}
        if owner:
            try:
                from .tracking import Tracker
                self.tracker_data=Tracker(owner).data
            except (OSError,ValueError):pass

    def refresh(self):
        try:
            self.source.refresh(self.cluster)
            self.last_request=time.monotonic()
            self.status='Refreshing from '+self.source.label+'; host cache lasts 30s and API requests may queue.'
        except OSError as error:self.status='Refresh failed: '+str(error)

    def consume(self):
        while True:
            try:message=self.events.get_nowait()
            except queue.Empty:return
            kind=message.get('type')
            if kind=='clusters':
                players=message.get('players')
                stamp=message.get('updated_at')
                if not isinstance(players,list) or not isinstance(stamp,(int,float)) or stamp<=0:
                    self.status='Invalid cluster snapshot; keeping the last view.';continue
                self.players=players
                self.stamp=stamp
                self.page=0
                self.status='Loaded '+str(len(players))+' campus seats from '+self.source.label+'. Press r or Enter to refresh.'
            elif kind=='error':self.status='Campus seats unavailable: '+str(message.get('text','Unknown error'))[:180]
            elif kind=='event' and not str(message.get('text','')).startswith('Loading campus API seats'):
                self.status=str(message.get('text',''))[:180]
            elif kind=='local_api_notice':self.status=str(message.get('text',''))[:180]
            elif kind=='signed_out':self.status='Sign-in expired. Renew it in HQ, then reopen clusters.'
            elif kind=='closed':
                self.connected=False
                if not self.status.startswith(('Campus seats unavailable','Sign-in expired')):
                    self.status='Host connection closed. Last snapshot remains visible; reopen from HQ to refresh.'

    def segments(self):
        players=relationship_overlay(overlay_campus(self.players,[]),self.tracker_data)
        return lobby_lines(players,self.view,self.cluster)

    def rows(self):
        return [''.join(text for text,_ in row) for row in self.segments()]

    def heading(self,now=None):
        return f'LAN42 CLUSTERS | {self.source.label} | {len(self.players)} seats | snapshot {age_label(self.stamp,now)}'

    def command(self,text):
        text=text.strip()
        if self.pending_track is not None:
            selected=self.pending_track;self.pending_track=None
            if text.lower() in ('y','yes'):
                current={(player.get('name','').lower(),seat(player)) for player in self.players}
                if any(item not in current for item in selected):
                    self.status='Campus seats changed. Refresh and select again; nobody was added.'
                else:
                    try:
                        from .tracking import Tracker
                        tracker=Tracker(self.owner)
                        tracker.change([name for name,_ in selected])
                        self.tracker_data=tracker.data
                        self.status='Added to tracking: '+', '.join(name for name,_ in selected)
                    except (OSError,ValueError) as error:self.status=str(error)[:180]
                return True
            if text.lower() in ('','n','no'):
                self.status='Tracking cancelled.';return True
        if text in ('/quit','q'):return False
        if text in ('','r','/refresh'):
            self.refresh();return True
        normalized=normalize_cluster_command(text)
        if normalized in ('/clusters','/clusters 1','/clusters 2'):
            self.cluster=int(normalized[-1]) if normalized[-1] in '12' else 0
            self.view='map';self.page=0;self.refresh();return True
        if text in ('/next','n'):
            self.page+=1;return True
        if text in ('/prev','p'):
            self.page=max(0,self.page-1);return True
        if text in ('/map','/roster'):
            self.view=text[1:];self.page=0;return True
        if text.startswith('/track '):
            numbers=text.split()[1:]
            if not numbers or any(not number.isdecimal() for number in numbers):
                self.status='Use /track NUMBERS here, or /track LOGINS in HQ.';return True
            shown={number:(player.get('name','').lower(),location) for number,player,location in roster(self.players) if location}
            selected=[]
            for value in dict.fromkeys(numbers):
                item=shown.get(int(value))
                if not item:
                    self.status='No campus entry '+value+' in this snapshot. Refresh and check the displayed numbers.';return True
                selected.append(item)
            self.pending_track=selected
            self.status='Track current occupants '+', '.join(f'{name} (c{loc[0]}r{loc[1]}s{loc[2]})' for name,loc in selected)+'? Type y Enter to confirm; Enter cancels.'
            return True
        if text.startswith('/locate '):
            login=text.split(maxsplit=1)[1].strip().lower()
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',login):
                self.status='Use /locate LOGIN.';return True
            entry=next((player for player in self.players if player.get('name','').lower()==login),None)
            location=seat(entry) if entry else None
            if location:
                self.cluster=location[0];self.view='roster';self.page=0
                self.status=f'{login} is at c{location[0]}r{location[1]}s{location[2]} · snapshot {age_label(self.stamp)}.'
            else:self.status='Login absent from this snapshot. Press r to refresh.'
            return True
        self.status='Use /clusters [1|2], /c1, /c2, r, /map, /roster, /next, /prev, /locate LOGIN, /track NUMBERS or /quit.'
        return True

    def run(self,screen):
        screen.timeout(250)
        colors=False
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1,curses.COLOR_GREEN,curses.COLOR_BLACK)
            for pair,color in enumerate((curses.COLOR_CYAN,curses.COLOR_YELLOW,curses.COLOR_MAGENTA,
                                         curses.COLOR_BLUE,curses.COLOR_RED,curses.COLOR_WHITE),2):
                curses.init_pair(pair,color,curses.COLOR_BLACK)
            colors=True
        installed=generation()
        self.refresh()
        while True:
            if generation()!=installed:raise RestartRequested()
            if getattr(self,'refresh_requested',None) and self.refresh_requested.is_set():
                self.refresh_requested.clear();self.refresh()
            self.consume()
            screen.erase()
            height,width=screen.getmaxyx()
            def line(y,value):
                if y<height:screen.addnstr(y,0,value,max(1,width-1))
            line(0,self.heading())
            line(1,'r/Enter refresh from host · /clusters both · /c1 /c2 · Tab map/roster · PgUp/PgDn · q quit')
            line(2,self.status)
            content=self.segments() if self.stamp else [[('Waiting for the first campus snapshot…',0)]]
            capacity=max(1,height-5)
            pages=max(1,(len(content)+capacity-1)//capacity)
            self.page=min(self.page,pages-1)
            for index,segments in enumerate(content[self.page*capacity:(self.page+1)*capacity],3):
                x=0
                for value,style in segments:
                    if x>=width-1:break
                    try:screen.addnstr(index,x,value,width-1-x,curses.color_pair(style) if colors and style else 0)
                    except curses.error:pass
                    x+=len(value)
            line(height-2,f'{self.view} · page {self.page+1}/{pages} · {self.source.label} · {age_label(self.stamp)}')
            line(height-1,'> '+self.input)
            screen.refresh()
            key=screen.getch()
            if key in (3,4):return
            if key==ord('q') and not self.input:return
            if key==ord('r') and not self.input:self.refresh();continue
            if key in (curses.KEY_F0+3,):self.refresh()
            elif key==9:self.view='roster' if self.view=='map' else 'map';self.page=0
            elif key==curses.KEY_NPAGE:self.page+=1
            elif key==curses.KEY_PPAGE:self.page=max(0,self.page-1)
            elif key in (10,13):
                command=self.input;self.input=''
                if not self.command(command):return
            elif key in (127,8,curses.KEY_BACKSPACE):self.input=self.input[:-1]
            elif 32<=key<=126 and len(self.input)<100:self.input+=chr(key)


def launch(cluster=0):
    events=queue.Queue()
    owner=pwd.getpwuid(os.getuid()).pw_name
    source=source_for(events,owner)
    viewer=ClusterViewer(source,events,cluster,owner)
    viewer.refresh_requested=threading.Event()
    signal.signal(signal.SIGUSR1,lambda *_:viewer.refresh_requested.set())
    try:
        with ui_notices(lambda text:events.put_nowait(dict(type='local_api_notice',text=text))):
            curses.wrapper(viewer.run)
    finally:source.close()

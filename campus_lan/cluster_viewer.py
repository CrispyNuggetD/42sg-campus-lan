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
import textwrap

from . import PROTOCOL,auth_client
from .access import Policy
from .api_pacing import ui_notices
from .cluster_commands import normalize_cluster_command
from .lobby_view import lobby_lines,overlay_campus,relationship_overlay,roster,seat
from .updater import RestartRequested,generation
from .numbered_occupants import ProfileCommands


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
        self.owner=session.get('login',owner)
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
        uid=Policy().local_operator()
        self.owner='hnah' if uid==234449 else None
        self.events=events
        self.busy=False

    def refresh(self,cluster):
        if self.busy:return False
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
        return True

    def close(self):pass


def source_for(events,owner):
    try:return HostSource(events,owner)
    except (OSError,ValueError) as host_error:
        try:return LocalSource(events)
        except (OSError,ValueError):raise host_error


class ClusterViewer(ProfileCommands):
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
        self.pending_profile_decision=None
        self.focus_location=None
        self.hits=[]
        self.session_hint_pending=False
        self.session_hint_shown=False
        self.tracker_data={}
        if owner:
            try:
                from .tracking import Tracker
                self.tracker_data=Tracker(owner).data
            except (OSError,ValueError):pass

    def refresh(self):
        try:
            if self.source.refresh(self.cluster) is False:
                self.status='Refresh already in progress; waiting for the campus snapshot.'
                return
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
                unchanged=stamp==self.stamp and self.stamp>0
                self.players=players
                self.stamp=stamp
                pending=getattr(self,'pending_number_action',None)
                self.pending_number_action=None
                if pending:
                    pending()
                    continue
                if unchanged:
                    self.status='No newer campus snapshot yet; showing cached seats ('+age_label(stamp)+'). The host cache lasts 30s.'
                else:
                    self.page=0
                    self.status='Loaded '+str(len(players))+' campus seats from '+self.source.label+'. Press r or Enter to refresh.'
            elif kind=='error':self.status='Campus seats unavailable: '+str(message.get('text','Unknown error'))[:180]
            elif kind=='event' and not str(message.get('text','')).startswith('Loading campus API seats'):
                self.status=str(message.get('text',''))[:180]
            elif kind=='local_profile_notice':self.status=str(message.get('text',''))[:300]
            elif kind=='local_api_notice':self.status=str(message.get('text',''))[:180]
            elif kind=='signed_out':self.status='Sign-in expired. Renew it in HQ, then reopen clusters.'
            elif kind=='closed':
                self.connected=False
                if not self.status.startswith(('Campus seats unavailable','Sign-in expired')):
                    self.status='Host connection closed. Last snapshot remains visible; reopen from HQ to refresh.'

    def segments(self):
        players=relationship_overlay(overlay_campus(self.players,[]),self.tracker_data,self.owner,getattr(self,'cohorts',{}))
        return lobby_lines(players,self.view,self.cluster)

    def rows(self):
        return [''.join(text for text,_ in row) for row in self.segments()]

    def heading(self,now=None):
        return f'LAN42 CLUSTERS | {self.source.label} | {len(self.players)} seats | snapshot {age_label(self.stamp,now)}'

    def number_players(self):return self.players if self.stamp else None

    def report_profile(self,text):
        self.session_hint_pending=False
        self.status=text

    def load_number_roster(self,callback):
        self.pending_number_action=callback
        self.refresh()

    def confirm_profile(self,description,accept,decline):
        self.session_hint_pending=False
        self.pending_profile_decision=(description,accept,decline)
        self.status=description

    def popup_prompts(self):
        if not getattr(self,'consent',None):
            from .popup_permissions import Permissions,Prompts
            self.consent=Prompts(Permissions(self.owner),self.report_profile)
        return self.consent

    def open_urls(self,category,urls,description):
        def launch():
            def work():
                import webbrowser
                opened=True
                for url in urls:
                    if self.popup_prompts().permissions.mode(category)=='deny':opened=False;break
                    try:opened=bool(webbrowser.open_new_tab(url)) and opened
                    except Exception:opened=False
                self.events.put(dict(type='local_profile_notice',text='Profile opened.' if opened else 'Browser could not open the profile; check your browser locally.'))
            threading.Thread(target=work,daemon=True).start()
            return False
        self.popup_prompts().request(category,description,launch)
        active=self.popup_prompts().activate()
        if active:self.status=active[1]+' [y/N]'

    def click(self,x,y,double=False):
        if self.pending_profile_decision or getattr(getattr(self,'consent',None),'active',None):return False
        for row,left,right,members in self.hits:
            if row==y and left<=x<right:
                self.session_hint_pending=False
                identity=tuple(sorted((player.get('name','').lower(),seat(player)) for player in members))
                previous=getattr(self,'last_click',None)
                now=time.monotonic()
                self.last_click=(x,y,identity,now)
                if double and previous and previous[:2]==(x,y) and now-previous[3]<0.8 and previous[2]!=identity:
                    self.report_profile('Campus occupant or map position changed; select again.')
                    return True
                self.focus_location=seat(members[0])
                self.status='Selected '+', '.join(str(next((n for n,p,_ in roster(self.players) if p.get('name')==player.get('name') and seat(p)==seat(player)),'?'))+' = '+player.get('name','') for player in members)+' at c%dr%ds%d'%self.focus_location
                if double:
                    if len(members)!=1:
                        self.report_profile('Shared seat: double-click an individual roster entry, or use /profile NUMBER to choose a student.')
                    else:
                        player=members[0]
                        name=player.get('name','').lower()
                        if not any(p.get('name','').lower()==name and seat(p)==seat(player) for p in self.players):
                            self.report_profile('Campus occupant changed; select again.')
                        else:
                            try:
                                from .profile_browser import resolve
                                urls=resolve([name],literal_logins=[name])
                                self.open_urls('profiles',urls,'Open the Intra profile for '+name+' in your browser?')
                            except (OSError,ValueError) as error:self.report_profile(str(error))
                return True
        return False

    def command(self,text):
        text=text.strip()
        if self.session_hint_pending:
            self.session_hint_pending=False
            if not text and not self.pending_profile_decision and not getattr(getattr(self,'consent',None),'active',None):
                self.status='Double-click opens a student profile; single-click highlights their seat.'
                return True
        if getattr(self,'confirmation_truncated',False) and text.lower() in ('y','yes'):
            self.status='Confirmation does not fit. Resize the terminal or cancel and select fewer people.'
            return True
        if self.pending_profile_decision:
            _,accept,decline=self.pending_profile_decision
            self.pending_profile_decision=None
            if text.lower() in ('y','yes'):accept();return True
            decline()
            if text.lower() in ('','n','no'):return True
        prompts=getattr(self,'consent',None)
        if prompts and prompts.active:
            prompts.answer(text)
            active=prompts.activate()
            if active:self.status=active[1]+' [y/N]'
            return True
        if text.isdecimal():text='/profile '+text
        if self.profile_command(text):return True
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
            def track(names):
                try:
                    from .tracking import Tracker
                    tracker=Tracker(self.owner)
                    tracker.change(names)
                    self.tracker_data=tracker.data
                    self.status='Added to tracking: '+', '.join(names)
                except (OSError,ValueError) as error:self.status=str(error)[:180]
            self.confirm_occupants(numbers,track)
            return True
        if text.startswith('/locate '):
            target=text.split(maxsplit=1)[1].strip()
            if target.isdecimal():
                self.confirm_occupants([target],lambda names:self.command('/locate '+names[0]))
                return True
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
        self.status='Use /clusters [1|2], /c1, /c2, r, /map, /roster, /next, /prev, /locate LOGIN, /track NUMBERS, /profile LOGIN|NUMBER or /quit.'
        return True

    def run(self,screen):
        from .cohort_display import cohort_index
        self.cohorts=cohort_index()
        screen.timeout(250)
        try:
            curses.mousemask(curses.BUTTON1_CLICKED|curses.BUTTON1_RELEASED|curses.BUTTON1_DOUBLE_CLICKED)
            curses.mouseinterval(250)
        except curses.error:pass
        colors=False
        if curses.has_colors():
            curses.start_color()
            curses.init_pair(1,curses.COLOR_GREEN,curses.COLOR_BLACK)
            for pair,color in enumerate((curses.COLOR_CYAN,curses.COLOR_YELLOW,curses.COLOR_MAGENTA,
                                         curses.COLOR_BLUE,curses.COLOR_RED,curses.COLOR_WHITE),2):
                curses.init_pair(pair,color,curses.COLOR_BLACK)
            from .lobby_view import init_cluster_colors
            init_cluster_colors(curses)
            colors=True
        installed=generation()
        self.refresh()
        if not self.session_hint_shown:
            self.session_hint_shown=True
            self.session_hint_pending=True
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
            decision=self.pending_profile_decision
            active=getattr(getattr(self,'consent',None),'active',None)
            description=decision[0] if decision else active[1]+' [y/N]' if active else (
                'Tip: double-click an occupied seat or roster entry to open its Intra profile; single-click highlights. Browser permission still applies. Enter dismisses.'
                if self.session_hint_pending else self.status)
            wrapped=textwrap.wrap(description,max(1,width-1)) or ['']
            max_notice=max(1,height-6)
            self.confirmation_truncated=len(wrapped)>max_notice
            notice_rows=min(len(wrapped),max_notice)
            notice_start=max(2,height-1-notice_rows)
            for y,value in enumerate(wrapped[:max_notice],notice_start):line(y,value)
            content_start=2
            if self.confirmation_truncated:line(height-2,'Resize or cancel and select fewer occupants; confirmation disabled.')
            content=self.segments() if self.stamp else [[('Waiting for the first campus snapshot…',0)]]
            capacity=max(1,notice_start-content_start-1)
            pages=max(1,(len(content)+capacity-1)//capacity)
            self.page=min(self.page,pages-1)
            from .lobby_view import occupant_hits
            start=self.page*capacity
            self.hits=[(row-start+content_start,left,right,members) for row,left,right,members in occupant_hits(self.players,self.view,self.cluster)
                       if start<=row<start+capacity]
            for index,segments in enumerate(content[start:start+capacity],content_start):
                x=0
                for value,style in segments:
                    if x>=width-1:break
                    attr=curses.color_pair(style) if colors and style else 0
                    if any(row==index and left<x+len(value) and x<right and any(seat(player)==self.focus_location for player in members)
                           for row,left,right,members in self.hits):attr|=curses.A_REVERSE|curses.A_BOLD
                    try:screen.addnstr(index,x,value,width-1-x,attr)
                    except curses.error:pass
                    x+=len(value)
            line(notice_start-1,f'{self.view} · page {self.page+1}/{pages} · {self.source.label} · {age_label(self.stamp)}')
            line(height-1,'> '+self.input)
            screen.refresh()
            key=screen.getch()
            if key==curses.KEY_MOUSE:
                try:
                    _,x,y,_,buttons=curses.getmouse()
                    if buttons&(curses.BUTTON1_CLICKED|curses.BUTTON1_RELEASED|curses.BUTTON1_DOUBLE_CLICKED):
                        self.click(x,y,double=bool(buttons&curses.BUTTON1_DOUBLE_CLICKED))
                except curses.error:pass
                continue
            if key in (3,4):return
            if key==ord('q') and not self.input:return
            if key==ord('r') and not self.input and not self.pending_profile_decision and not active:
                self.session_hint_pending=False;self.refresh();continue
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
    identity=getattr(source,'owner',None)
    viewer=ClusterViewer(source,events,cluster,identity if isinstance(identity,str) else owner)
    viewer.refresh_requested=threading.Event()
    signal.signal(signal.SIGUSR1,lambda *_:viewer.refresh_requested.set())
    try:
        with ui_notices(lambda text:events.put_nowait(dict(type='local_api_notice',text=text))):
            curses.wrapper(viewer.run)
    finally:source.close()

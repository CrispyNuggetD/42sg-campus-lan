"""Typed local commands; never invoked by server messages."""
import curses
import hashlib
import socket
import json
import os
import subprocess
from .auth import config_dir,private_read,private_write


def local_path(name):
    machine=hashlib.sha256(socket.gethostname().encode()).hexdigest()[:16]
    return config_dir()/(name+'-'+machine+'.json')


class History:
    def __init__(self):
        self.path=local_path('command-history')
        try:
            data=json.loads(private_read(self.path))
            self.items=[x for x in data if isinstance(x,str) and len(x)<=400][-200:] if isinstance(data,list) else []
        except (OSError,ValueError):self.items=[]
        self.index=len(self.items);self.draft=''

    def add(self,text):
        if text and (not self.items or self.items[-1]!=text):
            self.items.append(text);self.items=self.items[-200:]
            while len(json.dumps(self.items).encode())>60000:self.items.pop(0)
            private_write(self.path,json.dumps(self.items))
        self.index=len(self.items);self.draft=''

    def move(self,delta,current):
        if self.index==len(self.items):self.draft=current
        self.index=max(0,min(len(self.items),self.index+delta))
        return self.draft if self.index==len(self.items) else self.items[self.index]


def shell_command(screen,command):
    """Use the real terminal for stdin/output, then restore curses even on errors."""
    curses.def_prog_mode();curses.endwin()
    try:
        env=dict(os.environ,LOGIN_STARTUP_SKIP='1')
        subprocess.call([os.environ.get('SHELL') or '/bin/sh','-ic',command],env=env)
    except KeyboardInterrupt:pass
    except OSError as error:print(error)
    finally:
        try:input('\nPress Enter to return to LAN42…')
        except (EOFError,KeyboardInterrupt):pass
        curses.reset_prog_mode();screen.clear();screen.refresh()


class LocalConsole:
    def with_audio_volume(self,action):
        from .volume import Volume
        try:
            volume=Volume()
            level=volume.get()
        except (OSError,ValueError):
            # Unknown volume never implies permission to change it.
            action();return
        if level!=0:action();return
        try:settings=json.loads(private_read(local_path('audio-volume')))
        except (OSError,ValueError):settings={}
        def enable():
            try:volume.set(50);action();return True
            except (OSError,ValueError) as error:self.lines.append(str(error));return False
        if isinstance(settings,dict) and settings.get('auto_on') is True:enable();return
        if getattr(self,'audio_volume_pending',False):return
        self.audio_volume_pending=True
        def decline():self.audio_volume_pending=False
        def accept():
            self.audio_volume_pending=False
            if not enable():return
            if isinstance(settings,dict) and settings.get('asked') is True:return
            def always():
                private_write(local_path('audio-volume'),json.dumps({'auto_on':True,'asked':True}))
                self.lines.append('Automatic unmute to 50% enabled. /settings audio-auto-on off disables it.')
            self.popup_prompts().confirm('Always raise muted output to 50% for uwu on this device?',always,
                lambda:private_write(local_path('audio-volume'),json.dumps({'auto_on':False,'asked':True})))
        self.popup_prompts().confirm('Output is muted or at 0%. Raise it to 50% for uwu?',accept,decline)

    def volume_command(self,text):
        parts=text.split()
        if parts[:2]==['/settings','audio-auto-on']:
            if len(parts)!=3 or parts[2] not in ('on','off'):
                self.lines.append('Use /settings audio-auto-on on|off');return True
            try:
                private_write(local_path('audio-volume'),json.dumps({'auto_on':parts[2]=='on','asked':True}))
                self.lines.append('Automatic uwu unmute '+parts[2]+'.')
            except (OSError,ValueError) as error:self.lines.append(str(error))
            return True
        if not parts or parts[0] not in ('/volume','/adjust_volume'):return False
        try:
            if len(parts)>2:raise ValueError('Use /volume [0–100].')
            from .volume import Volume
            level=Volume().adjust(int(parts[1]) if len(parts)==2 else None)
            self.lines.append('Output volume: '+str(level)+'%')
        except (OSError,ValueError) as error:self.lines.append(str(error))
        return True

"""Local popup consent. Empty answers deny; remote events never grant consent."""
from collections import deque
import hashlib
import json
import os
import re
import secrets
import atexit
from .auth import config_dir,private_read,private_write

BROWSER_CATEGORIES={'search','help','forknite','profiles','signin','tools','photos'}
CATEGORIES=('browser','help','forknite','profiles','signin','tools','photos','notifications','terminals','search')
MODES=('ask','allow','deny')


def ensure_session():
    """Share once grants with app-opened game/tool windows, not later launches."""
    if re.fullmatch(r'[a-f0-9]{32}',os.environ.get('LAN42_POPUP_SESSION','')) and session_alive():return
    token=secrets.token_hex(16)
    os.environ['LAN42_POPUP_SESSION']=token
    os.environ['LAN42_POPUP_OWNER_PID']=str(os.getpid())
    def cleanup():
        for path in config_dir().glob('.popup-session-'+token+'-*.json'):
            try:path.unlink()
            except OSError:pass
    atexit.register(cleanup)


def session_alive():
    try:
        pid=int(os.environ.get('LAN42_POPUP_OWNER_PID','0'))
        if pid<=0:return False
        os.kill(pid,0);return True
    except (ValueError,OSError):return False


class Permissions:
    def __init__(self,owner):
        self.owner=owner
        self.path=config_dir()/('popup-permissions-'+hashlib.sha256(owner.lower().encode()).hexdigest()+'.json')
        self.policies={};self.error=None;self.once=set()
        self.reload()

    def reload(self):
        self.policies={};self.error=None
        try:
            data=json.loads(private_read(self.path))
            if not isinstance(data,dict) or any(k not in CATEGORIES or v not in MODES for k,v in data.items()):raise ValueError()
            self.policies=data
        except FileNotFoundError:pass
        except (OSError,ValueError):self.error='Popup settings could not be read; popups remain blocked until the private file is repaired.'

    def scope(self,category):
        self.reload()
        return 'browser' if category in BROWSER_CATEGORIES and category not in self.policies else category

    def persistent_mode(self,category):
        if category not in CATEGORIES:raise ValueError('Unknown popup category.')
        self.reload()
        if self.error:return 'deny'
        if category in BROWSER_CATEGORIES:
            browser=self.policies.get('browser','ask')
            if browser=='deny':return 'deny'
            return self.policies.get(category,browser)
        return self.policies.get(category,'ask')

    def session_path(self):
        token=os.environ.get('LAN42_POPUP_SESSION','')
        if not re.fullmatch(r'[a-f0-9]{32}',token) or not session_alive():return None
        owner=hashlib.sha256(self.owner.lower().encode()).hexdigest()
        return config_dir()/('.popup-session-'+token+'-'+owner+'.json')

    def session_granted(self):
        path=self.session_path()
        if path:
            try:return json.loads(private_read(path)).get('browser') is True
            except (OSError,ValueError,AttributeError):return False
        return 'browser' in self.once

    def always_offered(self):
        path=self.session_path()
        if not path:return False
        try:return json.loads(private_read(path)).get('always_offered') is True
        except (OSError,ValueError,AttributeError):return False

    def mark_always_offered(self):
        path=self.session_path()
        if path:
            try:data=json.loads(private_read(path))
            except (OSError,ValueError):data={}
            data['always_offered']=True;private_write(path,json.dumps(data))

    def grant_once(self,category):
        if self.scope(category)!='browser':return
        path=self.session_path()
        if path:private_write(path,json.dumps(dict(browser=True)))
        else:self.once.add('browser')

    def revoke_once(self):
        self.once.discard('browser')
        path=self.session_path()
        if path:path.unlink(missing_ok=True)

    def mode(self,category):
        persistent=self.persistent_mode(category)
        if persistent=='ask' and self.scope(category)=='browser' and self.session_granted():return 'allow'
        return persistent

    def summary(self,category):
        effective=self.mode(category)
        configured=self.policies.get(category,'inherit' if category in BROWSER_CATEGORIES else 'ask')
        if category=='browser' and configured=='ask' and effective=='allow':return 'browser=ask (allowed this session)'
        return category+'='+configured+' (effective '+effective+')'

    def set(self,category,mode):
        self.reload()
        if self.error:raise ValueError(self.error)
        if category not in (*CATEGORIES,'all') or mode not in (*MODES,'inherit'):raise ValueError('Use /settings permissions CATEGORY ask|allow|deny|inherit')
        candidate=dict(self.policies)
        for key in CATEGORIES if category=='all' else (category,):
            if mode=='inherit':candidate.pop(key,None)
            else:candidate[key]=mode
        private_write(self.path,json.dumps(candidate));self.policies=candidate
        if category in ('browser','all') and mode!='allow':self.revoke_once()


class Prompts:
    def __init__(self,permissions,report):
        self.permissions=permissions;self.report=report;self.pending=deque();self.active=None;self.offered_always=set()

    def request(self,category,description,action):
        mode=self.permissions.mode(category)
        if mode=='allow':action();return
        if mode=='deny':self.report(description+' blocked. /settings permissions '+category+' ask');return
        if self.active and self.active[1].endswith(description):return
        # Keep the latest unsolicited notification; terminal history retains every event.
        if category=='notifications':self.pending=deque(p for p in self.pending if p[0]!=category)
        if len(self.pending)>=20:self.report('Popup queue full; action skipped.');return
        scope=self.permissions.scope(category)
        if scope=='browser':description='Allow browser pages for this LAN42 session? '+description
        def guarded():
            if self.permissions.mode(category)=='deny':self.report('Popup blocked by current settings.');return False
            return action()
        guarded.popup_category=category
        self.pending.append((scope,description,guarded,'once'))

    def session_question(self,description,accept,decline,needed=lambda:True,always=None):
        # A running-joke sound choice cannot inherit persistent allow or offer always-on.
        accept.decline=decline;accept.needed=needed;accept.always_action=always
        self.pending.append(('notifications',description,accept,'session'))

    def confirm(self,description,accept,decline=lambda:None):
        # File/group consent never inherits permission to display a popup.
        if len(self.pending)>=20:self.report('Confirmation queue full; action skipped.');return
        accept.decline=decline
        self.pending.append(('notifications',description,accept,'decision'))

    def remember(self,category):
        category=self.permissions.scope(category)
        if self.permissions.persistent_mode(category)!='ask':return
        if category=='browser':
            if self.permissions.always_offered() or category in self.offered_always:return
        elif category in self.offered_always:return
        if any(p[0]==category and p[3]=='always' for p in self.pending):return
        self.offered_always.add(category)
        if category=='browser':self.permissions.mark_always_offered()
        self.pending.append((category,'Always allow '+category+' popups on this account?',None,'always'))

    def activate(self):
        while not self.active and self.pending:
            item=self.pending.popleft();category,description,action,stage=item
            action_category=getattr(action,'popup_category',category) if action else category
            mode=self.permissions.mode(action_category)
            if stage=='session' and not getattr(action,'needed',lambda:True)():continue
            if stage=='once':item=(self.permissions.scope(action_category),description,action,stage)
            if stage=='always' and self.permissions.persistent_mode(category)!='ask':continue
            if stage=='once' and mode=='deny':continue
            if stage=='once' and mode=='allow':
                action();continue
            self.active=item
        return self.active

    def answer(self,value):
        if not self.active:return
        category,description,action,stage=self.active;self.active=None
        yes=value.strip().lower() in ('y','yes')
        if stage=='decision':
            try:action() if yes else action.decline()
            except (OSError,ValueError):self.report('Action could not be completed.')
        elif stage=='session':
            try:
                if value.strip().lower() in ('a','always') and getattr(action,'always_action',None):action.always_action()
                elif yes:action()
                else:action.decline()
            except (OSError,ValueError):self.report('Sound choice could not be saved; sound remains off.')
            self.report('Koel sound controls: /settings koel-sound on|off|always. Always-on needs its own confirmation.')
        elif stage=='always':
            if yes:
                try:self.permissions.set(category,'allow');self.report('Always allowed: '+category+'. /settings permissions '+category+' ask resets it.')
                except (OSError,ValueError):self.report('Could not save popup settings; future actions will still ask.')
            else:self.report(('Browser allowed for this LAN42 session only.' if category=='browser' else 'Allow once only; future '+category+' popups will ask.')+' /settings permissions '+category+' allow makes it permanent.')
        elif yes:
            # Re-check a queued action if preferences changed while it was waiting.
            action_category=getattr(action,'popup_category',category)
            if self.permissions.mode(action_category)=='deny':self.report(description+' blocked by current settings.');return
            try:
                self.permissions.grant_once(action_category)
                if action() is not False:self.remember(action_category)
            except (OSError,ValueError):self.report('Popup action failed; always-allow was not saved.')
        else:self.report(description+' skipped. /settings permissions '+category+' ask keeps asking.')


def console_permission(owner,category,description):
    settings=Permissions(owner);mode=settings.mode(category)
    if mode=='allow':return True
    if mode=='deny':return False
    try:
        approved=input(('Allow browser pages for this LAN42 session? ' if settings.scope(category)=='browser' else '')+description+' [y/N] ').strip().lower() in ('y','yes')
        if approved:settings.grant_once(category)
        return approved
    except (EOFError,KeyboardInterrupt):return False


def console_remember(owner,category):
    settings=Permissions(owner)
    category=settings.scope(category)
    if settings.persistent_mode(category)!='ask':return
    try:yes=input('Always allow '+category+' popups? [y/N] ').strip().lower() in ('y','yes')
    except (EOFError,KeyboardInterrupt):yes=False
    if yes:settings.set(category,'allow')
    print('Change later: /settings permissions '+category+' ask|allow|deny')

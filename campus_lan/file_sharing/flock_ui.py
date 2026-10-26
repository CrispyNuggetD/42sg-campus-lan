"""Local consent for the host's public campus flock, discovered only through pinned TLS."""
import re
import os
from pathlib import Path
import secrets
from .security import Denied
from .flock import FlockPreferences, LABEL


class FlockUI:
    def flock_preferences(self):
        from .. import auth_client
        fingerprint=auth_client.fingerprint(auth_client.load_trust())
        uid=getattr(self,'uid',0) if getattr(self,'secure',False) else 0
        return FlockPreferences(fingerprint,uid)

    def flock_status(self,data):
        if getattr(self,'role','lobby')!='lobby':return
        info=data.get('flock') if isinstance(data,dict) else None
        if info is not None:
            if (not isinstance(info,dict) or info.get('scope')!='42-singapore' or info.get('campus_id')!=64
                    or not all(isinstance(info.get(k),str) and re.fullmatch('[a-f0-9]{32}',info[k]) for k in ('group','epoch'))
                    or not isinstance(info.get('host'),str) or not re.fullmatch('[a-z0-9_.-]{1,24}',info['host'])):return
        previous=getattr(self,'flock_info',None)
        self.flock_info=info
        worker=getattr(self,'courier',None)
        public_worker=worker and (getattr(worker,'flock_epoch',None) or getattr(worker,'join_pending',None)=='flock')
        requested_epoch=getattr(worker,'flock_epoch',None) or getattr(self,'flock_attempt',None)
        if public_worker and (not info or requested_epoch!=info['epoch']):
            worker.stop();self.courier=None;self.koel_offers={};self.flock_attempt=None
            self.lines.append('42 Singapore flock paused: host unavailable or session changed. Uploads stopped; your local folder and downloads are kept. Same-day reconnects reuse your daily folder (SGT).')
        if not info:
            self.flock_seen=None;self.flock_attempt=None
            return
        from ..auth_daily import current_seat
        try:current_seat()
        except (OSError,ValueError):return
        try:preferences=self.flock_preferences()
        except (OSError,ValueError):return
        if preferences.mode=='never':return
        pending=getattr(self,'pending_flock_choice',None)
        if pending and getattr(self,'secure',False) and pending.get('epoch')==info['epoch'] and pending.get('fingerprint')==preferences.fingerprint:
            self.pending_flock_choice=None
            try:self.flock_join(pending['mode'])
            except (OSError,ValueError) as error:self.lines.append('KoelDrop: '+str(error))
            return
        if preferences.mode=='always' and getattr(self,'secure',False):
            if getattr(self,'flock_attempt',None)!=info['epoch']:
                try:self.flock_join('always',approved=True)
                except (OSError,ValueError) as error:
                    self.flock_attempt=info['epoch'];self.lines.append('KoelDrop: '+str(error))
            return
        if getattr(self,'flock_seen',None)==info['epoch']:return
        self.flock_seen=info['epoch']
        # Anonymous campus clients can see the invitation, never claim eligibility.
        # The join request itself requires verified membership + real socket proof.
        self.lines.extend([LABEL+' is available from '+info['host']+'. Verified 42SG sign-in and an active campus seat are required.',
                           '/koel flock once | always | never. Joining shares today’s dedicated folder, including retained contents; incoming files need approval. Local copies are never automatically deleted.'])
        if not self.important_notification_allowed('flock'):return
        from ..announcement_client import claim
        if not claim(preferences.fingerprint+':flock:'+info['epoch']+':'+str(preferences.uid)):return
        contexts=getattr(self,'flock_actions',{})
        if len(contexts)>=16:contexts.pop(next(iter(contexts)))
        key=secrets.token_hex(16);contexts[key]=dict(info);self.flock_actions=contexts
        if not getattr(self,'tracking_notifier',None):
            from ..desktop_notifications import Notifications
            self.tracking_notifier=Notifications(self.inbox)
        self.tracking_notifier.flock(LABEL+' is open',
            'Verified 42SG users on campus only. Join today’s upload folder (reused on reconnect); approve incoming files separately. Local files are kept.',key)

    def flock_join(self,mode,approved=False):
        info=getattr(self,'flock_info',None)
        if not info:raise Denied('The host flock is unavailable. Local files are kept; waiting for the trusted host.')
        preferences=self.flock_preferences()
        if not getattr(self,'secure',False):
            self.pending_flock_choice=dict(mode=mode,epoch=info['epoch'],fingerprint=preferences.fingerprint)
            self.lines.append('Sign in first; eligibility is checked by the host before joining. Always-join consent is confirmed after sign-in.')
            self.start_signin();return
        worker=getattr(self,'courier',None)
        already_joined=bool(worker and getattr(worker,'sync',None) and getattr(worker,'flock_epoch',None)==info['epoch'])
        if worker and (getattr(worker,'sync',None) or getattr(worker,'join_pending',None)) and not already_joined:
            self.flock_attempt=info['epoch']
            self.lines.append('Another KoelDrop group is active or joining. It was kept; /koel leave first, then /koel flock '+mode+'.')
            return
        if not approved:
            self.popup_prompts().confirm(
                ('Always join this trusted host’s ' if mode=='always' else 'Join once: ')+LABEL+'? Service directory: '+preferences.base+
                '/42-singapore/<trusted-host>/<student-id>/<SGT-date>/. Same-day reconnects reuse this folder. Files left or added there upload to admitted SG flock members and remain on the host across restarts, subject to quotas. Incoming files and deletions need separate approval. Only LAN42-marked daily folders for this host/account/group are reused; other existing folders are refused. Folders are never renamed or erased; local copies survive shutdown and remain until you remove them yourself.',
                lambda:self.flock_join(mode,approved=True))
            return
        from .flock import sgoinfre_target,link_sgoinfre
        target=sgoinfre_target()
        if (not preferences.storage_chosen and target is not None
                and Path(preferences.base)==Path.home()/'KoelDrop' and not os.path.lexists(preferences.base)):
            def choose(use_nas):
                try:
                    if use_nas:link_sgoinfre(preferences,target)
                    else:
                        preferences.storage_chosen=True;preferences.save()
                    self.flock_join(mode,approved=True)
                except (OSError,ValueError) as error:self.lines.append('KoelDrop: '+str(error))
            self.popup_prompts().confirm(
                'Save KoelDrop in campus sgoinfre to spare your small home quota? Create '+preferences.base+
                ' as a symlink to '+str(target)+'? [y/N] No keeps files in home. sgoinfre availability/retention follows campus policy; local copies are not backups. Existing paths are never replaced.',
                lambda:choose(True),lambda:choose(False))
            return
        preferences.save(mode='always' if mode=='always' else 'ask')
        self.flock_attempt=info['epoch']
        if already_joined:
            self.lines.append('Already in this flock. Future-join preference: '+preferences.mode+'.')
            return
        worker=self.koel_worker()
        worker.submit('flock',info['group'],info['host'],info['epoch'],preferences.base,preferences.fingerprint)

    def flock_command(self,action,args):
        try:
            preferences=self.flock_preferences()
            if action=='flock-dir':
                if len(args)!=1:raise Denied('Use /koel flock-dir "DEDICATED SERVICE DIRECTORY"')
                path=args[0]
                self.popup_prompts().confirm('Use '+path+' as the KoelDrop service directory? Only marked daily 42-singapore subfolders will sync. Same-day reconnects share their retained contents. Other existing files are not imported or deleted.',lambda:preferences.save(base=path))
            else:
                mode=args[0] if len(args)==1 else 'status' if not args else None
                if mode in ('once','always'):self.flock_join(mode)
                elif mode in ('ask','never'):
                    preferences.save(mode=mode)
                    self.pending_flock_choice=None;self.flock_attempt=None
                    self.lines.append('Flock preference: '+mode+'. Existing group membership is unchanged; /koel leave stops uploads.')
                elif mode=='status':
                    self.lines.append(LABEL+': '+('available' if getattr(self,'flock_info',None) else 'host unavailable')+' | preference='+preferences.mode+' | service directory='+preferences.base)
                    self.lines.append('/koel flock once|always|never|ask | /koel flock-dir "PATH". Fresh folders are retained, never automatically deleted.')
                else:raise Denied('Use /koel flock once|always|never|ask|status')
        except (OSError,ValueError) as error:self.lines.append('KoelDrop: '+str(error))
        return True

    def flock_notification_action(self,message):
        modes={'flock_once':'once','flock_always':'always','flock_never':'never'}
        mode=modes.get(message.get('action'))
        if not mode:return False
        info=getattr(self,'flock_actions',{}).pop(message.get('context'),None)
        current=getattr(self,'flock_info',None)
        if not info or not current or info['epoch']!=current['epoch']:return True
        return self.flock_command('flock',[mode])

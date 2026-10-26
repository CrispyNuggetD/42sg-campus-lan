"""Local announcement commands and trusted-host events for the curses client."""
import json
import queue
import re
import threading
import time
from .auth import AuthError,config_dir,private_read
from . import auth_client
from .announcement_client import HostWatch,HostSettings,act,claim,credentials


class AnnouncementUI:
    def announcement_tick(self):
        if not getattr(self,'connected',False) or not getattr(self,'id',None):return
        if not getattr(self,'host_watch',None):
            self.host_watch=HostWatch(self.inbox);self.host_watch.start()

    def announcement_work(self,operation):
        def work():
            try:result=operation();message=dict(type='local_announcement_result',result=result)
            except AuthError as error:message=dict(type='local_announcement_result',error=str(error))
            except (OSError,ValueError):message=dict(type='local_announcement_result',error='Announcement request failed; check host availability or sign-in.')
            try:self.inbox.put_nowait(message)
            except queue.Full:pass
        threading.Thread(target=work,daemon=True).start()

    def announcement_command(self,text):
        command,_,arguments=text.partition(' ')
        if command not in ('/announce','/broadcast'):return False
        arguments=arguments.strip()
        if arguments in ('','status'):
            status=getattr(self,'announcement_status',{})
            self.lines.append('API host: '+(status.get('owner','trusted host')+' online' if status.get('online') else 'offline/not configured; local guest lobby stays available'))
            self.lines.append('/announce TEXT submits to the API host; only that host can broadcast or approve. /announce approve|reject REQUEST_ID')
            return True
        if arguments=='refresh':
            watch=getattr(self,'host_watch',None)
            if watch:watch.next_locator=0;watch.next_poll=0
            return True
        parts=arguments.split()
        if parts[0] in ('approve','reject'):
            if len(parts)!=2 or not re.fullmatch('[a-f0-9]{32}',parts[1]):self.lines.append('Use /announce approve|reject REQUEST_ID')
            else:self.announcement_work(lambda:act('decide',id=parts[1],decision=parts[0]))
            return True
        try:
            from .announcements import message
            body=message(arguments);trust=auth_client.load_trust();proof=credentials(trust)
            if not proof:raise AuthError('Sign in with 42 first; guest names cannot submit announcements.')
            session=auth_client.load_session(trust) if 'admin' not in proof else None
            author=session['login'] if session else self.name
            host='admin' in proof or getattr(self,'announcement_status',{}).get('host',False)
            owner=getattr(self,'announcement_status',{}).get('owner',self.name if host else 'API host')
            if host:
                description='Broadcast as '+owner+' (host)? Do not abuse this: every trusted running client receives an admin alert. '+body
            else:
                description='Ask '+owner+' to approve an announcement quoting intra:'+author+'? '+body
            self.popup_prompts().confirm(description,lambda:self.announcement_work(lambda:act('request',text=body)))
        except (OSError,ValueError) as error:self.lines.append(str(error))
        return True

    def announcement_action(self,event):
        decision={'announce_approve':'approve','announce_reject':'reject'}.get(event.get('action'))
        if not decision:return False
        context=event.get('context');ident=context.get('request_id') if isinstance(context,dict) else None
        if isinstance(ident,str) and re.fullmatch('[a-f0-9]{32}',ident):
            self.announcement_work(lambda:act('decide',id=ident,decision=decision))
        return True

    def host_settings_command(self,text):
        parts=text.split()
        if len(parts)<2 or parts[0]!='/settings' or parts[1] not in ('host-discovery','auto-host-join','host-poll'):return False
        try:
            settings=HostSettings();key={'host-discovery':'discovery','auto-host-join':'auto_join','host-poll':'interval'}[parts[1]]
            if len(parts)==3:
                if key=='interval':value=int(parts[2])
                else:
                    if parts[2] not in ('on','off'):raise ValueError('Use on|off.')
                    value=parts[2]=='on'
                settings.set(key,value)
            elif len(parts)!=2:raise ValueError('Use /settings '+parts[1]+' VALUE')
            self.lines.append('Host discovery='+str(settings.data['discovery'])+', saved-session auto-join='+str(settings.data['auto_join'])+', offline check='+str(settings.data['interval'])+' seconds.')
        except (OSError,ValueError) as error:self.lines.append(str(error))
        return True

    def link_api_guest_node(self,event):
        if (getattr(self,'role','lobby')!='lobby' or getattr(self,'secure',False)
                or not event.get('auto_connect',True)):return
        callback=getattr(self,'peer_callback',None)
        if not callback:return
        key=(event['host'],event['data']['epoch'])
        now=time.monotonic()
        if (not callback or getattr(self,'api_link_key',None)==key or getattr(self,'api_link_busy',False)
                or now<getattr(self,'api_link_retry',0)):return
        self.api_link_busy=True;self.api_link_retry=now+event.get('retry_interval',120)
        def link():
            connected=False
            try:callback(event['host'],31415);connected=True
            except (OSError,ValueError,RuntimeError):pass
            try:self.inbox.put_nowait(dict(type='local_api_link',key=key,connected=connected))
            except queue.Full:self.api_link_busy=False
        threading.Thread(target=link,daemon=True).start()

    def announcement_event(self,event):
        kind=event.get('type')
        if kind=='local_api_link':
            self.api_link_busy=False
            if event.get('connected'):
                self.api_link_key=event['key'];self.lines.append('Guest node linked to the trusted API host seat; guest identities stay unverified.')
            return True
        if kind=='local_announcement_result':
            if event.get('error'):self.lines.append(event['error']);return True
            result=event.get('result',{})
            self.lines.append('Announcement '+str(result.get('id',''))+': '+str(result.get('status','unknown'))+
                              (' — waiting for '+result['owner']+' to approve/reject' if result.get('status')=='pending' else ''))
            watch=getattr(self,'host_watch',None)
            if watch:watch.next_poll=0
            return True
        if kind!='local_host_update':return False
        if not event.get('online'):
            self.announcement_status=dict(online=False)
            self.lines.append('API host unavailable; your local guest lobby keeps running. Retrying on the configured interval.')
            return True
        data=event['data'];self.announcement_status=dict(data,online=True)
        self.link_api_guest_node(event)
        if event.get('recovered'):
            from .network import seat_label
            text=data['owner']+' (API host) has come online at '+seat_label(event['host'])+' ('+event['host']+').'
            self.lines.append(text)
            if getattr(self,'notify_enabled',False) and claim(data['epoch']+':online'):
                self.desktop_notice('LAN42 API host online',text,data['owner'])
            if getattr(self,'role','lobby')=='lobby' and not getattr(self,'secure',False):
                from .login_settings import auto_login_paused
                if event.get('auto_join') and not auto_login_paused() and not getattr(self,'game',{}).get('room'):
                    try:
                        trust=auth_client.load_trust()
                        if auth_client.load_session(trust):self.start_signin(saved_only=True)
                        else:self.lines.append('Guest mesh can link now. Use /signin for verified/API privileges.')
                    except (OSError,ValueError):pass
        states=getattr(self,'announcement_request_states',{})
        for item in data.get('statuses',[]):
            if states.get(item['id'])!=item['status']:
                states[item['id']]=item['status']
                self.lines.append('Announcement request '+item['id']+': '+item['status'])
        self.announcement_request_states=states
        for request in data.get('pending',[]):
            key='pending:'+request['id']
            if states.get(key):continue
            states[key]=True
            self.lines.append('Approve/reject intra:'+request['author']+': '+request['text']+' | /announce approve|reject '+request['id'])
            if claim(data['epoch']+':request:'+request['id']):
                if not getattr(self,'tracking_notifier',None):
                    from .desktop_notifications import Notifications
                    self.tracking_notifier=Notifications(self.inbox)
                self.tracking_notifier.approval('Announcement request from intra:'+request['author'],
                                               request['text'],request['author'],request['id'])
        for announcement in data['announcements']:
            author=announcement['author']+(' (host)' if announcement['is_host'] else '')
            title='LAN42 announcement — '+author
            body='“'+announcement['text']+'”'
            self.lines.extend([title,body])
            if claim(data['epoch']+':'+announcement['id']):
                # Privileged API-host channel intentionally bypasses ordinary LAN mute.
                if not getattr(self,'tracking_notifier',None):
                    from .desktop_notifications import Notifications
                    self.tracking_notifier=Notifications(self.inbox)
                self.tracking_notifier.announcement(title,body,announcement['author'])
        return True

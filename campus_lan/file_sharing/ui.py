"""Terminal and native-notification consent for the opt-in courier."""
import re
import secrets
import shlex
import time
from .settings import ExperimentalSettings
from .security import Denied,login


class KoelUI:
    def koel_worker(self):
        if not ExperimentalSettings().enabled:raise Denied('KoelDrop is disabled. /settings experimental on opts in.')
        if not getattr(self,'secure',False) or getattr(self,'role','lobby')!='lobby':raise Denied('Use KoelDrop from your signed-in HQ lobby.')
        worker=getattr(self,'courier',None)
        if worker is None or worker.stopped.is_set():
            from .. import auth_client
            from .client import Courier
            from .remote import RemoteStore
            trust=auth_client.load_trust()
            if auth_client.endpoint(trust)!=getattr(self,'current',None):raise Denied('Connect to your configured trusted lobby first.')
            self.courier=Courier(self.session_token,self.uid,self.name,self.inbox,RemoteStore(self.session_token,trust))
        return self.courier

    def experimental_command(self,text):
        try:parts=shlex.split(text)
        except ValueError:
            if text.startswith(('/koel','/files')):self.lines.append('KoelDrop: close the quotation marks in your command.');return True
            return False
        if not parts or parts[0] not in ('/roadmap','/experimental','/files','/koel','/koeldrop'):return False
        from . import roadmap
        if parts[0] in ('/roadmap','/experimental'):
            self.lines.extend(roadmap());return True
        try:
            action=parts[1] if len(parts)>1 else 'status';args=parts[2:]
            if action in ('status','help') and not ExperimentalSettings().enabled:
                self.lines.extend(roadmap());return True
            worker=self.koel_worker()
            if action in ('status','help'):
                worker.submit('status')
                self.lines.extend(['/koel create | invite LOGIN...|friends|@LIST | accept NUMBER | decline NUMBER',
                                   '/koel dir "EMPTY PATH" | pending | receive NUMBER | reject NUMBER | sync | leave',
                                   '/koel trust LOGIN...|friends|@LIST|off — explicit group receive whitelist; no automatic deletions'])
            elif action=='pending':self.koel_pending()
            elif action=='create' and not args:
                self.popup_prompts().confirm('Create KoelDrop and upload files added to its dedicated folder? [y/N]',lambda:worker.submit('create'))
            elif action=='invite' and args:
                from .workflow import invite_targets
                names=invite_targets(self.get_tracker(),args,self.name)
                worker.submit('invite',names)
            elif action in ('accept','decline') and len(args)==1:
                invite=getattr(self,'koel_invites',{}).get(int(args[0]))
                if not invite or invite['expires']<=time.time():raise Denied('Invitation missing or expired; ask the host to invite again.')
                if action=='accept':worker.submit('accept',invite['group'],invite['host'],invite['invite'])
                else:self.koel_invites.pop(int(args[0]));self.lines.append('KoelDrop invitation declined.')
            elif action in ('receive','reject') and len(args)==1:
                offer=getattr(self,'koel_offers',{}).get(int(args[0]))
                if not offer:raise Denied('No such file offer. /koel pending')
                worker.submit('receive' if action=='receive' else 'decline',offer['version'])
            elif action=='dir' and len(args)==1:worker.submit('dir',args[0])
            elif action=='trust' and args:
                names=[] if args==['off'] else self.get_tracker().resolve(args)
                if len(names)>100:raise Denied('Receive whitelist is limited to 100 people.')
                if not names and args!=['off']:raise Denied('That receive whitelist is empty.')
                if names:
                    self.popup_prompts().confirm('Automatically receive files from '+', '.join(names)+' in this group? [y/N]',lambda:worker.submit('trust',names))
                else:worker.submit('trust',[])
            elif action in ('sync','leave') and not args:worker.submit(action)
            else:raise Denied('Use /koel help for commands.')
        except (OSError,ValueError) as error:self.lines.append('KoelDrop: '+str(error))
        return True

    def koel_pending(self):
        lines=[]
        for number,invite in getattr(self,'koel_invites',{}).items():
            if invite['expires']>time.time():lines.append('Invitation '+str(number)+' from '+invite['host']+' — /koel accept '+str(number)+' (opts into folder uploads) or /koel decline '+str(number))
        for number,offer in getattr(self,'koel_offers',{}).items():
            lines.append('File '+str(number)+': '+offer['author']+' → '+offer['path']+' ('+('delete request' if offer['deleted'] else str(offer['size'])+' bytes')+') — /koel receive '+str(number)+' or /koel reject '+str(number))
        self.lines.extend(lines or ['No pending KoelDrop invitations or files.'])

    def koel_invitation(self,message):
        if not getattr(self,'secure',False) or not ExperimentalSettings().enabled:return
        try:
            gid=message['group'];token=message['invite'];host=login(message['host']);expiry=message['expires']
            if not isinstance(gid,str) or not re.fullmatch('[a-f0-9]{32}',gid):return
            if not isinstance(token,str) or not re.fullmatch('[A-Za-z0-9_-]{43}',token):return
            if type(expiry) not in (int,float) or not time.time()<expiry<=time.time()+301:return
        except (ValueError,KeyError,TypeError):return
        invites={key:value for key,value in getattr(self,'koel_invites',{}).items() if value['expires']>time.time()}
        if len(invites)>=32 or any(value['invite']==token for value in invites.values()):return
        number=getattr(self,'koel_invite_number',0)+1;self.koel_invite_number=number
        invites[number]=dict(group=gid,invite=token,host=host,expires=expiry);self.koel_invites=invites
        self.lines.extend(['uwu, '+host+' invited you to KoelDrop.',
                           '/koel accept '+str(number)+' creates a dedicated folder and uploads files you add there. Incoming files need separate approval.',
                           '/koel decline '+str(number)+' says no. Invitation expires in five minutes or when the host signs out.'])
        self.koel_notice('uwu, '+host+' invited you to KoelDrop',
                         'Accept to join and upload files added to a dedicated folder. Incoming files need separate approval.',host,
                         '/koel accept '+str(number),'/koel decline '+str(number),False)

    def koel_notice(self,title,body,name,accept,decline,sound):
        contexts=getattr(self,'koel_actions',{})
        if len(contexts)>=100:contexts.pop(next(iter(contexts)))
        key=secrets.token_hex(16);contexts[key]=(accept,decline);self.koel_actions=contexts
        def show():
            if not self.notify_enabled or not ExperimentalSettings().enabled:return False
            if not getattr(self,'tracking_notifier',None):
                from ..desktop_notifications import Notifications
                self.tracking_notifier=Notifications(self.inbox)
            self.tracking_notifier.show(title,body,name,koel_sound=sound,
                                       custom_actions={'koel_accept':'Approve','koel_decline':'Decline'},action_context=key)
        self.request_popup('notifications','Show KoelDrop notification: '+title+'?',show)

    def koel_local(self,message):
        worker=getattr(self,'courier',None)
        if not worker or message.get('courier')!=id(worker) or not ExperimentalSettings().enabled:return
        self.lines.extend(''.join(c for c in str(line) if c.isprintable()) for line in message.get('lines',[]))
        if message.get('deliver'):self.send(message['deliver'])
        if 'offers' in message:
            previous={o['version']:key for key,o in getattr(self,'koel_offers',{}).items()}
            offers={};number=getattr(self,'koel_offer_number',0)
            for offer in message['offers']:
                key=previous.get(offer['version'])
                if key is None:number+=1;key=number
                offers[key]=offer
            self.koel_offers=offers;self.koel_offer_number=number
        from ..koel_sound import SoundChoice
        for notice in message.get('notices',[]):
            key=next((key for key,o in self.koel_offers.items() if o['version']==notice['version']),None)
            if key is None:continue
            title=(notice['author']+' requested deleting ' if notice['deleted'] else '🔊 uwu, '+notice['author']+' sent you ')+notice['path'].rsplit('/',1)[-1]
            body=notice['path']+' · '+str(notice['size'])+' bytes. /koel receive '+str(key)+' or /koel reject '+str(key)
            self.lines.extend([title,body])
            self.koel_notice(title,body,notice['author'],'/koel receive '+str(key),'/koel reject '+str(key),SoundChoice(self.name).read()['enabled'])

    def koel_notification_action(self,message):
        commands=getattr(self,'koel_actions',{}).pop(message.get('context'),None)
        if commands:self.experimental_command(commands[0 if message['action']=='koel_accept' else 1])

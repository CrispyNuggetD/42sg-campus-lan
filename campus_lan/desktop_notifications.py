"""Native desktop actions return drafts to the local UI, never send messages."""
import html
import queue
import shutil
import subprocess
import threading


class Notifications:
    def __init__(self,inbox):
        self.inbox=inbox;self.jobs=queue.Queue(maxsize=32);self.closed=threading.Event()
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()

    def show(self,title,body,name,icon='',can_message=False,koel_sound=None,custom_actions=None,action_context=None):
        try:self.jobs.put_nowait((title,body,name,icon,can_message,koel_sound,custom_actions,action_context))
        except queue.Full:pass

    def fallback(self,title,body,name,icon,can_message,koel_sound=None,custom_actions=None,action_context=None):
        if not shutil.which('notify-send'):return
        args=['notify-send','--app-name=LAN42 tracking','--expire-time=15000']
        if icon:args+=['--icon',icon]
        from .koel_sound import sound_hints
        for key,value in sound_hints(koel_sound).items():
            args+=['--hint',('boolean:'+key+':'+str(value).lower()) if isinstance(value,bool) else 'string:'+key+':'+value]
        try:subprocess.run([*args,'--',title,body],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5)
        except (OSError,subprocess.SubprocessError):pass

    def run(self):
        try:
            from gi.repository import Gio,GLib
            context=GLib.MainContext.new();context.push_thread_default()
            bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
            service='org.freedesktop.Notifications';path='/org/freedesktop/Notifications'
            caps=bus.call_sync(service,path,service,'GetCapabilities',None,None,Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
        except Exception:
            while not self.closed.is_set():
                try:self.fallback(*self.jobs.get(timeout=.25))
                except queue.Empty:pass
            return
        pending={}
        def signal(connection,sender,object_path,interface,signal_name,parameters):
            values=parameters.unpack();ident=values[0]
            if signal_name=='NotificationClosed':pending.pop(ident,None);return
            item=pending.pop(ident,None)
            if item and values[1] in item[1]:
                name,allowed,action_context=item
                try:
                    message=dict(type='notification_action',action=values[1],login=name)
                    if action_context is not None:message['context']=action_context
                    self.inbox.put_nowait(message)
                except queue.Full:pass
        subscription=bus.signal_subscribe(service,service,None,path,None,Gio.DBusSignalFlags.NONE,signal)
        try:
            while not self.closed.is_set():
                while context.pending():context.iteration(False)
                try:job=self.jobs.get(timeout=.1)
                except queue.Empty:continue
                title,body,name,icon,can_message,koel_sound,custom_actions,action_context=job
                actions=[]
                if 'actions' in caps:
                    if custom_actions is not None:
                        for key,label in custom_actions.items():actions.extend([key,label])
                    else:
                        if can_message:actions+=['message','Say hi / write message']
                        actions+=['profile','Open Intra profile']
                hints={'category':GLib.Variant('s','presence.online')}
                if icon:hints['image-path']=GLib.Variant('s',icon)
                from .koel_sound import sound_hints
                requested=koel_sound if 'sound' in caps else False if koel_sound is not None else None
                for key,value in sound_hints(requested).items():hints[key]=GLib.Variant('b' if isinstance(value,bool) else 's',value)
                try:
                    args=GLib.Variant('(susssasa{sv}i)',('LAN42 tracking',0,icon,title,html.escape(body) if 'body-markup' in caps else body,actions,hints,15000))
                    ident=bus.call_sync(service,path,service,'Notify',args,None,Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
                    pending[ident]=(name,set(actions[::2]),action_context)
                    if len(pending)>100:pending.pop(next(iter(pending)))
                except Exception:self.fallback(title,body,name,icon,can_message,False if koel_sound is not None else None)
        finally:
            bus.signal_unsubscribe(subscription);context.pop_thread_default()

    def close(self):self.closed.set()

    def poke(self,title,body,name,koel_sound=False,duration=2):
        """App-owned transient toast; callers enforce recipient consent or trusted host authority."""
        def show():
            import sys
            import time
            if koel_sound:
                try:
                    from .koel_sound import play
                    play()
                except OSError:pass
            if sys.platform=='darwin':
                # An app-owned panel can expire exactly, unlike Notification Center banners.
                script='''ObjC.import('AppKit');
function run(argv) {
 $.NSApplication.sharedApplication;
 const frame=$.NSScreen.mainScreen.visibleFrame;
 const panel=$.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
   $.NSMakeRect(frame.origin.x+frame.size.width-350,frame.origin.y+frame.size.height-110,330,90),128,2,false);
 panel.level=3; panel.hidesOnDeactivate=false;
 const label=$.NSTextField.alloc.initWithFrame($.NSMakeRect(15,10,300,70));
 label.stringValue=argv[0]+'\\n'+argv[1]; label.editable=false; label.selectable=false;
 label.bezeled=false; label.drawsBackground=false;
 panel.contentView.addSubview(label); panel.orderFrontRegardless;
 $.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(Number(argv[2])));
 panel.close;
}'''
                try:subprocess.run(['osascript','-l','JavaScript','-e',script,title,body,str(duration)],timeout=6,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                except (OSError,subprocess.SubprocessError):pass
                return
            try:
                from gi.repository import Gio,GLib
                bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
                service='org.freedesktop.Notifications';path='/org/freedesktop/Notifications'
                hints={'transient':GLib.Variant('b',True),'resident':GLib.Variant('b',False),
                       'suppress-sound':GLib.Variant('b',True)}
                args=GLib.Variant('(susssasa{sv}i)',('LAN42',0,'',title,html.escape(body),[],hints,int(duration*1000)))
                ident=bus.call_sync(service,path,service,'Notify',args,None,Gio.DBusCallFlags.NONE,3000,None).unpack()[0]
                time.sleep(duration)
                try:bus.call_sync(service,path,service,'CloseNotification',GLib.Variant('(u)',(ident,)),None,Gio.DBusCallFlags.NONE,3000,None)
                except Exception:pass
            except Exception:
                if not shutil.which('notify-send'):return
                try:
                    result=subprocess.run(['notify-send','--print-id','--expire-time='+str(int(duration*1000)),'--hint=boolean:transient:true',
                                           '--hint=boolean:suppress-sound:true','--',title,body],capture_output=True,text=True,timeout=4)
                    ident=result.stdout.strip()
                    if ident.isdecimal() and shutil.which('gdbus'):
                        time.sleep(duration)
                        subprocess.run(['gdbus','call','--session','--dest','org.freedesktop.Notifications',
                                        '--object-path','/org/freedesktop/Notifications','--method',
                                        'org.freedesktop.Notifications.CloseNotification',ident],
                                       stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=4)
                except (OSError,subprocess.SubprocessError):pass
        threading.Thread(target=show,daemon=True).start()

    def approval(self,title,body,name,request_id):
        """Only a local API-host request invokes this owner decision popup."""
        import sys
        if sys.platform!='darwin':
            self.show(title,body,name,custom_actions={'announce_approve':'Approve','announce_reject':'Reject'},
                      action_context={'request_id':request_id})
            return
        def choose():
            script='''on run argv
try
set result to display dialog (item 2 of argv) with title (item 1 of argv) buttons {"Reject", "Approve"} default button "Reject" giving up after 120
if gave up of result then return ""
return button returned of result
on error
return ""
end try
end run'''
            try:
                result=subprocess.run(['osascript','-e',script,title,body],capture_output=True,text=True,timeout=125)
                decision={'Approve':'announce_approve','Reject':'announce_reject'}.get(result.stdout.strip())
                if decision:self.inbox.put_nowait(dict(type='notification_action',action=decision,login=name,
                                                       context={'request_id':request_id}))
            except (OSError,subprocess.SubprocessError,queue.Full):pass
        threading.Thread(target=choose,daemon=True).start()

    def flock(self,title,body,context):
        """Three local choices; the UI still confirms the folder/upload consent."""
        import sys
        if sys.platform!='darwin':
            self.show(title,body,'',koel_sound=False,
                      custom_actions={'flock_once':'Join once','flock_always':'Always join','flock_never':'Never show again'},action_context=context)
            return
        def choose():
            script='''ObjC.import('AppKit');
function run(argv) {
 $.NSApplication.sharedApplication;
 let choice=-1;
 ObjC.registerSubclass({name:'LAN42FlockChoice',superclass:'NSObject',methods:{
 'choose:':{types:['void',['id']],implementation:function(sender){choice=Number(sender.tag);}}
 }});
 const target=$.LAN42FlockChoice.new;
 const frame=$.NSScreen.mainScreen.visibleFrame;
 const panel=$.NSPanel.alloc.initWithContentRectStyleMaskBackingDefer(
 $.NSMakeRect(frame.origin.x+frame.size.width-510,frame.origin.y+frame.size.height-205,490,185),128,2,false);
 panel.level=3;panel.hidesOnDeactivate=false;
 const label=$.NSTextField.alloc.initWithFrame($.NSMakeRect(15,65,460,105));
 label.stringValue=argv[0]+'\\n'+argv[1];label.editable=false;label.selectable=false;label.bezeled=false;label.drawsBackground=false;
 panel.contentView.addSubview(label);
 ['Join once','Always join','Never show again'].forEach(function(text,index){
 const button=$.NSButton.alloc.initWithFrame($.NSMakeRect(15+index*155,15,150,35));
 button.title=text;button.bezelStyle=1;button.tag=index;button.target=target;button.action='choose:';
 panel.contentView.addSubview(button);
 });
 panel.orderFrontRegardless;
 const deadline=Date.now()+40000;
 while(choice<0 && Date.now()<deadline){$.NSRunLoop.currentRunLoop.runUntilDate($.NSDate.dateWithTimeIntervalSinceNow(0.05));}
 panel.close;return choice<0?'':String(choice);
}'''
            try:
                result=subprocess.run(['osascript','-l','JavaScript','-e',script,title,body],capture_output=True,text=True,timeout=45)
                action={'0':'flock_once','1':'flock_always','2':'flock_never'}.get(result.stdout.strip())
                if action:self.inbox.put_nowait(dict(type='notification_action',action=action,context=context))
            except (OSError,subprocess.SubprocessError,queue.Full):pass
        threading.Thread(target=choose,daemon=True).start()

    def announcement(self,title,body,name):
        self.poke(title,body,name,koel_sound=False,duration=12)

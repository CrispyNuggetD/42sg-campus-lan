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

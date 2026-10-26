"""Run under dbus-run-session: no real desktop notifications or messages."""
import queue
import threading
from gi.repository import Gio,GLib
from campus_lan.desktop_notifications import Notifications

xml='''<node><interface name="org.freedesktop.Notifications">
<method name="GetCapabilities"><arg type="as" direction="out"/></method>
<method name="Notify"><arg type="s" direction="in"/><arg type="u" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="s" direction="in"/><arg type="as" direction="in"/><arg type="a{sv}" direction="in"/><arg type="i" direction="in"/><arg type="u" direction="out"/></method>
<signal name="ActionInvoked"><arg type="u"/><arg type="s"/></signal>
<signal name="NotificationClosed"><arg type="u"/><arg type="u"/></signal>
</interface></node>'''
ready=threading.Event();received=queue.Queue();stop=threading.Event()
def service():
    context=GLib.MainContext.new();context.push_thread_default()
    bus=Gio.bus_get_sync(Gio.BusType.SESSION,None)
    bus.call_sync('org.freedesktop.DBus','/org/freedesktop/DBus','org.freedesktop.DBus','RequestName',GLib.Variant('(su)',('org.freedesktop.Notifications',0)),None,Gio.DBusCallFlags.NONE,2000,None)
    def method(connection,sender,path,interface,name,parameters,invocation):
        if name=='GetCapabilities':invocation.return_value(GLib.Variant('(as)',(['actions','body','body-markup','sound'],)))
        else:
            values=parameters.unpack();assert 'message' in values[5] and 'profile' in values[5]
            assert values[4]=='cluster 2\nrow 3 &amp; seat 9'
            invocation.return_value(GLib.Variant('(u)',(42,)));received.put((bus,values))
    ident=bus.register_object('/org/freedesktop/Notifications',Gio.DBusNodeInfo.new_for_xml(xml).interfaces[0],method,None,None)
    ready.set()
    while not stop.is_set():
        if context.pending():context.iteration(False)
        else:stop.wait(.01)
    bus.unregister_object(ident);context.pop_thread_default()
thread=threading.Thread(target=service,daemon=True);thread.start();assert ready.wait(3)
inbox=queue.Queue();notifier=Notifications(inbox)
try:
    notifier.show('dthoo joined','cluster 2\nrow 3 & seat 9','dthoo',can_message=True)
    bus,values=received.get(timeout=5)
    bus.emit_signal(None,'/org/freedesktop/Notifications','org.freedesktop.Notifications','ActionInvoked',GLib.Variant('(us)',(42,'message')))
    assert inbox.get(timeout=5)==dict(type='notification_action',action='message',login='dthoo')
    notifier.show('silent koel','cluster 2\nrow 3 & seat 9','dthoo',can_message=True,koel_sound=False)
    _,values=received.get(timeout=5);assert values[6]['suppress-sound'] is True
    notifier.show('opted-in koel','cluster 2\nrow 3 & seat 9','dthoo',can_message=True,koel_sound=True)
    _,values=received.get(timeout=5)
    assert values[6]['suppress-sound'] is False and values[6]['sound-file'].endswith('/assets/sounds/uwu.ogg')
    print('PASS: native draft actions and opted-in sound-file hints; no real desktop notifications or audio')
finally:notifier.close();stop.set();thread.join(2)

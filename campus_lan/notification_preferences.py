"""Private per-computer notification channels; importance is assigned locally."""
import json
from .auth import private_read, private_write
from .local_console import local_path

DEFAULTS = dict(host=True, announcements=True, releases=True, warnings=True,
                tracking=True, chat=False, dms=False, pokes=False)
IMPORTANT = frozenset(('host', 'announcements', 'releases', 'warnings'))


class Preferences:
    def __init__(self):
        self.path = local_path('notification-channels')
        self.data = {}
        try:
            self.data = json.loads(private_read(self.path))
            if not isinstance(self.data, dict) or any(k not in (*DEFAULTS, 'all') or type(v) is not bool for k,v in self.data.items()):
                raise ValueError('Invalid notification preferences.')
        except FileNotFoundError:pass
        except (OSError, ValueError):self.data = {'all': False}

    def allows(self, category):
        return self.data.get('all', True) and self.data.get(category, DEFAULTS[category])

    def set(self, category, enabled):
        if category not in (*DEFAULTS, 'all'):raise ValueError('Unknown notification category.')
        self.data[category] = enabled
        private_write(self.path, json.dumps(self.data))


class NotificationControls:
    def notification_allowed(self, category):
        # --no-notify is an explicit all-channel override for this launch.
        if getattr(self, 'notifications_disabled', False):return False
        if category not in IMPORTANT and not getattr(self, 'notify_enabled', True):return False
        return Preferences().allows(category)

    def important_notification_allowed(self, category):
        if not self.notification_allowed(category):return False
        # Honour existing explicit desktop-popup denials. Important channels are
        # otherwise on by default; they do not ask on every host arrival.
        from .popup_permissions import Permissions
        return Permissions(getattr(self, 'name', 'guest')).persistent_mode('notifications') != 'deny'

    def notification_command(self, text):
        parts = text.split()
        if parts[:2] in (['/settings', 'notifications'], ['/profile', 'notifications']):parts = ['/notify', *parts[2:]]
        if not parts or parts[0] != '/notify':return False
        try:
            settings = Preferences()
            if parts[1:] in (['on'], ['off']):
                # Compatibility: ordinary social/arrival alerts only.
                enabled = parts[1] == 'on'
                self.notify_enabled = enabled
                for key in ('chat', 'dms', 'pokes', 'tracking'):settings.set(key, enabled)
                self.lines.append('Ordinary notifications '+parts[1]+'. Host/broadcast/release/warning preferences stay separate; /notify all off silences everything.')
            elif len(parts) == 3 and parts[1] in (*DEFAULTS, 'all') and parts[2] in ('on', 'off'):
                settings.set(parts[1], parts[2] == 'on')
                if parts[2] == 'on':
                    self.notify_enabled = True
                    if parts[1] == 'all':self.notifications_disabled = False
                self.lines.append('Notifications '+parts[1]+': '+parts[2]+'.')
                if parts[1] == 'all' and parts[2] == 'off':self.lines.append('All desktop alerts silenced, including host availability and approved broadcasts. In-app messages remain visible.')
            elif len(parts) != 1:raise ValueError('Use /notify [CATEGORY on|off], /notify on|off, or /notify all off.')
            self.lines.append('Desktop channels: '+', '.join(k+'='+('on' if self.notification_allowed(k) else 'off') for k in DEFAULTS))
            self.lines.append('Host online enables sign-in/API views; guest chat/games work without it. /notify all on restores the channel choices; OS notification permissions still apply.')
        except (OSError, ValueError) as error:self.lines.append(str(error))
        return True

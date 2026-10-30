"""Local login preferences; no credentials or browser data in this file."""
import json
from .auth import config_dir,private_read,private_write
from .preferences import settings_path

_paused=False


def pause_for_session():
    global _paused
    _paused=True


def auto_login_paused():return _paused


class LoginSettings:
    def __init__(self):
        self.path=settings_path('login-settings.json',config_dir())
        self.data=dict(autologin='off',close_tab=True,autologin_asked=False);self.error=None
        try:
            data=json.loads(private_read(self.path))
            if (not isinstance(data,dict) or set(data)-{'autologin','close_tab','autologin_asked'}
                    or data.get('autologin','off') not in ('off','saved','on')
                    or type(data.get('close_tab',True)) is not bool
                    or type(data.get('autologin_asked',False)) is not bool):raise ValueError()
            self.data.update(data)
        except FileNotFoundError:pass
        except (OSError,ValueError):
            self.error='Login settings are unreadable; automatic login is disabled. Repair '+str(self.path)
            self.data=dict(autologin='off',close_tab=False,autologin_asked=False)

    def set(self,key,value):
        if self.error:raise ValueError(self.error)
        if key=='autologin' and value not in ('off','saved','on'):raise ValueError('Use /settings autologin off|saved|on')
        if key=='close_tab' and type(value) is not bool:raise ValueError('Use /settings signin-close on|off')
        if key=='autologin_asked' and type(value) is not bool:raise ValueError('Invalid login prompt preference.')
        if key not in self.data:raise ValueError('Unknown login setting.')
        candidate=dict(self.data,**{key:value})
        if key=='autologin':candidate['autologin_asked']=True
        private_write(self.path,json.dumps(candidate));self.data=candidate

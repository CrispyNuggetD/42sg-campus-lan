"""Local per-user choice to open the read-only cluster miniapp with HQ."""
import hashlib
import json
from pathlib import Path
from .auth import config_dir,private_read,private_write
from .preferences import settings_path


class ClusterSettings:
    def __init__(self,owner):
        self.path=settings_path('clusters-auto-open-'+hashlib.sha256(owner.lower().encode()).hexdigest()+'.json',config_dir())

    def read(self):
        try:return json.loads(private_read(self.path)).get('enabled') is True
        except FileNotFoundError:return Path('/proc/ish').is_dir()
        except (OSError,ValueError,AttributeError):return False

    def set(self,enabled):
        private_write(self.path,json.dumps({'enabled':enabled is True}))

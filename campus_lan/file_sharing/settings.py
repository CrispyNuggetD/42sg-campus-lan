"""Explicit local experimental opt-in. Off when absent, malformed or unreadable."""
import json
from ..auth import config_dir,private_read,private_write


class ExperimentalSettings:
    def __init__(self):
        self.path=config_dir()/'experimental.json';self.enabled=False
        try:
            data=json.loads(private_read(self.path))
            self.enabled=isinstance(data,dict) and data.get('enabled') is True
        except (OSError,ValueError):pass

    def set(self,enabled):
        private_write(self.path,json.dumps(dict(enabled=enabled is True)))
        self.enabled=enabled is True

"""Explicit local experimental opt-in. Off when absent, malformed or unreadable."""
import json
import secrets
from ..auth import config_dir,private_read,private_write


class ExperimentalSettings:
    def __init__(self):
        self.path=config_dir()/'experimental.json';self.enabled=False;self.generation=''
        try:
            data=json.loads(private_read(self.path))
            self.enabled=isinstance(data,dict) and data.get('enabled') is True
            if isinstance(data,dict) and isinstance(data.get('generation'),str):self.generation=data['generation']
        except (OSError,ValueError):pass

    def set(self,enabled):
        generation=self.generation if self.enabled==(enabled is True) else secrets.token_hex(16)
        private_write(self.path,json.dumps(dict(enabled=enabled is True,generation=generation)))
        self.generation=generation
        self.enabled=enabled is True

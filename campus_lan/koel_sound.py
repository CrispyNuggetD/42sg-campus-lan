"""Opt-in running-joke sound preferences. No playback happens in this module."""
import json
from pathlib import Path
from .auth import private_read,private_write,config_dir
from .popup_permissions import Permissions

ASSET=Path(__file__).resolve().parents[1]/'assets/sounds/uwu.ogg'
MAC_ASSET=ASSET.with_name('uwu-mac.wav')


class SoundChoice:
    def __init__(self,owner):
        import hashlib
        self.preference=config_dir()/('koel-sound-'+hashlib.sha256(owner.lower().encode()).hexdigest()+'.json')
        session=Permissions(owner).session_path()
        self.path=session.with_name(session.stem+'-koel.json') if session else None
        self.local=dict(asked=False,enabled=False)

    def always_on(self):
        try:return json.loads(private_read(self.preference)).get('always') is True
        except (OSError,ValueError,AttributeError):return False

    def set_always(self,enabled):
        private_write(self.preference,json.dumps(dict(always=enabled is True)))
        if enabled:self.choose(True)

    def read(self):
        if self.always_on():return dict(asked=True,enabled=True)
        if self.path:
            try:
                data=json.loads(private_read(self.path))
                if type(data.get('asked')) is bool and type(data.get('enabled')) is bool:return data
            except (OSError,ValueError,AttributeError):pass
            return dict(asked=False,enabled=False)
        return dict(self.local)

    def choose(self,enabled):
        data=dict(asked=True,enabled=enabled is True)
        if self.path:private_write(self.path,json.dumps(data))
        self.local=data


def sound_hints(enabled):
    """None leaves normal notification policy unchanged; False explicitly silences."""
    from .audio_quiet import active
    if active():return {'suppress-sound':True}
    if enabled is None:return {}
    if not enabled:return {'suppress-sound':True}
    try:
        if ASSET.stat().st_size>128*1024 or ASSET.read_bytes()[:4]!=b'OggS':return {'suppress-sound':True}
    except OSError:return {'suppress-sound':True}
    return {'sound-file':str(ASSET),'suppress-sound':False}


def play():
    """Play the bundled clip locally, without a shell or a desktop notification."""
    from .audio_quiet import active
    if active():return
    import shutil
    import subprocess
    import sys
    if 'sound-file' not in sound_hints(True):
        if active():return
        raise OSError('The bundled koel sound is unavailable.')
    choices = [('afplay', [])] if sys.platform == 'darwin' else [
        ('paplay', []), ('pw-play', []), ('ffplay', ['-nodisp', '-autoexit', '-loglevel', 'quiet'])]
    # Native PCM avoids the short Vorbis playback path on macOS. The padded
    # copy contains the same decoded call, with room for device startup/drain.
    asset = MAC_ASSET if sys.platform == 'darwin' else ASSET
    if not asset.is_file():
        raise OSError('The bundled Mac sound is unavailable; update LAN42 and retry.')
    for name, flags in choices:
        executable = shutil.which(name)
        if executable:
            subprocess.Popen([executable, *flags, str(asset)], stdin=subprocess.DEVNULL,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
            return
    raise OSError('No local sound player found (afplay on Mac; paplay or pw-play on Linux).')

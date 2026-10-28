"""Opt-in GNOME dock shortcut. Reads are separate from consented changes."""
import ast
import os
from pathlib import Path
import shutil
import subprocess
import sys

APP_ID = 'lan42-koeldrop.desktop'
SCHEMA = 'org.gnome.shell'
KEY = 'favorite-apps'


def supported():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    return sys.platform.startswith('linux') and any(name in desktop for name in ('gnome', 'ubuntu')) and bool(shutil.which('gsettings'))


def favorites():
    result = subprocess.run(['gsettings', 'get', SCHEMA, KEY], check=True,
                            capture_output=True, text=True, timeout=3)
    value = result.stdout.strip()
    if value.startswith('@as '):value = value[4:]
    apps = ast.literal_eval(value)
    if not isinstance(apps, list) or not all(isinstance(app, str) for app in apps):
        raise ValueError('Invalid Ubuntu favorites setting.')
    return apps


def needs_favorite():
    if not supported():return False
    try:return APP_ID not in favorites()
    except (OSError, ValueError, SyntaxError, subprocess.SubprocessError):return False


def exec_quote(value):
    # Desktop Entry Exec quoting differs from shell quoting; percent is a field code.
    value = str(value).replace('%', '%%')
    for char in ('\\', '"', '`', '$'):
        value = value.replace(char, '\\' + char)
    return '"' + value + '"'


def add_favorite():
    """Call only from an explicit local confirmation callback."""
    if not supported():raise ValueError('Ubuntu/GNOME dock favorites are unavailable.')
    apps = favorites()
    data_home = Path(os.environ.get('XDG_DATA_HOME') or Path.home()/'.local/share')
    destination = data_home/'applications'/APP_ID
    # Launch on click, without joining a group, uploading, or creating folders now.
    command = ' '.join(exec_quote(part) for part in (sys.executable, Path(__file__).resolve(), '--open'))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text('[Desktop Entry]\nType=Application\nName=KoelDrop\n'
                           'Comment=Open your KoelDrop folder\nIcon=folder-download\n'
                           'Exec='+command+'\nTerminal=false\nCategories=Network;FileTransfer;\n', encoding='utf-8')
    if APP_ID not in apps:
        # Re-read so a favorite pinned while the prompt was open is preserved.
        apps = favorites()
        if APP_ID not in apps:
            subprocess.run(['gsettings', 'set', SCHEMA, KEY, repr(apps + [APP_ID])],
                           check=True, capture_output=True, text=True, timeout=3)
    if APP_ID not in favorites():raise ValueError('Ubuntu did not save the KoelDrop favorite.')


def open_folder():
    folder = Path.home()/'KoelDrop'
    folder.mkdir(parents=True, exist_ok=True)
    subprocess.run(['xdg-open', str(folder)], check=True, timeout=10)


if __name__ == '__main__' and sys.argv[1:] == ['--open']:
    open_folder()


def bookmark_supported():
    desktop = os.environ.get('XDG_CURRENT_DESKTOP', '').lower()
    return sys.platform.startswith('linux') and any(name in desktop for name in ('gnome', 'ubuntu'))


def bookmark_file():
    return Path(os.environ.get('XDG_CONFIG_HOME') or Path.home()/'.config')/'gtk-3.0/bookmarks'


def bookmarked(folder=None):
    from urllib.parse import unquote
    folder = Path(folder) if folder is not None else Path.home()/'KoelDrop'
    try:lines = bookmark_file().read_text(encoding='utf-8').splitlines()
    except FileNotFoundError:return False
    return any(unquote(line.split(' ', 1)[0]).rstrip('/') == unquote(folder.absolute().as_uri()).rstrip('/')
               for line in lines if line)


def add_bookmark(folder=None):
    """Append a GTK/Files location only after local consent; retain other bookmarks."""
    import fcntl
    import tempfile
    if not bookmark_supported():raise ValueError('Files sidebar bookmarks require Ubuntu/GNOME.')
    folder = Path(folder) if folder is not None else Path.home()/'KoelDrop'
    path = bookmark_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with (path.parent/'.lan42-bookmarks.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if bookmarked(folder):return
        try:original = path.read_text(encoding='utf-8')
        except FileNotFoundError:original = ''
        text = original + ('\n' if original and not original.endswith('\n') else '') + folder.absolute().as_uri() + ' KoelDrop\n'
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
                temporary = Path(output.name)
                output.write(text)
            os.replace(temporary, path)
        finally:
            if temporary:temporary.unlink(missing_ok=True)

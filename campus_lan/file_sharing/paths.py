"""Remote logical names never become server filesystem paths."""
from pathlib import Path,PurePosixPath
import os
import stat
import unicodedata
from .security import Denied


def logical_path(value):
    if (not isinstance(value,str) or not value or len(value.encode())>512 or value.startswith('/')
            or '\\' in value or '%' in value or unicodedata.normalize('NFC',value)!=value):raise Denied('Invalid relative file path.')
    parts=value.split('/')
    if len(parts)>8 or any(not p or p in ('.','..') or p.startswith('.') or len(p.encode())>120
                          or any(ord(c)<32 or ord(c)==127 or c in ':<>|?*' for c in p) for p in parts):
        raise Denied('Invalid relative file path.')
    if any(p.endswith((' ','.')) or p.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*(f'COM{i}' for i in range(10)),*(f'LPT{i}' for i in range(10))} for p in parts):
        raise Denied('Invalid relative file path.')
    return '/'.join(parts)


def private_directory(path,create=False):
    path=Path(path).expanduser()
    if not path.is_absolute() or '..' in path.parts:raise Denied('Use an absolute dedicated directory.')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for component in path.parts[1:]:
            if create:
                try:os.mkdir(component,0o700,dir_fd=fd)
                except FileExistsError:pass
            next_fd=os.open(component,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        info=os.fstat(fd)
        if info.st_uid!=os.getuid() or stat.S_IMODE(info.st_mode)&0o077:raise Denied('Directory must be owned by you and mode 700.')
        return fd
    except Exception:os.close(fd);raise

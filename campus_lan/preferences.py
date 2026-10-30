"""Portable, explicitly selected preferences; auth and device consent stay local."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat
from .auth import config_dir, private_read, private_write


def allowed(name):
    return name == 'login-settings.json' or bool(re.fullmatch(
        r'(tracking|clusters-auto-open|popup-permissions|koel-sound|koel-auto|notification-channels-account|audio-volume-account|web-search-account|clock-tools-account)-[a-f0-9]{64}\.json', name))


def directory(path, create=False, portable=False):
    path = Path(path).expanduser().absolute()
    if create and not path.exists():
        path.mkdir(parents=True, mode=0o700)
    path = path.resolve(strict=True)
    info = path.stat()
    if portable:
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
            raise ValueError('Preferences directory must be owned by you.')
        files=list(path.iterdir())
        if any(not allowed(item.name) for item in files):
            raise ValueError('Choose a dedicated folder containing only portable LAN42 preferences.')
        # Git does not retain private mode bits across an OS checkout. Selecting
        # this dedicated folder explicitly restores those permissions locally.
        for item in files:
            record=item.lstat()
            if not stat.S_ISREG(record.st_mode) or record.st_uid != os.getuid():
                raise ValueError('Refusing an unsafe preference file: '+str(item))
        path.chmod(0o700)
        for item in files:
            fd=os.open(item,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as stream:
                if os.fstat(stream.fileno()).st_uid!=os.getuid():raise ValueError('Preference owner changed.')
                os.fchmod(stream.fileno(),0o600)
        info=path.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Preferences directory must be owned by you and mode 700: ' + str(path))
    return path


def root(local=None):
    local = Path(local) if local is not None else config_dir()
    link = local / 'preferences'
    if link.exists() or link.is_symlink():
        return directory(link)
    return local


def settings_path(name, local=None):
    if not allowed(name):
        raise ValueError('This file is not a portable preference.')
    base=Path(local) if local is not None else config_dir()
    destination=root(base)/name
    legacy=base/name
    if destination!=legacy and not destination.exists() and legacy.exists():
        private_write(destination,private_read(legacy))
    return destination


def copy_preferences(source, target):
    """Validate the whole selection before writing; never overwrite conflicts."""
    pending = []
    for path in sorted(source.iterdir()):
        if not allowed(path.name):
            continue
        raw = private_read(path)
        json.loads(raw)
        dst = target / path.name
        if dst.exists() or dst.is_symlink():
            if private_read(dst) != raw:
                raise ValueError('Different preference already exists; preserve/reconcile it first: ' + str(dst))
        else:
            pending.append((dst, raw))
    for dst, raw in pending:
        private_write(dst, raw)
    return len(pending)


def storage(target):
    local = config_dir()
    local.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory(local)
    source = root(local)
    target = directory(target, create=True, portable=True)
    if target == local or local in target.parents:
        raise ValueError('Choose a separate preferences folder outside the local auth directory.')
    if any(not allowed(path.name) for path in target.iterdir()):
        raise ValueError('Choose a dedicated folder containing only portable LAN42 preferences.')
    for path in target.iterdir():
        private_read(path)  # Reject symlinked/unsafe existing files even when nothing is copied.
    link = local / 'preferences'
    if link.exists() and not link.is_symlink():
        raise ValueError('Existing preferences directory retained; choose export instead of replacing it.')
    copy_preferences(source, target)
    temporary = local / ('.preferences-' + secrets.token_hex(8))
    try:
        temporary.symlink_to(target, target_is_directory=True)
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def perform(action, path=None):
    if action == 'storage':
        return str(storage(path) if path is not None else root())
    if path is None:
        raise ValueError('Supply a folder path.')
    if action == 'export':
        target = directory(path, create=True)
        count = copy_preferences(root(), target)
    elif action == 'import':
        source = directory(path, portable=True)
        count = copy_preferences(source, directory(root(), create=True))
    else:
        raise ValueError('Use storage, export or import.')
    return f'{count} preference files {action}ed. Existing files preserved.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('storage', 'export', 'import'))
    parser.add_argument('path', nargs='?')
    args = parser.parse_args()
    try:
        print(perform(args.action, args.path))
    except (OSError, ValueError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()

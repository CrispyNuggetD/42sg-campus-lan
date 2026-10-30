"""Portable, explicitly selected preferences; auth and device consent stay local."""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import subprocess
from datetime import datetime, timezone
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


class PreferenceConflict(ValueError):
    pass


def combine(existing, incoming):
    """Union collections recursively; existing scalar choices win."""
    if isinstance(existing, dict) and isinstance(incoming, dict):
        return {key: combine(existing[key], incoming[key]) if key in existing and key in incoming
                else existing[key] if key in existing else incoming[key]
                for key in dict.fromkeys([*existing, *incoming])}
    if isinstance(existing, list) and isinstance(incoming, list):
        result = list(existing)
        for item in incoming:
            if item not in result:
                result.append(item)
        return result
    return existing


def decode(raw, name):
    try:
        value = json.loads(raw)
    except ValueError as error:
        raise ValueError('Invalid JSON or unresolved Git conflict in '+name+
                         '; use /settings resolve FOLDER combine|overwrite for Git conflicts.') from error
    if not isinstance(value, dict):
        raise ValueError('Preference must be a JSON object: '+name)
    # Upgrade legacy relationship files before combining them with schema v2.
    if name.startswith('tracking-') and value.get('schema_version', 1) == 1:
        value = dict(schema_version=2, people={name: dict(relationship='tracked', alerts={})
                     for name in value.get('logins', [])}, lists={},
                     clusters=dict(enabled=False, include=[], exclude=[], scope='all'))
    return value


def encoded(value, name):
    if name.startswith('tracking-'):
        if len(value.get('people', {})) > 100 or len(value.get('lists', {})) > 50 or any(
                len(members) > 100 for members in value.get('lists', {}).values()):
            raise ValueError('Combined tracking exceeds 100 people, 50 lists or 100 members per list; no files changed.')
    raw = json.dumps(value, ensure_ascii=False, indent=2)+'\n'
    if len(raw.encode()) > 64000:
        raise ValueError('Combined preference is too large: '+name)
    return raw


def preserve(name, raw):
    base = Path(os.environ.get('XDG_STATE_HOME', str(Path.home()/'.local/state')))
    folder = base/'42sg-campus-lan'/'backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    private_write(folder/name, raw)


def copy_preferences(source, target, mode=None, local_first=False):
    """Plan and validate every file before changing any destination."""
    if mode not in (None, 'combine', 'overwrite'):
        raise ValueError('Choose combine (append) or overwrite.')
    pending = []
    for path in sorted(source.iterdir()):
        if not allowed(path.name):
            continue
        raw = private_read(path)
        incoming = decode(raw, path.name)
        dst = target/path.name
        old = None
        if dst.exists() or dst.is_symlink():
            old = private_read(dst)
            existing = decode(old, path.name)
            if existing == incoming:
                continue
            if mode is None:
                raise PreferenceConflict('Different preference already exists: '+path.name+
                    '. Choose combine (append friends/lists; keep local scalar choices) or overwrite (use incoming folder).')
            if mode == 'combine':
                raw = encoded(combine(incoming, existing) if local_first else combine(existing, incoming), path.name)
        # Validate size/limits even when the chosen mode replaces the file.
        encoded(decode(raw, path.name), path.name)
        if raw != old:
            pending.append((dst, raw, old))
    for dst, raw, old in pending:
        if old is not None:
            preserve(dst.name, old)
    for dst, raw, old in pending:
        private_write(dst, raw)
    return len(pending)


def storage(target, mode=None):
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
    if mode == 'overwrite':
        # Incoming folder wins; retain local-only files because overwrite is per file.
        copy_preferences(target, source, mode='overwrite')
    copy_preferences(source, target, mode=mode, local_first=True)
    temporary = local / ('.preferences-' + secrets.token_hex(8))
    try:
        temporary.symlink_to(target, target_is_directory=True)
        os.replace(temporary, link)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def perform(action, path=None, mode=None):
    if action == 'storage':
        return str(storage(path, mode) if path is not None else root())
    if path is None:
        raise ValueError('Supply a folder path.')
    if action == 'resolve':
        return resolve(path, mode)
    if action == 'export':
        target = directory(path, create=True)
        count = copy_preferences(root(), target, mode)
    elif action == 'import':
        source = directory(path, portable=True)
        count = copy_preferences(source, directory(root(), create=True), mode)
    else:
        raise ValueError('Use storage, export or import.')
    return f'{count} preference files {action}ed. Mode: {mode or "preserve existing"}. Replaced files backed up locally under XDG_STATE_HOME/42sg-campus-lan/backups.'


def resolve(path, mode=None):
    """Resolve only allowlisted portable JSON conflicts in a chosen Git folder."""
    folder = directory(path, portable=True)
    def git(*args):
        return subprocess.run(['git', '-C', str(folder), *args], check=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
    try:
        top = Path(os.fsdecode(git('rev-parse', '--show-toplevel')).strip())
    except subprocess.CalledProcessError as error:
        raise ValueError('Choose a portable settings folder inside a Git repository.') from error
    prefix = folder.relative_to(top).as_posix()+'/'
    entries = git('diff', '--name-only', '--diff-filter=U', '-z', '--', '.').split(b'\0')
    pending = []
    for item in filter(None, entries):
        relative = os.fsdecode(item)
        name = relative.removeprefix(prefix)
        if not relative.startswith(prefix) or not allowed(name):
            raise ValueError('Refusing conflict outside portable settings: '+relative)
        if mode not in ('combine', 'overwrite'):
            raise PreferenceConflict('Git conflict: '+name+'. Choose /settings resolve FOLDER combine|overwrite; overwrite selects incoming Git version.')
        try:
            ours = decode(git('show', ':2:'+relative), name)
            theirs = decode(git('show', ':3:'+relative), name)
        except subprocess.CalledProcessError as error:
            raise ValueError('Delete/modify conflict needs manual Git review: '+name) from error
        raw = encoded(combine(ours, theirs) if mode == 'combine' else theirs, name)
        pending.append((folder/name, relative, raw, private_read(folder/name)))
    for dst, relative, raw, old in pending:
        preserve(dst.name, old)
    for dst, relative, raw, old in pending:
        private_write(dst, raw)
        git('add', '--', str(dst))
    return f'{len(pending)} Git preference conflicts resolved and staged. Review and commit in the private repository; nothing pushed.'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('storage', 'export', 'import', 'resolve'))
    parser.add_argument('path', nargs='?')
    parser.add_argument('--mode', choices=('combine', 'overwrite'))
    args = parser.parse_args()
    try:
        try:
            result = perform(args.action, args.path, args.mode)
        except PreferenceConflict as error:
            if args.mode is not None or not sys.stdin.isatty():
                raise
            print(error)
            choice = input('Combine/append, overwrite, or cancel? [combine/overwrite/cancel] ').strip().lower()
            if choice in ('append', 'a', 'c'):
                choice = 'combine'
            if choice not in ('combine', 'overwrite'):
                parser.exit(1, 'Cancelled; preferences unchanged.\n')
            result = perform(args.action, args.path, choice)
        print(result)
    except (OSError, ValueError, EOFError, subprocess.SubprocessError) as error:
        parser.exit(1, str(error) + '\n')


if __name__ == '__main__':
    main()

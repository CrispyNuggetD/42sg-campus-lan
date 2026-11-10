"""Private local display names; explicit bounded campus-list refresh only."""
import argparse
from datetime import datetime, timezone
import json
import os
import stat
from pathlib import Path
import re
import unicodedata
import urllib.error

from .auth import AuthError, private_read, private_write
from .avatar_cache import cache_root

MAX_PAGES = 20


def cache_path():
    return cache_root().parent / 'student-names' / 'names.json'


def clean_name(value):
    if not isinstance(value, str):
        return ''
    return ' '.join(''.join(' ' if unicodedata.category(c).startswith('C') else c for c in value).split())[:120]


def display_name(user):
    for value in (user.get('usual_full_name'), user.get('displayname'),
                  ' '.join(str(value or '') for value in (user.get('usual_first_name') or user.get('first_name'), user.get('last_name'))),
                  ' '.join(str(user.get(k) or '') for k in ('first_name', 'last_name'))):
        name = clean_name(value)
        if name and name.casefold() != str(user.get('login', '')).casefold():
            return name
    return ''


def cached_name(login):
    """Offline lookup only; an absent/invalid cache simply leaves the login."""
    try:
        data = json.loads(private_read(cache_path()))
        if data.get('schema') != 1 or data.get('campus_id') != 64:
            return ''
        return clean_name(data['names'].get(login.lower()))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return ''


def refresh():
    from .access import Policy
    from .campus_info import API, load
    Policy().local_operator()
    directory = load()
    if not directory or not isinstance(directory.get('students'), list):
        raise ValueError('Existing approved Singapore directory required.')
    approved = {s['id']: s['login'].lower() for s in directory['students']
                if isinstance(s, dict) and type(s.get('id')) is int
                and isinstance(s.get('login'), str)
                and re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', s['login'])}
    if not approved:
        raise ValueError('Existing directory has no valid accounts.')
    path = cache_path().expanduser().resolve()
    if any((p / '.git').exists() for p in (path.parent, *path.parent.parents)):
        raise ValueError('Name cache must stay outside Git repositories.')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Name cache directory must be owned by you and mode 700; no API calls made.')
    api = API()
    original = api.opener.open
    # Stop on provider rate limits immediately; no long retry loop for this job.
    def bounded_open(request, *args, **kwargs):
        try:
            return original(request, *args, **kwargs)
        except urllib.error.HTTPError as error:
            if error.code == 429 or 500 <= error.code < 600:
                raise AuthError('Name refresh stopped: HTTP %d; Retry-After %s. Previous cache preserved.' %
                                (error.code, error.headers.get('Retry-After', 'unspecified'))) from None
            raise
    api.opener.open = bounded_open
    names = {}
    for page in range(1, MAX_PAGES + 1):
        users = api.get('campus/64/users', **{'page[number]': page, 'page[size]': 100})
        if not isinstance(users, list) or len(users) > 100:
            raise ValueError('Invalid campus page; previous name cache preserved.')
        for user in users:
            if not isinstance(user, dict):
                raise ValueError('Invalid campus account; previous name cache preserved.')
            uid = user.get('id')
            login = approved.get(uid) if type(uid) is int else None
            raw_login = user.get('login')
            if login and isinstance(raw_login, str) and raw_login.lower() == login:
                name = display_name(user)
                if name:
                    if login in names and names[login] != name:
                        raise ValueError('Conflicting campus names; previous cache preserved.')
                    names[login] = name
        if len(users) < 100:
            break
    else:
        raise ValueError('Name refresh reached its 20-page cap; previous cache preserved.')
    result = dict(schema=1, campus_id=64, generated_at=datetime.now(timezone.utc).isoformat(),
                  source='campus/64/users', directory_accounts=len(approved),
                  pages=page, names=names)
    raw = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if len(raw.encode()) > 65536:
        raise ValueError('Name cache exceeds private reader size; previous cache preserved.')
    private_write(path, raw)
    return dict(directory_accounts=len(approved), named_accounts=len(names),
                missing_logins=sorted(set(approved.values()) - names.keys()),
                campus_GET_requests=page, cache_path=str(path))


def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        print(json.dumps(refresh(), indent=2))
    except (AuthError, OSError, ValueError, KeyError, TypeError) as error:
        raise SystemExit(str(error)) from None


if __name__ == '__main__':
    main()

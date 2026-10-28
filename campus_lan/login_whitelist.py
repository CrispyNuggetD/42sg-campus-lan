"""Local input validation only; this directory never grants API access or identity."""
import difflib
import json
import os
from pathlib import Path
import re
from .campus_info import directory

PATTERN=re.compile(r'[A-Za-z0-9_.-]{1,32}')
PHOTO_SELECTOR_MESSAGE='Photo batches need explicit Intra logins. /tool all and cohort selectors are unsupported.'


def unsupported_photo_selector(names):
    parts=[name.lower() for name in names if isinstance(name,str)]
    return any(name=='all' or re.fullmatch(r'cohort\d*',name) for name in parts)


class WhitelistUnavailable(ValueError):
    pass


def allowed_logins():
    """Prefer the private campus JSON; optionally use an explicit text whitelist."""
    configured=os.environ.get('LAN42_INTRA_WHITELIST')
    root=directory()
    source=Path(configured).expanduser() if configured else root/'singapore.json'
    if not configured and not source.exists():source=root/'singapore_intra.txt'
    try:
        if source.stat().st_size>8*1024*1024:raise ValueError()
        raw=source.read_text()
        if source.suffix.lower()=='.json':
            records=json.loads(raw)['students']
            names=[row['login'] for row in records]
        else:names=raw.split()
        if not names or any(not isinstance(n,str) or not PATTERN.fullmatch(n) for n in names):raise ValueError()
    except (OSError,ValueError,KeyError,TypeError):
        raise WhitelistUnavailable('Singapore login whitelist unavailable or invalid. Use private singapore.json or singapore_intra.txt in the campus-data folder, or set LAN42_INTRA_WHITELIST to your local file.') from None
    return {n.lower() for n in names}


def validate_logins(names):
    names=list(dict.fromkeys(names))
    if any(not isinstance(n,str) or not PATTERN.fullmatch(n) for n in names):
        raise ValueError('Invalid Intra login format; use logins or supported selectors.')
    names=list(dict.fromkeys(n.lower() for n in names))
    if not names:return []
    allowed=allowed_logins()
    unknown=[n for n in names if n not in allowed]
    if unknown:
        message='Not in the local Singapore whitelist: '+', '.join(unknown[:5])
        if len(unknown)>5:message+=' (and '+str(len(unknown)-5)+' more)'
        if len(unknown)==1:
            near=difflib.get_close_matches(unknown[0],sorted(allowed),n=1,cutoff=0.7)
            if near:message+='. Did you mean '+near[0]+'?'
        raise ValueError(message)
    return names

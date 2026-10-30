"""Local input validation only; this directory never grants API access or identity."""
import difflib
import json
import os
from pathlib import Path
import re
from .campus_info import directory
from .intake_selectors import intake_number

PATTERN=re.compile(r'[A-Za-z0-9_.-]{1,32}')
SG_SELECTORS=frozenset(('all','sg','42sg'))
PHOTO_SELECTOR_MESSAGE='Choose Cache all logins for all/sg/42sg/cohort selectors; a single photo lookup needs one Intra login.'


def unsupported_photo_selector(names):
    parts=[name.lower() for name in names if isinstance(name,str)]
    return any(name in SG_SELECTORS or re.fullmatch(r'(?:cohort|intake|i)\d*',name) for name in parts)


def expand_photo_targets(names):
    """Expand local cohort selectors, never interpreting a bare number as one."""
    result=[]
    for raw in names:
        value=raw.lower() if isinstance(raw,str) else ''
        if value in ('cohort','intake'):raise ValueError('Use cohort1 as one word; "cohort 1" is not a photo selector.')
        number=intake_number(value)
        if value in SG_SELECTORS or number is not None:
            from .campus_info import load
            data=load()
            if not isinstance(data,dict) or not isinstance(data.get('students'),list):
                raise ValueError('Photo selectors need the local private Singapore student cache.')
            cohort=number
            selected=[row.get('login') for row in data['students'] if isinstance(row,dict) and (cohort is None or row.get('cohort')==cohort)]
            if not selected:raise ValueError('No students found for '+value+'.')
            result.extend(validate_logins(selected))
        else:result.append(raw)
    return list(dict((name.lower() if isinstance(name,str) else name,name) for name in result).values())


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

"""Resolve explicit profile arguments locally; browser login stays in the browser."""
import re
from .campus_info import load
from .login_whitelist import SG_SELECTORS,validate_logins
from .intake_selectors import intake_number


def resolve(arguments):
    arguments=list(arguments);bulk='--open-many' in arguments
    arguments=[a for a in arguments if a!='--open-many']
    if not arguments:raise ValueError('Use /profile LOGIN...')
    names=[]
    for argument in arguments:
        if argument.lower() in SG_SELECTORS or intake_number(argument) is not None:
            data=load()
            if not data:raise ValueError('Campus cache unavailable on this computer.')
            cohort=None if argument.lower() in SG_SELECTORS else intake_number(argument)
            names.extend(s['login'] for s in data['students'] if cohort is None or s.get('cohort')==cohort)
        elif re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',argument):names.append(argument.lower())
        else:raise ValueError('Use Intra logins, all, or cohort4; no shell expressions.')
    names=validate_logins(names)
    if any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',n) for n in names):raise ValueError('Invalid cached login.')
    if len(names)>10 and not bulk:raise ValueError(str(len(names))+' tabs selected. To open them explicitly, use /profile --open-many '+' '.join(arguments))
    return ['https://profile-v3.intra.42.fr/users/'+name for name in names]

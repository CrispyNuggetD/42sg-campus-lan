"""Fixed, bounded audio windows. No system-volume, process or command controls."""
import datetime as dt
import json
import math
import re
import time
from .auth import private_write,config_dir
from .release_notices import state_file

SGT=dt.timezone(dt.timedelta(hours=8))
MAX_DURATION=12*3600
FIELDS={'schema','scope','campus_id','issued','windows'}


def path():return config_dir()/'campus-audio-quiet.json'


def defaults(now):
    today=dt.datetime.fromtimestamp(now,SGT).date();result=[]
    for offset in range(8):
        day=today+dt.timedelta(days=offset)
        hour=15 if day.weekday()==2 else 13 if day.weekday()==5 else None
        if hour is None:continue
        start=dt.datetime.combine(day,dt.time(hour),SGT).timestamp();end=start+3*3600
        if end>now:result.append(dict(start=start,end=end,reason='default'))
    return result


def valid(state,now,receiving=False):
    if not isinstance(state,dict) or set(state)!=FIELDS:return False
    if type(state['schema']) is not int or state['schema']!=1 or state['scope']!='lan42-audio' or type(state['campus_id']) is not int or state['campus_id']!=64:return False
    issued=state['issued']
    if type(issued) not in (int,float) or not math.isfinite(issued) or issued>now+120 or (receiving and issued<now-120):return False
    if not isinstance(state['windows'],list) or len(state['windows'])>16:return False
    for row in state['windows']:
        if not isinstance(row,dict) or set(row)!={'start','end','reason'} or row['reason'] not in ('exam','manual'):return False
        if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ('start','end')):return False
        if not 0<row['end']-row['start']<=MAX_DURATION or row['start']<issued-MAX_DURATION or row['end']>issued+8*86400:return False
    return True


def accept(state,fingerprint,clock=time.time):
    now=clock()
    if not valid(state,now,True) or not isinstance(fingerprint,str) or not re.fullmatch('[a-f0-9]{64}',fingerprint):return False
    with state_file('campus-audio-quiet',per_computer=False) as (file,old):
        if old.get('fingerprint')==fingerprint and type(old.get('issued')) in (int,float) and old['issued']>state['issued']:return False
        state=dict(state,windows=[w for w in state['windows'] if w['end']>now])
        private_write(file,json.dumps(dict(state,fingerprint=fingerprint)))
    return True


def schedule(clock=time.time):
    now=clock();result=defaults(now)
    try:
        with state_file('campus-audio-quiet',per_computer=False) as (file,state):
            fingerprint=state.get('fingerprint');payload={k:v for k,v in state.items() if k!='fingerprint'}
            from .auth_client import load_trust,fingerprint as trusted_fingerprint
            if not valid(payload,now):return result
            pending=[w for w in payload['windows'] if w['end']>now]
            if pending!=payload['windows']:
                state['windows']=pending;private_write(file,json.dumps(state))
            if fingerprint==trusted_fingerprint(load_trust()):result+=pending
    except (OSError,ValueError,KeyError,TypeError,AttributeError):pass
    return sorted(result,key=lambda w:w['start'])


def active(clock=time.time):
    now=clock()
    return any(w['start']<=now<w['end'] for w in schedule(clock))


def browser_environment():
    from .auth_client import load_trust,fingerprint
    try:pin=fingerprint(load_trust())
    except (OSError,ValueError):pin=''
    return dict(LAN42_AUDIO_QUIET_PATH=str(path()),LAN42_AUDIO_QUIET_FINGERPRINT=pin)


class QuietNotices:
    def __init__(self):self.seen=set();self.was_quiet=False;self.resume=False
    def tick(self,rows,now,audible=True):
        rows=[w for w in rows if w['end']>now];live={(w['start'],w['end']) for w in rows}
        self.seen &= live;lines=[]
        for row in rows:
            key=(row['start'],row['end'])
            if 0<row['start']-now<=1800 and key not in self.seen:
                self.seen.add(key)
                lines.append('LAN42 audio will auto-mute at '+dt.datetime.fromtimestamp(row['start'],SGT).strftime('%a %d %b %H:%M SGT')+' for an exam quiet window; other apps/system output are unaffected.')
        quiet=any(w['start']<=now<w['end'] for w in rows)
        if quiet and not self.was_quiet:
            self.resume=audible;lines.append('LAN42 exam quiet is active. App audio is suppressed; system volume is unchanged.')
        if not quiet and self.was_quiet and audible:lines.append('LAN42 exam quiet ended. Your existing sound choices apply again; no system volume was changed.')
        self.was_quiet=quiet
        return lines

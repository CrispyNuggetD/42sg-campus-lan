"""Current aggregate campus occupancy only; no student identities in status data."""
import json
import math
import time
from .auth import config_dir,private_read,private_write


def validate_status(value):
    if not isinstance(value,dict) or set(value)!={'total','c1','c2','updated_at'}:return None
    if any(type(value[k]) is not int or not 0<=value[k]<=10000 for k in ('total','c1','c2')):return None
    if value['total']!=value['c1']+value['c2']:return None
    stamp=value['updated_at']
    if type(stamp) not in (int,float) or not math.isfinite(stamp) or stamp<=0:return None
    return dict(value)


def summarize(players,stamp):
    from .lobby_view import seat
    people={}
    for index,player in enumerate(players):
        location=seat(player);name=player.get('name')
        if not location or not isinstance(name,str):continue
        record=str(player.get('id',''))
        priority=(int(record) if record.isdecimal() else 0,index)
        name=name.lower()
        if name not in people or priority>people[name][0]:people[name]=(priority,location[0])
    c1=sum(cluster==1 for _,cluster in people.values())
    c2=sum(cluster==2 for _,cluster in people.values())
    return validate_status(dict(total=c1+c2,c1=c1,c2=c2,updated_at=stamp))


def cached_status():
    from .clusters import cached_snapshot
    try:players,stamp=cached_snapshot()
    except ValueError:return None
    return summarize(players,stamp)


def publish_status(value):
    value=validate_status(value)
    if value is None:raise ValueError('Invalid campus occupancy status')
    private_write(config_dir()/'campus-status.json',json.dumps(value))


def local_status():
    from .access import Policy
    Policy().local_operator()
    try:return validate_status(json.loads(private_read(config_dir()/'campus-status.json')))
    except (OSError,ValueError):return None


def format_status(value,now=None):
    value=validate_status(value)
    if value is None:return 'Campus: unavailable'
    age=max(0,int((time.time() if now is None else now)-value['updated_at']))
    age_text='stale ('+str(age//60)+'m)' if age>120 else str(age)+'s ago'
    return f"Campus: {value['total']} online (C1:{value['c1']} | C2:{value['c2']}) · {age_text}"

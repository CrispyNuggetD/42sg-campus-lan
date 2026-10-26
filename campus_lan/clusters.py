"""On-demand campus API occupancy, distinct from LAN42 peer presence."""
import re
import threading
import time
from .campus_info import API,load

_lock=threading.Lock()
_snapshot=None
_stamp=0


def normalize_locations(records):
    result=[];seen=set()
    for record in records:
        name=(record.get('user') or {}).get('login');host=record.get('host','')
        if record.get('end_at') is not None or not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',name):continue
        if not isinstance(host,str) or not re.fullmatch(r'c[12]r[0-9]{1,2}s[0-9]{1,2}',host) or (name,host) in seen:continue
        seen.add((name,host))
        result.append(dict(id=str(record.get('id','')),name=name,seat=host,verified=True))
    return result


def snapshot():
    global _snapshot,_stamp
    with _lock:
        if _snapshot is not None and time.time()-_stamp<30:return _snapshot,_stamp
        from .access import SG_CAMPUS_ID
        api=API();campus={'id':SG_CAMPUS_ID}
        records=api.pages('campus/'+str(int(campus['id']))+'/locations',**{'filter[active]':'true'})
        _snapshot=normalize_locations(records);_stamp=time.time()
        return _snapshot,_stamp

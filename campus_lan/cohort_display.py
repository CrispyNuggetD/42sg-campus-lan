"""Local-only cohort decoration from the existing private Singapore cache."""
import json
import re
from .campus_info import directory


def cohort_index():
    path=directory()/'singapore.json'
    try:
        if path.stat().st_size>8*1024*1024:return {}
        data=json.loads(path.read_text())
        rows=data.get('students',[])
        if not isinstance(rows,list) or len(rows)>5000:return {}
        result={};conflicts=set()
        for row in rows:
            if not isinstance(row,dict):continue
            name=row.get('login');number=row.get('cohort')
            if (isinstance(name,str) and re.fullmatch(r'[a-zA-Z0-9_.-]{1,32}',name)
                    and type(number) is int and 1<=number<=99):
                name=name.lower()
                if name in conflicts:continue
                if name in result and result[name]!=number:
                    result.pop(name);conflicts.add(name)
                else:result[name]=number
        return result
    except (OSError,ValueError,AttributeError):return {}

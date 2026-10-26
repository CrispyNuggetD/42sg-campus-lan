"""Bounded, host-cached Singapore calendar reads. Upstream text is never executable."""
import asyncio
import datetime as dt
import re
import time
from .auth import AuthError

MAX_DURATION=12*3600


def stamp(value):
    if not isinstance(value,str) or len(value)>40:raise ValueError('Invalid calendar time.')
    value=dt.datetime.fromisoformat(value.replace('Z','+00:00'))
    if value.tzinfo is None:raise ValueError('Calendar times need a timezone.')
    return value.timestamp()


def utc(value):return dt.datetime.fromtimestamp(value,dt.timezone.utc).isoformat().replace('+00:00','Z')


def windows(rows,exam_endpoint,now):
    result=[]
    for row in rows:
        if not isinstance(row,dict):continue
        if row.get('cancelled') is True or row.get('is_cancelled') is True or row.get('status') in ('cancelled','canceled','deleted'):continue
        ids=[]
        if 'campus_id' in row:ids.append(row['campus_id'])
        if isinstance(row.get('campus_ids'),list):ids+=row['campus_ids']
        campus=row.get('campus',[])
        if isinstance(campus,dict):campus=[campus]
        if isinstance(campus,list):ids += [c.get('id') for c in campus if isinstance(c,dict)]
        if ids and 64 not in ids:continue
        if not exam_endpoint:
            kind=row.get('kind','');name=row.get('name','')
            if kind not in ('exam','exams') and not (kind in ('','other','event') and isinstance(name,str) and re.search(r'\bexam\b',name,re.I) and not re.search(r'\b(?:prep|preparation|workshop|training|practice|mock|briefing)\b',name,re.I)):continue
        try:start=stamp(row['begin_at']);end=stamp(row['end_at']) if row.get('end_at') else start+3*3600
        except (ValueError,KeyError,TypeError,OverflowError):continue
        if not 0<end-start<=MAX_DURATION or end<=now or start>now+7*86400:continue
        # Fixed exam buffers, no upstream free-text or URLs enter the wire state.
        result.append((start,end))
    return sorted(set(result))[:16]


class ExamQuiet:
    def __init__(self,host,api_factory=None,policy_factory=None,clock=time.time):
        self.host=host;self.api_factory=api_factory;self.policy_factory=policy_factory;self.clock=clock
        self.api=None;self.intervals=[];self.sources={'exams':[],'events':[]};self.manual_until=0;self.manual_start=0;self.refreshed=None
        self.coverage=dict(exams='not_checked',events='not_checked');self.next_refresh=0

    def refresh(self):
        from .file_sharing.security import campus_ip
        from .access import Policy
        campus_ip(self.host)
        (self.policy_factory or Policy)().local_operator()
        if self.api is None:
            from .campus_info import API
            self.api=(self.api_factory or API)()
        now=self.clock();ok=False
        for kind in ('exams','events'):
            try:
                records=[]
                for page in range(1,4):
                    batch=self.api.get('campus/64/'+kind,**{'range[begin_at]':utc(now-86400)+','+utc(now+7*86400),
                        'page[number]':page,'page[size]':100})
                    if not isinstance(batch,list) or len(batch)>100:raise ValueError('Invalid calendar page.')
                    records+=batch
                    if len(batch)<100:break
                else:raise ValueError('Calendar page bound exceeded.')
                self.sources[kind]=windows(records,kind=='exams',now);self.coverage[kind]='ok';ok=True
            except (OSError,ValueError):self.coverage[kind]='unavailable'
        self.intervals=sorted({w for rows in self.sources.values() for w in rows if w[1]>now})[:16]
        if ok:self.refreshed=now
        # Keep still-valid last-known windows on API failure; never invent dates.
        self.intervals=[w for w in self.intervals if w[1]>now]
        self.next_refresh=now+3600

    async def run(self):
        from .audio_quiet import QuietNotices,defaults
        notices=QuietNotices()
        while True:
            now=self.clock()
            for line in notices.tick(defaults(now)+self.state()['windows'],now):print(line,flush=True)
            if self.clock()>=self.next_refresh:
                task=asyncio.create_task(asyncio.to_thread(self.refresh))
                try:await asyncio.shield(task)
                except asyncio.CancelledError:
                    await asyncio.gather(task,return_exceptions=True);raise
                except (OSError,ValueError):self.next_refresh=self.clock()+3600
            now=self.clock()
            for line in notices.tick(defaults(now)+self.state()['windows'],now):print(line,flush=True)
            await asyncio.sleep(15)

    def state(self):
        now=self.clock();self.intervals=[w for w in self.intervals if w[1]>now]
        self.sources={key:[w for w in rows if w[1]>now] for key,rows in self.sources.items()}
        rows=[dict(start=start,end=end,reason='exam') for start,end in self.intervals]
        if self.manual_until>now:rows.insert(0,dict(start=self.manual_start,end=self.manual_until,reason='manual'))
        else:self.manual_until=0
        return dict(schema=1,scope='lan42-audio',campus_id=64,issued=now,windows=rows[:16])

    def manual(self,minutes):
        if type(minutes) is not int or not 0<=minutes<=720:raise AuthError('Quiet mode accepts 0–720 minutes only.')
        self.manual_start=self.clock()
        self.manual_until=self.manual_start+minutes*60 if minutes else 0
        return dict(quiet=self.state())

    def schedule(self):
        self.state()
        return dict(campus_id=64,refreshed=self.refreshed,coverage=self.coverage,
                    windows=[dict(begin=utc(start),end=utc(end)) for start,end in self.intervals],
                    notice='Visible API entries only; unpublished/special exams may be absent. Precautionary SGT defaults: Wed 15–18 and every Sat 13–16, even if cancelled.')

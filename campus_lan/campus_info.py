"""Local campus directory; exports contain selected academic fields, no credentials.

Run `python3 -m campus_lan.campus_info refresh` on the API owner's computer.
The JSON/Markdown destination is the owner's private workspace, never public Git.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from .auth import config_dir, private_read, provider_tls_context, NoRedirect, AuthError


def directory():
    return Path(os.environ.get('LAN42_CAMPUS_DATA', str(Path.home()/'Documents/42_Singapore_SUTD_hnah_private/42/data/campus')))


def load():
    try:return json.loads((directory()/'singapore.json').read_text())
    except (OSError, ValueError):return None


def matches_filters(student, filters):
    # Whitelisted comparisons only: no SQL execution, eval, joins or file access.
    for expression in filters:
        match=re.fullmatch(r'(cohort|level|status|active|login)(>=|<=|!=|=|>|<)([A-Za-z0-9_.-]{1,32})',expression,re.I)
        if not match:raise ValueError('Filters: cohort=4 level>=2 status=ALUMNI active=true login=hnah; combine with AND.')
        field,op,value=match.groups();field=field.lower();actual=student.get(field)
        if field in ('cohort','level'):
            try:value=float(value);actual=float(actual)
            except (ValueError,TypeError):return False
        else:actual=str(actual).lower();value=value.lower()
        if not {'=':lambda:actual==value,'!=':lambda:actual!=value,'>':lambda:actual>value,'<':lambda:actual<value,'>=':lambda:actual>=value,'<=':lambda:actual<=value}[op]():return False
    return True


def random_profiles(number, excluded, cohorts=(), filters=()):
    data=load()
    if not data:raise ValueError('Campus cache missing. Run python3 -m campus_lan.campus_info refresh on the API host.')
    candidates=[s for s in data['students'] if s['login'].lower() not in {x.lower() for x in excluded} and (not cohorts or s.get('cohort') in cohorts) and matches_filters(s,filters)]
    if number is None:number=min(50,len(candidates))
    if not 1<=number<=50 or number>len(candidates):raise ValueError('Not enough cached students, or count outside 1–50.')
    return [dict(login=s['login'],avatar=None) for s in random.sample(candidates,number)]


class API:
    def __init__(self):
        settings=json.loads(private_read(config_dir()/'auth-server.json'))
        self.settings=settings
        self.last=0
        self.token=None
        self.expires=0
        self.opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=provider_tls_context()),NoRedirect())

    def request(self,url,data=None,authenticated=True):
        if authenticated and (not self.token or time.monotonic()>=self.expires):
            body=urllib.parse.urlencode(dict(grant_type='client_credentials',client_id=self.settings['client_id'],client_secret=self.settings['client_secret'])).encode()
            result=self.request('https://api.intra.42.fr/oauth/token',body,False)
            self.token=result['access_token'];self.expires=time.monotonic()+float(result.get('expires_in',300))-30
        for attempt in range(5):
            from .api_pacing import wait
            wait()
            self.last=time.monotonic()
            headers={'Accept':'application/json','User-Agent':'LAN42-campus-directory/1.0'}
            if authenticated:headers['Authorization']='Bearer '+self.token
            if data is not None:headers['Content-Type']='application/x-www-form-urlencoded'
            try:
                with self.opener.open(urllib.request.Request(url,data=data,headers=headers),timeout=30) as response:
                    raw=response.read(16*1024*1024+1)
                    if len(raw)>16*1024*1024:raise ValueError('API response too large')
                    return json.loads(raw)
            except urllib.error.HTTPError as e:
                if e.code==429 or 500<=e.code<600:
                    delay=max(5*2**attempt,min(300,float(e.headers.get('Retry-After','0'))))
                    time.sleep(delay);continue
                raise AuthError('Campus API request rejected (HTTP '+str(e.code)+').') from None
        raise AuthError('Campus API remains busy; refresh stopped without replacing the last complete export.')

    def get(self,path,**params):
        return self.request('https://api.intra.42.fr/v2/'+path+('?' + urllib.parse.urlencode(params) if params else ''))

    def pages(self,path,**params):
        result=[]
        for page in range(1,501):
            batch=self.get(path,**params,**{'page[number]':page,'page[size]':100})
            if not isinstance(batch,list):raise ValueError('Expected paginated API list')
            result.extend(batch)
            if len(batch)<100:return result
        raise ValueError('Pagination safety limit reached')


def summarize(data):
    students=data['students']
    starts=Counter(s['intake'] for s in students)
    # Dense shared starts identify intake batches. Isolated starts often belong
    # to transfers/staff; leave those unassigned rather than invent a cohort.
    batches=sorted(start for start,n in starts.items() if n>=10 and start!='unknown')
    numbers={start:i+1 for i,start in enumerate(batches)}
    for student in students:student['cohort']=numbers.get(student['intake'])
    data['cohort_basis']='Inferred: shared 42cursus start dates with at least 10 students, numbered chronologically. Other starts unassigned; not official cohort metadata.'
    data['cohorts']=[]
    for start in batches:
        group=[s for s in students if s['intake']==start]
        data['cohorts'].append(dict(cohort=numbers[start],intake=start,count=len(group),statuses=dict(Counter(s['status'] for s in group)),active_accounts=sum(s.get('active') is True for s in group)))
    data['unassigned_cohort_count']=sum(s['cohort'] is None for s in students)
    data['account_activity_counts']={'true':sum(s.get('active') is True for s in students),'false':sum(s.get('active') is False for s in students),'unknown':sum(s.get('active') is None for s in students)}
    return data


def render(data):
    def cell(v):return str(v if v is not None else 'unknown').replace('|','\\|').replace('\n',' ')
    lines=['# 42 Singapore campus directory','', 'Generated: '+data['generated_at'], '',
           data['cohort_basis']+' Piscine month/year is listed separately. Account active? is an API account flag, not confirmation of current enrollment. BLACKHOLED/FREEZE states are unavailable in these responses; past deadlines do not establish either state. No emails, phone numbers, tokens or private raw profiles are exported.', '',
           '| Campus | ID | Cached students |', '| --- | --- | --- |', f"| {cell(data['campus'].get('name'))} | {data['campus']['id']} | {len(data['students'])} |",'',
           '| Inferred cohort | Intake start | Students | Active accounts | API statuses |', '| --- | --- | ---: | ---: | --- |']
    for cohort in data['cohorts']:
        lines.append('| '+str(cohort['cohort'])+' | '+cohort['intake']+' | '+str(cohort['count'])+' | '+str(cohort['active_accounts'])+' | '+cell(', '.join(k+': '+str(v) for k,v in cohort['statuses'].items()))+' |')
    lines+=['','Unassigned cohort: '+str(data['unassigned_cohort_count'])+' students. Account active? counts: '+str(data['account_activity_counts']), '', '| Campus field | API value |','| --- | --- |']
    lines += ['| '+cell(k)+' | '+cell(v)+' |' for k,v in data['campus'].items()]
    lines+=['','| Login | Inferred cohort | Intake start | Piscine | Status (API) | Account active? | Level | Blackhole deadline (API) | Cursus end |','| --- | --- | --- | --- | --- | --- | ---: | --- | --- |']
    for s in data['students']:lines.append('| '+' | '.join(cell(s.get(k)) for k in ('login','cohort','intake','piscine','status','active','level','blackholed_at','end_at'))+' |')
    return '\n'.join(lines)+'\n'


def normalize(user):
    cursus=next((c for c in user.get('cursus_users',[]) if c.get('cursus_id')==21 or (c.get('cursus') or {}).get('slug')=='42cursus'),None)
    if not cursus:return None
    # Keep explicit enum/status values only. Never infer BLACKHOLED/FREEZE from
    # inactive flags, missing fields, level, or an elapsed blackhole deadline.
    status=cursus.get('status') or user.get('status')
    if status is None and user.get('alumni?') is True:status='ALUMNI'
    start=cursus.get('begin_at')
    return dict(id=user['id'],login=user['login'],intake=(start or 'unknown')[:10],begin_at=start,
                piscine=' '.join(str(user.get(k) or 'unknown') for k in ('pool_month','pool_year')),
                status=status or 'UNKNOWN',active=user.get('active?'),alumni=user.get('alumni?'),
                level=cursus.get('level'),blackholed_at=cursus.get('blackholed_at'),end_at=cursus.get('end_at'))


def refresh():
    import fcntl
    target=directory();target.mkdir(parents=True,exist_ok=True,mode=0o700)
    with (target/'.refresh.lock').open('w') as lock:
        try:fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise ValueError('Campus refresh already running') from None
        api=API()
        campuses=api.pages('campus')
        campus=next((c for c in campuses if 'singapore' in (c.get('name','')+' '+c.get('slug','')).lower()),None)
        if not campus:raise ValueError('Singapore campus not found')
        print('Found Singapore campus '+str(campus['id'])+'; fetching paginated users at <1 request/sec.',flush=True)
        users=api.pages('campus/'+str(campus['id'])+'/users')
        print('Received '+str(len(users))+' campus records; normalizing academic fields.',flush=True)
        # Bulk cursus enrollments avoid a separate request for every campus user.
        # Intersect against the campus list even when the server accepts a campus
        # filter: unrelated-campus profiles must never enter the local export.
        campus_ids={u['id'] for u in users}
        enrollments=api.pages('cursus_users',**{'filter[campus_id]':campus['id'],'filter[cursus_id]':21})
        students=[]
        for enrollment in enrollments:
            user=enrollment.get('user') or {}
            if user.get('id') not in campus_ids or enrollment.get('cursus_id')!=21:continue
            student=normalize(dict(user,cursus_users=[enrollment]))
            if student:students.append(student)
        students=sorted({s['id']:s for s in students}.values(),key=lambda s:(s['intake'],s['login']))
        cohorts=[]
        for intake in sorted({s['intake'] for s in students}):
            group=[s for s in students if s['intake']==intake]
            cohorts.append(dict(intake=intake,count=len(group),statuses=dict(Counter(s['status'] for s in group))))
        data=dict(schema_version=1,generated_at=datetime.now(timezone.utc).isoformat(),campus={k:campus[k] for k in ('id','name','slug','country','city','website','active','public') if k in campus},
                  cohort_basis='42cursus begin_at date; inferred intake, not official cohort numbering',cohorts=cohorts,students=students,
                  status_counts=dict(Counter(s['status'] for s in students)))
        summarize(data)
        for name,content in [('singapore.json',json.dumps(data,indent=2)+'\n'),('singapore.md',render(data))]:
            temporary=target/(name+'.tmp');temporary.write_text(content);temporary.chmod(0o600);temporary.replace(target/name)
        print('Saved '+str(len(students))+' 42cursus students in '+str(target),flush=True)


def info_lines(query=''):
    data=load()
    if not data:return ['Campus cache missing. API host: python3 -m campus_lan.campus_info refresh']
    parts=query.split();page=1
    if parts and parts[-1].isdigit():page=max(1,int(parts.pop()))
    search=' '.join(parts).lower()
    rows=[s for s in data['students'] if not search or search in (s['login']+' '+s['intake']+' '+s['status']+' cohort'+str(s.get('cohort'))).lower()]
    lines=[data['campus']['name']+' · '+str(len(data['students']))+' cached 42cursus students · '+data['generated_at'],
           'Cohort numbers inferred from shared start dates; other starts unassigned. BLACKHOLED/FREEZE unavailable.',
           'Account active? '+str(data.get('account_activity_counts',{}))+' (not enrollment status)',
           'Statuses: '+', '.join(k+' '+str(v) for k,v in data['status_counts'].items()),
           '/info [login / cohort4 / intake-date / status] [PAGE] · 12 rows/page']
    if not search:
        lines+=['Cohort '+str(c['cohort'])+' (inferred) · '+c['intake']+': '+str(c['count'])+' students · '+', '.join(k+' '+str(v) for k,v in c['statuses'].items()) for c in data['cohorts']]
    lines+=['LOGIN          COHORT INTAKE       STATUS         ACTIVE? LEVEL  BLACKHOLE DEADLINE']
    lines += [f"{s['login']:<14} {str(s.get('cohort') or '?'):<6} {s['intake']:<12} {s['status']:<14} {str(s['active']):<7} {str(s['level']):<6} {s['blackholed_at'] or 'unknown'}" for s in rows[(page-1)*12:page*12]]
    lines+=['Page '+str(page)+' / '+str(max(1,(len(rows)+11)//12))+' · '+str(len(rows))+' matching students']
    return lines


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('action',choices=['refresh','info'],default='info',nargs='?');args=parser.parse_args()
    try:
        if args.action=='refresh':refresh()
        else:print('\n'.join(info_lines()))
    except (AuthError,OSError,ValueError,KeyError):
        parser.exit(1,'Campus refresh failed; last completed export preserved. Check local API configuration/access or retry later.\n')

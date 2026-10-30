"""Account-scoped clocks and schedules. No commands, audio or networking in saved data."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shlex
import time
from .auth import config_dir, private_read, private_write
from .preferences import settings_path

WEEKDAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')


class AmbiguousHour(ValueError):
    pass


def duration(value):
    if value.isdecimal():
        seconds = int(value)
    else:
        parts = re.findall(r'(\d+)([dhms])', value.lower())
        if not parts or ''.join(n+u for n,u in parts) != value.lower():
            raise ValueError('Use a duration such as 30m, 1h30m or 45s.')
        seconds = sum(int(n)*dict(d=86400,h=3600,m=60,s=1)[u] for n,u in parts)
    if not 1 <= seconds <= 366*86400:
        raise ValueError('Choose between 1 second and 366 days.')
    return seconds


def wall_time(value):
    value = value.lower()
    match = re.fullmatch(r'(\d{1,2})(?::(\d{2})(?::(\d{2}))?)?(am|pm)?', value)
    if match:
        hour, minute, second, period = match.groups()
        hour, minute, second = int(hour), int(minute or 0), int(second or 0)
        if period:
            if not 1 <= hour <= 12:raise ValueError('AM/PM hours must be 1–12.')
            hour = hour % 12 + (12 if period == 'pm' else 0)
        elif ':' not in value and 1 <= hour <= 12:
            raise AmbiguousHour(value)
    elif re.fullmatch(r'\d{4}|\d{6}', value):
        hour, minute = int(value[:2]), int(value[2:4])
        second = int(value[4:]) if len(value) == 6 else 0
    else:
        raise ValueError('Use 8am, 8pm, 08:00, 16:25:32 or 162532.')
    if not 0 <= hour < 24 or not 0 <= minute < 60 or not 0 <= second < 60:
        raise ValueError('Invalid clock time.')
    return [hour, minute, second]


def offset(value):
    value=value.upper()
    if value in ('Z','+Z','UTC','GMT'):return 0
    if value=='SGT':return 480
    if value.startswith(('UTC','GMT')):value=value[3:]
    compact=re.fullmatch(r'([+-])(\d{2})(\d{2})',value)
    if compact:value=compact[1]+str(int(compact[2]))+':'+compact[3]
    if re.fullmatch(r'[+-]?\d{1,2}\.\d{1,6}',value):
        total=Decimal(value)*60
        if total!=int(total):raise ValueError('Timezone must resolve to whole minutes; use +4:30.')
        total=int(total)
    else:
        match = re.fullmatch(r'([+-]?)(\d{1,2})(?::(\d{2}))?', value)
        if not match:raise ValueError('Use a timezone such as +8, +4.5, +4:30 or Z (UTC).')
        sign, hours, minutes = match.groups()
        minutes = int(minutes or 0)
        if minutes >= 60:raise ValueError('Invalid timezone offset.')
        total = (int(hours)*60+minutes)*(-1 if sign == '-' else 1)
    if not -720 <= total <= 840:raise ValueError('Timezone range is GMT-12 to GMT+14.')
    return total


def split_zone(value):
    match=re.fullmatch(r'(.+?)(\+?Z|UTC|GMT|SGT|(?:UTC|GMT)?[+-](?:\d{4}|\d{1,2}(?:\.\d{1,6}|:\d{2})?))',value,re.I)
    return (match[1],match[2]) if match else (value,None)


def wall_spec(value, default):
    clock,zone=split_zone(value)
    minutes=offset(zone) if zone else default
    try:return wall_time(clock),minutes
    except AmbiguousHour:raise AmbiguousHour(value) from None


def with_period(value,period):
    clock,zone=split_zone(value)
    return clock+period+(zone or '')


def zone_label(minutes):
    if minutes==0:return 'UTC'
    return (
        'GMT'+('+' if minutes >= 0 else '-')+str(abs(minutes)//60)+
        (f':{abs(minutes)%60:02}' if abs(minutes)%60 else ''))


def next_wall(clock, days, now, minutes=480):
    local = datetime.fromtimestamp(now, timezone(timedelta(minutes=minutes)))
    for distance in range(8):
        day = local + timedelta(days=distance)
        candidate = day.replace(hour=clock[0], minute=clock[1], second=clock[2], microsecond=0)
        if candidate.weekday() in days and candidate.timestamp() > now:
            return candidate.timestamp()
    raise ValueError('No scheduled day selected.')


def alarm_timestamp(alarm, display_offset=None):
    minutes=display_offset if display_offset is not None else 0 if alarm.get('explicit_utc',alarm['zone']==0) else 480
    return datetime.fromtimestamp(alarm['due'],timezone(timedelta(minutes=minutes))).strftime('%Y-%m-%d %H:%M:%S')+' '+zone_label(minutes)


def elapsed_label(value):
    value = max(0, int(value))
    return f'{value//3600:02}:{value%3600//60:02}:{value%60:02}'


class Clocks:
    def __init__(self, owner):
        key = hashlib.sha256(owner.lower().encode()).hexdigest()
        self.path = settings_path('clock-tools-account-'+key+'.json')
        self.lock = config_dir()/('clock-tools-'+key+'.lock')

    def load(self):
        try:data = json.loads(private_read(self.path))
        except FileNotFoundError:return dict(schema=1, zone=480, display_offset=None, alarms=[])
        if isinstance(data,dict):
            if 'display_utc' in data:
                old=data.pop('display_utc')
                if type(old) is not bool:raise ValueError('Invalid display setting.')
                data.setdefault('display_offset',0 if old else None)
            data.setdefault('display_offset',None)
        if (not isinstance(data,dict) or set(data) != {'schema','zone','display_offset','alarms'}
                or data['display_offset'] is not None and (type(data['display_offset']) is not int or not -720<=data['display_offset']<=840) or data['schema'] != 1
                or type(data['zone']) is not int or not -720 <= data['zone'] <= 840
                or not isinstance(data['alarms'],list) or len(data['alarms']) > 64):
            raise ValueError('Invalid clock settings; repair '+str(self.path))
        identities=set()
        for alarm in data['alarms']:
            if isinstance(alarm,dict):alarm.setdefault('explicit_utc',alarm.get('zone')==0)
            if isinstance(alarm,dict) and isinstance(alarm.get('due'),str):
                value=alarm['due']
                if not re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z',value):raise ValueError('Saved alarm timestamps must use ISO 8601 UTC Z.')
                alarm['due']=datetime.fromisoformat(value[:-1]+'+00:00').timestamp()
            required={'id','kind','label','due','enabled','repeat','zone','clock','days','paused','remaining','explicit_utc'}
            if not isinstance(alarm,dict) or set(alarm)!=required:raise ValueError('Invalid alarm record.')
            if (not isinstance(alarm['id'],str) or not re.fullmatch('[a-f0-9]{8}',alarm['id'])
                    or alarm['id'] in identities or alarm['kind'] not in ('alarm','timer')
                    or not isinstance(alarm['label'],str) or len(alarm['label'])>100
                    or any(ord(c)<32 for c in alarm['label'])
                    or any(type(alarm[k]) is not bool for k in ('enabled','paused','explicit_utc'))
                    or type(alarm['zone']) is not int or not -720<=alarm['zone']<=840
                    or alarm['repeat'] not in ('once','daily','weekly') and type(alarm['repeat']) is not int):
                raise ValueError('Invalid alarm record.')
            for key in ('due','remaining'):
                if type(alarm[key]) not in (int,float) or not math.isfinite(alarm[key]) or alarm[key]<0 or alarm[key]>253370764799:
                    raise ValueError('Invalid alarm time.')
            if type(alarm['repeat']) is int and not 60<=alarm['repeat']<=366*86400:
                raise ValueError('Recurring alarms require at least one minute.')
            if (not isinstance(alarm['days'],list) or not alarm['days'] or
                    any(type(d) is not int or not 0<=d<7 for d in alarm['days'])
                    or not isinstance(alarm['clock'],list) or len(alarm['clock'])!=3
                    or any(type(v) is not int or not 0<=v<limit for v,limit in zip(alarm['clock'],(24,60,60)))):
                raise ValueError('Invalid recurring time.')
            identities.add(alarm['id'])
        return data

    def edit(self, action):
        self.lock.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(self.lock,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'r+') as lock:
            fcntl.flock(lock,fcntl.LOCK_EX)
            private_read(self.lock)
            data=self.load()
            result,changed=action(data)
            if changed:
                saved=json.loads(json.dumps(data))
                for alarm in saved['alarms']:
                    alarm['due']=datetime.fromtimestamp(alarm['due'],timezone.utc).isoformat().replace('+00:00','Z')
                private_write(self.path,json.dumps(saved))
            return result

    def add(self, kind, spec, now=None):
        now=time.time() if now is None else now
        def action(data):
            minutes=data['zone']
            if len(data['alarms'])>=64:raise ValueError('Maximum 64 schedules; cancel or clear old entries.')
            args=list(spec);repeat='once';days=list(range(7));clock=[0,0,0]
            if not args:raise ValueError('Supply a duration or clock time.')
            mode=args.pop(0) if args[0] in ('daily','weekdays','weekly','every','on') else None
            if kind=='timer' and mode:raise ValueError('Timers use a duration; use /alarm for recurring schedules.')
            if mode=='weekly':
                if not args:raise ValueError('Use /alarm weekly mon,wed 8pm [label].')
                try:days=[WEEKDAYS.index(d.lower()) for d in args.pop(0).split(',')]
                except ValueError:raise ValueError('Use mon,tue,wed,thu,fri,sat,sun.') from None
            if mode=='weekdays':days=list(range(5))
            date=args.pop(0) if mode=='on' and args else None
            if not args:raise ValueError('Supply a duration or clock time.')
            value=args.pop(0)
            if kind=='alarm' and args and args[0].lower() in ('am','pm'):
                value=with_period(value,args.pop(0).lower())
            if kind=='alarm' and args and re.fullmatch(r'\+?Z|UTC|GMT|SGT|(?:UTC|GMT)?[+-](?:\d{4}|\d{1,2}(?:\.\d{1,6}|:\d{2})?)',args[0],re.I):
                value+=args.pop(0)
            if kind=='timer' or mode=='every' or re.fullmatch(r'(\d+[dhms])+',value.lower()):
                seconds=duration(value)
                if mode=='every':
                    if seconds<60:raise ValueError('Recurring alarms require at least one minute.')
                    repeat=seconds
                elif mode is not None:raise ValueError('Use a wall clock time for daily/weekly schedules.')
                due=now+seconds
            else:
                clock,minutes=wall_spec(value,data['zone'])
                if date:
                    try:
                        day=datetime.strptime(date,'%Y-%m-%d').replace(tzinfo=timezone(timedelta(minutes=minutes)))
                        due=day.replace(hour=clock[0],minute=clock[1],second=clock[2]).timestamp()
                    except ValueError:raise ValueError('Use /alarm on YYYY-MM-DD 08:00 [label].') from None
                    if due<=now:raise ValueError('Choose a future date/time.')
                else:due=next_wall(clock,days,now,minutes)
                if mode in ('daily','weekdays','weekly'):repeat='weekly' if mode=='weekly' else 'daily'
            label=' '.join(args) or ('Timer' if kind=='timer' else 'Alarm')
            if len(label)>100 or any(ord(c)<32 for c in label):raise ValueError('Use a label of at most 100 printable characters.')
            alarm=dict(id=secrets.token_hex(4),kind=kind,label=label,due=due,enabled=True,repeat=repeat,
                       zone=minutes,clock=clock,days=days,paused=False,remaining=0,explicit_utc=minutes==0)
            data['alarms'].append(alarm)
            return alarm,True
        return self.edit(action)

    def change(self, kind, operation, ident=None, extra=None, now=None):
        now=time.time() if now is None else now
        def action(data):
            matches=[a for a in data['alarms'] if a['kind']==kind and (operation=='clear' or a['id']==ident)]
            if not matches and operation!='clear':raise ValueError('No matching '+kind+' ID.')
            if operation in ('cancel','clear'):
                data['alarms']=[a for a in data['alarms'] if a not in matches]
            else:
                alarm=matches[0]
                if operation=='pause' and kind=='timer':
                    if not alarm['paused']:alarm.update(remaining=max(0,alarm['due']-now),paused=True)
                elif operation=='resume' and kind=='timer':
                    if alarm['paused']:alarm.update(due=now+alarm['remaining'],paused=False,enabled=True)
                elif operation=='snooze':alarm.update(due=now+duration(extra or '5m'),enabled=True,paused=False)
                else:raise ValueError('Use cancel, snooze, or timer pause/resume.')
            return len(matches),bool(matches)
        return self.edit(action)

    def poll(self, now=None):
        now=time.time() if now is None else now
        def action(data):
            fired=[]
            for alarm in data['alarms']:
                if len(fired)>=8:break
                if not alarm['enabled'] or alarm['paused'] or alarm['due']>now:continue
                fired.append(dict(alarm))
                repeat=alarm['repeat']
                if type(repeat) is int:
                    alarm['due']+= (int((now-alarm['due'])//repeat)+1)*repeat
                elif repeat in ('daily','weekly'):
                    alarm['due']=next_wall(alarm['clock'],alarm['days'],now,alarm['zone'])
                else:alarm['enabled']=False
            return fired,bool(fired)
        return self.edit(action)


class TimeControls:
    def clocks(self):
        clock=getattr(self,'clock_tools',None)
        if clock is None or getattr(self,'clock_owner',None)!=self.name:
            self.clock_tools=Clocks(self.name);self.clock_owner=self.name
        return self.clock_tools

    def clock_badge(self):
        minutes=getattr(self,'clock_zone',480)
        label=datetime.now(timezone(timedelta(minutes=minutes))).strftime('%H:%M:%S')+' '+zone_label(minutes)
        watch=getattr(self,'stopwatch_state',None)
        if watch and watch['started'] is not None:
            label+=' · SW '+elapsed_label(watch['elapsed']+time.monotonic()-watch['started'])
        timer=getattr(self,'clock_timer_due',None)
        if timer is not None:label+=' · TMR '+elapsed_label(timer-time.time())
        return label

    def time_tick(self):
        if getattr(self,'role','lobby')!='lobby':return
        now=time.monotonic()
        if now<getattr(self,'clock_next_tick',0):return
        self.clock_next_tick=now+1
        try:
            fired=self.clocks().poll()
            data=self.clocks().load();self.clock_zone=data['display_offset'] if data['display_offset'] is not None else 480
            timers=[a['due'] for a in data['alarms'] if a['kind']=='timer' and a['enabled'] and not a['paused']]
            self.clock_timer_due=min(timers) if timers else None
            self.clock_error=False
            for alarm in fired:
                title=('Timer finished: ' if alarm['kind']=='timer' else 'Alarm: ')+alarm['label']
                message=title+' ['+alarm['id']+'] · /'+alarm['kind']+' snooze '+alarm['id']+' 5m'
                self.lines.append(message)
                try:self.desktop_notice(title,message,self.name,category='alarms')
                except (OSError,ValueError):self.lines.append('Desktop alarm unavailable; the in-app alarm is shown above.')
        except (OSError,ValueError) as error:
            if not getattr(self,'clock_error',False):self.lines.append('Clock schedules need attention: '+str(error))
            self.clock_error=True

    def time_command(self,text):
        pending=getattr(self,'pending_alarm_hour',None)
        if pending and not text.startswith('/'):
            if text.lower() in ('cancel','no'):
                self.pending_alarm_hour=None;self.lines.append('Alarm setup cancelled.');return True
            if text.lower() not in ('am','pm'):
                self.lines.append('Choose am or pm, or type cancel.');return True
            text=re.sub(r'(?<!\S)'+re.escape(self.pending_alarm_value)+r'(?!\S)',with_period(self.pending_alarm_value,text.lower()),pending,count=1)
            self.pending_alarm_hour=None
        try:parts=shlex.split(text)
        except ValueError:
            if text.startswith(('/alarm','/timer','/stopwatch','/clock','/time')):
                self.lines.append('Close the quotation marks.');return True
            return False
        if not parts or parts[0] not in ('/alarm','/timer','/stopwatch','/clock','/time'):return False
        if getattr(self,'role','lobby')!='lobby':
            self.lines.append('Use clock tools in your HQ window.');return True
        self.pending_alarm_hour=None
        try:
            command=parts[0];args=parts[1:]
            if command in ('/clock','/time'):
                clock=self.clocks()
                if args:
                    if len(args)!=2:raise ValueError('Use /clock zone +8|+4.5|Z or /clock display +8|+4.5|UTC|local.')
                    if args[0]=='zone':
                        minutes=offset(args[1])
                        clock.edit(lambda data:(data.update(zone=minutes),True))
                        self.lines.append('New wall-clock schedules default to '+zone_label(minutes)+'.')
                    elif args[0]=='display':
                        chosen=None if args[1].lower()=='local' else offset(args[1])
                        clock.edit(lambda data:(data.update(display_offset=chosen),True))
                    else:raise ValueError('Use /clock zone +8|+4.5|Z or /clock display +8|+4.5|UTC|local.')
                minutes=clock.load()['display_offset']
                if minutes is None:minutes=480
                self.clock_zone=minutes
                self.lines.append(datetime.now(timezone(timedelta(minutes=minutes))).strftime('%a %Y-%m-%d %H:%M:%S')+' '+zone_label(minutes))
                self.lines.append('Viewing defaults to GMT+8; /clock display +8|+4.5|UTC|local. Explicit UTC schedules retain UTC viewing. Schedules require HQ running.')
            elif command=='/stopwatch':self.stopwatch_command(args)
            else:
                kind=command[1:];clock=self.clocks()
                if not args or args==['list'] or args==['status']:
                    now=time.time()
                    for alarm in clock.load()['alarms']:
                        if alarm['kind']!=kind:continue
                        when=alarm_timestamp(alarm,clock.load()['display_offset'])
                        state='paused '+elapsed_label(alarm['remaining']) if alarm['paused'] else 'done' if not alarm['enabled'] else 'in '+elapsed_label(alarm['due']-now)
                        self.lines.append(alarm['id']+' · '+alarm['label']+' · '+when+' · '+state+' · repeat='+str(alarm['repeat']))
                    self.lines.extend(['/alarm 30m | 8am | 162532 [label] · /alarm daily 8pm | weekdays 08:00 | weekly mon,wed 16:25 | every 30m | on YYYY-MM-DD 8pm',
                                       '/timer 5m [label] | /timer pause ID | resume ID · /alarm or /timer cancel ID | snooze ID 5m | clear',
                                       'Default GMT+8. /clock zone +8 · /stopwatch start|pause|lap|reset|status. Alarms require HQ running.'])
                elif args[0] in ('cancel','clear','pause','resume','snooze'):
                    op=args[0]
                    if (op=='clear' and len(args)!=1) or (op!='clear' and len(args) not in ((2,3) if op=='snooze' else (2,))):raise ValueError('Supply the displayed ID; snooze optionally accepts 5m.')
                    count=clock.change(kind,op,args[1] if len(args)>1 else None,args[2] if len(args)>2 else None)
                    self.lines.append(kind+' '+op+': '+str(count)+' schedule(s).')
                else:
                    alarm=clock.add(kind,args)
                    when=alarm_timestamp(alarm,clock.load()['display_offset'])
                    self.lines.append(kind+' '+alarm['id']+' set: '+when+' · '+alarm['label'])
        except AmbiguousHour as error:
            self.pending_alarm_hour=shlex.join(parts);self.pending_alarm_value=str(error)
            self.lines.append(str(error)+' am or pm? Type am or pm, or cancel. Nothing is scheduled yet.')
        except (OSError,ValueError) as error:self.lines.append('Clock: '+str(error))
        return True

    def stopwatch_command(self,args):
        operation=args[0] if len(args)==1 else 'start' if not args else None
        if operation not in ('start','resume','pause','stop','lap','reset','status'):
            raise ValueError('Use /stopwatch start|pause|lap|reset|status.')
        watch=getattr(self,'stopwatch_state',dict(elapsed=0,started=None,laps=[]))
        now=time.monotonic()
        value=watch['elapsed']+(now-watch['started'] if watch['started'] is not None else 0)
        if operation in ('start','resume') and watch['started'] is None:watch['started']=now
        elif operation in ('pause','stop'):
            watch.update(elapsed=value,started=None)
        elif operation=='reset':watch=dict(elapsed=0,started=None,laps=[]);value=0
        elif operation=='lap':watch['laps']=(watch['laps']+[value])[-20:]
        self.stopwatch_state=watch
        self.lines.append('Stopwatch '+elapsed_label(value)+f'.{int(value*100)%100:02}'+(' running' if watch['started'] is not None else ' paused')+' · session only')
        if operation in ('lap','status'):
            self.lines.extend('Lap '+str(n)+': '+elapsed_label(lap)+f'.{int(lap*100)%100:02}' for n,lap in enumerate(watch['laps'],1))

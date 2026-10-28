"""Versioned private relationships, named lists and independent arrival rules."""
from copy import deepcopy
import hashlib
import json
import re
from .auth import config_dir,private_read,private_write
from .login_whitelist import validate_logins

INTERVAL=300
RELATIONSHIPS={'tracked','friends','mutuals','oomf'}
ALIASES={'friend':'friends','mutual':'mutuals','moots':'mutuals','moot':'mutuals','acquaintances':'tracked','acquaintance':'tracked'}
FRIENDLY={'friends','mutuals','oomf'}
VARIABLES=RELATIONSHIPS|set(ALIASES)|{'alltracked'}
EVENTS={'campus','lobby'}


def login(value):
    if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',value):
        raise ValueError('Use Intra logins: /track dthoo hnah')
    return value.lower()


def relationship(value):
    value=ALIASES.get(value.lower(),value.lower())
    if value not in RELATIONSHIPS:raise ValueError('Relationships: tracked, friends, mutuals (moots), oomf.')
    return value


class Tracker:
    def __init__(self,owner):
        self.path=config_dir()/('tracking-'+hashlib.sha256(owner.lower().encode()).hexdigest()+'.json')
        self.data=dict(schema_version=2,people={},lists={},clusters=dict(enabled=False,include=[],exclude=[],scope='all'))
        self.campus={};self.peers={};self.rules_error=None;self.load_error=None;self.targets={}
        try:
            stored=json.loads(private_read(self.path))
            if stored.get('schema_version',1)==1:
                self.data['people']={login(n):dict(relationship='tracked',alerts={}) for n in stored['logins'][:100]}
            else:
                if stored.get('schema_version')!=2:raise ValueError('Unsupported relationship schema')
                people={}
                for name,record in stored['people'].items():
                    alerts=record.get('alerts',{})
                    if any(k not in EVENTS or type(v) is not bool for k,v in alerts.items()):raise ValueError('Invalid alert setting')
                    people[login(name)]=dict(relationship=relationship(record['relationship']),alerts=alerts)
                lists={self.list_name(n):list(dict.fromkeys(login(x) for x in members)) for n,members in stored.get('lists',{}).items()}
                rules=stored.get('clusters',self.data['clusters'])
                if type(rules['enabled']) is not bool:raise ValueError('Invalid cluster switch')
                rules=dict(rules,scope=str(rules.get('scope','all')))
                if rules['scope'] not in ('all','1','2'):raise ValueError('Invalid cluster scope')
                for key in ('include','exclude'):
                    if not isinstance(rules[key],list) or any(not isinstance(x,str) for x in rules[key]):raise ValueError('Invalid selectors')
                self.data.update(people=people,lists=lists,clusters=rules)
        except FileNotFoundError:pass
        except (OSError,ValueError,KeyError,TypeError,AttributeError):
            self.load_error='Cannot read relationship configuration; repair the file shown by /track config before making changes.'
        try:self.file_mtime_ns=self.path.stat().st_mtime_ns
        except OSError:self.file_mtime_ns=0

    @property
    def names(self):return list(self.data['people'])

    @property
    def rules_enabled(self):return self.data['clusters']['enabled'] and bool(self.data['clusters']['include'])

    def save(self,candidate):
        if self.load_error:raise ValueError(self.load_error)
        if len(candidate['people'])>100 or len(candidate['lists'])>50 or any(len(v)>100 for v in candidate['lists'].values()):
            raise ValueError('Maximum: 100 tracked people, 50 lists, 100 members per list.')
        raw=json.dumps(candidate)
        if len(raw.encode())>64000:raise ValueError('Local relationship configuration is too large.')
        private_write(self.path,raw);self.data=candidate
        try:self.file_mtime_ns=self.path.stat().st_mtime_ns
        except OSError:self.file_mtime_ns=0

    def change(self,names,remove=False):
        names=list(dict.fromkeys(login(n) for n in names))
        if not remove:names=validate_logins(names)
        candidate=deepcopy(self.data)
        for name in names:
            if remove:candidate['people'].pop(name,None)
            else:candidate['people'].setdefault(name,dict(relationship='tracked',alerts={}))
        self.save(candidate)
        if remove:
            for name in names:self.campus.pop(name,None);self.peers.pop(name,None)

    def set_relationship(self,names,status):
        status=relationship(status);names=validate_logins([login(n) for n in names]);candidate=deepcopy(self.data)
        for name in names:
            record=candidate['people'].setdefault(name,dict(alerts={}))
            record['relationship']=status
        self.save(candidate)

    def list_name(self,name):
        name=login(name.lstrip('@'))
        if name in VARIABLES or name=='all' or re.fullmatch(r'cohort\d+',name):raise ValueError('That list name is reserved; choose another name.')
        return name

    def change_list(self,name,members=(),remove=False,delete=False):
        name=self.list_name(name);members=[login(n) for n in members]
        if not remove and not delete:members=validate_logins(members)
        candidate=deepcopy(self.data)
        if delete:candidate['lists'].pop(name,None)
        else:
            current=candidate['lists'].get(name,[])
            candidate['lists'][name]=[n for n in current if n not in members] if remove else list(dict.fromkeys(current+members))
        self.save(candidate)

    def is_variable(self,value):
        return value.lower() in VARIABLES or value.startswith(('@','login:')) or value.lower() in self.data['lists']

    def resolve(self,selectors,validate=True):
        result=[]
        for raw in selectors:
            value=raw.lower();status=ALIASES.get(value,value)
            if value in ('online','verified'):raise ValueError('Use /sabo '+value+'; this presence selector is resolved by the API host, not the local relationship list.')
            if value.startswith('login:'):names=[login(value[6:])]
            elif value=='alltracked':names=self.names
            elif status in RELATIONSHIPS:
                statuses=FRIENDLY if status=='friends' else {status}
                names=[n for n,r in self.data['people'].items() if r['relationship'] in statuses]
            elif value.startswith('@') or value in self.data['lists']:
                key=value.lstrip('@')
                if key not in self.data['lists']:raise ValueError('Unknown local list: '+key)
                names=self.data['lists'][key]
            elif value=='all' or re.fullmatch(r'cohort\d+',value):
                from .campus_info import load
                data=load()
                if not data:raise ValueError('Cohort/all selectors need the local private campus cache.')
                cohort=None if value=='all' else int(value[6:])
                names=[login(s['login']) for s in data['students'] if cohort is None or s.get('cohort')==cohort]
            else:names=[login(value)]
            result.extend(names)
        result=list(dict.fromkeys(result))
        return validate_logins(result) if validate else result

    def set_alerts(self,selectors,event,enabled):
        if event not in EVENTS:raise ValueError('Alert events: campus or lobby.')
        names=self.resolve(selectors)
        if not names:raise ValueError('No people match that selector.')
        candidate=deepcopy(self.data)
        for name in names:
            record=candidate['people'].setdefault(name,dict(relationship='tracked',alerts={}))
            record['alerts'][event]=enabled
        self.save(candidate)

    def configure_rules(self,action,selectors=()):
        action=action.lower()
        location=None
        if action!='scope':
            aliases={'c1':'1','cluster1':'1','c2':'2','cluster2':'2'}
            tokens=[action,*selectors]
            locations={aliases[t.lower()] for t in tokens if t.lower() in aliases}
            if len(locations)>1:raise ValueError('Choose c1, c2 or all for the cluster location.')
            location=next(iter(locations),None)
            tokens=[t for t in tokens if t.lower() not in aliases]
            if not tokens:action='scope';selectors=[location]
            elif tokens[0].lower()=='all':
                if len(tokens)!=1 or location:raise ValueError('Use /settings clusters all to select both clusters.')
                action='scope';selectors=['all']
            else:action=tokens[0].lower();selectors=tokens[1:]
        candidate=deepcopy(self.data);rules=candidate['clusters']
        if location:rules['scope']=location
        if action in ('on','off'):
            if selectors:raise ValueError('Use /settings clusters on|off [c1|c2].')
            rules['enabled']=action=='on'
        elif action in ('include','exclude'):
            if not selectors:raise ValueError('Supply logins, friends, @list or cohort4.')
            self.resolve(selectors)  # Validate before saving; cohorts stay dynamic.
            rules[action]=list(dict.fromkeys(rules[action]+[x.lower() for x in selectors]))
        elif action=='scope':
            if len(selectors)!=1:raise ValueError('Use /settings clusters c1|c2|all')
            scope={'c1':'1','c2':'2'}.get(selectors[0].lower(),selectors[0].lower())
            if scope not in ('all','1','2'):raise ValueError('Use /settings clusters c1|c2|all')
            rules['scope']=scope
        elif action=='clear':
            if list(selectors)==['include']:rules['include']=[]
            elif list(selectors)==['exclude']:rules['exclude']=[]
            elif not selectors:rules['include']=[];rules['exclude']=[]
            else:raise ValueError('Use clusters clear [include|exclude].')
        else:raise ValueError('Clusters: c1|c2|all, on|off, include SELECTOR..., exclude SELECTOR..., clear [include|exclude].')
        self.save(candidate)

    def transitions(self,players,source):
        previous=self.campus if source=='campus' else self.peers
        current={p.get('name','').lower():p for p in players}
        personal={n for n,r in self.data['people'].items() if r['alerts'].get(source,True)}
        rules=set();self.rules_error=None
        if self.rules_enabled:
            try:rules=set(self.resolve(self.data['clusters']['include']))-set(self.resolve(self.data['clusters']['exclude']))
            except ValueError as error:self.rules_error=str(error)
        scope=self.data['clusters'].get('scope','all')
        from .lobby_view import seat
        def snapshot(player):
            location=seat(player)
            value='c{}r{}s{}'.format(*location) if location else player.get('seat','unknown')
            return dict(seat=value,verified=bool(player.get('verified')))
        if scope!='all':
            # Keep a previously matching seat for one departure/move notice.
            # Missing API data is handled by the caller, never as an empty poll.
            rules={n for n in rules if (n in current and seat(current[n]) and seat(current[n])[0]==int(scope))
                   or (previous.get(n) and seat(previous[n]) and seat(previous[n])[0]==int(scope))}
        self.targets[source]=personal|rules
        notices=[]
        for name in sorted(personal|rules):
            player=current.get(name)
            old=previous.get(name)
            new=snapshot(player) if player else None
            changes=[]
            if new and not old:changes=['online']
            elif old and not new:changes=['offline']
            elif new and old:
                if old['seat']!=new['seat']:changes.append('seat')
                if source=='lobby' and old['verified']!=new['verified']:changes.append('verification')
            if changes:
                record=self.data['people'].get(name,{})
                status=record.get('relationship','tracked')
                details=new or old
                notices.append(dict(login=name,source=source,seat=details['seat'],verified=details['verified'],
                                    changes=changes,previous_seat=old['seat'] if old else None,
                                    relationship=status,reason='personal' if name in personal else 'clusters',
                                    warm=name in personal and status in FRIENDLY))
            previous[name]=new
        # Drop obsolete selectors and bound state to current configured targets.
        for name in list(previous):
            if name not in personal|rules:previous.pop(name,None)
        return notices


def describe(notice):
    name=notice['login']
    if notice.get('warm'):
        label={'friends':'friend','mutuals':'mutual','oomf':'oomf'}[notice['relationship']]
        prefix='Your '+label+' '+name
    else:prefix=(('Campus update: ' if notice['source']=='campus' else 'LAN42 update: ') if notice.get('reason')=='clusters' else '')+name
    changes=notice.get('changes',['online'])
    def location(value):
        match=re.fullmatch(r'c([12])r(\d+)s(\d+)',value or '')
        return f'cluster {match[1]}, row {match[2]}, seat {match[3]} ({value})' if match else value or 'unknown'
    campus=notice['source']=='campus'
    if 'offline' in changes:
        title=prefix+(' is offline on campus' if campus else ' has left the LAN42 lobby')
        body='Last seen at '+location(notice.get('seat'))+'.'
    elif 'seat' in changes or 'verification' in changes:
        title=prefix+(' moved on campus' if campus else ' changed status in the LAN42 lobby')
        parts=[]
        if 'seat' in changes:parts.append(name+' moved from '+location(notice.get('previous_seat'))+' to '+location(notice.get('seat'))+'.')
        if 'verification' in changes:parts.append('Identity is now '+('42 Verified.' if notice.get('verified') else 'Guest (unverified).'))
        body=' '.join(parts)
    elif campus:
        title=prefix+' is online on campus'+(' — go say hi!' if notice.get('warm') else '')
        body=name+' is at '+location(notice.get('seat'))+'.'
    else:
        title=prefix+' has joined the LAN42 lobby'+(' — say hi!' if notice.get('warm') else '.')
        body=('42 Verified' if notice.get('verified') else 'Guest identity (unverified)')+' · '+notice.get('seat','unknown')
    return title,body

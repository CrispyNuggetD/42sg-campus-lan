"""Local-only relationship settings; selectors never leave this client."""
from .tracking import relationship, RELATIONSHIPS, ALIASES

HELP=[
 '/track LOGIN... — acquaintances (tracked); /untrack LOGIN...|all',
 '/track — grouped relationships and lists; /track friends|mutuals|oomf|tracked — view a group',
 '/track friends dthoo thtay — track as friends; other relationship labels and @lists work too',
 '/track status friends dthoo thtay — set a relationship (also: tracked, mutuals/moots, oomf)',
 '/track list lunch add dthoo thtay | /track list lunch remove thtay | /track list lunch delete',
 '/track alerts SELECTOR campus|lobby on|off — per-person event preferences',
 '/settings clusters c1|c2|all | on|off | include SELECTOR... | exclude SELECTOR... | clear [include|exclude]',
 'Selectors: friends (includes mutuals/oomf), tracked (acquaintances), alltracked, mutuals/moots, oomf, @lunch, cohort4.',
 '/track config — private configuration path. Relationships are local labels, not reciprocal requests.',
]


def relationship_lines(tracker, selectors=None):
    selected=set(tracker.resolve(selectors)) if selectors else set(tracker.names)
    lines=['Local relationships']
    for status,title in (('friends','Friends'),('mutuals','Mutuals'),('oomf','OOMF'),('tracked','Acquaintances (tracked)')):
        names=sorted(n for n,r in tracker.data['people'].items()
                     if n in selected and r['relationship']==status)
        if names:
            lines.append(f'  {title} ({len(names)})')
            lines.extend('    '+name for name in names)
    if len(lines)==1:lines.append('  Nobody tracked here yet.')
    return lines


def rule_lines(tracker):
    rules=tracker.data['clusters']
    return ['Cluster arrival rules: '+('on' if rules['enabled'] else 'off')+' · location: '+('all clusters' if rules.get('scope','all')=='all' else 'cluster'+rules['scope']),
            'Include: '+(', '.join(rules['include']) or 'nobody'),
            'Exclude: '+(', '.join(rules['exclude']) or 'nobody'),
            'Rules are separate from relationships. Exclusions apply to these rules only.']


def configure(tracker,args):
    if not args:
        lines=relationship_lines(tracker)+['','Named lists']
        for name,members in sorted(tracker.data['lists'].items()):
            lines.append(f'  @{name} ({len(members)})')
            lines.extend('    '+member for member in sorted(members))
        if not tracker.data['lists']:lines.append('  None yet. /track list NAME add LOGIN...')
        return lines+['','Campus checks every five minutes while HQ runs. /track help']+rule_lines(tracker)
    command=args[0].lower()
    if command=='help':return HELP
    if command=='config':return ['Private relationship config: '+str(tracker.path)]
    if command in RELATIONSHIPS or command in ALIASES:
        if len(args)==1:return relationship_lines(tracker,[command])
        status=relationship(command)
        names=tracker.resolve(args[1:]);tracker.set_relationship(names,status)
        return ['Relationship '+status+': '+(', '.join(names) or 'nobody')]
    if command in ('status','relationship'):
        if len(args)<3:raise ValueError('Use /track status friends dthoo thtay')
        try:status=relationship(args[1]);names=args[2:]
        except ValueError:status=relationship(args[-1]);names=args[1:-1]
        names=tracker.resolve(names);tracker.set_relationship(names,status)
        return ['Relationship '+status+': '+(', '.join(names) or 'nobody')]
    if command in ('list','lists'):
        if len(args)==1:return ['@'+n+': '+', '.join(v) for n,v in tracker.data['lists'].items()] or ['No named lists yet. /track list lunch add dthoo']
        name=tracker.list_name(args[1])
        if len(args)==2:
            if name not in tracker.data['lists']:tracker.change_list(name)
        elif args[2]=='delete' and len(args)==3:tracker.change_list(name,delete=True)
        elif args[2] in ('add','remove') and len(args)>3:
            tracker.change_list(name,tracker.resolve(args[3:]),remove=args[2]=='remove')
        else:raise ValueError('Use /track list NAME [add|remove LOGIN...|delete]')
        return ['@'+name+': '+(', '.join(tracker.data['lists'].get(name,[])) or 'empty/deleted')]
    if command=='alerts':
        if len(args)!=4 or args[3] not in ('on','off'):raise ValueError('Use /track alerts friends campus off')
        tracker.set_alerts([args[1]],args[2],args[3]=='on')
        return [args[1]+' '+args[2]+' alerts: '+args[3]]
    if command=='clusters':
        if len(args)>1:tracker.configure_rules(args[1],args[2:])
        return rule_lines(tracker)
    names=tracker.resolve(args)
    if not names:raise ValueError('No people match that selector.')
    tracker.change(names)
    return ['Tracking locally: '+', '.join(names),'Default relationship: tracked. /track status friends LOGIN promotes a friend.']

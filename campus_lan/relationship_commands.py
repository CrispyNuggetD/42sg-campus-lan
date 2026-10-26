"""Local-only relationship settings; selectors never leave this client."""
from .tracking import relationship

HELP=[
 '/track LOGIN... — acquaintances (tracked); /untrack LOGIN...|all',
 '/track status friends dthoo thtay — set a relationship (also: tracked, mutuals/moots, oomf)',
 '/track list lunch add dthoo thtay | /track list lunch remove thtay | /track list lunch delete',
 '/track alerts SELECTOR campus|lobby on|off — per-person event preferences',
 '/settings clusters c1|c2|all | on|off | include SELECTOR... | exclude SELECTOR... | clear [include|exclude]',
 'Selectors: friends (includes mutuals/oomf), tracked (acquaintances), alltracked, mutuals/moots, oomf, @lunch, cohort4.',
 '/track config — private configuration path. Relationships are local labels, not reciprocal requests.',
]


def rule_lines(tracker):
    rules=tracker.data['clusters']
    return ['Cluster arrival rules: '+('on' if rules['enabled'] else 'off')+' · location: '+('all clusters' if rules.get('scope','all')=='all' else 'cluster'+rules['scope']),
            'Include: '+(', '.join(rules['include']) or 'nobody'),
            'Exclude: '+(', '.join(rules['exclude']) or 'nobody'),
            'Rules are separate from relationships. Exclusions apply to these rules only.']


def configure(tracker,args):
    if not args:
        return ['Local relationships: '+(', '.join(n+' ['+r['relationship']+']' for n,r in tracker.data['people'].items()) or 'nobody'),
                'Named lists: '+(', '.join('@'+n+' ('+str(len(v))+')' for n,v in tracker.data['lists'].items()) or 'none'),
                'Campus checks every five minutes while HQ runs. /track help']+rule_lines(tracker)
    command=args[0].lower()
    if command=='help':return HELP
    if command=='config':return ['Private relationship config: '+str(tracker.path)]
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

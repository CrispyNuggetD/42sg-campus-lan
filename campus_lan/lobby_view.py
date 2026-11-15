"""Pure roster and ASCII floor-plan rendering shared by the terminal lobby."""
import re
import zlib
import time

# Physical layout from the owner's cluster screenshots: highest row at the top,
# even seats above odd seats, staggered by one desk.
LAYOUT = {1: {8:12, 7:9, 6:6, 5:6, 4:6, 3:6, 2:6, 1:6},
          2: {7:6, 6:15, 5:15, 4:15, 3:12, 2:15, 1:15}}


def guest_style(name):
    return 2 + zlib.crc32(str(name).encode()) % 6


def seat(player):
    if player.get('remote_approved'):return None
    value = str(player.get('seat', ''))
    match = re.fullmatch(r'Cluster ([12]), row (\d+), seat (\d+)', value)
    if not match:
        match = re.fullmatch(r'c([12])r(\d+)s(\d+)', value)
    return tuple(map(int, match.groups())) if match else None


def roster(players):
    ordered = sorted(players, key=lambda p: (seat(p) or (3,0,0), p.get('name',''), p.get('id','')))
    return [(i, p, seat(p)) for i,p in enumerate(ordered,1)]


def plain(text):
    return [(text, 0)]


FRIEND_STYLE=49  # unknown-intake friendly band; known intakes use 24..31
LIST_STYLE=50    # unknown-intake list band; known intakes use 32..39
SIGNED_STYLE=1  # green
GUEST_STYLE=21  # amber; ? marker carries guest status
API_STYLE=22    # cyan occupancy when intake is unknown
CLUSTER_STYLES={1:8,2:9}  # cool cyan / warm amber
SELF_STYLE=51             # unknown-intake self band; known intakes use 41..48
SELECTED_STYLE=1 << 12  # rendering flag; never a replacement color pair
COHORT_STYLES={n:11+(n-1)%8 for n in range(1,100)}  # Stable intake palette, with I labels.


def init_cluster_colors(curses):
    curses.init_pair(8,curses.COLOR_CYAN,curses.COLOR_BLACK)
    curses.init_pair(9,curses.COLOR_YELLOW,curses.COLOR_BLACK)
    curses.init_pair(21,curses.COLOR_YELLOW,curses.COLOR_BLACK)
    curses.init_pair(22,curses.COLOR_CYAN,curses.COLOR_BLACK)
    extended=(33,45,82,214,141,220,203,37)
    basic=(curses.COLOR_BLUE,curses.COLOR_CYAN,curses.COLOR_GREEN,curses.COLOR_YELLOW,
           curses.COLOR_MAGENTA,curses.COLOR_WHITE,curses.COLOR_RED,curses.COLOR_CYAN)
    palette=extended if getattr(curses,'COLORS',0)>=256 else basic
    for pair,color in enumerate(palette,11):
        curses.init_pair(pair,color,curses.COLOR_BLACK)
    band=236 if getattr(curses,'COLORS',0)>=256 else curses.COLOR_BLACK
    for start in (24,32,41):
        for index,color in enumerate(palette):
            curses.init_pair(start+index,color,band)
    for pair in (FRIEND_STYLE,LIST_STYLE,SELF_STYLE):
        curses.init_pair(pair,curses.COLOR_CYAN,band)


def selection_attributes(curses, colors=False, now=None, style=API_STYLE):
    """Pulse weight, never foreground/background hue or identifying text."""
    moment=time.monotonic() if now is None else now
    attr=curses.A_UNDERLINE
    if colors:attr|=curses.color_pair(style & ~SELECTED_STYLE)
    if int(moment/.6)%2==0:attr|=curses.A_BOLD
    return attr


def relationship_overlay(players, data, owner=None, cohorts=None):
    """Local display decoration only; never send relationship/list data to peers."""
    people=data.get('people',{})
    listed={name for members in data.get('lists',{}).values() for name in members}
    result=[]
    for player in players:
        name=player.get('name','').lower()
        trusted=player.get('verified') or player.get('api_presence')
        friendly=people.get(name,{}).get('relationship') in {'friends','mutuals','oomf'}
        kind='friend' if trusted and friendly else 'list' if trusted and name in listed else None
        number=(cohorts or {}).get(name)
        if type(number) is not int or not 1<=number<=99:number=None
        result.append(dict(player,local_relationship=kind,local_relationship_label=people.get(name,{}).get('relationship') if trusted else None,local_self=bool(trusted and owner and name==owner.lower()),local_cohort=number if trusted else None))
    return result


def player_style(player):
    cohort=player.get('local_cohort')
    known=cohort in COHORT_STYLES
    offset=(cohort-1)%8 if known else 0
    # Relationship changes the background band, never the cohort foreground.
    if player.get('local_self'):return 41+offset if known else SELF_STYLE
    if player.get('local_relationship')=='friend':return 24+offset if known else FRIEND_STYLE
    if player.get('local_relationship')=='list':return 32+offset if known else LIST_STYLE
    if known:return COHORT_STYLES[cohort]
    if player.get('api_presence') and not player.get('lan42_peer'):return API_STYLE
    return SIGNED_STYLE if player.get('verified') or player.get('remote_approved') else GUEST_STYLE


def relationship_badge(player):
    if player.get('local_self'):return 'Y','you'
    relation=player.get('local_relationship_label')
    if relation in ('friends','mutuals','oomf','tracked'):
        return {'friends':('F','friend'),'mutuals':('M','mutual'),'oomf':('O','oomf'),'tracked':('T','tracked')}[relation]
    if player.get('local_relationship')=='friend':return 'F','friend'
    if player.get('local_relationship')=='list':return 'L','list'
    if player.get('api_presence') and not player.get('lan42_peer'):return 'A','API only'
    if player.get('verified') or player.get('remote_approved'):return '+','verified/approved'
    return '?','guest'


def map_legend():
    return [('Y you ',0),('F/M/O friends ',0),('L list ',0),
            ('T tracked A API + verified ? guest ',0),('>cell< select',0)]


def overlay_campus(players, peers):
    by_name={}
    for peer in peers:
        name=peer.get('name','').lower()
        if name not in by_name or peer.get('verified'):by_name[name]=peer
    result=[]
    for player in players:
        peer=by_name.get(player.get('name','').lower())
        result.append(dict(player,api_presence=True,lan42_peer=peer is not None,verified=bool(peer and peer.get('verified'))))
    return result


def player_line(number, player, location):
    label = f'c{location[0]}r{location[1]}s{location[2]}' if location else 'Unknown / off campus'
    name = str(player.get('name','guest'))[:24]
    status=('Remote approved / '+('42 signed in' if player.get('verified') else 'unverified')) if player.get('remote_approved') else ('LAN42 verified' if player.get('verified') else 'LAN42 guest') if player.get('lan42_peer') else 'API login' if player.get('api_presence') else '42 Verified' if player.get('verified') else 'Guest'
    relation=player.get('local_relationship')
    if relation:status+=' / '+relationship_badge(player)[1]
    if player.get('local_self'):status+=' / you'
    if player.get('local_cohort'):status+=' / I'+str(player['local_cohort'])+'~'
    badge,_=relationship_badge(player)
    return [(f'{number:>3}. [{badge}] {name:<20}', player_style(player)),(f' {label:<22} {status}',CLUSTER_STYLES.get(location[0],0) if location else 0)]


def lobby_lines(players, view='roster', cluster=1):
    if cluster == 0 and view != 'roster':
        # Cluster 2 is physically above Cluster 1.
        first = lobby_lines(players, view, 2)
        second = lobby_lines(players, view, 1)
        marker = plain('CURRENTLY ONLINE - map markers match these roster numbers')
        return first[:first.index(marker)-1] + [plain('')] + second
    entries = roster(players)
    if view == 'roster':
        lines = []
        for group,title in ((1,'CLUSTER 1'), (2,'CLUSTER 2'), (3,'OFF CAMPUS / SEAT UNKNOWN')):
            members = [(n,p,s) for n,p,s in entries if (s[0] if s else 3)==group]
            lines.append([(f'{title} - {len(members)} online',CLUSTER_STYLES.get(group,0))])
            lines.extend(player_line(n,p,s) for n,p,s in members)
            if not members:
                lines.append(plain('     Nobody connected here yet.'))
            lines.append(plain(''))
        return lines

    lines = [[(f'CLUSTER {cluster} - physical seat map | 4F09 = I4 / Friend / #09',CLUSTER_STYLES[cluster])],
             map_legend()]
    occupied = {}
    for n,p,s in entries:
        if s and s[0]==cluster:
            occupied.setdefault((s[1],s[2]), []).append((n,p))
    for row,count in LAYOUT[cluster].items():
        if cluster==1 and row==6:
            lines.append(plain(' '*28+'+---    ---+'))
        if cluster==1 and row==5:
            lines.append(plain('    '+' WALL R5/R6 '.center(24,'=')+'+          |'))
        for parity in (0,1):
            line = [(f'R{row:<2} ' if parity==0 else '    ',CLUSTER_STYLES[cluster])]
            for desk in range(1,count+1):
                if desk % 2 != parity:
                    line.append(('    ',0))
                    continue
                members = occupied.get((row,desk), [])
                token,style = f'[{desk:02}]',0
                if members:
                    priority={'friend':0,'list':1}
                    n,p = min(members,key=lambda item:(-1 if item[1].get('local_self') else priority.get(item[1].get('local_relationship'),2 if item[1].get('verified') else 3 if item[1].get('lan42_peer') else 4)))
                    badge,_=relationship_badge(p)
                    cohort=p.get('local_cohort')
                    intake=str(cohort) if cohort else '?'
                    number=f'{n:02}' if n<100 else '**'
                    token = '[++]' if len(members)>1 else (intake+badge+number if len(intake)==1 else intake+badge+(str(n) if n<10 else '*'))
                    style = player_style(p)
                line.append((token,style))
            if cluster==1 and row in (5,6):
                label='bocal' if (row,parity)==(6,1) else ''
                line.append(('|'+label.center(10)+'|',CLUSTER_STYLES[1]))
            lines.append(line)
        if cluster==1 and row==5:
            lines.append(plain(' '*28+'+----------+'))
    lines.append([('Intake colors: ',0)]+[(f'I{number} ',COHORT_STYLES[number]) for number in range(1,9)]+[('(~ inferred)',0)])
    lines += [plain(''), plain('CURRENTLY ONLINE - map markers match these roster numbers')]
    lines.extend(player_line(n,p,s) for n,p,s in entries)
    if not entries:
        lines.append(plain('Waiting for presence from your node...'))
    if any(s and s[0]==cluster and not 1<=s[2]<=LAYOUT[cluster].get(s[1],0) for _,_,s in entries):
        lines.append(plain('Some reported seats are outside this layout; see the roster.'))
    lines.append(plain('Unmarked desks mean no LAN42 peer reported; not necessarily vacant. In~ = locally inferred intake.'))
    return lines


def occupant_hits(players, view='map', cluster=0):
    """Return row/column hit regions from layout geometry, including cohort/shared markers."""
    entries=roster(players)
    ordered={number:player for number,player,_ in entries}
    occupied={}
    for _,player,location in entries:
        if location:occupied.setdefault(location,[]).append(player)
    hits=[];current_cluster=None;current_row=None
    for y,segments in enumerate(lobby_lines(players,view,cluster)):
        first=segments[0][0] if segments else ''
        heading=re.match(r'CLUSTER ([12]) - physical',first)
        if heading:current_cluster=int(heading[1]);current_row=None
        row=re.match(r'R(\d+)\s',first)
        if row:current_row=int(row[1])
        numbered=re.match(r'\s*(\d+)\. ',first)
        if numbered:
            player=ordered.get(int(numbered[1]))
            if player:hits.append((y,0,sum(len(text) for text,_ in segments),[player]))
            current_row=None
            continue
        if first.startswith('CURRENTLY ONLINE'):current_row=None
        if current_cluster and current_row and (row or first=='    ') and len(segments)>=LAYOUT[current_cluster][current_row]+1:
            x=len(first)
            for desk,(text,_) in enumerate(segments[1:LAYOUT[current_cluster][current_row]+1],1):
                members=occupied.get((current_cluster,current_row,desk),[])
                if text.strip() and members:hits.append((y,x,x+len(text),members))
                x+=len(text)
    return hits


def selected_details(players, location, name=None):
    members=[p for p in players if seat(p)==location and (not name or p.get('name','').lower()==name.lower())] if location else []
    if not members:return 'Selection no longer in snapshot.' if location else ''
    address='c%dr%ds%d'%location
    labels=[]
    for player in members:
        badge,label=relationship_badge(player)
        intake=' | I'+str(player['local_cohort'])+'~' if player.get('local_cohort') else ''
        labels.append(player.get('name','?')+' ['+badge+': '+label+']'+intake)
    return 'SELECTED '+'; '.join(labels)+' | '+address


def selection_overlay(players, content, view, cluster, location, name=None):
    """Add gutter arrows and a pulse flag; keep cell text, color and geometry."""
    if not location:return content
    hits=[hit for hit in occupant_hits(players,view,cluster)
          if any(seat(p)==location and (not name or p.get('name','').lower()==name.lower()) for p in hit[3])]
    result=[]
    for row,segments in enumerate(content):
        x=0;out=list(segments)
        for index,(text,style) in enumerate(segments):
            selected=any(y==row and left<x+len(text) and x<right for y,left,right,_ in hits)
            if selected:
                out[index]=(text,style|SELECTED_STYLE)
                if len(text)==4 and index>0:
                    before,previous_style=out[index-1]
                    if before.endswith(' '):out[index-1]=(before[:-1]+'>',previous_style)
                    if index+1<len(out):
                        after,next_style=out[index+1]
                        if after.startswith(' '):out[index+1]=('<'+after[1:],next_style)
                elif text[:5].strip().endswith('.'):
                    out[index]=('>'+text[1:],style|SELECTED_STYLE)
            x+=len(text)
        result.append(out)
    return result

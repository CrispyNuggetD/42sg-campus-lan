"""Pure roster and ASCII floor-plan rendering shared by the terminal lobby."""
import re
import zlib

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


FRIEND_STYLE=4  # magenta
LIST_STYLE=2    # cyan
SIGNED_STYLE=1  # green
GUEST_STYLE=3   # yellow
API_STYLE=5     # blue
CLUSTER_STYLES={1:8,2:9}  # cool cyan / warm amber
SELF_STYLE=10             # high-contrast personal badge
COHORT_STYLES={n:11+(n-1)%8 for n in range(1,100)}


def init_cluster_colors(curses):
    curses.init_pair(8,curses.COLOR_CYAN,curses.COLOR_BLACK)
    curses.init_pair(9,curses.COLOR_YELLOW,curses.COLOR_BLACK)
    curses.init_pair(10,curses.COLOR_BLACK,curses.COLOR_WHITE)
    for pair,(fg,bg) in enumerate(((curses.COLOR_GREEN,curses.COLOR_BLACK),
                                  (curses.COLOR_CYAN,curses.COLOR_BLACK),
                                  (curses.COLOR_YELLOW,curses.COLOR_BLACK),
                                  (curses.COLOR_WHITE,curses.COLOR_BLUE),
                                  (curses.COLOR_BLACK,curses.COLOR_CYAN),
                                  (curses.COLOR_MAGENTA,curses.COLOR_BLACK),
                                  (curses.COLOR_BLUE,curses.COLOR_WHITE),
                                  (curses.COLOR_RED,curses.COLOR_BLACK)),11):
        curses.init_pair(pair,fg,bg)


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
        result.append(dict(player,local_relationship=kind,local_self=bool(trusted and owner and name==owner.lower()),local_cohort=number if trusted else None))
    return result


def player_style(player):
    if player.get('local_self'):return SELF_STYLE
    if player.get('local_relationship')=='friend':return FRIEND_STYLE
    if player.get('local_relationship')=='list':return LIST_STYLE
    if player.get('local_cohort') in COHORT_STYLES:return COHORT_STYLES[player['local_cohort']]
    if player.get('api_presence') and not player.get('lan42_peer'):return API_STYLE
    return SIGNED_STYLE if player.get('verified') or player.get('remote_approved') else GUEST_STYLE


def map_legend():
    return [('You ',SELF_STYLE),('Friend ',FRIEND_STYLE),('List ',LIST_STYLE),('Signed/approved ',SIGNED_STYLE),
            ('Guest ',GUEST_STYLE),('API only ',API_STYLE),('Empty* ',0),('[++]: shared · C:N = cohort:roster',0)]


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
    if relation:status+=' / '+relation
    if player.get('local_self'):status+=' / you'
    if player.get('local_cohort'):status+=' / C'+str(player['local_cohort'])+'~'
    return [(f'{number:>3}. {name:<24}', player_style(player)),(f' {label:<22} {status}',CLUSTER_STYLES.get(location[0],0) if location else 0)]


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

    lines = [[(f'CLUSTER {cluster} - physical seat map (even desks above odd desks)',CLUSTER_STYLES[cluster])],
             map_legend()]
    occupied = {}
    for n,p,s in entries:
        if s and s[0]==cluster:
            occupied.setdefault((s[1],s[2]), []).append((n,p))
    for row,count in LAYOUT[cluster].items():
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
                    token = '[++]' if len(members)>1 else (f'[#{n}]' if n<10 else f'[{n:02}]' if n<100 else '[**]')
                    cohort=p.get('local_cohort')
                    if len(members)==1 and cohort and cohort<10 and n<100:token=f'{cohort}:{n:02}'
                    style = player_style(p)
                line.append((token,style))
            lines.append(line)
    lines += [plain(''), plain('CURRENTLY ONLINE - map markers match these roster numbers')]
    lines.extend(player_line(n,p,s) for n,p,s in entries)
    if not entries:
        lines.append(plain('Waiting for presence from your node...'))
    if any(s and s[0]==cluster and not 1<=s[2]<=LAYOUT[cluster].get(s[1],0) for _,_,s in entries):
        lines.append(plain('Some reported seats are outside this layout; see the roster.'))
    lines.append(plain('Unmarked desks mean no LAN42 peer reported; not necessarily vacant. Cn~ = locally inferred cohort.'))
    return lines

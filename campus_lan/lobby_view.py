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


def relationship_overlay(players, data):
    """Local display decoration only; never send relationship/list data to peers."""
    people=data.get('people',{})
    listed={name for members in data.get('lists',{}).values() for name in members}
    result=[]
    for player in players:
        name=player.get('name','').lower()
        trusted=player.get('verified') or player.get('api_presence')
        friendly=people.get(name,{}).get('relationship') in {'friends','mutuals','oomf'}
        kind='friend' if trusted and friendly else 'list' if trusted and name in listed else None
        result.append(dict(player,local_relationship=kind))
    return result


def player_style(player):
    if player.get('local_relationship')=='friend':return FRIEND_STYLE
    if player.get('local_relationship')=='list':return LIST_STYLE
    if player.get('api_presence') and not player.get('lan42_peer'):return API_STYLE
    return SIGNED_STYLE if player.get('verified') or player.get('remote_approved') else GUEST_STYLE


def map_legend():
    return [('Friend ',FRIEND_STYLE),('List ',LIST_STYLE),('Signed/approved ',SIGNED_STYLE),
            ('Guest ',GUEST_STYLE),('API only ',API_STYLE),('Empty* ',0),('[++]: shared',0)]


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
    return [(f'{number:>3}. {name:<24}', player_style(player)),(f' {label:<22} {status}',0)]


def lobby_lines(players, view='roster', cluster=1):
    if cluster == 0 and view != 'roster':
        first = lobby_lines(players, view, 1)
        second = lobby_lines(players, view, 2)
        marker = plain('CURRENTLY ONLINE - map markers match these roster numbers')
        return first[:first.index(marker)-1] + [plain('')] + second
    entries = roster(players)
    if view == 'roster':
        lines = []
        for group,title in ((1,'CLUSTER 1'), (2,'CLUSTER 2'), (3,'OFF CAMPUS / SEAT UNKNOWN')):
            members = [(n,p,s) for n,p,s in entries if (s[0] if s else 3)==group]
            lines.append(plain(f'{title} - {len(members)} online'))
            lines.extend(player_line(n,p,s) for n,p,s in members)
            if not members:
                lines.append(plain('     Nobody connected here yet.'))
            lines.append(plain(''))
        return lines

    lines = [plain(f'CLUSTER {cluster} - physical seat map (even desks above odd desks)'),
             map_legend()]
    occupied = {}
    for n,p,s in entries:
        if s and s[0]==cluster:
            occupied.setdefault((s[1],s[2]), []).append((n,p))
    for row,count in LAYOUT[cluster].items():
        for parity in (0,1):
            line = [(f'R{row:<2} ' if parity==0 else '    ',0)]
            for desk in range(1,count+1):
                if desk % 2 != parity:
                    line.append(('    ',0))
                    continue
                members = occupied.get((row,desk), [])
                token,style = f'[{desk:02}]',0
                if members:
                    priority={'friend':0,'list':1}
                    n,p = min(members,key=lambda item:priority.get(item[1].get('local_relationship'),2 if item[1].get('verified') else 3 if item[1].get('lan42_peer') else 4))
                    token = '[++]' if len(members)>1 else (f'[#{n}]' if n<10 else f'[{n:02}]' if n<100 else '[**]')
                    style = player_style(p)
                line.append((token,style))
            lines.append(line)
    lines += [plain(''), plain('CURRENTLY ONLINE - map markers match these roster numbers')]
    lines.extend(player_line(n,p,s) for n,p,s in entries)
    if not entries:
        lines.append(plain('Waiting for presence from your node...'))
    if any(s and s[0]==cluster and not 1<=s[2]<=LAYOUT[cluster].get(s[1],0) for _,_,s in entries):
        lines.append(plain('Some reported seats are outside this layout; see the roster.'))
    lines.append(plain('Unmarked desks mean no LAN42 peer reported; not necessarily vacant.'))
    return lines

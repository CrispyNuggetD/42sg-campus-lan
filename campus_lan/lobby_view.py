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


def player_line(number, player, location):
    label = f'c{location[0]}r{location[1]}s{location[2]}' if location else 'Unknown / off campus'
    name = str(player.get('name','guest'))[:24]
    return [(f'{number:>3}. {name:<24}', 1 if player.get('verified') else guest_style(name)),
            (f" {label:<22} {'42 Verified' if player.get('verified') else 'Guest'}", 0)]


def lobby_lines(players, view='roster', cluster=1):
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
             plain('Plain [02]: desk | coloured [#1]/[10]: roster # | [++]: shared')]
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
                    n,p = members[0]
                    token = '[++]' if len(members)>1 else (f'[#{n}]' if n<10 else f'[{n:02}]' if n<100 else '[**]')
                    style = 1 if p.get('verified') else guest_style(p.get('name','guest'))
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

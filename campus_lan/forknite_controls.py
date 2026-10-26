"""Host controls for the native wrapper, never C source modifications."""
HELP=[
 'FORKNITE | start roomy, tighten between native rounds until the first death',
 '/start — fresh tournament | /stop — stop simulation and queued rounds',
 '/diners TOTAL — fill table with random stand-ins, e.g. /diners 7 (stop first)',
 '/browser — reopen this room website with your LAN42 identity',
 '/status — native phase, diner count, timings and storm settings',
 '/timings DIE EAT SLEEP — milliseconds, e.g. /timings 600 100 100',
 '/storm on|off — progressive rounds or one continuous native run',
 '/storm step MS — reduce death deadline each round | /storm pause MS — gap',
 '/meals N — meal goal per storm round | /preset chill|chaos',
 '/sabo RANDOM N — add N cached campus students, excluding seated people',
 '/sabo LOGIN... | /sabo 4 random cohort4 | /sabo cohort4 cohort5',
 '/sabo history — selections | /tool LOGIN... — batch private photo cache',
 '/help — this guide | /leave — leave room; last departure closes game',
 'Stop before changing settings. At least two diners are needed; no filler bots.',
]


def parse(command,arg):
    bits=arg.split()
    if command=='/timings' and len(bits)==3 and all(b.isdecimal() for b in bits):
        return dict(action='configure',patch=dict(zip(('die','eat','sleep'),map(int,bits))))
    if command=='/storm':
        if bits in (['on'],['off']):return dict(action='configure',patch=dict(storm=bits[0]=='on'))
        if len(bits)==2 and bits[0] in ('step','pause') and bits[1].isdecimal():
            return dict(action='configure',patch={('shrink' if bits[0]=='step' else 'pause'):int(bits[1])})
    if command=='/meals' and len(bits)==1 and bits[0].isdecimal():return dict(action='configure',patch=dict(meals=int(bits[0])))
    if command=='/preset' and bits in (['chill'],['chaos']):return dict(action='configure',preset=bits[0])
    raise ValueError('Invalid FORKNITE settings. Use /help for examples.')


def summary(status):
    s=status['settings']
    return (f"FORKNITE {status['phase']} | round {status['round']} | {status['players']} diners | "
            f"die/eat/sleep {status['deadline']}/{s['eat']}/{s['sleep']}ms | "
            f"storm {'on' if s['storm'] else 'off'} · step {s['shrink']}ms · meals {s['meals']} · gap {s['pause']}ms")

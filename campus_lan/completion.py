"""Predictable local completion; never sends partial input to the server."""
import os

GAMES = ('bluff', 'forknite', 'hexwars', 'tetris')
COMMANDS = ('/admin', '/answer', '/authhost', '/bot', '/browser', '/connect', '/diners', '/forknite', '/game', '/games',
            '/help', '/info', '/info_campus', '/home', '/host', '/invite', '/invite-room', '/join', '/leave',
            '/lobby', '/map', '/next', '/meals', '/notify', '/practice', '/prev', '/preset', '/profile', '/quit', '/settings',
            '/restart', '/roster', '/rooms', '/signin', '/start', '/stop', '/status', '/storm', '/timings',
            '/update', '/upgrade', '/vote', '/who')


def complete(text):
    """Return (completed input, candidates). Ambiguous words expand common prefix."""
    if not text.startswith('/'):
        return text, []
    parts = text.split()
    if not parts:
        return text, []
    if len(parts) == 1 and not text.endswith(' '):
        prefix, choices, lead = parts[0], COMMANDS, ''
    else:
        command = parts[0]
        if command in ('/game', '/host') and (len(parts) == 1 or (len(parts) == 2 and not text.endswith(' '))):
            choices = GAMES
        elif command in ('/game', '/host') and parts[1:2] == ['bluff'] and len(parts) <= 3:
            choices = ('free', 'prompt')
        elif command in ('/settings','/profile') and (len(parts)==1 or (len(parts)==2 and not text.endswith(' '))):
            choices = ('signin','signout','notifications')
        elif command in ('/settings','/profile') and parts[1:2]==['notifications'] and len(parts)<=3:
            choices = ('on','off')
        elif command == '/storm' and (len(parts)==1 or (len(parts)==2 and not text.endswith(' '))):
            choices = ('on','off','step','pause')
        elif command == '/preset' and len(parts)<=2:
            choices = ('chill','chaos')
        elif command == '/notify' and len(parts) <= 2:
            choices = ('on', 'off')
        elif command == '/map' and len(parts) <= 2:
            choices = ('1', '2')
        else:
            return text, []
        prefix = '' if text.endswith(' ') else parts[-1]
        lead = text if text.endswith(' ') else text[:len(text)-len(prefix)]
    matches = [word for word in choices if word.startswith(prefix)]
    if not matches:
        return text, []
    value = matches[0] + ' ' if len(matches) == 1 else os.path.commonprefix(matches)
    return lead + value, matches

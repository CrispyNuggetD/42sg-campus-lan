"""Predictable local completion; never sends partial input to the server."""
import os

GAMES = ('bluff', 'forknite', 'hexwars', 'tetris')
COMMANDS = ('/quiet','/exams','/search','/key4','/changelog','/setup','/allow','/volume','/adjust_volume','/announce','/broadcast','/uwu','/about','/repo','/koel','/koeldrop','/roadmap','/files','/track', '/untrack', '/compose', '/dm', '/alert', '/locate', '/clusters', '/cluster', '/cluster1', '/cluster2', '/c1', '/c2', '/make', '/sabo', '/tool', '/tools', '/admin', '/answer', '/authhost', '/bot', '/browser', '/connect', '/diners', '/forknite', '/game', '/games',
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
            choices = ('search','signin','signout','notifications','clusters','clusters-auto-open','permissions','autologin','signin-close','koel-sound','host-discovery','host-poll','auto-host-join','audio-auto-on','audio-startup-volume') if command=='/settings' else ('signin','signout','notifications')
        elif command=='/settings' and parts[1:2]==['search'] and len(parts)<=3:
            choices=('ecosia','google','custom','counting')
        elif command=='/settings' and parts[1:3]==['search','counting'] and len(parts)<=4:
            choices=('on','off')
        elif command=='/settings' and parts[1:2]==['autologin'] and len(parts)<=3:
            choices=('off','saved','on')
        elif command=='/settings' and parts[1:2]==['koel-sound'] and len(parts)<=3:
            choices=('on','off','always')
        elif command=='/settings' and parts[1:2] in (['signin-close'],['audio-auto-on'],['audio-startup-volume'],['clusters-auto-open']) and len(parts)<=3:
            choices=('on','off')
        elif command=='/settings' and parts[1:2]==['permissions'] and len(parts)<=3:
            choices=('all','browser','search','help','forknite','profiles','signin','tools','photos','notifications','terminals')
        elif command=='/settings' and parts[1:2]==['permissions'] and len(parts)<=4:
            choices=('ask','allow','deny','inherit')
        elif command in ('/roadmap','/experimental') and len(parts)<=2:
            choices=('koeldrop','files')
        elif command in ('/files','/koel','/koeldrop') and len(parts)<=2:
            choices=('status','help','dock','bookmark','sidebar','favorite','flock','flock-dir','create','invite','accept','decline','dir','pending','receive','reject','resolve','trust','sync','leave')
        elif command in ('/files','/koel','/koeldrop') and parts[1:2]==['flock'] and len(parts)<=3:
            choices=('once','always','never','ask','status')
        elif command in ('/setup','/allow') and len(parts)<=2:
            choices=('all','batch')
        elif command=='/uwu' and len(parts)<=2:
            choices=('auto','on','off')
        elif command=='/track' and len(parts)<=2:
            choices=('help','status','list','lists','alerts','clusters','config','tracked','friends','mutuals','moots','oomf')
        elif command=='/track' and parts[1:2]==['status'] and len(parts)<=3:
            choices=('tracked','friends','mutuals','moots','oomf')
        elif command=='/settings' and parts[1:2]==['clusters'] and len(parts)<=3:
            choices=('c1','c2','all','on','off','include','exclude','clear')
        elif command=='/settings' and parts[1:3]==['clusters','scope'] and len(parts)<=4:
            choices=('1','2','all')
        elif command=='/sabo' and 'online' in parts[1:] and 'cluster' in parts[1:] and len(parts)<=5:
            choices=('1','2')
        elif command=='/sabo' and parts[1:2]==['online'] and len(parts)<=3:
            choices=('cluster','c1','c2')
        elif command=='/sabo' and len(parts)<=2:
            choices=('online','verified','random','history','friends','tracked','alltracked','mutuals','moots','oomf')
        elif command in ('/dm','/alert') and len(parts)<=2:
            choices=('friends','tracked','alltracked','mutuals','moots','oomf')
        elif command in ('/settings','/profile') and parts[1:2]==['notifications'] and len(parts)<=3:
            choices = ('on','off','all','host','announcements','releases','warnings','tracking','flock','files','chat','dms','pokes')
        elif command == '/storm' and (len(parts)==1 or (len(parts)==2 and not text.endswith(' '))):
            choices = ('on','off','step','pause')
        elif command == '/preset' and len(parts)<=2:
            choices = ('chill','chaos')
        elif command == '/notify' and len(parts) <= 2:
            choices = ('on','off','all','host','announcements','releases','warnings','tracking','flock','files','chat','dms','pokes')
        elif command == '/notify' and len(parts)<=3:
            choices=('on','off')
        elif command in ('/settings','/profile') and parts[1:2]==['notifications'] and len(parts)<=4:
            choices=('on','off')
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

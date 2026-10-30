"""Capture numbered campus occupants before person-targeted actions."""
from .lobby_view import roster
import re


def selection(players):
    return {number:(player.get('name','').lower(),location)
            for number,player,location in roster(players) if location}


def capture(arguments, players):
    shown=selection(players)
    selected={}
    resolved=[]
    for argument in arguments:
        if argument.isdecimal():
            number=int(argument)
            if number not in shown:
                raise ValueError('No campus occupant '+argument+' in this snapshot. Refresh /clusters and check the numbered roster.')
            name=shown[number][0]
            if name.isdecimal() or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',name):
                raise ValueError('Campus occupant has an invalid Intra login; refresh the snapshot.')
            selected[number]=shown[number]
            resolved.append(name)
        else:resolved.append(argument)
    return resolved,selected


def describe(selected):
    return ', '.join(str(number)+' = '+name+' (c%dr%ds%d)'%location
                     for number,(name,location) in selected.items())


def unchanged(selected, players):
    current=selection(players)
    return all(current.get(number)==entry for number,entry in selected.items())


class ProfileCommands:
    """UI hooks: number_players, report_profile, confirm_profile, open_urls."""
    def profile_command(self, text):
        parts=text.split()
        if not parts or parts[0]!='/profile':return False
        if parts[1:2] and parts[1] in ('signin','signout','notifications'):return False
        arguments=parts[1:]
        def launch(resolved, literal_logins=()):
            try:
                from .profile_browser import resolve
                urls=resolve(resolved,literal_logins=literal_logins) if resolved else ['https://profile-v3.intra.42.fr/']
                self.open_urls('profiles',urls,'Open '+str(len(urls))+' Intra profile tab(s) in your browser?')
            except (OSError,ValueError) as error:self.report_profile(str(error))
        if any(argument.isdecimal() for argument in arguments):
            self.confirm_occupants(arguments,lambda resolved:launch(resolved,[name for original,name in zip(arguments,resolved) if original.isdecimal()]))
        else:launch(arguments)
        return True

    def confirm_occupants(self, arguments, action):
        players=self.number_players()
        if players is None:
            self.load_number_roster(lambda:self.confirm_occupants(arguments,action))
            return
        try:resolved,selected=capture(arguments,players)
        except ValueError as error:
            self.report_profile(str(error));return
        def accept():
            current=self.number_players()
            if current is None or not unchanged(selected,current):
                self.report_profile('Campus occupants changed. Refresh and enter the number again; action cancelled.')
                return
            action(resolved)
        self.confirm_profile('Use these campus occupants? '+describe(selected)+' [y/N]',accept,
                             lambda:self.report_profile('Occupant selection cancelled.'))

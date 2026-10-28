"""Local click and function-key controls; never dispatched from network data."""
import curses


class QuickControls:
    def quick_action(self, action):
        if getattr(self, 'permission_prompt', False) or getattr(self, 'wizard', None):
            return
        if action == 'account':
            if getattr(self, 'role', 'lobby') == 'game':
                self.lines.append('Use F2 or the account button in your HQ window.')
            elif getattr(self,'signed_in',getattr(self,'secure',False)):
                self.settings_command('/settings signout')
            else:
                self.start_signin()
        elif action == 'clusters':
            if getattr(self,'role','lobby')=='game':self.lines.append('Use F7 in your HQ window for campus clusters.')
            elif not self.local_api_command('/clusters'):self.send(dict(type='command',text='/clusters'))
        elif action == 'mute':
            self.shortcut_audio_muted = True
            self.volume_command('/volume 0')
            self.lines.append('Uwu output paused in this window; F4 resumes output control.')
        elif action == 'volume':
            self.shortcut_audio_muted = False
            self.volume_command('/volume')
            if not getattr(self,'key4_discovered',False):
                self.key4_discovered=True
                self.lines.append('Security-history joke: “The private key is 4.” Click [4?] in the footer or /key4 to search the eMudhra incident.')
        elif action == 'key4':
            self.search_command('/key4')
        elif action == 'uwu':
            self.uwu_command('/uwu')
        elif action == 'auto':
            self.uwu_command('/uwu off' if getattr(self, 'uwu_auto_due', None) is not None else '/uwu auto')

    def quick_key(self, key):
        for number, action in enumerate(('account', 'mute', 'volume', 'uwu', 'auto', 'clusters'), 2):
            if key == curses.KEY_F0 + number:
                self.quick_action(action)
                return True
        return False

    def draw_quick_controls(self, screen):
        self.control_hits = []
        if getattr(self, 'permission_prompt', False) or getattr(self, 'wizard', None):
            return
        h, w = screen.getmaxyx()
        signed = getattr(self,'signed_in',getattr(self,'secure',False))
        if getattr(self, 'role', 'lobby') != 'game':
            text = ('42 signed in: click here to sign out (F2).' if signed else
                    'Guest: /signin or click here (F2). API views need the campus host online.')
            self.line(screen, h-3, text, curses.A_BOLD)
            self.control_hits.append((h-3, 0, min(len(text), w-1), 'account'))
        controls = [('account', 'F2 '+('Sign out' if signed else 'Sign in')),
                    ('mute', 'F3 Mute'), ('volume', 'F4 0/30%'), ('uwu', 'F5 Uwu'),
                    ('auto', 'F6 Auto:'+('on' if getattr(self, 'uwu_auto_due', None) is not None else 'off'))]
        controls.append(('clusters','F7 Clusters'))
        if getattr(self,'key4_discovered',False):controls.append(('key4','4?'))
        x = 0
        for action, label in controls:
            text = '['+label+']'
            self.line(screen, h-2, text, curses.A_REVERSE, x=x)
            self.control_hits.append((h-2, x, min(x+len(text), w-1), action))
            x += len(text)+1

    def quick_click(self, x, y):
        for row, left, right, action in getattr(self, 'control_hits', []):
            if row == y and left <= x < right:
                self.quick_action(action)
                return True
        return False

import queue
import os
import unittest
from unittest.mock import patch
from campus_lan.client import Client, request_terminal_resize
from campus_lan.presence import API

class Screen:
    def __init__(self):
        self.lines = []
    def getmaxyx(self): return (32,110)
    def erase(self): pass
    def addnstr(self,y,x,text,n,attr):
        assert 0<=y<32 and 0<=x<110
        self.lines.append(text[:n])
    def refresh(self): pass

class Terminal:
    def __init__(self, tty=True):
        self.tty = tty
        self.output = ''
        self.flushed = False
    def isatty(self): return self.tty
    def write(self, text): self.output += text
    def flush(self): self.flushed = True

class ClientChecks(unittest.TestCase):
    def test_terminal_resize_only_grows_undersized_dimensions(self):
        terminal = Terminal()
        resized = request_terminal_resize(
            terminal, lambda fallback: os.terminal_size((90, 20)))
        self.assertTrue(resized)
        self.assertEqual(terminal.output, '\033[8;28;90t')
        self.assertTrue(terminal.flushed)

    def test_terminal_resize_skips_large_or_non_tty_output(self):
        large = Terminal()
        self.assertFalse(request_terminal_resize(
            large, lambda fallback: os.terminal_size((100, 40))))
        self.assertEqual(large.output, '')
        redirected = Terminal(False)
        self.assertFalse(request_terminal_resize(
            redirected, lambda fallback: os.terminal_size((20, 10))))

    def test_render_and_private_results_in_history(self):
        c = Client.__new__(Client)
        c.name,c.connected,c.state = 'hnah',True,{}
        c.input,c.play,c.scroll = '',False,0
        from collections import deque
        c.lines,c.inbox = deque(maxlen=500),queue.Queue()
        c.game = {}
        c.inbox.put(dict(type='game',game='bluff',room='1',phase='voting',
                        leader='hnah',options=[dict(number=1,text='test',author=None)]))
        c.consume()
        self.assertIn('hidden',c.lines[-1])
        c.game = {}
        screen = Screen()
        c.draw(screen)
        self.assertTrue(any('[Guest]' in text for text in screen.lines))

    def test_lobby_chat_notifies_other_senders_but_not_system_events(self):
        c = Client.__new__(Client)
        c.name, c.role = 'hnah', 'lobby'
        c.lines, c.inbox = [], queue.Queue()
        for text in ('darren [Guest]: hello', 'darren [Guest]: again',
                     'hnah [Guest]: my message', 'darren went offline.'):
            c.inbox.put(dict(type='event', text=text))
        with patch.object(c, 'notify') as notify:
            c.consume()
        self.assertEqual([call.args[0] for call in notify.call_args_list],
                         ['darren [Guest]: hello', 'darren [Guest]: again'])
        self.assertTrue(all(call.kwargs == {'throttle': False}
                            for call in notify.call_args_list))
        self.assertEqual(len(c.lines), 4)
        c.role = 'game'
        c.inbox.put(dict(type='event', text='darren [Guest]: game window'))
        with patch.object(c, 'notify') as notify:
            c.consume()
            notify.assert_not_called()

    def test_chat_notifications_respect_mute_without_dropping_bursts(self):
        c = Client.__new__(Client)
        c.notify_enabled, c.last_notice = True, 100
        with patch('campus_lan.client.time.monotonic', return_value=101), \
             patch('campus_lan.client.shutil.which', return_value=None), \
             patch('campus_lan.client.curses.beep') as beep:
            c.notify('darren [Guest]: first', throttle=False)
            c.notify('darren [Guest]: second', throttle=False)
            self.assertEqual(beep.call_count, 2)
            c.notify('ordinary presence notice')
            self.assertEqual(beep.call_count, 2)
            c.notify_enabled = False
            c.notify('darren [Guest]: muted', throttle=False)
            self.assertEqual(beep.call_count, 2)

    def test_api_location_only(self):
        api = API()
        api.token,api.expires = 'fake-test-token',10**12
        from io import BytesIO
        with patch('urllib.request.urlopen',return_value=BytesIO(b'{"location":"c1r2s3","email":"unused"}')):
            self.assertEqual(api.get_seat('hnah'),'c1r2s3')

if __name__=='__main__':
    unittest.main()

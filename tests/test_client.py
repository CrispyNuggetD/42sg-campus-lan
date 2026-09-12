import queue
import unittest
from unittest.mock import patch
from campus_lan.client import Client
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

class ClientChecks(unittest.TestCase):
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

    def test_api_location_only(self):
        api = API()
        api.token,api.expires = 'fake-test-token',10**12
        from io import BytesIO
        with patch('urllib.request.urlopen',return_value=BytesIO(b'{"location":"c1r2s3","email":"unused"}')):
            self.assertEqual(api.get_seat('hnah'),'c1r2s3')

if __name__=='__main__':
    unittest.main()

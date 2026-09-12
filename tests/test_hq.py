import collections
import queue
import unittest
from unittest.mock import Mock, patch
from campus_lan.client import Client

class HQ(unittest.TestCase):
    def client(self):
        c=Client.__new__(Client)
        c.name='hnah'
        c.home=('127.0.0.1',32101)
        c.game_target=('127.0.0.1',32102)
        c.lines=collections.deque()
        c.peer_callback=Mock()
        return c

    def test_link_stays_home_and_game_uses_selected_peer(self):
        c=self.client()
        c.link_friend('192.168.1.12',32103)
        c.peer_callback.assert_called_once_with('192.168.1.12',32103)
        self.assertEqual(c.home,('127.0.0.1',32101))
        with patch('campus_lan.client.subprocess.run',return_value=Mock(returncode=0)) as run:
            c.open_game('/join 7')
            args=run.call_args[0][0]
            self.assertEqual(args[2:],['game','192.168.1.12','--port','32103','--guest-name','hnah','--room','7'])
            c.open_game('/host bluff prompt')
            args=run.call_args[0][0]
            self.assertEqual(args[2:6],['game','127.0.0.1','--port','32101'])
            self.assertEqual(args[-4:],['--create','bluff','--game-mode','prompt'])

    def test_game_initial_command_waits_for_welcome(self):
        c=self.client()
        c.initial_command='/join 7'
        c.inbox=queue.Queue()
        c.send=Mock()
        c.inbox.put(dict(type='welcome',id='2',version='test'))
        c.consume()
        c.send.assert_called_once_with(dict(type='command',text='/join 7'))
        self.assertIsNone(c.initial_command)

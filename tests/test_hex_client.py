from collections import deque
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan.client import Client
from campus_lan.hexwars import HexWars
from test_hexwars import players


class Screen:
    def __init__(self):
        self.rows = [' ' * 76 for _ in range(28)]

    def getmaxyx(self):
        return 28, 76

    def addnstr(self, y, x, text, n, attr):
        text = text[:n]
        assert x + len(text) < 76
        self.rows[y] = self.rows[y][:x] + text + self.rows[y][x + len(text):]


class HexClient(unittest.TestCase):
    def client(self):
        c = Client.__new__(Client)
        c.game = dict(game='hexwars', room='1', phase='waiting', bots=[])
        c.lines = deque(maxlen=500)
        c.inbox = queue.Queue()
        c.send = Mock()
        return c

    def test_menu_starter_does_not_overwrite_and_demo_submission(self):
        c = self.client()
        c.bot_command('/bot')
        self.assertEqual(c.wizard[0], 'bot_menu')
        c.wizard_answer('2')
        c.send.assert_called_with(dict(type='command', text='/bot demo'))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'my bot.c'
            c.bot_command('/bot starter "' + str(path) + '"')
            self.assertIn('bot_turn', path.read_text())
            path.write_text('my edits')
            c.bot_command('/bot starter "' + str(path) + '"')
            self.assertEqual(path.read_text(), 'my edits')

    def test_compiler_result_does_not_upload_into_new_room(self):
        c = self.client()
        c.inbox.put(dict(type='local_bot', room='2', wasm='abc'))
        c.consume()
        c.send.assert_not_called()
        self.assertIn('Room changed', c.lines[-1])

    def test_board_and_workshop_fit_minimum_terminal(self):
        c = self.client()
        screen = Screen()
        c.draw_hexwars(screen)
        self.assertTrue(any('BOT WORKSHOP' in row for row in screen.rows))
        c.game.update(HexWars(players(6)).view())
        screen = Screen()
        c.draw_hexwars(screen)
        text = '\n'.join(screen.rows)
        self.assertEqual(text.count('<'), 61)
        for name in ('p0', 'p1', 'p2', 'p3', 'p4', 'p5'):
            self.assertIn(name, text)
        self.assertIn('Turn 0/300', text)


if __name__ == '__main__':
    unittest.main()

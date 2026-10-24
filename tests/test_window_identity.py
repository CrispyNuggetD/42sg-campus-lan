import io
import unittest
from unittest.mock import patch
from campus_lan.client import Client
from test_client import Screen

class WindowIdentity(unittest.TestCase):
    def client(self,role):
        c=Client.__new__(Client)
        c.role,c.name,c.connected,c.state=role,'hnah',True,{}
        c.game={}
        c.colors=True
        return c

    def test_hq_and_game_banners_are_distinct(self):
        hq,game=self.client('lobby'),self.client('game')
        game.game=dict(game='tetris',room='7')
        with patch('campus_lan.client.curses.color_pair',side_effect=lambda pair:pair<<8) as colour:
            hq.draw(Screen())
            self.assertEqual(colour.call_args[0][0],2)
            screen=Screen()
            game.draw(screen)
            self.assertEqual(colour.call_args[0][0],4)
        self.assertIn('HQ LOBBY',hq.terminal_title())
        self.assertIn('GAME | TETRIS | ROOM 7',screen.lines[0])

    def test_titles_change_once_and_strip_control_sequences(self):
        c=self.client('game')
        c.name='bad\x1b\x07\nname'
        output=io.StringIO()
        with patch('campus_lan.client.sys.stdout',output), patch.object(output,'isatty',return_value=True), patch('campus_lan.client.subprocess.run'):
            c.update_title()
            c.update_title()
            c.game=dict(game='bluff',room='2')
            c.update_title()
        value=output.getvalue()
        self.assertEqual(value.count('\x1b]0;'),2)
        self.assertEqual(value.count('\x07'),2)
        self.assertIn('WHO SAID THAT? | ROOM 2',value)
        self.assertIn('badname',value)

    def test_tmux_name_contains_game_and_room(self):
        c=self.client('game');c.game=dict(game='forknite',room='7')
        with patch.dict('os.environ',{'TMUX_PANE':'%123'}), patch('campus_lan.client.shutil.which',return_value='/usr/bin/tmux'), patch('campus_lan.client.subprocess.run') as run:
            c.update_title();c.update_title()
        self.assertEqual(run.call_count,1)
        self.assertEqual(run.call_args.args[0],['tmux','rename-window','-t','%123','forknite-7'])

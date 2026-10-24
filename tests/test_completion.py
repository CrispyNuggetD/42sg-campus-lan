import unittest
from campus_lan.completion import complete


class Completion(unittest.TestCase):
    def test_commands_and_games(self):
        self.assertEqual(complete('/sig'),('/signin ',['/signin']))
        self.assertEqual(complete('/rest'),('/restart ',['/restart']))
        self.assertEqual(complete('/game f'),('/game forknite ',['forknite']))
        self.assertEqual(complete('/game h'),('/game hexwars ',['hexwars']))
        self.assertEqual(complete('/host t'),('/host tetris ',['tetris']))
        self.assertEqual(complete('/game ')[1],['bluff','forknite','hexwars','tetris'])

    def test_signout_does_not_collide_with_signin(self):
        self.assertEqual(complete('/sign'),('/signin ',['/signin']))
        self.assertEqual(complete('/signo'),('/signo',[]))

    def test_modes_options_and_plain_text(self):
        self.assertEqual(complete('/game bluff p'),('/game bluff prompt ',['prompt']))
        self.assertEqual(complete('/game bluff ')[1],['free','prompt'])
        self.assertEqual(complete('/notify o'),('/notify o',['on','off']))
        self.assertEqual(complete('hello'),('hello',[]))
        self.assertEqual(complete('/game forknite --exec'),('/game forknite --exec',[]))

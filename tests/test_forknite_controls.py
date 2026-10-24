import unittest
from campus_lan.forknite_controls import parse,summary,HELP


class Controls(unittest.TestCase):
    def test_valid_settings(self):
        self.assertEqual(parse('/timings','600 100 100')['patch'],dict(die=600,eat=100,sleep=100))
        self.assertEqual(parse('/storm','on')['patch'],dict(storm=True))
        self.assertEqual(parse('/storm','step 25')['patch'],dict(shrink=25))
        self.assertEqual(parse('/storm','pause 2000')['patch'],dict(pause=2000))
        self.assertEqual(parse('/meals','3')['patch'],dict(meals=3))
        self.assertEqual(parse('/preset','chaos')['preset'],'chaos')

    def test_invalid_arguments(self):
        for cmd,arg in [('/timings','1 2'),('/storm','yes'),('/preset','evil'),('/meals','1; touch anything')]:
            with self.assertRaises(ValueError):parse(cmd,arg)
        self.assertIn('/stop','\n'.join(HELP));self.assertIn('/timings','\n'.join(HELP))

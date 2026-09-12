import unittest
from campus_lan.games import Tetris, Bluff

class Games(unittest.TestCase):
    def test_tetris_walls_and_rotation(self):
        t = Tetris(42)
        for _ in range(30):
            t.move('left')
        self.assertTrue(t.fits(t.shape,t.x,t.y))
        t.move('rotate')
        self.assertTrue(t.fits(t.shape,t.x,t.y))
        t.move('drop')
        self.assertEqual(sum(bool(c) for row in t.board for c in row),4)

    def test_line_clear_and_topout(self):
        t = Tetris(1)
        t.board[-1] = [1]*10
        for x in range(3,7):
            t.board[-1][x] = 0
        t.kind,t.shape,t.x,t.y = 1,[(0,0),(1,0),(2,0),(3,0)],3,17
        t.lock()
        self.assertEqual((t.lines,t.score),(1,100))
        t.board = [[1]*10 for _ in range(18)]
        t.spawn()
        self.assertTrue(t.over)

    def test_bluff_privacy_scoring_and_timeout(self):
        g = Bluff({'1':'a','2':'b','3':'c'},'1','prompt',0,10)
        for p in g.players:
            g.answer(p,'secret'+p,1)
        self.assertNotIn('options',g.view())
        g.tick(2)
        self.assertEqual(g.phase,'voting')
        self.assertTrue(all(x['author'] is None for x in g.view()['options']))
        actual = [g.players[p] for p,_ in g.options]
        for p in g.players:
            g.vote(p,actual,3)
        g.tick(4)
        self.assertEqual(g.phase,'results')
        self.assertTrue(all(x['author'] for x in g.view()['options']))
        self.assertIn('a: 4 points',g.result)
        timeout = Bluff({'1':'a','2':'b','3':'c'},'1','free',0,5)
        timeout.tick(6)
        self.assertEqual(timeout.phase,'results')
        self.assertIn('cancelled',timeout.result)

    def test_invalid_guesses_and_late_answer(self):
        g = Bluff({'1':'a','2':'b','3':'c'},'1','free',0,5)
        with self.assertRaises(ValueError):
            g.answer('1','late',6)
        g.answer('1','ok',1)
        g.answer('2','also ok',1)
        g.tick(6)
        with self.assertRaises(ValueError):
            g.vote('2',['invented'],7)
        g.tick(12)
        self.assertEqual(g.phase,'results')

if __name__=='__main__':
    unittest.main()

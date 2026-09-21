import unittest
from campus_lan.hexwars import HexWars, demo_action


def players(count=2):
    return {str(i): dict(name='p' + str(i), attributes=[3, 3, 3], wasm=None)
            for i in range(count)}


class HexRules(unittest.TestCase):
    def test_board_topology_and_spawns(self):
        for count in range(2, 7):
            game = HexWars(players(count))
            self.assertEqual(len(game.cells), 61)
            self.assertEqual(len(game.snapshot(0)), 616)
            self.assertEqual(sum(c['owner'] >= 0 for c in game.cells), count)
            for i, cell in enumerate(game.cells):
                for direction, neighbor in enumerate(cell['neighbors']):
                    if neighbor >= 0:
                        self.assertEqual(game.cells[neighbor]['neighbors'][(direction + 3) % 6], i)

    def arena(self, count=2):
        game = HexWars(players(count))
        for cell in game.cells:
            cell.update(owner=-1, units=0)
        center = next(i for i, c in enumerate(game.cells) if c['q'] == c['r'] == 0)
        neighbors = game.cells[center]['neighbors']
        for i in range(count):
            game.cells[neighbors[i]].update(owner=i, units=20)
        return game, center, neighbors

    def test_simultaneous_tie_does_not_favor_submission_order(self):
        game, center, neighbors = self.arena()
        game.step({'1': {'action': [neighbors[1], center, 10]},
                   '0': {'action': [neighbors[0], center, 10]}})
        self.assertEqual((game.cells[center]['owner'], game.cells[center]['units']), (-1, 0))
        self.assertEqual(game.cells[neighbors[0]]['units'], 13)

    def test_attack_armor_growth_and_friendly_reinforcement(self):
        game, center, neighbors = self.arena()
        game.players[0]['attributes'] = [2, 5, 2]
        game.cells[center].update(owner=1, units=5)
        game.step({'0': {'action': [neighbors[0], center, 10]}, '1': {'action': [-1, -1, 0]}})
        # 100 attacking power - 40 defending power = 6 survivors + 2 growth.
        self.assertEqual((game.cells[center]['owner'], game.cells[center]['units']), (0, 8))
        game.step({'0': {'action': [neighbors[0], center, 5]}, '1': {'action': [-1, -1, 0]}})
        self.assertEqual(game.cells[center]['units'], 15)

    def test_three_way_battle_and_max_units(self):
        game, center, neighbors = self.arena(3)
        game.step({str(i): {'action': [neighbors[i], center, 10 if i == 0 else 3]}
                   for i in range(3)})
        self.assertEqual((game.cells[center]['owner'], game.cells[center]['units']), (0, 7))
        game.cells[center]['units'] = 99
        game.step({str(i): {'action': [-1, -1, 0]} for i in range(3)})
        self.assertEqual(game.cells[center]['units'], 99)

    def test_illegal_moves_and_timeouts_disqualify_without_crashing(self):
        game = HexWars(players())
        for action in ([100, 0, 1], [0, 60, 1], [0, 1, -1], [True, 1, 2], 'bad'):
            self.assertFalse(game.valid(0, action))
        for _ in range(3):
            game.step({'0': {'error': 'timeout'}, '1': {'action': [-1, -1, 0]}})
        self.assertTrue(game.over)
        self.assertIn('Winner: p1', game.result)
        self.assertEqual(game.players[0]['faults'], 3)
        self.assertFalse(game.alive(0))

    def test_full_games_terminate_and_are_deterministic(self):
        states = []
        for _ in range(2):
            game = HexWars(players(6), max_turns=80)
            while not game.over:
                game.step({p['pid']: {'action': demo_action(game, i)}
                           for i, p in enumerate(game.players) if game.alive(i)})
            self.assertLessEqual(game.turn, 80)
            self.assertTrue(game.result)
            self.assertTrue(all(0 <= c['units'] <= 99 for c in game.cells))
            states.append(game.view())
        self.assertEqual(*states)

    def test_forfeit_and_turn_limit_draw(self):
        game = HexWars(players(), max_turns=1)
        game.step({str(i): {'action': [-1, -1, 0]} for i in range(2)})
        self.assertTrue(game.result.startswith('Draw:'))
        game = HexWars(players())
        game.forfeit('0')
        self.assertTrue(game.over)
        self.assertIn('p1', game.result)

    def test_simultaneous_disqualifications_produce_draw(self):
        game = HexWars(players())
        for _ in range(3):
            game.step({'0': {'error': 'timeout'}, '1': {'error': 'timeout'}})
        self.assertEqual(game.result, 'Draw: no armies remain.')
        self.assertTrue(all(p['faults'] == 3 for p in game.players))


if __name__ == '__main__':
    unittest.main()

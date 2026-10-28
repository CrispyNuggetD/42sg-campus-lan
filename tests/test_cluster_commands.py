import unittest
from campus_lan.cluster_commands import normalize_cluster_command
from campus_lan.lobby_view import lobby_lines


class ClusterCommandTests(unittest.TestCase):
    def test_aliases(self):
        for command in ('/clusters', './clusters'):
            self.assertEqual(normalize_cluster_command(command), '/clusters')
        for number in (1, 2):
            for command in (f'/cluster {number}', f'/cluster{number}', f'/c{number}', f'/clusters {number}'):
                self.assertEqual(normalize_cluster_command(command), f'/clusters {number}')
        self.assertEqual(normalize_cluster_command('/c1 2'), '/clusters invalid')

    def test_both_maps_share_roster_numbers(self):
        players = [{'name': 'one', 'seat': 'c1r1s1'}, {'name': 'two', 'seat': 'c2r1s1'}]
        lines = [''.join(text for text, _ in line) for line in lobby_lines(players, 'map', 0)]
        output = '\n'.join(lines)
        self.assertIn('CLUSTER 1', output)
        self.assertIn('CLUSTER 2', output)
        self.assertEqual(sum('CURRENTLY ONLINE -' in line for line in lines), 1)
        self.assertIn('[#1]', output)
        self.assertIn('[#2]', output)

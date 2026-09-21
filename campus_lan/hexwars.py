"""Deterministic, simultaneous-turn Hex Wars rules (no I/O)."""
from collections import defaultdict

DIRECTIONS = ((1, 0), (1, -1), (0, -1), (-1, 0), (-1, 1), (0, 1))
RADIUS = 4
MAX_TURNS = 300
MAX_UNITS = 99


class HexWars:
    def __init__(self, players, max_turns=MAX_TURNS):
        if not 2 <= len(players) <= 6:
            raise ValueError('Hex Wars needs 2–6 bots. Use /practice for a computer opponent.')
        self.players = [dict(pid=pid, name=bot['name'], attributes=list(bot['attributes']),
                             faults=0, status='ready') for pid, bot in players.items()]
        self.turn, self.max_turns = 0, max_turns
        self.over, self.result = False, ''
        self.cells = [dict(q=q, r=r, owner=-1, units=8)
                      for r in range(-RADIUS, RADIUS + 1)
                      for q in range(-RADIUS, RADIUS + 1) if abs(q + r) <= RADIUS]
        index = {(c['q'], c['r']): i for i, c in enumerate(self.cells)}
        for cell in self.cells:
            cell['neighbors'] = [index.get((cell['q'] + q, cell['r'] + r), -1)
                                 for q, r in DIRECTIONS]
        corners = ((4, 0), (4, -4), (0, -4), (-4, 0), (-4, 4), (0, 4))
        slots = {2: (0, 3), 3: (0, 2, 4), 4: (0, 1, 3, 4),
                 5: (0, 1, 2, 3, 4), 6: (0, 1, 2, 3, 4, 5)}[len(players)]
        for player, slot in enumerate(slots):
            self.cells[index[corners[slot]]].update(owner=player, units=24)

    def alive(self, player):
        return any(c['owner'] == player for c in self.cells)

    def snapshot(self, player):
        words = [1, self.turn, player, len(self.players), len(self.cells), self.max_turns]
        for cell in self.cells:
            words.extend([cell['q'], cell['r'], cell['owner'], cell['units'], *cell['neighbors']])
        return words

    def forfeit(self, pid, reason='left', finish=True):
        for player, info in enumerate(self.players):
            if info['pid'] == pid:
                info['status'] = reason
                for cell in self.cells:
                    if cell['owner'] == player:
                        cell.update(owner=-1, units=0)
        if finish:
            self.finish_if_needed()

    def fault(self, player, reason):
        info = self.players[player]
        info['faults'] += 1
        info['status'] = reason[:100]
        if info['faults'] >= 3:
            self.forfeit(info['pid'], 'disqualified: 3 bot faults', finish=False)

    def valid(self, player, action):
        if not isinstance(action, (tuple, list)) or len(action) != 3 or any(type(v) is not int for v in action):
            return False
        source, target, units = action
        if units == 0:
            return True
        return (0 <= source < len(self.cells) and 0 <= target < len(self.cells)
                and self.cells[source]['owner'] == player
                and target in self.cells[source]['neighbors']
                and 1 <= units < self.cells[source]['units'])

    def step(self, replies):
        if self.over:
            return
        orders = []
        # Validate every order against the same snapshot before any deductions.
        for player, info in enumerate(self.players):
            if not self.alive(player):
                continue
            reply = replies.get(info['pid'], {'error': 'missing bot reply'})
            action = reply.get('action')
            if reply.get('error') or not self.valid(player, action):
                self.fault(player, str(reply.get('error') or 'invalid move'))
            else:
                info['status'] = 'playing'
                if action[2]:
                    orders.append((player, *action))
        self.finish_if_needed()
        if self.over:
            return
        arrivals = defaultdict(lambda: defaultdict(int))
        for player, source, target, units in orders:
            self.cells[source]['units'] -= units
            arrivals[target][player] += units
        for target, armies in arrivals.items():
            cell = self.cells[target]
            owner = cell['owner']
            armies[owner] += cell['units']
            power = {}
            factors = {}
            for player, units in armies.items():
                factor = 8 if player == -1 else 5 + self.players[player]['attributes'][2 if player == owner else 1]
                factors[player] = factor
                power[player] = units * factor
            strongest = max(power, key=power.get)
            remaining = power[strongest] - sum(p for player, p in power.items() if player != strongest)
            if remaining <= 0:
                cell.update(owner=-1, units=0)
            else:
                cell.update(owner=strongest, units=min(MAX_UNITS, (remaining + factors[strongest] - 1) // factors[strongest]))
        for cell in self.cells:
            if cell['owner'] >= 0:
                cell['units'] = min(MAX_UNITS, cell['units'] + self.players[cell['owner']]['attributes'][0])
        self.turn += 1
        self.finish_if_needed()

    def finish_if_needed(self):
        active = [i for i in range(len(self.players)) if self.alive(i)]
        if self.over or (len(active) > 1 and self.turn < self.max_turns):
            return
        self.over = True
        if not active:
            self.result = 'Draw: no armies remain.'
            return
        scores = {i: (sum(c['owner'] == i for c in self.cells),
                      sum(c['units'] for c in self.cells if c['owner'] == i)) for i in active}
        best = max(scores.values())
        winners = [self.players[i]['name'] for i in active if scores[i] == best]
        self.result = ('Winner: ' if len(winners) == 1 else 'Draw: ') + ', '.join(winners)
        self.result += ' (last army standing)' if len(active) == 1 else ' (turn limit: territory, then units)'

    def view(self):
        scores = []
        for i, info in enumerate(self.players):
            scores.append(dict(name=info['name'], symbol=chr(65 + i), attributes=info['attributes'],
                               tiles=sum(c['owner'] == i for c in self.cells),
                               units=sum(c['units'] for c in self.cells if c['owner'] == i),
                               faults=info['faults'], status=info['status'] if self.alive(i) else
                               (info['status'] if info['status'].startswith('disqualified') else 'eliminated')))
        return dict(phase='results' if self.over else 'running', turn=self.turn,
                    max_turns=self.max_turns, cells=[dict(c) for c in self.cells],
                    scores=scores, result=self.result, over=self.over)


def demo_action(engine, player):
    """Built-in sparring bot; also makes the arena playable without a compiler."""
    best, action = -100000, [-1, -1, 0]
    cells = engine.cells

    def distance(a, b):
        return (abs(a['q'] - b['q']) + abs(a['r'] - b['r'])
                + abs(a['q'] + a['r'] - b['q'] - b['r'])) // 2

    enemies = [c for c in cells if c['owner'] != player]
    if not enemies:
        return action
    for i, cell in enumerate(cells):
        if cell['owner'] != player or cell['units'] < 3:
            continue
        target = min(enemies, key=lambda c: distance(cell, c))
        for n in cell['neighbors']:
            if n < 0:
                continue
            neighbor = cells[n]
            if neighbor['owner'] != player:
                score = 100 + cell['units'] - 2 * neighbor['units']
            elif distance(neighbor, target) < distance(cell, target) and neighbor['units'] + cell['units'] < MAX_UNITS:
                score = cell['units'] - distance(cell, target)
            else:
                continue
            if score > best:
                best, action = score, [i, n, cell['units'] - 1]
    return action

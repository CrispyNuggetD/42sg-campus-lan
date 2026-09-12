"""Server-authoritative game rules, independent of terminal/network."""
import random

SHAPES = [((0,1),(1,1),(2,1),(3,1)), ((1,0),(2,0),(1,1),(2,1)),
          ((1,0),(0,1),(1,1),(2,1)), ((1,0),(2,0),(0,1),(1,1)),
          ((0,0),(1,0),(1,1),(2,1)), ((0,0),(0,1),(1,1),(2,1)),
          ((2,0),(0,1),(1,1),(2,1))]
PROMPTS = ["The project passes every test except one. What does {leader} say?",
           "A duck walks into the cluster. What does {leader} say?",
           "The vending machine dispenses a compiler error. {leader}'s response?",
           "Someone asks for one tiny favour at 3am. What does {leader} say?",
           "You can rename one C keyword. What would {leader} propose?",
           "A segfault sends you a friend request. What does {leader} reply?"]

class Tetris:
    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.board = [[0]*10 for _ in range(18)]
        self.score = self.lines = 0
        self.over = False
        self.spawn()

    def spawn(self):
        self.kind = self.rng.randrange(7)+1
        self.shape = list(SHAPES[self.kind-1])
        self.x, self.y = 3, 0
        self.over = not self.fits(self.shape, self.x, self.y)

    def fits(self, shape, x, y):
        return all(0 <= x+a < 10 and 0 <= y+b < 18 and
                   not self.board[y+b][x+a] for a,b in shape)

    def move(self, action):
        if self.over:
            return
        if action == 'rotate':
            if self.kind == 2:
                return
            shape = [(2-b,a) for a,b in self.shape]
            for dx in (0,-1,1,-2,2):
                if self.fits(shape,self.x+dx,self.y):
                    self.shape, self.x = shape, self.x+dx
                    return
        elif action in ('left','right'):
            dx = -1 if action == 'left' else 1
            if self.fits(self.shape,self.x+dx,self.y):
                self.x += dx
        elif action == 'drop':
            while self.fits(self.shape,self.x,self.y+1):
                self.y += 1
            self.lock()
        elif action == 'down':
            if self.fits(self.shape,self.x,self.y+1):
                self.y += 1
            else:
                self.lock()

    def lock(self):
        for a,b in self.shape:
            self.board[self.y+b][self.x+a] = self.kind
        remaining = [row for row in self.board if not all(row)]
        cleared = 18-len(remaining)
        self.lines += cleared
        self.score += (0,100,300,500,800)[cleared]
        self.board = [[0]*10 for _ in range(cleared)]+remaining
        self.spawn()

    def view(self):
        board = [row[:] for row in self.board]
        if not self.over:
            for a,b in self.shape:
                board[self.y+b][self.x+a] = self.kind
        return dict(board=board,score=self.score,lines=self.lines,over=self.over)

class Bluff:
    def __init__(self, players, leader, mode, now, seconds=45, rng=None):
        self.players = dict(players)
        self.leader = leader
        self.rng = rng or random.Random()
        self.prompt = (self.rng.choice(PROMPTS).format(leader=self.players[leader])
                       if mode == 'prompt' else
                       'Write a message unlike yourself. Then find the real leader!')
        self.phase, self.deadline = 'writing', now+seconds
        self.seconds = seconds
        self.answers, self.votes, self.options = {}, {}, []
        self.result = ''

    def answer(self, player, text, now):
        if self.phase != 'writing' or player not in self.players or now >= self.deadline:
            raise ValueError('Not accepting answers now.')
        if not text.strip():
            raise ValueError('Write something first.')
        self.answers[player] = text[:240]

    def tick(self, now):
        if self.phase == 'writing' and (len(self.answers)==len(self.players) or now>=self.deadline):
            if self.leader not in self.answers or len(self.answers)<2:
                self.phase = 'results'
                self.result = 'Round cancelled: need the leader and at least one other answer.'
                return
            self.options = list(self.answers.items())
            self.rng.shuffle(self.options)
            self.phase, self.deadline = 'voting', now+self.seconds
        elif self.phase == 'voting' and (len(self.votes)>=len(self.players) or now>=self.deadline):
            self.phase = 'results'
            scores = {p:0 for p in self.players}
            # Everyone guesses the true author of each entry. 2 points per correct
            # guess; an author earns 1 for each opponent they fooled.
            for voter, guesses in self.votes.items():
                for (author,_), guess in zip(self.options, guesses):
                    if author == voter:
                        continue
                    if guess == author:
                        scores[voter] += 2
                    else:
                        scores[author] += 1
            self.result = ' | '.join(f'{self.players[p]}: {n} points' for p,n in scores.items())

    def vote(self, player, guesses, now):
        if self.phase != 'voting' or player not in self.players or now >= self.deadline:
            raise ValueError('Not accepting votes now.')
        names = {name:p for p,name in self.players.items()}
        if len(guesses)!=len(self.options) or any(n not in names for n in guesses):
            raise ValueError('Use /vote followed by one real username per entry, in order.')
        self.votes[player] = [names[n] for n in guesses]

    def view(self):
        result = dict(phase=self.phase,leader=self.players[self.leader],prompt=self.prompt,
                      deadline=self.deadline,submitted=len(self.answers),total=len(self.players),
                      voted=len(self.votes),result=self.result,players=list(self.players.values()))
        if self.phase in ('voting','results'):
            result['options'] = [dict(number=i+1,text=text,
                                     author=self.players[p] if self.phase=='results' else None)
                                 for i,(p,text) in enumerate(self.options)]
        return result

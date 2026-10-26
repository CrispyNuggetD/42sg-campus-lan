import collections
import unittest
from campus_lan.client import Client
from campus_lan.lobby_view import LAYOUT, lobby_lines, roster, guest_style


def player(name, seat='unknown', id=''):
    return dict(name=name, seat=seat, id=id, hostname='test')


class Canvas:
    def __init__(self,h,w):
        self.h,self.w = h,w
        self.rows = [[' ']*w for _ in range(h)]
    def getmaxyx(self): return self.h,self.w
    def erase(self): pass
    def refresh(self): pass
    def addnstr(self,y,x,text,n,attr):
        assert 0<=y<self.h and 0<=x<self.w
        for i,ch in enumerate(text[:n]):
            self.rows[y][x+i] = ch
    def text(self): return '\n'.join(''.join(row).rstrip() for row in self.rows)


class LobbyView(unittest.TestCase):
    def test_layout_and_stagger_match_screenshots(self):
        self.assertEqual(sum(LAYOUT[1].values()),57)
        self.assertEqual(sum(LAYOUT[2].values()),93)
        rows = [''.join(text for text,_ in line) for line in lobby_lines([], 'map', 1)]
        self.assertTrue(rows[2].startswith('R8'))
        self.assertGreater(rows[2].index('[02]'),rows[3].index('[01]'))
        self.assertIn('[12]',rows[2])
        self.assertNotIn('[13]',rows[3])

    def test_numbered_groups_colours_and_shared_seats(self):
        peers = [player('home'),player('thtay','c2r1s3'),player('hnah','Cluster 1, row 8, seat 6')]
        ordered = roster(peers)
        self.assertEqual([p['name'] for _,p,_ in ordered], ['hnah','thtay','home'])
        rows=lobby_lines(peers, 'map', 1)
        self.assertTrue(any('[#1]' in text and style==guest_style('hnah') for line in rows for text,style in line))
        self.assertNotEqual(guest_style('hnah'),1)  # verified green remains reserved
        peers.append(player('other','c1r8s6'))
        self.assertTrue(any('[++]' in text for line in lobby_lines(peers,'map',1) for text,_ in line))

    def test_small_terminal_paging_keeps_roster_and_chat_accessible(self):
        c=Client.__new__(Client)
        c.name,c.connected,c.input,c.play,c.scroll='hnah',True,'',False,0
        c.lines=collections.deque(['hello friends'])
        c.game={}
        c.state=dict(players=[player('p'+str(i),'c1r2s3',str(i)) for i in range(32)])
        c.lobby_command('/who')
        seen=''
        for _ in range(4):
            screen=Canvas(28,76)
            c.draw(screen)
            rendered=screen.text()
            self.assertIn('CURRENTLY ONLINE: 32',rendered)
            self.assertIn('hello friends',rendered)
            seen+=rendered
            c.lobby_command('/next')
        self.assertIn('32.',seen)
        c.lobby_command('/map 2')
        self.assertEqual((c.cluster,c.lobby_page),(2,0))
        c.draw(Canvas(28,76))
        c.game=dict(game='tetris',board=[])
        c.lobby_command('/lobby')
        self.assertFalse(c.play)
        c.lobby_command('/game')
        self.assertTrue(c.play)
        self.assertFalse(c.show_lobby)

    def test_clusters_heading_has_no_overwritten_text_and_controls_fit_tmux(self):
        c=Client.__new__(Client)
        c.name,c.connected,c.input,c.play,c.scroll='owner',True,'',False,0
        c.lines=collections.deque(['chat remains visible']);c.game={};c.colors=False
        c.state=dict(players=[player('owner','c1r1s1')])
        c.cluster_source=True;c.cluster_stamp=100;c.cluster=2;c.lobby_view='map';c.lobby_page=0
        c.cluster_players=[player('p'+str(i),'c2r1s'+str(i+1)) for i in range(15)]
        for h,w in ((28,76),(54,204)):
            screen=Canvas(h,w);c.draw(screen)
            heading=''.join(screen.rows[3]).rstrip()
            self.assertTrue(heading.startswith('CAMPUS API: 15'))
            self.assertNotIn('unverified',heading)
            self.assertIn('/next /prev',''.join(screen.rows[4]))
            self.assertIn('page ',''.join(screen.rows[4]))
            self.assertIn('chat remains visible',screen.text())

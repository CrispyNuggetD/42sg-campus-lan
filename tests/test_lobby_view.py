import collections
import unittest
from campus_lan.client import Client
from campus_lan.lobby_view import LAYOUT, lobby_lines, roster, guest_style, relationship_overlay, player_style, GUEST_STYLE


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
        self.assertTrue(any('[?1]' in text and style==GUEST_STYLE for line in rows for text,style in line))
        self.assertNotEqual(guest_style('hnah'),1)  # verified green remains reserved
        peers.append(player('other','c1r8s6'))
        self.assertTrue(any('[++]' in text for line in lobby_lines(peers,'map',1) for text,_ in line))

    def test_relationship_colors_have_distinct_categories_and_priority(self):
        people=[dict(player('friend','c1r1s1'),verified=True),
                dict(player('listed','c1r1s2'),api_presence=True),
                dict(player('signed','c1r1s3'),verified=True),
                player('guest','c1r1s4'),dict(player('api','c1r1s5'),api_presence=True)]
        data=dict(people={'friend':dict(relationship='friends')},lists={'lunch':['friend','listed']})
        decorated=relationship_overlay(people,data)
        styles=[player_style(p) for p in decorated]
        self.assertEqual(len(set(styles)),5)
        self.assertEqual(decorated[0]['local_relationship'],'friend')
        self.assertEqual(decorated[1]['local_relationship'],'list')
        self.assertNotIn('local_relationship',people[0])
        rows=lobby_lines(decorated,'map',1)
        self.assertIn('>nn< selected',''.join(text for text,_ in rows[1]))
        self.assertTrue(any(style==0 and text=='[06]' for row in rows for text,style in row))

    def test_cluster_flavours_and_self_override_relationship_without_guest_spoof(self):
        from campus_lan.lobby_view import CLUSTER_STYLES,SELF_STYLE
        people=[dict(player('hnah','c1r1s1'),api_presence=True),
                dict(player('other','c2r1s1'),api_presence=True),player('hnah')]
        decorated=relationship_overlay(people,{'people':{'hnah':{'relationship':'friends'}}},'hnah')
        self.assertEqual(player_style(decorated[0]),SELF_STYLE)
        self.assertEqual(player_style(decorated[2]),GUEST_STYLE)
        self.assertEqual(len({SELF_STYLE,*CLUSTER_STYLES.values()}),3)
        rows=lobby_lines(decorated,'roster',0)
        self.assertTrue(any('CLUSTER 1' in text and style==CLUSTER_STYLES[1] for row in rows for text,style in row))
        self.assertTrue(any('CLUSTER 2' in text and style==CLUSTER_STYLES[2] for row in rows for text,style in row))
        self.assertIn('/ you',''.join(text for row in rows for text,_ in row))
        self.assertNotIn('local_self',people[0])

    def test_friends_and_cohorts_combine_once_with_self_priority(self):
        from campus_lan.lobby_view import SELF_STYLE,FRIEND_STYLE,COHORT_STYLES
        people=[dict(player('hnah','c1r1s1'),api_presence=True),
                dict(player('friend4','c1r1s2'),api_presence=True),
                dict(player('friend5','c1r1s3'),api_presence=True),
                dict(player('other5','c1r1s4'),api_presence=True),player('spoof','c1r1s5')]
        data={'people':{n:{'relationship':'friends'} for n in ('hnah','friend4','friend5')}}
        decorated=relationship_overlay(people,data,'hnah',{'hnah':4,'friend4':4,'friend5':5,'other5':5,'spoof':4})
        self.assertEqual(len(decorated),len(people))
        self.assertEqual([player_style(p) for p in decorated],[SELF_STYLE,FRIEND_STYLE,FRIEND_STYLE,COHORT_STYLES[5],GUEST_STYLE])
        rows=lobby_lines(decorated,'roster',0)
        text='\n'.join(''.join(s for s,_ in row) for row in rows)
        self.assertEqual(text.count('friend4'),1)
        self.assertIn('friend / I4~',text)
        self.assertIn('friend / I5~',text)
        mapped=lobby_lines(decorated,'map',1)
        self.assertTrue(any(token=='[F2]' and style==FRIEND_STYLE for row in mapped for token,style in row))
        self.assertTrue(any(token=='[F3]' and style==FRIEND_STYLE for row in mapped for token,style in row))
        self.assertIsNone(decorated[-1]['local_cohort'])

    def test_guest_name_cannot_claim_friend_or_list_color(self):
        decorated=relationship_overlay([player('friend')],dict(people={'friend':dict(relationship='friends')},lists={'lunch':['friend']}))
        self.assertEqual(player_style(decorated[0]),GUEST_STYLE)

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


class SelectionAccessibility(unittest.TestCase):
    def test_monochrome_relationship_markers_and_intake_text(self):
        from campus_lan.lobby_view import relationship_badge,map_legend,COHORT_STYLES,API_STYLE
        people=[dict(name=n,seat='c1r1s'+str(i+1),api_presence=True) for i,n in enumerate(('me','friend','mutual','oomf','tracked','listed','other'))]
        data={'people':{'friend':{'relationship':'friends'},'mutual':{'relationship':'mutuals'},'oomf':{'relationship':'oomf'},'tracked':{'relationship':'tracked'}},'lists':{'lunch':['listed']}}
        shown=relationship_overlay(people,data,'me',{'friend':4})
        self.assertEqual([relationship_badge(p)[0] for p in shown],list('YFMOTLA'))
        text='\n'.join(''.join(t for t,_ in row) for row in lobby_lines(shown,'roster',1))
        for badge in ('[Y]','[F]','[M]','[O]','[T]','[L]','[A]'):self.assertIn(badge,text)
        self.assertIn('I4~',text)
        self.assertEqual(len(set(COHORT_STYLES.values())),8)
        self.assertLessEqual(sum(len(t) for t,_ in map_legend()),75)

    def test_selection_is_persistent_and_does_not_change_hit_geometry(self):
        from campus_lan.lobby_view import selection_overlay,occupant_hits,SELECTED_STYLE,selected_details
        players=relationship_overlay([dict(name='friend',seat='c1r8s2',api_presence=True)],{'people':{'friend':{'relationship':'friends'}}})
        content=lobby_lines(players,'map',1)
        selected=selection_overlay(players,content,'map',1,(1,8,2),'friend')
        self.assertTrue(any(text=='>01<' and style==SELECTED_STYLE for row in selected for text,style in row))
        self.assertEqual([sum(len(t) for t,_ in row) for row in selected],[sum(len(t) for t,_ in row) for row in content])
        self.assertIn('friend [F: friend]',selected_details(players,(1,8,2),'friend'))
        changed=[dict(name='replacement',seat='c1r8s2',api_presence=True)]
        self.assertEqual(selection_overlay(changed,lobby_lines(changed,'map',1),'map',1,(1,8,2),'friend'),lobby_lines(changed,'map',1))
        self.assertIn('no longer',selected_details(changed,(1,8,2),'friend'))

    def test_shared_seat_selection_is_explicit(self):
        from campus_lan.lobby_view import selection_overlay
        players=[dict(name=n,seat='c1r1s1',api_presence=True) for n in ('a','b')]
        result=selection_overlay(players,lobby_lines(players,'map',1),'map',1,(1,1,1))
        self.assertTrue(any(text=='>++<' for row in result for text,_ in row))


class MapPaletteAndPulse(unittest.TestCase):
    def test_extended_palette_colors_occupied_intakes_and_unknown_api(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        from campus_lan.lobby_view import init_cluster_colors,API_STYLE,GUEST_STYLE
        colors=SimpleNamespace(COLORS=256,COLOR_BLACK=0,COLOR_BLUE=4,COLOR_CYAN=6,
                               COLOR_GREEN=2,COLOR_YELLOW=3,COLOR_MAGENTA=5,
                               COLOR_WHITE=7,COLOR_RED=1,init_pair=Mock())
        init_cluster_colors(colors)
        pairs={call.args[0]:call.args[1:] for call in colors.init_pair.call_args_list}
        self.assertEqual(len({pairs[n][0] for n in range(11,19)}),8)
        self.assertEqual(pairs[API_STYLE][0],colors.COLOR_CYAN)
        self.assertEqual(pairs[GUEST_STYLE][0],colors.COLOR_YELLOW)
        self.assertNotEqual(pairs[API_STYLE][0],colors.COLOR_WHITE)
        rows=lobby_lines([], 'map',1)
        swatches=next(row for row in rows if row[0][0]=='Intake colors: ')
        self.assertEqual([style for _,style in swatches[1:9]],list(range(11,19)))

    def test_selection_pulse_changes_attributes_without_hiding_marker(self):
        from types import SimpleNamespace
        from campus_lan.lobby_view import selection_attributes,map_legend,SELECTED_STYLE
        colors=SimpleNamespace(A_BOLD=1,A_UNDERLINE=2,A_REVERSE=4,color_pair=lambda style:style<<8)
        bright=selection_attributes(colors,True,now=0)
        quiet=selection_attributes(colors,True,now=.7)
        self.assertNotEqual(bright,quiet)
        for attr in (bright,quiet):
            self.assertEqual(attr&3,3)
            self.assertEqual(attr&(SELECTED_STYLE<<8),SELECTED_STYLE<<8)
        self.assertNotEqual(selection_attributes(colors,False,0),selection_attributes(colors,False,.7))
        self.assertTrue(all(style!=SELECTED_STYLE for _,style in map_legend()))

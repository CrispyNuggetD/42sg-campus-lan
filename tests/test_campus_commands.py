import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from campus_lan.campus_info import random_profiles,matches_filters
from campus_lan.clusters import normalize_locations
from campus_lan.profile_browser import resolve
from campus_lan.forknite import ensure_binary
from campus_lan import api_pacing

class Commands(unittest.TestCase):
    def test_cohort_union_filters_and_exclusions(self):
        data={'students':[dict(login='a',cohort=4,level=3),dict(login='b',cohort=5,level=1),dict(login='c',cohort=6,level=9)]}
        with patch('campus_lan.campus_info.load',return_value=data):
            self.assertEqual({p['login'] for p in random_profiles(None,[],[4,5])},{'a','b'})
            self.assertEqual(random_profiles(1,[],[4,5],['level>=2']),[dict(login='a',avatar=None)])
            with self.assertRaises(ValueError):random_profiles(2,['A'],[4,5])
        with self.assertRaises(ValueError):matches_filters({'login':'a'},["login=a;DROP"])

    def test_profile_validation_dedup_and_bulk_guard(self):
        self.assertEqual(resolve(['thtay','HNAH','thtay']),['https://profile-v3.intra.42.fr/users/thtay','https://profile-v3.intra.42.fr/users/hnah'])
        with self.assertRaises(ValueError):resolve(['../../private'])
        data={'students':[dict(login='u'+str(i),cohort=4) for i in range(12)]}
        with patch('campus_lan.profile_browser.load',return_value=data):
            with self.assertRaisesRegex(ValueError,'12 tabs'):resolve(['cohort4'])
            self.assertEqual(len(resolve(['--open-many','all'])),12)

    def test_active_location_whitelist_and_dedup(self):
        good=dict(id=1,host='c1r3s6',end_at=None,user={'login':'hnah'})
        records=[good,good,dict(good,end_at='2026-01-01'),dict(good,host='bad\nseat'),dict(good,user={'login':'bad\nlogin'})]
        self.assertEqual(normalize_locations(records),[dict(id='1',name='hnah',seat='c1r3s6',verified=True)])

    def test_missing_configured_binary_builds_and_checks_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'philo'
            def make(*args,**kwargs):target.write_text('#!/bin/sh\n');target.chmod(0o700)
            with patch.dict('os.environ',{'LAN42_PHILO_BINARY':str(target)}),patch('campus_lan.forknite.subprocess.run',side_effect=make) as run:
                self.assertEqual(ensure_binary(),str(target));self.assertEqual(run.call_args.args[0],['make','-C',tmp])
                ensure_binary();self.assertEqual(run.call_count,1)

    def test_global_pacing_across_threads(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.api_pacing.config_dir',return_value=Path(tmp)):
            starts=[]
            def call():api_pacing.wait();starts.append(time.time())
            threads=[threading.Thread(target=call) for _ in range(4)]
            for thread in threads:thread.start()
            for thread in threads:thread.join()
            starts.sort()
            self.assertTrue(all(b-a>=.49 for a,b in zip(starts,starts[1:])))

    def test_overlay_preserves_api_seats_and_peer_verification(self):
        from campus_lan.lobby_view import overlay_campus,player_style
        players=[dict(name='a',seat='c1r1s1'),dict(name='b',seat='c1r2s2'),dict(name='c',seat='c2r3s3')]
        over=overlay_campus(players,[dict(name='a',seat='unknown',verified=True),dict(name='b',verified=False)])
        self.assertEqual(over[0]['seat'],'c1r1s1');self.assertEqual(player_style(over[0]),1)
        self.assertTrue(over[1]['lan42_peer']);self.assertFalse(over[1]['verified'])
        self.assertFalse(over[2]['lan42_peer']);self.assertEqual(player_style(over[2]),7)

    def test_focus_selects_cluster_and_scrolls_to_seat(self):
        import collections
        from campus_lan.client import Client
        from test_lobby_view import Canvas
        client=Client.__new__(Client);client.lines=collections.deque();client.secure=False
        player=dict(name='a',seat='c2r1s3',id='a',verified=True)
        client.cluster_players=[player];client.cluster_source=True;client.cluster_stamp=0
        client.focus_player(player)
        self.assertEqual(client.cluster,2)
        canvas=Canvas(28,100);client.draw_lobby(canvas,[])
        self.assertIn('SELECTED a',canvas.text());self.assertGreater(client.lobby_page,0)
        self.assertTrue(client.lobby_hits)

    def test_text_portions_have_one_blank_separator(self):
        from campus_lan.client import SectionLog
        log=SectionLog(['help line one','help line two'])
        log.append('Room opened');log.extend(['Campus header','Student row']);log.append('Student online')
        self.assertEqual(list(log),['help line one','help line two','','Room opened','','Campus header','Student row','','Student online'])

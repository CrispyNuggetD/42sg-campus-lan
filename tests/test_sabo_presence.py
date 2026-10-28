import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import AsyncMock,Mock,patch
from campus_lan.auth import Broker,AuthError
from campus_lan.server import Lobby
from campus_lan import clusters
from campus_lan.client import Client
from campus_lan.completion import complete
import collections


class PresenceSelection(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        for p in (patch.dict(os.environ,{'XDG_CONFIG_HOME':temp.name}),patch('campus_lan.login_whitelist.allowed_logins',return_value={f'fixture-{i:02}' for i in range(65)}|{'fixture-host','online','verified'})):
            p.start();self.addCleanup(p.stop)
        self.broker=Broker(Mock());self.lobby=Lobby(auth_broker=self.broker)
        self.add_member('host','fixture-host',1)
        self.web=Mock();self.seated=[{'name':'fixture-host'}]
        async def control(data):
            if data['action']=='roster':return {'players':self.seated}
            if data['action']=='campus_status':return {'ok':True}
            return {'added':[p['login'] for p in data['profiles']]}
        self.web.control=AsyncMock(side_effect=control)
        self.lobby.rooms['room']=dict(game='forknite',host='host',members={'host'},web=self.web)
        self.lobby.event=AsyncMock()
        async def lookup(names):return [dict(login=n,avatar=None) for n in names],[]
        self.lobby.profile_lookup.lookup_many=AsyncMock(side_effect=lookup)

    def add_member(self,pid,name,uid,**changes):
        key='key-'+pid
        self.broker.sessions[key]=dict(uid=uid,login=name,sg_member=True,campus_id=64,expires=time.time()+600,**changes)
        self.lobby.clients[pid]=dict(name=name,uid=uid,session_key=key)

    async def test_online_uses_stale_api_snapshot_not_signins_or_new_crawl(self):
        self.add_member('off-campus','fixture-02',2)
        self.lobby.clients['guest']=dict(name='fixture-01',uid=None,verified=True)
        present=[dict(name='fixture-01'),dict(name='fixture-01'),dict(name='fixture-host')]
        with patch.object(clusters,'_snapshot',present),patch.object(clusters,'_stamp',time.time()-900),patch.object(clusters,'API') as api:
            await self.lobby.command('host','/sabo online')
            api.assert_not_called()
        self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-01'])
        notice=' '.join(call.args[0] for call in self.lobby.event.call_args_list)
        self.assertIn('Host campus API snapshot',notice);self.assertIn('s old',notice)

    async def test_empty_or_missing_snapshot_never_falls_back(self):
        for snapshot in (None,[]):
            with patch.object(clusters,'_snapshot',snapshot),patch.object(clusters,'API') as api:
                if snapshot is None:
                    with self.assertRaisesRegex(ValueError,'Load /clusters'):await self.lobby.command('host','/sabo online')
                else:await self.lobby.command('host','/sabo online')
                api.assert_not_called()
            self.lobby.profile_lookup.lookup_many.assert_not_called()

    async def test_verified_checks_sessions_and_canonical_login_not_nickname_flags(self):
        self.add_member('valid','fixture-03',3)
        self.add_member('duplicate','fixture-03',3)
        self.lobby.clients['valid']['name']='spoofed-nickname'
        self.add_member('expired','fixture-04',4);self.broker.sessions['key-expired']['expires']=time.time()-1
        self.add_member('outsider','fixture-05',5);self.broker.sessions['key-outsider']['campus_id']=1
        self.add_member('remote','fixture-06',6);self.lobby.clients['remote']['remote_approved']=True
        self.lobby.clients['forged']=dict(name='fixture-07',uid=7,verified=True,role='admin')
        with patch.object(clusters,'cached_snapshot') as snapshot:
            await self.lobby.command('host','/sabo verified')
            snapshot.assert_not_called()
        self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-03'])

    async def test_capacity_counts_dedup_and_profile_batches_stay_bounded(self):
        present=[dict(name=f'fixture-{i:02}') for i in range(65)]
        self.seated.append(dict(name='fixture-00'))
        with patch.object(clusters,'cached_snapshot',return_value=(present,time.time())):
            await self.lobby.command('host','/sabo online')
        batches=[c.args[0] for c in self.lobby.profile_lookup.lookup_many.call_args_list]
        self.assertTrue(all(len(b)<=10 for b in batches));names=sum(batches,[])
        self.assertEqual(len(names),48);self.assertNotIn('fixture-00',names)
        self.lobby.profile_lookup.lookup_many.reset_mock()
        with patch.object(clusters,'cached_snapshot',return_value=(present,time.time())):
            await self.lobby.command('host','/sabo 2 ONLINE')
        self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-01','fixture-02'])

    async def test_authentication_and_room_ownership_checked_before_snapshot(self):
        with patch.object(clusters,'cached_snapshot') as snapshot:
            self.lobby.clients['forged']=dict(name='fixture-01',uid=123,role='admin',verified=True)
            with self.assertRaises(AuthError):await self.lobby.command('forged','/sabo online')
            self.add_member('member','fixture-01',3)
            with self.assertRaisesRegex(ValueError,'room host'):await self.lobby.command('member','/sabo online')
            snapshot.assert_not_called()
        self.lobby.profile_lookup.lookup_many.assert_not_called()

    async def test_invalid_combinations_rejected_before_api_lookup(self):
        with patch.object(clusters,'cached_snapshot') as snapshot:
            for args in ('online typo','online verified','online 0','online 51','online cohort1','online 2 3'):
                with self.assertRaises(ValueError):await self.lobby.command('host','/sabo '+args)
            snapshot.assert_not_called()
        self.lobby.profile_lookup.lookup_many.assert_not_called()

    async def test_literal_reserved_login_can_be_requested_explicitly(self):
        await self.lobby.command('host','/sabo login:online')
        self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['online'])

    async def test_client_delegates_presence_to_host_without_local_directory(self):
        c=Client.__new__(Client);c.name='fixture-host';c.lines=collections.deque();c.send=Mock()
        with patch('campus_lan.login_whitelist.allowed_logins',side_effect=AssertionError('Presence must resolve on host')),patch('campus_lan.tracking.Tracker',side_effect=AssertionError('Presence does not need local relationships')):
            self.assertFalse(c.group_command('/sabo online'))
            self.assertFalse(c.group_command('/sabo verified 2'))
        c.send.assert_not_called()
        self.assertEqual(complete('/sabo on')[0],'/sabo online ')
        self.assertEqual(complete('/sabo ver')[0],'/sabo verified ')

    async def test_empty_capacity_and_unlisted_targets_never_lookup_profiles(self):
        with patch.object(clusters,'cached_snapshot',return_value=([dict(name='fixture-01')],1)):
            self.seated[:]=[dict(name=f'fixture-{i:02}') for i in range(50)]
            await self.lobby.command('host','/sabo online')
            self.lobby.profile_lookup.lookup_many.assert_not_called()
            self.seated[:]=[]
            with patch('campus_lan.login_whitelist.allowed_logins',return_value=set()):
                with self.assertRaisesRegex(ValueError,'whitelist'):await self.lobby.command('host','/sabo online')
            self.lobby.profile_lookup.lookup_many.assert_not_called()

    async def test_cluster_filter_is_seat_based_and_not_a_requested_count(self):
        records=[dict(name='fixture-01',seat='c1r1s1'),dict(name='fixture-02',seat='c1r1s2'),dict(name='fixture-03',seat='c2r1s1')]
        with patch.object(clusters,'cached_snapshot',return_value=(records,1)):
            await self.lobby.command('host','/sabo online cluster 1')
            self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-01','fixture-02'])
            self.lobby.profile_lookup.lookup_many.reset_mock()
            await self.lobby.command('host','/sabo online c2')
            self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-03'])
            self.lobby.profile_lookup.lookup_many.reset_mock()
            await self.lobby.command('host','/sabo online 1 cluster 1')
            self.lobby.profile_lookup.lookup_many.assert_awaited_once_with(['fixture-01'])
        self.assertEqual(complete('/sabo online cluster ')[1],['1','2'])

    async def test_bad_cluster_syntax_never_reads_the_snapshot(self):
        with patch.object(clusters,'cached_snapshot') as snapshot:
            for args in ('online cluster 3','online cluster','online c1 c2','verified cluster 1','online cluster 1 typo'):
                with self.assertRaises(ValueError):await self.lobby.command('host','/sabo '+args)
            snapshot.assert_not_called()

    async def test_status_is_sent_only_to_current_api_authorized_members(self):
        self.lobby.send=AsyncMock()
        self.add_member('remote','fixture-02',2);self.lobby.clients['remote']['remote_approved']=True
        self.lobby.clients['guest']=dict(name='fixture-01',uid=123,verified=True)
        with patch('campus_lan.access.Policy.require_host'),patch('campus_lan.campus_status.cached_status',return_value=dict(total=17,c1=8,c2=9,updated_at=100)):
            await self.lobby.send_campus_status()
        self.lobby.send.assert_awaited_once()
        self.assertIs(self.lobby.send.call_args.args[0],self.lobby.clients['host'])
        self.assertEqual(self.lobby.send.call_args.args[1]['status']['total'],17)

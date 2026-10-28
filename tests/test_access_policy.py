import asyncio
import collections
import copy
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from campus_lan.access import Policy,DEFAULT,SG_CAMPUS_ID,INITIAL_OWNER_UID
from campus_lan.auth import AuthError,Broker,Provider,private_write,config_dir
from campus_lan.server import Lobby
from campus_lan.campus_info import API

HOST='a'*64

def member(uid=2,login='student'):
    return dict(uid=uid,login=login,sg_member=True,campus_id=64)

def policy():
    data=copy.deepcopy(DEFAULT);data['approved_hosts']=[HOST]
    return Policy(data)

class PolicyTests(unittest.TestCase):
    def test_fail_closed_guest_forgery_and_numeric_admin(self):
        p=policy()
        for identity in (None,{'login':'hnah','admin':True},dict(uid=True,sg_member=True,campus_id=64),dict(uid=2,sg_member=True,campus_id=1)):
            with self.assertRaises(AuthError):p.require_member(identity)
        self.assertFalse(p.is_admin('234449'));self.assertFalse(p.is_admin(True))
        self.assertTrue(p.is_admin(INITIAL_OWNER_UID))
        self.assertFalse(p.is_admin(2));self.assertEqual(p.require_member(member())['uid'],2)
        with patch('campus_lan.access.host_id',return_value='b'*64):
            with self.assertRaises(AuthError):p.require_host()
        with patch('campus_lan.access.host_id',return_value=HOST):p.require_host()

    def test_operator_and_admin_are_independent_and_policy_revocation_is_live(self):
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}),patch('campus_lan.access.host_id',return_value=HOST):
            p=policy();p.data['api_operators']=[2];p.save()
            private_write(config_dir()/'local-operator.json',json.dumps({'uid':2}))
            self.assertEqual(Policy().local_operator(),2)
            with self.assertRaises(AuthError):Policy().local_operator(admin=True)
            p.data['api_operators']=[];p.save()
            with self.assertRaises(AuthError):Policy().local_operator()

    def test_provider_rejects_non_sg_and_revokes_even_for_admin_named_account(self):
        for campuses,allowed in [([],False),([{'campus_id':1}],False),([{'campus_id':64}],True)]:
            p=Provider('id','secret')
            p.request=Mock(side_effect=[dict(access_token='x'*20,token_type='bearer'),dict(id=234449,login='hnah',campus_users=campuses),{}])
            if allowed:self.assertEqual(p.identify('code','verifier')['campus_id'],64)
            else:
                with self.assertRaises(AuthError):p.identify('code','verifier')
            self.assertIn('/oauth/revoke',p.request.call_args_list[-1].args[0])

class ScopedAPI(unittest.TestCase):
    def api(self):
        a=API.__new__(API);a._members={};return a

    def test_queryless_scoped_requests_work_on_campus_python(self):
        a=self.api();base='https://api.intra.42.fr/v2/'
        a._validate_url(base+'campus/64',None,True)
        a._members['234449']=True
        a._validate_url(base+'users/234449',None,True)
        for target in ('users/2','users','campus/1','campus/64/users?&',
                       'campus/64/users?filter[id]=234449&filter[id]=2'):
            with self.subTest(target=target),self.assertRaises((AuthError,ValueError)):
                a._validate_url(base+target,None,True)

    def test_rejects_arbitrary_paths_writes_scope_overrides_and_unproven_profiles(self):
        a=self.api();base='https://api.intra.42.fr/v2/'
        for target in ('users/234449','users','campus/1/users','cursus_users?filter[campus_id]=64','campus/64/locations','campus/64/users?filter[campus_id]=1','campus/64/users?filter[id]=1&filter[id]=2','campus/64/users?page[number]=51','campus/64/../1/users'):
            with self.subTest(target=target),self.assertRaises((AuthError,ValueError)):a._validate_url(base+target,None,True)
        with self.assertRaises(AuthError):a._validate_url(base+'campus/64',b'write',True)
        with self.assertRaises(AuthError):a._validate_url('https://evil.example/v2/campus/64',None,True)
        a._validate_url(base+'campus/64/locations?filter[active]=true',None,True)
        a._validate_url(base+'campus/64/users?filter[login]=hnah',None,True)

    def test_non_sg_target_is_rejected_before_full_profile_fetch(self):
        a=self.api();a.pages=Mock(return_value=[]);a.request=Mock()
        with self.assertRaises(AuthError):a.member_profile('outsider')
        a.request.assert_not_called()
        a.pages.assert_called_once_with('campus/64/users',**{'filter[login]':'outsider'})
        a.pages.return_value=[{'id':234449,'login':'hnah'}]
        a.request.return_value=dict(id=234449,login='hnah',campus_users=[{'campus_id':64}])
        self.assertEqual(a.member_profile('hnah')['id'],234449)
        self.assertEqual(a._members,{})
        a.request.return_value=dict(id=234449,campus_users=[{'campus_id':1}])
        with self.assertRaises(AuthError):a.member_profile('hnah')

class ServerBoundaries(unittest.IsolatedAsyncioTestCase):
    async def test_cluster_viewer_can_only_refresh_and_is_not_a_chat_recipient(self):
        broker=Broker(Mock());broker.sessions['viewer-session']=dict(member(),expires=time.time()+100)
        lobby=Lobby(auth_broker=broker)
        lobby.clients['1']=dict(name='student',uid=2,session_key='viewer-session',role='clusters',writer=Mock())
        with patch('campus_lan.clusters.snapshot',return_value=([dict(name='fixture',seat='c1r1s1')],100)) as seats,patch.object(lobby,'send',new=unittest.mock.AsyncMock()) as send,patch.object(lobby,'event',new=unittest.mock.AsyncMock()):
            await lobby.command('1','/clusters')
            seats.assert_called_once()
            self.assertEqual(send.call_args.args[1]['type'],'clusters')
            for text in ('hello','/dm fixture hello','/info','/sabo fixture'):
                with self.assertRaises(AuthError):await lobby.command('1',text)
        self.assertFalse(await lobby.deliver_direct('fixture','student','hello'))
        with patch.object(lobby,'broadcast',new=unittest.mock.AsyncMock()) as broadcast,patch.object(lobby,'send_campus_status',new=unittest.mock.AsyncMock()):
            await lobby.state()
            self.assertEqual(broadcast.call_args.args[0]['players'],[])

    async def test_guest_admin_nickname_cannot_read_even_cached_data_or_trigger_sabo(self):
        lobby=Lobby();lobby.clients['1']=dict(name='hnah',uid=234449,role='admin')
        with patch('campus_lan.clusters.snapshot') as seats,patch('campus_lan.campus_info.info_lines') as info,patch('campus_lan.campus_info.refresh') as refresh,patch.object(lobby.profile_lookup,'lookup_many') as profiles:
            for command in ('/clusters','/campus-presence','/info','/sabo hnah','/sabo random'):
                with self.assertRaises(AuthError):await lobby.command('1',command)
            seats.assert_not_called();info.assert_not_called();refresh.assert_not_called();profiles.assert_not_called()

    async def test_verified_members_get_seats_but_not_operator_directory(self):
        broker=Broker(Mock());broker.sessions['session-key']=dict(member(),expires=time.time()+100)
        lobby=Lobby(auth_broker=broker);lobby.clients['1']=dict(name='student',uid=2,session_key='session-key')
        with patch('campus_lan.clusters.snapshot',return_value=([],1)) as seats,patch.object(lobby,'send',new=unittest.mock.AsyncMock()) as send,patch.object(lobby,'event',new=unittest.mock.AsyncMock()):
            await lobby.command('1','/clusters');seats.assert_called_once()
            self.assertEqual(send.call_args.args[1]['type'],'clusters')
            with self.assertRaises(AuthError):await lobby.command('1','/info')
            broker.sessions['session-key']['campus_id']=1
            with self.assertRaises(AuthError):await lobby.command('1','/clusters')

    async def test_host_revocation_blocks_existing_sessions(self):
        p=policy()
        b=Broker(Mock(),policy_factory=lambda:p);b.sessions['key']=dict(member(),expires=time.time()+100)
        with patch('campus_lan.access.host_id',return_value=HOST):
            self.assertTrue(b.active('key'));p.data['approved_hosts']=[];self.assertFalse(b.active('key'))

class LocalOwnerViews(unittest.TestCase):
    def test_local_owner_clusters_stay_on_device_and_do_not_send_a_network_command(self):
        from campus_lan.client import Client
        import queue
        c=Client.__new__(Client);c.secure=False;c.lines=collections.deque();c.inbox=queue.Queue();c.send=Mock()
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}),patch('campus_lan.access.host_id',return_value=HOST):
            p=policy();p.save();private_write(config_dir()/'local-operator.json',json.dumps({'uid':234449}))
            def thread(target,daemon):return Mock(start=target)
            with patch('campus_lan.client.threading.Thread',side_effect=thread),patch('campus_lan.clusters.snapshot',return_value=([{'name':'fixture','seat':'c1r1s1'}],42)):
                self.assertTrue(c.local_api_command('/clusters 2'))
            c.send.assert_not_called();msg=c.inbox.get_nowait()
            self.assertEqual(msg['type'],'clusters');self.assertEqual(msg['cluster'],2)
            p.data['api_operators']=[];p.save()
            with patch('campus_lan.clusters.snapshot') as fetch:
                self.assertTrue(c.local_api_command('/clusters'))
                fetch.assert_not_called()

class HostStartup(unittest.IsolatedAsyncioTestCase):
    async def test_credentials_do_not_implicitly_approve_host(self):
        from campus_lan.auth_server import serve_auth
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}),patch('campus_lan.access.host_id',return_value=HOST),patch('campus_lan.auth_server.asyncio.start_server') as listen:
            private_write(config_dir()/'auth-server.json',json.dumps({'client_id':'fixture','client_secret':'fixture'}))
            with self.assertRaises(AuthError):await serve_auth()
            listen.assert_not_called()

class PolicyAdministration(unittest.TestCase):
    def test_admin_grant_is_sg_checked_and_does_not_grant_operator_or_host(self):
        from campus_lan.access import main
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}),patch('campus_lan.access.host_id',return_value=HOST):
            p=policy();p.save();private_write(config_dir()/'local-operator.json',json.dumps({'uid':234449}))
            with patch('sys.argv',['access','grant','admin','2']),patch('campus_lan.campus_info.API') as api:
                api.return_value.member_profile.return_value={'id':2,'campus_users':[{'campus_id':64}]}
                main();api.return_value.member_profile.assert_called_once_with('2')
            updated=Policy();self.assertTrue(updated.is_admin(2))
            self.assertNotIn(2,updated.data['api_operators']);self.assertEqual(updated.data['approved_hosts'],[HOST])
            p=updated;p.data['admins']=[234449];p.save()
            with patch('sys.argv',['access','revoke','admin','234449']),self.assertRaises(AuthError):main()
            self.assertEqual(Policy().data['admins'],[234449])

    def test_revoked_host_cannot_self_reenroll_and_missing_file_has_no_implicit_hosts(self):
        from campus_lan.access import main
        with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp}),patch('campus_lan.access.host_id',return_value=HOST):
            p=Policy();p.data['approved_hosts'].append(HOST)
            self.assertEqual(Policy().data['approved_hosts'],[])
            p.data['approved_hosts']=[];p.save()
            with patch('sys.argv',['access','enroll-local']),patch('campus_lan.campus_info.API') as api:
                with self.assertRaises(AuthError):main()
                api.assert_not_called()

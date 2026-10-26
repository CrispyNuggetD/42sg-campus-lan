import collections
import io
import json
import os
from pathlib import Path
import queue
import secrets
import ssl
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
import asyncio
from campus_lan.announcements import Announcements
from campus_lan.access import Policy,DEFAULT

def test_policy():
    import copy
    data=copy.deepcopy(DEFAULT);data["admins"]=[1]
    policy=Policy(data);policy.local_operator=Mock(return_value=1)
    return policy
from campus_lan.auth import AuthError,AuthHTTP,Broker,digest,config_dir,private_write
from campus_lan.auth_server import setup
from campus_lan import auth_client
from campus_lan.announcement_client import HostWatch,claim
from campus_lan.client import Client

class Authority(unittest.TestCase):
    def setUp(self):
        self.now=1000
        def authenticate(token):
            people={'student':dict(uid=2,login='dthoo',sg_member=True,campus_id=64),'owner':dict(uid=1,login='hnah',sg_member=True,campus_id=64)}
            if token not in people:raise AuthError('No identity')
            return people[token]
        self.broker=Mock();self.broker.authenticate.side_effect=authenticate
        self.notice=Mock()
        self.admin='a'*64
        self.manager=Announcements(self.broker,'hnah',self.admin,clock=lambda:self.now,on_request=self.notice,policy=test_policy())

    def test_student_needs_host_approval_and_is_quoted_as_real_identity(self):
        request=self.manager.submit(dict(session='student',text='New version!',login='hnah',host=True))
        self.assertEqual(request['status'],'pending');self.assertEqual(request['author'],'dthoo')
        self.assertEqual(self.manager.poll({})['announcements'],[])
        self.notice.assert_called_once()
        with self.assertRaises(AuthError):self.manager.decide(dict(session='student',id=request['id'],decision='approve',host=True))
        self.manager.decide(dict(admin=self.admin,id=request['id'],decision='approve',text='cannot replace original'))
        event=self.manager.poll({})['announcements'][0]
        self.assertEqual(event['author'],'dthoo');self.assertFalse(event['is_host']);self.assertEqual(event['text'],'New version!')
        self.assertEqual(self.manager.poll(dict(session='student'))['statuses'][0]['status'],'approved')
        self.assertEqual(self.manager.poll({})['pending'],[])

    def test_owner_broadcasts_directly_and_gets_host_tag(self):
        self.manager.submit(dict(admin=self.admin,text='Please update LAN42',author='dthoo'))
        event=self.manager.poll({})['announcements'][0]
        self.assertEqual(event['author'],'hnah');self.assertTrue(event['is_host'])
        self.notice.assert_not_called()

    def test_rejection_expiry_and_repeat_decisions_do_not_broadcast(self):
        request=self.manager.submit(dict(session='student',text='Hello'))
        self.manager.decide(dict(session='owner',id=request['id'],decision='reject'))
        self.manager.decide(dict(admin=self.admin,id=request['id'],decision='approve'))
        self.assertEqual(self.manager.feed,[])
        self.now+=31
        other=self.manager.submit(dict(session='student',text='Another'))
        self.now+=301
        self.assertEqual(self.manager.decide(dict(admin=self.admin,id=other['id'],decision='approve'))['status'],'expired')
        self.assertEqual(self.manager.feed,[])

    def test_forged_identity_invalid_authority_and_unhashable_id_rejected(self):
        for data in ({'login':'hnah'},{'admin':'é'},{'admin':'0'*64}):
            with self.assertRaises(AuthError):self.manager.submit(dict(data,text='No'))
        with self.assertRaises(AuthError):self.manager.decide(dict(admin=self.admin,id=[],decision='approve'))
        with self.assertRaises(AuthError):self.manager.submit(dict(session='student',text='x'*401))

class Watch(unittest.TestCase):
    def test_offline_checks_are_bounded_and_recovery_emits_once(self):
        now=[0];inbox=queue.Queue();watch=HostWatch(inbox,clock=lambda:now[0])
        trust=dict(lobby_host='10.12.4.14',lobby_port=31417)
        result=dict(owner='hnah',epoch='epoch',announcements=[],statuses=[],pending=[])
        with patch('campus_lan.announcement_client.HostSettings') as settings, \
             patch('campus_lan.announcement_client.credentials',return_value={}), \
             patch('campus_lan.announcement_client.auth_locator.refresh'), \
             patch('campus_lan.announcement_client.auth_client.load_trust',return_value=trust), \
             patch('campus_lan.announcement_client.auth_client.post',side_effect=[AuthError('offline'),result,result]) as post:
            settings.return_value.data=dict(discovery=True,auto_join=True,interval=120)
            watch.step();offline=inbox.get_nowait();self.assertFalse(offline['online']);self.assertTrue(offline['configured'])
            now[0]=60;watch.step();self.assertEqual(post.call_count,1);self.assertTrue(inbox.empty())
            now[0]=120;watch.step();self.assertTrue(inbox.get_nowait()['recovered'])
            now[0]=125;watch.step();self.assertFalse(inbox.get_nowait()['recovered'])

    def test_popups_are_once_per_machine_not_once_across_all_shared_home_seats(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.announcement_client.config_dir',return_value=Path(tmp)), \
             patch('campus_lan.announcement_client.socket.gethostname',side_effect=['seat-a','seat-a','seat-b']):
            self.assertTrue(claim('same-announcement'));self.assertFalse(claim('same-announcement'));self.assertTrue(claim('same-announcement'))

    def test_guest_mesh_link_retries_after_an_early_host_startup_race(self):
        from types import SimpleNamespace
        c=Client.__new__(Client);c.lines=[];c.inbox=queue.Queue();c.role='lobby';c.secure=False
        c.peer_callback=Mock(side_effect=[OSError('not started yet'),None])
        event=dict(host='10.12.4.14',data={'epoch':'epoch'},auto_connect=True,retry_interval=120)
        with patch('campus_lan.announcement_ui.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target)), \
             patch('campus_lan.announcement_ui.time.monotonic',side_effect=[0,50,121]):
            c.link_api_guest_node(event);c.announcement_event(c.inbox.get_nowait())
            c.link_api_guest_node(event);self.assertEqual(c.peer_callback.call_count,1)
            c.link_api_guest_node(event);c.announcement_event(c.inbox.get_nowait())
            self.assertEqual(c.peer_callback.call_count,2)
            self.assertEqual(c.api_link_key,('10.12.4.14','epoch'))

    def test_student_confirms_request_and_host_gets_abuse_warning(self):
        for host in (False,True):
            c=Client.__new__(Client);c.lines=[];c.name='hnah' if host else 'dthoo'
            c.announcement_status={'owner':'hnah','host':host};c.popup_prompts=Mock();c.announcement_work=Mock()
            proof={'admin':'a'*64} if host else {'session':'b'*64}
            with patch('campus_lan.announcement_ui.auth_client.load_trust',return_value={}), \
                 patch('campus_lan.announcement_ui.auth_client.load_session',return_value={'login':'dthoo'}), \
                 patch('campus_lan.announcement_ui.credentials',return_value=proof), \
                 patch('campus_lan.announcement_ui.act') as act:
                self.assertTrue(c.announcement_command('/broadcast Please update'))
                description,accept=c.popup_prompts.return_value.confirm.call_args.args
                self.assertIn('Do not abuse' if host else 'intra:dthoo',description)
                act.assert_not_called();accept();c.announcement_work.call_args.args[0]()
                act.assert_called_once_with('request',text='Please update')

    def test_plain_guest_network_cannot_inject_trusted_host_events(self):
        c=Client.__new__(Client);c.connected=True;c.inbox=queue.Queue()
        c.sock=Mock();c.sock.makefile.return_value=io.BytesIO(b'{"type":"local_host_update","online":true}\n')
        c.receive();self.assertTrue(c.inbox.empty())

    def test_approved_admin_feed_bypasses_normal_chat_mute(self):
        c=Client.__new__(Client);c.lines=[];c.notify_enabled=False;c.tracking_notifier=Mock()
        data=dict(owner='hnah',epoch='epoch',pending=[],statuses=[],announcements=[dict(id='a'*32,author='dthoo',text='Update please',is_host=False)])
        with patch('campus_lan.announcement_ui.claim',return_value=True):
            self.assertTrue(c.announcement_event(dict(type='local_host_update',online=True,recovered=False,data=data)))
            c.tracking_notifier.announcement.assert_called_once()
            self.assertIn('dthoo',c.lines[0]);self.assertNotIn('(host)',c.lines[0])

class NativeTLS(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name});self.env.start()
        credentials=Path(self.temp.name)/'fake.env'
        private_write(credentials,'FT42_CLIENT_ID=test-id\nFT42_CLIENT_SECRET=test-secret\nFT42_REDIRECT_URI=http://localhost:31415/callback\n')
        self.trust=setup(credentials,'127.0.0.1')
        self.broker=Broker(Mock())
        self.token='b'*64;self.broker.sessions[digest(self.token)]=dict(uid=2,login='dthoo',expires=time.time()+600,sg_member=True,campus_id=64)
        self.manager=Announcements(self.broker,'hnah','a'*64,on_request=Mock(),policy=test_policy())
        self.http=AuthHTTP(self.broker,'');self.http.announcements=self.manager
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(config_dir()/'auth-cert.pem',config_dir()/'auth-key.pem')
        self.server=await asyncio.start_server(self.http.handle,'127.0.0.1',0,ssl=context)
        port=self.server.sockets[0].getsockname()[1];self.http.authority=f'127.0.0.1:{port}'
        self.trust['broker_url']='https://'+self.http.authority

    async def asyncTearDown(self):
        self.server.close();await self.server.wait_closed();await asyncio.sleep(.02)
        self.env.stop();self.temp.cleanup()

    async def post(self,path,data):return await asyncio.to_thread(auth_client.post,self.trust,'/announcements/'+path,data)

    async def test_request_reject_and_approve_over_real_pinned_tls(self):
        request=await self.post('request',dict(session=self.token,text='A signed-in request',author='hnah'))
        self.assertEqual(request['author'],'dthoo');self.assertEqual(request['status'],'pending')
        with self.assertRaises(AuthError):await self.post('decide',dict(session=self.token,id=request['id'],decision='approve'))
        await self.post('decide',dict(admin='a'*64,id=request['id'],decision='approve'))
        feed=await self.post('poll',{})
        self.assertEqual(feed['announcements'][0]['author'],'dthoo')
        self.assertFalse(feed['announcements'][0]['is_host'])
        self.assertEqual(feed['pending'],[])

if __name__=='__main__':unittest.main()

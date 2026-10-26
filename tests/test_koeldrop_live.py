"""Controlled campus evidence and in-memory HTTP; never contact the live API."""
import asyncio
import io
import json
import os
from pathlib import Path
import queue
import tempfile
import time
import unittest
from unittest.mock import Mock,patch
from campus_lan.auth import Broker,digest
from campus_lan.client import Client
from campus_lan.file_sharing.client import Courier
from campus_lan.file_sharing.remote import RemoteStore
from campus_lan.file_sharing.runtime import Runtime
from campus_lan.file_sharing.security import Gate,Proof,Denied,Conflict
from campus_lan.file_sharing.settings import ExperimentalSettings
from campus_lan.file_sharing.store import Store
from campus_lan.file_sharing.http import Requests


class KoelDropLive(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.env=patch.dict(os.environ,XDG_CONFIG_HOME=self.tmp.name);self.env.start();self.addCleanup(self.env.stop)
        self.settings=ExperimentalSettings();self.settings.set(True)
        self.broker=Broker(Mock());self.tokens={'hnah':'1'*64,'dthoo':'2'*64}
        self.peers={'hnah':'10.11.3.6','dthoo':'10.11.4.2'}
        self.uids={'hnah':1,'dthoo':2}
        proofs=Mock()
        proofs.identity.side_effect=lambda uid,name:Proof(True,('c1r3s6' if uid==1 else 'c1r4s2',),time.time())
        proofs.target.side_effect=lambda name:(self.uids[name],name)
        self.gate=Gate(self.broker,proofs,enabled=lambda:ExperimentalSettings().enabled)
        self.actors={}
        for name,token in self.tokens.items():
            self.broker.sessions[digest(token)]=dict(uid=self.uids[name],login=name,expires=time.time()+3600)
            self.actors[name]=self.gate.admit(token,self.peers[name],True)
        self.store=Store(Path(self.tmp.name)/'store',self.gate);self.addCleanup(self.store.close)
        self.requests=Requests(self.store,self.actors['hnah'],31416)
        self.trust=dict(lobby_host=self.peers['hnah'],broker_url='https://'+self.peers['hnah']+':31416')
        owner=self
        class Connection:
            def __init__(self,trust):
                if trust!=owner.trust:raise AssertionError('Unexpected endpoint')
            def request(self,method,route,body,headers):
                name=next(n for n,t in owner.tokens.items() if headers['Authorization']=='Bearer '+t)
                normalized={k.lower():v for k,v in headers.items()};normalized['host']=owner.requests.authority
                self.reply=owner.requests.dispatch(method,route,normalized,body,owner.peers[name],True,owner.peers['hnah'])
            def getresponse(self):
                reply=self.reply;stream=io.BytesIO(reply.body)
                return Mock(status=reply.status,read=stream.read,getheaders=lambda:list(reply.headers.items()))
            def close(self):pass
        self.connection=patch('campus_lan.auth_client.PinnedHTTPSConnection',Connection)
        self.connection.start();self.addCleanup(self.connection.stop)

    def remote(self,name):return RemoteStore(self.tokens[name],self.trust)
    def courier(self,name):
        courier=Courier(self.tokens[name],self.uids[name],name,queue.Queue(),self.remote(name))
        self.addCleanup(lambda:courier.sync.mirror.close() if courier.sync else None)
        courier.perform('dir',(str(Path(self.tmp.name)/('mirror-'+name)),))
        return courier

    def test_two_users_upload_approve_reply_and_leave_through_http_client(self):
        host=self.courier('hnah');host.perform('create',())
        gid=host.sync.group
        invitation=host.remote.invite(None,gid,'dthoo')
        bob=self.courier('dthoo');bob.perform('accept',(gid,'hnah',invitation['invite']))
        (host.sync.mirror.path/'funny.txt').write_bytes(b'uwu')
        host.perform('sync',());bob.perform('sync',())
        self.assertFalse((bob.sync.mirror.path/'funny.txt').exists())
        version=next(iter(bob.sync.pending));bob.perform('receive',(version,))
        self.assertEqual((bob.sync.mirror.path/'funny.txt').read_bytes(),b'uwu')
        (bob.sync.mirror.path/'funny.txt').write_bytes(b'lunch?')
        bob.perform('sync',());host.perform('sync',())
        host.perform('receive',(next(iter(host.sync.pending)),))
        self.assertEqual((host.sync.mirror.path/'funny.txt').read_bytes(),b'lunch?')
        bob.perform('leave',())
        with self.assertRaises(Denied):bob.remote.manifest(None,gid)
        self.assertTrue((Path(self.tmp.name)/'mirror-dthoo'/'funny.txt').exists())

    def test_stale_write_cannot_overwrite_and_off_blocks_remote_before_connection(self):
        remote=self.remote('hnah');gid=remote.create()
        one=remote.put(None,gid,'a.txt',b'one')
        remote.put(None,gid,'a.txt',b'two',one['version'])
        with self.assertRaises(Conflict):remote.put(None,gid,'a.txt',b'stale',one['version'])
        remote.cancelled=lambda:not ExperimentalSettings().enabled
        self.settings.set(False)
        with patch('campus_lan.auth_client.PinnedHTTPSConnection') as connection:
            with self.assertRaises(Denied):remote.manifest(None,gid)
            connection.assert_not_called()

    def test_existing_personal_folder_is_never_uploaded(self):
        host=self.courier('hnah');path=Path(host.folder);path.mkdir();(path/'private.txt').write_bytes(b'private')
        with self.assertRaises(Denied):host.perform('create',())
        self.assertIsNone(host.sync)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM versions').fetchone()[0],0)

    def test_worker_stops_when_disabled_without_scanning(self):
        worker=self.courier('hnah');self.settings.set(False)
        worker.submit('create');worker.thread.join(2)
        self.assertTrue(worker.stopped.is_set());self.assertFalse(worker.thread.is_alive())
        self.assertIsNone(worker.sync)

    def test_settings_default_off_and_generations_invalidate_fast_toggle(self):
        first=self.settings.generation
        self.settings.set(False);off=self.settings.generation
        self.settings.set(True)
        self.assertNotEqual(first,off);self.assertNotEqual(first,self.settings.generation)
        self.settings.path.write_text('{bad json');self.assertFalse(ExperimentalSettings().enabled)
        self.settings.path.unlink();self.assertFalse(ExperimentalSettings().enabled)

    def test_wire_cannot_inject_local_approval_events(self):
        client=Client.__new__(Client);client.inbox=queue.Queue();client.connected=True
        messages=[dict(type=kind) for kind in ('notification_action','local_koel','local_signin','popup_opened','signin_resume','event')]
        client.sock=Mock();client.sock.makefile.return_value=io.BytesIO(b''.join(json.dumps(m).encode()+b'\n' for m in messages))
        client.receive()
        self.assertEqual(client.inbox.get_nowait(),dict(type='event'));self.assertTrue(client.inbox.empty())

    def test_popup_allow_does_not_approve_group_or_file(self):
        from campus_lan.popup_permissions import Permissions,Prompts
        permissions=Permissions('hnah');permissions.set('notifications','allow')
        report=[];prompts=Prompts(permissions,report.append);action=Mock();decline=Mock()
        prompts.confirm('Join this group?',action,decline)
        self.assertEqual(prompts.activate()[3],'decision');action.assert_not_called()
        prompts.answer('');decline.assert_called_once();action.assert_not_called()
        prompts.confirm('Join this group?',action);prompts.activate();prompts.answer('y');action.assert_called_once()

    def test_invitation_is_only_delivered_to_verified_recipient(self):
        gid=self.store.create(self.actors['hnah'],self.peers['hnah'])
        invitation=self.store.invite(self.actors['hnah'],gid,'dthoo')
        runtime=Runtime(self.broker,self.peers['hnah'],31416,owner='hnah')
        runtime.requests=self.requests;runtime.generation=ExperimentalSettings().generation
        writer=Mock();writer.get_extra_info.return_value=(self.peers['hnah'],1234)
        lobby=Mock();lobby.clients={1:dict(session_key=digest(self.tokens['hnah']),writer=writer),
                                  2:dict(uid=2,role='lobby'),3:dict(uid=3,role='lobby'),4:dict(name='dthoo',role='lobby')}
        from unittest.mock import AsyncMock
        lobby.broadcast=AsyncMock();lobby.event=AsyncMock()
        asyncio.run(runtime.deliver_invite(lobby,1,dict(group=gid,invite=invitation['invite'])))
        message,recipients=lobby.broadcast.call_args.args
        self.assertEqual(recipients,{2});self.assertEqual(message['invite'],invitation['invite'])
        self.settings.set(False)
        with self.assertRaises(Denied):asyncio.run(runtime.deliver_invite(lobby,1,dict(group=gid,invite=invitation['invite'])))

    def test_invalid_native_invitation_is_ignored_and_valid_one_requires_action(self):
        client=Client.__new__(Client);client.secure=True;client.lines=[];client.koel_notice=Mock()
        message=dict(group='a'*32,invite='b'*43,host='hnah',expires=time.time()+200)
        client.koel_invitation(dict(message,host='hnah\n/koel create'))
        self.assertFalse(hasattr(client,'koel_invites'))
        client.koel_invitation(message)
        self.assertEqual(len(client.koel_invites),1);self.assertFalse(hasattr(client,'courier'))
        self.assertIn('/koel accept 1',' '.join(client.lines))
        client.koel_invitation(message);self.assertEqual(len(client.koel_invites),1)

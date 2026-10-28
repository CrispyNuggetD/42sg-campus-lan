import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock,patch
from urllib.parse import quote
from campus_lan.auth import Broker,digest
from campus_lan.file_sharing import start
from campus_lan.file_sharing.security import Gate,Proof,Denied,Conflict,Limit,CampusProofs
from campus_lan.file_sharing.store import Store,MAX_FILE
from campus_lan.file_sharing.http import Requests
from campus_lan.file_sharing.sync import Mirror,ReceivePolicy


class Evidence:
    def __init__(self,clock):
        self.clock=clock;self.member=True;self.seats={1:('c1r1s1',),2:('c2r2s2',),3:('c1r3s3',)}
        self.names={'hnah':1,'dthoo':2,'thtay':3}
    def identity(self,uid,name):return Proof(self.member,self.seats.get(uid,()),self.clock())
    def target(self,name):
        if name not in self.names:raise Denied('Not a campus account.')
        return self.names[name],name


class FileSharing(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(tempfile.gettempdir()).resolve());self.addCleanup(self.tmp.cleanup)
        self.now=1000.;self.clock=lambda:self.now
        self.broker=Broker(Mock(),clock=self.clock);self.proofs=Evidence(self.clock);self.gate=Gate(self.broker,self.proofs,self.clock)
        self.tokens={};self.actors={}
        for uid,name,peer in ((1,'hnah','10.11.1.1'),(2,'dthoo','10.12.2.2'),(3,'thtay','10.11.3.3')):
            token=str(uid)*64;self.tokens[name]=token
            self.broker.sessions[digest(token)]=dict(uid=uid,login=name,expires=2000.)
            self.actors[name]=self.gate.admit(token,peer,True)
        self.host,self.bob,self.other=(self.actors[n] for n in ('hnah','dthoo','thtay'))
        self.store=Store(Path(self.tmp.name)/'store',self.gate,self.clock);self.addCleanup(self.store.close)
        self.gid=self.store.create(self.host,self.host.peer_ip)

    def test_keep_both_preserves_local_and_server_versions(self):
        from campus_lan.file_sharing.controller import SyncSession
        self.join()
        remote=self.store._put_history(self.bob,self.gid,'report.pdf',b'dthoo version')
        mirror=Mirror(Path(self.tmp.name)/'keep-both',1,'hnah');self.addCleanup(mirror.close)
        (mirror.path/'report.pdf').write_bytes(b'my version')
        sync=SyncSession(self.store,self.host,self.gid,mirror)
        sync.step(publish=True)
        path=sync.keep_both(remote['version'])
        self.assertTrue(path.startswith('hnah/report_hnah_'))
        self.assertEqual((mirror.path/path).read_bytes(),b'my version')
        self.assertEqual((mirror.path/'report.pdf').read_bytes(),b'dthoo version')
        files={f['path']:f for f in self.store.manifest(self.host,self.gid)['files']}
        self.assertEqual(files['report.pdf']['version'],remote['version'])
        self.assertEqual(self.store.read(self.host,self.gid,files[path]['version'])[1],b'my version')
        self.assertEqual(len(list((mirror.path/'.lan42-file-backups').glob('*.bak'))),1)

    def test_keep_both_stale_offer_leaves_local_intact(self):
        from campus_lan.file_sharing.controller import SyncSession
        remote=self.store._put_history(self.host,self.gid,'report.pdf',b'first')
        mirror=Mirror(Path(self.tmp.name)/'stale-both',1,'hnah');self.addCleanup(mirror.close)
        (mirror.path/'report.pdf').write_bytes(b'mine')
        sync=SyncSession(self.store,self.host,self.gid,mirror);sync.step()
        self.store._put_history(self.host,self.gid,'report.pdf',b'changed',remote['version'])
        with self.assertRaises(Conflict):sync.keep_both(remote['version'])
        self.assertEqual((mirror.path/'report.pdf').read_bytes(),b'mine')
        self.assertFalse((mirror.path/'hnah').exists())

    def test_conflict_notification_deduplicates_and_offers_keep_both(self):
        from campus_lan.file_sharing.ui import KoelUI
        ui=KoelUI();worker=Mock();ui.courier=worker;ui.lines=[];ui.name='hnah'
        ui.koel_notice=Mock()
        offer=dict(version='a'*32,path='report.pdf',author='dthoo',size=2,deleted=False)
        message=dict(courier=id(worker),offers=[offer],conflicts=[offer],notices=[])
        ui.koel_local(message);ui.koel_local(message)
        ui.koel_notice.assert_called_once()
        call=ui.koel_notice.call_args
        self.assertEqual(call.kwargs['labels'],('Keep both','Later'))
        self.assertEqual(call.args[3],'/koel resolve 1')
        self.assertIn('dthoo',call.args[1])
        ui.popup_prompts=Mock();ui.koel_worker=lambda:worker
        ui.koel_command('/koel resolve 1')
        worker.submit.assert_not_called()
        ui.popup_prompts().confirm.call_args.args[1]()
        worker.submit.assert_called_once_with('resolve','a'*32)

    def test_add_only_names_author_revisions_retry_and_rename(self):
        self.join()
        first=self.store.put(self.bob,self.gid,'report.pdf',b'one')
        self.assertEqual(first['path'],'report_dthoo_1.pdf')
        self.assertEqual(self.store.put(self.bob,self.gid,'report.pdf',b'one'),first)
        second=self.store.put(self.bob,self.gid,'report.pdf',b'two',first['version'])
        self.assertEqual(second['path'],'report_dthoo_2.pdf')
        reverted=self.store.put(self.bob,self.gid,'report.pdf',b'one',second['version'])
        self.assertEqual(reverted['path'],'report_dthoo_3.pdf')
        renamed=self.store.put(self.bob,self.gid,'renamed.pdf',b'one')
        self.assertEqual(renamed['path'],'renamed_dthoo_1.pdf')
        other=self.store.put(self.host,self.gid,'report.pdf',b'host')
        self.assertEqual(other['path'],'report_hnah_1.pdf')
        self.assertEqual(len(self.store.manifest(self.host,self.gid)['files']),5)
        self.assertEqual(self.store.read(self.host,self.gid,first['version'])[1],b'one')
        with self.assertRaises(Denied):self.store.delete(self.bob,self.gid,first['path'],first['version'])

    def test_editing_assigned_name_advances_lineage_without_overwrite(self):
        first=self.store.put(self.host,self.gid,'x.txt',b'one')
        second=self.store.put(self.host,self.gid,first['path'],b'two',first['version'])
        self.assertEqual(second['path'],'x_hnah_2.txt')
        self.assertEqual(self.store.read(self.host,self.gid,first['version'])[1],b'one')

    def test_addition_limits_separate_shared_and_own_persisted(self):
        from campus_lan.file_sharing.store import SHARED_ADDITIONS_PER_MINUTE,OWN_ADDITIONS_PER_MINUTE
        for n in range(SHARED_ADDITIONS_PER_MINUTE):self.store.put(self.host,self.gid,'shared/file'+str(n),b'x')
        with self.assertRaises(Limit):self.store.put(self.host,self.gid,'root.txt',b'x')
        for n in range(OWN_ADDITIONS_PER_MINUTE):self.store.put(self.host,self.gid,'hnah/file'+str(n),b'x')
        with self.assertRaises(Limit):self.store.put(self.host,self.gid,'hnah/extra',b'x')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM additions').fetchone()[0],36)
        self.now+=61
        self.store.put(self.host,self.gid,'root.txt',b'x')
        self.store.put(self.host,self.gid,'hnah/extra',b'x')

    def test_upload_receipt_cannot_write_other_member_or_reserved_paths(self):
        mirror=Mirror(Path(self.tmp.name)/'receipt-check',1,'hnah');self.addCleanup(mirror.close)
        mirror.members={'hnah','dthoo'}
        (mirror.path/'report.pdf').write_bytes(b'x')
        for assigned in ('dthoo/report.pdf','logs/report.pdf','elsewhere/report.pdf'):
            receipt=dict(path=assigned,number=1,author='hnah',version='a'*32,digest=hashlib.sha256(b'x').hexdigest())
            with self.assertRaises(Denied):mirror.upload('report.pdf',lambda *args:receipt,approved=True)
            self.assertFalse((mirror.path/assigned).exists())

    def test_addition_limits_survive_new_store_connection_and_identity_scope(self):
        from campus_lan.file_sharing.store import SHARED_ADDITIONS_PER_MINUTE
        for n in range(SHARED_ADDITIONS_PER_MINUTE):self.store.put(self.host,self.gid,'item'+str(n),b'x')
        reopened=Store(Path(self.tmp.name)/'store',self.gate,self.clock)
        try:
            with self.assertRaises(Limit):reopened.put(self.host,self.gid,'extra',b'x')
            # Retry receipts do not consume an additional slot.
            self.assertEqual(reopened.put(self.host,self.gid,'item0',b'x')['path'],'item0_hnah_1')
        finally:reopened.close()
        self.join()
        self.assertEqual(self.store.put(self.bob,self.gid,'report.pdf',b'x')['path'],'report_dthoo_1.pdf')
        with self.assertRaises(Denied):self.store.put(self.bob,self.gid,'hnah/fake.txt',b'x')

    def test_shared_byte_limit_and_downloaded_copy_becomes_new_authored_addition(self):
        from campus_lan.file_sharing import store as module
        with patch.object(module,'SHARED_BYTES_PER_MINUTE',3):
            first=self.store.put(self.host,self.gid,'a.txt',b'abc')
            with self.assertRaises(Limit):self.store.put(self.host,self.gid,'b.txt',b'x')
            self.store.put(self.host,self.gid,'hnah/b.txt',b'x')
        self.join()
        second=self.store.put(self.bob,self.gid,first['path'],b'dthoo edit',first['version'])
        self.assertEqual(second['path'],'a_dthoo_1.txt')
        self.assertEqual(self.store.read(self.host,self.gid,first['version'])[1],b'abc')

    def test_http_delete_denied_and_assigned_name_returned(self):
        request=Requests(self.store,self.host,34443)
        headers={'host':'10.11.1.1:34443','authorization':'Bearer '+self.tokens['hnah'],'content-type':'application/octet-stream','x-lan42-file-path':'report.pdf','if-none-match':'*','content-length':'3'}
        route='/v1/groups/'+self.gid+'/files'
        reply=request.dispatch('PUT',route,headers,b'one',self.host.peer_ip,True,self.host.peer_ip)
        self.assertEqual(reply.status,201)
        receipt=json.loads(reply.body);self.assertEqual(receipt['path'],'report_hnah_1.pdf')
        delete={**headers,'content-length':'0','x-lan42-file-path':receipt['path'],'if-match':receipt['version']}
        self.assertEqual(request.dispatch('DELETE',route,delete,b'',self.host.peer_ip,True,self.host.peer_ip).status,403)
        self.assertEqual(len(self.store.manifest(self.host,self.gid)['files']),1)

    def test_assigned_copy_upload_feedback_does_not_echo_or_remove_sources(self):
        from campus_lan.file_sharing.controller import SyncSession
        mirror=Mirror(Path(self.tmp.name)/'append-client',1,'hnah');self.addCleanup(mirror.close)
        sync=SyncSession(self.store,self.host,self.gid,mirror)
        source=mirror.path/'report.pdf';source.write_bytes(b'mine')
        report=sync.step(publish=True)
        self.assertEqual(report['uploaded'],['report_hnah_1.pdf'])
        self.assertEqual(source.read_bytes(),b'mine')
        self.assertEqual((mirror.path/'report_hnah_1.pdf').read_bytes(),b'mine')
        self.assertEqual(sync.step(publish=True)['uploaded'],[])
        source.write_bytes(b'edit');sync.step(publish=True)
        self.assertEqual((mirror.path/'report_hnah_2.pdf').read_bytes(),b'edit')
        source.unlink();sync.step(publish=True,publish_deletes=True)
        self.assertEqual(len(self.store.manifest(self.host,self.gid)['files']),2)

    def legacy_manifest(self,*args):
        """Fixture for validating safety when reading earlier mutable records."""
        return dict(self.store.manifest(*args),append_only=False)

    def join(self,actor=None):
        actor=actor or self.bob
        invitation=self.store.invite(self.host,self.gid,actor.login)
        self.store.accept(actor,self.gid,invitation['invite']);return invitation

    def test_runtime_construction_never_opens_socket_or_scans_folders(self):
        with patch('socket.socket') as socket:
            runtime=start(self.broker,'10.11.1.1',31416,root=Path(self.tmp.name)/'unused',owner='hnah')
            self.assertIsNone(runtime.requests)
            socket.assert_not_called()

    def test_tls_campus_membership_freshness_and_actual_socket_address_required(self):
        for peer,tls in (('127.0.0.1',True),('0.0.0.0',True),('192.168.1.2',True),('10.11.1.0',True),('10.11.1.1',False),('10.11.9.9',True)):
            with self.assertRaises(Denied):self.gate.admit(self.tokens['hnah'],peer,tls)
        self.proofs.member=False
        with self.assertRaises(Denied):self.gate.check(self.host)
        self.proofs.member=True
        with patch.object(self.proofs,'identity',return_value=Proof(True,('c1r1s1',),self.now-121)):
            with self.assertRaises(Denied):self.gate.check(self.host)
        self.proofs.seats[1]=()
        with self.assertRaises(Denied):self.legacy_manifest(self.host,self.gid)

    def test_invitation_is_recipient_bound_one_use_and_never_logged_raw(self):
        invite=self.store.invite(self.host,self.gid,'dthoo')
        with self.assertRaises(Denied):self.store.accept(self.other,self.gid,invite['invite'])
        self.store.accept(self.bob,self.gid,invite['invite'])
        with self.assertRaises(Denied):self.store.accept(self.bob,self.gid,invite['invite'])
        self.assertNotIn(invite['invite'],json.dumps(self.store.history(self.host,self.gid)))
        with self.assertRaises(Denied):self.store.invite(self.bob,self.gid,'thtay')

    def test_invite_expiry_host_logout_and_new_recipient_session(self):
        invite=self.store.invite(self.host,self.gid,'dthoo');self.now+=301
        with self.assertRaises(Denied):self.store.accept(self.bob,self.gid,invite['invite'])
        self.now=1000.;self.join()
        new_token='a'*64;self.broker.sessions[digest(new_token)]=dict(uid=2,login='dthoo',expires=2000.)
        new_identity=self.gate.admit(new_token,self.bob.peer_ip,True)
        with self.assertRaises(Denied):self.legacy_manifest(new_identity,self.gid)
        self.broker.logout(self.host.session_key)
        with self.assertRaises(Denied):self.legacy_manifest(self.bob,self.gid)

    def test_private_folders_and_shared_root_permissions(self):
        self.join()
        mine=self.store._put_history(self.host,self.gid,'hnah/a.txt',b'host')
        theirs=self.store._put_history(self.bob,self.gid,'dthoo/a.txt',b'guest')
        self.assertEqual(self.store.read(self.host,self.gid,theirs['version'])[1],b'guest')
        for actor,path in ((self.host,'dthoo/a.txt'),(self.bob,'hnah/a.txt'),(self.host,'welcome.md'),(self.host,'logs/events.json')):
            with self.assertRaises(Denied):self.store._put_history(actor,self.gid,path,b'bad')
        shared=self.store._put_history(self.host,self.gid,'funny.txt',b'one')
        changed=self.store._put_history(self.bob,self.gid,'funny.txt',b'two',shared['version'])
        self.store._delete_history(self.host,self.gid,'funny.txt',changed['version'])
        self.assertEqual(self.store.read(self.bob,self.gid,shared['version'])[1],b'one')
        with self.assertRaises(Denied):self.legacy_manifest(self.other,self.gid)

    def test_stale_overwrites_and_deletes_preserve_original_history(self):
        version=self.store._put_history(self.host,self.gid,'note.txt',b'initial')
        with self.assertRaises(Conflict):self.store._put_history(self.host,self.gid,'note.txt',b'blind')
        second=self.store._put_history(self.host,self.gid,'note.txt',b'changed',version['version'])
        with self.assertRaises(Conflict):self.store._put_history(self.host,self.gid,'note.txt',b'stale',version['version'])
        with self.assertRaises(Conflict):self.store._delete_history(self.host,self.gid,'note.txt',version['version'])
        self.assertEqual(self.store.read(self.host,self.gid,second['version'])[1],b'changed')
        events=self.store.history(self.host,self.gid)
        previous='0'*64
        for event in events:
            self.assertEqual(event['previous'],previous)
            payload=json.dumps(event['event'],sort_keys=True,separators=(',',':'))
            self.assertEqual(event['hash'],hashlib.sha256((previous+payload).encode()).hexdigest());previous=event['hash']

    def test_traversal_hidden_names_and_cross_group_version_access(self):
        for path in ('../outside','/absolute','hnah/../../outside','a//b','hnah/.env','%2e%2e/outside','a\\b','a\n.txt','logs/a','other/directory/file'):
            with self.assertRaises(Denied):self.store._put_history(self.host,self.gid,path,b'bad')
        version=self.store._put_history(self.host,self.gid,'file.txt',b'ok')
        other_group=self.store.create(self.host,self.host.peer_ip)
        with self.assertRaises(Denied):self.store.read(self.host,other_group,version['version'])
        self.assertFalse((Path(self.tmp.name)/'outside').exists())

    def test_file_and_retained_quota_and_private_modes(self):
        with self.assertRaises(Limit):self.store._put_history(self.host,self.gid,'big.bin',b'x'*(MAX_FILE+1))
        with patch('campus_lan.file_sharing.store.MAX_STORAGE',1):
            with self.assertRaises(Limit):self.store._put_history(self.host,self.gid,'two.txt',b'12')
        version=self.store._put_history(self.host,self.gid,'safe.py',b'print("never executed")')
        self.assertEqual((self.store.root/'objects'/(version['version']+'.blob')).stat().st_mode&0o777,0o600)
        self.assertEqual((self.store.root/'files.sqlite').stat().st_mode&0o777,0o600)

    def test_storage_and_mirror_symlink_escape_is_refused(self):
        outside=Path(self.tmp.name)/'outside';outside.mkdir(mode=0o700)
        link=Path(self.tmp.name)/'link';link.symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OSError):Store(link,self.gate,self.clock)
        mirror=Mirror(Path(self.tmp.name)/'mirror',1,'hnah');self.addCleanup(mirror.close)
        (mirror.path/'hnah').symlink_to(outside,target_is_directory=True)
        with self.assertRaises(OSError):mirror._read('hnah/file')
        (outside/'file').write_bytes(b'outside')
        (mirror.path/'hard').hardlink_to(outside/'file')
        with self.assertRaises(Denied):mirror._read('hard')

    def test_http_auth_proxy_rejection_and_download_is_attachment(self):
        request=Requests(self.store,self.host,34443)
        headers=dict(host='10.11.1.1:34443',authorization='Bearer '+self.tokens['hnah'])
        def get(extra=None,peer='10.11.1.1',tls=True,local='10.11.1.1'):
            return request.dispatch('GET','/v1/groups/'+self.gid+'/manifest',{**headers,**(extra or {})},b'',peer,tls,local)
        self.assertEqual(get().status,200)
        for extra in ({'origin':'http://evil'},{'x-forwarded-for':'10.11.1.1'},{'cookie':'anything'},{'host':'localhost:34443'},{'authorization':'Bearer bad'}):
            self.assertEqual(get(extra).status,403)
        self.assertEqual(get(tls=False).status,403);self.assertEqual(get(peer='127.0.0.1').status,403)
        version=self.store._put_history(self.host,self.gid,'page.html',b'<script>evil()</script>')
        reply=request.dispatch('GET','/v1/groups/'+self.gid+'/files',{**headers,'x-lan42-file-version':version['version']},b'',self.host.peer_ip,True,self.host.peer_ip)
        self.assertEqual(reply.status,200);self.assertEqual(reply.headers['Content-Type'],'application/octet-stream')
        self.assertTrue(reply.headers['Content-Disposition'].startswith('attachment;'));self.assertEqual(reply.headers['X-Content-Type-Options'],'nosniff')

    def test_http_requires_write_preconditions_and_does_not_serve_filesystem(self):
        request=Requests(self.store,self.host,34443)
        headers={'host':'10.11.1.1:34443','authorization':'Bearer '+self.tokens['hnah'],'content-type':'application/octet-stream','content-length':'1','x-lan42-file-path':quote('shared/a.txt',safe='/')}
        route='/v1/groups/'+self.gid+'/files'
        self.assertEqual(request.dispatch('PUT',route,headers,b'x',self.host.peer_ip,True,self.host.peer_ip).status,409)
        self.assertEqual(request.dispatch('PUT',route,{**headers,'if-none-match':'*'},b'x',self.host.peer_ip,True,self.host.peer_ip).status,201)
        self.assertEqual(request.dispatch('GET','/etc/passwd',{**headers,'content-length':'0'},b'',self.host.peer_ip,True,self.host.peer_ip).status,403)

    def test_two_user_mirror_approval_conflicts_and_delete_consent(self):
        self.join();version=self.store._put_history(self.bob,self.gid,'dthoo/funny.txt',b'funny')
        mirror=Mirror(Path(self.tmp.name)/'mirror',1,'hnah');self.addCleanup(mirror.close)
        offer=mirror.offers(self.legacy_manifest(self.host,self.gid))[0]
        fetch=lambda v:self.store.read(self.host,self.gid,v)[1]
        with self.assertRaises(Denied):mirror.receive(offer,fetch)
        self.assertFalse((mirror.path/'dthoo/funny.txt').exists())
        mirror.receive(offer,fetch,approved=True)
        self.assertEqual((mirror.path/'dthoo/funny.txt').read_bytes(),b'funny')
        self.assertEqual((mirror.path/'dthoo/funny.txt').stat().st_mode&0o777,0o400)
        with self.assertRaises(Denied):mirror.upload('dthoo/funny.txt',lambda *a:None,approved=True)
        second=self.store._put_history(self.bob,self.gid,'dthoo/funny.txt',b'new',version['version'])
        path=mirror.path/'dthoo/funny.txt';path.chmod(0o600);path.write_bytes(b'local edits')
        offer=mirror.offers(self.legacy_manifest(self.host,self.gid))[0]
        with self.assertRaises(Conflict):mirror.receive(offer,fetch,approved=True)
        self.assertEqual(path.read_bytes(),b'local edits')
        policy=ReceivePolicy(allowed_uids=frozenset({2}))
        self.assertTrue(policy.allows(offer))
        self.store._delete_history(self.bob,self.gid,'dthoo/funny.txt',second['version'])
        deletion=mirror.offers(self.legacy_manifest(self.host,self.gid))[0]
        self.assertFalse(policy.allows(deletion))

    def test_automatic_receive_for_friends_is_explicit_and_local(self):
        self.join();self.store._put_history(self.bob,self.gid,'root.txt',b'data')
        mirror=Mirror(Path(self.tmp.name)/'mirror',1,'hnah',ReceivePolicy(friend_names=frozenset({'dthoo'})));
        offer=mirror.offers(self.legacy_manifest(self.host,self.gid))[0]
        mirror.receive(offer,lambda version:self.store.read(self.host,self.gid,version)[1])
        self.assertEqual((mirror.path/'root.txt').read_bytes(),b'data')
        new=mirror.relocate(Path(self.tmp.name)/'new-mirror')
        self.addCleanup(new.close)
        self.assertTrue((mirror.path/'root.txt').exists());self.assertEqual(os.listdir(new.fd),[])

    def test_campus_proof_adapter_rejects_other_campuses_and_keeps_only_minimal_fields(self):
        api=Mock()
        api.get.side_effect=[dict(id=99,name='Singapore'),dict(id=1,login='hnah',email='not retained',**{'active?':True},campus_users=[dict(campus_id=99,is_primary=True)])]
        api.pages.return_value=[dict(end_at=None,user=dict(id=1,login='hnah'),host='c1r1s1')]
        proof=CampusProofs(api,99,self.clock).identity(1,'hnah')
        self.assertTrue(proof.member);self.assertEqual(proof.seats,('c1r1s1',));self.assertNotIn('email',str(proof))
        api.get.return_value=dict(id=99,name='Other campus');api.get.side_effect=None
        with self.assertRaises(Denied):CampusProofs(api,99,self.clock).identity(1,'hnah')

    def test_cli_staged_commands_do_not_send_invites_or_touch_files(self):
        import collections
        from campus_lan.client import Client
        client=Client.__new__(Client);client.lines=collections.deque();client.send=Mock();client.request_popup=Mock()
        for command in ('/files create','/files invite friends','/files accept anything','/files dir /tmp/anything','/settings files on'):
            if command.startswith('/settings'):client.settings_command(command)
            else:self.assertTrue(client.koel_command(command))
        client.send.assert_not_called();client.request_popup.assert_not_called()
        self.assertIn('signed-in HQ',' '.join(client.lines))
        client.koel_command('/roadmap files');self.assertIn('KoelDrop',' '.join(client.lines))

    def test_namespace_stays_reserved_after_member_leaves_and_pending_invite(self):
        self.store.invite(self.host,self.gid,'dthoo')
        with self.assertRaises(Denied):self.store._put_history(self.host,self.gid,'dthoo',b'collision')
        self.join();self.store._put_history(self.bob,self.gid,'dthoo/a.txt',b'private namespace')
        self.store.leave(self.bob,self.gid)
        with self.assertRaises(Denied):self.store._put_history(self.host,self.gid,'dthoo/a.txt',b'host overwrite')
        with self.assertRaises(Denied):self.store._put_history(self.host,self.gid,'dthoo',b'collision')

    def test_incoming_install_never_replaces_a_racing_local_file_and_keeps_backup(self):
        first=self.store._put_history(self.host,self.gid,'note.txt',b'first')
        mirror=Mirror(Path(self.tmp.name)/'race-mirror',1,'hnah');self.addCleanup(mirror.close)
        fetch=lambda version:self.store.read(self.host,self.gid,version)[1]
        offer=mirror.offers(self.legacy_manifest(self.host,self.gid))[0];mirror.receive(offer,fetch,approved=True)
        self.store._put_history(self.host,self.gid,'note.txt',b'second',first['version'])
        offer=mirror.offers(self.legacy_manifest(self.host,self.gid))[0]
        backup=mirror._backup
        def editor(parent,name,baseline):
            backup(parent,name,baseline)
            (mirror.path/'note.txt').write_bytes(b'new local editor contents')
        with patch.object(mirror,'_backup',side_effect=editor):
            with self.assertRaises(Conflict):mirror.receive(offer,fetch,approved=True)
        self.assertEqual((mirror.path/'note.txt').read_bytes(),b'new local editor contents')
        self.assertEqual([p.read_bytes() for p in (mirror.path/'.lan42-file-backups').iterdir()],[b'first'])

    def test_simultaneous_stale_writes_have_one_winner(self):
        from concurrent.futures import ThreadPoolExecutor
        first=self.store._put_history(self.host,self.gid,'race.txt',b'first')
        def write(data):
            try:return self.store._put_history(self.host,self.gid,'race.txt',data,first['version'])
            except Conflict:return None
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(write,(b'one',b'two')))
        self.assertEqual(sum(result is not None for result in results),1)

    def test_file_directory_collisions_are_rejected_in_both_directions(self):
        self.store._put_history(self.host,self.gid,'hnah/file',b'one')
        with self.assertRaises(Conflict):self.store._put_history(self.host,self.gid,'hnah/file/child',b'two')
        self.store._put_history(self.host,self.gid,'hnah/folder/child',b'one')
        with self.assertRaises(Conflict):self.store._put_history(self.host,self.gid,'hnah/folder',b'two')

    def test_generated_welcome_and_audit_are_read_only_and_cannot_be_published(self):
        mirror=Mirror(Path(self.tmp.name)/'info-mirror',1,'hnah');self.addCleanup(mirror.close)
        manifest=self.legacy_manifest(self.host,self.gid)
        mirror.initialize_info(manifest['welcome'],self.store.history(self.host,self.gid))
        self.assertEqual((mirror.path/'welcome.md').stat().st_mode&0o777,0o400)
        self.assertIn('group_created',(mirror.path/'logs/activity.json').read_text())
        with self.assertRaises(Denied):mirror.upload('logs/activity.json',lambda *a:None,approved=True)
        with self.assertRaises(FileExistsError):mirror.initialize_info('new',[])

    def test_http_stream_rejects_unauthenticated_or_oversized_body_before_reading_it(self):
        import asyncio
        from unittest.mock import AsyncMock
        request=Requests(self.store,self.host,34443)
        async def attempt(authorization,size):
            reader=Mock()
            reader.readline=AsyncMock(side_effect=[b'PUT /v1/groups/anything/files HTTP/1.1\r\n',b'Host: 10.11.1.1:34443\r\n',('Authorization: '+authorization+'\r\n').encode(),('Content-Length: '+str(size)+'\r\n').encode(),b'\r\n'])
            reader.readexactly=AsyncMock()
            writer=Mock();writer.get_extra_info.side_effect=lambda key:{'peername':('10.11.1.1',9999),'sockname':('10.11.1.1',34443),'ssl_object':object()}[key]
            writer.wait_closed=AsyncMock()
            await request.handle(reader,writer)
            reader.readexactly.assert_not_called();writer.close.assert_called_once()
        asyncio.run(attempt('Bearer bad',1))
        asyncio.run(attempt('Bearer '+self.tokens['hnah'],MAX_FILE+1))

    def test_explicit_sync_pass_detects_file_drop_and_waits_for_other_members_approval(self):
        from campus_lan.file_sharing.controller import SyncSession
        self.join()
        host_mirror=Mirror(Path(self.tmp.name)/'host-mirror',1,'hnah');self.addCleanup(host_mirror.close)
        bob_mirror=Mirror(Path(self.tmp.name)/'bob-mirror',2,'dthoo');self.addCleanup(bob_mirror.close)
        host=SyncSession(self.store,self.host,self.gid,host_mirror)
        bob=SyncSession(self.store,self.bob,self.gid,bob_mirror)
        (bob_mirror.path/'dthoo').mkdir();(bob_mirror.path/'dthoo/funny.txt').write_bytes(b'uwu')
        bob.step(publish=False)
        self.assertFalse(self.legacy_manifest(self.host,self.gid)['files'])
        report=bob.step(publish=True);self.assertEqual(report['uploaded'],['dthoo/funny_dthoo_1.txt'])
        report=host.step();self.assertEqual(report['notices'][0].title,'🔊 uwu, dthoo sent you funny_dthoo_1.txt')
        self.assertFalse((host_mirror.path/'dthoo/funny_dthoo_1.txt').exists())
        version=next(iter(host.pending));host.accept(version)
        self.assertEqual((host_mirror.path/'dthoo/funny_dthoo_1.txt').read_bytes(),b'uwu')
        self.assertEqual(host.step()['notices'],[])

    def test_sync_decline_is_not_repeated_and_new_version_requires_new_approval(self):
        from campus_lan.file_sharing.controller import SyncSession
        self.join();first=self.store._put_history(self.bob,self.gid,'funny.txt',b'one')
        mirror=Mirror(Path(self.tmp.name)/'decline-mirror',1,'hnah');self.addCleanup(mirror.close)
        sync=SyncSession(self.store,self.host,self.gid,mirror)
        self.assertEqual(len(sync.step()['notices']),1);sync.decline(first['version'])
        self.assertEqual(sync.step()['notices'],[])
        self.store._put_history(self.bob,self.gid,'funny.txt',b'two',first['version'])
        self.assertEqual(len(sync.step()['notices']),1)
        with self.assertRaises(Denied):sync.accept(first['version'])

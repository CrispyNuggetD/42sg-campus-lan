"""Public flock: controlled campus evidence, private temporary folders, mocked GUI."""
import io
import json
import os
from pathlib import Path
import queue
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from campus_lan.auth import Broker,AuthError,digest
from campus_lan.client import Client
from campus_lan.file_sharing.runtime import Runtime
from campus_lan.file_sharing.client import Courier
from campus_lan.file_sharing.flock import FlockPreferences,fresh_folder
from campus_lan.file_sharing.security import Denied
from campus_lan.desktop_notifications import Notifications


class FlockTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp.name});env.start();self.addCleanup(env.stop)
        self.policy=Mock();self.policy.local_operator.return_value=1
        self.broker=Broker(Mock(),policy_factory=lambda:self.policy)
        self.api=Mock();self.members={1:True,2:True,3:False}
        def get(route):
            if route=='campus/64':return dict(id=64,name='Singapore')
            uid=int(route.split('/')[1])
            return dict(id=uid,login={1:'hnah',2:'dthoo',3:'other'}[uid],**{'active?':True},
                        campus_users=[dict(campus_id=64 if self.members[uid] else 99,is_primary=True)])
        self.api.get.side_effect=get
        self.api.pages.side_effect=lambda route,**kw:[dict(end_at=None,host='c1r1s'+str(kw['filter[user_id]']),user=dict(id=kw['filter[user_id]'],login={1:'hnah',2:'dthoo'}[kw['filter[user_id]']]))]
        self.runtime=Runtime(self.broker,'10.11.1.1',31416,api_factory=lambda:(self.api,64),root=self.root/'store',owner='hnah')
        self.addCleanup(lambda:self.runtime.close() if self.runtime.requests else None)
        self.runtime.start_public()
        self.token='2'*64
        self.broker.sessions[digest(self.token)]=dict(uid=2,login='dthoo',expires=time.time()+3600,sg_member=True,campus_id=64)

    def dispatch(self,method,target,data=None,peer='10.11.1.2',token=None):
        body=json.dumps(data).encode() if data is not None else b''
        headers={'host':'10.11.1.1:31416','authorization':'Bearer '+(token or self.token),
                 'content-length':str(len(body)),'content-type':'application/json'}
        return self.runtime.requests.dispatch(method,target,headers,body,peer,True,'10.11.1.1')

    def join(self):
        info=self.runtime.public_status()
        return self.dispatch('POST','/v1/flock/join',{k:info[k] for k in ('group','epoch')})

    def test_startup_has_no_student_bearer_or_folder_watch(self):
        self.assertIsNotNone(self.runtime.public_status())
        host=self.runtime.requests.host
        with self.assertRaises(AuthError):self.broker.authenticate(host.session_key)
        self.assertEqual(set(self.broker.sessions),{digest(self.token)})
        self.assertEqual(self.runtime.requests.store.db.execute('SELECT count(*) FROM versions').fetchone()[0],0)
        self.assertFalse((self.root/'KoelDrop').exists())
        self.policy.local_operator.assert_called_with(admin=True)

    def test_join_checks_sg_session_real_seat_and_current_epoch(self):
        info=self.runtime.public_status();gid=info['group']
        self.assertEqual(self.dispatch('GET','/v1/groups/'+gid+'/manifest').status,403)
        self.assertEqual(self.dispatch('POST','/v1/flock/join',dict(group=gid,epoch='0'*32)).status,409)
        self.assertEqual(self.dispatch('POST','/v1/flock/join',dict(group=gid,epoch=info['epoch']),peer='10.11.1.9').status,403)
        self.assertEqual(self.dispatch('POST','/v1/flock/join',dict(group=gid,epoch=info['epoch']),peer='127.0.0.1').status,403)
        self.assertEqual(self.join().status,200)
        self.assertEqual(self.dispatch('GET','/v1/groups/'+gid+'/manifest').status,200)
        self.assertEqual(self.dispatch('POST','/v1/flock/join',dict(group=gid,epoch=info['epoch']),token='9'*64).status,403)
        self.broker.sessions[digest('3'*64)]=dict(uid=3,login='other',expires=time.time()+3600,sg_member=True,campus_id=64)
        self.assertEqual(self.dispatch('POST','/v1/flock/join',dict(group=gid,epoch=info['epoch']),token='3'*64,peer='10.11.1.3').status,403)
        for call in self.api.pages.call_args_list:self.assertEqual(call.args[0],'campus/64/locations')

    def test_restart_retains_host_files_but_resets_membership_and_epoch(self):
        info=self.runtime.public_status();gid=info['group'];self.assertEqual(self.join().status,200)
        gate=self.runtime.requests.store.gate;actor=gate.admit(self.token,'10.11.1.2',True)
        self.runtime.requests.store.put(actor,gid,'dthoo/kept.txt',b'keep me')
        self.runtime.close();self.runtime.start_public()
        current=self.runtime.public_status()
        self.assertEqual(current['group'],gid);self.assertNotEqual(current['epoch'],info['epoch'])
        self.assertFalse(gate.running)
        self.assertEqual(self.dispatch('GET','/v1/groups/'+gid+'/manifest').status,403)
        self.assertEqual(self.join().status,200)
        manifest=json.loads(self.dispatch('GET','/v1/groups/'+gid+'/manifest').body)
        self.assertEqual(manifest['files'][0]['path'],'dthoo/kept.txt')
        self.assertEqual(self.runtime.requests.store.db.execute('SELECT count(*) FROM groups').fetchone()[0],1)

    def test_revocation_and_host_presence_fail_closed_without_deleting_files(self):
        info=self.runtime.public_status();self.policy.local_operator.return_value=9
        self.assertEqual(self.join().status,403)
        self.policy.local_operator.return_value=1
        self.members[1]=False;self.runtime.requests.store.gate.proofs.cache.clear()
        self.assertEqual(self.join().status,403)
        self.assertTrue((self.root/'store'/'files.sqlite').exists())

    def test_host_user_leaving_does_not_close_the_service_flock(self):
        token='1'*64;self.broker.sessions[digest(token)]=dict(uid=1,login='hnah',expires=time.time()+3600,sg_member=True,campus_id=64)
        info=self.runtime.public_status();payload={k:info[k] for k in ('group','epoch')}
        self.assertEqual(self.dispatch('POST','/v1/flock/join',payload,peer='10.11.1.1',token=token).status,200)
        self.assertEqual(self.dispatch('POST','/v1/groups/'+info['group']+'/leave',{},peer='10.11.1.1',token=token).status,200)
        self.assertEqual(self.join().status,200)

    def test_existing_destinations_never_get_imported_renamed_or_erased(self):
        base=self.root/'chosen';old=base/'42-singapore';old.mkdir(parents=True)
        (old/'personal.txt').write_bytes(b'private')
        fp='a'*64;epoch='b'*32
        first=fresh_folder(base,fp,epoch);(first/'retained.txt').write_bytes(b'previous')
        second=fresh_folder(base,fp,epoch)
        self.assertNotEqual(first,second);self.assertEqual(list(second.iterdir()),[])
        self.assertEqual((first/'retained.txt').read_bytes(),b'previous')
        self.assertEqual((old/'personal.txt').read_bytes(),b'private')
        link=self.root/'linked';link.symlink_to(base,target_is_directory=True)
        with self.assertRaises(OSError):fresh_folder(link,fp,epoch)

    def test_courier_joins_fresh_folder_uploads_only_it_and_waits_for_receive_approval(self):
        from campus_lan.file_sharing.remote import RemoteStore
        fixture=self
        class Connection:
            def __init__(self,trust):pass
            def request(self,method,route,body,headers):
                normalized={k.lower():v for k,v in headers.items()};normalized['host']='10.11.1.1:31416'
                self.reply=fixture.runtime.requests.dispatch(method,route,normalized,body,'10.11.1.2',True,'10.11.1.1')
            def getresponse(self):
                reply=self.reply;stream=io.BytesIO(reply.body)
                return Mock(status=reply.status,read=stream.read,getheaders=lambda:list(reply.headers.items()))
            def close(self):pass
        info=self.runtime.public_status();base=self.root/'service';base.mkdir();(base/'personal.txt').write_bytes(b'never upload')
        worker=Courier(self.token,2,'dthoo',queue.Queue(),RemoteStore(self.token,dict(lobby_host='10.11.1.1')))
        self.addCleanup(lambda:worker.sync.mirror.close() if worker.sync else None)
        with patch('campus_lan.auth_client.PinnedHTTPSConnection',Connection):
            worker.perform('flock',(info['group'],'hnah',info['epoch'],str(base),'a'*64))
            store=self.runtime.requests.store
            self.assertEqual(store.db.execute('SELECT count(*) FROM versions').fetchone()[0],0)
            (worker.sync.mirror.path/'dthoo').mkdir()
            (worker.sync.mirror.path/'dthoo'/'upload.txt').write_bytes(b'public flock')
            worker.perform('sync',())
            store.put(self.runtime.requests.host,info['group'],'download.txt',b'needs approval')
            worker.perform('sync',())
            self.assertFalse((worker.sync.mirror.path/'download.txt').exists())
            worker.perform('receive',(next(iter(worker.sync.pending)),))
            folder=worker.sync.mirror.path;self.assertEqual((folder/'download.txt').read_bytes(),b'needs approval')
            worker.perform('leave',())
            self.assertTrue((folder/'download.txt').exists());self.assertIsNone(worker.sync)
            paths=[r['path'] for r in store.db.execute('SELECT path FROM versions')]
            self.assertNotIn('personal.txt',paths)


class FlockUITests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp.name});env.start();self.addCleanup(env.stop)
        campus=patch('campus_lan.auth_daily.current_seat',return_value='10.11.1.2');campus.start();self.addCleanup(campus.stop)
        self.c=Client.__new__(Client);self.c.role='lobby';self.c.secure=True;self.c.uid=2
        self.c.lines=[];self.c.inbox=queue.Queue();self.c.courier=None;self.c.name='dthoo'
        self.c.tracking_notifier=Mock();self.c.start_signin=Mock()
        self.preferences=FlockPreferences('a'*64,2);self.preferences.save(base=str(self.root/'service'))
        self.c.flock_preferences=lambda:self.preferences
        self.c.important_notification_allowed=Mock(return_value=True)
        self.c.popup_prompts=Mock();self.worker=Mock();self.worker.sync=None;self.worker.join_pending=None
        self.c.koel_worker=Mock(return_value=self.worker)
        self.info=dict(group='b'*32,epoch='c'*32,host='hnah',scope='42-singapore',campus_id=64)
        self.c.flock_info=self.info

    def test_click_always_requires_upload_and_directory_consent(self):
        c=self.c;c.flock_actions={'key':self.info}
        c.flock_notification_action(dict(action='flock_always',context='key'))
        self.worker.submit.assert_not_called();self.assertEqual(self.preferences.mode,'ask')
        description,accept=c.popup_prompts().confirm.call_args.args
        self.assertIn('Incoming files and deletions need separate approval',description)
        self.assertIn('never reused, renamed or erased',description)
        accept();self.worker.submit.assert_called_once_with('flock','b'*32,'hnah','c'*32,str(self.root/'service'),'a'*64)
        self.assertEqual(FlockPreferences('a'*64,2).mode,'always')

    def test_always_rejoins_without_reasking_but_does_not_replace_private_group(self):
        c=self.c;self.preferences.save(mode='always')
        c.flock_status(dict(flock=self.info));c.flock_status(dict(flock=self.info))
        self.worker.submit.assert_called_once();c.popup_prompts().confirm.assert_not_called()
        c.flock_attempt=None;c.courier=Mock(sync=object(),flock_epoch=None,join_pending=None)
        c.flock_status(dict(flock=self.info));self.assertEqual(self.worker.submit.call_count,1)
        self.assertIn('Another KoelDrop group',' '.join(c.lines))

    def test_guest_click_requests_signin_not_a_join(self):
        c=self.c;c.secure=False;c.flock_join('once')
        c.start_signin.assert_called_once();self.worker.submit.assert_not_called()
        self.assertEqual(c.pending_flock_choice['mode'],'once')
        c.secure=True;c.flock_status(dict(flock=self.info))
        self.assertIsNone(c.pending_flock_choice);c.popup_prompts().confirm.assert_called_once()

    def test_never_is_persistent_and_notification_is_deduplicated(self):
        c=self.c
        with patch('campus_lan.auth_daily.current_seat',return_value='10.11.1.2'),patch('campus_lan.announcement_client.claim',return_value=True):
            c.flock_status(dict(flock=self.info));c.flock_status(dict(flock=self.info))
        c.tracking_notifier.flock.assert_called_once()
        c.flock_command('flock',['never']);self.assertEqual(FlockPreferences('a'*64,2).mode,'never')
        c.flock_seen=None;c.flock_status(dict(flock=self.info));self.assertEqual(c.tracking_notifier.flock.call_count,1)
        c.flock_command('flock',['ask']);self.assertEqual(FlockPreferences('a'*64,2).mode,'ask')

    def test_host_shutdown_stops_public_worker_and_keeps_directory(self):
        c=self.c;c.courier=Mock(flock_epoch='c'*32);worker=c.courier
        folder=self.root/'kept';folder.mkdir();(folder/'file.txt').write_bytes(b'keep')
        c.flock_status(None);worker.stop.assert_called_once();self.assertIsNone(c.courier)
        self.assertEqual((folder/'file.txt').read_bytes(),b'keep')
        self.assertIn('local folder and downloads are kept',' '.join(c.lines))

    def test_offline_while_join_pending_stops_it_and_allows_later_retry(self):
        c=self.c;c.courier=Mock(sync=None,flock_epoch=None,join_pending='flock');worker=c.courier
        c.flock_attempt=self.info['epoch']
        c.flock_status(None)
        worker.stop.assert_called_once();self.assertIsNone(c.flock_attempt);self.assertIsNone(c.courier)

    def test_invitation_channel_mute_does_not_open_native_prompt(self):
        c=self.c;c.important_notification_allowed.return_value=False
        c.flock_status(dict(flock=self.info))
        c.tracking_notifier.flock.assert_not_called()
        self.assertIn('/koel flock once',' '.join(c.lines))

    def test_stale_or_forged_local_action_cannot_join(self):
        c=self.c;c.flock_notification_action(dict(action='flock_once',context='forged'))
        self.worker.submit.assert_not_called();c.popup_prompts().confirm.assert_not_called()
        c.flock_actions={'old':dict(self.info,epoch='d'*32)}
        c.flock_notification_action(dict(action='flock_always',context='old'))
        c.popup_prompts().confirm.assert_not_called()

    def test_native_choices_are_local_and_mac_result_is_not_shell_code(self):
        n=Notifications.__new__(Notifications);n.show=Mock();n.inbox=queue.Queue()
        with patch('sys.platform','linux'):n.flock('title','body','ctx')
        self.assertEqual(set(n.show.call_args.kwargs['custom_actions']),{'flock_once','flock_always','flock_never'})
        with patch('sys.platform','darwin'),patch('campus_lan.desktop_notifications.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target)),patch('campus_lan.desktop_notifications.subprocess.run',return_value=Mock(stdout='2')) as run:
            n.flock('title','body','ctx')
        self.assertEqual(n.inbox.get_nowait()['action'],'flock_never')
        self.assertNotIn('shell',run.call_args.kwargs)

    def test_full_upload_and_retention_disclosure_is_visible_in_small_terminal(self):
        c=self.c;c.flock_join('always')
        description=c.popup_prompts().confirm.call_args.args[0]
        c.permission_prompt=True;c.popup_prompts().active=('notifications',description,Mock(),'decision')
        class Screen:
            def __init__(self):self.rows={}
            def getmaxyx(self):return 28,76
            def addnstr(self,y,x,text,n,attr):
                assert 0<=y<28 and 0<=x<76
                self.rows[y]=text[:n]
        screen=Screen();c.draw_permission_prompt(screen)
        visible=' '.join(' '.join(screen.rows[y].split()) for y in sorted(screen.rows))
        self.assertIn('remain on the host across restarts',visible)
        self.assertIn('never reused, renamed or erased',visible)
        self.assertIn('until you remove them yourself',visible)
        self.assertIn('[y/N] Enter = no',visible)

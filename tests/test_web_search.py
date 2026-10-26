import hashlib
import json
import os
from pathlib import Path
import queue
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
from campus_lan.auth import AuthError,private_read,private_write
from campus_lan.client import Client
from campus_lan.local_console import History
from campus_lan.search_counts import SearchCounts
from campus_lan.web_search import SearchSettings,custom_template


class SearchTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp.name});env.start();self.addCleanup(env.stop)

    def report(self,counts,query,event,source='peer'):
        return counts.dispatch('/search/report',dict(fingerprint=hashlib.sha256(query.encode()).hexdigest(),event=format(event,'032x')),source)

    def test_permanent_aggregates_repeats_and_no_history_schema(self):
        c=SearchCounts(self.root);self.report(c,'query one',1);self.report(c,'query one',2)
        self.report(c,'query two',3);self.report(c,'query two',3)
        self.assertEqual(c.summary()['ecosia_total'],3);self.assertEqual(c.summary()['ecosia_unique_estimate'],2)
        self.assertEqual(c.db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall(),[('aggregate',)])
        self.assertEqual([r[1] for r in c.db.execute('PRAGMA table_info(aggregate)')],['id','total','sketch'])
        c.close();c=SearchCounts(self.root);self.addCleanup(c.close)
        self.assertEqual(c.summary()['ecosia_total'],3);self.assertEqual(c.summary()['ecosia_unique_estimate'],2)
        blob=(self.root/'search-counts.sqlite').read_bytes()
        self.assertNotIn(b'query one',blob);self.assertNotIn(hashlib.sha256(b'query one').hexdigest().encode(),blob)
        self.assertEqual(os.stat(self.root/'search-counts.sqlite').st_mode&0o777,0o600)

    def test_unique_estimate_and_bounded_storage(self):
        c=SearchCounts(self.root);self.addCleanup(c.close)
        for i in range(1000):self.report(c,'query '+str(i),i,source=str(i//20))
        self.assertEqual(c.summary()['ecosia_total'],1000)
        self.assertLess(abs(c.summary()['ecosia_unique_estimate']-1000),100)
        self.assertEqual(c.db.execute('SELECT length(sketch) FROM aggregate').fetchone()[0],4096)

    def test_malformed_identified_and_rate_limited_reports_do_not_count(self):
        c=SearchCounts(self.root);self.addCleanup(c.close)
        with self.assertRaises(AuthError):c.dispatch('/search/report',dict(session='secret',fingerprint='a'*64,event='b'*32))
        with self.assertRaises(AuthError):c.dispatch('/search/report',dict(fingerprint='raw query',event='b'*32))
        for i in range(30):self.report(c,'one',i)
        with self.assertRaises(AuthError):self.report(c,'one',31)
        self.assertEqual(c.summary()['ecosia_total'],30)

    def test_anonymous_http_report_has_no_provider_or_identity_lookup(self):
        import asyncio
        from campus_lan.auth import AuthHTTP,Broker
        counts=SearchCounts(self.root);self.addCleanup(counts.close)
        provider=Mock();broker=Broker(provider);http=AuthHTTP(broker,'host:31416');http.search_counts=counts
        payload=json.dumps(dict(fingerprint='a'*64,event='b'*32)).encode()
        class Writer:
            def __init__(self):self.data=b''
            def write(self,data):self.data+=data
            async def drain(self):pass
            def close(self):pass
            async def wait_closed(self):pass
            def get_extra_info(self,key):return ('10.11.1.2',1234) if key=='peername' else None
        async def request():
            reader=asyncio.StreamReader();writer=Writer()
            reader.feed_data(b'POST /search/report HTTP/1.1\r\nHost: host:31416\r\nContent-Type: application/json\r\nContent-Length: '+str(len(payload)).encode()+b'\r\n\r\n'+payload);reader.feed_eof()
            await http.handle(reader,writer);return writer.data
        response=asyncio.run(request())
        self.assertTrue(response.startswith(b'HTTP/1.1 200'))
        self.assertEqual(counts.summary()['ecosia_total'],1);provider.identify.assert_not_called()
        self.assertEqual(broker.sessions,{})

    def test_losing_key_does_not_reset_or_rekey_existing_totals(self):
        c=SearchCounts(self.root);self.report(c,'kept',1);c.close()
        (self.root/'search-counts.key').unlink()
        with self.assertRaises(AuthError):SearchCounts(self.root)
        self.assertTrue((self.root/'search-counts.sqlite').exists())
        self.assertFalse((self.root/'search-counts.key').exists())

    def client(self):
        c=Client.__new__(Client);c.lines=[];c.inbox=queue.Queue();c.popup_prompts=Mock()
        c.popup_prompts().permissions.mode.return_value='allow'
        c.request_popup=lambda category,description,action:action()
        return c

    def sync_thread(self):
        return patch('campus_lan.web_search.threading.Thread',side_effect=lambda target,daemon:SimpleNamespace(start=target))

    def test_fallback_opens_first_and_reports_no_raw_query_or_identity(self):
        c=self.client();order=[]
        with self.sync_thread(),patch('webbrowser.open_new_tab',side_effect=lambda url:order.append('browser') or True),patch('campus_lan.auth_client.load_trust',return_value={}),patch('campus_lan.auth_client.post',side_effect=lambda *a:order.append('report') or (_ for _ in ()).throw(OSError())) as post:
            c.search_command('/search privacy test')
        self.assertEqual(order,['browser','report'])
        payload=post.call_args.args[2]
        self.assertEqual(set(payload),{'fingerprint','event'})
        self.assertNotIn('privacy test',json.dumps(payload))
        result=c.inbox.get_nowait();self.assertIn('Opened without a host-recorded count',' '.join(result['lines']))

    def test_opt_out_and_browser_failure_never_report(self):
        c=self.client();c.search_command('/settings search counting off')
        with self.sync_thread(),patch('webbrowser.open_new_tab',return_value=True),patch('campus_lan.auth_client.post') as post:
            c.search_command('/key4');post.assert_not_called()
        settings=SearchSettings();settings.counting=True;settings.save()
        with self.sync_thread(),patch('webbrowser.open_new_tab',return_value=False),patch('campus_lan.auth_client.post') as post:
            c.search_command('/search no launch');post.assert_not_called()

    def test_google_switch_confirms_once_and_declining_keeps_ecosia(self):
        c=self.client();c.search_command('/settings search google')
        self.assertEqual(SearchSettings().engine,'ecosia')
        c.popup_prompts().confirm.call_args.args[1]()
        self.assertEqual(SearchSettings().engine,'google')
        c.search_command('/settings search google');self.assertEqual(c.popup_prompts().confirm.call_count,1)

    def test_custom_template_and_safe_query_encoding(self):
        for url in ('javascript:alert(1)','http://example.com/?q={query}','https://{query}.example.com/','https://user:password@example.com/?q={query}'):
            with self.assertRaises(ValueError):custom_template(url)
        c=self.client();c.search_command('/settings search custom https://example.com/search?q={query}')
        self.assertEqual(SearchSettings().url('two words & more'),'https://example.com/search?q=two+words+%26+more')

    def test_search_queries_are_excluded_from_persistent_history(self):
        history=History();history.add('/search sensitive words');history.add('/key4');history.add('/settings search counting off');history.add('/who')
        self.assertEqual(json.loads(private_read(history.path)),['/who'])
        private_write(history.path,json.dumps(['/search legacy query','/who']))
        history=History();self.assertEqual(json.loads(private_read(history.path)),['/who'])

    def test_f4_never_searches_automatically_but_discovered_link_does(self):
        c=self.client();c.volume_command=Mock();c.search_command=Mock()
        c.quick_action('volume');c.quick_action('volume')
        c.search_command.assert_not_called();self.assertEqual(len(c.lines),1)
        class Screen:
            def getmaxyx(self):return 28,76
        c.line=Mock();c.draw_quick_controls(Screen())
        row,left,right,action=next(hit for hit in c.control_hits if hit[3]=='key4')
        self.assertLessEqual(right,75);c.quick_click(left,row)
        c.search_command.assert_called_once_with('/key4')

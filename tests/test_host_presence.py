import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock,Mock,patch
from campus_lan import clusters
from campus_lan.auth import AuthError,config_dir
from campus_lan.auth_server import prime_campus_presence,maintain_campus_presence
from campus_lan.campus_status import publish_status


class HostPresence(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        p=patch.dict(os.environ,{'XDG_CONFIG_HOME':temp.name});p.start();self.addCleanup(p.stop)

    async def test_startup_fetches_only_after_host_approval_and_publishes_counts_only(self):
        order=[];api=Mock()
        api.pages.return_value=[dict(id=1,host='c1r1s1',end_at=None,user={'login':'fixture-one'}),dict(id=2,host='c2r1s1',end_at=None,user={'login':'fixture-two'})]
        def factory():order.append('api');return api
        with patch('campus_lan.access.Policy.require_host',side_effect=lambda:order.append('approval')),patch.object(clusters,'API',side_effect=factory),patch.object(clusters,'_snapshot',None),patch.object(clusters,'_stamp',0):
            self.assertTrue(await prime_campus_presence())
            self.assertEqual(len(clusters.cached_snapshot()[0]),2)
        self.assertEqual(order,['approval','api'])
        api.pages.assert_called_once_with('campus/64/locations',**{'filter[active]':'true'})
        path=config_dir()/'campus-status.json';status=json.loads(path.read_text())
        self.assertEqual((status['total'],status['c1'],status['c2']),(2,1,1))
        self.assertEqual(set(status),{'total','c1','c2','updated_at'});self.assertEqual(path.stat().st_mode&0o777,0o600)

    async def test_unapproved_host_does_not_fetch_or_write(self):
        with patch('campus_lan.access.Policy.require_host',side_effect=AuthError('denied')),patch.object(clusters,'snapshot') as fetch:
            self.assertFalse(await prime_campus_presence());fetch.assert_not_called()
        self.assertFalse((config_dir()/'campus-status.json').exists())

    async def test_failure_preserves_last_success_and_does_not_print_exception(self):
        previous=[dict(name='fixture-user',seat='c1r1s1')]
        publish_status(dict(total=1,c1=1,c2=0,updated_at=1));path=config_dir()/'campus-status.json';before=path.read_bytes()
        api=Mock();api.pages.side_effect=OSError('private-fixture-detail')
        with patch('campus_lan.access.Policy.require_host'),patch.object(clusters,'API',return_value=api),patch.object(clusters,'_snapshot',previous),patch.object(clusters,'_stamp',1),patch('builtins.print') as output:
            self.assertFalse(await prime_campus_presence())
            self.assertEqual(clusters.cached_snapshot(),(previous,1))
            self.assertNotIn('private-fixture-detail',str(output.call_args))
        self.assertEqual(path.read_bytes(),before)

    async def test_maintenance_seeds_immediately_then_refreshes_once_per_minute(self):
        with patch('campus_lan.auth_server.prime_campus_presence',new_callable=AsyncMock,return_value=True) as prime,patch('campus_lan.auth_server.asyncio.sleep',new_callable=AsyncMock,side_effect=[None,asyncio.CancelledError]) as sleep:
            with self.assertRaises(asyncio.CancelledError):await maintain_campus_presence()
        self.assertEqual(prime.await_count,2);self.assertEqual([c.args[0] for c in sleep.call_args_list],[60,60])

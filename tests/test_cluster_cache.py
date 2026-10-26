"""All clients in one host process share occupancy refreshes, including cold starts."""
from concurrent.futures import ThreadPoolExecutor
import threading
import unittest
from unittest.mock import Mock,patch
from campus_lan import clusters

class ClusterCache(unittest.TestCase):
    def test_ten_concurrent_clients_share_one_refresh_then_expire_together(self):
        record=dict(id=1,host='c1r1s1',end_at=None,user={'login':'fixture'})
        api=Mock();api.pages.return_value=[record]
        barrier=threading.Barrier(10)
        def client(_):
            barrier.wait(timeout=5)
            return clusters.snapshot()
        with patch.object(clusters,'_snapshot',None),patch.object(clusters,'_stamp',0),patch.object(clusters,'API',return_value=api) as factory,patch.object(clusters.time,'time',return_value=100) as clock:
            with ThreadPoolExecutor(max_workers=10) as pool:results=list(pool.map(client,range(10)))
            factory.assert_called_once()
            api.pages.assert_called_once_with('campus/64/locations',**{'filter[active]':'true'})
            self.assertTrue(all(value[0] is results[0][0] and value[1]==100 for value in results))
            clock.return_value=129
            self.assertIs(clusters.snapshot()[0],results[0][0]);self.assertEqual(api.pages.call_count,1)
            clock.return_value=130
            api.pages.return_value=[dict(record,host='c2r2s2')]
            refreshed,stamp=clusters.snapshot()
            self.assertEqual(api.pages.call_count,2);self.assertEqual(stamp,130)
            self.assertEqual(refreshed[0]['seat'],'c2r2s2')

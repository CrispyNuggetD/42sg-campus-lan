import queue
import unittest
from unittest.mock import Mock,patch

from campus_lan.cluster_viewer import ClusterViewer,age_label,source_for


class ClusterViewerTests(unittest.TestCase):
    def viewer(self):
        source=Mock()
        source.label='Pinned host API'
        return ClusterViewer(source,queue.Queue()),source

    def test_refresh_aliases_keep_source_age_visible_and_do_not_touch_hq(self):
        viewer,source=self.viewer()
        viewer.command('/c1')
        source.refresh.assert_called_once_with(1)
        viewer.events.put(dict(type='clusters',players=[dict(name='fixture',seat='c1r1s1')],updated_at=100,cluster=1))
        viewer.consume()
        self.assertIn('35s ago',viewer.heading(135))
        self.assertIn('stale · 2m 1s ago',viewer.heading(221))
        self.assertIn('fixture','\n'.join(viewer.rows()))
        viewer.command('/clusters');source.refresh.assert_called_with(0)
        viewer.command('/c2');source.refresh.assert_called_with(2)
        viewer.command('r');source.refresh.assert_called_with(2)
        self.assertEqual(age_label(0),'no snapshot yet')

    def test_failed_refresh_retains_last_snapshot_and_reports_error(self):
        viewer,source=self.viewer()
        viewer.events.put(dict(type='clusters',players=[dict(name='fixture',seat='c2r2s2')],updated_at=100,cluster=2))
        viewer.consume()
        viewer.events.put(dict(type='event',text='Campus seats unavailable. Retry later.'))
        viewer.consume()
        self.assertEqual(viewer.players[0]['name'],'fixture')
        self.assertIn('unavailable',viewer.status)
        viewer.command('/locate fixture')
        self.assertEqual(viewer.cluster,2)
        self.assertIn('c2r2s2',viewer.status)

    def test_numeric_tracking_requires_confirmation_of_captured_occupants(self):
        viewer,_=self.viewer();viewer.owner='fixture-owner'
        viewer.players=[dict(name='fixture',seat='c1r1s1')]
        viewer.command('/track 1')
        self.assertIn('fixture (c1r1s1)',viewer.status)
        with patch('campus_lan.tracking.Tracker') as tracker:
            viewer.command('y')
            tracker.assert_called_once_with('fixture-owner')
            tracker.return_value.change.assert_called_once_with(['fixture'])
        viewer.command('/track 1')
        viewer.players=[dict(name='other',seat='c1r1s1')]
        with patch('campus_lan.tracking.Tracker') as tracker:
            viewer.command('y')
            tracker.assert_not_called()
            self.assertIn('changed',viewer.status)

    def test_local_fallback_requires_approved_operator(self):
        events=queue.Queue()
        with patch('campus_lan.cluster_viewer.HostSource',side_effect=ValueError('host unavailable')),patch('campus_lan.cluster_viewer.LocalSource') as local:
            self.assertIs(source_for(events,'fixture'),local.return_value)
        with patch('campus_lan.cluster_viewer.HostSource',side_effect=ValueError('host unavailable')),patch('campus_lan.cluster_viewer.LocalSource',side_effect=ValueError('operator denied')):
            with self.assertRaisesRegex(ValueError,'host unavailable'):source_for(events,'fixture')

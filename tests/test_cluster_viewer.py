import contextlib
import io
import queue
import threading
import unittest
from types import SimpleNamespace
from unittest.mock import Mock,patch

from campus_lan import api_pacing
from campus_lan.cluster_viewer import ClusterViewer,LocalSource,age_label,launch,source_for


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

    def test_refresh_before_new_snapshot_reports_cached_data_and_keeps_page(self):
        viewer,source=self.viewer()
        players=[dict(name='fixture',seat='c1r1s1')]
        viewer.events.put(dict(type='clusters',players=players,updated_at=100,cluster=0))
        viewer.consume()
        viewer.page=2
        viewer.command('')
        source.refresh.assert_called_once_with(0)
        viewer.events.put(dict(type='clusters',players=players,updated_at=100,cluster=0))
        viewer.consume()
        self.assertIn('No newer campus snapshot yet',viewer.status)
        self.assertEqual(viewer.page,2)

    def test_local_refresh_in_progress_reports_waiting(self):
        viewer,source=self.viewer()
        source.refresh.return_value=False
        viewer.command('')
        self.assertIn('already in progress',viewer.status)
        local=LocalSource.__new__(LocalSource)
        local.busy=True
        self.assertIs(local.refresh(0),False)

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

    def test_local_api_notice_stays_inside_cluster_curses_screen(self):
        source=Mock();source.label='Local approved API'
        output=io.StringIO()
        def render(run):
            worker=threading.Thread(target=api_pacing.report,args=('[LAN42] API queued: waiting 0.24s',))
            worker.start();worker.join()
            viewer=run.__self__
            viewer.consume()
            self.assertIn('API queued',viewer.status)
        with patch('campus_lan.cluster_viewer.source_for',return_value=source),patch('campus_lan.cluster_viewer.pwd.getpwuid',return_value=SimpleNamespace(pw_name=None)),patch('campus_lan.cluster_viewer.signal.signal'),patch('campus_lan.cluster_viewer.curses.wrapper',side_effect=render),contextlib.redirect_stdout(output):
            launch()
        self.assertEqual(output.getvalue(),'')
        source.close.assert_called_once()

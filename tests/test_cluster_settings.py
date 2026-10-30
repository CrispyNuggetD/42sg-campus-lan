import tempfile
import os
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from campus_lan.client import Client
from campus_lan.cluster_settings import ClusterSettings


class ClusterSettingsTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':tmp.name})
        env.start();self.addCleanup(env.stop)

    def test_auto_open_is_saved_per_user_and_runs_once_after_hq_connects(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.cluster_settings.config_dir',return_value=Path(tmp)):
            choice=ClusterSettings('fixture')
            self.assertFalse(choice.read())
            choice.set(True)
            self.assertTrue(ClusterSettings('fixture').read())
            self.assertFalse(ClusterSettings('other').read())
            client=Client.__new__(Client)
            client.name='fixture';client.role='lobby';client.id=None;client.connected=True;client.signed_in=True
            client.clusters_auto_open_checked=False;client.open_clusters=Mock()
            client.clusters_auto_open_tick();client.open_clusters.assert_not_called()
            client.id='1';client.clusters_auto_open_tick();client.clusters_auto_open_tick()
            client.open_clusters.assert_called_once_with('/clusters',approved=True)
            client.lines=[]
            with patch.object(client,'quiet_command',return_value=False),patch.object(client,'search_command',return_value=False),patch.object(client,'notification_command',return_value=False),patch.object(client,'host_settings_command',return_value=False):
                self.assertTrue(client.settings_command('/settings clusters-auto-open off'))
            self.assertIn('off',client.lines[-1])
            choice.set(False)
            self.assertFalse(ClusterSettings('fixture').read())


    def test_auto_open_waits_for_signin_and_retries_failed_launches(self):
        from campus_lan.auth import AuthError
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.cluster_settings.config_dir',return_value=Path(tmp)), \
             patch('campus_lan.cluster_settings.ClusterSettings.read',return_value=True), \
             patch('campus_lan.popup_permissions.Permissions.persistent_mode',return_value='allow'), \
             patch('campus_lan.access.Policy.local_operator',side_effect=AuthError('not operator')), \
             patch('campus_lan.client.time.monotonic',return_value=100) as now:
            c=Client.__new__(Client);c.name='fixture';c.role='lobby';c.id='ready';c.connected=True;c.signed_in=False
            c.open_clusters=Mock()
            c.clusters_auto_open_tick();c.open_clusters.assert_not_called()
            self.assertFalse(getattr(c,'clusters_auto_open_checked',False))
            c.signed_in=True;now.return_value=106
            c.open_clusters.side_effect=lambda *a,**kw:setattr(c,'clusters_launch_ok',False)
            c.clusters_auto_open_tick();self.assertFalse(c.clusters_auto_open_checked)
            now.return_value=112
            c.open_clusters.side_effect=lambda *a,**kw:setattr(c,'clusters_launch_ok',True)
            c.clusters_auto_open_tick();c.clusters_auto_open_tick()
            self.assertTrue(c.clusters_auto_open_checked);self.assertEqual(c.open_clusters.call_count,2)

    def test_auto_open_honors_explicit_terminal_denial(self):
        with patch('campus_lan.cluster_settings.ClusterSettings.read',return_value=True), \
             patch('campus_lan.popup_permissions.Permissions.persistent_mode',return_value='deny'):
            c=Client.__new__(Client);c.name='fixture';c.role='lobby';c.id='ready';c.connected=True;c.signed_in=True
            c.open_clusters=Mock();c.clusters_auto_open_tick();c.open_clusters.assert_not_called()

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from campus_lan.client import Client
from campus_lan.cluster_settings import ClusterSettings


class ClusterSettingsTests(unittest.TestCase):
    def test_auto_open_is_saved_per_user_and_runs_once_after_hq_connects(self):
        with tempfile.TemporaryDirectory() as tmp,patch('campus_lan.cluster_settings.config_dir',return_value=Path(tmp)):
            choice=ClusterSettings('fixture')
            self.assertFalse(choice.read())
            choice.set(True)
            self.assertTrue(ClusterSettings('fixture').read())
            self.assertFalse(ClusterSettings('other').read())
            client=Client.__new__(Client)
            client.name='fixture';client.role='lobby';client.id=None;client.connected=True
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


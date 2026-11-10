"""Isolated preview tests: no desktop, real cache or network access."""
import unittest
from unittest.mock import Mock, patch
from campus_lan.cluster_photo import PhotoPreview, present


class PhotoPreviewTests(unittest.TestCase):
    def test_each_selection_raises_preview_without_stealing_keyboard_focus(self):
        root=Mock()
        present(root)
        present(root)
        self.assertEqual(root.attributes.call_count,2)
        root.attributes.assert_called_with('-topmost',True)
        self.assertEqual(root.deiconify.call_count,2)
        self.assertEqual(root.lift.call_count,2)
        root.focus_force.assert_not_called()
        root.grab_set.assert_not_called()

    @patch('campus_lan.cluster_photo.AvatarCache')
    @patch('campus_lan.cluster_photo.subprocess.Popen')
    def test_missing_photo_never_launches_or_fetches(self, launch, cache):
        cache.return_value.read.side_effect=FileNotFoundError
        report=Mock()
        preview=PhotoPreview(report)
        preview.show('fixture')
        launch.assert_not_called()
        cache.return_value.fetch.assert_not_called()
        report.assert_called_once_with('No existing local photo for fixture.')

    @patch('campus_lan.cluster_photo.threading.Thread')
    @patch('campus_lan.cluster_photo.AvatarCache')
    @patch('campus_lan.cluster_photo.subprocess.Popen')
    def test_reuses_one_process_and_closes_with_parent(self, launch, cache, thread):
        process=launch.return_value
        process.poll.return_value=None
        preview=PhotoPreview(Mock())
        preview.show('first')
        preview.show('second')
        launch.assert_called_once()
        self.assertEqual(process.stdin.write.call_count,2)
        cache.return_value.fetch.assert_not_called()
        preview.close()
        process.terminate.assert_called_once()
        process.wait.assert_called_once()

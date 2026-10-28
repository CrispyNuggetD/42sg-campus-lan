import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from campus_lan.file_sharing import desktop
from campus_lan.file_sharing.ui import KoelUI


class DesktopTests(unittest.TestCase):
    def test_gsettings_read(self):
        for value, expected in (("['files.desktop']", ['files.desktop']), ('@as []', [])):
            with patch.object(desktop.subprocess, 'run', return_value=SimpleNamespace(stdout=value)):
                self.assertEqual(desktop.favorites(), expected)

    def test_pin_preserves_favorites_and_writes_launcher_only_after_accept(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'XDG_DATA_HOME': root}), patch.object(desktop, 'supported', return_value=True), patch.object(desktop, 'favorites', side_effect=[['files.desktop'], ['files.desktop', 'new.desktop'], ['files.desktop', 'new.desktop', desktop.APP_ID]]), patch.object(desktop.subprocess, 'run') as run:
            desktop.add_favorite()
            self.assertEqual(run.call_args.args[0][-1], repr(['files.desktop', 'new.desktop', desktop.APP_ID]))
            content = (Path(root)/'applications'/desktop.APP_ID).read_text()
            self.assertIn('Name=KoelDrop', content)
            self.assertIn('--open', content)
            self.assertIn('Terminal=false', content)

    def test_existing_favorite_is_not_duplicated(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'XDG_DATA_HOME': root}), patch.object(desktop, 'supported', return_value=True), patch.object(desktop, 'favorites', return_value=[desktop.APP_ID]), patch.object(desktop.subprocess, 'run') as run:
            desktop.add_favorite()
            run.assert_not_called()

    def test_unavailable_settings_skip_startup(self):
        with patch.object(desktop, 'supported', return_value=True), patch.object(desktop, 'favorites', side_effect=subprocess.TimeoutExpired('gsettings', 3)):
            self.assertFalse(desktop.needs_favorite())

    def test_startup_and_manual_consent(self):
        ui = KoelUI();ui.lines=[];prompts=Mock();ui.popup_prompts=lambda:prompts
        with patch.object(desktop, 'supported', return_value=True), patch.object(desktop, 'needs_favorite', return_value=True), patch.object(desktop, 'add_favorite') as add:
            ui.koel_favorite(startup=True)
            add.assert_not_called()
            prompts.confirm.assert_called_once()
            ui.koel_favorite(startup=True)
            prompts.confirm.assert_called_once()
            prompts.confirm.call_args.args[1]()
            add.assert_called_once()
            self.assertTrue(ui.koel_command('/koel favorite'))
            self.assertEqual(prompts.confirm.call_count, 2)

    def test_no_prompt_when_pinned_or_not_supported(self):
        for supported, needed in ((True, False), (False, False)):
            ui=KoelUI();ui.lines=[];ui.popup_prompts=Mock()
            with patch.object(desktop, 'supported', return_value=supported), patch.object(desktop, 'needs_favorite', return_value=needed), patch.object(desktop, 'add_favorite') as add:
                ui.koel_favorite(startup=True)
                ui.popup_prompts.assert_not_called();add.assert_not_called()

    def test_desktop_exec_quoting(self):
        self.assertEqual(desktop.exec_quote('/tmp/Koel Drop%$'), '"/tmp/Koel Drop%%\\$"')


class BookmarkTests(unittest.TestCase):
    def test_preserves_locations_encodes_spaces_and_avoids_duplicates(self):
        with tempfile.TemporaryDirectory() as root, patch.dict('os.environ', {'XDG_CONFIG_HOME': root}), patch.object(desktop, 'bookmark_supported', return_value=True):
            target=Path(root)/'Koel Drop'
            path=desktop.bookmark_file();path.parent.mkdir(parents=True)
            original='file:///tmp/other Other location\nsmb://server/share Shared'
            path.write_text(original)
            self.assertFalse(desktop.bookmarked(target))
            desktop.add_bookmark(target)
            expected=original+'\n'+target.as_uri()+' KoelDrop\n'
            self.assertEqual(path.read_text(), expected)
            self.assertTrue(desktop.bookmarked(target))
            desktop.add_bookmark(target)
            self.assertEqual(path.read_text(), expected)
            self.assertFalse(target.exists())

    def test_sidebar_confirmation_is_independent_of_dock(self):
        ui=KoelUI();ui.lines=[];prompts=Mock();ui.popup_prompts=lambda:prompts
        with patch.object(desktop, 'bookmark_supported', return_value=True), patch.object(desktop, 'bookmarked', return_value=False), patch.object(desktop, 'add_bookmark') as add:
            ui.koel_bookmark(startup=True)
            add.assert_not_called()
            prompts.confirm.assert_called_once()
            self.assertIn('Files sidebar', prompts.confirm.call_args.args[0])
            ui.koel_bookmark(startup=True)
            prompts.confirm.assert_called_once()
            prompts.confirm.call_args.args[1]()
            add.assert_called_once()
            self.assertTrue(ui.koel_command('/koel bookmark'))
            self.assertTrue(ui.koel_command('/koel sidebar'))

    def test_already_bookmarked_skips_prompt(self):
        ui=KoelUI();ui.lines=[];ui.popup_prompts=Mock()
        with patch.object(desktop, 'bookmark_supported', return_value=True), patch.object(desktop, 'bookmarked', return_value=True):
            ui.koel_bookmark(startup=True)
            ui.popup_prompts.assert_not_called()

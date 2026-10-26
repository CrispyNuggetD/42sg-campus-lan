import collections
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from campus_lan.koel_sound import SoundChoice,sound_hints,ASSET
from campus_lan.client import Client
from campus_lan.file_sharing.workflow import file_notice
from campus_lan.file_sharing.sync import Offer

class KoelSound(unittest.TestCase):
    def setUp(self):
        quiet=patch('campus_lan.audio_quiet.active',return_value=False);quiet.start();self.addCleanup(quiet.stop)
        volume_patch=patch('campus_lan.volume.Volume');volume=volume_patch.start();self.addCleanup(volume_patch.stop)
        volume.return_value.get.return_value=50
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        for target in ('campus_lan.koel_sound.config_dir','campus_lan.popup_permissions.config_dir'):
            patcher=patch(target,return_value=Path(temporary.name));patcher.start();self.addCleanup(patcher.stop)
        environment=patch.dict(os.environ,{'LAN42_POPUP_SESSION':'b'*32,'LAN42_POPUP_OWNER_PID':str(os.getpid())})
        environment.start();self.addCleanup(environment.stop)

    def client(self):
        c=Client.__new__(Client);c.name='hnah';c.role='lobby';c.connected=True;c.id='1';c.lines=collections.deque();c.input='';c.play=False
        return c

    def test_off_by_default_once_is_shared_for_launch_then_resets(self):
        choice=SoundChoice('hnah');self.assertEqual(choice.read(),dict(asked=False,enabled=False))
        choice.choose(True);self.assertTrue(SoundChoice('hnah').read()['enabled'])
        with patch.dict(os.environ,{'LAN42_POPUP_SESSION':'c'*32}):
            self.assertEqual(SoundChoice('hnah').read(),dict(asked=False,enabled=False))
        self.assertFalse(SoundChoice('other').read()['enabled'])

    def test_startup_ignores_general_always_allow_enter_still_means_off(self):
        c=self.client();c.popup_prompts().permissions.set('all','allow')
        c.sound_tick();c.permission_tick();self.assertEqual(c.popup_prompts().active[3],'session')
        c.permission_answer('');self.assertEqual(SoundChoice('hnah').read(),dict(asked=True,enabled=False))
        c.sound_tick();self.assertIsNone(c.popup_prompts().activate())

    def test_always_option_requires_the_separate_sure_question(self):
        c=self.client();c.sound_tick();c.permission_tick();c.permission_answer('a')
        self.assertFalse(SoundChoice('hnah').always_on());c.permission_tick()
        self.assertIn('Are you SURE?',c.popup_prompts().active[1])
        c.permission_answer('');self.assertFalse(SoundChoice('hnah').always_on())
        c.settings_command('/settings koel-sound always');c.permission_tick();c.permission_answer('y')
        self.assertTrue(SoundChoice('hnah').always_on())
        with patch.dict(os.environ,{'LAN42_POPUP_SESSION':'d'*32}):self.assertTrue(SoundChoice('hnah').read()['enabled'])
        c.settings_command('/settings koel-sound off');self.assertFalse(SoundChoice('hnah').always_on());self.assertFalse(SoundChoice('hnah').read()['enabled'])

    def test_uwu_asks_when_disabled_and_plays_only_after_accept(self):
        c=self.client()
        with patch('campus_lan.koel_sound.play') as play:
            self.assertTrue(c.uwu_command('/uwu'))
            play.assert_not_called()
            c.permission_tick();c.permission_answer('')
            play.assert_not_called()
            c.uwu_command('/uwu');c.permission_tick();c.permission_answer('y')
            play.assert_called_once()
            c.uwu_command('/uwu');self.assertEqual(play.call_count,2)

    def test_uwu_always_waits_for_separate_confirmation(self):
        c=self.client()
        with patch('campus_lan.koel_sound.play') as play:
            c.uwu_command('/uwu');c.permission_tick();c.permission_answer('a')
            play.assert_not_called()
            c.permission_tick();c.permission_answer('y')
            play.assert_called_once()
            self.assertTrue(SoundChoice('hnah').always_on())

    def test_asset_and_sound_hints_are_bounded_and_default_silent(self):
        self.assertTrue(ASSET.read_bytes().startswith(b'OggS'));self.assertLess(ASSET.stat().st_size,128*1024)
        self.assertEqual(sound_hints(None),{});self.assertEqual(sound_hints(False),{'suppress-sound':True})
        self.assertEqual(sound_hints(True),{'sound-file':str(ASSET),'suppress-sound':False})
        offer=Offer('dthoo/funny.txt','1'*32,'2'*64,5,2,'dthoo',False)
        notice=file_notice(offer,Path('/tmp/example'))
        self.assertEqual(notice.title,'🔊 uwu, dthoo sent you funny.txt');self.assertFalse(notice.koel_sound)

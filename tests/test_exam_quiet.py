"""Fake clocks, campus evidence and playback only. No notifications, volume or live API."""
import datetime as dt
import json
import os
import tempfile
import unittest
from unittest.mock import Mock,patch
from campus_lan import audio_quiet as audio
from campus_lan.exam_quiet import ExamQuiet,windows,stamp,utc
from campus_lan.release_notices import release,COALESCE,COOLDOWN
from campus_lan.auth import private_read
from campus_lan.client import Client
from campus_lan.campus_info import API


def at(value):return stamp(value)


class ExamQuietTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':temp.name});env.start();self.addCleanup(env.stop)
        self.now=at('2026-10-27T01:00:00Z');self.pin='a'*64

    def payload(self,start=None,end=None):
        return dict(schema=1,scope='lan42-audio',campus_id=64,issued=self.now,windows=[dict(start=start or self.now,end=end or self.now+10800,reason='exam')])

    def test_defaults_use_sgt_wednesday_and_every_saturday_even_offline(self):
        for day in ('2026-10-31','2026-11-07','2026-11-14'):
            self.assertTrue(audio.active(lambda:at(day+'T13:00:00+08:00')))
            self.assertFalse(audio.active(lambda:at(day+'T16:00:00+08:00')))
        self.assertTrue(audio.active(lambda:at('2026-10-28T15:00:00+08:00')))
        self.assertFalse(audio.active(lambda:at('2026-10-28T18:00:00+08:00')))

    def test_api_special_and_missing_end_use_three_hours_foreign_and_prep_rejected(self):
        rows=[dict(begin_at='2026-10-31T13:00:00+08:00',campus_id=64),dict(begin_at='2026-10-31T13:00:00+08:00',campus_id=1),dict(begin_at='$(rm -rf)',end_at='bad',campus_id=64)]
        result=windows(rows,True,self.now)
        self.assertEqual(result,[(at('2026-10-31T13:00:00+08:00'),at('2026-10-31T16:00:00+08:00'))])
        events=[dict(name='Saturday ✨Special✨ Exam 🇸🇬',kind='event',campus_id=64,begin_at='2026-10-31T13:00:00+08:00'),dict(name='Exam preparation workshop',kind='event',campus_id=64,begin_at='2026-10-31T13:00:00+08:00')]
        self.assertEqual(windows(events,False,self.now),result)

    def test_queued_special_survives_host_outage_and_completed_windows_are_removed(self):
        state=self.payload(self.now+3600,self.now+14400)
        self.assertTrue(audio.accept(state,self.pin,lambda:self.now))
        with patch('campus_lan.auth_client.load_trust',return_value={}),patch('campus_lan.auth_client.fingerprint',return_value=self.pin):
            self.assertFalse(audio.active(lambda:self.now+3500))
            self.assertTrue(audio.active(lambda:self.now+3700))
            self.assertFalse(audio.active(lambda:self.now+15000))
        stored=json.loads(private_read(audio.path()));self.assertEqual(stored['windows'],[])

    def test_injection_unknown_fields_bad_scope_overlong_and_replay_are_rejected(self):
        for change in (dict(command='rm -rf'),dict(scope='system-volume'),dict(issued=self.now-500)):
            self.assertFalse(audio.accept(dict(self.payload(),**change),self.pin,lambda:self.now))
        bad=self.payload();bad['windows'][0]['end']=self.now+13*3600
        self.assertFalse(audio.accept(bad,self.pin,lambda:self.now))
        bad=self.payload();bad['windows'][0]['reason']='$(sh malicious)'
        self.assertFalse(audio.accept(bad,self.pin,lambda:self.now))
        self.assertTrue(audio.accept(self.payload(),self.pin,lambda:self.now))
        older=self.payload();older['issued']-=1
        self.assertFalse(audio.accept(older,self.pin,lambda:self.now))

    def test_quiet_stops_clip_native_hints_and_even_previously_queued_volume_raise(self):
        from campus_lan.koel_sound import play,sound_hints
        c=Client.__new__(Client);c.lines=[];c.audio_volume_pending=False;c.popup_prompts=Mock()
        with patch('campus_lan.audio_quiet.active',return_value=False),patch('campus_lan.volume.Volume') as volume:
            volume.return_value.get.return_value=0;c.with_audio_volume(Mock())
            accept=c.popup_prompts().confirm.call_args.args[1]
            with patch('campus_lan.audio_quiet.active',return_value=True),patch('subprocess.Popen') as spawn:
                accept();play();self.assertEqual(sound_hints(None),{'suppress-sound':True})
                volume.return_value.set.assert_not_called();spawn.assert_not_called()

    def test_notices_at_30_minutes_start_and_end_without_history(self):
        notices=audio.QuietNotices();row=dict(start=3600,end=14400,reason='exam')
        self.assertEqual(len(notices.tick([row],1800)),1)
        self.assertEqual(notices.tick([row],1801),[])
        self.assertIn('active',' '.join(notices.tick([row],3600)))
        self.assertIn('ended',' '.join(notices.tick([],14400)))
        self.assertEqual(notices.seen,set())
        notices.tick([dict(start=20000,end=21000,reason='exam')],20000,audible=False)
        self.assertEqual(notices.tick([],21000,audible=False),[])

    def test_one_shared_bounded_weekly_fetch_and_partial_failure_keep_known_dates(self):
        api=Mock();api.get.side_effect=lambda route,**params:[dict(campus_id=64,begin_at='2026-10-31T13:00:00+08:00')] if route.endswith('exams') else []
        policy=Mock();service=ExamQuiet('10.11.1.1',lambda:api,lambda:policy,lambda:self.now)
        service.refresh();self.assertEqual(api.get.call_count,2)
        service.state();service.schedule();service.state();self.assertEqual(api.get.call_count,2)
        api.get.side_effect=lambda route,**params: (_ for _ in ()).throw(ValueError()) if route.endswith('exams') else []
        service.refresh();self.assertEqual(len(service.intervals),1)
        self.now=at('2026-11-01T00:00:00Z');self.assertEqual(service.state()['windows'],[])
        self.assertEqual(service.sources,{'exams':[],'events':[]})

    def test_calendar_allowlist_denies_global_other_campus_and_unbounded_range(self):
        from urllib.parse import urlencode
        api=API.__new__(API);api._members={}
        params={'range[begin_at]':utc(self.now-86400)+','+utc(self.now+7*86400),'page[number]':1,'page[size]':100}
        with patch('campus_lan.campus_info.time.time',return_value=self.now):
            api._validate_url('https://api.intra.42.fr/v2/campus/64/exams?'+urlencode(params),None,True)
            for route in ('exams','campus/1/exams','campus/64/events'):
                with self.assertRaises(ValueError):api._validate_url('https://api.intra.42.fr/v2/'+route,None,True)

    def test_only_numeric_configured_admin_can_publish_manual_mute_no_commands(self):
        from campus_lan.auth import Broker,digest,AuthError
        from campus_lan.announcements import Announcements
        broker=Broker(Mock(),clock=lambda:self.now);token='b'*64
        broker.sessions[digest(token)]=dict(uid=2,login='hnah',sg_member=True,campus_id=64,expires=self.now+3600)
        policy=Mock();policy.is_admin.return_value=False
        feed=Announcements(broker,'hnah',policy=policy);feed.exam_quiet=ExamQuiet('10.11.1.1',clock=lambda:self.now)
        with self.assertRaises(AuthError):feed.dispatch('/announcements/quiet',dict(session=token,minutes=60))
        policy.is_admin.return_value=True
        with patch('subprocess.Popen') as spawn,patch('subprocess.run') as run:
            self.assertEqual(feed.dispatch('/announcements/quiet',dict(session=token,minutes=60))['quiet']['windows'][0]['reason'],'manual')
            for minutes in ('rm -rf',True,721,-1):
                with self.assertRaises(AuthError):feed.dispatch('/announcements/quiet',dict(session=token,minutes=minutes))
            with self.assertRaises(AuthError):feed.dispatch('/announcements/quiet',dict(session=token,minutes=60,command='malicious'))
            spawn.assert_not_called();run.assert_not_called()


class ReleaseBudgetTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':temp.name});env.start();self.addCleanup(env.stop)
        self.now=1_800_000_000
    def step(self,version,silenced=False):return release(version,'date',silenced,lambda:self.now)
    def test_burst_coalesces_to_latest_then_rolling_24_hour_cooldown_survives_reload(self):
        self.assertEqual(self.step('2.0.0-beta.1'),(False,False))
        for i in range(1,6):self.now+=60;self.assertEqual(self.step('2.0.'+str(i)+'-beta.1'),(True,False))
        self.now+=COALESCE;self.assertEqual(self.step('2.0.5-beta.1'),(False,True))
        self.now+=60;self.step('2.0.6-beta.1');self.now+=COALESCE
        self.assertFalse(self.step('2.0.6-beta.1')[1])
        self.now+=COOLDOWN;self.assertTrue(self.step('2.0.6-beta.1')[1])
        self.assertFalse(self.step('2.0.6-beta.1')[1])
    def test_exam_quiet_defers_popup_without_losing_the_latest_pending_version(self):
        self.step('2.0.0');self.step('2.1.0');self.now+=COALESCE
        self.assertFalse(self.step('2.1.0',True)[1])
        self.assertTrue(self.step('2.1.0')[1])

    def test_host_restart_budget_is_shared_and_does_not_reset_with_a_new_host_epoch(self):
        from campus_lan.release_notices import reserve
        self.assertTrue(reserve('host-arrival-budget',900,lambda:self.now))
        for _ in range(5):
            self.now+=10;self.assertFalse(reserve('host-arrival-budget',900,lambda:self.now))
        self.now+=900;self.assertTrue(reserve('host-arrival-budget',900,lambda:self.now))

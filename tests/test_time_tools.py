from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from campus_lan.time_tools import (AmbiguousHour, Clocks, TimeControls, duration,
                                   wall_time, offset, alarm_timestamp)

SGT=timezone(timedelta(hours=8))
NOW=datetime(2026,10,30,12,0,tzinfo=SGT).timestamp()


class ClockTools(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        env=patch.dict(os.environ,{'XDG_CONFIG_HOME':self.temp.name})
        env.start();self.addCleanup(env.stop)
        self.clock=Clocks('fixture')

    def test_duration_clock_and_timezone_examples(self):
        self.assertEqual(duration('1h30m'),5400)
        self.assertEqual(wall_time('162532'),[16,25,32])
        self.assertEqual(wall_time('8pm'),[20,0,0])
        self.assertEqual(wall_time('12am'),[0,0,0])
        self.assertEqual(wall_time('12pm'),[12,0,0])
        with self.assertRaises(AmbiguousHour):wall_time('8')
        self.assertEqual(offset('+5:30'),330)
        for value in ('250000','126099','13pm'):
            with self.assertRaises(ValueError):wall_time(value)
        for value in ('0','-3m','3monkeys'):
            with self.assertRaises(ValueError):duration(value)

    def test_explicit_decimal_offsets_and_zulu(self):
        self.assertEqual(offset('+4.5'),270)
        self.assertEqual(offset('-3.5'),-210)
        self.assertEqual(offset('+0430'),270)
        for alias in ('Z','z','+Z','+z'):self.assertEqual(offset(alias),0)
        alarm=self.clock.add('alarm',['162121+4.5'],NOW)
        self.assertEqual(alarm['zone'],270)
        self.assertEqual(datetime.fromtimestamp(alarm['due'],SGT).strftime('%H:%M:%S'),'19:51:21')
        utc=self.clock.add('alarm',['162121Z'],NOW)
        self.assertEqual(utc['zone'],0)
        spaced=self.clock.add('alarm',['4:21:21','pm','+4.5'],NOW)
        self.assertEqual(spaced['clock'],[16,21,21])
        self.assertEqual(spaced['zone'],270)
        for alias in ('+Z','+z','z'):
            other=self.clock.add('alarm',['162121'+alias],NOW)
            self.assertEqual(other['due'],utc['due'])
        saved=json.loads(self.clock.path.read_text())
        self.assertTrue(all(a['due'].endswith('Z') for a in saved['alarms']))
        self.assertIn('2026-10-30T16:21:21Z',[a['due'] for a in saved['alarms']])
        ui=TimeControls();ui.name='offset-fixture';ui.role='lobby';ui.lines=[]
        with patch('campus_lan.time_tools.time.time',return_value=NOW):
            ui.time_command('/alarm 8+4.5')
            ui.time_command('pm')
        self.assertEqual(ui.clocks().load()['alarms'][0]['clock'],[20,0,0])
        self.assertEqual(ui.clocks().load()['alarms'][0]['zone'],270)

    def test_timestamp_storage_is_utc_but_default_view_is_sgt(self):
        explicit=self.clock.add('alarm',['162121+4.5'],NOW)
        self.assertEqual(alarm_timestamp(explicit),'2026-10-30 19:51:21 GMT+8')
        self.assertEqual(alarm_timestamp(explicit,0),'2026-10-30 11:51:21 UTC')
        utc=self.clock.add('alarm',['162121Z'],NOW)
        self.assertEqual(alarm_timestamp(utc),'2026-10-30 16:21:21 UTC')
        saved=json.loads(self.clock.path.read_text())
        self.assertTrue(all(a['due'].endswith('Z') for a in saved['alarms']))
        ui=TimeControls();ui.name='fixture';ui.role='lobby';ui.lines=[]
        ui.time_command('/clock display utc')
        self.assertEqual(ui.clocks().load()['display_offset'],0)
        ui.time_command('/clock display +4.5')
        self.assertEqual(ui.clocks().load()['display_offset'],270)
        self.assertEqual(alarm_timestamp(utc,270),'2026-10-30 20:51:21 GMT+4:30')
        ui.time_command('/clock display local')
        self.assertIsNone(ui.clocks().load()['display_offset'])

    def test_relative_alarm_and_compact_absolute_sgt(self):
        relative=self.clock.add('alarm',['30m','Tea'],NOW)
        self.assertEqual(relative['due'],NOW+1800)
        absolute=self.clock.add('alarm',['162532'],NOW)
        self.assertEqual(datetime.fromtimestamp(absolute['due'],SGT).isoformat(),'2026-10-30T16:25:32+08:00')
        self.assertEqual(self.clock.poll(NOW+1800)[0]['label'],'Tea')
        self.assertEqual(Clocks('fixture').poll(NOW+1800),[])
        self.assertEqual(Clocks('other').load()['alarms'],[])

    def test_recurrence_advances_without_replaying_missed_occurrences(self):
        interval=self.clock.add('alarm',['every','30m'],NOW)
        self.assertEqual(len(self.clock.poll(NOW+10*3600)),1)
        saved=next(a for a in self.clock.load()['alarms'] if a['id']==interval['id'])
        self.assertGreater(saved['due'],NOW+10*3600)
        daily=self.clock.add('alarm',['weekdays','08:00'],NOW)
        self.assertEqual(datetime.fromtimestamp(daily['due'],SGT).strftime('%a %H:%M'),'Mon 08:00')
        weekly=self.clock.add('alarm',['weekly','mon,fri','16:25'],NOW)
        self.assertEqual(datetime.fromtimestamp(weekly['due'],SGT).strftime('%a %H:%M'),'Fri 16:25')
        dated=self.clock.add('alarm',['on','2026-10-31','8pm'],NOW)
        self.assertEqual(datetime.fromtimestamp(dated['due'],SGT).strftime('%m-%d %H:%M'),'10-31 20:00')

    def test_timer_pause_resume_and_snooze(self):
        timer=self.clock.add('timer',['60'],NOW)
        self.clock.change('timer','pause',timer['id'],now=NOW+10)
        self.assertEqual(self.clock.poll(NOW+90),[])
        self.clock.change('timer','resume',timer['id'],now=NOW+100)
        self.assertEqual(self.clock.poll(NOW+149),[])
        self.assertEqual(len(self.clock.poll(NOW+150)),1)
        self.clock.change('timer','snooze',timer['id'],'5m',NOW+150)
        self.assertEqual(self.clock.poll(NOW+449),[])
        self.assertEqual(len(self.clock.poll(NOW+450)),1)

    def test_multiple_hq_instances_claim_each_alarm_once(self):
        self.clock.add('alarm',['1s'],NOW)
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda _:Clocks('fixture').poll(NOW+2),range(2)))
        self.assertEqual(sum(map(len,results)),1)

    def test_am_pm_question_and_stopwatch_use_no_real_notifications(self):
        ui=TimeControls();ui.name='fixture';ui.role='lobby';ui.lines=[];ui.desktop_notice=Mock()
        with patch('campus_lan.time_tools.time.time',return_value=NOW):
            ui.time_command('/alarm 08 Wake')
            self.assertFalse(ui.clocks().load()['alarms'])
            self.assertIn('am or pm',' '.join(ui.lines))
            ui.time_command('pm')
        alarm=ui.clocks().load()['alarms'][0]
        self.assertEqual(datetime.fromtimestamp(alarm['due'],SGT).hour,20)
        with patch('campus_lan.time_tools.time.monotonic',side_effect=[100,105,109,120]):
            ui.time_command('/stopwatch')
            ui.time_command('/stopwatch lap')
            ui.time_command('/stopwatch pause')
            ui.time_command('/stopwatch status')
        self.assertEqual(ui.stopwatch_state['elapsed'],9)
        self.assertEqual(ui.stopwatch_state['laps'],[5])
        ui.desktop_notice.assert_not_called()

    def test_bad_persisted_data_fails_closed(self):
        self.clock.add('alarm',['30m'],NOW)
        data=json.loads(self.clock.path.read_text());data['alarms'][0]['repeat']=1
        self.clock.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):self.clock.poll(NOW+3000)


class DueClockSound(unittest.TestCase):
    def test_due_timer_and_alarm_sound_once_without_replaying(self):
        from campus_lan.client import Client
        for kind in ('timer','alarm'):
            with self.subTest(kind=kind),patch('campus_lan.koel_sound.SoundChoice') as choice, \
                 patch('campus_lan.koel_sound.play') as play, \
                 patch('campus_lan.audio_quiet.active',return_value=False), \
                 patch('campus_lan.time_tools.time.monotonic',return_value=100) as now:
                c=Client.__new__(Client);c.name='fixture';c.role='lobby';c.lines=[]
                c.important_notification_allowed=Mock(return_value=True)
                c.tracking_notifier=Mock();c.with_audio_volume=Mock(side_effect=lambda action:action())
                clock=Mock();clock.poll.side_effect=[[dict(kind=kind,label='Tea',id='fixture')],[]]
                clock.load.return_value=dict(alarms=[],display_offset=None)
                c.clocks=Mock(return_value=clock);choice.return_value.read.return_value={'enabled':True}
                c.time_tick();now.return_value=102;c.time_tick()
                play.assert_called_once();c.tracking_notifier.announcement.assert_called_once()
                self.assertTrue(any('Tea' in line for line in c.lines))


if __name__=='__main__':unittest.main()

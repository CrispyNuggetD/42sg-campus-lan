import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from campus_lan.campus_info import directory,normalize,summarize,random_profiles,info_lines,render

class CampusInfo(unittest.TestCase):
    def test_directory_follows_sibling_private_repo_with_explicit_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            module=root/'lan42/campus_lan/campus_info.py'
            sibling=root/'42_Singapore_SUTD_hnah_private/42/data/campus'
            sibling.mkdir(parents=True)
            (sibling/'singapore.json').write_text('{}')
            with patch('campus_lan.campus_info.__file__',str(module)),patch.dict(os.environ,{'LAN42_CAMPUS_DATA':''}):
                self.assertEqual(directory(),sibling.resolve())
                with patch.dict(os.environ,{'LAN42_CAMPUS_DATA':str(root/'chosen')}):
                    self.assertEqual(directory(),root/'chosen')
                (sibling/'singapore.json').unlink()
                with patch('campus_lan.campus_info.Path.home',return_value=root):
                    self.assertEqual(directory(),root/'Documents/42_Singapore_SUTD_hnah_private/42/data/campus')

    def test_deadline_does_not_invent_blackhole_or_freeze_status(self):
        user=dict(id=1,login='fixture',**{'active?':False},cursus_users=[dict(cursus_id=21,begin_at='2025-11-17T00:00:00Z',blackholed_at='2020-01-01T00:00:00Z',end_at=None)])
        student=normalize(user)
        self.assertEqual(student['status'],'UNKNOWN');self.assertFalse(student['active'])
        self.assertIsNone(normalize(dict(id=2,login='pisciner',cursus_users=[dict(cursus_id=9)])))

    def test_batch_cohorts_do_not_number_isolated_transfers(self):
        students=[]
        for batch in range(2):
            for i in range(10):students.append(dict(id=batch*10+i,login='u'+str(batch*10+i),intake='2025-0'+str(batch+1)+'-01',status='UNKNOWN',active=True))
        students.append(dict(id=99,login='transfer',intake='2014-01-01',status='ALUMNI',active=False))
        data=summarize(dict(students=students))
        self.assertEqual([c['cohort'] for c in data['cohorts']],[1,2])
        self.assertEqual(data['unassigned_cohort_count'],1)
        self.assertIsNone(students[-1]['cohort'])

    def test_random_sabo_excludes_seated_and_is_distinct(self):
        with patch('campus_lan.campus_info.load',return_value={'students':[{'login':x} for x in ['hnah','one','two','three']]}):
            profiles=random_profiles(3,['HNAH'])
            self.assertEqual({p['login'] for p in profiles},{'one','two','three'})
            self.assertTrue(all(p['avatar'] is None for p in profiles))
            with self.assertRaises(ValueError):random_profiles(4,['hnah'])

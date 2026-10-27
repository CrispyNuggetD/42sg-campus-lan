"""Own-operator Singapore history only; fake provider and policy throughout."""
from datetime import datetime,timedelta,timezone
import unittest
from unittest.mock import Mock,patch
from urllib.parse import urlencode,urlsplit,parse_qs
from campus_lan.campus_info import API
from campus_lan.auth import AuthError

class Locations(unittest.TestCase):
    def api(self):
        api=API.__new__(API);api._members={}
        api.member_profile=Mock(return_value={'id':234449})
        return api

    def params(self):
        now=datetime.now(timezone.utc)
        return {'range[end_at]':(now-timedelta(days=7)).isoformat()+','+now.isoformat(),
                'sort':'-begin_at','page[number]':1,'page[size]':100,'filter[user_id]':234449}

    def test_routes_own_history_to_campus_endpoint(self):
        api=self.api();api.request=Mock(return_value=[])
        with patch('campus_lan.access.Policy') as policy:
            policy.return_value.local_operator.return_value=234449
            params=self.params();del params['filter[user_id]']
            self.assertEqual(api.get('users/hnah/locations',**params),[])
            url=api.request.call_args.args[0]
            self.assertEqual(urlsplit(url).path,'/v2/campus/64/locations')
            self.assertEqual(parse_qs(urlsplit(url).query)['filter[user_id]'],['234449'])
            api.member_profile.assert_called_once_with('hnah')
            api.member_profile.return_value={'id':2}
            with self.assertRaises(AuthError):api.get('users/other/locations',**params)
            self.assertEqual(api.request.call_count,1)
            with self.assertRaises(AuthError):api.get('users/hnah/locations',**params,**{'filter[user_id]':2})

    def test_history_allowlist_rejects_broad_or_foreign_reads(self):
        api=self.api()
        def validate(params):
            api._validate_url('https://api.intra.42.fr/v2/campus/64/locations?'+urlencode(params),None,True)
        with patch('campus_lan.access.Policy') as policy:
            policy.return_value.local_operator.return_value=234449
            valid=self.params();validate(valid)
            active=dict(valid);del active['range[end_at]'];active['filter[active]']='true';validate(active)
            for overrides in ({'filter[user_id]':2},{'page[number]':51},{'page[size]':1000},
                              {'sort':'begin_at'},{'filter[campus_id]':1},
                              {'range[end_at]':'2020-01-01T00:00:00Z,2026-01-01T00:00:00Z'}):
                with self.subTest(overrides=overrides),self.assertRaises((AuthError,ValueError)):
                    validate(dict(valid,**overrides))
            policy.return_value.local_operator.side_effect=AuthError('not enrolled')
            with self.assertRaises(AuthError):validate(valid)

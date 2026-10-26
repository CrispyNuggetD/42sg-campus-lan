import json
import unittest
from unittest.mock import Mock,patch
from campus_lan.profile_lookup import ProfileLookup
from campus_lan.auth import AuthError

class Lookup(unittest.IsolatedAsyncioTestCase):
    async def test_minimal_sg_profiles_cache_and_avatar_allowlist(self):
        api=Mock();api.member_profile.side_effect=[{'login':'thtay','email':'do-not-return','image':{'link':'https://cdn.intra.42.fr/thtay.jpg'}},{'login':'dthoo','image':{'link':'https://attacker.example/tracker'}}]
        with patch('campus_lan.campus_info.API',return_value=api):
            lookup=ProfileLookup(clock=lambda:100)
            profiles,errors=await lookup.lookup_many(['thtay','dthoo','thtay'])
            self.assertFalse(errors)
            self.assertEqual(profiles,[dict(login='thtay',avatar='https://cdn.intra.42.fr/thtay.jpg'),dict(login='dthoo',avatar=None)])
            self.assertEqual(api.member_profile.call_count,2)
            await lookup.lookup_many(['thtay']);self.assertEqual(api.member_profile.call_count,2)
            self.assertNotIn('do-not-return',json.dumps(profiles))

    async def test_invalid_input_and_concurrency_do_not_call_api(self):
        with patch('campus_lan.campus_info.API') as api:
            lookup=ProfileLookup()
            with self.assertRaises(AuthError):await lookup.lookup_many(['../secret'])
            with self.assertRaises(AuthError):await lookup.lookup_many([])
            async with lookup.lock:
                with self.assertRaises(AuthError):await lookup.lookup_many(['thtay'])
            api.assert_not_called()

    async def test_non_sg_target_is_safe(self):
        with patch('campus_lan.campus_info.API') as api:
            api.return_value.member_profile.side_effect=AuthError('not SG')
            profiles,errors=await ProfileLookup().lookup_many(['outsider'])
            self.assertEqual(profiles,[]);self.assertEqual(errors,['outsider'])

    async def test_hourly_budget_stops_requests(self):
        with patch('campus_lan.campus_info.API') as api:
            lookup=ProfileLookup(clock=lambda:100);lookup.requests.extend([100]*300)
            profiles,errors=await lookup.lookup_many(['thtay'])
            self.assertEqual(profiles,[]);self.assertEqual(errors,['thtay']);api.assert_not_called()

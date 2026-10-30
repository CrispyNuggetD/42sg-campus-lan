import json
import unittest
from unittest.mock import Mock,patch,AsyncMock
from campus_lan.profile_lookup import PROFILE_LOOKUPS_PER_HOUR, ProfileLookup
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
            self.assertEqual(PROFILE_LOOKUPS_PER_HOUR,600)
            lookup=ProfileLookup(clock=lambda:100);lookup.requests.extend([100]*599)
            api.return_value.member_profile.return_value={'login':'thtay','image':{}}
            profiles,errors=await lookup.lookup_many(['thtay'])
            self.assertEqual([p['login'] for p in profiles],['thtay']);self.assertFalse(errors)
            profiles,errors=await lookup.lookup_many(['dthoo'])
            self.assertEqual(profiles,[]);self.assertEqual(errors,['dthoo'])
            self.assertEqual(api.return_value.member_profile.call_count,1)

    async def test_game_snapshot_seats_cached_members_without_api_or_photo_work(self):
        lookup=ProfileLookup()
        with patch('campus_lan.campus_info.load',return_value={'students':[{'login':'cached'},{'login':'missing-photo'}]}), \
             patch.object(lookup,'lookup_many',new_callable=AsyncMock) as live, \
             patch('campus_lan.campus_info.API') as api:
            profiles,errors=await lookup.lookup_game_many(['cached','missing-photo'])
            self.assertEqual(profiles,[dict(login='cached',avatar=None),dict(login='missing-photo',avatar=None)])
            self.assertFalse(errors);live.assert_not_called();api.assert_not_called()

    async def test_unknown_game_target_still_requires_sg_profile_validation(self):
        lookup=ProfileLookup()
        with patch('campus_lan.campus_info.load',return_value={'students':[{'login':'cached'}]}), \
             patch.object(lookup,'lookup_many',new_callable=AsyncMock,return_value=([],['outsider'])) as live:
            profiles,errors=await lookup.lookup_game_many(['cached','outsider'])
            live.assert_awaited_once_with(['outsider'])
            self.assertEqual(profiles,[dict(login='cached',avatar=None)])
            self.assertEqual(errors,['outsider'])

import json
import unittest
from unittest.mock import Mock, patch
from campus_lan.profile_lookup import ProfileLookup
from campus_lan.auth import AuthError, TOKEN_URL


class Lookup(unittest.IsolatedAsyncioTestCase):
    @patch('campus_lan.profile_lookup.private_read',return_value=b'{"client_id":"private-id","client_secret":"private-secret"}')
    async def test_minimal_profiles_cache_token_and_request_spacing(self, read):
        api=Mock(side_effect=[{'access_token':'private-token','expires_in':3600},
            {'login':'thtay','email':'do-not-return','image':{'link':'https://cdn.intra.42.fr/thtay.jpg'}},
            {'login':'dthoo','image':{'link':'https://attacker.example/tracker'}}])
        sleep=Mock()
        lookup=ProfileLookup(request=api,clock=lambda:100,sleep=sleep)
        profiles,errors=await lookup.lookup_many(['thtay','dthoo','thtay'])
        self.assertFalse(errors)
        self.assertEqual(profiles,[dict(login='thtay',avatar='https://cdn.intra.42.fr/thtay.jpg'),dict(login='dthoo',avatar=None)])
        self.assertEqual(api.call_count,3)
        await lookup.lookup_many(['thtay'])
        self.assertEqual(api.call_count,3)
        self.assertEqual(api.call_args_list[0].args[0],TOKEN_URL)
        self.assertEqual(api.call_args_list[1].kwargs['headers'],{'Authorization':'Bearer private-token'})
        self.assertEqual(sleep.call_count,2)
        self.assertNotIn('private-',json.dumps(profiles))

    async def test_invalid_input_and_concurrency_do_not_call_api(self):
        api=Mock();lookup=ProfileLookup(request=api)
        with self.assertRaises(AuthError):await lookup.lookup_many(['../secret'])
        with self.assertRaises(AuthError):await lookup.lookup_many([])
        async with lookup.lock:
            with self.assertRaises(AuthError):await lookup.lookup_many(['thtay'])
        api.assert_not_called()

    @patch('campus_lan.profile_lookup.private_read',side_effect=FileNotFoundError)
    async def test_missing_owner_config_is_safe(self, read):
        api=Mock();profiles,errors=await ProfileLookup(request=api).lookup_many(['thtay'])
        self.assertEqual(profiles,[]);self.assertEqual(errors,['thtay']);api.assert_not_called()

    @patch('campus_lan.profile_lookup.private_read',return_value=b'{"client_id":"id","client_secret":"secret"}')
    async def test_hourly_budget_stops_requests(self, read):
        api=Mock();lookup=ProfileLookup(request=api,clock=lambda:100)
        lookup.requests.extend([100]*300)
        profiles,errors=await lookup.lookup_many(['thtay'])
        self.assertEqual(profiles,[]);self.assertEqual(errors,['thtay']);api.assert_not_called()

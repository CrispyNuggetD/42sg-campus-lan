import io
import unittest
import urllib.error
from unittest.mock import Mock, patch
from campus_lan.auth import request_json, AuthConfigError


class Diagnostics(unittest.TestCase):
    def test_invalid_client_has_safe_specific_error(self):
        response=urllib.error.HTTPError('https://api.intra.42.fr/oauth/token',401,'Unauthorized',{},io.BytesIO(b'{"error":"invalid_client","error_description":"SECRET must never appear"}'))
        opener=Mock();opener.open.side_effect=response
        with patch('campus_lan.auth.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(AuthConfigError) as result:
                request_json('https://api.intra.42.fr/oauth/token')
        self.assertIn('app credentials',str(result.exception))
        self.assertNotIn('SECRET',str(result.exception))

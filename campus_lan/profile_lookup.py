"""Bounded public-profile reads using the owner's existing private app settings.

Secrets and app access tokens stay in this process, never in the game wrapper.
"""
import asyncio
from collections import deque
import json
import re
import time
import urllib.parse
from .auth import (AuthError, config_dir, private_read, request_json, TOKEN_URL)


class ProfileLookup:
    def __init__(self, request=request_json, clock=time.monotonic, sleep=time.sleep):
        self.request, self.clock, self.sleep = request, clock, sleep
        self.lock = asyncio.Lock()
        self.cache = {}
        self.token = None
        self.expires = 0
        self.last_request = None
        self.requests = deque()

    def _request(self, url, data=None, headers=None):
        now = self.clock()
        while self.requests and self.requests[0] <= now - 3600:
            self.requests.popleft()
        if len(self.requests) >= 300:
            raise AuthError('Sabo API budget reached (300 requests/hour). Try later.')
        if self.last_request is not None:
            self.sleep(max(0, 1 - (now-self.last_request)))
        self.last_request = self.clock()
        self.requests.append(self.last_request)
        return self.request(url, data=data, headers=headers)

    def _lookup(self, login):
        cached = self.cache.get(login)
        if cached and cached['expires'] > self.clock():
            return cached['profile']
        if not self.token or self.expires <= self.clock():
            try:
                settings = json.loads(private_read(config_dir()/'auth-server.json'))
            except (OSError, ValueError):
                raise AuthError('Sabo needs the API owner\'s private LAN42 host configuration on this machine.') from None
            body = urllib.parse.urlencode(dict(grant_type='client_credentials',
                client_id=settings['client_id'], client_secret=settings['client_secret'])).encode()
            token = self._request(TOKEN_URL, data=body,
                headers={'Content-Type':'application/x-www-form-urlencoded'})
            if not isinstance(token.get('access_token'), str) or not token['access_token']:
                raise AuthError('42 did not issue a usable app token.')
            self.token = token['access_token']
            self.expires = self.clock() + max(1, min(float(token.get('expires_in',300)),7200)-30)
        try:
            user = self._request('https://api.intra.42.fr/v2/users/'+urllib.parse.quote(login,safe=''),
                headers={'Authorization':'Bearer '+self.token})
        except AuthError:
            self.token = None
            raise
        name = user.get('login')
        if not isinstance(name,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',name):
            raise AuthError('42 returned an invalid public profile.')
        image = user.get('image') or {}
        versions = image.get('versions') or {} if isinstance(image,dict) else {}
        avatar = (versions.get('small') if isinstance(versions,dict) else None) or (image.get('link') if isinstance(image,dict) else None)
        if avatar:
            try:
                url = urllib.parse.urlsplit(avatar)
                if (url.scheme!='https' or not url.hostname or not (url.hostname=='42.fr' or url.hostname.endswith('.42.fr'))
                        or url.username or url.password):
                    avatar = None
            except (ValueError,TypeError):
                avatar = None
        profile = dict(login=name,avatar=avatar)
        self.cache[login] = dict(profile=profile,expires=self.clock()+3600)
        return profile

    async def lookup_many(self, logins):
        if not 1 <= len(logins) <= 10 or any(not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',x) for x in logins):
            raise AuthError('Use /sabo LOGIN... with 1–10 valid Intra logins.')
        profiles, errors = [], []
        # One batch at a time; caps concurrency and prevents duplicate token requests.
        if self.lock.locked():
            raise AuthError('A sabo lookup is already running; try again shortly.')
        async with self.lock:
            for login in dict.fromkeys(x.lower() for x in logins):
                try:
                    profiles.append(await asyncio.to_thread(self._lookup,login))
                except (AuthError,KeyError,ValueError,TypeError):
                    errors.append(login)
        return profiles, errors

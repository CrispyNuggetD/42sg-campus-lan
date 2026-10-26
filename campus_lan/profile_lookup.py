"""Bounded public-profile reads using the owner's existing private app settings.

Secrets and app access tokens stay in this process, never in the game wrapper.
"""
import asyncio
from collections import deque
import re
import time
import urllib.parse
from .auth import AuthError


class ProfileLookup:
    def __init__(self, clock=time.monotonic):
        self.clock=clock
        self.lock=asyncio.Lock()
        self.cache={}
        self.requests=deque()

    def _lookup(self, login):
        self.cache={name:entry for name,entry in self.cache.items() if entry['expires']>self.clock()}
        cached=self.cache.get(login)
        if cached and cached['expires']>self.clock():return cached['profile']
        now=self.clock()
        while self.requests and self.requests[0]<=now-3600:self.requests.popleft()
        if len(self.requests)>=300:raise AuthError('SG profile budget reached; try later.')
        self.requests.append(now)
        from .campus_info import API
        user=API().member_profile(login)
        name=user.get('login')
        if name!=login:raise AuthError('SG profile identity mismatch.')
        image=user.get('image') or {};versions=image.get('versions') or {} if isinstance(image,dict) else {}
        avatar=(versions.get('small') if isinstance(versions,dict) else None) or (image.get('link') if isinstance(image,dict) else None)
        if avatar:
            try:
                url=urllib.parse.urlsplit(avatar)
                if url.scheme!='https' or not url.hostname or not (url.hostname=='42.fr' or url.hostname.endswith('.42.fr')) or url.username or url.password:avatar=None
            except (ValueError,TypeError):avatar=None
        profile=dict(login=name,avatar=avatar)
        self.cache[login]=dict(profile=profile,expires=self.clock()+60)
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
                except (AuthError,OSError,KeyError,ValueError,TypeError):
                    errors.append(login)
        return profiles, errors

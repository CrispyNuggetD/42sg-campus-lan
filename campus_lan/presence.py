"""Optional host-only public profile lookup. Never authenticates guest players."""
import asyncio
import json
import os
import time
import urllib.parse
import urllib.request
from .server import clean

class API:
    def __init__(self):
        self.token, self.expires = '', 0

    def get_seat(self, login):
        if time.time() >= self.expires:
            payload = urllib.parse.urlencode(dict(
                grant_type='client_credentials',
                client_id=os.environ['INTRA_CLIENT_ID'],
                client_secret=os.environ['INTRA_CLIENT_SECRET'])).encode()
            req = urllib.request.Request('https://api.intra.42.fr/oauth/token',data=payload)
            with urllib.request.urlopen(req,timeout=8) as response:
                result = json.load(response)
            self.token = result['access_token']
            self.expires = time.time()+max(0,int(result['expires_in'])-60)
            time.sleep(.6)
        req = urllib.request.Request(
            'https://api.intra.42.fr/v2/users/'+urllib.parse.quote(login,safe=''),
            headers={'Authorization':'Bearer '+self.token})
        with urllib.request.urlopen(req,timeout=8) as response:
            result = json.load(response)
        return clean(result.get('location') or 'not seated',50)

async def refresh(lobby):
    if not (os.getenv('INTRA_CLIENT_ID') and os.getenv('INTRA_CLIENT_SECRET')):
        return
    api = API()
    while True:
        names = [c['name'] for c in list(lobby.clients.values())]
        seats = {}
        failed = False
        for name in names:
            try:
                seats[name] = await asyncio.to_thread(api.get_seat,name)
            except Exception:
                # Never log response bodies, credentials or tokens.
                failed = True
                break
            await asyncio.sleep(.6)
        lobby.seats = seats
        lobby.api_status = ('API unavailable/limited; retry in 120s' if failed else
                            'API seats refreshed; guest names remain unverified')
        await lobby.state()
        await asyncio.sleep(120)

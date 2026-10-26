"""Scoped seat reads; unverified guest names never trigger provider API calls."""
import asyncio
from .server import clean

class API:
    def get_seat(self, login):
        from .campus_info import API as ScopedAPI
        result=ScopedAPI().member_profile(login)
        return clean(result.get('location') or 'not seated',50)

async def refresh(lobby):
    # The old environment-secret guest path is intentionally removed. Approved
    # views use /clusters and /campus-presence after server-side authentication.
    return

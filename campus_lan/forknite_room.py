"""Room-owned native game wrapper. LAN42 supplies all participant identities."""
import asyncio
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parent.parent


class ForkniteRoom:
    @classmethod
    async def create(cls):
        self=cls()
        from .avatar_cache import AvatarCache
        self.avatar_cache=AvatarCache()
        self.avatar_jobs=set()
        self.avatar_names=set()
        self.tool_pending=set()
        self.tool_task=None
        self.tool_ready=[]
        self.avatar_gate=asyncio.Semaphore(1)
        node=shutil.which('node')
        from .forknite import ensure_binary
        binary=await asyncio.to_thread(ensure_binary)
        if not node:raise ValueError('FORKNITE needs Node.js.')
        with socket.socket() as sock:
            sock.bind(('0.0.0.0',0));self.port=sock.getsockname()[1]
        self.secret=secrets.token_hex(32)
        logs=Path(os.environ.get('LAN42_FORKNITE_LOGDIR',str(ROOT/'minigames/forknite/.logs')));logs.mkdir(exist_ok=True)
        self.output=(logs/('room-'+str(self.port)+'.log')).open('ab')
        from .audio_quiet import browser_environment
        try:
            self.process=subprocess.Popen([node,str(ROOT/'minigames/forknite/server.js'),'--exec',binary,'--port',str(self.port),'--','50','600','100','100'],
                stdin=subprocess.DEVNULL,stdout=self.output,stderr=subprocess.STDOUT,
                env=dict(os.environ,**browser_environment(),LAN42_FORKNITE_CONTROL=self.secret,LAN42_AVATAR_CACHE=str(self.avatar_cache.root)),cwd=str(ROOT))
            for _ in range(50):
                if self.process.poll() is not None:break
                try:
                    await self.control({'action':'members','members':[]})
                    return self
                except (OSError,ValueError):await asyncio.sleep(.1)
            raise ValueError('FORKNITE failed to start. Check minigames/forknite/.logs.')
        except BaseException:
            await self.close()
            raise

    async def prepare_avatar(self,name,url):
        async with self.avatar_gate:
            if url:result=await asyncio.to_thread(self.avatar_cache.fetch,name,url)
            else:
                try:self.avatar_cache.read(name);result=dict(status='cached')
                except (OSError,ValueError):result=dict(status='missing')
            if result.get('status')!='cached':
                self.tool_pending.add(name)
                if not self.tool_task or self.tool_task.done():
                    self.tool_task=asyncio.create_task(self.open_tools())

    async def open_tools(self):
        # Coalesce missing photos into one local owner-only batch panel.
        while self.avatar_jobs:await asyncio.sleep(.5)
        self.tool_ready=sorted(set(self.tool_ready)|self.tool_pending)
        self.tool_pending.clear()

    async def control(self,data):
        records=data.get('members',[]) if data.get('action')=='members' else data.get('profiles',[]) if data.get('action')=='sabo_profiles' else []
        for record in records:
            name=record.get('name') or record.get('login')
            if name and (record.get('avatar') or record.get('login') or record.get('verified')) and name not in self.avatar_names:
                self.avatar_names.add(name)
                task=asyncio.create_task(self.prepare_avatar(name,record.get('avatar')))
                self.avatar_jobs.add(task)
                task.add_done_callback(self.avatar_jobs.discard)
        def request():
            req=urllib.request.Request('http://127.0.0.1:'+str(self.port)+'/internal/room',data=json.dumps(data).encode(),
                headers={'Content-Type':'application/json','Authorization':'Bearer '+self.secret})
            try:
                with urllib.request.urlopen(req,timeout=3) as response:return json.load(response)
            except urllib.error.HTTPError as error:
                try:message=json.loads(error.read(4096)).get('error','FORKNITE request failed')
                except (ValueError,AttributeError):message='FORKNITE request failed'
                raise ValueError(message) from None
        return await asyncio.to_thread(request)

    async def close(self):
        for task in getattr(self,"avatar_jobs",set()):task.cancel()
        process=getattr(self,'process',None)
        if process and process.poll() is None:
            process.terminate()
            try:await asyncio.to_thread(process.wait,5)
            except subprocess.TimeoutExpired:process.kill();await asyncio.to_thread(process.wait)
        if getattr(self,'tool_task',None):self.tool_task.cancel()
        if getattr(self,'output',None):self.output.close()

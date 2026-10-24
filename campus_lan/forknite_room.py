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
        self.avatar_gate=asyncio.Semaphore(1)
        node=shutil.which('node')
        local=ROOT/'minigames/forknite/philo'
        binary=os.environ.get('LAN42_PHILO_BINARY') or (str(local) if local.is_file() else shutil.which('philo'))
        if not node or not binary:
            raise ValueError('FORKNITE needs Node.js and minigames/forknite/philo (or LAN42_PHILO_BINARY).')
        with socket.socket() as sock:
            sock.bind(('0.0.0.0',0));self.port=sock.getsockname()[1]
        self.secret=secrets.token_hex(32)
        logs=Path(os.environ.get('LAN42_FORKNITE_LOGDIR',str(ROOT/'minigames/forknite/.logs')));logs.mkdir(exist_ok=True)
        self.output=(logs/('room-'+str(self.port)+'.log')).open('ab')
        try:
            self.process=subprocess.Popen([node,str(ROOT/'minigames/forknite/server.js'),'--exec',binary,'--port',str(self.port),'--','50','600','100','100'],
                stdin=subprocess.DEVNULL,stdout=self.output,stderr=subprocess.STDOUT,
                env=dict(os.environ,LAN42_FORKNITE_CONTROL=self.secret,LAN42_AVATAR_CACHE=str(self.avatar_cache.root)),cwd=str(ROOT))
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
            await asyncio.to_thread(self.avatar_cache.fetch,name,url)
            await asyncio.sleep(1)

    async def control(self,data):
        records=data.get('members',[]) if data.get('action')=='members' else data.get('profiles',[]) if data.get('action')=='sabo_profiles' else []
        for record in records:
            name=record.get('name') or record.get('login')
            if name and record.get('avatar') and name not in self.avatar_names:
                self.avatar_names.add(name)
                task=asyncio.create_task(self.prepare_avatar(name,record['avatar']))
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
        self.output.close()

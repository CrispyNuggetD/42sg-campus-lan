"""Opt-in, one-connection remote guest admission; never campus/API authority."""
import argparse
import asyncio
import contextlib
import ipaddress
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import time

NETWORK=ipaddress.ip_network('192.168.0.0/16')


def eligible(source):
    try:
        ip=ipaddress.ip_address(source)
        return ip.version==4 and ip in NETWORK
    except ValueError:return False


def local(source):
    try:return ipaddress.ip_address(source).is_loopback
    except ValueError:return False


def control_path(port):
    from .auth import config_dir
    root=config_dir()/'remote-control'
    root.mkdir(mode=0o700,parents=True,exist_ok=True)
    info=root.lstat()
    if root.is_symlink() or info.st_uid!=os.getuid() or info.st_mode&0o077:
        raise ValueError('Remote control directory must be private to the host user.')
    return root/('host-'+str(port)+'.sock')


class RemoteGate:
    def __init__(self):
        self.pending={};self.active={};self.recent={}
        self.server=None;self.path=None

    async def start(self,port):
        if sys.platform!='darwin':raise ValueError('Remote guest approval is currently Mac-only.')
        path=control_path(port)
        # Never remove an existing controller belonging to another process.
        if path.exists():raise ValueError('Remote control socket exists; stop its host or remove the stale socket locally.')
        self.server=await asyncio.start_unix_server(self.control,path=str(path),limit=4096)
        self.path=path
        self.path.chmod(0o600)

    async def close(self):
        for item in list(self.pending.values()):
            if not item['future'].done():item['future'].set_result(False)
        for writer in self.active.values():writer.close()
        if self.server:
            self.server.close();await self.server.wait_closed()
        if self.path:
            with contextlib.suppress(FileNotFoundError):self.path.unlink()

    async def admit(self,source,name,writer):
        if not eligible(source):raise ValueError('Only 192.168.0.0/16 may request remote admission; no campus address impersonation.')
        now=time.monotonic()
        self.recent={ip:stamp for ip,stamp in self.recent.items() if now-stamp<10}
        if len(self.pending)>=16 or len(self.active)>=32 or source in self.recent:
            raise ValueError('Remote approval busy; retry later.')
        self.recent[source]=now
        request=secrets.token_hex(8);future=asyncio.get_running_loop().create_future()
        self.pending[request]=dict(source=source,name=name[:24],expires=time.time()+60,future=future)
        print('Remote request '+request+' from '+source+'; approve/deny with python3 -m campus_lan.remote_access (expires in 60s).',flush=True)
        try:
            if not await asyncio.wait_for(future,60):raise ValueError('Host declined remote connection.')
            self.active[request]=writer
            return request
        except asyncio.TimeoutError:raise ValueError('Host approval timed out.') from None
        finally:self.pending.pop(request,None)

    async def control(self,reader,writer):
        try:
            data=json.loads(await asyncio.wait_for(reader.readline(),3))
            action=data.get('action');request=data.get('id')
            if action=='list':
                result={'pending':[dict(id=k,source=v['source'],name=v['name'],expires=v['expires']) for k,v in self.pending.items()],
                        'active':list(self.active)}
            elif action in ('approve','deny') and request in self.pending:
                future=self.pending[request]['future']
                if future.done():raise ValueError('Request already decided.')
                future.set_result(action=='approve');result={'ok':True}
            elif action=='revoke' and request in self.active:
                self.active.pop(request).close();result={'ok':True}
            else:raise ValueError('Unknown or expired request; approvals are never saved by IP.')
        except (ValueError,TypeError,AttributeError,asyncio.TimeoutError):result={'error':'Invalid, expired or already decided request.'}
        try:
            writer.write((json.dumps(result)+'\n').encode());await writer.drain()
        finally:writer.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=31417)
    parser.add_argument('action',choices=('list','approve','deny','revoke','join'))
    parser.add_argument('target',nargs='?')
    args=parser.parse_args()
    if not 1<=args.port<=65535:parser.error('Invalid port')
    if args.action=='join':
        if not args.target or not eligible(args.target):parser.error('Choose the host private 192.168.x.x address')
        from .client import connect
        connect(args.target,args.port,home=('127.0.0.1',31415),remote_guest=True)
        return
    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
        sock.settimeout(4);sock.connect(str(control_path(args.port)))
        sock.sendall((json.dumps(dict(action=args.action,id=args.target))+'\n').encode())
        with sock.makefile('rb') as stream:print(stream.readline(8192).decode().strip())


if __name__=='__main__':
    try:main()
    except (OSError,ValueError) as error:sys.exit(str(error))

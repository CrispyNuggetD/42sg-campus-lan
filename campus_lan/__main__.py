import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import threading
import pwd
from . import VERSION, PROTOCOL
from .client import connect
from .network import address, ask_seat
from .server import serve

def runtime_dir():
    path = Path(os.environ.get('XDG_STATE_HOME',str(Path.home()/'.local/state')))/'42sg-campus-lan'
    path.mkdir(parents=True,exist_ok=True,mode=0o700)
    return path

def probe(host,port):
    try:
        with socket.create_connection((host,port),timeout=.5) as sock:
            sock.settimeout(.5)
            sock.sendall((json.dumps(dict(type='ping',protocol=PROTOCOL))+'\n').encode())
            with sock.makefile('rb') as stream:
                msg = json.loads(stream.readline(2048))
            if msg.get('type')=='pong' and msg.get('protocol')==PROTOCOL:
                return msg
    except (OSError,ValueError,AttributeError):
        pass
    return None

def start_background(bind,port):
    target = '127.0.0.1' if bind=='0.0.0.0' else bind
    existing = probe(target,port)
    if existing:
        print(f"Reusing lobby server v{existing['version']} on {target}:{port}.")
        return target
    path = runtime_dir()
    log = path/f'server-{port}.log'
    with log.open('ab') as output:
        child = subprocess.Popen(
            [sys.executable,'-m','campus_lan','server','--bind',bind,'--port',str(port),'--managed'],
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
            start_new_session=True,close_fds=True,
            cwd=str(Path(__file__).resolve().parent.parent))
    for _ in range(50):
        if child.poll() is not None:
            raise RuntimeError(f'Server could not start (port may be occupied). See {log}')
        if probe(target,port):
            threading.Thread(target=child.wait,daemon=True).start()
            print(f'Background server PID {child.pid}; log: {log}')
            print('This node stays alive while your app is open, including visits to other nodes.')
            return target
        time.sleep(.1)
    raise RuntimeError(f'Server startup not confirmed. Inspect {log}; no process was killed.')

class Owner:
    def __init__(self,host,port,name):
        self.host,self.port = host,port
        self.socket = socket.create_connection((host,port),timeout=5)
        try:
            self.socket.sendall((json.dumps(dict(type='owner',protocol=PROTOCOL,
                name=name,hostname=socket.gethostname()))+'\n').encode())
            with self.socket.makefile('rb') as stream:
                msg = json.loads(stream.readline(2048))
        except Exception:
            self.socket.close()
            raise
        if msg.get('type')!='owner_ready':
            self.socket.close()
            raise RuntimeError('Local server needs an update/restart before using peer mode.')
        self.socket.settimeout(3)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.heartbeat,daemon=True)
        self.thread.start()

    def heartbeat(self):
        while not self.stop.wait(5):
            try:
                self.socket.sendall(b'heartbeat\n')
            except OSError:
                return

    def peer(self,host,port):
        host = socket.gethostbyname(host)
        if host==self.host and port==self.port:
            return
        with socket.create_connection((self.host,self.port),timeout=6) as control:
            control.settimeout(6)
            control.sendall((json.dumps(dict(type='connect_peer',protocol=PROTOCOL,
                                           host=host,port=port))+'\n').encode())
            with control.makefile('rb') as stream:
                result = json.loads(stream.readline(4096))
            if result.get('type')!='peer_connected':
                raise RuntimeError(result.get('text','Peer handshake failed.'))
        print(f'Nodes linked with {host}:{port}; presence refreshes every 5 seconds.')

    def close(self):
        self.stop.set()
        self.thread.join(timeout=4)
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.socket.close()

def main():
    parser = argparse.ArgumentParser(description='42SG guest LAN lobby — Python 3.9+, no pip packages')
    parser.add_argument('--version',action='version',version=VERSION)
    sub = parser.add_subparsers(dest='mode',required=True)
    for name in ('host','server','join'):
        p = sub.add_parser(name)
        if name=='join':
            p.add_argument('address',nargs='?',help='IP, hostname, or c1r2s3; omit for seat questions')
            p.add_argument('--local-port',type=int,default=31416,help='Your own node port')
        else:
            p.add_argument('--bind',default='0.0.0.0')
        p.add_argument('--port',type=int,default=31416)
        if name=='server':
            p.add_argument('--managed',action='store_true',help=argparse.SUPPRESS)
        if name!='server':
            p.add_argument('--guest-name',help='Unverified testing nickname; default OS username')
            p.add_argument('--no-notify',action='store_true')
    args = parser.parse_args()
    if not 1<=args.port<=65535:
        parser.error('Port must be between 1 and 65535')
    if args.mode=='server':
        # Hold the lock for the entire server lifetime; never overwrite another PID.
        lock = (runtime_dir()/f'server-{args.port}.pid').open('a+')
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('A local server already owns this port. Use lan42 host to reconnect.')
        lock.seek(0)
        lock.truncate()
        lock.write(str(os.getpid())+'\n')
        lock.flush()
        try:
            asyncio.run(serve(args.bind,args.port,managed=args.managed))
        finally:
            lock.close()
        return
    username = args.guest_name or pwd.getpwuid(os.getuid()).pw_name
    if args.mode=='host':
        local_port = args.port
        local = start_background(args.bind,local_port)
        target = local
    else:
        target = address(args.address) if args.address else ask_seat()
        if not target:
            return
        local_port = args.local_port
        if not 1<=local_port<=65535:
            parser.error('Local port must be between 1 and 65535')
        local = start_background('0.0.0.0',local_port)
    owner = Owner(local,local_port,username)
    try:
        owner.peer(target,args.port)
        connect(target,args.port,username,not args.no_notify,peer_callback=owner.peer,
                home=(local,local_port))
    finally:
        owner.close()

if __name__=='__main__':
    try:
        main()
    except (KeyboardInterrupt,EOFError):
        pass
    except (OSError,RuntimeError,ValueError) as e:
        print(f'lan42: {e}',file=sys.stderr)
        sys.exit(1)

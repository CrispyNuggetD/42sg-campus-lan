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
            [sys.executable,'-m','campus_lan','server','--bind',bind,'--port',str(port)],
            stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,
            start_new_session=True,close_fds=True,
            cwd=str(Path(__file__).resolve().parent.parent))
    for _ in range(50):
        if child.poll() is not None:
            raise RuntimeError(f'Server could not start (port may be occupied). See {log}')
        if probe(target,port):
            threading.Thread(target=child.wait,daemon=True).start()
            print(f'Background server PID {child.pid}; log: {log}')
            print('Closing this client leaves the server and other players running.')
            return target
        time.sleep(.1)
    raise RuntimeError(f'Server startup not confirmed. Inspect {log}; no process was killed.')

def main():
    parser = argparse.ArgumentParser(description='42SG guest LAN lobby — Python 3.9+, no pip packages')
    parser.add_argument('--version',action='version',version=VERSION)
    sub = parser.add_subparsers(dest='mode',required=True)
    for name in ('host','server','join'):
        p = sub.add_parser(name)
        if name=='join':
            p.add_argument('address',nargs='?',help='IP, hostname, or c1r2s3; omit for seat questions')
        else:
            p.add_argument('--bind',default='0.0.0.0')
        p.add_argument('--port',type=int,default=31416)
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
            asyncio.run(serve(args.bind,args.port))
        finally:
            lock.close()
        return
    if args.mode=='host':
        target = start_background(args.bind,args.port)
    else:
        target = address(args.address) if args.address else ask_seat()
    if target:
        connect(target,args.port,args.guest_name,not args.no_notify)

if __name__=='__main__':
    try:
        main()
    except (KeyboardInterrupt,EOFError):
        pass
    except (OSError,RuntimeError,ValueError) as e:
        print(f'lan42: {e}',file=sys.stderr)
        sys.exit(1)

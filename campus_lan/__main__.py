import argparse
import asyncio
import os
import socket
import subprocess
import sys
import time
from . import VERSION
from .client import connect
from .server import serve

def main():
    parser = argparse.ArgumentParser(description='42SG guest LAN lobby — Python 3.9+, no pip packages')
    parser.add_argument('--version',action='version',version=VERSION)
    sub = parser.add_subparsers(dest='mode',required=True)
    for name in ('host','server','join'):
        p = sub.add_parser(name)
        if name=='join':
            p.add_argument('address')
        else:
            p.add_argument('--bind',default='0.0.0.0')
        p.add_argument('--port',type=int,default=31416)
        if name!='server':
            p.add_argument('--guest-name',help='Explicitly unverified testing nickname; default OS username')
            p.add_argument('--no-notify',action='store_true')
    args = parser.parse_args()
    if not 1<=args.port<=65535:
        parser.error('Port must be between 1 and 65535')
    if args.mode=='server':
        asyncio.run(serve(args.bind,args.port))
        return
    child = None
    try:
        if args.mode=='host':
            child = subprocess.Popen([sys.executable,'-m','campus_lan','server','--bind',args.bind,'--port',str(args.port)])
            target = '127.0.0.1' if args.bind=='0.0.0.0' else args.bind
            for _ in range(30):
                if child.poll() is not None:
                    raise RuntimeError('Server did not start; check whether the port is occupied.')
                time.sleep(.1)
                try:
                    with socket.create_connection((target,args.port),timeout=.1):
                        pass
                    break
                except OSError:
                    continue
            else:
                raise RuntimeError('Server startup timed out.')
            if child.poll() is not None:
                raise RuntimeError('Server exited; port may be occupied.')
            print(f'Friends: lan42 join <this computer LAN IP> --port {args.port}')
        else:
            target = args.address
        connect(target,args.port,args.guest_name,not args.no_notify)
    finally:
        if child:
            child.terminate()
            try:
                child.wait(timeout=3)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()

if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
    except (OSError,RuntimeError) as e:
        print(f'lan42: {e}',file=sys.stderr)
        sys.exit(1)

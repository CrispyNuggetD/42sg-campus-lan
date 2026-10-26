"""Cross-process owner-local pacing for every 42 API request."""
import fcntl
import os
import time
from .auth import config_dir


def wait():
    root=config_dir();root.mkdir(parents=True,exist_ok=True,mode=0o700)
    fd=os.open(root/'api-pacing.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as handle:
        fcntl.flock(handle,fcntl.LOCK_EX)
        handle.seek(0)
        try:last=float(handle.read())
        except ValueError:last=0
        delay=max(0,.51-(time.time()-last))
        if delay:
            print('[LAN42] API queued: waiting %.2fs (global maximum 2 requests/second).'%delay,flush=True)
            time.sleep(delay)
        handle.seek(0);handle.truncate();handle.write(str(time.time()));handle.flush()

"""Cross-process owner-local pacing for every 42 API request."""
import fcntl
from contextlib import contextmanager
import queue
import os
import time
from .auth import config_dir


_notice_handler=None


@contextmanager
def ui_notices(handler):
    """Route worker-thread notices through the active UI instead of its terminal."""
    global _notice_handler
    previous=_notice_handler
    _notice_handler=handler
    try:yield
    finally:_notice_handler=previous


def report(text):
    handler=_notice_handler
    if handler is None:print(text,flush=True)
    else:
        try:handler(text)
        except queue.Full:pass  # Never fall back to printing over curses.


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
            report('[LAN42] API queued: waiting %.2fs (global maximum 2 requests/second).'%delay)
            time.sleep(delay)
        handle.seek(0);handle.truncate();handle.write(str(time.time()));handle.flush()

"""Permanent anonymous aggregates of launch reports, not browsing history or attestations."""
import hashlib
import hmac
import math
import os
import re
import secrets
import sqlite3
import stat
import threading
import time
from .auth import AuthError,config_dir,private_read

REGISTERS=4096  # HyperLogLog; expected relative standard error about 1.6%.


class SearchCounts:
    def __init__(self,root=None,clock=time.time):
        self.clock=clock;self.lock=threading.RLock();self.rates={};self.receipts={}
        root=root or config_dir();root.mkdir(parents=True,exist_ok=True,mode=0o700)
        info=root.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode&0o077:raise AuthError('Search aggregate directory must be private and owned by you.')
        key=root/'search-counts.key'
        try:self.key=bytes.fromhex(private_read(key).decode())
        except FileNotFoundError:
            if (root/'search-counts.sqlite').exists():raise AuthError('Aggregate key missing; restore it without resetting the retained totals.')
            try:
                fd=os.open(key,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                with os.fdopen(fd,'w') as output:output.write(secrets.token_hex(32))
            except FileExistsError:pass
            self.key=bytes.fromhex(private_read(key).decode())
        if len(self.key)!=32:raise AuthError('Invalid search counter key.')
        path=root/'search-counts.sqlite'
        fd=os.open(path,os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        info=os.fstat(fd);os.close(fd)
        if info.st_uid!=os.getuid() or info.st_mode&0o077 or info.st_nlink!=1 or not stat.S_ISREG(info.st_mode):raise AuthError('Search counter storage must be private.')
        self.db=sqlite3.connect(str(path),check_same_thread=False,timeout=3)
        self.db.execute('CREATE TABLE IF NOT EXISTS aggregate(id INTEGER PRIMARY KEY CHECK(id=1),total INTEGER,sketch BLOB)')
        with self.db:self.db.execute('INSERT OR IGNORE INTO aggregate VALUES(1,0,?)',(bytes(REGISTERS),))
        try:self.summary()  # Reject corrupt state rather than inventing/resetting totals.
        except Exception:self.db.close();raise

    def summary(self):
        with self.lock:
            total,sketch=self.db.execute('SELECT total,sketch FROM aggregate WHERE id=1').fetchone()
            if type(total) is not int or total<0 or not isinstance(sketch,bytes) or len(sketch)!=REGISTERS or any(v>53 for v in sketch):raise AuthError('Invalid search aggregate.')
            estimate=(.7213/(1+1.079/REGISTERS))*REGISTERS**2/sum(2.0**(-v) for v in sketch)
            zeros=sketch.count(0)
            if zeros and estimate<=2.5*REGISTERS:estimate=REGISTERS*math.log(REGISTERS/zeros)
            return dict(ecosia_total=total,ecosia_unique_estimate=min(total,round(estimate)),
                        label='permanent host-recorded launch reports; estimated unique search URLs',relative_error=.01625)

    def dispatch(self,route,data,source='local'):
        if route=='/search/stats':return self.summary()
        if route!='/search/report' or set(data)!={'fingerprint','event'}:raise AuthError('Invalid aggregate report.')
        if not isinstance(data['fingerprint'],str) or not re.fullmatch('[a-f0-9]{64}',data['fingerprint']):raise AuthError('Invalid search fingerprint.')
        if not isinstance(data['event'],str) or not re.fullmatch('[a-f0-9]{32}',data['event']):raise AuthError('Invalid search event.')
        with self.lock:
            now=self.clock();self.receipts={k:v for k,v in self.receipts.items() if now-v<300}
            self.rates={k:v for k,v in self.rates.items() if now-v[0]<60}
            # Source rate keys and replay nonces exist only briefly in RAM, with
            # no query association; no source, identity or event reaches SQLite.
            event=hmac.new(self.key,('event:'+data['event']).encode(),hashlib.sha256).digest()
            if event in self.receipts:return self.summary()
            source=hmac.new(self.key,('rate:'+source).encode(),hashlib.sha256).digest()
            start,n=self.rates.get(source,(now,0))
            if n>=30 or len(self.rates)>=512 or len(self.receipts)>=10000:raise AuthError('Aggregate reporting is busy; browsing still works.')
            value=int.from_bytes(hmac.new(self.key,bytes.fromhex(data['fingerprint']),hashlib.sha256).digest()[:8],'big')
            index=value>>52;tail=value&((1<<52)-1);rank=53-tail.bit_length()
            with self.db:
                self.db.execute('BEGIN IMMEDIATE')
                total,stored=self.db.execute('SELECT total,sketch FROM aggregate WHERE id=1').fetchone()
                if type(total) is not int or total<0 or not isinstance(stored,bytes) or len(stored)!=REGISTERS or any(v>53 for v in stored):raise AuthError('Invalid aggregate state; retained data was not reset.')
                if total>=2**63-1:raise AuthError('Aggregate total capacity reached.')
                sketch=bytearray(stored);sketch[index]=max(sketch[index],rank)
                self.db.execute('UPDATE aggregate SET total=?,sketch=? WHERE id=1',(total+1,bytes(sketch)))
            self.receipts[event]=now;self.rates[source]=(start,n+1)
            return self.summary()

    def close(self):
        with self.lock:self.db.close()

"""Private, repository-external raster avatar cache; no credentials in entries."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from .auth import NoRedirect, provider_tls_context

MAX_IMAGE=1024*1024
TTL=86400


def cache_root():
    base=Path(os.environ.get('XDG_CACHE_HOME',str(Path.home()/'.cache')))
    return base/'42sg-campus-lan/avatars'


def key(login):
    if not isinstance(login,str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}',login):
        raise ValueError('Invalid Intra login')
    return hashlib.sha256(login.lower().encode()).hexdigest()


def image_type(data):
    if not data or len(data)>MAX_IMAGE:raise ValueError('Photo must be at most 1 MiB')
    if data.startswith(b'\x89PNG\r\n\x1a\n'):return 'image/png'
    if data.startswith(b'\xff\xd8\xff'):return 'image/jpeg'
    if data.startswith((b'GIF87a',b'GIF89a')):return 'image/gif'
    if data.startswith(b'RIFF') and data[8:12]==b'WEBP':return 'image/webp'
    raise ValueError('Choose a PNG, JPEG, GIF or WebP image; HTML and SVG are not accepted')


class AvatarCache:
    def __init__(self,root=None):
        self.root=Path(root or cache_root()).expanduser().resolve()
        if any((p/'.git').exists() for p in [self.root,*self.root.parents]):
            raise ValueError('Avatar cache must be outside Git repositories')
        self.root.mkdir(parents=True,exist_ok=True,mode=0o700)
        self.root.chmod(0o700)

    def _atomic(self,path,data):
        temporary=path.with_name(path.name+'.'+secrets.token_hex(8))
        fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        try:
            with os.fdopen(fd,'wb') as output:output.write(data)
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def store(self,login,data,source='import'):
        mime=image_type(data)
        self._atomic(self.root/(key(login)+'.img'),data)
        self._atomic(self.root/(key(login)+'.json'),json.dumps(dict(saved_at=time.time(),source=source,mime=mime)).encode())
        return dict(status='cached',mime=mime,bytes=len(data))

    def read(self,login):
        p=self.root/(key(login)+'.img')
        fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW)
        with os.fdopen(fd,'rb') as f:data=f.read(MAX_IMAGE+1)
        return data,image_type(data)

    def fetch(self,login,url,force=False):
        # Coordinate acquisition across all local rooms/admin processes.
        lock=os.open(self.root/'acquisition.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(lock,fcntl.LOCK_EX)
            return self._fetch(login,url,force)
        finally:
            os.close(lock)

    def _fetch(self,login,url,force=False):
        digest=key(login)
        meta=self.root/(digest+'.json')
        try:info=json.loads(meta.read_text())
        except (OSError,ValueError):info={}
        if not force and time.time()-info.get('saved_at',0)<TTL:
            try:self.read(login);return dict(status='cached')
            except (OSError,ValueError):pass
        if not force and time.time()-info.get('attempted_at',0)<900:
            return dict(status=info.get('status','cooldown'),http=info.get('http'))
        u=urllib.parse.urlsplit(url or '')
        if u.scheme!='https' or u.hostname!='cdn.intra.42.fr' or u.username or u.password or u.port not in (None,443):
            return dict(status='invalid_photo_url')
        ratefile=self.root/'acquisition.json'
        try:recent=json.loads(ratefile.read_text()).get('requests',[])
        except (OSError,ValueError):recent=[]
        now=time.time();recent=[n for n in recent if isinstance(n,(int,float)) and n>now-3600]
        if len(recent)>=300:return dict(status='local_photo_budget_exhausted')
        if recent:time.sleep(max(0,recent[-1]+1-now))
        recent.append(time.time());self._atomic(ratefile,json.dumps(dict(requests=recent)).encode())
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPSHandler(context=provider_tls_context()),NoRedirect())
        try:
            request=urllib.request.Request(url,headers={'User-Agent':'LAN42-avatar-cache/1.0','Accept':'image/*'})
            with opener.open(request,timeout=10) as response:data=response.read(MAX_IMAGE+1)
            return self.store(login,data,'cdn')
        except urllib.error.HTTPError as exc:
            body=exc.read(2048).decode('utf-8','replace')
            cf=re.search(r'error code:\s*(\d{4})',body,re.I)
            result=dict(status='cdn_denied' if exc.code==403 else 'http_error',http=exc.code)
            if cf:result['cloudflare_code']=cf.group(1)
        except (OSError,ValueError):result=dict(status='invalid_image_or_network_error')
        info.update(result,attempted_at=time.time())
        # Failed refreshes preserve existing image bytes and their save timestamp.
        self._atomic(meta,json.dumps(info).encode())
        return result


def main():
    parser=argparse.ArgumentParser(description='Private LAN42 avatar cache')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('import');p.add_argument('login');p.add_argument('file',type=Path)
    p=sub.add_parser('fetch');p.add_argument('login')
    args=parser.parse_args();cache=AvatarCache()
    if args.command=='import':
        with args.file.open('rb') as f:result=cache.store(args.login,f.read(MAX_IMAGE+1))
    else:
        import asyncio
        from .profile_lookup import ProfileLookup
        profiles,errors=asyncio.run(ProfileLookup().lookup_many([args.login]))
        result=cache.fetch(args.login,profiles[0]['avatar']) if profiles else dict(status='profile_lookup_failed')
    print(json.dumps(result))


if __name__=='__main__':main()

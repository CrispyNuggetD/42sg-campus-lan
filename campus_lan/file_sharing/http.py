"""Native HTTPS requests behind the existing pinned broker listener."""
from dataclasses import dataclass
import asyncio
import json
import re
import urllib.parse
from ..auth import http_request
from .security import Denied,Conflict,Limit,campus_ip
from .store import MAX_FILE


@dataclass
class Response:
    status:int
    body:bytes
    headers:dict


def response(status,value,raw=False,headers=None):
    base={'Content-Type':'application/octet-stream' if raw else 'application/json',
          'Cache-Control':'no-store','X-Content-Type-Options':'nosniff',
          'Content-Security-Policy':"default-src 'none'; frame-ancestors 'none'",'Referrer-Policy':'no-referrer'}
    base.update(headers or {})
    return Response(status,value if raw else json.dumps(value).encode(),base)


class Requests:
    def __init__(self,store,host,port):
        store.gate.check(host)
        if type(port) is not int or not 1024<=port<=65535:raise Denied('Use an unprivileged fixed port.')
        self.store=store;self.host=host;self.bind_ip=campus_ip(host.peer_ip);self.authority=self.bind_ip+':'+str(port)
        self.slots=asyncio.Semaphore(4)
        self.flock=None

    def authenticate(self,headers,peer_ip,tls,local_ip):
        if local_ip!=self.bind_ip or tls is not True:raise Denied('Pinned HTTPS on the exact campus interface is required.')
        if headers.get('host')!=self.authority or any(k in headers for k in ('origin','forwarded','x-forwarded-for','x-real-ip','upgrade','transfer-encoding','cookie')):
            raise Denied('Native non-proxied requests only.')
        authorization=headers.get('authorization','')
        if not re.fullmatch(r'Bearer [a-f0-9]{64}',authorization):raise Denied('Verified session required.')
        self.store.gate.check(self.host)
        return self.store.gate.admit(authorization[7:],peer_ip,tls)

    def dispatch(self,method,target,headers,body,peer_ip,tls,local_ip):
        try:
            actor=self.authenticate(headers,peer_ip,tls,local_ip)
            if (not isinstance(body,bytes) or len(body)>MAX_FILE or str(len(body))!=headers.get('content-length','0')):
                return response(413,dict(error='Invalid or oversized body.'))
            if len(target)>512 or not target.startswith('/v1/') or '%' in target or '#' in target or target.startswith('//'):raise Denied('Invalid route.')
            url=urllib.parse.urlsplit(target);parts=url.path.strip('/').split('/')
            if url.query and not (method=='GET' and len(parts)==4 and parts[3]=='history'):raise Denied('Unexpected query parameters.')
            payload={}
            if method=='POST':
                if headers.get('content-type')!='application/json' or len(body)>4096:raise Denied('Bounded JSON required.')
                payload=json.loads(body)
                if not isinstance(payload,dict):raise Denied('Expected an object.')
            if parts==['v1','flock','join'] and method=='POST':
                if not self.flock or set(payload)!={'group','epoch'} or any(payload[k]!=self.flock[k] for k in ('group','epoch')):raise Conflict('The flock session changed.')
                self.store.join_flock(actor,self.flock['group'])
                return response(200,dict(joined=True,**self.flock))
            if parts==['v1','groups'] and method=='POST':
                if payload:raise Denied('No client-supplied host identity or binding.')
                if actor.uid!=self.host.uid or (actor.session_key!=self.host.session_key and not self.flock):raise Denied('Only the verified service host can create groups.')
                return response(201,dict(group=self.store.create(actor,self.bind_ip)))
            if len(parts)!=4 or parts[:2]!=['v1','groups']:raise Denied('Unknown route.')
            gid,action=parts[2:]
            if action=='invites' and method=='POST' and set(payload)=={'login'}:return response(201,self.store.invite(actor,gid,payload['login']))
            if action=='accept' and method=='POST' and set(payload)=={'invite'}:
                self.store.accept(actor,gid,payload['invite']);return response(200,dict(accepted=True))
            if action=='leave' and method=='POST' and not payload:
                self.store.leave(actor,gid);return response(200,dict(left=True))
            if action=='manifest' and method=='GET' and not body:return response(200,self.store.manifest(actor,gid))
            if action=='history' and method=='GET' and not body:
                query=urllib.parse.parse_qs(url.query,strict_parsing=True)
                if set(query)-{'after'} or len(query.get('after',['0']))!=1:raise Denied('Invalid cursor.')
                return response(200,dict(events=self.store.history(actor,gid,int(query.get('after',['0'])[0]))))
            if action=='files':
                if method=='GET' and not body:
                    version=headers.get('x-lan42-file-version','');metadata,data=self.store.read(actor,gid,version)
                    filename=urllib.parse.quote(metadata['path'].rsplit('/',1)[-1],safe='')
                    return response(200,data,True,{'Content-Disposition':"attachment; filename*=UTF-8''"+filename,'ETag':version,'X-LAN42-File-SHA256':metadata['digest']})
                encoded=headers.get('x-lan42-file-path','')
                if len(encoded)>1536:raise Denied('Invalid file path.')
                path=urllib.parse.unquote_to_bytes(encoded).decode('utf-8')
                if urllib.parse.quote(path,safe='/')!=encoded:raise Denied('Use canonical encoded paths.')
                match=headers.get('if-match')
                if match is not None and not re.fullmatch(r'[a-f0-9]{32}',match):raise Conflict('Current version required.')
                if method=='PUT' and headers.get('content-type')=='application/octet-stream':
                    if match is None and headers.get('if-none-match')!='*':raise Conflict('Explicit create or current version required.')
                    if match is not None and 'if-none-match' in headers:raise Conflict('Ambiguous write conditions.')
                    return response(201,self.store.put(actor,gid,path,body,match))
                if method=='DELETE':raise Denied('KoelDrop is add-only.')
            raise Denied('Unsupported operation.')
        except Conflict:return response(409,dict(error='Version conflict or missing write precondition.'))
        except Limit:return response(429,dict(error='File-sharing quota or request budget reached.'))
        except (ValueError,KeyError,TypeError,UnicodeError):return response(403,dict(error='Request denied.'))
        except OSError:return response(503,dict(error='Private storage unavailable.'))

    async def handle(self,reader,writer,parsed=None):
        """May handle a supplied TLS stream in tests; this module never binds a port."""
        if self.slots.locked():
            writer.close();return
        async with self.slots:
            try:
                peer=writer.get_extra_info('peername');local=writer.get_extra_info('sockname')
                tls=writer.get_extra_info('ssl_object') is not None
                method,target,headers=parsed if parsed is not None else await http_request(reader)
                await asyncio.to_thread(self.authenticate,headers,peer[0],tls,local[0])
                size=int(headers.get('content-length','0'))
                if not 0<=size<=MAX_FILE:raise Limit('Oversized request.')
                body=await asyncio.wait_for(reader.readexactly(size),15)
                reply=await asyncio.to_thread(self.dispatch,method,target,headers,body,peer[0],tls,local[0])
                reason={200:'OK',201:'Created',403:'Forbidden',409:'Conflict',413:'Payload Too Large',429:'Too Many Requests',503:'Unavailable'}[reply.status]
                headers_out={**reply.headers,'Content-Length':str(len(reply.body)),'Connection':'close'}
                writer.write(('HTTP/1.1 '+str(reply.status)+' '+reason+'\r\n'+''.join(k+': '+v+'\r\n' for k,v in headers_out.items())+'\r\n').encode()+reply.body)
                await asyncio.wait_for(writer.drain(),5)
            except (ValueError,OSError,TypeError,KeyError,IndexError,asyncio.TimeoutError,asyncio.IncompleteReadError):pass
            finally:
                writer.close()
                try:await writer.wait_closed()
                except OSError:pass

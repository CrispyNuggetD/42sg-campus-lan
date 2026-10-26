"""Native file API client. Uses only the existing pinned broker, never invite URLs."""
import json
import re
import urllib.parse
from .. import auth_client
from .security import Denied,Conflict,Limit
from .store import MAX_FILE


class RemoteStore:
    def __init__(self,session_token,trust=None):
        self.trust=trust or auth_client.load_trust();self.token=session_token
        if not re.fullmatch(r'[a-f0-9]{64}',session_token):raise Denied('Sign in first.')
        self.host=self.trust['lobby_host'];self.cancelled=lambda:False

    def _request(self,method,route,data=None,raw=False,headers=None):
        if self.cancelled():raise Denied('KoelDrop is paused.')
        connection=auth_client.PinnedHTTPSConnection(self.trust)
        body=data if raw else json.dumps(data).encode() if data is not None else b''
        request_headers={'Authorization':'Bearer '+self.token,'Content-Length':str(len(body)),
                         'Content-Type':'application/octet-stream' if raw else 'application/json',**(headers or {})}
        try:
            connection.request(method,route,body=body,headers=request_headers)
            reply=connection.getresponse();payload=reply.read(MAX_FILE+1)
            if self.cancelled():raise Denied('KoelDrop is paused.')
            if len(payload)>MAX_FILE:raise Limit('Server response is too large.')
            if reply.status==409:raise Conflict('A file or group changed; refresh before trying again.')
            if reply.status==429:raise Limit('KoelDrop quota reached; wait before syncing more files.')
            if reply.status not in (200,201):raise Denied('KoelDrop request rejected. Check experimental opt-in, sign-in, campus seat and invitation.')
            return (dict(reply.getheaders()),payload) if method=='GET' and route.endswith('/files') else json.loads(payload)
        except (OSError,ValueError) as error:
            if isinstance(error,(Denied,Conflict,Limit)):raise
            raise Denied('KoelDrop host is unavailable or the response was invalid.') from None
        finally:connection.close()

    def create(self):return self._request('POST','/v1/groups',{})['group']
    def invite(self,identity,gid,name):return self._request('POST','/v1/groups/'+gid+'/invites',dict(login=name))
    def accept(self,gid,token):return self._request('POST','/v1/groups/'+gid+'/accept',dict(invite=token))
    def leave(self,identity,gid):return self._request('POST','/v1/groups/'+gid+'/leave',{})
    def manifest(self,identity,gid):return self._request('GET','/v1/groups/'+gid+'/manifest')
    def history(self,identity,gid,after=0):return self._request('GET','/v1/groups/'+gid+'/history?after='+str(after))['events']
    def put(self,identity,gid,path,data,expected=None):
        conditions={'if-match':expected} if expected else {'if-none-match':'*'}
        return self._request('PUT','/v1/groups/'+gid+'/files',data,True,{'x-lan42-file-path':urllib.parse.quote(path,safe='/'),**conditions})
    def delete(self,identity,gid,path,expected):
        return self._request('DELETE','/v1/groups/'+gid+'/files',None,False,{'x-lan42-file-path':urllib.parse.quote(path,safe='/'),'if-match':expected})
    def read(self,identity,gid,version):
        headers,data=self._request('GET','/v1/groups/'+gid+'/files',headers={'x-lan42-file-version':version})
        return headers,data

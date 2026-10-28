"""Loopback-only, owner-operated photo import. No access to Chrome profiles."""
import asyncio
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import urllib.parse
import webbrowser
from .auth import config_dir, private_read
from .avatar_cache import AvatarCache, MAX_IMAGE
from .profile_lookup import ProfileLookup
from .login_whitelist import validate_logins, WhitelistUnavailable, PHOTO_SELECTOR_MESSAGE, unsupported_photo_selector
from .avatar_imports import BrowserImports, downloads_directory
from pathlib import Path


def validate_photo_login(value):
    if unsupported_photo_selector([value]):raise ValueError(PHOTO_SELECTOR_MESSAGE)
    return validate_logins([value])[0]

PAGE=r'''<!doctype html><meta charset="utf-8"><title>LAN42 · private avatar tools</title>
<style>body{max-width:720px;margin:50px auto;padding:20px;background:#151723;color:#eee;font:16px system-ui}input,button{padding:10px;margin:6px}a{color:#d8f96b}#drop{border:2px dashed #aaa;padding:25px;margin-top:20px}pre{white-space:pre-wrap}</style>
<h1>LAN42 · private avatar cache</h1><p>This panel runs on this computer only. Photos stay outside Git. It cannot read your Chrome profile or cookies. It watches only exact filenames for photo imports you explicitly start, not your other downloads.</p>
<label>Intra logins <input id="login" placeholder="thtay hnah" size="55"></label>
<button id="lookup">Look up photo link</button><button id="fetch">Try normal server download</button>
<p><button id="extension">Extension setup</button> <button id="prepare">Prepare one-click save</button></p>
<p><a id="photo" target="_blank" rel="noopener noreferrer" hidden>Open photo in my browser</a></p>
<details><summary>Chrome download folder</summary><p>Set the folder Chrome uses, not the private avatar cache.</p><input id="downloads" size="55"><button id="save-downloads">Use this folder</button></details>
<div id="drop">If the photo opens in your normal browser, save it there. Then choose or drop that image here to cache it locally.<br><input id="file" type="file" accept="image/png,image/jpeg,image/gif,image/webp"></div>
<pre id="status">Ready.</pre><button id="download-log" hidden>Download batch log</button><pre id="batch-log" aria-label="Batch results" role="log"></pre><p>PNG/JPEG/GIF/WebP · maximum 1 MiB · no screenshots, browser state or credentials are collected.</p>
<script>
const initialLogins=new URLSearchParams(location.search).get('logins')||'';
const token=new URLSearchParams(location.hash.slice(1)).get('key');history.replaceState(null,'',location.pathname);
const $=id=>document.getElementById(id);let photoUrl=null;
let photoConsent=PHOTO_CONSENT;
function question(text,yesLabel='Allow once'){return new Promise(resolve=>{const d=document.createElement('dialog');const p=document.createElement('p');p.textContent=text;d.append(p);const no=document.createElement('button'),yes=document.createElement('button');no.textContent='No (Enter)';yes.textContent=yesLabel;d.append(no,yes);const hint=document.createElement('p');hint.textContent='Change later: /settings permissions photos ask|allow|deny in LAN42.';d.append(hint);document.body.append(d);let done=false;function finish(value){if(done)return;done=true;d.close();d.remove();resolve(value);}no.onclick=()=>finish(false);yes.onclick=()=>finish(true);d.oncancel=e=>{e.preventDefault();finish(false);};d.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();finish(false);}};d.showModal();no.focus();});}
async function consentPhotos(){const p=await call('/photo_permission',JSON.stringify({}));if(p.mode==='deny')return false;if(p.mode==='allow')return true;if(photoConsent){photoConsent=false;return true;}return question('Allow photo tabs and extension saves for this batch?');}
async function rememberPhotos(){const p=await call('/photo_permission',JSON.stringify({}));if(p.mode==='ask'&&await question('Always allow photo tabs and extension saves for this account?','Always allow'))await call('/photo_permission',JSON.stringify({always:true}));}

$('login').value=initialLogins;
AVATAR_BATCH_SCRIPT
let batchLog=[];
$('download-log').onclick=()=>{const url=URL.createObjectURL(new Blob([batchLog.join('\n')+'\n'],{type:'text/plain'}));const link=document.createElement('a');link.href=url;link.download='lan42-avatar-batch.txt';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
const batch=document.createElement('button');batch.textContent='Cache all logins';$('lookup').before(batch);
batch.onclick=async()=>{
 if(!await consentPhotos()){$('status').textContent='Photo batch skipped. /settings permissions photos allow enables future batches.';return;}
 batch.disabled=true;batchLog=[];$('batch-log').textContent='';$('download-log').hidden=false;
 const names=$('login').value.trim().split(/\s+/).filter(Boolean);
 const append=line=>{batchLog.push(line);$('batch-log').textContent=batchLog.join('\n');console.log(line);};
 try{
  const result=await runAvatarBatch(names,{call,progress:(i,total,name)=>{$('status').textContent='Processing '+i+' of '+total+' · '+name;},log:r=>append(r.number+'. '+r.login+' — '+r.outcome+': '+r.reason)});
  const summary='Requested '+result.requested+', skipped '+result.skipped+', failed '+result.failed+', success '+result.success+'. See batch log below or Download batch log.';
  $('status').textContent=summary;append(summary);
  if(result.opened){try{await rememberPhotos();}catch(e){append('Photo preference could not be saved.');}}
 }finally{batch.disabled=false;}
};
if($('login').value)setTimeout(()=>batch.click(),500);
async function call(path,body,type='application/json'){const r=await fetch(path,{method:'POST',headers:{'X-LAN42-Admin':token||'','Content-Type':type},body});const data=await r.json();if(!r.ok)throw Error(data.error||'Request failed');return data;}
async function lookup(){const login=$('login').value.trim();if(unsupportedAvatarSelector(login))throw Error('Photo batches need explicit Intra logins; all and cohort selectors are unsupported.');const data=await call('/lookup',JSON.stringify({login}));photoUrl=data.avatar;$('photo').hidden=!photoUrl;$('photo').href=photoUrl||'#';$('status').textContent=JSON.stringify(data,null,2);return data;}
let pendingJob=null;
async function showDownloads(){try{const d=await call('/downloads_directory',JSON.stringify({}));$('downloads').value=d.directory;}catch(e){$('status').textContent=e.message;}}showDownloads();
$('save-downloads').onclick=async()=>{try{const d=await call('/downloads_directory',JSON.stringify({directory:$('downloads').value}));$('status').textContent='Importer watches '+d.expected_directory;}catch(e){$('status').textContent=e.message;}};
$('extension').onclick=async()=>{try{const d=await call('/extension',JSON.stringify({}));$('status').textContent='One-time Chrome setup: open chrome://extensions, enable Developer mode, choose Load unpacked, then select:\n'+d.path+'\nPin LAN42 — save this avatar. Permissions: active tab, scripting, downloads. No cookies or browsing-history permission. Chrome’s downloads permission is required; the code does not inspect other downloads.';}catch(e){$('status').textContent=e.message;}};
$('prepare').onclick=async()=>{if(!await consentPhotos())return;try{await lookup();if(!photoUrl)throw Error('No photo URL returned');const d=await call('/prepare',JSON.stringify({login:$('login').value.trim()}));pendingJob=d.job;const url=new URL(photoUrl);url.hash=new URLSearchParams({'lan42-import':d.job}).toString();$('photo').href=url.toString();$('photo').hidden=false;$('photo').textContent='Open photo, then click the LAN42 avatar extension';$('status').textContent='Ready. Click the photo link, then the extension icon on that tab. LAN42 expects the temporary file under '+d.expected_directory;}catch(e){$('status').textContent=e.message;}};
setInterval(async()=>{if(!pendingJob)return;try{const d=await call('/job_status',JSON.stringify({job:pendingJob}));if(d.status!=='waiting_for_browser_save'){$('status').textContent=d.status==='cached'?'Photo cached automatically. Click Reload cached photo in FORKNITE.':'Import status: '+d.status;pendingJob=null;}}catch(e){/* Local panel may have closed. */}},1500);
$('photo').onclick=async e=>{e.preventDefault();try{if(await consentPhotos()){const opened=window.open($('photo').href,'_blank','noopener');await rememberPhotos();}}catch(error){$('status').textContent=error.message;}};
$('lookup').onclick=()=>lookup().catch(e=>$('status').textContent=e.message);
$('fetch').onclick=async()=>{try{await lookup();const data=await call('/fetch',JSON.stringify({login:$('login').value.trim()}));$('status').textContent=JSON.stringify(data,null,2);}catch(e){$('status').textContent=e.message;}};
async function upload(file){if(!file)return;try{if(file.size>1048576)throw Error('Image exceeds 1 MiB');const login=$('login').value.trim();if(!/^[A-Za-z0-9_.-]{1,32}$/.test(login))throw Error('Enter the Intra login first');const data=await call('/import?login='+encodeURIComponent(login),file,'application/octet-stream');$('status').textContent='Cached locally for '+login+'. In FORKNITE click Reload cached photo.\n'+JSON.stringify(data,null,2);}catch(e){$('status').textContent=e.message;}}
$('file').onchange=e=>upload(e.target.files[0]);$('drop').ondragover=e=>e.preventDefault();$('drop').ondrop=e=>{e.preventDefault();upload(e.dataTransfer.files[0]);};
</script>'''.replace('AVATAR_BATCH_SCRIPT', (Path(__file__).with_name('avatar_batch.js')).read_text())


def launch(logins=(),approved=False,photos_approved=False,owner=None):
    import pwd,os
    from .popup_permissions import console_permission,console_remember,Permissions
    if unsupported_photo_selector(logins):
        print(PHOTO_SELECTOR_MESSAGE);return
    owner=owner or pwd.getpwuid(os.getuid()).pw_name
    if Permissions(owner).mode('tools')=='deny':
        print('Browser panel blocked by local popup settings.');return
    if not approved and not console_permission(owner,'tools','Open the local photo-tool browser panel?'):
        print('Browser panel skipped. /settings permissions tools ask|allow|deny');return
    if logins and not photos_approved:
        photos_approved=console_permission(owner,'photos','Allow photo tabs and extension saves for this batch?')
        if not photos_approved:logins=()
    # Owner-only entry: verify private host configuration exists, without exposing it.
    from .access import Policy
    Policy().local_operator()
    private_read(config_dir()/'auth-server.json')
    cache=AvatarCache();imports=BrowserImports(cache);token=secrets.token_hex(32)
    # All API lookups share one event loop, lock, pacing and cache in this panel.
    loop=asyncio.new_event_loop();thread=threading.Thread(target=loop.run_forever,daemon=True);thread.start()
    lookup=ProfileLookup();gate=threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,data):
            body=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
        def do_GET(self):
            if urllib.parse.urlsplit(self.path).path!='/':self.reply(404,{'error':'Not found'});return
            body=PAGE.replace('PHOTO_CONSENT','true' if photos_approved else 'false').encode();self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer');self.send_header('X-Frame-Options','DENY');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'");self.end_headers();self.wfile.write(body)
        def do_POST(self):
            authority='127.0.0.1:'+str(self.server.server_port)
            if (self.headers.get('Host')!=authority or self.headers.get('Origin')!='http://'+authority
                    or not secrets.compare_digest(self.headers.get('X-LAN42-Admin',''),token)):
                self.reply(403,{'error':'Local owner session required'});return
            if not gate.acquire(blocking=False):self.reply(429,{'error':'One operation at a time'});return
            try:
                Policy().local_operator()
                size=int(self.headers.get('Content-Length','0'))
                if not 0<size<=MAX_IMAGE:raise ValueError('Invalid body size (maximum 1 MiB)')
                self.connection.settimeout(15);raw=self.rfile.read(size)
                url=urllib.parse.urlsplit(self.path)
                if url.path=='/import':
                    login=validate_photo_login(urllib.parse.parse_qs(url.query).get('login',[''])[0])
                    self.reply(200,cache.store(login,raw));return
                data=json.loads(raw)
                if url.path=='/photo_permission':
                    from .popup_permissions import Permissions
                    preferences=Permissions(owner)
                    if data.get('always') is True:preferences.set('photos','allow')
                    self.reply(200,dict(mode=preferences.mode('photos')));return
                if url.path=='/downloads_directory':
                    result=imports.set_directory(data['directory']) if data.get('directory') else dict(directory=str(imports.root.parent),expected_directory=str(imports.root))
                    self.reply(200,result);return
                if url.path=='/extension':
                    self.reply(200,dict(path=str(Path(__file__).resolve().parent.parent/'browser-tools/avatar-saver')));return
                if url.path=='/job_status':self.reply(200,imports.status(data.get('job')));return
                if url.path=='/prepare':self.reply(200,imports.prepare(validate_photo_login(data.get('login'))));return
                try:login=validate_photo_login(data.get('login'))
                except ValueError as error:
                    if url.path=='/batch_one':
                        self.reply(200,dict(status='failed' if isinstance(error,WhitelistUnavailable) else 'skipped',reason=str(error)));return
                    raise
                future=asyncio.run_coroutine_threadsafe(lookup.lookup_many([login]),loop)
                profiles,errors=future.result(timeout=25)
                if not profiles:
                    if url.path=='/batch_one':
                        self.reply(200,dict(status='failed',reason='Profile lookup failed: login unavailable, not a Singapore member, or API limits reached'));return
                    raise ValueError('Profile lookup failed; check the login, API configuration or limits')
                profile=profiles[0]
                if url.path=='/lookup':result=profile
                elif url.path in ('/fetch','/batch_one'):
                    if url.path=='/batch_one' and not profile.get('avatar'):
                        self.reply(200,dict(status='skipped',reason='No photo available'));return
                    result=cache.fetch(login,profile['avatar'])
                    if url.path=='/batch_one' and result.get('status')!='cached':
                        from .popup_permissions import Permissions
                        if Permissions(owner).mode('photos')=='deny':raise ValueError('Photo popups are denied in settings')
                        if not (photos_approved or data.get('photo_consent') is True):raise ValueError('Browser photo permission required')
                        if not profile.get('avatar'):raise ValueError('No photo available')
                        result=imports.prepare(login)
                        photo=urllib.parse.urlsplit(profile['avatar'])
                        opened=webbrowser.open(urllib.parse.urlunsplit(photo._replace(fragment=urllib.parse.urlencode({'lan42-import':result['job']}))))
                        if not opened:result=dict(status='failed',reason='Browser could not open the photo tab')
                else:self.reply(404,{'error':'Not found'});return
                self.reply(200,result)
            except Exception:
                self.reply(400,{'error':'Operation failed. Check login/file type, API availability and the 1 MiB limit. No private details were logged.'})
            finally:gate.release()
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    address='http://127.0.0.1:'+str(server.server_port)
    # Token goes directly to a local browser fragment, never to logs or Git.
    opened=webbrowser.open(address+'/?'+urllib.parse.urlencode({'logins':' '.join(logins)})+'#key='+token)
    if opened and not approved:console_remember(owner,'tools')
    if opened and photos_approved and not approved:console_remember(owner,'photos')
    print('LAN42 avatar admin opened locally. Keep this terminal open; Ctrl-C closes the panel.')
    print('Private cache: '+str(cache.root))
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        server.server_close();imports.close();loop.call_soon_threadsafe(loop.stop);thread.join(timeout=2)
        if not thread.is_alive():loop.close()

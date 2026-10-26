"""User-initiated searches in the default browser, with an explicit search engine."""
import hashlib
import json
import queue
import re
import secrets
import threading
import urllib.parse
from .auth import private_read,private_write
from .local_console import local_path

INCIDENT='eMudhra "the private key is 4" October 2026'
TEMPLATES=dict(ecosia='https://www.ecosia.org/search?q={query}',google='https://www.google.com/search?q={query}')
INTRO='Ecosia says 100% of profits fund climate action, mainly tree planting. Results come from Bing, Google or EUSP, depending on availability; this is not a promise of a tree per search.'


def custom_template(value):
    if not isinstance(value,str) or len(value)>1000 or value.count('{query}')!=1 or re.search(r'[\s\x00-\x1f\x7f]',value):raise ValueError('Use one {query} in an HTTPS search URL, with no spaces.')
    parsed=urllib.parse.urlsplit(value)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or '{query}' not in parsed.query or '{' in parsed.netloc or parsed.port not in (None,443):raise ValueError('Use a fixed HTTPS host with {query} in its query string.')
    return value


class SearchSettings:
    def __init__(self):
        self.path=local_path('web-search');self.engine='ecosia';self.template=None;self.counting=True
        try:
            data=json.loads(private_read(self.path))
            if not isinstance(data,dict) or data.get('engine') not in ('ecosia','google','custom') or type(data.get('counting')) is not bool:raise ValueError()
            if data['engine']=='custom':custom_template(data.get('template'))
            self.engine=data['engine'];self.template=data.get('template');self.counting=data['counting']
        except FileNotFoundError:pass
        except (OSError,ValueError):self.counting=False

    def save(self):
        private_write(self.path,json.dumps(dict(engine=self.engine,template=self.template,counting=self.counting)))

    def url(self,query):
        query=' '.join(query.split())
        if not query or len(query)>400 or any(ord(c)<32 or ord(c)==127 for c in query):raise ValueError('Use 1–400 printable search characters.')
        template=self.template if self.engine=='custom' else TEMPLATES[self.engine]
        return template.replace('{query}',urllib.parse.quote_plus(query,safe=''))


class SearchControls:
    def search_result(self,message):
        if message.get('type')!='local_search_result':return False
        self.lines.extend(message.get('lines',[]))
        return True

    def search_remote(self,operation):
        def work():
            lines=[]
            try:
                from . import auth_client
                trust=auth_client.load_trust();data={}
                result=auth_client.post(trust,'/search/'+operation,data)
                lines.append('LAN42 impact: '+str(result['ecosia_total'])+' host-recorded Ecosia launch reports; about '+str(result['ecosia_unique_estimate'])+' unique search URLs (estimated). Permanent aggregate, not verified searches/trees.')
            except (OSError,ValueError,KeyError):lines.append('Search host unavailable. No host count was confirmed. Browsing still works; retry /search '+operation+' when connected.')
            try:self.inbox.put_nowait(dict(type='local_search_result',lines=lines))
            except queue.Full:pass
        threading.Thread(target=work,daemon=True).start()

    def launch_search(self,query):
        settings=SearchSettings();url=settings.url(query);engine=settings.engine
        def launch():
            def work():
                import webbrowser
                lines=[]
                opened=False
                if self.popup_prompts().permissions.mode('search')!='deny':
                    try:opened=bool(webbrowser.open_new_tab(url))
                    except Exception:pass
                if not opened:lines.append('Search browser launch failed or was blocked; no report was counted.')
                else:
                    lines.append('Search handed to your default browser using '+engine+'.')
                    if engine=='ecosia' and SearchSettings().counting:
                        try:
                            from . import auth_client
                            auth_client.post(auth_client.load_trust(),'/search/report',dict(fingerprint=hashlib.sha256(url.encode()).hexdigest(),event=secrets.token_hex(16)))
                            lines.append('Added one anonymous launch report to the permanent LAN42 impact aggregate. No search URL, identity or click history is stored.')
                        except (OSError,ValueError):lines.append('Opened without a host-recorded count (host offline or reporting unavailable). No report is queued for later.')
                    elif engine=='ecosia':lines.append('Aggregate counting is off. No host report was sent.')
                try:self.inbox.put_nowait(dict(type='local_search_result',lines=lines))
                except queue.Full:pass
            threading.Thread(target=work,daemon=True).start()
            return False
        self.request_popup('search','Open a '+engine+' search in your default browser? The provider receives the search terms. Ecosia aggregate reporting is currently '+('on' if settings.counting else 'off')+'; /settings search counting off opts out. Only permanent totals and a uniqueness sketch persist on the host, without identity or click history.',launch)

    def search_command(self,text):
        if text.strip()=='/key4':
            self.launch_search(INCIDENT);return True
        if text=='/search' or text.startswith('/search '):
            query=text[len('/search'):].strip()
            if query=='forget':self.lines.append('There is no personal search history on the host to erase. Permanent merged aggregates cannot remove one contribution; /settings search counting off prevents future reports.')
            elif query=='stats':self.search_remote('stats')
            elif query:
                try:self.launch_search(query)
                except ValueError as error:self.lines.append(str(error))
            else:self.lines.append('/search TERMS | /search stats | /key4 | /settings search')
            return True
        if text.split()[:2]!=['/settings','search']:return False
        parts=text.split(maxsplit=3);settings=SearchSettings()
        try:
            if len(parts)==2:
                self.lines.extend(['WEB SEARCH | engine='+settings.engine+' | anonymous aggregate counting='+str(settings.counting),INTRO,
                    'Sources: https://support.ecosia.org/article/33-how-does-ecosia-make-money | https://support.ecosia.org/article/579-search-results-providers',
                    '/settings search ecosia|google | /settings search custom HTTPS_URL_WITH_{query}',
                    '/settings search counting on|off | /search stats',
                    'Searches are excluded from LAN42 command history. Counting defaults to on with an opt-out. Only a permanent total and approximate unique-search sketch persist; no raw queries, query-hash list, identities or result clicks are stored. Merged contributions cannot be individually removed.',
                    'The browser opens the chosen engine URL; LAN42 does not inspect or change your browser search settings.'])
                impact=getattr(self,'announcement_status',{}).get('search_impact')
                if isinstance(impact,dict):self.lines.append('Host impact: '+str(impact.get('ecosia_total',0))+' launches; approximately '+str(impact.get('ecosia_unique_estimate',0))+' unique searches.')
            elif parts[2]=='counting' and len(parts)==4 and parts[3] in ('on','off'):
                def save_counting():
                    current=SearchSettings();current.counting=parts[3]=='on';current.save()
                    self.lines.append('Search counting '+parts[3]+'. Existing permanent anonymous aggregates remain; future reporting follows this choice.')
                save_counting()
            elif parts[2] in ('ecosia','google') and len(parts)==3:
                def choose():
                    current=SearchSettings();current.engine=parts[2];current.template=None;current.save();self.lines.append('LAN42 search engine: '+parts[2]+'.')
                if parts[2]=='google' and settings.engine!='google':self.popup_prompts().confirm('Switch LAN42 searches to Google? Ecosia says all profits fund climate action, so consider Ecosia if that matters to you. Your choice: y switches to Google; Enter keeps the current engine.',choose)
                else:choose()
            elif parts[2]=='custom' and len(parts)==4:
                settings.template=custom_template(parts[3]);settings.engine='custom';settings.save();self.lines.append('Custom HTTPS search engine saved. Ecosia counters do not include custom-engine searches.')
            else:raise ValueError('Use /settings search for engine and counting options.')
        except (OSError,ValueError) as error:self.lines.append(str(error))
        return True

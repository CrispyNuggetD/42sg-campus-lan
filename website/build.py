"""Build Pages from the same self-contained guide opened by /help and README."""
import argparse
import ast
from html import escape
from pathlib import Path
import re
import posixpath
from urllib.parse import quote,urlsplit

ROOT=Path(__file__).resolve().parents[1]
REPO='https://github.com/CrispyNuggetD/42sg-campus-lan'
START='<!-- runtime-help:start -->'
END='<!-- runtime-help:end -->'



def protect_external_links(document):
    """Keep Campus HQ navigation local; external HTTP(S) links get a new tab."""
    from html.parser import HTMLParser
    from urllib.parse import urlsplit
    offsets=[0]
    for line in document.splitlines(keepends=True):offsets.append(offsets[-1]+len(line))
    edits=[]
    class Links(HTMLParser):
        def handle_starttag(self,tag,attrs):
            if tag!='a':return
            attributes=dict(attrs);url=urlsplit(attributes.get('href') or '')
            if url.scheme and url.scheme not in ('http','https'):return
            external=bool(url.netloc and url.netloc.lower()!='crispynuggetd.github.io')
            raw=self.get_starttag_text()
            cleaned=re.sub(r"\s+target\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",'',raw,flags=re.I)
            if external:
                cleaned=re.sub(r"\s+rel\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s>]+)",'',cleaned,flags=re.I)
                rel=set((attributes.get('rel') or '').split())|{'noopener','noreferrer'}
                cleaned=cleaned[:-1]+' target="_blank" rel="'+escape(' '.join(sorted(rel)),quote=True)+'"'+(' title="Opens in a new tab"' if 'title' not in attributes else '')+'>'
            line,column=self.getpos();begin=offsets[line-1]+column;edits.append((begin,begin+len(raw),cleaned))
    Links(convert_charrefs=True).feed(document)
    for begin,end,replacement in reversed(edits):document=document[:begin]+replacement+document[end:]
    return document

def help_lines():
    tree=ast.parse((ROOT/'campus_lan/client.py').read_text())
    return next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='HELP' for t in node.targets))


def guide():
    source=(ROOT/'docs/quick-guide.html').read_text()
    rows=''.join('<div class="row"><div class="cmd"><code>'+escape(line)+'</code></div></div>' for line in help_lines())
    section=START+'<section class="card" id="runtime-help"><h2>Current terminal /help</h2><p class="sub">The app’s help text, included directly from its source.</p>'+rows+'</section>'+END
    if START in source:return re.sub(re.escape(START)+'.*?'+re.escape(END),lambda _:section,source,flags=re.S)
    return source.replace('</div><p id="empty"',section+'</div><p id="empty"',1)


def branded_page(title,description,content):
    template=(ROOT/'website/templates/page.html').read_text()
    values=dict(title=escape(title,quote=True),description=escape(description,quote=True),
                style=(ROOT/'website/page.css').read_text(),content=content)
    return re.sub(r'{{(title|description|style|content)}}',lambda match:values[match[1]],template)


DOCUMENT_PAGES = {
    'docs/README.md':'handbook.html',
    'docs/roadmap.md':'roadmap.html',
    'docs/frontend-milestone.md':'frontend-milestone.html',
    **{'docs/'+name+'.md':name+'.html' for name in (
        'getting-started','campus-guide','minigames','file-sharing','preferences',
        'web-search','exam-quiet','sign-in','hosting','access-policy','versioning',
        'runtime-environment','local-testing','protocol','file-sharing-design','website-changelog')},
}


def roadmap_page(source):
    """Render a topic or plan directly from its canonical Markdown source."""
    import markdown
    title,body=(ROOT/source).read_text().split('\n',1)
    title=title.removeprefix('# ').strip()
    md=markdown.Markdown(extensions=['tables','fenced_code','toc','md_in_html'])
    document=md.convert(body)
    def links(match):
        key,url=match.groups()
        if urlsplit(url).scheme or url.startswith(('#','//')):return match[0]
        target,mark,anchor=url.partition('#')
        target=posixpath.normpath(str(Path(source).parent/target))
        destination=DOCUMENT_PAGES.get(target)
        if target=='README.md':destination=(REPO+'/blob/main/README.md' if mark else 'index.html')
        if target=='docs/quick-guide.html':destination='commands.html'
        if destination is None:destination=REPO+'/blob/main/'+quote(target,safe='/')
        return key+'="'+destination+('#'+anchor if mark else '')+'"'
    document=re.sub(r'(href|src)="([^"]+)"',links,document)
    planning=source in ('docs/roadmap.md','docs/frontend-milestone.md')
    eyebrow='Plan and collaborate' if planning else 'LAN42 user guide'
    subtitle='Small steps, open questions, useful experiments.' if planning else 'Find a task, follow the steps, get back to campus life.'
    content=('<section class="hero"><div class="eyebrow">'+eyebrow+'</div><h1>'+escape(title)+
             '</h1><p>'+subtitle+' Student-built and unofficial.</p></section>'+
             '<div class="document-layout"><aside class="contents" aria-label="Page contents"><strong>On this page</strong>'+md.toc+
             '</aside><article class="document">'+document+'</article></div>'+
             '<p class="muted">Generated from <a href="'+REPO+'/blob/main/'+source+'">the Markdown source</a>.'+
             (' Plans are proposals, not release commitments.' if planning else '')+'</p>')
    return branded_page(title,'LAN42 '+('plans and ways to collaborate.' if planning else 'task guides, commands and help.'),content)


def home():
    import markdown
    readme=(ROOT/'README.md').read_text()
    quickstart=re.search(r'```sh\n(.*?)```',readme,re.S).group(1).strip()
    contributors=readme.split('## Contributors',1)[1]
    credit='\n'.join(line for line in contributors.splitlines() if line.startswith('- '))
    ai=readme.split('**AI-assisted, human-directed.**',1)[1].split('Beta since',1)[0]
    fragment=(ROOT/'website/home.html').read_text()
    values=dict(quickstart=escape(quickstart),contributors=markdown.markdown(credit),
                ai=markdown.markdown('**AI-assisted, human-directed.**'+ai))
    return branded_page('Good company. A few good commands.',
        'LAN42 BETA: start in a minute. A student-built 42 Singapore community app for campus tools, chat, games and consent-based file sharing.',
        re.sub(r'{{(quickstart|contributors|ai)}}',lambda m:values[m[1]],fragment)+'<script>'+(ROOT/'website/home.js').read_text()+'</script>')


def build(output):
    output.mkdir(parents=True,exist_ok=True)
    (output/'index.html').write_text(home())
    (output/'commands.html').write_text(guide().replace(REPO+'#readme','handbook.html'))
    (output/'alpha-tester.html').write_text(branded_page('Thank you, Darren',
        'Darren (dthoo): LAN42 alpha testing credit, with a GitHub profile link that follows the account ID.',
        (ROOT/'website/alpha-tester.html').read_text()))
    for source,filename in DOCUMENT_PAGES.items():
        (output/filename).write_text(roadmap_page(source))
    # Inline across online pages; offline help remains independent of browser effects.
    pointer_style=(ROOT/'website/pointer.css').read_text()
    pointer_script=(ROOT/'website/pointer.js').read_text()
    for page in output.glob('*.html'):
        source=page.read_text()
        source=source.replace('</head>','<style>'+pointer_style+'</style></head>',1)
        source=source.replace('</body>','<script>'+pointer_script+'</script></body>',1)
        page.write_text(protect_external_links(source))
    (output/'.nojekyll').touch()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-guide',action='store_true')
    parser.add_argument('--check-guide',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'_site')
    args=parser.parse_args()
    current=guide();path=ROOT/'docs/quick-guide.html'
    if args.check_guide:
        if current!=path.read_text():parser.exit(1,'Refresh guide with python3 website/build.py --refresh-guide\n')
        return
    if args.refresh_guide:path.write_text(current);return
    build(args.output)

if __name__=='__main__':main()

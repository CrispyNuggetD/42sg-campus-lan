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


DOCUMENT_PAGES = {'docs/roadmap.md':'roadmap.html',
                  'docs/frontend-milestone.md':'frontend-milestone.html'}

def roadmap_page(source):
    import markdown
    path=ROOT/source
    title,body=path.read_text().split('\n',1)
    title=title.removeprefix('# ').strip()
    md=markdown.Markdown(extensions=['tables','fenced_code','toc'])
    document=md.convert(body)
    def links(match):
        key,url=match.groups()
        if urlsplit(url).scheme or url.startswith(('#','//')):return match[0]
        target,mark,anchor=url.partition('#')
        target=posixpath.normpath(str(Path(source).parent/target))
        destination=DOCUMENT_PAGES.get(target)
        if target=='README.md':destination='handbook.html'
        if destination is None:destination=REPO+'/blob/main/'+quote(target,safe='/')
        return key+'="'+destination+('#'+anchor if mark else '')+'"'
    document=re.sub(r'(href|src)="([^"]+)"',links,document)
    content=('<section class="hero"><div class="eyebrow">Build the next chapter together</div><h1>'+escape(title)+
             '</h1><p>Small steps, open questions, useful experiments. Student-built and unofficial.</p></section>'+
             '<div class="document-layout"><aside class="contents" aria-label="Page contents"><strong>On this page</strong>'+md.toc+
             '</aside><article class="document">'+document+'</article></div>'+
             '<p class="muted">Generated from <a href="'+REPO+'/blob/main/'+source+'">the Markdown source</a>. Plans are proposals, not release commitments.</p>')
    return branded_page(title,'LAN42 plans, frontend learning milestones and ways to collaborate.',content)


def build(output):
    import markdown
    output.mkdir(parents=True,exist_ok=True)
    (output/'index.html').write_text(guide().replace(REPO+'#readme','handbook.html'))
    md=markdown.Markdown(extensions=['tables','fenced_code','toc'])
    document=md.convert((ROOT/'README.md').read_text())
    def links(match):
        key,url=match.groups()
        if urlsplit(url).scheme or url.startswith(('#','//')):return match[0]
        if url=='docs/quick-guide.html':url='index.html'
        else:url=(REPO+'/blob/main/' if key=='href' else 'https://raw.githubusercontent.com/CrispyNuggetD/42sg-campus-lan/main/')+quote(url,safe='/#?=&')
        return key+'="'+url+'"'
    document=re.sub(r'(href|src)="([^"]+)"',links,document)
    style=(ROOT/'website/handbook.css').read_text()
    (output/'handbook.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LAN42 · Start here</title><style>'+style+'</style></head><body><header><a href="index.html">← LAN42 quick guide</a><a href="'+REPO+'">GitHub ↗</a></header><div class="layout"><nav aria-label="Handbook contents">'+md.toc+'</nav><main>'+document+'</main></div></body></html>')
    (output/'alpha-tester.html').write_text(branded_page('Thank you, Darren',
        'Darren (dthoo): LAN42 alpha testing credit, with a GitHub profile link that follows the account ID.',
        (ROOT/'website/alpha-tester.html').read_text()))
    for source,filename in DOCUMENT_PAGES.items():
        (output/filename).write_text(roadmap_page(source))
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

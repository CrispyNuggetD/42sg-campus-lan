"""Build Pages from the same self-contained guide opened by /help and README."""
import argparse
import ast
from html import escape
from pathlib import Path
import re
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
    (output/'handbook.html').write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>LAN42 · Full handbook</title><style>'+style+'</style></head><body><header><a href="index.html">← LAN42 quick guide</a><a href="'+REPO+'">GitHub ↗</a></header><div class="layout"><nav aria-label="Handbook contents">'+md.toc+'</nav><main>'+document+'</main></div></body></html>')
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

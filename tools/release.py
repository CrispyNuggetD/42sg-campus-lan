"""Create a server release only when shipped runtime content changes."""
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
META = ROOT/'campus_lan/release.json'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()

def runtime_path(path):
    if path in ('campus_lan/release.json',):
        return False
    if path.endswith(('.md', '.test.js')) or '/.logs/' in path:
        return False
    return path.startswith(('campus_lan/', 'minigames/', 'assets/', 'useful-scripts/', 'browser-tools/')) or path in ('lan42.sh', 'setup.sh', 'requirements-auth.txt')

def canonical_ast(value):
    # ast.dump formatting changed between Python 3.12 and 3.13. Serialize fields
    # ourselves so changing the interpreter cannot release an unchanged server.
    if isinstance(value, ast.AST):
        result = {'node':type(value).__name__}
        for key, item in ast.iter_fields(value):
            if item is not None and item != []:
                result[key] = canonical_ast(item)
        return result
    if isinstance(value, list):
        return [canonical_ast(item) for item in value]
    if isinstance(value, (bytes, complex)):
        return {'literal':repr(value)}
    return value

def fingerprint():
    digest = hashlib.sha256()
    for name in sorted(git('ls-files').splitlines()):
        path = ROOT/name
        if not runtime_path(name) or not path.is_file():
            continue
        content = path.read_bytes()
        if path.suffix == '.py':
            # Python comments, whitespace and docstrings do not change the server.
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    if node.body and isinstance(node.body[0], ast.Expr) and isinstance(node.body[0].value, ast.Constant) and isinstance(node.body[0].value.value, str):
                        node.body.pop(0)
            content = json.dumps(canonical_ast(tree), sort_keys=True, separators=(',', ':')).encode()
        digest.update(name.encode()+b'\0'+content+b'\0')
    return digest.hexdigest()

def classify(messages):
    if any(re.match(r'\w+(\([^)]*\))?!:', m) or 'BREAKING CHANGE:' in m for m in messages):
        return 'major'
    if any(re.match(r'feat(\([^)]*\))?:', m) for m in messages):
        return 'minor'
    return 'patch'

def bump(version, kind):
    core, _, channel = version.partition('-')
    parts = list(map(int, core.split('.')))
    index = {'major':0, 'minor':1, 'patch':2}[kind]
    parts[index] += 1
    for i in range(index+1, 3):
        parts[i] = 0
    return '.'.join(map(str, parts))+('-beta.1' if channel.startswith('beta.') else '')

def write_changelog(data):
    lines = ['# LAN42 server changelog', '', 'Generated from `campus_lan/release.json`; `/changelog` shows the same history.', '']
    for release in data['history']:
        lines.extend(['## '+release['version']+' · '+release['date'], ''])
        lines.extend('- '+note for note in release['notes'])
        lines.append('')
    (ROOT/'CHANGELOG.md').write_text('\n'.join(lines))

def prepare():
    data = json.loads(META.read_text())
    current = fingerprint()
    if data.get('runtime_sha256') == current:
        write_changelog(data)
        return False
    base = data['source']
    # A seed release cannot embed its own commit ID; its immutable tag is the boundary.
    try:
        base = git('rev-parse', 'refs/tags/v'+data['version']+'^{commit}')
    except subprocess.CalledProcessError:
        pass
    commits = git('rev-list', '--reverse', base+'..HEAD').splitlines()
    messages = []
    for sha in commits:
        paths = git('diff-tree','--no-commit-id','--name-only','-r','--root',sha).splitlines()
        if any(runtime_path(p) for p in paths):
            messages.append(git('show','-s','--format=%B',sha))
    if not messages:
        raise SystemExit('Runtime changed without a runtime commit; commit changes before releasing.')
    kind = classify(messages)
    data['version'] = bump(data['version'], kind)
    data['date'] = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    data['source'] = git('rev-parse','HEAD')
    data['runtime_sha256'] = current
    notes = [m.splitlines()[0] for m in messages]
    data['history'].insert(0, dict(version=data['version'], date=data['date'], kind=kind, notes=notes))
    META.write_text(json.dumps(data, indent=2)+'\n')
    write_changelog(data)
    return True

if __name__ == '__main__':
    prepare()

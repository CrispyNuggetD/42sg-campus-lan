"""Install one source block, backing up existing zsh config without executing it."""
import os
from pathlib import Path
import shlex
import shutil
import sys
import time

START = '# >>> 42sg-campus-lan helpers >>>'
END = '# <<< 42sg-campus-lan helpers <<<'

def install(repo, rc):
    old = rc.read_text() if rc.exists() else ''
    source = shlex.quote(str(repo / 'useful-scripts/campus.zsh'))
    block = START + '\n[ ! -f ' + source + ' ] || source ' + source + '\n' + END
    if block in old:
        return False
    addition = ('\n' if old and not old.endswith('\n') else '') + '\n' + block + '\n'
    rc.parent.mkdir(parents=True, exist_ok=True)
    if rc.exists():
        backup = rc.with_name(rc.name + '.lan42-backup-' + str(time.time_ns()))
        shutil.copy2(rc, backup)
        print('Backup:', backup)
    with rc.open('a') as output:
        output.write(addition)
    return True

if __name__ == '__main__':
    repo = Path(sys.argv[1]).resolve()
    rc = Path(os.environ.get('ZDOTDIR', str(Path.home()))) / '.zshrc'
    try:
        print('Updated:' if install(repo, rc) else 'Already installed:', rc)
        print('Open a new zsh terminal, or run: source ' + shlex.quote(str(rc)))
        print('Your existing dailylogin is preserved. lan42_dailylogin always calls the public helper.')
    except ValueError as exc:
        raise SystemExit(str(exc))

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
    block = START + '\nsource ' + shlex.quote(str(repo / 'useful-scripts/campus.zsh')) + '\n' + END
    if START in old or END in old:
        if old.count(START) != 1 or old.count(END) != 1 or old.index(START) > old.index(END):
            raise ValueError('Malformed helper markers; fix them before rerunning setup.')
        first, last = old.index(START), old.index(END) + len(END)
        new = old[:first] + block + old[last:]
    else:
        new = old + ('\n' if old and not old.endswith('\n') else '') + '\n' + block + '\n'
    if new == old:
        return False
    rc.parent.mkdir(parents=True, exist_ok=True)
    if rc.exists():
        backup = rc.with_name(rc.name + '.lan42-backup-' + str(time.time_ns()))
        shutil.copy2(rc, backup)
        print('Backup:', backup)
    rc.write_text(new)
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

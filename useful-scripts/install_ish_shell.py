"""Append iSH login-shell commands without changing its default shell."""
import os
from pathlib import Path
import shlex
import shutil
import sys
import time

START = '# >>> LAN42 iSH main-shell commands >>>'
END = '# <<< LAN42 iSH main-shell commands <<<'


def install(repo, profile, use_zsh=True):
    repo = Path(repo).resolve()
    direct = 'command sh ' + shlex.quote(str(repo/'lan42.sh')) + ' "$@"'
    helper = shlex.quote(str(repo/'useful-scripts/campus.zsh'))
    launch = ('if command -v zsh >/dev/null 2>&1; then\n'
              '    command zsh -ic \'source "$1"; shift; lan42 "$@"\' lan42 ' + helper + ' "$@"\n'
              '  else\n    ' + direct + '\n  fi') if use_zsh else direct
    block = (START + '\nlan42() {\n  ' + launch + '\n}\n'
             'lan42_here() { ' + direct + '; }\n' + END)
    old = profile.read_text() if profile.exists() else ''
    if block in old:
        return False
    # Replace only our own complete block, preserving all other profile content.
    if old.count(START) == old.count(END) == 1:
        begin = old.index(START)
        finish = old.index(END,begin) + len(END)
        new = old[:begin] + block + old[finish:]
    elif START in old or END in old:
        raise ValueError('Incomplete LAN42 profile block; leaving your profile unchanged.')
    else:
        new = old + ('\n' if old and not old.endswith('\n') else '') + '\n' + block + '\n'
    profile.parent.mkdir(parents=True,exist_ok=True)
    if profile.exists():
        shutil.copy2(profile, profile.with_name(profile.name+'.lan42-backup-'+str(time.time_ns())))
    profile.write_text(new)
    return True


if __name__ == '__main__':
    profile = Path.home()/'.profile'
    try:
        print('Updated:' if install(sys.argv[1],profile,sys.argv[2]!='0') else 'Already installed:',profile)
        print('Fresh iSH login: type lan42 directly; zsh is invoked for you when configured.')
        print('In the existing main shell, load once with: . ~/.profile')
    except ValueError as exc:
        raise SystemExit(str(exc))

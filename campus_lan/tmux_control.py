"""Restart LAN42 clients through their own /restart input, never a shell."""
import argparse
import os
from pathlib import Path
import shlex
import subprocess


def run(*args):
    return subprocess.run(args,capture_output=True,text=True,timeout=5)


def client_process(pid):
    if not pid.isdecimal():return False
    reply=run('ps','-p',pid,'-o','command=')
    if reply.returncode:return False
    try:words=shlex.split(reply.stdout)
    except ValueError:return False
    return (len(words)>=3 and Path(words[0]).name.lower().startswith('python')
            and words[1:3]==['-m','campus_lan']
            and (len(words)==3 or words[3] in ('lobby','host','join','game')))


def restart_panes(check=False):
    reply=run('tmux','list-panes','-a','-F','#{pane_id}\t#{pane_pid}\t#{pane_current_command}')
    if reply.returncode:raise OSError('No running tmux server found.')
    panes=[]
    for line in reply.stdout.splitlines():
        fields=line.split('\t')
        if len(fields)!=3:continue
        pane,pid,command=fields
        if not pane.startswith('%') or not pane[1:].isdecimal() or not command.lower().startswith('python'):continue
        if not client_process(pid):continue
        if not check:
            # Recheck immediately before injection; do not send to shell panes.
            if not client_process(pid):continue
            for args in (('C-u',),('-l','/restart'),('Enter',)):
                result=run('tmux','send-keys','-t',pane,*args)
                if result.returncode:raise OSError('Could not deliver /restart to '+pane)
        panes.append(pane)
    return panes


def main():
    parser=argparse.ArgumentParser(description='Restart running LAN42 tmux clients via /restart. Clears unfinished app input.')
    parser.add_argument('--check',action='store_true',help='List matching app panes without sending keys.')
    args=parser.parse_args()
    try:
        panes=restart_panes(args.check)
        print(('LAN42 panes: ' if args.check else 'Sent /restart to: ')+(', '.join(panes) or 'none'))
    except (OSError,subprocess.SubprocessError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()

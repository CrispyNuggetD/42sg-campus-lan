"""Restart LAN42 clients through their own /restart input, never a shell."""
import argparse
import os
from pathlib import Path
import shlex
import signal
import subprocess


def run(*args):
    return subprocess.run(args,capture_output=True,text=True,timeout=5)


def close_miniapp_window():
    """Close only this finished LAN42 miniapp window, never HQ or a shell."""
    pane=os.environ.get('TMUX_PANE','')
    if not pane.startswith('%') or not pane[1:].isdecimal():return False
    try:
        result=run('tmux','display-message','-p','-t',pane,
                   '#{window_id}\t#{@daily_role}\t#{pane_pid}\t#{window_panes}')
        if result.returncode:return False
        window,role,pid,count=result.stdout.strip().split('\t')
        if (not window.startswith('@') or count!='1' or pid!=str(os.getpid())
                or not (role=='lan42-clusters' or role.startswith(('lan42-game-','lan42-admin-')))):
            return False
        return run('tmux','kill-window','-t',window).returncode==0
    except (OSError,ValueError,subprocess.SubprocessError):return False


def refresh_cluster_window():
    """Wake only the verified clusters miniapp when HQ focuses its tmux window."""
    session=os.environ.get('LAN42_TMUX_SESSION','lan42')
    try:
        windows=run('tmux','list-windows','-t','='+session,'-F','#{window_id}\t#{@daily_role}')
        if windows.returncode:return False
        for line in windows.stdout.splitlines():
            window,separator,role=line.partition('\t')
            if not separator or role!='lan42-clusters' or not window.startswith('@'):continue
            details=run('tmux','display-message','-p','-t',window,'#{pane_pid}\t#{pane_current_command}\t#{window_panes}')
            if details.returncode:continue
            pid,command,count=details.stdout.strip().split('\t')
            if not pid.isdecimal() or count!='1' or not command.lower().startswith('python'):continue
            process=run('ps','-p',pid,'-o','command=')
            if process.returncode:continue
            try:words=shlex.split(process.stdout)
            except ValueError:continue
            if (len(words)<4 or not Path(words[0]).name.lower().startswith('python')
                    or words[1:4]!=['-m','campus_lan','clusters']):continue
            os.kill(int(pid),signal.SIGUSR1)
            return True
    except (OSError,ValueError,subprocess.SubprocessError):pass
    return False


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

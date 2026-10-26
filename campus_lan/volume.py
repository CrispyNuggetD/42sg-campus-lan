"""System output volume shared by the local TUI and shell helper."""
import argparse
import os
import re
import shutil
import subprocess
import sys


def run(*args):
    try:
        result=subprocess.run(args,capture_output=True,text=True,timeout=4,env={**os.environ,"LC_ALL":"C"})
    except (OSError,subprocess.TimeoutExpired) as exc:raise OSError('System volume service unavailable.') from exc
    if result.returncode:raise OSError('System volume service rejected the request.')
    return result.stdout.strip()


class Volume:
    def __init__(self):
        self.backend='mac' if sys.platform=='darwin' else ('pactl' if shutil.which('pactl') else 'wpctl' if shutil.which('wpctl') else None)
        if self.backend is None:raise OSError('No system volume service found (pactl or wpctl required).')

    def get(self):
        if self.backend=='mac':
            value=run('osascript','-e','get {output volume, output muted} of (get volume settings)')
            level,muted=value.split(', ')
            return 0 if muted=='true' else int(level)
        if self.backend=='pactl':
            muted=run('pactl','get-sink-mute','@DEFAULT_SINK@')
            values=re.findall(r'(\d+)%',run('pactl','get-sink-volume','@DEFAULT_SINK@'))
            if not values:raise OSError('Could not read system volume.')
            return 0 if 'yes' in muted else round(sum(map(int,values))/len(values))
        value=run('wpctl','get-volume','@DEFAULT_AUDIO_SINK@')
        match=re.search(r'Volume:\s*([0-9.]+)',value)
        if not match:raise OSError('Could not read system volume.')
        return 0 if '[MUTED]' in value else round(float(match[1])*100)

    def set(self,value):
        if type(value) is not int or not 0<=value<=100:raise ValueError('Volume must be an integer from 0 to 100.')
        if self.backend=='mac':run('osascript','-e',f'set volume output volume {value} output muted {"true" if value==0 else "false"}')
        else:
            if self.backend=='pactl':
                run('pactl','set-sink-volume','@DEFAULT_SINK@',str(value)+'%')
                run('pactl','set-sink-mute','@DEFAULT_SINK@','1' if value==0 else '0')
            else:
                run('wpctl','set-volume','@DEFAULT_AUDIO_SINK@',str(value)+'%')
                run('wpctl','set-mute','@DEFAULT_AUDIO_SINK@','1' if value==0 else '0')
        return value

    def adjust(self,value=None):return self.set((30 if self.get()==0 else 0) if value is None else value)


def main():
    parser=argparse.ArgumentParser(description='Toggle output volume 0/30, or set 0–100. Uses the desktop output slider.')
    parser.add_argument('level',nargs='?',type=int)
    args=parser.parse_args()
    try:print('Output volume: '+str(Volume().adjust(args.level))+'%')
    except (OSError,ValueError) as error:parser.exit(1,str(error)+'\n')

if __name__=='__main__':main()

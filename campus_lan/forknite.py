"""Launch the bundled browser game without importing or modifying C projects."""
import os
from pathlib import Path
import shutil
import sys
import subprocess
from .updater import update_checkout, generation

ROOT = Path(__file__).resolve().parent.parent


def launch(arguments):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('FORKNITE needs Node.js (12 or later).')
    arguments = list(arguments)
    if not arguments:
        local_binary = ROOT/'minigames/forknite/philo'
        binary = os.environ.get('LAN42_PHILO_BINARY') or (str(local_binary) if local_binary.is_file() and os.access(local_binary,os.X_OK) else None) or shutil.which('philo')
        if not binary:
            raise RuntimeError('Set LAN42_PHILO_BINARY=/absolute/path/to/philo, or run lan42 forknite --exec /path/to/philo -- 50 130 60 60')
        arguments = ['--exec', binary, '--', '50', '130', '60', '60']
    while True:
        installed = generation()
        child = subprocess.Popen([node, str(ROOT/'minigames/forknite/server.js'), *arguments], env=dict(os.environ, LAN42_FORKNITE_SUPERVISED='1', LAN42_PYTHON=sys.executable))
        reloading = False
        try:
            while True:
                try:
                    code = child.wait(timeout=.5)
                    break
                except subprocess.TimeoutExpired:
                    if generation() != installed:
                        child.terminate()
                        try:
                            child.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            child.kill(); child.wait()
                        reloading = True
                        break
        except KeyboardInterrupt:
            child.terminate()
            child.wait()
            return
        if reloading:
            continue
        result = child
        if result.returncode not in (75, 76):
            if result.returncode:
                raise RuntimeError('FORKNITE exited with status '+str(result.returncode))
            return
        if result.returncode == 76:
            update_checkout(ROOT)
        print('[lan42] Restarting bundled FORKNITE; reconnect your browser.', flush=True)

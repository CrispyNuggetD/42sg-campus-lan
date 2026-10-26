"""Launch the bundled browser game without importing or modifying C projects."""
import os
from pathlib import Path
import shutil
import sys
import subprocess
from .updater import update_checkout, generation

ROOT = Path(__file__).resolve().parent.parent


def ensure_binary():
    local=ROOT/'minigames/forknite/philo'
    configured=os.environ.get('LAN42_PHILO_BINARY')
    folder=os.environ.get('LAN42_PHILO_DIR')
    binary=Path(configured).expanduser() if configured else Path(folder).expanduser()/'philo' if folder else local.resolve()
    if binary.is_file() and os.access(binary,os.X_OK):return str(binary)
    if not configured and not folder and not local.is_symlink():
        found=shutil.which('philo')
        if found:return found
        raise ValueError('Configure LAN42_PHILO_DIR or LAN42_PHILO_BINARY, then retry FORKNITE.')
    print('[LAN42] philo missing; running make in '+str(binary.parent),flush=True)
    try:subprocess.run(['make','-C',str(binary.parent)],check=True,timeout=120)
    except (OSError,subprocess.SubprocessError):raise ValueError('philo build failed; check the configured directory and make output.') from None
    if not binary.is_file() or not os.access(binary,os.X_OK):raise ValueError('make did not produce the configured philo executable.')
    return str(binary)


def launch(arguments):
    node = shutil.which('node')
    if not node:
        raise RuntimeError('FORKNITE needs Node.js (12 or later).')
    arguments = list(arguments)
    if not arguments:
        binary = ensure_binary()
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

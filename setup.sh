#!/bin/sh
set -eu
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
command -v git >/dev/null || { echo "Git is required."; exit 1; }
command -v python3 >/dev/null || { echo "Python 3.9+ is required."; exit 1; }
python3 - "$repo_dir" <<'PY'
import os, shlex, sys
from pathlib import Path
if sys.version_info < (3,9):
    raise SystemExit('Python 3.9+ is required; no packages will be installed.')
repo = Path(sys.argv[1])
dest = Path(os.environ.get('LAN42_BIN_DIR', str(Path.home()/'.local/bin')))
dest.mkdir(parents=True, exist_ok=True)
target = dest/'lan42'
content = '#!/bin/sh\n# Installed by 42sg-campus-lan setup.sh\nexec /bin/sh '+shlex.quote(str(repo/'launch.sh'))+' "$@"\n'
if target.exists() and 'Installed by 42sg-campus-lan' not in target.read_text():
    raise SystemExit(f'Refusing to replace an unrelated command: {target}')
target.write_text(content)
target.chmod(0o755)
print(f'Installed {target}\nRepo: {repo}\nRun: {target} host\nFriends: {target} join HOST_IP')
print('If needed, add ~/.local/bin to PATH in your shell configuration.')
PY

"""Release metadata shared by the server, startup and local changelog."""
import json
from pathlib import Path
DATA = json.loads(Path(__file__).with_name('release.json').read_text())
VERSION = DATA['version']
RELEASE_DATE = DATA['date']
def banner():
    return f'LAN42 BETA · v{VERSION} · {RELEASE_DATE} | /changelog'
def changelog():
    result = ['LAN42 server changelog']
    for release in DATA['history']:
        result.append(f"{release['version']} · {release['date']}")
        result.extend('  '+note for note in release['notes'])
    return result

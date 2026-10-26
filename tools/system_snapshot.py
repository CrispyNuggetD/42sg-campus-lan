"""Collect an explicit, privacy-limited local hardware/OS observation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import subprocess

def command(*args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL, timeout=5).strip()
    except (OSError, subprocess.SubprocessError):
        return None

def snapshot(label):
    linux = platform.system() == 'Linux'
    cpu = platform.processor()
    ram = None
    os_release = {}
    if linux:
        for line in Path('/etc/os-release').read_text().splitlines():
            key, _, value = line.partition('=')
            if key in ('NAME','VERSION','VERSION_ID','PRETTY_NAME'):
                os_release[key] = value.strip('"')
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith('model name'):
                cpu = line.partition(':')[2].strip();break
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):
                ram = int(line.split()[1])*1024;break
    elif platform.system() == 'Darwin':
        cpu = command('sysctl','-n','machdep.cpu.brand_string') or cpu
        value = command('sysctl','-n','hw.memsize')
        ram = int(value) if value else None
        os_release = {'version': platform.mac_ver()[0], 'build': command('sw_vers','-buildVersion')}
    storage = []
    for name, path in [('system','/'), ('home',str(Path.home())), ('sgoinfre','/sgoinfre'), ('goinfre','/goinfre'), ('NAS','/mnt/nas')]:
        entry = {'label':name, 'available':Path(path).exists()}
        if entry['available']:
            usage = shutil.disk_usage(path)
            entry.update(total_bytes=usage.total, used_bytes=usage.used, free_bytes=usage.free)
            if linux:
                # Filesystem type only; do not export NAS addresses or usernames.
                entry['filesystem'] = command('findmnt','-n','-o','FSTYPE','-T',path)
        storage.append(entry)
    from campus_lan import VERSION
    return dict(label=label, observed_at=datetime.now(timezone.utc).isoformat(),
                system=platform.system(), kernel=platform.release(), architecture=platform.machine(),
                os=os_release, cpu=cpu, logical_cpus=__import__('os').cpu_count(), ram_bytes=ram,
                storage=storage, lan42_version=VERSION,
                validation='Observation only; see runtime-environment.md for tests. Quotas are not filesystem capacity. NAS mount may use another path; unavailable is not proof of absence.')

if __name__ == '__main__':
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label',required=True);p.add_argument('--output',type=Path,required=True)
    args=p.parse_args();data=snapshot(args.label)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(data,indent=2)+'\n')

"""Local C compilation and bounded, import-free WebAssembly bot execution."""
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

SDK = Path(__file__).resolve().parents[1] / 'minigames' / 'hexwars'
MAX_WASM = 32768
MAX_SOURCE = 65536


def validate_wasm(data):
    """Bound allocations before the runtime instantiates untrusted modules."""
    if not isinstance(data, bytes) or len(data) > MAX_WASM or data[:8] != b'\0asm\x01\0\0\0':
        raise ValueError('Expected a WebAssembly v1 bot, at most 32 KiB.')
    pos = 8

    def uint(end):
        nonlocal pos
        value = 0
        for shift in range(0, 35, 7):
            if pos >= end:
                break
            b = data[pos]
            pos += 1
            value |= (b & 127) << shift
            if not b & 128 and value <= 0xffffffff:
                return value
        raise ValueError('Malformed WebAssembly integer.')

    def limits(end, cap):
        flags = uint(end)
        if flags != 1:
            raise ValueError('Bot memory/table must have a fixed maximum; shared memory is disabled.')
        minimum, maximum = uint(end), uint(end)
        if not 0 <= minimum <= maximum <= cap:
            raise ValueError('Bot memory/table exceeds the arena limit.')

    memories = 0
    seen = set()
    while pos < len(data):
        section = data[pos]
        pos += 1
        size = uint(len(data))
        end = pos + size
        if end > len(data) or section > 12 or (section and section in seen):
            raise ValueError('Malformed WebAssembly section.')
        seen.add(section)
        if section == 2 and uint(end) != 0:
            raise ValueError('Bot imports are disabled: no WASI, files, network, or host functions.')
        if section == 8:
            raise ValueError('WebAssembly start functions are disabled.')
        if section == 4:
            count = uint(end)
            if count > 1:
                raise ValueError('Too many bot tables.')
            for _ in range(count):
                if pos >= end or data[pos] != 0x70:
                    raise ValueError('Only function tables are supported.')
                pos += 1
                limits(end, 1024)
        if section == 5:
            memories = uint(end)
            if memories != 1:
                raise ValueError('Bot must define exactly one memory.')
            limits(end, 16)  # 1 MiB including stack and board
        if section in (2, 4, 5) and pos != end:
            raise ValueError('Malformed WebAssembly limits.')
        pos = end
    if memories != 1:
        raise ValueError('Bot must define its own bounded memory.')


def compile_bot(path):
    """Only called by the uploading client, never on remotely supplied C."""
    source = Path(path).expanduser().resolve()
    if source.suffix != '.c' or not source.is_file() or source.stat().st_size > MAX_SOURCE:
        raise ValueError('Choose a .c file no larger than 64 KiB.')
    compiler = os.environ.get('LAN42_CLANG') or shutil.which('clang')
    linker = os.environ.get('LAN42_WASM_LD') or shutil.which('wasm-ld')
    if not linker:
        linker = next((shutil.which('wasm-ld-' + str(v)) for v in range(22, 10, -1)
                       if shutil.which('wasm-ld-' + str(v))), None)
    if not compiler or not linker:
        raise ValueError('C bots need Clang and wasm-ld (LLVM LLD). See minigames/hexwars/README.md.')
    with tempfile.TemporaryDirectory(prefix='lan42-hex-') as directory:
        output = Path(directory) / 'bot.wasm'
        command = [compiler, '--target=wasm32', '-std=c99', '-O2', '-Wall', '-Wextra',
                   '-Werror', '-ffreestanding', '-fno-builtin', '-nostdlib', '-nostdinc',
                   '-I', str(SDK), '-fuse-ld=' + linker, str(source), str(SDK / 'bridge.c'),
                   '-Wl,--no-entry,--export=hw_state,--export=hw_config,--export=hw_step',
                   '-Wl,--initial-memory=131072,--max-memory=1048576,-z,stack-size=32768',
                   '-Wl,--strip-all', '-o', str(output)]
        try:
            result = subprocess.run(command, capture_output=True, timeout=15)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError('Bot compilation failed or exceeded 15 seconds.') from exc
        if result.returncode:
            raise ValueError(result.stderr.decode('utf-8', 'replace')[-3000:])
        data = output.read_bytes()
    validate_wasm(data)
    return data


def run_bots(jobs):
    """One isolated runtime process per batch; no user-provided JavaScript."""
    node = shutil.which('node')
    if not node:
        raise ValueError('Hosting C bots requires Node.js. See the Hex Wars guide.')
    requests = []
    for data, state in jobs:
        validate_wasm(data)
        requests.append(dict(wasm=base64.b64encode(data).decode('ascii'), state=state))
    try:
        result = subprocess.run([node, '--max-old-space-size=64', str(SDK / 'runner.js')],
                                input=json.dumps(requests).encode(), capture_output=True,
                                timeout=2, env={'PATH': os.environ.get('PATH', '')})
        if result.returncode or len(result.stdout) > 8192:
            raise ValueError('Bot runtime failed.')
        replies = json.loads(result.stdout)
        if not isinstance(replies, list) or len(replies) != len(jobs):
            raise ValueError('Invalid bot runtime reply.')
        return replies
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        raise ValueError('Bot runtime failed or exceeded its time limit.') from exc


def inspect_bot(data):
    result = run_bots([(data, None)])[0]
    attrs = result.get('attributes')
    if (result.get('error') or not isinstance(attrs, list) or len(attrs) != 3
            or any(type(n) is not int or not 1 <= n <= 5 for n in attrs) or sum(attrs) != 9):
        raise ValueError('Invalid bot: exports must match the SDK; attributes must be 1..5 and total 9. '
                         + result.get('error', ''))
    return attrs

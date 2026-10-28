#!/usr/bin/env python3
"""Resolve tmux without administrator rights; print its executable on stdout."""
import argparse
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile


def root_path():
    return Path(os.environ.get('FORTYTWO_TOOLS_ROOT', str(Path.home()/'.local/share/42-tools'))) / 'tmux'


def check(binary):
    result=subprocess.run([str(binary),'-V'],capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('tmux cannot run with the available system libraries.')


def ensure(root=None):
    existing=shutil.which('tmux')
    if existing:
        check(existing)
        return Path(existing)
    root=Path(root) if root is not None else root_path()
    wrapper=root/'bin/tmux'
    if wrapper.is_file():
        check(wrapper)
        return wrapper
    if sys.platform=='darwin':
        if not shutil.which('brew'):
            raise RuntimeError('Install Homebrew from https://brew.sh, then rerun setup.')
        subprocess.run(['brew','install','tmux'],check=True,stdout=sys.stderr)
        binary=shutil.which('tmux')
        if not binary:raise RuntimeError('Homebrew finished but tmux is not on PATH; load brew shellenv and retry.')
        check(binary)
        return Path(binary)
    required=('apt-get','apt-cache','dpkg-deb')
    if not all(shutil.which(tool) for tool in required):
        raise RuntimeError('No supported user-level tmux package source. Use a school-provided tmux on PATH, or run lan42_here without tmux.')
    # Read the distro's existing package metadata; no apt update/install or sudo.
    dependencies=subprocess.run(['apt-cache','depends','tmux'],capture_output=True,text=True,check=True).stdout
    packages=['tmux']
    for line in dependencies.splitlines():
        match=re.fullmatch(r'\s*(?:PreDepends|Depends):\s*([a-z0-9][a-z0-9+.-]*)(?::[a-z0-9]+)?\s*',line)
        if match and match[1] not in ('libc6','libc-bin'):
            packages.append(match[1])
    packages=list(dict.fromkeys(packages))
    if len(packages)>20:raise RuntimeError('Unexpected tmux dependency list; stopping user-level setup.')
    root.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='tmux-download-',dir=root.parent) as tmp:
        download=Path(tmp)
        print('Preparing user-level tmux from configured Ubuntu/Debian repositories (no sudo).',file=sys.stderr)
        subprocess.run(['apt-get','download',*packages],cwd=download,check=True,stdout=sys.stderr)
        archives=list(download.glob('*.deb'))
        if len(archives)!=len(packages):raise RuntimeError('Incomplete tmux package download; retry when package mirrors are available.')
        payload=download/'payload';payload.mkdir()
        for archive in archives:
            subprocess.run(['dpkg-deb','--extract',str(archive),str(payload)],check=True,stdout=sys.stderr)
        binary=payload/'usr/bin/tmux'
        if not binary.is_file():raise RuntimeError('Downloaded package did not contain tmux.')
        # Never extract a replacement libc/loader. Libraries remain private to
        # this wrapper; do not export LD_LIBRARY_PATH into the user's shell.
        libs=[payload/'usr/lib',payload/'lib']
        libs += [p for base in list(libs) if base.is_dir() for p in base.iterdir() if p.is_dir()]
        env=dict(os.environ,LD_LIBRARY_PATH=os.pathsep.join(str(p) for p in libs))
        result=subprocess.run([str(binary),'-V'],env=env,capture_output=True,text=True)
        if result.returncode:raise RuntimeError('User-level tmux failed its library check. Use lan42_here; ask the school for an available tmux build.')
        root.mkdir(parents=True,exist_ok=True)
        installed=root/'payload'
        if installed.exists():shutil.rmtree(installed)
        shutil.move(str(payload),str(installed))
    libpaths=[str(installed/p.relative_to(payload)) for p in libs]
    wrapper.parent.mkdir(parents=True,exist_ok=True)
    wrapper.write_text('#!/bin/sh\nLD_LIBRARY_PATH='+shlex.quote(os.pathsep.join(libpaths))+'${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH} exec '+shlex.quote(str(installed/'usr/bin/tmux'))+' "$@"\n')
    wrapper.chmod(0o700)
    check(wrapper)
    return wrapper


def confirm_install(root=None):
    """Check existing executables freely; obtain consent before installation."""
    if shutil.which('tmux') or ((Path(root) if root is not None else root_path())/'bin/tmux').is_file():
        return True
    plan=('Install tmux using your existing Homebrew.' if sys.platform=='darwin' else
          'Download/extract tmux and direct libraries into your account; no sudo or system packages.')
    print('tmux is missing. '+plan, file=sys.stderr)
    print('Help install tmux? [y/N]: ',end='',flush=True,file=sys.stderr)
    return sys.stdin.readline().strip().lower() in ('y','yes')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path)
    args=parser.parse_args()
    try:
        if not confirm_install(args.root):
            sys.exit('tmux installation skipped. Use lan42_here or rerun setup to enable workspace support.')
        print(ensure(args.root))
    except (OSError,RuntimeError,subprocess.SubprocessError) as error:
        sys.exit('tmux setup: '+str(error)+' No system packages were installed. Rerun setup after fixing the error.')

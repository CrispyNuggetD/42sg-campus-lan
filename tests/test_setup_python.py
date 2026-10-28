"""Exercise consent and private Python binding with a fake uv, no downloads."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class PythonSetup(unittest.TestCase):
    def attempt(self,answer):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);tools=root/'tools';bin=root/'bin';bin.mkdir()
            uv=bin/'uv'
            uv.write_text('#!/bin/sh\necho "$*" >> "$TEST_ROOT/calls"\ncase "$2" in find) echo "$TEST_ROOT/managed-python" ;; esac\n')
            uv.chmod(0o700)
            runtime=root/'managed-python';runtime.write_text('#!/bin/sh\nexit 0\n');runtime.chmod(0o700)
            script='''
. "$1"
python_works() { case "$1" in */managed-python) return 0 ;; *) return 1 ;; esac; }
setup_python
'''
            result=subprocess.run(['sh','-c',script,'test',str(ROOT/'useful-scripts/setup_python.sh')],input=answer,text=True,capture_output=True,
                 env=dict(os.environ,PATH=str(bin)+os.pathsep+os.environ['PATH'],TEST_ROOT=tmp,FORTYTWO_TOOLS_ROOT=str(tools)))
            calls=(root/'calls').read_text() if (root/'calls').exists() else ''
            bound=(tools/'python/bin/python3').is_symlink()
            return result,calls,bound

    def test_decline_and_eof_do_not_install(self):
        for answer in ('n\n','\n',''):
            result,calls,bound=self.attempt(answer)
            self.assertNotEqual(result.returncode,0)
            self.assertEqual(calls,'');self.assertFalse(bound)
            self.assertIn('[y/N]',result.stderr)

    def test_yes_installs_validates_and_binds_private_runtime(self):
        result,calls,bound=self.attempt('y\n')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(calls.splitlines(),['python install 3.11','python find --managed-python 3.11'])
        self.assertTrue(bound)

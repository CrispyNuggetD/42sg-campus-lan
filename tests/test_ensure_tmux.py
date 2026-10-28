"""Private package extraction only; no real downloads or package-manager writes."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock,patch

spec=importlib.util.spec_from_file_location('ensure_tmux',Path(__file__).resolve().parents[1]/'useful-scripts/ensure_tmux.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class Rootless(unittest.TestCase):
    def test_consent_defaults_to_no_and_accepts_only_explicit_yes(self):
        import io
        for answer, expected in [('',False),('n\n',False),('y\n',True),('yes\n',True),('maybe\n',False)]:
            with tempfile.TemporaryDirectory() as tmp, patch.object(m.shutil,'which',return_value=None), patch.object(m.sys,'stdin',io.StringIO(answer)), patch.object(m.sys,'stderr',io.StringIO()):
                self.assertEqual(m.confirm_install(Path(tmp)/'absent'),expected)
                self.assertFalse((Path(tmp)/'absent').exists())

    def test_system_tmux_is_reused_without_download(self):
        with patch.object(m.shutil,'which',return_value='/usr/bin/tmux'),patch.object(m.subprocess,'run',return_value=Mock(returncode=0)) as run:
            self.assertEqual(str(m.ensure()),'/usr/bin/tmux')
            run.assert_called_once_with(['/usr/bin/tmux','-V'],capture_output=True,text=True)

    def test_download_extract_verify_and_private_wrapper(self):
        calls=[]
        with tempfile.TemporaryDirectory(prefix="friend's tools ") as tmp:
            root=Path(tmp)/'install'
            def run(args,**kwargs):
                calls.append(args)
                if args[:2]==['apt-cache','depends']:
                    return Mock(stdout='tmux\n Depends: libc6\n Depends: libevent-core-2.1-7\n Depends: libtinfo6\n',returncode=0)
                if args[:2]==['apt-get','download']:
                    for name in args[2:]:(Path(kwargs['cwd'])/(name+'.deb')).touch()
                if args[:2]==['dpkg-deb','--extract']:
                    binary=Path(args[-1])/'usr/bin/tmux';binary.parent.mkdir(parents=True,exist_ok=True);binary.touch()
                return Mock(returncode=0,stdout='tmux test')
            with patch.object(m.sys,'platform','linux'),patch.object(m.shutil,'which',side_effect=lambda name:None if name=='tmux' else '/usr/bin/'+name),patch.object(m.subprocess,'run',side_effect=run):
                wrapper=m.ensure(root)
            self.assertTrue(wrapper.is_file())
            self.assertTrue((root/'payload/usr/bin/tmux').is_file())
            self.assertIn('LD_LIBRARY_PATH=',wrapper.read_text())
            self.assertIn('"$@"',wrapper.read_text())
            self.assertIn(['apt-get','download','tmux','libevent-core-2.1-7','libtinfo6'],calls)
            self.assertFalse(any('sudo' in c or 'install' in c or 'update' in c for c in calls))

    def test_download_failure_never_publishes_wrapper(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'install'
            with patch.object(m.sys,'platform','linux'),patch.object(m.shutil,'which',side_effect=lambda name:None if name=='tmux' else '/usr/bin/'+name),patch.object(m.subprocess,'run',side_effect=[Mock(stdout='',returncode=0),subprocess.CalledProcessError(1,['apt-get','download'])]):
                with self.assertRaises(subprocess.CalledProcessError):m.ensure(root)
            self.assertFalse((root/'bin/tmux').exists())

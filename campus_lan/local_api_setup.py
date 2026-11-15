"""Explicit local operator setup; no TLS broker, listener or service installation."""
import getpass
import json
import subprocess
import sys
import warnings
from .auth import AuthError,config_dir,private_read,private_write


def setup():
    if not sys.stdin.isatty():
        raise AuthError('Run API setup in an interactive terminal; credentials are entered privately.')
    print('Standalone Singapore API: owner-controlled device setup.')
    print('Uses your private 42 application UID and secret; verifies the existing hnah operator through the Singapore campus endpoint.')
    print('Saves credentials mode 600 outside Git. No campus host, browser sign-in, TLS certificates or systemd required.')
    print('Existing host/operator revocations still apply. This does not claim the device is on campus or enable public sign-in hosting.')
    if input('Set up standalone API access on this device? [y/N]: ').strip().lower() not in ('y','yes'):
        print('API setup skipped. Guest mode remains available.')
        return False
    path=config_dir()/'auth-server.json'
    if path.exists():
        settings=json.loads(private_read(path))
        if not isinstance(settings,dict) or not all(isinstance(settings.get(k),str) and settings[k].strip() for k in ('client_id','client_secret')):
            raise AuthError('Existing API configuration is incomplete; it was not overwritten.')
        print('Reusing existing private application configuration.')
    else:
        # Refuse getpass fallback that would echo credentials into a terminal/log.
        with warnings.catch_warnings():
            warnings.simplefilter('error',getpass.GetPassWarning)
            try:
                client_id=getpass.getpass('42 application UID (hidden): ').strip()
                client_secret=getpass.getpass('42 application secret (hidden): ').strip()
            except getpass.GetPassWarning:
                raise AuthError('Hidden credential entry unavailable; use an interactive iSH shell.') from None
        if not client_id or not client_secret:
            raise AuthError('Application UID and secret are required; nothing was saved.')
        private_write(path,json.dumps(dict(client_id=client_id,client_secret=client_secret,
                                          standalone_api=True,access_policy_version=1)))
    subprocess.run([sys.executable,'-m','campus_lan.access','enroll-local'],check=True)
    from .access import Policy
    Policy().local_operator()
    print('Standalone API ready. Run lan42, then /clusters (or F3).')
    print('Guest/root is still your mesh nickname; local API access does not sign that nickname in as hnah.')
    return True


def main():
    try:setup()
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('Standalone API setup did not complete. Check private credentials, network and enrollment; no service was started.',file=sys.stderr)
        raise SystemExit(1) from None


if __name__=='__main__':main()

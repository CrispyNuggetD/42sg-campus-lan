"""Server-owned access policy. Nicknames, client roles and IPs confer no privilege."""
from functools import lru_cache
import copy
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
from .auth import AuthError, config_dir, private_read, private_write

SG_CAMPUS_ID = 64
INITIAL_OWNER_UID = 234449  # hnah; resolved against the SG campus endpoint.
DEFAULT = dict(schema=1, campus_id=SG_CAMPUS_ID, admins=[INITIAL_OWNER_UID],
               api_operators=[INITIAL_OWNER_UID], approved_hosts=[])


@lru_cache(maxsize=1)
def host_id():
    """Local fingerprint only; never export raw hardware identifiers."""
    if platform.system() == 'Linux':
        try:value=Path('/etc/machine-id').read_text().strip()
        except OSError:raise AuthError('Cannot identify this host; host approval is required.') from None
    elif platform.system() == 'Darwin':
        try:
            output=subprocess.check_output(['ioreg','-rd1','-c','IOPlatformExpertDevice'],text=True,timeout=5)
            value=re.search(r'"IOPlatformUUID"\s*=\s*"([^"]+)"',output).group(1)
        except (OSError,subprocess.SubprocessError,AttributeError):
            raise AuthError('Cannot identify this host; host approval is required.') from None
    else:raise AuthError('Host enrollment supports Linux and macOS.')
    return hashlib.sha256(('lan42-host-v1:'+value).encode()).hexdigest()


class Policy:
    def __init__(self, data=None):
        if data is None:
            try:data=json.loads(private_read(config_dir()/'access-policy.json'))
            except FileNotFoundError:data=copy.deepcopy(DEFAULT)
        if (not isinstance(data,dict) or set(data)!=set(DEFAULT) or data['schema']!=1
                or type(data['campus_id']) is not int or data['campus_id']!=SG_CAMPUS_ID
                or any(not isinstance(data[k],list) or any(type(v) is not int or v<=0 for v in data[k]) for k in ('admins','api_operators'))
                or not data['admins'] or not isinstance(data['approved_hosts'],list)
                or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in data['approved_hosts'])):
            raise AuthError('Invalid private LAN42 access policy; access denied.')
        self.data=copy.deepcopy(data)

    def save(self):
        private_write(config_dir()/'access-policy.json',json.dumps(self.data,indent=2))

    def is_admin(self, uid):
        return type(uid) is int and uid in self.data['admins']

    def require_member(self, person):
        if (not isinstance(person,dict) or type(person.get('uid')) is not int
                or person['uid']<=0 or person.get('sg_member') is not True or person.get('campus_id')!=SG_CAMPUS_ID):
            raise AuthError('Verified 42 Singapore membership is required for API-backed views.')
        return person

    def require_host(self):
        if host_id() not in self.data['approved_hosts'] and not self.campus_owner_host():
            raise AuthError('This machine is not an approved API host. Use python3 -m campus_lan.access enroll-local on an owner-controlled host.')

    def campus_owner_host(self):
        """Explicit account-scoped campus hosting; never inferred from client identity."""
        import os
        import pwd
        if platform.system() != 'Linux':return False
        try:
            grant=json.loads(private_read(config_dir()/'campus-owner-host.json'))
        except FileNotFoundError:return False
        if grant != dict(schema=1, uid=INITIAL_OWNER_UID, os_account='hnah'):
            return False
        if pwd.getpwuid(os.getuid()).pw_name != 'hnah':return False
        if INITIAL_OWNER_UID not in self.data['admins']:return False
        try:
            operator=json.loads(private_read(config_dir()/'local-operator.json'))
            if operator.get('uid') != INITIAL_OWNER_UID:return False
            from .auth_daily import current_seat
            current_seat()  # Valid seat hostname AND locally assigned campus IP.
        except (OSError,ValueError,KeyError):return False
        return True

    def local_operator(self, admin=False):
        self.require_host()
        try:record=json.loads(private_read(config_dir()/'local-operator.json'))
        except FileNotFoundError:raise AuthError('Local API operator enrollment is required.') from None
        uid=record.get('uid') if isinstance(record,dict) else None
        if type(uid) is not int or uid not in self.data['admins' if admin else 'api_operators']:
            raise AuthError('Local operator is not allowed to perform this action.')
        return uid


def sg_member(user):
    return isinstance(user,dict) and any(isinstance(c,dict) and c.get('campus_id')==SG_CAMPUS_ID
                                       for c in (user.get('campus_users') or []))


def migrate_legacy_host():
    """Owner-authorized upgrade of a pre-policy, managed campus host; never sign-in enrollment."""
    import fcntl
    import os
    import pwd
    import ssl
    import stat
    root=config_dir()
    if not (root/'auth-server.json').exists():return False
    info=root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid!=os.getuid() or info.st_mode & 0o077:
        raise AuthError('Legacy host configuration must be private and owned by the current user.')
    fd=os.open(root/'access-init.lock',os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'r+') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        private_read(root/'access-init.lock')  # Validate existing lock ownership/mode too.
        settings=json.loads(private_read(root/'auth-server.json'))
        if not isinstance(settings,dict):raise AuthError('Invalid legacy host configuration.')
        if (root/'access-policy.json').exists() or (root/'access-policy.json').is_symlink():
            Policy()  # An invalid/revoked policy is never replaced by migration.
            if settings.get('access_policy_version') is None:
                settings['access_policy_version']=1
                private_write(root/'auth-server.json',json.dumps(settings))
            return False
        if settings.get('access_policy_version') is not None:
            raise AuthError('This host already uses explicit access policy; missing policy cannot be auto-approved.')
        if pwd.getpwuid(os.getuid()).pw_name!='hnah':return False
        from .auth_daily import current_seat
        current_seat()  # Checks both the campus hostname and actual local address.
        import ipaddress
        try:old=ipaddress.IPv4Address(settings.get('host',''))
        except (ValueError,TypeError):raise AuthError('Legacy campus host address is invalid.') from None
        if old.packed[:2] not in (b'\x0a\x0b',b'\x0a\x0c'):
            raise AuthError('Only an existing campus host can use the automatic upgrade.')
        if (settings.get('owner_login') not in (None,'hnah')
                or not isinstance(settings.get('host_generation'),str)
                or not re.fullmatch('[a-f0-9]{32}',settings['host_generation'])):
            raise AuthError('Automatic upgrade requires the existing managed hnah host.')
        from .auth_client import validate_trust
        trust=validate_trust(json.loads(private_read(root/'auth-trust.json')))
        certificate=private_read(root/'auth-cert.pem').decode()
        if trust['certificate'].strip()!=certificate.strip():raise AuthError('Legacy certificate and trust disagree.')
        private_read(root/'auth-key.pem')
        context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(root/'auth-cert.pem',root/'auth-key.pem')
        from .campus_info import API
        person=API(enrollment=True).member_profile(str(INITIAL_OWNER_UID))
        if person.get('id')!=INITIAL_OWNER_UID or person.get('login')!='hnah' or not sg_member(person):
            raise AuthError('The initial Singapore owner could not be verified.')
        policy=Policy();policy.data['approved_hosts']=[host_id()]
        # Write operator identity first: interruption before the policy commit can
        # safely retry. Once a policy exists, this upgrade never approves again.
        private_write(root/'local-operator.json',json.dumps(dict(uid=INITIAL_OWNER_UID)))
        policy.save()
        settings['access_policy_version']=1
        private_write(root/'auth-server.json',json.dumps(settings))
        print('LAN42 upgraded the existing hnah campus host access policy. Future starts reuse it.')
        return True


def main():
    import argparse
    parser=argparse.ArgumentParser(description='Private local policy management; never exposed as a guest/network command.')
    sub=parser.add_subparsers(dest='action',required=True)
    enroll=sub.add_parser('enroll-local',help='Bootstrap hnah or enroll an approved machine/operator')
    enroll.add_argument('--uid',type=int,default=INITIAL_OWNER_UID)
    sub.add_parser('host-id',help='Print only this machine fingerprint for an admin to approve')
    sub.add_parser('show',help='Show non-secret role IDs and host fingerprints')
    for action in ('grant','revoke'):
        p=sub.add_parser(action);p.add_argument('role',choices=('admin','api-operator'));p.add_argument('uid',type=int)
    for action in ('approve-host','revoke-host'):
        p=sub.add_parser(action);p.add_argument('fingerprint')
    args=parser.parse_args();policy=Policy()
    if args.action=='host-id':
        print(host_id());return
    if args.action=='show':
        print(json.dumps(policy.data,indent=2));return
    if args.action=='enroll-local':
        # The bootstrap authority is the local account already holding the app secret.
        # Verify the fixed initial owner through a campus-scoped lookup before writing.
        ident=host_id()
        bootstrap=not (config_dir()/'access-policy.json').exists()
        if bootstrap and args.uid!=INITIAL_OWNER_UID:raise AuthError('Only hnah can bootstrap the policy.')
        if not bootstrap and ident not in policy.data['approved_hosts']:
            raise AuthError('An existing admin must explicitly approve this host first.')
        if args.uid not in policy.data['api_operators'] and args.uid not in policy.data['admins']:
            raise AuthError('This UID is not an allowed local administrator or API operator.')
        from .campus_info import API
        api=API(enrollment=True)
        owner=api.member_profile(str(args.uid))
        if owner.get('id')!=args.uid or not sg_member(owner):
            raise AuthError('Local identity could not be verified as a Singapore member.')
        if bootstrap:
            if owner.get('login')!='hnah':raise AuthError('Only hnah can bootstrap the policy.')
            policy.data['approved_hosts'].append(ident)
        policy.save();private_write(config_dir()/'local-operator.json',json.dumps(dict(uid=args.uid)))
        print('Approved host/operator enrollment completed. No service was started.');return
    policy.local_operator(admin=True)
    if args.action in ('grant','revoke'):
        key={'admin':'admins','api-operator':'api_operators'}[args.role]
        if args.uid<=0:raise AuthError('A positive 42 user ID is required.')
        if args.action=='grant':
            from .campus_info import API
            API().member_profile(str(args.uid))  # Reject non-SG/unknown targets before granting.
            if args.uid not in policy.data[key]:policy.data[key].append(args.uid)
        else:
            policy.data[key]=[uid for uid in policy.data[key] if uid!=args.uid]
            if not policy.data['admins']:raise AuthError('Cannot remove the last admin.')
    else:
        if not re.fullmatch('[a-f0-9]{64}',args.fingerprint):raise AuthError('Expected a host fingerprint.')
        if args.action=='approve-host':
            if args.fingerprint not in policy.data['approved_hosts']:policy.data['approved_hosts'].append(args.fingerprint)
        else:policy.data['approved_hosts']=[v for v in policy.data['approved_hosts'] if v!=args.fingerprint]
    policy.save();print('Private access policy updated; new permission checks apply immediately.')

if __name__=='__main__':
    try:main()
    except (OSError,ValueError,KeyError,TypeError):
        raise SystemExit('Access-policy operation denied or failed. Check local enrollment, permissions and SG identity.') from None

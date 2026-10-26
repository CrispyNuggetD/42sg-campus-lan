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
        if host_id() not in self.data['approved_hosts']:
            raise AuthError('This machine is not an approved API host. Use python3 -m campus_lan.access enroll-local on an owner-controlled host.')

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

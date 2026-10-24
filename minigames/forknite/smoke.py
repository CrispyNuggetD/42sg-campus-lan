"""Integration test: real HTTP lobby, slot ownership, SSE history, native stdout."""
import os, pathlib, subprocess, time, urllib.request, json, tempfile, socket
root = pathlib.Path(__file__).resolve().parent
before = set((root / '.logs').glob('*'))
with socket.socket() as s:
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
with tempfile.TemporaryDirectory() as tmp:
    fixture = pathlib.Path(tmp) / 'philo'
    fixture.write_text('#!/bin/sh\nprintf "0 1 has taken a fork\\n0 1 is eating\\n130 2 died\\n"\n')
    fixture.chmod(0o700)
    binary = os.environ.get('PHILO_BINARY', str(fixture))
    p = subprocess.Popen(['node', 'server.js', '--host', '127.0.0.1', '--port', str(port), '--exec', binary, '--', '50','130','60','60','2'], cwd=str(root), env={**{k:v for k,v in os.environ.items() if not k.startswith('FORTYTWO_')},'XDG_CACHE_HOME':tmp}, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    base = 'http://127.0.0.1:' + str(port)
    def join(data):
        req = urllib.request.Request(base+'/join', data=json.dumps(data).encode(), headers={'Content-Type':'application/json'})
        return json.load(urllib.request.urlopen(req))
    try:
        for _ in range(50):
            try:
                assert urllib.request.urlopen(base).status == 200
                break
            except OSError:
                time.sleep(.1)
        else:
            raise AssertionError('server did not start')
        assert json.load(urllib.request.urlopen(base+'/auth/me')) == {'enabled': False, 'user': None}
        claim = join({'id':1,'name':'hnah','verified':True,'avatar':'https://attacker.example/fake.jpg'})
        assert claim['token']
        try:
            join({'id':1,'name':'thtay'})
            raise AssertionError('duplicate claim accepted')
        except urllib.error.HTTPError as e:
            assert e.code == 409
        join({'id':1,'name':'hnah','token':claim['token']})
        p.stdin.write(b'start\n'); p.stdin.flush()
        time.sleep(1.5)
        with urllib.request.urlopen(base+'/events', timeout=4) as stream:
            snapshot = json.loads(stream.readline().decode()[6:])
        moves = [e for e in snapshot['events'] if e['type']=='move']
        assert moves
        if 'PHILO_BINARY' not in os.environ:
            assert any(e['action']=='died' for e in moves), moves[-5:]
        assert any(e['type']=='end' for e in snapshot['events'])
        assert snapshot['players'][0]['name']=='hnah'
        assert snapshot['players'][0]['verified'] is False
        assert snapshot['players'][0]['avatar'] is None
        print('PASS: lobby, ownership, native output, end, late-viewer history')
    finally:
        p.terminate()
        try: p.wait(timeout=4)
        except subprocess.TimeoutExpired: p.kill(); p.wait()
        for f in set((root / '.logs').glob('*')) - before:
            f.unlink()

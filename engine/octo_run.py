import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
#!/usr/bin/env python3
"""/octo runner. Usage: python3 octo_run.py [seed=N] [start=USD] [profit=USD] [tokens=N] [trades=N] [name=...] [cta=WORD]
Writes octo_cfg.json, renders 5 scenes in parallel, builds audio, muxes with loudnorm, prints summary."""
import sys, os, json, time, subprocess
B = _BASE; sys.path.insert(0, B)
import octo_gen
a = dict(x.split('=', 1) for x in sys.argv[1:])
seed = int(a.get('seed', int(time.time()) % 100000))
p = octo_gen.make_params(seed)
if 'start' in a: p['start'] = int(a['start'])
if 'profit' in a: p['profit'] = int(a['profit'])
if 'tokens' in a: p['shortlist'] = int(a['tokens'])
if 'trades' in a: p['trades'] = int(a['trades'])
p['name'] = a.get('name', 'OCTO AI'); p['cta'] = a.get('cta', 'OCTO')
tr = octo_gen.make_trades(p)
assert abs(tr[-1]['after'] - (p['start'] + p['profit'])) < 0.01 and tr[0]['win'] and tr[-1]['win']
cfgp = f'{B}/octo_cfg.json'; json.dump(p, open(cfgp, 'w'))
env = dict(os.environ, OCTO_CFG=cfgp)
sc = [('a', 0, 2.4), ('b', 2.4, 6.0), ('c', 6.0, 14.4), ('d', 14.4, 25.2), ('e', 25.2, 30.0)]
ps = [subprocess.Popen(['python3', f'{B}/core19.py', 'scene', n, str(t0), str(t1)], env=env, cwd=B) for n, t0, t1 in sc]
rc = subprocess.run(['python3', f'{B}/audio19.py'], env=env, cwd=B).returncode
assert rc == 0 and all(x.wait() == 0 for x in ps), 'render failed'
open(f'{B}/list19.txt', 'w').write(''.join(f"file 's19_{n}.mp4'\n" for n, _, _ in sc))
out = _os.path.join(_BASE, 'out', f'OCTO_AI_V6_seed{seed}.mp4')
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', f'{B}/list19.txt', '-c', 'copy', f'{B}/v19_silent.mp4'], check=True)
subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', f'{B}/v19_silent.mp4', '-i', f'{B}/audio19.wav', '-map', '0:v', '-map', '1:a', '-c:v', 'copy',
                '-af', 'loudnorm=I=-14:TP=-1.5:LRA=7', '-c:a', 'aac', '-b:a', '192k', '-shortest', out], check=True)
r = subprocess.run(['ffmpeg', '-hide_banner', '-nostats', '-i', out, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
print(out); print(p); print([l.strip() for l in r.splitlines()[-14:] if 'I:' in l or 'Peak:' in l])

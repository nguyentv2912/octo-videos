import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
import numpy as np, wave, math, sys
sys.path.insert(0, _BASE)
import core19 as C

SR = 44100
TOTAL = 30.0
N = int(TOTAL * SR)
rng = np.random.default_rng(7)
drums = [np.zeros(N, np.float32), np.zeros(N, np.float32)]
mel = [np.zeros(N, np.float32), np.zeros(N, np.float32)]
sfx = [np.zeros(N, np.float32), np.zeros(N, np.float32)]

def tt(d): return np.arange(int(d * SR)) / SR

def add_raw(bus, t0, sig, gain=1.0, pan=0.0):
    i = int(round(t0 * SR))
    if i >= N or i + len(sig) <= 0: return
    sig = np.asarray(sig, np.float32)
    if i < 0:
        sig = sig[-i:]; i = 0
    seg = sig[:N - i]
    l = math.cos((pan + 1) * math.pi / 4); r = math.sin((pan + 1) * math.pi / 4)
    bus[0][i:i + len(seg)] += seg * gain * l * 1.414
    bus[1][i:i + len(seg)] += seg * gain * r * 1.414

_ENG = [0.0, 1.6, 3.2, 9.6, 22.4, 38.4, 42.5, 44.8]; _OUT = [0.0, 1.2, 2.4, 6.0, 14.4, 25.2, 27.6, 30.0]
def Wf(x): return float(np.interp(x, _ENG, _OUT))
def add(bus, t0, sig, gain=1.0, pan=0.0):
    add_raw(bus, Wf(t0) if bus is sfx else t0, sig, gain, pan)

def kick():
    t = tt(0.42)
    f = 42 + 140 * np.exp(-t * 32)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(ph) * np.exp(-t * 7.0) + 0.3 * np.sin(2 * np.pi * 1800 * t) * np.exp(-t * 220)

def hat(open_=False):
    t = tt(0.22 if open_ else 0.05)
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    return n * np.exp(-t * (16 if open_ else 90)) * 0.5

def clap():
    t = tt(0.28)
    n = rng.standard_normal(len(t))
    n = np.convolve(n, np.ones(4) / 4, 'same') - np.convolve(n, np.ones(40) / 40, 'same')
    env = np.exp(-t * 20) * (0.6 + 0.4 * (np.sin(2 * np.pi * 70 * t) > 0))
    return n * env * 1.1

def bass(f, d):
    t = tt(d)
    saw = 2 * ((f * t) % 1) - 1
    lp = np.convolve(saw, np.ones(22) / 22, 'same')
    env = np.exp(-t * 3.2) * (1 - np.exp(-t * 300))
    return (0.75 * np.sin(2 * np.pi * f * t) + 0.5 * lp) * env

def pluck(f, d=0.4, decay=9.0, harm=3):
    t = tt(d)
    s = np.zeros_like(t)
    for h in range(1, harm + 1):
        s += np.sin(2 * np.pi * f * h * t) / h * np.exp(-t * (decay + 5 * h))
    return s * (1 - np.exp(-t * 600))

def whoosh(d=0.35):
    t = tt(d)
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    n = np.convolve(n, np.ones(6) / 6, 'same')
    return n * np.sin(np.pi * t / d) ** 2 * 0.9

def slash(d=0.3):
    t = tt(d)
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    k = 3 + int(10 * (1 - np.exp(-t[-1])))
    n = np.convolve(n, np.ones(3) / 3, 'same')
    f = 5200 * np.exp(-t * 9) + 300
    return (n * 0.7 + np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.35) * np.exp(-t * 11)

def riser(d):
    t = tt(d); u = t / d
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    n = np.convolve(n, np.ones(3) / 3, 'same')
    f = 80 * (16 ** u)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return n * (u ** 2) * 0.55 + np.sin(ph) * (u ** 1.5) * 0.35

def boom(d=2.0, f0=40):
    t = tt(d)
    return np.sin(2 * np.pi * (f0 + 70 * np.exp(-t * 12)) * t) * np.exp(-t * 2.0)

def crash(d=3.0):
    t = tt(d)
    n = np.diff(rng.standard_normal(len(t)), prepend=0)
    return n * np.exp(-t * 1.7) * 0.6

def buzz(d=0.25):
    t = tt(d)
    saw = 2 * ((165 * t) % 1) - 1
    saw2 = 2 * ((171 * t) % 1) - 1
    return np.convolve(saw + saw2, np.ones(8) / 8, 'same') * np.exp(-t * 9) * 0.55


BEAT = 0.4; BAR = 1.6
FS = lambda m_: 440.0 * 2 ** ((m_ - 69) / 12)   # midi -> Hz
# F# minor: F#=66 (octave 4)
ROOTS = [92.50, 73.42, 110.0, 82.41]                    # F#2 D2 A2 E2
CHORDS = [[185.0, 220.0, 277.18], [146.83, 185.0, 220.0], [220.0, 277.18, 329.63], [164.81, 207.65, 246.94]]
HOOK_T = [0.0, 0.75, 1.5, 2.5]                          # beats inside bar
HOOK = [[739.99, 880.0, 1108.73, 880.0], [1174.66, 1108.73, 880.0, 739.99],
        [1318.51, 1108.73, 880.0, 1108.73], [987.77, 830.61, 987.77, 1318.51]]
MINI = [369.99, 440.0, 493.88, 554.37, 659.25, 739.99, 880.0, 987.77]
TB, TS = C.TB, C.TS
MONT0, MONT1 = C.MONT0, C.MONT1
DROP = 3.2

# ---- intro (0-3.2): riser, pad, boom, mini pop arpeggio
add(sfx, 0.0, riser(2.4), 0.6)
tp = tt(2.6)
pad0 = sum(np.sin(2 * np.pi * f * tp) for f in [92.5, 138.59, 185.0, 277.18]) / 4 * np.minimum(1, tp / 1.2) * np.minimum(1, (2.6 - tp) / 0.3)
add(mel, 0.0, pad0, 0.22)
add(sfx, 0.5, boom(1.2, 34), 0.5)
add(sfx, DROP, boom(1.8, 42), 0.95)
add(sfx, DROP, crash(1.8), 0.4)

M0o, M1o = Wf(MONT0), Wf(MONT1); DROPo = Wf(3.2); T64 = Wf(6.4); T96 = Wf(9.6); R0 = Wf(35.2)
# ---- drums
kicks = []
b = 0
while DROPo + b * BEAT < TOTAL - 1.0:
    tk = DROPo + b * BEAT
    kicks.append(tk)
    add(drums, tk, kick(), 0.95)
    add(drums, tk + BEAT / 2, hat(True), 0.28, 0.2)
    bar_i = int((tk - DROPo) // BAR)
    if tk >= T64:
        add(drums, tk + BEAT / 4, hat(False), 0.14, -0.2)
        add(drums, tk + 3 * BEAT / 4, hat(False), 0.14, 0.2)
    if tk >= T96 and b % 2 == 1:
        add(drums, tk, clap(), 0.55)
    if M0o - 0.4 <= tk < M1o:
        add(drums, tk + BEAT / 4, hat(False), 0.18, -0.3)
        add(drums, tk + BEAT * 0.75, hat(False), 0.18, 0.3)
        add(drums, tk + BEAT * 0.5 + BEAT / 8, hat(False), 0.12, 0.0)
    b += 1
# snare roll R0 -> 38.4
n_roll = 0; tr_ = R0
while tr_ < M1o:
    gap = max(0.05, 0.2 - 0.15 * (tr_ - R0) / (M1o - R0))
    add(drums, tr_, clap(), 0.3 + 0.35 * (tr_ - R0) / (M1o - R0))
    tr_ += gap

sc = np.ones(N, np.float32)
def duck_out(t0, depth=0.78, tau=0.13, span=0.45):
    i = int(t0 * SR); seg = min(int(span * SR), N - i)
    if seg <= 0: return
    x = np.arange(seg) / SR
    sc[i:i + seg] = np.minimum(sc[i:i + seg], 1 - depth * np.exp(-x / tau))
def duck(t0, *a_, **k_): duck_out(Wf(t0), *a_, **k_)
for tk in kicks: duck_out(tk)

# ---- harmony: pad + bass + hook
nb = int((TOTAL - DROPo) // BAR) + 1
for bar in range(nb):
    t_bar = DROPo + bar * BAR
    if t_bar >= TOTAL - 0.4: break
    ci = bar % 4; root = ROOTS[ci]; chord = CHORDS[ci]
    dpad = BAR + 0.4
    tp = tt(dpad)
    env = np.minimum(1, tp / 0.6) * np.minimum(1, (dpad - tp) / 0.4)
    padsig = sum(np.sin(2 * np.pi * f * tp) + 0.5 * np.sin(2 * np.pi * f * 2.003 * tp) for f in chord) / 6 * env
    add(mel, t_bar, padsig, 0.13 if t_bar < M1o else 0.24)
    pat = [1, 1, 2, 1, 1, 1, 2, 1.5]
    for k in range(8):
        tn = t_bar + k * BEAT / 2
        add(mel, tn, bass(root * pat[k] * 2, BEAT / 2 * 0.95), 0.62 if tn >= T64 else 0.5)
    # arpeggio 16ths (chord tones), sparser early
    seq = [0, 1, 2, 1, 0, 1, 2, 1, 2, 1, 0, 1, 2, 1, 0, 2]
    for k in range(16):
        tn = t_bar + k * BEAT / 4
        if tn < T64: continue
        f = chord[seq[k]] * 2
        if M0o <= tn < M1o and k % 4 == 3: f *= 2
        add(mel, tn, pluck(f, 0.26, 11.0, 3), 0.14 if tn < M0o else 0.2, -0.5 + (k % 2))
    # the hook
    if t_bar >= T64:
        for j in range(4):
            tn = t_bar + HOOK_T[j] * BEAT
            f = HOOK[ci][j]
            g = 0.26
            add(mel, tn, pluck(f, 0.5, 6.0, 4), g, -0.15 + 0.1 * j)
            if M0o <= tn < M1o or tn >= M1o:
                add(mel, tn, pluck(f * 2, 0.4, 7.0, 3), 0.15, 0.25)

# ---- funnel (3.2 -> 9.6)
for i in range(4):
    add(sfx, 3.2 + 0.3 * i, pluck(MINI[i + 2] * 2, 0.3, 10.0, 2), 0.3, -0.5 + 0.33 * i)
for j in range(70):
    add(sfx, 3.8 + j * (3.0 / 70), pluck(1500 + 8 * j, 0.04, 60.0, 1), 0.10, ((j % 2) * 2 - 1) * 0.5)
for j in range(30):
    add(sfx, 7.0 + j * (1.8 / 30), pluck(900 + 40 * j, 0.1, 30.0, 2), 0.2, 0.0)
add(sfx, 8.8, pluck(1318.5, 0.9, 5.0, 3), 0.5)
add(sfx, 8.9, pluck(1760, 0.9, 5.0, 3), 0.4)
add(sfx, 9.6, whoosh(0.4), 0.4)
for i in range(30):
    add(sfx, 9.8 + i * (1.6 / 30), pluck(1400 + 50 * i, 0.05, 40.0, 1), 0.18, ((i % 2) * 2 - 1) * 0.4)

# ---- mini signature notes (+ whoosh when a mini leaves its dock)
for (te, i) in C.note_events():
    add(sfx, te, pluck(MINI[i] * 2, 0.55, 5.5, 4), 0.34, -0.7 + 0.2 * i)
for i in range(1, 8):
    add(sfx, 9.6 + 1.6 * i + 0.2, whoosh(0.3), 0.3, -0.5 if i % 2 else 0.5)
for te in (3.6, 22.4, 22.4, 22.4):
    add(sfx, te, whoosh(0.5), 0.35)
for te in (39.0, ):
    add(sfx, te, whoosh(0.5), 0.35)

# ---- trade 1: BUY / SELL
add(sfx, TB, pluck(MINI[3] * 2, 0.4, 8.0, 3), 0.55)
add(sfx, TB + 0.05, pluck(783.99, 0.7, 6.0, 3), 0.5)
add(sfx, TB, boom(0.6, 55), 0.55); duck(TB, 0.4, 0.2, 0.4)
add(sfx, TB + 0.1, pluck(1568, 0.5, 8.0, 2), 0.3)
for tp_ in (16.9, 17.3, 17.7):
    add(sfx, tp_, pluck(880, 0.5, 8.0, 2), 0.2, 0.4)
add(sfx, TS, slash(0.4), 0.65); duck(TS, 0.4, 0.2, 0.4)
add(sfx, TS + 0.04, pluck(739.99, 0.5, 7.0, 3), 0.55)
add(sfx, TS + 0.16, pluck(1108.73, 0.9, 5.0, 3), 0.5)
add(sfx, TS, boom(0.6, 55), 0.5)
for k, f in enumerate([2093, 2637, 3136, 2637, 3520]):
    add(sfx, TS + 0.3 + 0.05 * k, pluck(f, 0.25, 14.0, 1), 0.2, 0.3)
add(sfx, 20.0, pluck(880, 0.5, 8.0, 2), 0.2)
add(sfx, 20.8, pluck(1568, 0.9, 5.0, 3), 0.4)
add(sfx, 21.4, pluck(1760, 1.0, 4.5, 3), 0.4)
for k, f in enumerate([1108.73, 1318.5, 1480, 2217]):
    add(sfx, 21.6 + 0.06 * k, pluck(f, 1.0, 4.5, 3), 0.4, -0.3 + 0.2 * k)

# ---- rapid fire
for k in range(2, C.NT + 1):
    ev = C.EV[k - 1]
    add(sfx, ev - 0.2, pluck(554.37 * 2, 0.18, 14.0, 2), 0.22)
    add(sfx, ev - 0.2, boom(0.2, 62), 0.28); duck(ev - 0.2, 0.3, 0.12, 0.25)
    add(sfx, ev, slash(0.22), 0.32, 0.2); duck(ev, 0.3, 0.12, 0.25)
    if C.TR[k - 1]['win']:
        add(sfx, ev + 0.03, pluck(1318.5, 0.35, 10.0, 3), 0.3, 0.3)
        add(sfx, ev + 0.10, pluck(1760.0, 0.35, 11.0, 3), 0.26, -0.3)
    else:
        add(sfx, ev + 0.02, buzz(0.3), 0.4)
        add(sfx, ev + 0.02, boom(0.3, 70), 0.35)

# ---- climax at 38.4
add(sfx, 35.2, riser(2.16), 0.65)
add(sfx, MONT1, boom(2.6, 38), 1.0)
add(sfx, MONT1, crash(3.4), 0.55)
duck(MONT1, 0.5, 0.25, 0.8)
for k, f in enumerate([185, 277.18, 369.99, 554.37, 739.99, 1108.73, 1479.98, 2217.46]):
    add(sfx, MONT1 + 0.06 * k, pluck(f, 1.6, 3.5, 3), 0.28, -0.7 + 0.2 * k)
for i in range(10):
    add(sfx, MONT1 + 0.3 * i, pluck(1108.73 if i % 2 else 1318.5, 0.2, 16.0, 2), 0.2, -0.2 + 0.05 * i)
for k, f in enumerate([369.99, 440.0, 554.37, 739.99]):
    add(sfx, 41.6, pluck(f, 3.0, 1.8, 3), 0.28, -0.3 + 0.2 * k)

# ---- V2 additions: hook impact, feature-trade impacts, end-card chime
add(sfx, 0.0, boom(1.2, 46), 0.9)
add(sfx, 0.0, crash(1.0), 0.35)
for j in C.FEAT:
    e = C.EV[j]
    add(sfx, e - 0.5, riser(0.5), 0.45)
    add(sfx, e, boom(0.9, 48), 0.7); duck(e, 0.6, 0.3, 0.6)
    add(sfx, e, crash(0.7), 0.3)
    for k_, f_ in enumerate([880.0, 1108.73, 1318.5, 1760.0]):
        add(sfx, e + 0.05 * k_, pluck(f_, 0.6, 6.0, 3), 0.28, -0.3 + 0.2 * k_)
for k_, f_ in enumerate([739.99, 880.0, 1108.73, 1479.98]):
    add(sfx, 42.4 + 0.08 * k_, pluck(f_, 1.2, 4.0, 3), 0.3, -0.3 + 0.2 * k_)

for (te_, ii_, tx_) in C.SIGE:
    add(sfx, te_, pluck(MINI[ii_] * 4, 0.12, 30.0, 1), 0.10, -0.6 + 0.17 * ii_)
add(sfx, 15.0, pluck(1318.5, 0.5, 8.0, 3), 0.22); add(sfx, 15.06, pluck(1760.0, 0.5, 8.0, 3), 0.2)
for i_ in range(8):
    add(sfx, 0.45 + 0.05 * i_ + 0.35, pluck(MINI[i_] * 2, 0.5, 6.0, 4), 0.30, -0.7 + 0.2 * i_)
add(sfx, 0.05, boom(1.6, 36), 0.8)
add(sfx, 1.6, whoosh(0.4), 0.35); add(sfx, 1.6, pluck(1108.73, 0.9, 4.0, 3), 0.25)
for (t0_, t1_, tx_, c_) in C.CAP18:
    add(sfx, t0_ - 0.05, whoosh(0.3), 0.28)
add(sfx, 42.5, boom(1.8, 38), 0.7)
outL = drums[0] + mel[0] * sc + sfx[0]
outR = drums[1] + mel[1] * sc + sfx[1]
fade = np.ones(N, np.float32)
fi = int(0.03 * SR); fo = int(1.8 * SR)
fade[:fi] = np.linspace(0, 1, fi)
fade[-fo:] = np.linspace(1, 0, fo) ** 1.5
outL *= fade; outR *= fade
k = 1.4
outL = np.tanh(k * outL) / math.tanh(k); outR = np.tanh(k * outR) / math.tanh(k)
pk = max(np.abs(outL).max(), np.abs(outR).max())
outL *= 0.89 / pk; outR *= 0.89 / pk
pcm = (np.stack([outL, outR], 1) * 32767).astype('<i2')
with wave.open(_BASE + '/audio19.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print('audio ok', N / SR, 's')

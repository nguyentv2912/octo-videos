import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
import numpy as np, cv2, math, sys, os, subprocess
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FPS = 30
TOTAL = 42.0
OUT = _BASE

def hexrgb(h):
    h = h.lstrip('#')
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

CY = hexrgb('#19F0FF'); CYD = hexrgb('#0E7F91'); PU = hexrgb('#A24BFF'); PUD = hexrgb('#4A2090')
MG = hexrgb('#FF3DDC'); GR = hexrgb('#2BFF9A'); RD = hexrgb('#FF4D6D'); WH = hexrgb('#E8F7FF')
DIM = hexrgb('#8393BD'); GOLD = hexrgb('#FFD35A'); PANEL = hexrgb('#0A1030'); INK = hexrgb('#04061A')

def m(c, a):
    a = max(0.0, min(1.0, a))
    return (int(c[0] * a), int(c[1] * a), int(c[2] * a))
def mix(c1, c2, u):
    u = max(0.0, min(1.0, u))
    return tuple(int(c1[k] + (c2[k] - c1[k]) * u) for k in range(3))
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def smooth(u):
    u = clamp(u); return u * u * (3 - 2 * u)
def easeout(u):
    u = clamp(u); return 1 - (1 - u) ** 3
def ramp(t, t0, t1): return clamp((t - t0) / (t1 - t0))

# ---------------------------------------------------------------- fonts
FD = '/usr/share/fonts/opentype/inter/'
FONTS = {'b': FD + 'Inter-Bold.otf', 'sb': FD + 'Inter-SemiBold.otf', 'md': FD + 'Inter-Medium.otf',
         'mono': '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'}
_fc = {}
def F(k, size):
    key = (k, int(size))
    if key not in _fc:
        _fc[key] = ImageFont.truetype(FONTS[k], int(size))
    return _fc[key]
def fit(s, k, size, maxw):
    while size > 10 and F(k, size).getlength(s) > maxw:
        size -= 1
    return size

# ---------------------------------------------------------------- data
TOKENS = ["NEBU", "PUMPKY", "KRAKI", "ZAPPY", "MOONPIE", "GLITCH", "VOLTA", "SHRIMPY", "BYTEY", "NOVAX",
          "TIDAL", "ORBIT", "PIXLE", "COSMO", "DRIFT", "FLUXO", "QUARK", "SPARKO", "LUMEN", "TURBO7",
          "COBALT", "MANTA", "HYPERX", "RIPPLY", "ECHOZ", "BLITZY", "ASTRO9", "NEONY", "OCTAVE", "PLASMA"]

def make_trades():
    rng = np.random.default_rng(11)
    order = np.array([1] * 22 + [0] * 8)
    rng.shuffle(order)
    if order[0] == 0:
        j = int(np.where(order == 1)[0][0]); order[0], order[j] = order[j], order[0]
    if order[-1] == 0:
        j = int(np.where(order == 1)[0][-1]); order[-1], order[j] = order[j], order[-1]
    w = rng.uniform(0.35, 1.0, 22)
    l = -rng.uniform(0.07, 0.20, 8)
    target = 83799.0 / 1000.0
    lo, hi = 0.0, 6.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if np.prod(1 + mid * w) * np.prod(1 + l) < target: lo = mid
        else: hi = mid
    k = (lo + hi) / 2
    ret = np.zeros(30); wi = li = 0
    for n in range(30):
        if order[n]: ret[n] = k * w[wi]; wi += 1
        else: ret[n] = l[li]; li += 1
    bal = [1000.0]
    for n in range(30):
        bal.append(round(bal[-1] * (1 + ret[n]), 2))
    bal[30] = 83799.0
    tr = []
    for n in range(30):
        pnl = bal[n + 1] - bal[n]
        tr.append(dict(win=bool(order[n]), pnl=pnl, before=bal[n], after=bal[n + 1], ret=pnl / bal[n], token=TOKENS[n]))
    return tr
import octocfg as OC
TOKENS[:] = OC.tokens()
TR = OC.build_trades(TOKENS)
R1 = TR[0]['ret']
ENTRY = 0.000420
EXIT1 = ENTRY * (1 + R1)

# ---------------------------------------------------------------- timeline
STEP0 = 9.0; STEPD = 2.0
MONT0 = 25.0; MONT1 = 34.0
DT = (MONT1 - MONT0) / 29
EV = [STEP0 + 14.7] + [MONT0 + (k - 1) * DT for k in range(2, 31)]
NAMES = ["SCAN", "CHART", "WALLET", "BUY", "TRACK", "SELL", "CHECK", "PNL"]
STEPCOL = [CY, CY, PU, GR, PU, MG, CY, GR]
AGN = [("SCOUT", CY, "Phát hiện và quét", "token Solana"),
       ("FILTER", PU, "Kiểm tra thanh khoản,", "rủi ro, chất lượng"),
       ("ANALYST", CY, "Phân tích biểu đồ", "và tín hiệu giao dịch"),
       ("EXECUTOR", GR, "Mô phỏng thực hiện", "lệnh BUY / SELL"),
       ("RISK", MG, "Giám sát rủi ro và", "mức tiếp xúc vốn"),
       ("LOGGER", GOLD, "Ghi nhận và tổng hợp", "kết quả giao dịch")]
AG_MAP = [[0, 1], [2], [4], [3], [2, 4], [3], [5], [5]]

def ext(t, ts, te, a, r):
    u = (t - ts) / (te - ts)
    if u <= 0 or u >= 1: return 0.0
    if u < a: return smooth(u / a)
    if u > 1 - r: return smooth((1 - u) / r)
    return 1.0

def tent_state(t):
    e = [0.0] * 8
    if STEP0 <= t < MONT0:
        for i in range(8):
            e[i] = ext(t, STEP0 + STEPD * i, STEP0 + STEPD * (i + 1), 0.18, 0.2)
    elif MONT0 <= t < MONT1 + 0.2:
        for k in range(2, 31):
            i = (k - 2) % 8; ev = EV[k - 1]
            e[i] = max(e[i], ext(t, ev - 0.55, ev + 0.1, 0.4, 0.4))
    if t >= MONT1:
        for i in range(8):
            up = easeout(ramp(t, MONT1, MONT1 + 0.8 + 0.07 * i))
            down = 1 - smooth(ramp(t, 36.6 + 0.05 * i, 37.6 + 0.05 * i))
            e[i] = max(e[i] if t < MONT1 + 0.2 else 0.0, up * down)
    return e

def agent_levels(t, e):
    L = [0.0] * 6
    for i in range(6):
        base = 0.35 if t >= 3.0 + i else 0.0
        act = 0.0
        if 3.0 + i <= t < 4.0 + i:
            act = math.sin(math.pi * (t - 3.0 - i)) ** 0.6
        L[i] = max(base, act)
    for s in range(8):
        for a in AG_MAP[s]:
            L[a] = max(L[a], 0.35 + 0.65 * e[s])
    if t >= MONT1:
        for i in range(6):
            L[i] = max(L[i], 0.72 + 0.28 * math.sin(t * 4 + i))
    return L

def counters(t):
    scanned = int(round(30 * smooth(ramp(t, 9.25, 10.85))))
    done = sum(1 for ev in EV if t >= ev)
    wins = sum(1 for k in range(done) if TR[k]['win'])
    losses = done - wins
    if done == 0:
        prev = 1000.0
        bal = 1000.0
    else:
        prev = TR[done - 1]['after']; bal = prev
    if done < 30:
        ev_n = EV[done]
        u = easeout(ramp(t, ev_n - 0.25, ev_n))
        bal = prev + (TR[done]['after'] - prev) * u
    return scanned, done, wins, losses, bal

# ---------------------------------------------------------------- background
def build_bg():
    yy = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    c0 = np.array(hexrgb('#05061A'), np.float32); c1 = np.array(hexrgb('#0D0828'), np.float32)
    c2 = np.array(hexrgb('#041622'), np.float32)
    img = np.broadcast_to(c0 + (c1 - c0) * yy, (H, W, 3)).copy()
    s = (np.clip((yy - 0.5) / 0.5, 0, 1)) ** 1.5
    img = img * (1 - s) + c2 * s
    Y, X = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((X - 540) ** 2 + ((Y - 520) * 1.15) ** 2)
    img += np.array(PU, np.float32) * (0.30 * np.exp(-(d / 430) ** 2))[..., None]
    d2 = np.sqrt((X - 540) ** 2 + (Y - 1100) ** 2)
    img += np.array(CY, np.float32) * (0.06 * np.exp(-(d2 / 560) ** 2))[..., None]
    img[:, ::60] += np.array(CY, np.float32) * 0.045
    img[::60, :] += np.array(CY, np.float32) * 0.045
    vr = np.sqrt(((X - 540) / 540) ** 2 + ((Y - 960) / 960) ** 2)
    img *= (1 - 0.40 * np.clip(vr, 0, 1.3) ** 2)[..., None]
    img[::4] *= 0.93
    return np.clip(img, 0, 255).astype(np.uint8)

_prng = np.random.default_rng(3)
PXS = _prng.uniform(0, W, 70); PYS = _prng.uniform(0, H, 70); PSP = _prng.uniform(10, 38, 70)
PPH = _prng.uniform(0, 6.28, 70); PCOL = [CY if i % 3 else PU for i in range(70)]

# ---------------------------------------------------------------- canvas
class Cv:
    def __init__(self, bg):
        self.f = bg.copy()
        self.g = np.zeros((H // 2, W // 2, 3), np.uint8)
        self.T = []
        self.flash = 0.0
    def poly(self, pts, col, th=2, glow=0.0, closed=False):
        p = np.round(np.asarray(pts, np.float32)).astype(np.int32)
        cv2.polylines(self.f, [p], closed, col, th, cv2.LINE_AA)
        if glow > 0:
            cv2.polylines(self.g, [p // 2], closed, m(col, glow), max(1, int(th * 0.8)) + 1, cv2.LINE_AA)
    def circle(self, c, r, col, th=-1, glow=0.0):
        cv2.circle(self.f, (int(round(c[0])), int(round(c[1]))), max(1, int(round(r))), col, th, cv2.LINE_AA)
        if glow > 0:
            cv2.circle(self.g, (int(c[0] / 2), int(c[1] / 2)), max(1, int(r / 2)), m(col, glow),
                       -1 if th < 0 else max(1, th // 2 + 1), cv2.LINE_AA)
    def ellipse(self, c, axes, col, th=-1, glow=0.0, ang=0, a0=0, a1=360):
        cv2.ellipse(self.f, (int(c[0]), int(c[1])), (int(axes[0]), int(axes[1])), ang, a0, a1, col, th, cv2.LINE_AA)
        if glow > 0:
            cv2.ellipse(self.g, (int(c[0] / 2), int(c[1] / 2)), (max(1, int(axes[0] / 2)), max(1, int(axes[1] / 2))),
                        ang, a0, a1, m(col, glow), -1 if th < 0 else max(1, th // 2 + 1), cv2.LINE_AA)
    def fillpoly(self, pts, col, a=1.0):
        if a <= 0: return
        p = np.round(np.asarray(pts, np.float32)).astype(np.int32)
        x0, y0 = p.min(0); x1, y1 = p.max(0)
        x0 = max(0, x0); y0 = max(0, y0); x1 = min(W, x1 + 1); y1 = min(H, y1 + 1)
        if x1 <= x0 or y1 <= y0: return
        mask = np.zeros((y1 - y0, x1 - x0), np.uint8)
        cv2.fillPoly(mask, [p - np.array([x0, y0], np.int32)], 255, cv2.LINE_AA)
        roi = self.f[y0:y1, x0:x1]
        al = (mask.astype(np.float32) / 255.0 * a)[..., None]
        roi[:] = (roi * (1 - al) + np.array(col, np.float32) * al).astype(np.uint8)
    def rect(self, x0, y0, x1, y1, col, a=1.0):
        x0 = max(0, int(x0)); y0 = max(0, int(y0)); x1 = min(W, int(x1)); y1 = min(H, int(y1))
        if x1 <= x0 or y1 <= y0 or a <= 0: return
        roi = self.f[y0:y1, x0:x1]
        roi[:] = (roi * (1 - a) + np.array(col, np.float32) * a).astype(np.uint8)
    def text(self, x, y, s, k, size, col, a=1.0, anc='la', glow=0.0):
        if a <= 0.02: return
        self.T.append((x, y, s, k, int(size), m(col, a), glow * a, anc))
    def finish(self):
        g = self.g
        gts = [t for t in self.T if t[6] > 0]
        if gts:
            gi = Image.fromarray(g); d = ImageDraw.Draw(gi)
            for (x, y, s, k, size, col, gl, anc) in gts:
                d.text((x / 2, y / 2), s, font=F(k, max(6, size // 2)), fill=m(col, gl / max(gl, 1e-6) * min(1.0, gl)), anchor=anc)
            g = np.array(gi)
        g1 = cv2.GaussianBlur(g, (0, 0), 3.5); g2 = cv2.GaussianBlur(g, (0, 0), 11)
        gl = cv2.addWeighted(g1, 0.9, g2, 1.3, 0)
        gl = cv2.resize(gl, (W, H), interpolation=cv2.INTER_LINEAR)
        out = cv2.add(self.f, gl)
        if self.flash > 0.01:
            out = cv2.add(out, np.full_like(out, int(80 * self.flash)))
        im = Image.fromarray(out); d = ImageDraw.Draw(im)
        for (x, y, s, k, size, col, gl_, anc) in self.T:
            d.text((x, y), s, font=F(k, size), fill=col, anchor=anc)
        return np.asarray(im)

BG = build_bg()

def chamfer(x0, y0, x1, y1, c):
    return [(x0 + c, y0), (x1, y0), (x1, y1 - c), (x1 - c, y1), (x0, y1), (x0, y0 + c)]

# ---------------------------------------------------------------- head sprite
HX, HY = 540, 480
def build_head():
    S = 2; w, h = 460, 400; ox, oy = 230, 190
    top = [(170 * math.cos(th), 150 * math.sin(th)) for th in np.linspace(math.pi, 2 * math.pi, 60)]
    bot = [(170 * math.cos(th), 92 * math.sin(th)) for th in np.linspace(0, math.pi, 40)]
    poly = top + bot
    Hs, Ws = h * S, w * S
    yy, xx = np.mgrid[0:Hs, 0:Ws].astype(np.float32)
    X = xx / S - ox; Y = yy / S - oy
    yn = np.clip((Y + 150) / 250, 0, 1)[..., None]
    img = np.array([40, 66, 140], np.float32) * (1 - yn) + np.array([10, 16, 50], np.float32) * yn
    img += np.array([120, 170, 230], np.float32) * (0.55 * np.exp(-(((X + 70) / 80) ** 2 + ((Y + 95) / 60) ** 2)))[..., None]
    img += np.array(PU, np.float32) * (0.35 * np.exp(-(((X - 150) / 40) ** 2 + ((Y + 20) / 120) ** 2)))[..., None]
    img += np.array(CY, np.float32) * (0.25 * np.exp(-(((X + 150) / 40) ** 2 + ((Y + 20) / 120) ** 2)))[..., None]
    img = np.ascontiguousarray(np.clip(img, 0, 255).astype(np.uint8))
    P = lambda x, y: (int((x + ox) * S), int((y + oy) * S))
    pp = np.array([P(x, y) for x, y in poly], np.int32)
    mask = np.zeros((Hs, Ws), np.uint8)
    cv2.fillPoly(mask, [pp], 255, cv2.LINE_AA)
    for sx in (-1, 1):
        cv2.circle(mask, P(sx * 182, 12), 28 * S, 255, -1, cv2.LINE_AA)
    for (ax, ay, a0, a1) in [(120, 105, 205, 335), (82, 62, 215, 325)]:
        cv2.ellipse(img, P(0, 0), (ax * S, ay * S), 0, a0, a1, (6, 10, 30), 3 * S, cv2.LINE_AA)
        cv2.ellipse(img, P(0, 2), (ax * S, ay * S), 0, a0, a1, (70, 110, 190), 1 * S, cv2.LINE_AA)
    cv2.line(img, P(0, -160), P(0, -96), (6, 10, 30), 3 * S, cv2.LINE_AA)
    cv2.line(img, P(2, -160), P(2, -96), (70, 110, 190), S, cv2.LINE_AA)
    for ang in (215, 245, 295, 325):
        rx, ry = 120 * math.cos(math.radians(ang)), 105 * math.sin(math.radians(ang))
        cv2.circle(img, P(rx, ry), 4 * S, (20, 30, 70), -1, cv2.LINE_AA)
        cv2.circle(img, P(rx - 1, ry - 1), 1 * S + 1, (130, 170, 230), -1, cv2.LINE_AA)
    cv2.polylines(img, [pp], True, CYD, 4 * S, cv2.LINE_AA)
    inner = np.array([P(x * 0.95, y * 0.95) for x, y in poly], np.int32)
    cv2.polylines(img, [inner], True, PUD, 2 * S, cv2.LINE_AA)
    for sx in (-1, 1):
        cv2.circle(img, P(sx * 182, 12), 28 * S, (16, 26, 70), -1, cv2.LINE_AA)
        cv2.circle(img, P(sx * 182, 12), 28 * S, CYD, 3 * S, cv2.LINE_AA)
        cv2.circle(img, P(sx * 182, 12), 14 * S, (10, 60, 80), -1, cv2.LINE_AA)
    vis = np.array([P(x, y) for x, y in [(-132, -20), (110, -20), (132, 2), (132, 52), (-110, 52), (-132, 30)]], np.int32)
    cv2.fillPoly(img, [vis], (4, 7, 22), cv2.LINE_AA)
    cv2.polylines(img, [vis], True, CYD, 3 * S, cv2.LINE_AA)
    spr = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    al = cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return spr, al, ox, oy
HSPR, HAL, HOX, HOY = build_head()

def blit_head(cv, gain):
    x0 = HX - HOX; y0 = HY - HOY
    roi = cv.f[y0:y0 + HSPR.shape[0], x0:x0 + HSPR.shape[1]]
    al = HAL[..., None]
    roi[:] = (roi * (1 - al) + HSPR.astype(np.float32) * gain * al).astype(np.uint8)

def draw_head(cv, t, gain, eye_target, eye_col, scan, L):
    blit_head(cv, gain)
    if gain < 0.3: return
    # ear pods
    for sx in (-1, 1):
        cv.circle((HX + sx * 182, HY + 12), 10, m(CY, 0.5 + 0.4 * math.sin(t * 3 + sx)), -1, glow=0.6 * gain)
    # LEDs
    for i in range(6):
        th = math.radians(215 + i * 22)
        x = HX + 150 * math.cos(th); y = HY + 128 * math.sin(th)
        col = AGN[i][1]
        cv.circle((x, y), 7, m(col, 0.15 + 0.85 * L[i]), -1, glow=0.9 * L[i])
    # core hex
    pulse = 0.65 + 0.35 * math.sin(t * 3.0)
    cx, cy = HX, HY - 62
    hexp = [(cx + 32 * math.cos(math.radians(-90 + 60 * k)), cy + 32 * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    cv.fillpoly(hexp, (18, 8, 50), 1.0)
    cv.poly(hexp, m(PU, gain), 3, glow=0.8 * pulse, closed=True)
    hex2 = [(cx + 23 * math.cos(math.radians(-90 + 60 * k)), cy + 23 * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    cv.poly(hex2, m(CY, 0.8 * gain), 2, glow=0.5, closed=True)
    cv.text(cx, cy + 1, "6", 'mono', 34, WH, gain, 'mm', glow=0.6)
    # eyes
    ey = HY + 16
    for sx in (-1, 1):
        c = (HX + sx * 58, ey)
        br = 0.72 + 0.28 * math.sin(t * 2.2 + sx)
        cv.ellipse(c, (31, 17), m(eye_col, br * gain), -1, glow=0.95)
        off = (0, 0)
        if eye_target is not None:
            dx = eye_target[0] - c[0]; dy = eye_target[1] - c[1]
            n = math.hypot(dx, dy) + 1e-6
            off = (dx / n * 9, dy / n * 5)
        cv.circle((c[0] + off[0], c[1] + off[1]), 8, INK, -1)
        cv.circle((c[0] + off[0] - 2, c[1] + off[1] - 2), 2, WH, -1)
    if scan is not None:
        x = HX - 124 + 248 * scan
        cv.poly([(x, HY - 17), (x, HY + 49)], m(CY, 0.9 * gain), 3, glow=1.0)

# ---------------------------------------------------------------- tentacles
BASES = [np.array(p, np.float64) for p in
         [(410, 572), (440, 576), (470, 578), (500, 580), (670, 572), (640, 576), (610, 578), (580, 580)]]
SXS = [-1, -1, -1, -1, 1, 1, 1, 1]
RESTS = [np.array(p, np.float64) for p in
         [(290, 736), (350, 756), (410, 772), (470, 782), (790, 736), (730, 756), (670, 772), (610, 782)]]
NODES = [(70, 905), (70, 1005), (70, 1105), (70, 1205), (1010, 905), (1010, 1005), (1010, 1105), (1010, 1205)]
TIPS = [np.array((70 + 50, 905 + 0.0)) if i < 4 else np.array((1010 - 50, NODES[i][1] + 0.0)) for i in range(8)]
for i in range(4):
    TIPS[i] = np.array((NODES[i][0] + 50, NODES[i][1] + 0.0))

def bez(P0, P1, P2, P3, s):
    s = s[:, None]
    return ((1 - s) ** 3) * P0 + 3 * ((1 - s) ** 2) * s * P1 + 3 * (1 - s) * s * s * P2 + s ** 3 * P3

def draw_tentacle(cv, i, e, t, grow, gain):
    base = BASES[i]; sx = SXS[i]; rest = RESTS[i]; tgt = TIPS[i]
    tip = rest + (tgt - rest) * e
    P1 = base + np.array([sx * (40 + 300 * e), 135.0 - 25 * e])
    P2 = tip + np.array([-sx * 60 * e, -64 * (1 - e) - 90 * e])
    N = 44
    sn = np.linspace(0, 1, N)
    s = sn * grow
    pts = bez(base, P1, P2, tip, s)
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6)
    wa = 18 * 4 * e * (1 - e) + (2.5 if e > 0.98 else 0)
    ph = 2 * np.pi * (2.0 * sn - 1.6 * t)
    pts = pts + nrm * (wa * np.sin(ph) * np.sin(np.pi * sn))[:, None]
    r = 17 * (1 - sn) ** 0.9 + 4.5
    act = STEPCOL[i]
    rim = mix(CYD, act, e)
    gl = 0.85 * smooth(e)
    for k in range(N):
        cv.circle(pts[k], r[k] + 2.5, m(rim, gain), -1, glow=gl if k % 2 == 0 else 0.0)
    for k in range(N):
        u = sn[k]
        col = (int(24 * (1 - u) + 12 * u), int(40 * (1 - u) + 18 * u), int(96 * (1 - u) + 52 * u))
        cv.circle(pts[k], r[k], m(col, gain), -1)
    for k in range(N):
        cv.circle((pts[k][0] - r[k] * 0.3, pts[k][1] - r[k] * 0.35), r[k] * 0.36, m((70, 105, 180), gain), -1)
    for k in range(3, N - 2, 4):
        a = pts[k] + nrm[k] * r[k] * 0.92; b = pts[k] - nrm[k] * r[k] * 0.92
        cv.poly([a, b], m(mix(CYD, act, e), 0.9 * gain), 2)
    for k in range(6, N - 2, 6):
        cv.circle(pts[k], 2.4, m(mix(CY, act, e), gain), -1, glow=0.5 * e)
    tipc = pts[-1]
    cv.circle(tipc, r[-1] + 4, m(mix(CYD, act, 0.35 + 0.65 * e), gain), -1, glow=0.4 + 0.6 * e)
    cv.circle(tipc, 3, m(WH, gain), -1)

def draw_node(cv, i, e, t, a):
    c = NODES[i]; col = STEPCOL[i]
    cv.circle(c, 44, m(INK, a), -1)
    cv.circle(c, 38, m(col, a * (0.10 + 0.28 * e)), -1)
    cv.circle(c, 44, m(mix(CYD, col, e), a), 3, glow=0.9 * e * a)
    cv.text(c[0], c[1], NAMES[i], 'b', 17, mix(DIM, WH, e), a, 'mm')
    if e > 0.98:
        rot = t * 160
        for k in range(4):
            cv.ellipse(c, (58, 58), m(col, a), 3, glow=0.9, ang=0, a0=rot + k * 90, a1=rot + k * 90 + 48)

# ---------------------------------------------------------------- UI pieces
PX0, PX1, PY0, PY1 = 150, 930, 870, 1290
CX0, CX1, CY0, CY1 = PX0 + 22, PX1 - 92, PY0 + 76, PY1 - 34

def check_icon(cv, x, y, s, col, a, th=3, glow=0.0):
    cv.poly([(x - 0.55 * s, y), (x - 0.15 * s, y + 0.45 * s), (x + 0.6 * s, y - 0.5 * s)], m(col, a), th, glow=glow * a)

def draw_panel(cv, a, title, sub=None, subcol=CY):
    pts = chamfer(PX0, PY0, PX1, PY1, 26)
    cv.fillpoly(pts, PANEL, 0.88 * a)
    cv.poly(pts, m(CYD, a), 2, glow=0.35 * a, closed=True)
    for (x, y, dx, dy) in [(PX0, PY0 + 26, 1, 0), (PX1, PY1 - 26, -1, 0)]:
        pass
    cv.poly([(PX0 + 26, PY0), (PX0 + 90, PY0)], m(CY, a), 4, glow=0.9 * a)
    cv.poly([(PX1 - 26, PY1), (PX1 - 90, PY1)], m(PU, a), 4, glow=0.9 * a)
    cv.text(PX0 + 22, PY0 + 16, title, 'b', 27, WH, a)
    if sub:
        cv.text(PX1 - 22, PY0 + 20, sub, 'md', 21, subcol, a, 'ra')

def draw_grid(cv, a, pmin, pmax, fmt=True):
    for k in range(5):
        y = CY0 + (CY1 - CY0) * k / 4
        cv.poly([(CX0, y), (CX1 + 6, y)], m(CYD, a * 0.35), 1)
        if fmt:
            p = pmax - (pmax - pmin) * k / 4
            cv.text(CX1 + 14, y, f"{p:.6f}", 'md', 17, DIM, a * 0.8, 'lm')

def candle(cv, x, w, yo, yh, yl, yc, up, a, glow=0.0):
    col = GR if up else RD
    cv.poly([(x, yh), (x, yl)], m(col, a), 2, glow=glow)
    y0, y1 = min(yo, yc), max(yo, yc)
    if y1 - y0 < 2: y1 = y0 + 2
    cv.rect(x - w / 2, y0, x + w / 2, y1, m(col, a), 1.0)
    if glow > 0:
        cv.g[int(y0 / 2):int(y1 / 2) + 1, int((x - w / 2) / 2):int((x + w / 2) / 2) + 1] = np.maximum(
            cv.g[int(y0 / 2):int(y1 / 2) + 1, int((x - w / 2) / 2):int((x + w / 2) / 2) + 1], np.array(m(col, glow), np.uint8))

def arrow_marker(cv, x, y, up, col, a, label, scale=1.0):
    s = scale
    if up:
        tri = [(x, y + 8 * s), (x - 15 * s, y + 38 * s), (x + 15 * s, y + 38 * s)]
        ty = y + 62 * s
    else:
        tri = [(x, y - 8 * s), (x - 15 * s, y - 38 * s), (x + 15 * s, y - 38 * s)]
        ty = y - 62 * s
    cv.fillpoly(tri, col, a)
    cv.poly(tri, m(col, a), 2, glow=0.9 * a, closed=True)
    if label:
        size = 20
        wd = F('b', size).getlength(label)
        cv.rect(x - wd / 2 - 8, ty - 15, x + wd / 2 + 8, ty + 15, INK, 0.8 * a)
        cv.text(x, ty, label, 'b', size, col, a, 'mm', glow=0.5)

# trade 1 candles
def trade1_candles():
    rng = np.random.default_rng(5)
    c = np.zeros(48)
    for i in range(48):
        if i <= 14:
            c[i] = 1.0 - 0.06 * math.sin(i / 14 * math.pi) + rng.normal(0, 0.012)
        elif i <= 34:
            c[i] = 1 + R1 * (i - 14) / 20 + rng.normal(0, 0.02)
        else:
            c[i] = 1 + R1 * (1 - 0.2 * (i - 34) / 13) + rng.normal(0, 0.02)
    c[14] = 1.0; c[34] = 1 + R1
    o = np.concatenate([[1.0], c[:-1]])
    hi = np.maximum(o, c) + np.abs(rng.normal(0, 0.012, 48)) * 1.0
    lo = np.minimum(o, c) - np.abs(rng.normal(0, 0.012, 48)) * 1.0
    return o, hi, lo, c
T1O, T1H, T1L, T1C = trade1_candles()
T1MIN = float(T1L.min()) - 0.04; T1MAX = float(T1H.max()) + 0.22

_mr = np.random.default_rng(21)
MWALK = np.cumsum(_mr.normal(0.004, 0.045, 900)) + 0.3
MCL = 0.0004 * np.exp(MWALK)
MHI_N = np.abs(_mr.normal(0, 0.02, 900)); MLO_N = np.abs(_mr.normal(0, 0.02, 900))

def money(v, sign=False):
    s = f"${abs(v):,.0f}"
    if sign: return ("+" if v >= 0 else "-") + s
    return s

# ---------------------------------------------------------------- panel contents
def draw_boot(cv, a, t):
    if a <= 0.02: return
    draw_panel(cv, a, "KHỞI ĐỘNG 6 AI AGENTS", "TRUNG TÂM CHỈ HUY OCTOPUS", CY)
    msgs = ["quét token Solana mới", "lọc thanh khoản và rủi ro", "đọc biểu đồ, tìm tín hiệu",
            "sẵn sàng mô phỏng BUY / SELL", "giám sát mức tiếp xúc vốn", "ghi nhận kết quả giao dịch"]
    for i in range(6):
        ta = 3.0 + i + 0.15
        ai = ramp(t, ta, ta + 0.35) * a
        y = PY0 + 82 + i * 52
        cv.text(PX0 + 28, y, f"[{AGN[i][0]}]", 'mono', 24, AGN[i][1], ai, 'lm', glow=0.4)
        cv.text(PX0 + 230, y, "ONLINE", 'mono', 22, GR, ai, 'lm')
        cv.text(PX0 + 360, y, msgs[i], 'md', 22, WH, ai * 0.9, 'lm')
        check_icon(cv, PX1 - 50, y, 11, GR, ai, 3, glow=0.6)
    pr = clamp((t - 3.0) / 6.0)
    cv.rect(PX0 + 28, PY1 - 36, PX1 - 28, PY1 - 28, INK, a)
    cv.rect(PX0 + 28, PY1 - 36, PX0 + 28 + (PX1 - PX0 - 56) * pr, PY1 - 28, CY, a * 0.9)
    cv.poly([(PX0 + 28 + (PX1 - PX0 - 56) * pr, PY1 - 40), (PX0 + 28 + (PX1 - PX0 - 56) * pr, PY1 - 24)], m(WH, a), 2, glow=0.8 * a)

def draw_scan(cv, a, t):
    n = int(round(30 * smooth(ramp(t, 9.25, 10.85))))
    draw_panel(cv, a, "SCAN · SCOUT & FILTER", f"Đã quét {n}/30 token", CY)
    rows = 9
    first = max(0, n - rows)
    for r in range(rows):
        k = first + r
        if k >= n: break
        y = PY0 + 92 + r * 38
        fade = 1.0 if n <= rows else (0.45 + 0.55 * r / (rows - 1))
        cv.text(PX0 + 26, y, f"{k + 1:02d}", 'mono', 20, DIM, a * fade, 'lm')
        cv.text(PX0 + 78, y, f"${TOKENS[k]}", 'mono', 24, WH, a * fade, 'lm')
        cv.text(PX0 + 258, y, "LP · RISK", 'md', 18, DIM, a * fade, 'lm')
        check_icon(cv, PX0 + 410, y, 9, GR, a * fade, 3)
        cv.text(PX0 + 430, y, "PASS", 'mono', 18, GR, a * fade, 'lm')
    rc = (PX1 - 150, PY0 + 215 + 20); R = 125
    for rr in (R, R * 0.66, R * 0.33):
        cv.circle(rc, rr, m(CYD, a), 2)
    cv.poly([(rc[0] - R, rc[1]), (rc[0] + R, rc[1])], m(CYD, a * 0.7), 1)
    cv.poly([(rc[0], rc[1] - R), (rc[0], rc[1] + R)], m(CYD, a * 0.7), 1)
    th = t * 3.4
    for k in range(16):
        ang = th - k * 0.06
        cv.poly([rc, (rc[0] + R * math.cos(ang), rc[1] + R * math.sin(ang))], m(CY, a * (1 - k / 16) * 0.9), 2, glow=0.5 * (1 - k / 16))
    for k in range(n):
        ang = (k * 2.399) % 6.283; rad = R * (0.25 + 0.7 * ((k * 0.618) % 1.0))
        cv.circle((rc[0] + rad * math.cos(ang), rc[1] + rad * math.sin(ang)), 4, m(GR if k % 4 else CY, a), -1, glow=0.7 * a)

def draw_chart_frame_t1(cv, a, t, nrev):
    step = int((t - STEP0) // STEPD)
    caps = {1: "ANALYST đọc biểu đồ $NEBU", 2: "RISK kiểm tra ví mô phỏng", 3: f"EXECUTOR · BUY @ {ENTRY:.6f}",
            4: "RISK theo dõi vị thế", 5: f"EXECUTOR · SELL @ {EXIT1:.6f}", 6: "LOGGER xác nhận giao dịch",
            7: f"LOGGER ghi nhận PnL {money(TR[0]['pnl'], True)}"}
    cap = caps.get(step, "")
    draw_panel(cv, a, "$NEBU / SOL · 1m", cap, STEPCOL[step] if 0 <= step < 8 else CY)
    draw_grid(cv, a, ENTRY * T1MIN, ENTRY * T1MAX)
    n = 48; cw = (CX1 - CX0) / n
    yf = lambda p: CY1 - (p - T1MIN) / (T1MAX - T1MIN) * (CY1 - CY0)
    for i in range(n):
        if nrev <= i: break
        fr = clamp(nrev - i)
        o = T1O[i]; c = o + (T1C[i] - o) * fr
        h = max(o, c) + (T1H[i] - max(T1O[i], T1C[i])) * fr
        l = min(o, c) - (min(T1O[i], T1C[i]) - T1L[i]) * fr
        x = CX0 + (i + 0.5) * cw
        candle(cv, x, 8.5, yf(o), yf(h), yf(l), yf(c), c >= o, a, glow=0.5 if (i == int(nrev) and fr < 1.0) else 0.0)
    last = min(n - 1, int(nrev)) if nrev > 0 else None
    if last is not None and nrev > 1:
        i = min(int(nrev - 1e-6), n - 1)
        fr = clamp(nrev - i); cl = T1O[i] + (T1C[i] - T1O[i]) * fr
        y = yf(cl)
        for xx in range(int(CX0), int(CX1), 14):
            cv.poly([(xx, y), (xx + 7, y)], m(WH, a * 0.55), 1)
        txt = f"{ENTRY * cl:.6f}"
        wd = F('b', 17).getlength(txt)
        cv.rect(CX1 + 8, y - 12, CX1 + 8 + wd + 12, y + 12, mix(CYD, INK, 0.2), a)
        cv.text(CX1 + 14, y, txt, 'b', 17, WH, a, 'lm')
    # markers
    xb = CX0 + 14.5 * cw
    if t >= 15.9:
        age = t - 15.9
        arrow_marker(cv, xb, yf(T1L[14]), True, GR, a, f"BUY {ENTRY:.6f}", 0.6 + 0.4 * easeout(age / 0.25))
    xs = CX0 + 34.5 * cw
    if t >= 20.25:
        age = t - 20.25
        arrow_marker(cv, xs, yf(T1H[34]), False, MG, a, f"SELL {EXIT1:.6f}", 0.6 + 0.4 * easeout(age / 0.25))
    # overlays
    if 13.2 <= t < 15.0:
        oa = a * min(ramp(t, 13.2, 13.6), 1 - ramp(t, 14.6, 15.0))
        bx0, by0 = PX0 + 26, PY0 + 74
        cv.fillpoly(chamfer(bx0, by0, bx0 + 330, by0 + 110, 14), INK, 0.88 * oa)
        cv.poly(chamfer(bx0, by0, bx0 + 330, by0 + 110, 14), m(PU, oa), 2, glow=0.7 * oa, closed=True)
        cv.text(bx0 + 18, by0 + 14, "VÍ MÔ PHỎNG", 'b', 19, PU, oa)
        cv.text(bx0 + 18, by0 + 52, "$1,000.00", 'mono', 36, WH, oa, 'lm')
        cv.text(bx0 + 18, by0 + 90, "Tiếp xúc vốn", 'md', 17, DIM, oa, 'lm')
        cv.rect(bx0 + 150, by0 + 84, bx0 + 310, by0 + 96, PANEL, oa)
        cv.rect(bx0 + 150, by0 + 84, bx0 + 150 + 160 * 0.2 * smooth(ramp(t, 13.5, 14.2)), by0 + 96, PU, oa)
        cv.text(bx0 + 312, by0 + 90, "20%", 'b', 17, WH, oa, 'rm')
    if 17.2 <= t < 19.6:
        oa = a * min(ramp(t, 17.2, 17.5), 1 - ramp(t, 19.3, 19.6))
        nr = float(np.interp(t, [10.9, 13.0, 15.2, 16.2, 17.0, 19.0, 19.6, 20.3, 21.0, 23.0, 25.0], [0, 14, 14, 15, 15, 29, 29, 35, 35, 48, 48]))
        i = min(int(nr), 47); pct = (T1C[i] - 1.0) * 100
        bx0, by0 = PX0 + 26, PY0 + 74
        cv.fillpoly(chamfer(bx0, by0, bx0 + 270, by0 + 62, 12), INK, 0.88 * oa)
        cv.poly(chamfer(bx0, by0, bx0 + 270, by0 + 62, 12), m(PU, oa), 2, glow=0.6 * oa, closed=True)
        cv.text(bx0 + 16, by0 + 31, "Lãi tạm tính", 'md', 18, DIM, oa, 'lm')
        cv.text(bx0 + 254, by0 + 31, f"{pct:+.1f}%", 'mono', 26, GR if pct >= 0 else RD, oa, 'rm', glow=0.5)
    if 21.4 <= t < 25.0:
        oa = a * min(ramp(t, 21.4, 21.8), 1 - ramp(t, 24.7, 25.0))
        bx0, by0 = PX0 + 26, PY0 + 74
        cv.fillpoly(chamfer(bx0, by0, bx0 + 270, by0 + 62, 12), INK, 0.88 * oa)
        cv.poly(chamfer(bx0, by0, bx0 + 270, by0 + 62, 12), m(GR, oa), 2, glow=0.6 * oa, closed=True)
        check_icon(cv, bx0 + 34, by0 + 31, 14, GR, oa, 4, glow=0.8)
        cv.text(bx0 + 62, by0 + 31, "ĐÃ XÁC NHẬN", 'b', 22, GR, oa, 'lm', glow=0.4)
    if 23.7 <= t < 25.0:
        age = t - 23.7
        oa = a * (1 - ramp(t, 24.6, 25.0))
        sc = 0.7 + 0.3 * easeout(age / 0.3)
        txt = money(TR[0]['pnl'], True)
        cv.text((CX0 + CX1) / 2, (CY0 + CY1) / 2 - 10 - 20 * easeout(age / 0.8), txt, 'mono', int(92 * sc), GR, oa, 'mm', glow=0.9)
        cv.text((CX0 + CX1) / 2, (CY0 + CY1) / 2 + 60, f"Lệnh #1 · THẮNG · {R1 * 100:+.1f}%", 'b', 28, WH, oa, 'mm')

def draw_chart_mont(cv, a, t):
    head = 60 + (t - MONT0) * 7.0
    n = 42
    hi_i = int(head)
    i0 = hi_i - n + 1
    cl = MCL[i0:hi_i + 1].copy()
    # window range
    his = np.array([max(MCL[j - 1], MCL[j]) * (1 + MHI_N[j]) for j in range(i0, hi_i + 1)])
    los = np.array([min(MCL[j - 1], MCL[j]) * (1 - MLO_N[j]) for j in range(i0, hi_i + 1)])
    pmin = los.min() * 0.97; pmax = his.max() * 1.03
    k_now = sum(1 for ev in EV if t >= ev)
    draw_panel(cv, a, "THỊ TRƯỜNG SOLANA · 1m", f"Đã chốt {k_now}/30 lệnh · mô phỏng", CY)
    draw_grid(cv, a, pmin, pmax)
    cw = (CX1 - CX0) / n
    yf = lambda p: CY1 - (p - pmin) / (pmax - pmin) * (CY1 - CY0)
    frac = head - hi_i
    for r, j in enumerate(range(i0, hi_i + 1)):
        o = MCL[j - 1]; c = MCL[j]; hh = his[r]; ll = los[r]
        fr = frac if j == hi_i else 1.0
        cc = o + (c - o) * fr
        x = CX0 + (r + 0.5) * cw - frac * cw
        if x < CX0: continue
        candle(cv, x, 9, yf(o), yf(max(o, cc) + (hh - max(o, c)) * fr), yf(min(o, cc) - (min(o, c) - ll) * fr), yf(cc), cc >= o, a)
    # markers: trades 2..30
    latest = max([k for k in range(2, 31) if t >= EV[k - 1] - 0.2] or [0])
    for k in range(2, 31):
        ev = EV[k - 1]
        age = t - (ev - 0.2)
        if age < 0 or age > 2.4: continue
        jb = head - 0 - (t - (ev - 0.2)) * 7.0
        js = head - (t - ev) * 7.0 if t >= ev else None
        sc = 0.78 * (0.6 + 0.4 * easeout(age / 0.2)) * (1.0 - 0.35 * ramp(age, 1.2, 2.4))
        fa = a * (1.0 - 0.7 * ramp(age, 1.4, 2.4))
        xb = CX0 + (jb - i0 + 0.5) * cw
        if CX0 + 6 < xb < CX1 - 6:
            jj = int(jb)
            lbl = f"BUY {MCL[jj]:.5f}" if (k == latest and age < 0.9) else None
            arrow_marker(cv, xb, yf(min(MCL[jj - 1], MCL[jj]) * (1 - MLO_N[jj])), True, GR, fa, lbl, sc)
        if js is not None:
            xs = CX0 + (js - i0 + 0.5) * cw
            if CX0 + 6 < xs < CX1 - 6:
                jj = int(js)
                col = GR if TR[k - 1]['win'] else RD
                lbl = f"SELL {MCL[jj]:.5f}" if (k == latest and t - ev < 0.9) else None
                arrow_marker(cv, xs, yf(max(MCL[jj - 1], MCL[jj]) * (1 + MHI_N[jj])), False, MG if TR[k - 1]['win'] else RD, fa, lbl, sc)
    ycl = yf(MCL[hi_i - 1] + (MCL[hi_i] - MCL[hi_i - 1]) * frac)
    for xx in range(int(CX0), int(CX1), 14):
        cv.poly([(xx, ycl), (xx + 7, ycl)], m(WH, a * 0.5), 1)
    if k_now >= 2:
        tr = TR[min(k_now, 30) - 1]
        col = GR if tr['win'] else RD
        bx0, by0 = PX0 + 26, PY0 + 74
        cv.fillpoly(chamfer(bx0, by0, bx0 + 340, by0 + 56, 12), INK, 0.88 * a)
        cv.poly(chamfer(bx0, by0, bx0 + 340, by0 + 56, 12), m(col, a), 2, glow=0.6 * a, closed=True)
        cv.text(bx0 + 16, by0 + 28, f"Lệnh #{min(k_now, 30)}", 'b', 21, WH, a, 'lm')
        cv.text(bx0 + 130, by0 + 28, "THẮNG" if tr['win'] else "THUA", 'b', 21, col, a, 'lm')
        cv.text(bx0 + 326, by0 + 28, money(tr['pnl'], True), 'mono', 26, col, a, 'rm', glow=0.5)

RESULT_ROWS = [("Token được quét", "30", WH), ("Giao dịch mô phỏng", "30", WH), ("Lệnh thắng", "22", GR),
               ("Lệnh thua", "8", RD), ("Tỷ lệ thắng", "73.33%", CY), ("Vốn ban đầu", "$1,000", WH),
               ("Lợi nhuận mô phỏng", "+$82,799", GR), ("Số dư cuối mô phỏng", "$83,799", CY),
               ("ROI minh họa", "+8,279.9%", GR)]
def draw_results(cv, a, t):
    draw_panel(cv, a, "KẾT QUẢ GIAO DỊCH MÔ PHỎNG", "SỐ LIỆU MÔ PHỎNG", GOLD)
    for i, (lab, val, col) in enumerate(RESULT_ROWS):
        ta = 34.5 + i * 0.4
        ra = ramp(t, ta, ta + 0.3) * a
        if ra <= 0: continue
        y = PY0 + 76 + i * 38
        slide = (1 - easeout(ramp(t, ta, ta + 0.3))) * 40
        if i % 2 == 0:
            cv.rect(PX0 + 14, y - 18, PX1 - 14, y + 18, PUD, 0.22 * ra)
        cv.text(PX0 + 30 - slide, y, lab, 'md', 25, DIM if i < 8 else WH, ra, 'lm')
        cv.text(PX1 - 30 + slide, y, val, 'mono', 27, col, ra, 'rm', glow=0.5 if i >= 6 else 0.0)
    if t > 38.2:
        y = PY0 + 76 + 8 * 38
        pu = 0.5 + 0.5 * math.sin((t - 38.2) * 5)
        cv.poly(chamfer(PX0 + 14, y - 18, PX1 - 14, y + 18, 8), m(GR, a * (0.5 + 0.5 * pu)), 2, glow=0.9 * pu, closed=True)

def draw_chips(cv, a, e):
    for j in range(8):
        x0 = 40 + j * 126; x1 = x0 + 118; y0, y1 = 800, 846
        col = STEPCOL[j]
        cv.fillpoly(chamfer(x0, y0, x1, y1, 8), col, a * (0.08 + 0.72 * e[j]))
        cv.poly(chamfer(x0, y0, x1, y1, 8), m(mix(CYD, col, e[j]), a), 2, glow=0.8 * e[j] * a, closed=True)
        cv.text((x0 + x1) / 2, (y0 + y1) / 2, NAMES[j], 'b', 20, mix(DIM, WH, e[j]), a, 'mm')

def agent_icon(cv, idx, c, col, a, lv):
    x, y = c
    cv.circle(c, 31, m(col, a * (0.35 + 0.65 * lv)), 2, glow=0.7 * lv * a)
    cc = m(col, a * (0.55 + 0.45 * lv)); g = 0.5 * lv * a
    if idx == 0:
        cv.circle(c, 14, cc, 2, glow=g); cv.poly([(x - 22, y), (x + 22, y)], cc, 2); cv.poly([(x, y - 22), (x, y + 22)], cc, 2)
        cv.circle((x + 8, y - 6), 3, cc, -1, glow=g)
    elif idx == 1:
        cv.poly([(x - 16, y - 12), (x + 16, y - 12), (x + 4, y + 2), (x + 4, y + 16), (x - 4, y + 12), (x - 4, y + 2)], cc, 2, glow=g, closed=True)
    elif idx == 2:
        cv.poly([(x - 16, y + 8), (x - 6, y - 4), (x + 2, y + 4), (x + 14, y - 12)], cc, 3, glow=g)
        cv.circle((x + 14, y - 12), 3, cc, -1, glow=g)
    elif idx == 3:
        cv.poly([(x + 4, y - 18), (x - 10, y + 3), (x - 1, y + 3), (x - 5, y + 18), (x + 11, y - 5), (x + 2, y - 5)], cc, 2, glow=g, closed=True)
    elif idx == 4:
        cv.poly([(x, y - 16), (x + 17, y + 13), (x - 17, y + 13)], cc, 2, glow=g, closed=True)
        cv.poly([(x, y - 5), (x, y + 4)], cc, 2); cv.circle((x, y + 9), 1.6, cc, -1)
    else:
        cv.poly([(x - 14, y), (x - 4, y + 11), (x + 15, y - 11)], cc, 3, glow=g)

def draw_cards(cv, t, L):
    for i in range(6):
        a = ramp(t, 3.0 + 0.25 * i - 0.2, 3.0 + 0.25 * i + 0.5)
        if a <= 0: continue
        col = AGN[i][1]; lv = L[i]
        x0 = 40 + (i % 3) * 337; y0 = 1320 + (i // 3) * 122
        pts = chamfer(x0, y0, x0 + 325, y0 + 110, 16)
        cv.fillpoly(pts, mix(PANEL, col, 0.28 * lv), 0.85 * a)
        cv.poly(pts, m(mix(CYD, col, lv), a), 2, glow=0.8 * lv * a, closed=True)
        agent_icon(cv, i, (x0 + 52, y0 + 55), col, a, lv)
        cv.text(x0 + 102, y0 + 28, AGN[i][0], 'b', 28, mix(DIM, WH, 0.35 + 0.65 * lv), a, 'lm')
        mw = 210
        s1 = fit(AGN[i][2], 'md', 19, mw); s2 = fit(AGN[i][3], 'md', 19, mw)
        s = min(s1, s2)
        cv.text(x0 + 102, y0 + 64, AGN[i][2], 'md', s, DIM, a, 'lm')
        cv.text(x0 + 102, y0 + 88, AGN[i][3], 'md', s, DIM, a, 'lm')

def draw_stats(cv, t, a, vals, pulse):
    scanned, done, wins, losses, bal = vals
    tiles = [("TOKEN QUÉT", f"{scanned}/30", WH), ("GIAO DỊCH", f"{done}/30", WH),
             ("THẮNG / THUA", None, None), ("SỐ DƯ", money(bal), CY)]
    for i, (lab, val, col) in enumerate(tiles):
        x0 = 40 + i * 252; x1 = x0 + 242; y0, y1 = 1580, 1680
        pts = chamfer(x0, y0, x1, y1, 14)
        cv.fillpoly(pts, PANEL, 0.85 * a)
        cv.poly(pts, m(CYD, a), 2, closed=True)
        cv.text(x0 + 16, y0 + 24, lab, 'b', 19, DIM, a, 'lm')
        if val is not None:
            sz = fit(val, 'mono', 42, 214)
            cv.text(x0 + 16, y0 + 68, val, 'mono', sz, col, a, 'lm', glow=0.35 if i == 3 else 0.0)
        else:
            cv.text(x0 + 16, y0 + 68, f"{wins}", 'mono', 42, GR, a, 'lm', glow=0.35)
            wd = F('mono', 42).getlength(f"{wins}")
            cv.text(x0 + 16 + wd + 8, y0 + 68, "/", 'mono', 36, DIM, a, 'lm')
            cv.text(x0 + 16 + wd + 34, y0 + 68, f"{losses}", 'mono', 42, RD, a, 'lm', glow=0.35)

def draw_pnl(cv, t, a, bal, pulse):
    pnl = bal - 1000.0
    pts = chamfer(40, 1700, 1040, 1800, 18)
    col = GR if pnl >= 0 else RD
    cv.fillpoly(pts, mix(PANEL, col, 0.12), 0.9 * a)
    cv.poly(pts, m(col, a), 2, glow=(0.5 + 0.5 * pulse) * a, closed=True)
    cv.text(70, 1731, "PnL MÔ PHỎNG", 'b', 26, WH, a, 'lm')
    roi = pnl / 1000.0 * 100
    cv.text(70, 1771, f"ROI minh họa {roi:+,.1f}%", 'md', 22, DIM, a, 'lm')
    sz = int(66 * (1 + 0.18 * pulse))
    cv.text(1010, 1750, money(pnl, True), 'mono', sz, col, a, 'rm', glow=0.8)

def draw_header(cv, t):
    ah = ramp(t, 2.2, 3.0)
    cv.text(540, 150, "OCTOPUS 6 AI — MASTER V9 R02", 'b', 36, WH, ah, 'mm', glow=0.45)
    ab = ramp(t, 0.0, 0.5)
    pts = chamfer(320, 192, 760, 246, 14)
    if ab > 0.02:
        cv.fillpoly(pts, INK, 0.85 * ab)
        cv.poly(pts, m(GOLD, ab), 3, glow=0.6 * ab, closed=True)
    cv.text(540, 219, "MÔ PHỎNG · SIMULATION", 'b', 28, GOLD, ab, 'mm')
    cv.text(540, 1846, "SỐ LIỆU MÔ PHỎNG · KHÔNG PHẢI LỢI NHUẬN THỰC TẾ", 'sb', 26, DIM, ab, 'mm')

def draw_intro_title(cv, t):
    a = ramp(t, 0.5, 1.3) * (1 - ramp(t, 2.2, 2.8))
    if a <= 0: return
    cv.text(540, 1000, "OCTOPUS 6 AI", 'b', 112, WH, a, 'mm', glow=0.3)
    cv.text(540, 1100, "MASTER V9 R02", 'b', 62, PU, a, 'mm', glow=0.45)
    cv.text(540, 1175, "CINEMATIC AI TRADING SYSTEM · SOLANA · 6 AI AGENTS", 'md', 24, CY, a * ramp(t, 0.9, 1.6), 'mm')

def particles(cv, t):
    for i in range(70):
        y = (PYS[i] - PSP[i] * t) % H
        b = 0.25 + 0.2 * math.sin(t * 1.5 + PPH[i])
        cv.circle((PXS[i], y), 1 + (i % 3 == 0), m(PCOL[i], b), -1)

# ---------------------------------------------------------------- frame
def render(t):
    cv = Cv(BG)
    particles(cv, t)
    e = tent_state(t)
    L = agent_levels(t, e)
    vals = counters(t)
    aUI = ramp(t, 8.2, 9.0)
    aPanel = ramp(t, 2.3, 3.2)
    # panel contents
    if t < 9.0:
        draw_boot(cv, aPanel * (1 - ramp(t, 8.7, 9.0)), t)
    if 9.0 <= t < 11.2:
        a = ramp(t, 9.0, 9.3) * (1 - ramp(t, 10.7, 11.0))
        if a > 0: draw_scan(cv, a, t)
    if 10.9 <= t < MONT0:
        a = ramp(t, 10.9, 11.2)
        nrev = float(np.interp(t, [10.9, 13.0, 15.2, 16.2, 17.0, 19.0, 19.6, 20.3, 21.0, 23.0, 25.0], [0, 14, 14, 15, 15, 29, 29, 35, 35, 48, 48]))
        draw_chart_frame_t1(cv, a, t, nrev)
    if MONT0 <= t < 34.0:
        a = ramp(t, MONT0, MONT0 + 0.25) * (1 - ramp(t, 33.8, 34.2))
        draw_chart_mont(cv, a, t)
    if t >= 33.8:
        draw_results(cv, ramp(t, 33.8, 34.3), t)
    if t >= 2.2:
        pass
    draw_header(cv, t)
    draw_intro_title(cv, t)
    # chips, nodes
    if aUI > 0:
        draw_chips(cv, aUI, e)
        for i in range(8):
            draw_node(cv, i, e[i], t, aUI)
    draw_cards(cv, t, L)
    aT = ramp(t, 2.6, 3.6)
    pulse = 0.0
    if t >= 34.0:
        pulse = max(0.0, math.sin(clamp((t - 34.0) / 1.2) * math.pi))
    if aT > 0:
        draw_stats(cv, t, aT, vals, pulse)
        draw_pnl(cv, t, aT, vals[4], pulse)
    # head
    grow = easeout(ramp(t, 0.5, 2.4))
    gain = easeout(ramp(t, 0.0, 1.4))
    for i in range(8):
        draw_tentacle(cv, i, e[i], t, grow, gain)
    best = max(range(8), key=lambda i: e[i])
    et = NODES[best] if e[best] > 0.15 else None
    ecol = mix(CY, STEPCOL[best], e[best]) if e[best] > 0.15 else CY
    scan = None
    if 9.3 <= t < 10.9:
        scan = ((t - 9.3) / 0.8) % 1.0
        scan = scan if scan < 0.5 else 1.0 - (scan - 0.5) * 0 - 0  # sweep
        scan = ((t - 9.3) % 0.8) / 0.8
    elif 0.8 <= t < 2.4:
        scan = ((t - 0.8) % 0.8) / 0.8
    draw_head(cv, t, gain, et, ecol, scan, L)
    # climax burst
    if 34.0 <= t < 35.4:
        u = ramp(t, 34.0, 35.4)
        cv.flash = (1 - ramp(t, 34.0, 34.5)) * 0.9
        for k in range(28):
            ang = k * 2 * math.pi / 28 + 0.1
            r0 = 120 + 700 * easeout(u); r1 = r0 + 60 + 120 * (1 - u)
            col = CY if k % 2 else PU
            cv.poly([(HX + r0 * math.cos(ang), HY + 30 + r0 * math.sin(ang) * 0.9),
                     (HX + r1 * math.cos(ang), HY + 30 + r1 * math.sin(ang) * 0.9)],
                    m(col, (1 - u) * 0.9), 3, glow=1.0 * (1 - u))
        cv.ellipse((HX, HY + 20), (int(200 + 600 * easeout(u)), int(160 + 480 * easeout(u))), m(WH, (1 - u)), 4, glow=1.0 * (1 - u))
    if 20.2 <= t < 20.5:
        cv.flash = max(cv.flash, 0.25 * (1 - ramp(t, 20.2, 20.5)))
    return cv.finish()

# ---------------------------------------------------------------- main
def write_scene(name, t0, t1):
    n = int(round((t1 - t0) * FPS))
    tmp = f"{OUT}/scene_{name}.tmp.mp4"
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(FPS), tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        fr = render(t0 + f / FPS)
        p.stdin.write(fr.tobytes())
    p.stdin.close()
    rc = p.wait()
    if rc == 0:
        os.rename(tmp, f"{OUT}/scene_{name}.mp4")
        print('done', name, n, 'frames')
    else:
        print('ffmpeg failed', rc)
        sys.exit(1)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'still':
        for ts in sys.argv[2:]:
            t = float(ts)
            Image.fromarray(render(t)).save(f"{OUT}/still_{ts}.png")
            print('saved', ts)
    elif mode == 'scene':
        write_scene(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))
    elif mode == 'info':
        print('R1', R1, 'EXIT1', EXIT1)
        print('wins', sum(t['win'] for t in TR), 'final', TR[-1]['after'], 'first', TR[0])
        print('last win', TR[-1]['win'])

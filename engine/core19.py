import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
import sys, math, os, subprocess, bisect
sys.path.insert(0, _BASE)
import numpy as np, cv2
from PIL import Image
import core_o as core
import octocfg as OC
import oct3d as O3
import oct3d2 as O2
from PIL import ImageDraw
import logo as LG
NT = OC.NT
import core10_o as c10
from core_o import (W, H, FPS, OUT, CY, CYD, PU, PUD, MG, GR, RD, WH, DIM, GOLD, PANEL, INK, m, mix, clamp, smooth,
                  easeout, ramp, F, fit, Cv, BG, chamfer, TR, TOKENS, AGN, AG_MAP, check_icon, arrow_marker, candle,
                  agent_icon, T1O, T1H, T1L, T1C, T1MIN, T1MAX, R1, ENTRY, EXIT1, MCL, MHI_N, MLO_N)
from core10_o import usd, solf, moneyk, SCANNED, SOLP, CUM, NAMES

# ---------------------------------------------------------------- geometry / timeline (28-bar grid, 150 BPM)
PX0, PX1, PY0, PY1 = 150, 930, 480, 1010
c10.PX0, c10.PX1, c10.PY0, c10.PY1 = PX0, PX1, PY0, PY1
BAR = 1.6; BEAT = 0.4; TOTAL = 44.8
TB = 15.2; TS = 18.4
MONT0 = 22.4; MONT1 = 38.4
DT = (MONT1 - MONT0) / (NT - 1)
FEAT = sorted([j for j in range(1, NT - 1) if TR[j]['win']], key=lambda j: -TR[j]['pnl'])[:3]
_w = [1.0] * NT
for _j in FEAT: _w[_j + 1] = 2.2
_tot = sum(_w[1:NT]); _acc = 0.0
EV = [TS]
for _j in range(1, NT):
    _acc += _w[_j]; EV.append(MONT0 + (MONT1 - MONT0) * _acc / _tot)

MCOL = [CY, (70, 140, 255), PU, GR, (190, 110, 255), (255, 70, 120), (40, 225, 205), GOLD]
ROLE = ["SCOUT + FILTER", "ANALYST", "RISK", "EXECUTOR", "ANALYST + RISK", "EXECUTOR", "LOGGER", "LOGGER"]
DOCK = [(540 + (i - 3.5) * 112.0, 386.0) for i in range(8)]
MX, MY, MS = 540, 235, 0.82
MOUTH = (540.0, 326.0)
FUN = (855.0, 648.0)
ST = [(780.0, 735.0), (640.0, 612.0), (780.0, 612.0), (440.0, 1004.0), (780.0, 612.0), (900.0, 1004.0),
      (985.0, 1198.0), (968.0, 1578.0)]

# price / quantity per trade (illustrative)
def price_in(k):
    return ENTRY if k == 0 else round(0.00006 * (1 + ((k * 37) % 23) / 6.0), 6)
def price_out(k):
    return price_in(k) * (1 + TR[k]['ret'])
def qty(k):
    return int(round((TR[k]['before'] / SOLP) / price_in(k)))

# ---------------------------------------------------------------- mini job model
def _wp():
    W_ = [[] for _ in range(8)]
    for i in range(8):
        ta = 0.45 + 0.05 * i
        W_[i] += [(ta, MOUTH[0], MOUTH[1]), (ta + 0.6, DOCK[i][0], DOCK[i][1])]
    def leg(i, tl, ta, th, tr, st=None):
        s = st or ST[i]; d = DOCK[i]
        W_[i] += [(tl, d[0], d[1]), (ta, s[0], s[1]), (th, s[0], s[1]), (tr, d[0], d[1])]
    d0 = DOCK[0]
    W_[0] += [(3.6, d0[0], d0[1]), (4.3, FUN[0], FUN[1]), (9.4, FUN[0], FUN[1]), (10.1, ST[0][0], ST[0][1]),
              (11.0, ST[0][0], ST[0][1]), (11.5, d0[0], d0[1])]
    leg(1, 11.4, 12.0, 12.8, 13.3)
    leg(2, 13.0, 13.6, 14.4, 14.9)
    leg(3, 14.6, 15.2, 16.0, 16.5)
    leg(4, 16.2, 16.8, 17.6, 18.1)
    leg(5, 17.8, 18.4, 19.2, 19.7)
    leg(6, 19.4, 20.0, 20.8, 21.3)
    leg(7, 21.0, 21.6, 38.4, 39.0)
    leg(3, 22.4, 22.7, 38.4, 39.0)
    leg(5, 22.4, 22.7, 38.4, 39.0)
    leg(6, 22.4, 22.7, 38.4, 39.0)
    return W_
WP = _wp()

def mini_pos(i, t):
    pts = WP[i]
    if t <= pts[0][0]: return pts[0][1], pts[0][2]
    for (t0, x0, y0), (t1, x1, y1) in zip(pts[:-1], pts[1:]):
        if t0 <= t < t1:
            if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6: return x0, y0
            u = smooth((t - t0) / (t1 - t0))
            k = 0.16 * (1 if i % 2 == 0 else -1)
            mx = (x0 + x1) / 2 + (y1 - y0) * k; my = (y0 + y1) / 2 - (x1 - x0) * k
            return ((1 - u) ** 2 * x0 + 2 * u * (1 - u) * mx + u * u * x1,
                    (1 - u) ** 2 * y0 + 2 * u * (1 - u) * my + u * u * y1)
    return pts[-1][1], pts[-1][2]

WIN = [[(4.3, 9.4), (10.1, 10.9)], [(12.0, 12.8)], [(13.6, 14.4)], [(15.2, 16.0)], [(16.8, 17.6)], [(18.4, 19.2)],
       [(20.0, 20.8)], [(21.6, 22.4)]]
PUL = [[] for _ in range(8)]
for _k in range(2, NT + 1):
    _ev = EV[_k - 1]
    PUL[3].append(_ev - 0.2); PUL[5].append(_ev); PUL[7].append(_ev + 0.25); PUL[6].append(_ev + 0.4)
for _l in PUL: _l.sort()

def pulse(i, t):
    l = PUL[i]; j = bisect.bisect_right(l, t) - 1
    if j < 0: return 0.0
    d = t - l[j]
    return math.exp(-d / 0.2) if d < 1.0 else 0.0

def lvl(i, t):
    if t >= MONT1: return 0.6 + 0.4 * abs(math.sin(math.pi * (t - MONT1) / BEAT))
    v = 0.0
    for a, b in WIN[i]:
        if a <= t < b:
            v = max(v, min(ramp(t, a, a + 0.15), 1 - ramp(t, b - 0.15, b)))
    if i in (3, 5, 6, 7) and MONT0 + 0.3 <= t < MONT1:
        v = max(v, 0.3 + 0.7 * pulse(i, t))
    return v

# order log shown by the mother: (time, mini idx)
ORD = [(3.2, 0), (9.6, 0)] + [(9.6 + 1.6 * i, i) for i in range(1, 8)]
for _k in range(2, NT + 1):
    _ev = EV[_k - 1]
    ORD += [(_ev - 0.2, 3), (_ev, 5), (_ev + 0.25, 7), (_ev + 0.4, 6)]
ORD.sort()
_ORDT = [o[0] for o in ORD]

def cur_order(t):
    j = bisect.bisect_right(_ORDT, t) - 1
    return ORD[j] if j >= 0 else None

# events for audio
def note_events():
    ev = [(0.45 + 0.05 * i + 0.3, i) for i in range(8)]
    ev += [(9.6 + 1.6 * i + 1.2, i) for i in range(8)]
    for k in range(2, NT + 1):
        e = EV[k - 1]
        ev += [(e - 0.2, 3), (e, 5), (e + 0.25, 7), (e + 0.4, 6)]
    return sorted(ev)

# ---------------------------------------------------------------- state helpers
def counters12(t):
    scanned = int(round(SCANNED * smooth(ramp(t + 0.8, 4.6, 7.6))))
    done = sum(1 for e in EV if t >= e)
    wins = sum(1 for k in range(done) if TR[k]['win'])
    prev = OC.START if done == 0 else TR[done - 1]['after']
    bal = prev
    if done < NT:
        u = easeout(ramp(t, EV[done] - 0.25, EV[done]))
        bal = prev + (TR[done]['after'] - prev) * u
    return scanned, done, wins, done - wins, bal

def nrev12(t):
    return float(np.interp(t, [11.2, 12.8, 15.0, 15.4, 16.0, 17.6, 19.2, 22.4], [9, 14, 14, 15, 15, 35, 35, 48]))

def profit_state(t):
    kd = sum(1 for e in EV if t >= e)
    live = CUM[kd]; xend = float(kd)
    if kd == 0:
        if t >= TB:
            nr = nrev12(t)
            i = min(int(nr - 1e-6), 47)
            live = OC.START * (T1C[i] - 1.0)
            xend = clamp((nr - 15) / 20.0)
        else:
            live = 0.0; xend = 0.0
    elif kd < NT:
        u = easeout(ramp(t, EV[kd] - 0.25, EV[kd]))
        live = CUM[kd] + (CUM[kd + 1] - CUM[kd]) * u
        xend = kd + u
    return kd, live, xend

# ---------------------------------------------------------------- mother
SPR = cv2.resize(c10.HSPR, (int(600 * MS), int(420 * MS)), interpolation=cv2.INTER_AREA)
ALP = cv2.resize(c10.HAL, (int(600 * MS), int(420 * MS)), interpolation=cv2.INTER_AREA)[..., None].astype(np.float32)
OXS = int(300 * MS); OYS = int(275 * MS)

HS3 = 0.86; HCY3 = 262.0
def _proj(p, R, scale, cx, cy, D=1500.0):
    pc = R @ np.array(p, float)
    k = D / (pc[2] + D)
    return cx + scale * pc[0] * k, cy + scale * pc[1] * k

def draw_head12(cv, t, gain, tgt, ecol, L, open_, lean, scan):
    if gain <= 0.02: return
    cx = MX + lean[0]; cy = HCY3 + lean[1]
    pop = easeout(ramp(t, 0.0, 1.3))
    act = clamp(sum(L) / 4.0)
    if tgt is not None:
        look = (clamp((tgt[0] - MX) / 380.0, -1, 1), clamp((tgt[1] - cy) / 260.0, -0.3, 1))
    else:
        look = (0.35 * math.sin(t * 0.8), 0.1)
    yaw = 0.15 * math.sin(t * 0.55) + lean[0] / 8.0 * 0.16
    pitch = 0.035 * math.sin(t * 0.43) - 0.015 + lean[1] / 6.0 * 0.05
    R = O3.rotm(yaw, pitch)
    S_ = O3.mother_surfaces(t, act, ecol, open_, look, pop=pop * gain, glowpulse=0.5 + 0.5 * math.sin(t * 3.2))
    sc = HS3 * (0.82 + 0.18 * pop)
    img = O3.render(S_, R, sc, cx, cy, 1080, 500, ss=2.0, glow=cv.g, glow_off=(0, 0))
    O3.composite(cv.f, img, 0, 0, gain)
    if gain < 0.3: return
    leds, emb = O3.mother_anchor_points(t)
    Rm = R
    for i in range(6):
        x, y = _proj(leds[i], Rm, sc, cx, cy)
        cv.circle((x, y), 6, m(AGN[i][1], 0.15 + 0.85 * L[i]), -1, glow=0.9 * L[i])
    ex, ey = _proj(emb, Rm, sc, cx, cy)
    LG.put(cv, LG.emblem(), ex, ey, 74, 0.95 * gain, 0.35, squeeze=max(0.55, math.cos(yaw * 1.4)))
    if scan is not None:
        x = cx - 190 * MS + 380 * MS * scan
        cv.poly([(x, cy - 10), (x, cy + 50)], m(CY, 0.9 * gain), 3, glow=1.0)

# ---------------------------------------------------------------- minis
def draw_mini(cv, i, t):
    col = MCOL[i]; K = 1.7
    ta = 0.45 + 0.05 * i
    al = ramp(t, ta, ta + 0.15)
    if al <= 0.02: return
    x, y = mini_pos(i, t)
    x2, y2 = mini_pos(i, t + 0.03); x1, y1 = mini_pos(i, t - 0.03)
    vx = (x2 - x1) / 0.06; vy = (y2 - y1) / 0.06
    dx, dy = DOCK[i]
    away = clamp(math.hypot(x - dx, y - dy) / 220.0)
    pop = easeout(ramp(t, ta, ta + 0.5))
    s = (0.58 + 0.34 * away) * (0.4 + 0.6 * pop)
    lv = lvl(i, t)
    sqy = 1.0
    if t >= 39.0:
        ph = (t - 39.0) / BEAT
        y -= 16 * abs(math.sin(math.pi * ph)) * s / 0.58
        sqy = 1 - 0.10 * max(0.0, math.cos(math.pi * ph * 2) ** 8)
    sp = math.hypot(vx, vy)
    st = clamp(sp / 1100.0) * 0.30
    sx = 1 - 0.5 * st; sy = (1 + st) * sqy
    tilt = clamp(vx / 2200.0, -0.3, 0.3)
    sc = s * K
    def P(px, py): return (x + sc * (px * sx + tilt * py), y + sc * py * sy)
    # trail
    if sp > 250:
        for k in range(1, 5):
            tx, ty = mini_pos(i, t - 0.035 * k)
            f = (1 - k / 5.0) * clamp(sp / 900.0)
            cv.circle((tx, ty), 24 * s * (1 - k / 6.0), m(col, 0.28 * f * al), -1, glow=0.4 * f)
    # tether
    if away > 0.15:
        mx_ = (x + dx) / 2; my_ = (y + dy) / 2 + 30
        cv.poly([(dx, dy + 18), (mx_, my_), (x, y - 6)], m(col, 0.28 * al), 1)
    S_ = O3.mini_surfaces(t, i, col, lv, sp)
    for _s in S_:
        _s.P = _s.P * np.array([sx, sy, 1.0]); _s.ref = _s.ref * np.array([sx, sy, 1.0])
    R_ = O3.rotm(clamp(vx / 1800.0, -0.6, 0.6) + 0.14 * math.sin(t * 1.3 + i), clamp(vy / 2500.0, -0.3, 0.3) + 0.05 * math.sin(t * 1.7 + i))
    BX, BY = 130, 112
    gx0, gy0 = int(x) - BX, int(y) - BY
    img_ = O3.render(S_, R_, sc, BX, BY, 260, 260, ss=2.0, glow=cv.g, glow_off=(gx0, gy0))
    O3.composite(cv.f, img_, gx0, gy0, al)
    # tools
    if i == 0:
        a0 = P(0, -30); a1 = P(0, -52)
        cv.poly([a0, a1], m(col, al), 2)
        cv.circle(a1, 3 * s + 1, m(WH, al), -1, glow=0.8 * al)
        for q in range(2):
            fr = (t * 1.6 + q * 0.5) % 1.0
            cv.ellipse(a1, (max(2, int((8 + 22 * fr) * s)), max(1, int((5 + 12 * fr) * s))), m(col, (1 - fr) * al * (0.4 + 0.6 * lv)), 2, a0=200, a1=340)
    elif i == 1:
        c0 = P(30, -24)
        cv.circle(c0, 10 * sc / 1.7 * 1.3, m(col, al), 3, glow=0.6 * al)
        cv.poly([P(37, -17), P(48, -4)], m(col, al), 3)
        cv.circle(c0, 3, m(WH, al * (0.4 + 0.6 * lv)), -1)
    elif i == 2:
        bx = [P(-42, -36), P(-22, -36), P(-22, -18), P(-42, -18)]
        cv.fillpoly(bx, mix(PANEL, col, 0.5), al)
        cv.poly(bx, m(col, al), 2, glow=0.5 * al, closed=True)
        cv.circle(P(-32, -27), 2.5 * s + 1, m(WH, al * (0.5 + 0.5 * lv)), -1)
    elif i == 3:
        for sg in (-1, 1):
            tip = 46 - 9 * lv
            cl = [P(sg * 32, 10), P(sg * tip, -6), P(sg * (tip - 6), -14), P(sg * 30, 0)]
            cv.fillpoly(cl, col, al)
            cv.poly(cl, m(WH, 0.4 * al), 1, closed=True)
    elif i == 4:
        L_ = 40 + 40 * lv
        cv.poly([P(26, 2), P(26 + L_, 2)], m(col, 0.9 * al), 2 + int(lv * 2), glow=0.9 * (0.4 + 0.6 * lv) * al)
        cv.circle(P(26 + L_, 2), 4, m(WH, al), -1, glow=0.9 * al)
    elif i == 5:
        for sg in (-1, 1):
            bl = [P(sg * 30, -6), P(sg * 58, -28), P(sg * 48, -2)]
            cv.fillpoly(bl, mix(col, WH, 0.3 * lv), al)
            cv.poly(bl, m(WH, 0.6 * al), 1, closed=True)
    elif i == 6:
        cc = P(0, -4)
        a0 = int(t * 200) % 360
        cv.ellipse(cc, (max(4, int(48 * s)), max(2, int(13 * s))), m(col, al), 2, glow=0.6 * al, a0=a0, a1=a0 + 250)
        check_icon(cv, *P(0, -42), 9 * s, col, al * (0.4 + 0.6 * lv), 3, glow=0.6)
    elif i == 7:
        cc = P(0, -44)
        cv.circle(cc, 10 * s + 2, m(GOLD, al), -1, glow=0.7 * al)
        cv.text(cc[0], cc[1] + 1, "$", 'mono', max(10, int(18 * s)), INK, al, 'mm')

# ---------------------------------------------------------------- panels / cards
def zframe(cv, a, col, y0=1122, y1=1300):
    pts = chamfer(60, y0, 940, y1, 16)
    cv.fillpoly(pts, mix(PANEL, col, 0.22), 0.95 * a)
    cv.poly(pts, m(col, a), 3, glow=0.9 * a, closed=True)

def card_buy12(cv, a):
    y0, y1 = 1122, 1300; ym = (y0 + y1) / 2
    zframe(cv, a, GR)
    cv.fillpoly(chamfer(80, y0 + 18, 262, y1 - 18, 12), GR, 0.95 * a)
    cv.text(171, ym - 12, "BUY", 'b', 58, INK, a, 'mm')
    cv.text(171, ym + 36, "CONFIRMED", 'b', 24, INK, a, 'mm')
    cv.text(290, y0 + 36, f"${TR[0]['token']}   ·   price {ENTRY:.6f} SOL", 'md', 28, DIM, a, 'lm')
    txt = f"{solf(OC.START)} SOL  ≈  {usd(OC.START)}"
    cv.text(290, y0 + 90, txt, 'mono', fit(txt, 'mono', 52, 560), WH, a, 'lm', glow=0.5)
    cv.text(290, y0 + 144, f"quantity  {qty(0):,}  ${TR[0]['token']}", 'md', 28, GR, a, 'lm')
    cv.text(760, y0 + 144, "7/8 SIGNALS", 'b', 26, GOLD, a, 'lm', glow=0.5)
    check_icon(cv, 880, ym - 14, 24, GR, a, 7, glow=0.9)

def card_sell12(cv, a):
    y0, y1 = 1122, 1300; ym = (y0 + y1) / 2
    tr = TR[0]
    zframe(cv, a, MG)
    cv.fillpoly(chamfer(80, y0 + 18, 262, y1 - 18, 12), MG, 0.95 * a)
    cv.text(171, ym - 12, "SELL", 'b', 58, INK, a, 'mm')
    cv.text(171, ym + 36, "FILLED", 'b', 24, INK, a, 'mm')
    cv.text(290, y0 + 36, f"${TR[0]['token']}   ·   price {EXIT1:.6f} SOL", 'md', 28, DIM, a, 'lm')
    txt = f"{solf(tr['after'])} SOL ≈ {usd(tr['after'])}"
    cv.text(290, y0 + 90, txt, 'mono', fit(txt, 'mono', 36, 400), WH, a, 'lm', glow=0.4)
    cv.text(290, y0 + 144, f"quantity  {qty(0):,}  ${TR[0]['token']}", 'md', 28, MG, a, 'lm')
    cv.text(920, y0 + 44, usd(tr['pnl'], True), 'mono', 54, GR, a, 'rm', glow=0.9)
    cv.text(920, y0 + 98, f"{solf(tr['pnl'], True)} SOL", 'mono', 28, GR, a, 'rm')
    cv.text(920, y0 + 140, f"{tr['ret'] * 100:+.1f}%", 'mono', 30, WH, a, 'rm')

def card_check12(cv, a):
    y0, y1 = 1122, 1300; ym = (y0 + y1) / 2
    zframe(cv, a, CY)
    check_icon(cv, 150, ym, 36, GR, a, 9, glow=0.9)
    cv.text(230, ym - 22, "TRADE VERIFIED", 'b', 52, WH, a, 'lm', glow=0.3)
    cv.text(230, ym + 36, "LOGGER  ·  trade #1 recorded", 'md', 30, DIM, a, 'lm')

def card_pnl12(cv, a, u):
    y0, y1 = 1122, 1300; ym = (y0 + y1) / 2
    tr = TR[0]
    zframe(cv, a, GR)
    cv.text(90, y0 + 36, "TRADE #1  ·  PNL", 'b', 28, DIM, a, 'lm')
    cv.text(90, y0 + 112, usd(tr['pnl'] * u, True), 'mono', 84, GR, a, 'lm', glow=0.9)
    cv.text(920, y0 + 70, f"{solf(tr['pnl'] * u, True)} SOL", 'mono', 44, GR, a, 'rm', glow=0.5)
    cv.text(920, y0 + 130, f"{tr['ret'] * 100 * u:+.1f}%", 'mono', 38, WH, a, 'rm')

SL = [(-1, (1070.0, 0.0)), (0, (1118.0, 100.0)), (1, (1224.0, 40.0)), (2, (1268.0, 36.0)), (3, (1308.0, 0.0))]
def geom(x):
    for (a0, g0), (a1, g1) in zip(SL[:-1], SL[1:]):
        if a0 <= x <= a1:
            u = (x - a0) / (a1 - a0)
            return g0[0] + (g1[0] - g0[0]) * u, g0[1] + (g1[1] - g0[1]) * u
    return SL[-1][1]

def feed_card(cv, a, k, y0, h, hi):
    if h < 10 or a <= 0.02: return
    tr = TR[k - 1]; col = GR if tr['win'] else RD
    x0 = 60
    pts = chamfer(x0, y0, x0 + 880, y0 + h, 12)
    cv.fillpoly(pts, mix(PANEL, col, 0.22 if hi else 0.12), 0.92 * a)
    cv.poly(pts, m(col, a), 3 if hi else 2, glow=(0.9 if hi else 0.2) * a, closed=True)
    pnl = tr['pnl']; tag = "WIN" if tr['win'] else "LOSS"
    if h >= 80:
        cv.text(x0 + 22, y0 + 24, f"#{k}   ${tr['token']}   ·   BUY → SELL", 'b', 28, WH, a, 'lm')
        t2 = f"{solf(tr['before'])} SOL ≈ {usd(tr['before'])}"
        cv.text(x0 + 22, y0 + 56, t2, 'mono', fit(t2, 'mono', 28, 520), WH, a, 'lm')
        t3 = f"qty {qty(k - 1):,}   {price_in(k - 1):.6f} → {price_out(k - 1):.6f}"
        cv.text(x0 + 22, y0 + 82, t3, 'mono', fit(t3, 'mono', 24, 520), DIM, a, 'lm')
        cv.text(x0 + 858, y0 + 30, usd(pnl, True), 'mono', 44, col, a, 'rm', glow=0.8)
        cv.text(x0 + 858, y0 + 64, f"{solf(pnl, True)} SOL", 'mono', 24, col, a, 'rm')
        cv.text(x0 + 858, y0 + 88, f"{tag}  {tr['ret'] * 100:+.1f}%", 'b', 24, col, a, 'rm')
    else:
        txt = f"#{k} ${tr['token']}   {solf(pnl, True)} SOL   {usd(pnl, True)}"
        cv.text(x0 + 20, y0 + h / 2, txt, 'mono', fit(txt, 'mono', 24, 640), mix(WH, col, 0.5), a, 'lm')
        cv.text(x0 + 860, y0 + h / 2, f"{tag} {tr['ret'] * 100:+.1f}%", 'b', 24, col, a, 'rm')

def draw_feed(cv, a, t):
    pts = chamfer(60, 1114, 940, 1306, 16)
    cv.poly(pts, m(CYD, 0.6 * a), 2, closed=True)
    if t < TB + 0.1 or t >= 22.3: cv.text(84, 1136, "ORDER FEED", 'b', 24, DIM, a * 0.8, 'lm') if t < TB + 0.1 else None
    kd = sum(1 for e in EV if t >= e)
    if t < 22.3 or kd < 1: return
    u = easeout(ramp(t, EV[kd - 1], EV[kd - 1] + 0.2)) if kd > 1 else 1.0
    fa = a * ramp(t, 22.3, 22.5)
    for j in range(0, 4):
        kk = kd - j
        if kk < 1: break
        x = j - (1 - u)
        y0, h = geom(x)
        al = 1.0 if 0 <= x <= 2 else (1 + x if x < 0 else max(0.0, 3 - x))
        feed_card(cv, fa * clamp(al), kk, y0, h, hi=(j == 0))

# ---------------------------------------------------------------- stage
CAPS = [(11.2, f"CHART  ·  ANALYST reads ${TR[0]['token']}", CY), (12.8, "WALLET  ·  RISK checks funds", PU),
        (14.4, "BUY  ·  EXECUTOR", GR), (16.0, "TRACK  ·  RISK watches position", PU),
        (17.6, "SELL  ·  EXECUTOR", MG), (19.2, "CHECK  ·  LOGGER verifies", CY), (20.8, "PNL  ·  LOGGER records", GR)]
CX0, CX1, CY0_, CY1_ = PX0 + 22, PX1 - 92, PY0 + 78, PY1 - 40

def draw_trade12(cv, a, t):
    if a <= 0.02: return
    cap = ("", CY)
    for ts_, txt, col in CAPS:
        if t >= ts_: cap = (txt, col)
    c10.draw_panel10(cv, a, f"${TR[0]['token']} / SOL  ·  1m", cap[0], cap[1])
    nrev = nrev12(t)
    c10.draw_grid10(cv, a, ENTRY * T1MIN, ENTRY * T1MAX, CX0, CX1, CY0_, CY1_)
    n = 48; cw = (CX1 - CX0) / n
    yf = lambda p: CY1_ - (p - T1MIN) / (T1MAX - T1MIN) * (CY1_ - CY0_)
    for i in range(n):
        if nrev <= i: break
        fr = clamp(nrev - i)
        o = T1O[i]; c = o + (T1C[i] - o) * fr
        h_ = max(o, c) + (T1H[i] - max(T1O[i], T1C[i])) * fr
        l_ = min(o, c) - (min(T1O[i], T1C[i]) - T1L[i]) * fr
        x = CX0 + (i + 0.5) * cw
        candle(cv, x, 9, yf(o), yf(h_), yf(l_), yf(c), c >= o, a, glow=0.5 if (i == int(nrev) and fr < 1.0) else 0.0)
    if nrev > 1:
        i = min(int(nrev - 1e-6), n - 1)
        fr = clamp(nrev - i); cl = T1O[i] + (T1C[i] - T1O[i]) * fr
        y = yf(cl)
        for xx in range(int(CX0), int(CX1), 14):
            cv.poly([(xx, y), (xx + 7, y)], m(WH, a * 0.55), 1)
        txt = f"{ENTRY * cl:.6f}"
        wd = F('b', 18).getlength(txt)
        cv.rect(CX1 + 8, y - 13, CX1 + 8 + wd + 12, y + 13, mix(CYD, INK, 0.2), a)
        cv.text(CX1 + 14, y, txt, 'b', 18, WH, a, 'lm')
    if t >= TB:
        arrow_marker(cv, CX0 + 14.5 * cw, yf(T1L[14]), True, GR, a, None, 0.7 + 0.4 * easeout((t - TB) / 0.25))
    if t >= TS:
        arrow_marker(cv, CX0 + 34.5 * cw, yf(T1H[34]), False, MG, a, f"SELL {EXIT1:.6f}", 0.7 + 0.4 * easeout((t - TS) / 0.25))
    bx0, by0 = PX0 + 26, PY0 + 86
    if 13.6 <= t < 15.2:
        oa = a * min(ramp(t, 13.6, 13.9), 1 - ramp(t, 14.9, 15.2))
        pts = chamfer(bx0, by0, bx0 + 360, by0 + 112, 14)
        cv.fillpoly(pts, INK, 0.9 * oa)
        cv.poly(pts, m(PU, oa), 2, glow=0.7 * oa, closed=True)
        cv.text(bx0 + 18, by0 + 24, "WALLET", 'b', 24, PU, oa, 'lm')
        cv.text(bx0 + 18, by0 + 62, f"{solf(OC.START)} SOL", 'mono', 38, WH, oa, 'lm', glow=0.4)
        cv.text(bx0 + 18, by0 + 94, f"≈ {usd(OC.START)}  ·  position {solf(OC.START)} SOL", 'md', 20, DIM, oa, 'lm')
    if 16.8 <= t < 22.0:
        oa = a * min(ramp(t, 16.8, 17.1), 1 - ramp(t, 21.6, 22.0))
        i = min(int(nrev - 1e-6), 47); pct = (T1C[i] - 1.0) * 100
        up = OC.START * (T1C[i] - 1.0)
        pts = chamfer(bx0, by0, bx0 + 360, by0 + 84, 12)
        cv.fillpoly(pts, INK, 0.9 * oa)
        cv.poly(pts, m(PU, oa), 2, glow=0.6 * oa, closed=True)
        cv.text(bx0 + 16, by0 + 28, "OPEN PROFIT", 'md', 24, DIM, oa, 'lm')
        cv.text(bx0 + 344, by0 + 28, f"{pct:+.1f}%", 'mono', 32, GR if pct >= 0 else RD, oa, 'rm', glow=0.5)
        cv.text(bx0 + 344, by0 + 62, f"{usd(up, True)}  ·  {solf(up, True)} SOL", 'mono', 22, GR if up >= 0 else RD, oa, 'rm')

def draw_mont12(cv, a, t):
    if a <= 0.02: return
    kd = sum(1 for e in EV if t >= e)
    c10.draw_panel10(cv, a, "SOLANA MARKET  ·  1m", f"{kd}/{NT} trades closed", CY)
    head = 60 + (t - MONT0) * 7.0
    n = 38
    hi_i = int(head); i0 = hi_i - n + 1
    his = np.array([max(MCL[j - 1], MCL[j]) * (1 + MHI_N[j]) for j in range(i0, hi_i + 1)])
    los = np.array([min(MCL[j - 1], MCL[j]) * (1 - MLO_N[j]) for j in range(i0, hi_i + 1)])
    pmin = los.min() * 0.97; pmax = his.max() * 1.03
    cx0, cx1, cy0, cy1 = PX0 + 22, PX1 - 92, PY0 + 78, PY1 - 40
    c10.draw_grid10(cv, a, pmin, pmax, cx0, cx1, cy0, cy1)
    cw = (cx1 - cx0) / n
    yf = lambda p: cy1 - (p - pmin) / (pmax - pmin) * (cy1 - cy0)
    frac = head - hi_i
    for r, j in enumerate(range(i0, hi_i + 1)):
        o = MCL[j - 1]; c = MCL[j]; hh = his[r]; ll = los[r]
        fr = frac if j == hi_i else 1.0
        cc = o + (c - o) * fr
        x = cx0 + (r + 0.5) * cw - frac * cw
        if x < cx0: continue
        candle(cv, x, 11, yf(o), yf(max(o, cc) + (hh - max(o, c)) * fr), yf(min(o, cc) - (min(o, c) - ll) * fr), yf(cc), cc >= o, a)
    for k in range(2, NT + 1):
        ev = EV[k - 1]
        age = t - (ev - 0.2)
        if age < 0 or age > 1.6: continue
        fa = a * (1.0 - 0.7 * ramp(age, 0.8, 1.6))
        sc = 0.55 * (0.6 + 0.4 * easeout(age / 0.2))
        jb = head - age * 7.0
        xb = cx0 + (jb - i0 + 0.5) * cw
        jj = int(jb)
        if cx0 + 6 < xb < cx1 - 6 and 1 <= jj < 900:
            arrow_marker(cv, xb, yf(min(MCL[jj - 1], MCL[jj]) * (1 - MLO_N[jj])), True, GR, fa, None, sc)
        if t >= ev:
            js = head - (t - ev) * 7.0
            xs = cx0 + (js - i0 + 0.5) * cw
            jj = int(js)
            if cx0 + 6 < xs < cx1 - 6 and 1 <= jj < 900:
                win = TR[k - 1]['win']
                arrow_marker(cv, xs, yf(max(MCL[jj - 1], MCL[jj]) * (1 + MHI_N[jj])), False, MG if win else RD, fa, None, sc)

# ---------------------------------------------------------------- deck (chips, buttons)
def draw_actchips(cv, t, a):
    for i in range(8):
        lv = lvl(i, t); col = MCOL[i]
        x0 = 60 + i * 120; x1 = x0 + 114; y0, y1 = 964, 1010
        pts = chamfer(x0, y0, x1, y1, 8)
        cv.fillpoly(pts, mix(PANEL, col, 0.12 + 0.4 * lv), 0.9 * a)
        cv.poly(pts, m(mix(CYD, col, lv), a), 2, glow=0.8 * lv * a, closed=True)
        cv.text((x0 + x1) / 2, (y0 + y1) / 2, NAMES[i], 'b', 22, mix(DIM, WH, 0.3 + 0.7 * lv), a, 'mm')

def last_trade(t, which):
    # index of last BUY/SELL started
    if which == 'buy':
        ks = [k for k in range(NT) if t >= (TB if k == 0 else EV[k] - 0.2)]
    else:
        ks = [k for k in range(NT) if t >= EV[k]]
    return ks[-1] if ks else None

def draw_buttons(cv, t, a):
    for side in ('buy', 'sell'):
        x0, x1 = (60, 500) if side == 'buy' else (580, 1020)
        y0, y1 = 1022, 1104
        col = GR if side == 'buy' else MG
        i = 3 if side == 'buy' else 5
        pl = pulse(i, t) if t >= MONT0 + 0.3 else 0.0
        if t < MONT0:
            tt = TB if side == 'buy' else TS
            pl = math.exp(-(t - tt) / 0.25) if 0 <= t - tt < 1.2 else 0.0
        k = last_trade(t, side)
        press = 4 * pl
        pts = chamfer(x0 + press, y0 + press, x1 - press, y1 - press, 14)
        cv.fillpoly(pts, mix(PANEL, col, 0.18 + 0.5 * pl), 0.95 * a)
        cv.poly(pts, m(col, a), 3, glow=(0.3 + 0.7 * pl) * a, closed=True)
        lx = x0 + 28 if side == 'buy' else x0 + 28
        cv.text(lx, y0 + 28, "BUY" if side == 'buy' else "SELL", 'b', 46, col if pl < 0.5 else WH, a, 'lm', glow=0.5 * pl)
        cv.text(lx, y0 + 62, "EXECUTOR", 'md', 24, DIM, a, 'lm')

def draw_agents(cv, t, a, L):
    for i in range(6):
        col = AGN[i][1]; lv = L[i]
        x0 = 60 + i * 162; w_ = 150; y0 = 1318; h_ = 98
        pts = chamfer(x0, y0, x0 + w_, y0 + h_, 12)
        cv.fillpoly(pts, mix(PANEL, col, 0.28 * lv), 0.85 * a)
        cv.poly(pts, m(mix(CYD, col, lv), a), 2, glow=0.8 * lv * a, closed=True)
        agent_icon(cv, i, (x0 + w_ / 2, y0 + 36), col, a, lv)
        cv.text(x0 + w_ / 2, y0 + 80, AGN[i][0], 'b', 24, mix(DIM, WH, 0.35 + 0.65 * lv), a, 'mm')

def draw_profit12(cv, t, a, pulse_):
    if a <= 0.02: return
    kd, live, xend = profit_state(t)
    pts = chamfer(40, 1428, 1040, 1670, 18)
    gold = t >= MONT1 + 0.2
    col = GOLD if gold else (GR if live >= 0 else RD)
    cv.fillpoly(pts, mix(PANEL, col, 0.10), 0.9 * a)
    cv.poly(pts, m(col, a), 2, glow=(0.4 + 0.5 * pulse_) * a, closed=True)
    cv.text(70, 1458, "LIVE PROFIT", 'b', 30, WH, a, 'lm')
    has = kd or t >= TB
    cv.text(70, 1494, f"≈ {solf(live, True)} SOL" if has else "waiting for first trade", 'mono' if has else 'md', 26, DIM, a, 'lm')
    sz = int((128 if gold else 108) * (1 + 0.06 * pulse_))
    cv.text(940, 1500, usd(live, True), 'mono', sz, col, a, 'rm', glow=(1.0 if gold else 0.8))
    x0, x1, y0, y1 = 130, 890, 1568, 1646
    xmax = max(1.0, xend)
    vals = CUM[:kd + 1] + [live]
    ymax = max(100.0, max(vals)) * 1.18
    ymin = min(0.0, min(vals)) * 1.3
    X = lambda x: x0 + x / xmax * (x1 - x0)
    Y = lambda v: y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
    step = 10 ** math.floor(math.log10(max(ymax, 1) / 3.0))
    for mult in (1, 2, 5, 10):
        if ymax / (step * mult) <= 3: step *= mult; break
    v = math.ceil(ymin / step) * step
    while v <= ymax:
        yy = Y(v)
        cv.poly([(x0, yy), (x1, yy)], m(CYD, a * (0.7 if abs(v) < 1e-9 else 0.3)), 1)
        cv.text(x0 - 10, yy, moneyk(v), 'md', 20, DIM, a, 'rm')
        v += step
    px = [(X(0), Y(0.0))] + [(X(j), Y(CUM[j])) for j in range(1, kd + 1)]
    if kd < NT and (xend > kd + 1e-6 or kd == 0):
        px.append((X(xend), Y(live)))
    if len(px) >= 2:
        area = [(px[0][0], Y(0.0))] + px + [(px[-1][0], Y(0.0))]
        cv.fillpoly(area, GR, 0.12 * a)
        for j in range(1, len(px)):
            up = px[j][1] <= px[j - 1][1]
            c_ = GR if up else RD
            newest = j == len(px) - 1
            cv.poly([px[j - 1], px[j]], m(GOLD if gold and newest else c_, a), 5 if newest else 3, glow=(1.0 if newest else 0.25) * a)
        for j in range(1, len(px) - 1):
            cv.circle(px[j], 3, m(WH, a * 0.8), -1)
        hd = px[-1]
        cv.circle(hd, 8, m(GOLD if gold else WH, a), -1, glow=1.0 * a)
    cv.text(x1, y1 + 14, f"trade {min(NT, int(round(xend)))}/{NT}", 'md', 24, DIM, a, 'rm')

def draw_tiles(cv, t, a, vals):
    scanned, done, wins, losses, bal = vals
    tiles = [("TOKENS SCANNED", f"{scanned:,}", WH, None), ("TRADES", f"{done}/{NT}", WH, None),
             ("WINS / LOSSES", None, None, None), ("BALANCE", usd(bal), CY, f"≈ {solf(bal)} SOL")]
    for i, (lab, val, col, sub) in enumerate(tiles):
        x0 = 40 + i * 252; x1 = x0 + 242; y0, y1 = 1684, 1784
        pts = chamfer(x0, y0, x1, y1, 14)
        cv.fillpoly(pts, PANEL, 0.85 * a)
        cv.poly(pts, m(CYD, a), 2, closed=True)
        cv.text(x0 + 16, y0 + 22, lab, 'b', 22, DIM, a, 'lm')
        if val is not None:
            sz = fit(val, 'mono', 42, 214)
            cv.text(x0 + 16, y0 + 58, val, 'mono', sz, col, a, 'lm', glow=0.35 if i == 3 else 0.0)
            if sub: cv.text(x0 + 16, y0 + 80, sub, 'mono', 22, DIM, a, 'lm')
        else:
            cv.text(x0 + 16, y0 + 58, f"{wins}", 'mono', 42, GR, a, 'lm', glow=0.35)
            wd = F('mono', 42).getlength(f"{wins}")
            cv.text(x0 + 16 + wd + 8, y0 + 58, "/", 'mono', 36, DIM, a, 'lm')
            cv.text(x0 + 16 + wd + 34, y0 + 58, f"{losses}", 'mono', 42, RD, a, 'lm', glow=0.35)

# ---------------------------------------------------------------- effects
def fx_buy(cv, t, tb):
    d = t - tb
    if not (0 <= d < 0.5): return
    u = d / 0.7
    c = (ST[3][0], ST[3][1] + 20)
    cv.ellipse(c, (int(40 + 260 * easeout(u)), int(24 + 90 * easeout(u))), m(GR, 1 - u), 4, glow=1.0 * (1 - u))
    cv.ellipse(c, (int(20 + 160 * easeout(u)), int(12 + 56 * easeout(u))), m(WH, 0.8 * (1 - u)), 2)

def fx_sell(cv, t, ts, win, seed):
    d = t - ts
    if not (0 <= d < 0.7): return
    u = d / 0.7
    col = MG if win else RD
    x0 = 640 + 30 * ((seed * 7) % 3); y0 = int(ST[5][1]) - 4
    cv.poly([(x0, y0), (x0 + 300 * easeout(u * 1.4 if u < 0.7 else 1), y0 + 110 * easeout(u * 1.4 if u < 0.7 else 1))],
            m(col, 1 - u), 6, glow=1.0 * (1 - u))
    cv.poly([(x0 + 40, y0 - 10), (x0 + 340 * easeout(min(1, u * 1.4)), y0 + 100 * easeout(min(1, u * 1.4)))], m(WH, 0.8 * (1 - u)), 2)
    if win:
        rng = np.random.default_rng(seed)
        for q in range(14):
            ang = rng.uniform(-3.14, 0.0); sp = rng.uniform(80, 280)
            px_ = ST[5][0] + math.cos(ang) * sp * u; py_ = ST[5][1] + 10 + math.sin(ang) * sp * u + 260 * u * u
            cv.circle((px_, py_), 5, m(GOLD, 1 - u), -1, glow=0.8 * (1 - u))

# ---------------------------------------------------------------- intro title
def draw_intro12(cv, t):
    a = ramp(t, 0.0, 0.2) * (1 - ramp(t, 2.7, 3.1))
    if a <= 0: return
    pop = easeout(ramp(t, 0.0, 0.6))
    LG.put(cv, LG.emblem(), 540, 560, int(250 * (0.85 + 0.15 * pop)), a, 0.7, shine=clamp((t - 0.3) / 1.6))
    LG.put(cv, LG.wordmark(120, OC.NAME), 540, 770, 640, a * ramp(t, 0.1, 0.45), 0.6)
    cv.text(540, 852, "8 AI SCAN THE SIGNALS  ·  SOLANA", 'md', 30, CY, a * ramp(t, 0.3, 0.7), 'mm', glow=0.3)
    cv.text(540, 912, f"{SCANNED:,} NEW TOKENS  →  {OC.SHORT} PASS THE FILTER", 'b', 36, GOLD, a * ramp(t, 0.6, 1.0), 'mm', glow=0.5)

def agent_levels12(t):
    L = [0.0] * 6
    for i in range(6):
        ta = 1.6 + 0.3 * i
        L[i] = 0.35 if t >= ta + 0.4 else (math.sin(math.pi * clamp((t - ta) / 0.7)) ** 0.6 if ta <= t < ta + 0.7 else 0.0)
    for s in range(8):
        lv = lvl(s, t)
        for a_ in AG_MAP[s]:
            L[a_] = max(L[a_], 0.35 + 0.65 * lv)
    if t >= MONT1:
        for i in range(6): L[i] = max(L[i], 0.72 + 0.28 * math.sin(t * 4 + i))
    return L


DYS = 2
class Shift:
    def __init__(self, cv, dy): self.cv = cv; self.dy = dy
    def _p(self, pts): return [(p[0], p[1] + self.dy) for p in pts]
    def poly(self, pts, *a, **k): return self.cv.poly(self._p(pts), *a, **k)
    def circle(self, c, *a, **k): return self.cv.circle((c[0], c[1] + self.dy), *a, **k)
    def ellipse(self, c, *a, **k): return self.cv.ellipse((c[0], c[1] + self.dy), *a, **k)
    def fillpoly(self, pts, *a, **k): return self.cv.fillpoly(self._p(pts), *a, **k)
    def rect(self, x0, y0, x1, y1, *a, **k): return self.cv.rect(x0, y0 + self.dy, x1, y1 + self.dy, *a, **k)
    def text(self, x, y, *a, **k): return self.cv.text(x, y + self.dy, *a, **k)

# ---------------------------------------------------------------- frame

# ---------------------------------------------------------------- virtual camera
def camera17(img, t):
    s_ = 1.0; dx = dy = 0.0; cx, cy = 540.0, 960.0
    if t < 2.6:
        s_ += 0.07 * (1 - easeout(t / 2.6)); cx, cy = 540.0, 300.0
    for j, e in enumerate(EV):
        d = t - e
        if 0 <= d < 0.5:
            amp = 0.045 if j in FEAT else 0.012
            if j == NT - 1: amp = 0.0
            s_ += amp * math.exp(-d / 0.12)
            sh = (7.0 if j in FEAT else 3.0) * math.exp(-d / 0.10) * math.sin(d * 70)
            if TR[j]['win']: dx += sh
            else: dy += sh
    d = t - MONT1
    if 0 <= d < 1.0: s_ += 0.05 * math.exp(-d / 0.3)
    if s_ == 1.0 and dx == 0.0 and dy == 0.0: return img
    M = np.float32([[s_, 0, cx * (1 - s_) + dx], [0, s_, cy * (1 - s_) + dy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)


# ===================== V3c: 8 AI scan signals =====================
_lvl15 = lvl
def lvl(i, t):
    v = _lvl15(i, t)
    if MONT0 + 0.3 <= t < MONT1 and i in (0, 1, 2, 4):
        v = max(v, 0.25 + 0.55 * abs(math.sin(t * 2.1 + i * 1.3)))
    return v

_sr = np.random.default_rng(OC.SEED + 21)
_T0 = TR[0]['token']
_liq = round(float(_sr.uniform(18, 64)), 1); _mom = round(float(_sr.uniform(4.5, 9.5)), 1)
_volx = round(float(_sr.uniform(2.2, 4.8)), 1); _sw = int(_sr.integers(3, 7)); _trail = int(_sr.integers(6, 12))
SIGE = []
_scan_names = [TOKENS[(10 + k) % len(TOKENS)] for k in range(20)]
for k in range(12):
    SIGE.append((3.8 + 0.47 * k, 0, f"${_scan_names[k]}  ·  new pool  ·  age {int(_sr.integers(8, 90))}s"))
SIGE.append((9.1, 0, f"{OC.SHORT} of {SCANNED:,} tokens pass the filter"))
SIGE += [(10.4, 0, f"${_T0}  ·  new pool  ·  liquidity {_liq} SOL"),
         (12.4, 1, f"breakout +{_mom}%  ·  volume x{_volx}"),
         (14.0, 2, f"{_sw} smart wallets entering"),
         (15.0, 3, "entry signal 7/8 confirmed"),
         (17.2, 4, f"trend holding  ·  trail stop {_trail}%"),
         (18.2, 5, "exit signal  ·  target reached"),
         (19.8, 6, "mint revoked  ·  LP locked"),
         (21.9, 7, "trade #1 logged")]
SIGE.sort()
_SIGT = [e[0] for e in SIGE]

def _n(i, t): return 0.5 + 0.5 * math.sin(t * (0.9 + 0.17 * i) + i * 2.1)

def sig_val(i, t):
    lv = lvl(i, t); n = _n(i, t)
    if i == 0:
        v = int(10 + 9 * n); return f"{v}/min", v / 20.0
    if i == 1:
        x = (2 + 7 * n) * (0.6 + 0.4 * lv) + 0.0; return f"+{x:.1f}%", x / 10.0
    if i == 2:
        k = 1 + int(5 * n); return f"{k} smart", k / 6.0
    if i == 3:
        v = 52 + 30 * n; v = v + (88 - v) * lv; return f"{int(v)}/100", v / 100.0
    if i == 4:
        v = 60 + 35 * n; return f"HOLD {int(v)}", v / 100.0
    if i == 5:
        v = 25 + 40 * n; v = v + (90 - v) * lv; return f"{int(v)}/100", v / 100.0
    if i == 6:
        v = 88 + 10 * n; return f"SAFE {int(v)}", v / 100.0
    sc_, done, wins, losses, bal = counters12(t)
    return f"{wins}W {losses}L", (wins / max(1, done) if done else 0.0)

def draw_strip17(cv, t, a):
    for i in range(8):
        x0 = 60 + i * 120; x1 = x0 + 114; y0, y1 = 1022, 1104
        lv = lvl(i, t); col = MCOL[i]
        pts = chamfer(x0, y0, x1, y1, 10)
        cv.fillpoly(pts, mix(PANEL, col, 0.10 + 0.40 * lv), 0.92 * a)
        cv.poly(pts, m(mix(CYD, col, lv), a), 2, glow=0.8 * lv * a, closed=True)
        cv.text((x0 + x1) / 2, y0 + 20, NAMES[i], 'b', 20, mix(DIM, col, 0.5 + 0.5 * lv), a, 'mm')
        txt, fr = sig_val(i, t)
        cv.text((x0 + x1) / 2, y0 + 47, txt, 'mono', fit(txt, 'mono', 24, 100), WH, a, 'mm')
        cv.rect(x0 + 10, y1 - 15, x1 - 10, y1 - 9, mix(PANEL, CYD, 0.5), a)
        cv.rect(x0 + 10, y1 - 15, x0 + 10 + (x1 - x0 - 20) * clamp(fr), y1 - 9, col, a)

def _card_a(t):
    r = 0.0
    for (a0, a1, b0, b1) in [(TB + 0.1, TB + 0.3, TB + 1.4, TB + 1.6), (TS + 0.1, TS + 0.3, TS + 1.4, TS + 1.6), (20.0, 20.2, 20.6, 20.8), (20.8, 21.0, 22.1, 22.3)]:
        r = max(r, ramp(t, a0, a1) * (1 - ramp(t, b0, b1)))
    return r

def draw_feed17(cv, a, t):
    if t >= 22.3: return draw_feed(cv, a, t)
    a = a * (1 - _card_a(t))
    pts = chamfer(60, 1114, 940, 1306, 16)
    cv.poly(pts, m(CYD, 0.6 * a), 2, closed=True)
    cv.text(84, 1136, "SIGNAL FEED", 'b', 24, DIM, a * 0.8, 'lm')
    kd = bisect.bisect_right(_SIGT, t)
    cv.text(916, 1136, f"{kd} signals", 'md', 22, DIM, a * 0.8, 'rm')
    for j in range(4):
        k = kd - 1 - j
        if k < 0: break
        te, ii, txt = SIGE[k]
        u = easeout(ramp(t, te, te + 0.18)) if j == 0 else 1.0
        al = a * u * (1.0, 0.8, 0.6, 0.42)[j]
        y = 1172 + 38 * j + (1 - u) * 14
        col = MCOL[ii]
        cv.fillpoly(chamfer(80, y - 15, 178, y + 15, 7), mix(PANEL, col, 0.40), 0.95 * al)
        cv.text(129, y, NAMES[ii], 'b', 20, WH, al, 'mm')
        if txt.startswith("$") or True:
            cv.text(196, y, txt, 'md', fit(txt, 'md', 26, 730), mix(WH, col, 0.18) if j == 0 else WH, al, 'lm')

def draw_packets(cv, t):
    if t < 3.4 or t >= MONT1: return
    for i in range(8):
        lv = lvl(i, t)
        if lv < 0.4: continue
        col = MCOL[i]
        px_, py_ = mini_pos(i, t)
        sx, sy = px_, py_ - 18
        for q in range(3):
            ph = (t * 1.9 + q / 3.0 + i * 0.17) % 1.0
            mx_ = (sx + MOUTH[0]) / 2 + (1 if i % 2 else -1) * 60; my_ = (sy + MOUTH[1]) / 2 - 40
            x = (1 - ph) ** 2 * sx + 2 * ph * (1 - ph) * mx_ + ph * ph * MOUTH[0]
            y = (1 - ph) ** 2 * sy + 2 * ph * (1 - ph) * my_ + ph * ph * MOUTH[1]
            al = math.sin(math.pi * ph) ** 0.6 * min(1.0, lv * 1.4)
            for tr_ in range(1, 4):
                p2 = ph - 0.035 * tr_
                if p2 < 0: break
                x2 = (1 - p2) ** 2 * sx + 2 * p2 * (1 - p2) * mx_ + p2 * p2 * MOUTH[0]
                y2 = (1 - p2) ** 2 * sy + 2 * p2 * (1 - p2) * my_ + p2 * p2 * MOUTH[1]
                cv.circle((x2, y2), 5 - tr_, m(col, al * (1 - tr_ / 4.0)), -1, glow=0.5 * al)
            cv.circle((x, y), 6, m(col, al), -1, glow=1.0 * al)
            cv.circle((x, y), 2, m(WH, al), -1)

def render17(t):
    cv = Cv(BG)
    core.particles(cv, t)
    aUI = ramp(t, 0.7, 2.0)
    dimf = 1.0
    for (a0, a1) in [(TB + 0.1, TB + 1.6), (TS + 0.1, TS + 1.6), (20.0, 22.3)]:
        if a0 <= t < a1: dimf = 0.62
    L = agent_levels12(t)
    draw_intro12(cv, t)
    # stage
    if 3.0 <= t < 9.9:
        c10.draw_funnel(cv, ramp(t, 3.0, 3.4) * (1 - ramp(t, 9.3, 9.6)), t + 0.8)
    if 9.5 <= t < 11.5:
        c10.draw_scan10(cv, ramp(t, 9.5, 9.75) * (1 - ramp(t, 11.0, 11.3)), t + 0.4)
    if 11.1 <= t < 22.7:
        draw_trade12(cv, ramp(t, 11.1, 11.4) * (1 - ramp(t, 22.15, 22.4)), t)
    if 22.2 <= t < 38.7:
        draw_mont12(cv, ramp(t, 22.2, 22.5) * (1 - ramp(t, 38.1, 38.4)), t)
    if t >= 38.1:
        c10.draw_results(cv, ramp(t, 38.1, 38.5) * (1 - ramp(t, 42.3, 42.6)), t)
    pulse_ = 0.0
    if t >= MONT1: pulse_ = max(0.0, math.sin(clamp((t - MONT1) / 1.2) * math.pi))
    if aUI > 0:
        sh = Shift(cv, DYS)
        draw_strip17(sh, t, aUI)
        draw_feed17(sh, aUI, t)
        draw_agents(sh, t, aUI * dimf, L)
        draw_profit12(sh, t, aUI, pulse_)
        draw_tiles(sh, t, aUI * dimf, counters12(t))
    # trade-1 cards
    ca = ramp(t, TB + 0.1, TB + 0.3) * (1 - ramp(t, TB + 1.4, TB + 1.6))
    sh = Shift(cv, DYS)
    if ca > 0.02: card_buy12(sh, ca)
    ca = ramp(t, TS + 0.1, TS + 0.3) * (1 - ramp(t, TS + 1.4, TS + 1.6))
    if ca > 0.02: card_sell12(sh, ca)
    ca = ramp(t, 20.0, 20.2) * (1 - ramp(t, 20.6, 20.8))
    if ca > 0.02: card_check12(sh, ca)
    ca = ramp(t, 20.8, 21.0) * (1 - ramp(t, 22.1, 22.3))
    if ca > 0.02: card_pnl12(sh, ca, easeout(ramp(t, 20.8, 21.8)))
    cv.text(40, 140, "Illustrative figures", 'md', 24, mix(DIM, WH, 0.45), ramp(t, 0.0, 0.4), 'lm')
    cv.text(40, 170, "Not financial advice", 'md', 24, mix(DIM, WH, 0.45), ramp(t, 0.0, 0.4), 'lm')
    # fx
    fx_buy(cv, t, TB)
    fx_sell(cv, t, TS, TR[0]['win'], 1)
    for k in range(2, NT + 1):
        e = EV[k - 1]
        if e - 0.3 <= t < e + 0.7:
            fx_buy(cv, t, e - 0.2)
            fx_sell(cv, t, e, TR[k - 1]['win'], k)
    # command beams
    for (to, ii) in ORD:
        d = t - to
        if 0 <= d < 0.35 and t < MONT0 + 0.0 or (0 <= d < 0.2 and t >= MONT0 and t < MONT1 and False):
            dk = DOCK[ii]; u = easeout(d / 0.3)
            cv.poly([MOUTH, (MOUTH[0] + (dk[0] - MOUTH[0]) * u, MOUTH[1] + (dk[1] - 24 - MOUTH[1]) * u)], m(CY, 1 - d / 0.35), 3, glow=1.0 * (1 - d / 0.35))
            if d > 0.2:
                cv.ellipse((dk[0], dk[1]), (int(20 + 50 * (d - 0.2) / 0.15), int(14 + 34 * (d - 0.2) / 0.15)), m(CY, 1 - (d - 0.2) / 0.15), 2, glow=0.8)
    # dock bar
    da = aUI if aUI > 0 else ramp(t, 1.0, 1.6)
    cv.poly([(120, 470), (960, 470)], m(CYD, 0.7 * da), 2, glow=0.3 * da)
    for i in range(8):
        d = DOCK[i]
        cv.poly([(d[0] - 34, 470), (d[0] - 24, 462), (d[0] + 24, 462), (d[0] + 34, 470)], m(MCOL[i], 0.65 * da), 2, glow=0.4 * da * (0.3 + lvl(i, t)))
        cv.text(d[0], 453, NAMES[i], 'b', 22, mix(DIM, MCOL[i], 0.4 + 0.6 * lvl(i, t)), da * ramp(t, 1.6, 2.4), 'mm')
    # minis
    draw_packets(cv, t)
    for i in range(8): draw_mini(cv, i, t)
    # mother side text
    gain = easeout(ramp(t, 0.0, 1.4))
    ta_ = ramp(t, 1.6, 2.4)
    _sa = ramp(t, 2.6, 3.2)
    LG.put(cv, LG.emblem(), 72, 90, 62, _sa, 0.3)
    cv.text(116, 90, OC.NAME, 'b', 40, WH, _sa, 'lm', glow=0.4)
    od = cur_order(t)
    if t >= MONT1:
        cv.text(960, 92, "MISSION", 'md', 24, DIM, ta_, 'rm')
        cv.text(960, 146, "COMPLETE", 'b', 48, GOLD, ta_, 'rm', glow=0.8)
        cv.text(960, 200, f"{NT} trades closed", 'md', 24, DIM, ta_, 'rm')
    elif od is not None:
        oc = MCOL[od[1]]
        fl = 1.0 if t - od[0] > 0.2 else 0.5 + 2.5 * (t - od[0])
        cv.text(960, 92, "ORDER", 'md', 24, DIM, ta_, 'rm')
        cv.text(960, 146, NAMES[od[1]], 'b', 54, oc, ta_ * min(1.0, fl), 'rm', glow=0.8)
        cv.text(960, 202, f"{ROLE[od[1]]}", 'md', 24, DIM, ta_, 'rm')
    # mother
    best = max(range(8), key=lambda i: lvl(i, t))
    tgt = None; lean = (0.0, 0.0)
    ecol = CY
    if lvl(best, t) > 0.3:
        px_, py_ = mini_pos(best, t)
        tgt = (px_, py_)
        lean = (clamp((px_ - MX) / 540.0, -1, 1) * 8, clamp((py_ - 400) / 1200.0, 0, 1) * 6)
        ecol = mix(CY, MCOL[best], 0.7 * lvl(best, t))
    for e in EV:
        if e <= t < e + 0.25: ecol = mix(ecol, RD if not TR[EV.index(e)]['win'] else GR, 0.6)
    scan = None
    if 0.8 <= t < 2.4: scan = ((t - 0.8) % 0.8) / 0.8
    open_ = easeout(ramp(t, 0.3, 0.9))
    draw_head12(cv, t, gain, tgt, ecol, L, open_, lean, scan)
    if 0.5 <= t < 1.6:
        u = ramp(t, 0.5, 1.6)
        cv.ellipse((MX, MY + 20), (int(120 + 700 * easeout(u)), int(90 + 500 * easeout(u))), m(CY, 1 - u), 3, glow=1.0 * (1 - u))
    if MONT1 <= t < MONT1 + 1.5:
        u = ramp(t, MONT1, MONT1 + 1.5)
        cv.flash = (1 - ramp(t, MONT1, MONT1 + 0.5)) * 0.9
        for k in range(28):
            ang = k * 2 * math.pi / 28 + 0.1
            r0 = 140 + 700 * easeout(u); r1 = r0 + 60 + 120 * (1 - u)
            col = CY if k % 2 else PU
            cv.poly([(MX + r0 * math.cos(ang), MY + 30 + r0 * math.sin(ang) * 0.9),
                     (MX + r1 * math.cos(ang), MY + 30 + r1 * math.sin(ang) * 0.9)], m(col, (1 - u) * 0.9), 3, glow=1.0 * (1 - u))
        cv.ellipse((MX, MY + 20), (int(200 + 600 * easeout(u)), int(160 + 480 * easeout(u))), m(WH, (1 - u)), 4, glow=1.0 * (1 - u))
    if abs(t - TS) < 0.12: cv.flash = max(cv.flash, 0.2)
    # feature trade overlay
    for j in FEAT:
        d = t - EV[j]
        if 0 <= d < 1.0:
            al = ramp(d, 0.0, 0.12) * (1 - ramp(d, 0.7, 1.0))
            col = GR if TR[j]['win'] else RD
            cv.rect(PX0 + 10, 650, PX1 - 10, 850, INK, 0.62 * al)
            cv.text(540, 722 - 26 * d, usd(TR[j]['pnl'], True), 'mono', 112, col, al, 'mm', glow=1.0)
            cv.text(540, 818, f"TRADE #{j + 1}  ·  ${TR[j]['token']}  ·  {TR[j]['ret'] * 100:+.1f}%", 'b', 30, WH, al, 'mm')
    # end card: realistic comment box typing the keyword
    ea = ramp(t, 42.4, 42.8)
    if ea > 0:
        _p = chamfer(PX0, PY0, PX1, PY1, 26)
        cv.fillpoly(_p, mix(PANEL, GOLD, 0.08), 0.96 * ea)
        cv.poly(_p, m(GOLD, ea), 3, glow=0.7 * ea, closed=True)
        LG.put(cv, LG.emblem(), 540, 606, 128, ea, 0.5, shine=clamp((t - 42.5) / 1.4))
        cv.text(540, 704, 'COMMENT', 'b', 42, WH, ea, 'mm', glow=0.3)
        word = OC.CTA
        n = int(clamp((t - 42.95) / (0.16 * len(word) + 1e-6), 0, 1) * len(word) + 1e-6)
        n = min(len(word), max(0, int((t - 42.95) / 0.17)))
        sent = t >= 43.85
        # input bar
        bx0, by0, bx1, by1 = 190, 746, 890, 836
        def rr(x0, y0, x1, y1, r, k=10):
            pts = []
            for (cx_, cy_, a0) in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0), (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
                for q in range(k + 1):
                    an = math.radians(a0 + 90 * q / k)
                    pts.append((cx_ + r * math.cos(an), cy_ + r * math.sin(an)))
            return pts
        flash = math.exp(-(t - 43.85) / 0.25) if sent else 0.0
        bar = rr(bx0, by0, bx1, by1, 45)
        cv.fillpoly(bar, mix((16, 20, 40), GR, 0.25 * flash), 0.98 * ea)
        cv.poly(bar, m(mix((70, 82, 130), GR if sent else CY, 0.6 if (sent or (n > 0)) else 0.0), ea), 2, glow=(0.2 + 0.7 * flash) * ea, closed=True)
        LG.put(cv, LG.emblem(), bx0 + 48, (by0 + by1) / 2, 46, ea, 0.0)
        if not sent:
            if n == 0:
                cv.text(bx0 + 96, (by0 + by1) / 2, 'Add a comment…', 'md', 30, DIM, ea * 0.9, 'lm')
            typed = word[:n]
            if typed:
                cv.text(bx0 + 96, (by0 + by1) / 2, typed, 'sb', 40, WH, ea, 'lm')
            tw = F('sb', 40).getlength(typed) if typed else 0
            if int(t * 2.2) % 2 == 0 and t >= 42.8:
                cv.rect(bx0 + 98 + tw, (by0 + by1) / 2 - 20, bx0 + 101 + tw, (by0 + by1) / 2 + 20, WH, ea)
        pa = 0.35 + 0.65 * (1.0 if n > 0 else 0.0)
        press = math.exp(-(t - 43.78) / 0.12) if 43.78 <= t < 44.2 else 0.0
        cv.text(bx1 - 40, (by0 + by1) / 2, 'Post', 'b', 32 - int(3 * press), mix(DIM, CY, 1.0 if n > 0 else 0.0), ea * pa, 'rm', glow=0.5 * (n > 0) * ea)
        if sent:
            u = easeout(ramp(t, 43.85, 44.25))
            ry = 882 + (1 - u) * 24
            cv.fillpoly(rr(bx0, ry, bx1, ry + 74, 22, 6), (14, 20, 40), 0.95 * ea * u)
            LG.put(cv, LG.emblem(), bx0 + 40, ry + 37, 44, ea * u, 0.0)
            cv.text(bx0 + 84, ry + 22, 'you', 'b', 24, WH, ea * u, 'lm')
            cv.text(bx0 + 150, ry + 22, 'now', 'md', 22, DIM, ea * u, 'lm')
            cv.text(bx0 + 84, ry + 52, word, 'sb', 30, WH, ea * u, 'lm')
            hx, hy = bx1 - 40, ry + 37
            cv.circle((hx - 7, hy - 4), 8, m((255, 70, 110), ea * u), -1)
            cv.circle((hx + 7, hy - 4), 8, m((255, 70, 110), ea * u), -1)
            cv.fillpoly([(hx - 15, hy), (hx + 15, hy), (hx, hy + 18)], (255, 70, 110), ea * u)
    return camera17(cv.finish(), t)


# =====================================================================================
# V5  (10/10 pass): cinematic mother, hook, spotlight, captions, clean deck, loop ending
# =====================================================================================
HS5 = 0.92; HCY5 = 272.0

def draw_head18(cv, t, tgt, ecol, open_, lean, act, roar=0.0, reveal=1.0, eyes=1.0, lash=None, under=None, squash=1.0, flare=0.0):
    cx = MX + lean[0]; cy = HCY5 + lean[1]
    if tgt is not None:
        look = (clamp((tgt[0] - MX) / 380.0, -1, 1), clamp((tgt[1] - cy) / 260.0, -0.3, 1))
    else:
        look = (0.35 * math.sin(t * 0.8), 0.1)
    yaw = 0.13 * math.sin(t * 0.5) + lean[0] / 8.0 * 0.16
    pitch = 0.03 * math.sin(t * 0.4) - 0.03 + lean[1] / 6.0 * 0.05 - 0.05 * roar
    R = O3.rotm(yaw, pitch)
    S_ = O2.mother_surfaces2(t, act, ecol, open_, look, pop=1.0, glowpulse=0.5 + 0.5 * math.sin(t * 3.2), roar=roar,
                             reveal=reveal, lash=lash, eyes=eyes)
    sc = HS5 * squash
    img = O3.render(S_, R, sc, cx, cy, 1080, 540, ss=2.0, glow=cv.g, glow_off=(0, 0), rimk=0.72,
                    rimcol=(0.55, 0.35, 1.0), under=under, glowk=0.5)
    O3.composite(cv.f, img, 0, 0, 1.0)
    if reveal > 0.6:
        leds, emb = O2.anchor_points()
        ex, ey = _proj(emb, R, sc, cx, cy)
        LG.put(cv, LG.emblem(), ex, ey, 62, 0.95 * clamp((reveal - 0.6) / 0.4), 0.35, squeeze=max(0.55, math.cos(yaw * 1.4)))
    if flare > 0.02:
        for p in O2.eye_points():
            x, y = _proj(p, R, sc, cx, cy)
            cv.poly([(x - 260 * flare, y), (x + 260 * flare, y)], m(ecol, 0.55 * flare), 2, glow=1.0 * flare)
            cv.poly([(x - 90 * flare, y), (x + 90 * flare, y)], m(WH, 0.7 * flare), 3, glow=1.0 * flare)

# ---- spotlight weights
_KT = [0.0, 3.2, 9.4, 9.8, 22.2, 22.6, 38.2, 38.6, 42.4, 44.8]
_KW = {'strip': [1, 0.75, 0.75, 1, 1, 0.7, 0.7, 0.55, 0.35, 0.2],
       'feed': [1, 1, 1, 1, 1, 1, 1, 0.55, 0.35, 0.2],
       'profit': [1, 0.5, 0.5, 0.55, 0.55, 1, 1, 1, 0.45, 0.2],
       'tiles': [1, 0.8, 0.8, 0.65, 0.65, 0.85, 0.85, 0.85, 0.35, 0.2]}
def wt(k, t):
    v = float(np.interp(t, _KT, _KW[k]))
    if k == 'profit' and TS - 0.2 <= t < 22.6: v = 1.0
    return v

# ---- captions
CAP18 = [(3.4, 5.6, f"SCAN: {SCANNED:,} NEW TOKENS", CY), (5.7, 7.7, f"ONLY {OC.SHORT} PASS THE FILTER", GOLD),
         (11.8, 13.7, f"CHART: BREAKOUT +{_mom}%", (70, 140, 255)), (13.9, 15.4, "7/8 SIGNALS  →  BUY", GR),
         (18.4, 20.3, f"SELL  {TR[0]['ret'] * 100:+.0f}%", MG), (22.6, 25.0, f"{NT - 1} MORE TRADES. SAME 8 AI.", CY)]
def draw_caps(cv, t):
    for (t0, t1, txt, col) in CAP18:
        if not (t0 <= t < t1): continue
        a = ramp(t, t0, t0 + 0.12) * (1 - ramp(t, t1 - 0.15, t1))
        pop = easeout(ramp(t, t0, t0 + 0.25))
        sz = fit(txt, 'b', 48, 880)
        w = F('b', sz).getlength(txt) + 64
        y = 930 + 12 * (1 - pop)
        pts = chamfer(540 - w / 2, y - 38, 540 + w / 2, y + 38, 14)
        cv.fillpoly(pts, INK, 0.86 * a)
        cv.poly(pts, m(col, a), 3, glow=0.9 * a, closed=True)
        cv.text(540, y, txt, 'b', sz, WH, a, 'mm', glow=0.25)

# ---- deck: strip, feed, profit, tiles (bigger type)
def draw_strip18(cv, t, a):
    for i in range(8):
        x0 = 40 + i * 113; x1 = x0 + 107; y0, y1 = 1022, 1112
        lv = lvl(i, t); col = MCOL[i]
        foc = 1.0 if t >= MONT1 else (0.55 + 0.45 * clamp(lv * 2.0))
        aa = a * foc
        pts = chamfer(x0, y0, x1, y1, 10)
        cv.fillpoly(pts, mix(PANEL, col, 0.10 + 0.45 * lv), 0.92 * aa)
        cv.poly(pts, m(mix(CYD, col, lv), aa), 2 + int(lv > 0.5), glow=0.9 * lv * aa, closed=True)
        cv.text((x0 + x1) / 2, y0 + 20, NAMES[i], 'b', 22, mix(DIM, col, 0.55 + 0.45 * lv), aa, 'mm')
        txt, fr = sig_val(i, t)
        cv.text((x0 + x1) / 2, y0 + 53, txt, 'mono', fit(txt, 'mono', 30, 98), WH, aa, 'mm', glow=0.3 * lv)
        cv.rect(x0 + 10, y1 - 15, x1 - 10, y1 - 9, mix(PANEL, CYD, 0.5), aa)
        cv.rect(x0 + 10, y1 - 15, x0 + 10 + (x1 - x0 - 20) * clamp(fr), y1 - 9, col, aa)

def feed_card(cv, a, k, y0, h, hi):
    if h < 10 or a <= 0.02: return
    tr = TR[k - 1]; col = GR if tr['win'] else RD
    x0 = 60
    pts = chamfer(x0, y0, x0 + 880, y0 + h, 12)
    cv.fillpoly(pts, mix(PANEL, col, 0.22 if hi else 0.12), 0.92 * a)
    cv.poly(pts, m(col, a), 3 if hi else 2, glow=(0.9 if hi else 0.2) * a, closed=True)
    pnl = tr['pnl']; tag = "WIN" if tr['win'] else "LOSS"
    if h >= 80:
        cv.text(x0 + 22, y0 + 30, f"#{k}  ${tr['token']}", 'b', 32, WH, a, 'lm')
        t2 = f"{solf(tr['before'])} SOL  →  {solf(tr['after'])} SOL"
        cv.text(x0 + 22, y0 + 72, t2, 'mono', fit(t2, 'mono', 28, 500), mix(WH, DIM, 0.3), a, 'lm')
        cv.text(x0 + 858, y0 + 34, usd(pnl, True), 'mono', 46, col, a, 'rm', glow=0.8)
        cv.text(x0 + 858, y0 + 74, f"{tag}  {tr['ret'] * 100:+.1f}%", 'b', 28, col, a, 'rm')
    else:
        txt = f"#{k} ${tr['token']}   {usd(pnl, True)}"
        cv.text(x0 + 20, y0 + h / 2, txt, 'mono', fit(txt, 'mono', 26, 560), mix(WH, col, 0.5), a, 'lm')
        cv.text(x0 + 860, y0 + h / 2, f"{tag} {tr['ret'] * 100:+.1f}%", 'b', 26, col, a, 'rm')

def draw_feed18(cv, a, t):
    if t >= 22.3: return draw_feed(cv, a, t)
    a = a * (1 - _card_a(t))
    pts = chamfer(60, 1124, 940, 1306, 16)
    cv.poly(pts, m(CYD, 0.6 * a), 2, closed=True)
    cv.text(84, 1148, "SIGNAL FEED", 'b', 24, DIM, a * 0.9, 'lm')
    kd = bisect.bisect_right(_SIGT, t)
    cv.text(916, 1148, f"{kd} signals", 'md', 22, DIM, a * 0.8, 'rm')
    for j in range(3):
        k = kd - 1 - j
        if k < 0: break
        te, ii, txt = SIGE[k]
        u = easeout(ramp(t, te, te + 0.18)) if j == 0 else 1.0
        al = a * u * (1.0, 0.72, 0.45)[j]
        y = 1192 + 44 * j + (1 - u) * 14
        col = MCOL[ii]
        cv.fillpoly(chamfer(80, y - 17, 186, y + 17, 7), mix(PANEL, col, 0.45), 0.95 * al)
        cv.text(133, y, NAMES[ii], 'b', 22, WH, al, 'mm')
        cv.text(204, y, txt, 'md', fit(txt, 'md', 30, 716), WH, al, 'lm', glow=0.15 if j == 0 else 0.0)

def draw_profit18(cv, t, a, pulse_):
    if a <= 0.02: return
    kd, live, xend = profit_state(t)
    pts = chamfer(40, 1318, 960, 1584, 18)
    gold = t >= MONT1 + 0.2
    col = GOLD if gold else (GR if live >= 0 else RD)
    cv.fillpoly(pts, mix(PANEL, col, 0.10), 0.9 * a)
    cv.poly(pts, m(col, a), 2, glow=(0.4 + 0.5 * pulse_) * a, closed=True)
    cv.text(70, 1350, "LIVE PROFIT", 'b', 32, WH, a, 'lm')
    has = kd or t >= TB
    cv.text(70, 1388, f"≈ {solf(live, True)} SOL" if has else "waiting for trade", 'mono' if has else 'md', 26, DIM, a, 'lm')
    sz = int((140 if gold else 124) * (1 + 0.06 * pulse_))
    cv.text(930, 1394, usd(live, True), 'mono', fit(usd(live, True), 'mono', sz, 540), col, a, 'rm', glow=(1.0 if gold else 0.8))
    x0, x1, y0, y1 = 70, 930, 1462, 1524
    xmax = max(1.0, xend)
    vals = CUM[:kd + 1] + [live]
    ymax = max(100.0, max(vals)) * 1.18
    ymin = min(0.0, min(vals)) * 1.3
    X = lambda x: x0 + x / xmax * (x1 - x0)
    Y = lambda v: y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
    cv.poly([(x0, Y(0.0)), (x1, Y(0.0))], m(CYD, a * 0.6), 1)
    px = [(X(0), Y(0.0))] + [(X(j), Y(CUM[j])) for j in range(1, kd + 1)]
    if kd < NT and (xend > kd + 1e-6 or kd == 0):
        px.append((X(xend), Y(live)))
    if len(px) >= 2:
        area = [(px[0][0], Y(0.0))] + px + [(px[-1][0], Y(0.0))]
        cv.fillpoly(area, GR, 0.12 * a)
        for j in range(1, len(px)):
            up = px[j][1] <= px[j - 1][1]
            newest = j == len(px) - 1
            cv.poly([px[j - 1], px[j]], m(GOLD if gold and newest else (GR if up else RD), a), 5 if newest else 3, glow=(1.0 if newest else 0.25) * a)
        cv.circle(px[-1], 8, m(GOLD if gold else WH, a), -1, glow=1.0 * a)
    scanned, done, wins, losses, bal = counters12(t)
    y = 1556
    cv.text(70, y, "TRADES", 'b', 22, DIM, a, 'lm')
    cv.text(162, y, f"{done}/{NT}", 'mono', 30, WH, a, 'lm')
    cv.text(330, y, "W/L", 'b', 22, DIM, a, 'lm')
    cv.text(384, y, f"{wins}", 'mono', 30, GR, a, 'lm')
    wd = F('mono', 30).getlength(f"{wins}")
    cv.text(388 + wd, y, f"/{losses}", 'mono', 30, RD, a, 'lm')
    cv.text(600, y, "BALANCE", 'b', 22, DIM, a, 'lm')
    cv.text(930, y, usd(bal), 'mono', 30, CY, a, 'rm', glow=0.3)

def draw_tiles18(cv, t, a, vals):
    scanned, done, wins, losses, bal = vals
    tiles = [("TOKENS SCANNED", f"{scanned:,}", WH), ("TRADES", f"{done}/{NT}", WH), ("WINS / LOSSES", None, None), ("BALANCE", usd(bal), CY)]
    for i, (lab, val, col) in enumerate(tiles):
        x0 = 40 + i * 252; x1 = x0 + 242; y0, y1 = 1674, 1774
        pts = chamfer(x0, y0, x1, y1, 14)
        cv.fillpoly(pts, PANEL, 0.85 * a)
        cv.poly(pts, m(CYD, a), 2, closed=True)
        cv.text(x0 + 16, y0 + 24, lab, 'b', 22, DIM, a, 'lm')
        if val is not None:
            cv.text(x0 + 16, y0 + 64, val, 'mono', fit(val, 'mono', 46, 214), col, a, 'lm', glow=0.35 if i == 3 else 0.0)
        else:
            cv.text(x0 + 16, y0 + 64, f"{wins}", 'mono', 46, GR, a, 'lm', glow=0.35)
            wd = F('mono', 46).getlength(f"{wins}")
            cv.text(x0 + 16 + wd + 8, y0 + 64, "/", 'mono', 40, DIM, a, 'lm')
            cv.text(x0 + 16 + wd + 36, y0 + 64, f"{losses}", 'mono', 46, RD, a, 'lm', glow=0.35)

# ---- hook + outro
def draw_hook18(cv, t):
    a1 = 1 - ramp(t, 1.45, 1.65)
    if a1 > 0:
        pop = 1.0
        cv.text(540, 720, "8 AI", 'b', int(190 * (0.8 + 0.2 * pop)), WH, a1, 'mm', glow=0.6)
        cv.text(540, 850, f"SCAN {SCANNED:,} TOKENS", 'b', 64, CY, a1, 'mm', glow=0.5)
    a2 = ramp(t, 1.6, 1.8) * (1 - ramp(t, 2.8, 3.1))
    if a2 > 0:
        pop = easeout(ramp(t, 1.6, 2.0))
        LG.put(cv, LG.emblem(), 540, 640, int(190 * (0.85 + 0.15 * pop)), a2, 0.7, shine=clamp((t - 1.7) / 1.2))
        LG.put(cv, LG.wordmark(120, OC.NAME), 540, 800, 540, a2, 0.6)
        cv.text(540, 872, "8 AI SCAN THE SIGNALS  ·  SOLANA", 'md', 30, CY, a2, 'mm', glow=0.3)
        cv.text(540, 930, f"{SCANNED:,} NEW TOKENS  →  {OC.SHORT} PASS THE FILTER", 'b', 38, GOLD, a2 * ramp(t, 1.8, 2.1), 'mm', glow=0.5)

def draw_outro18(cv, t):
    a = ramp(t, 42.5, 42.9) * (1 - ramp(t, 44.0, 44.6))
    if a <= 0: return
    pop = easeout(ramp(t, 42.5, 43.0))
    LG.put(cv, LG.emblem(), 540, 660, int(240 * (0.85 + 0.15 * pop)), a, 0.8, shine=clamp((t - 42.6) / 1.2))
    LG.put(cv, LG.wordmark(120, OC.NAME), 540, 860, 600, a * ramp(t, 42.6, 42.9), 0.7)
    cv.text(540, 940, "8 AI SCAN THE SIGNALS", 'b', 36, CY, a * ramp(t, 42.8, 43.1), 'mm', glow=0.4)

def camera18(img, t):
    s_ = 1.0; dx = dy = 0.0; cx, cy = 540.0, 960.0
    if t < 2.6:
        s_ += 0.07 * (1 - easeout(t / 2.6)); cx, cy = 540.0, 300.0
    z = smooth(ramp(t, 24.0, 25.4)) * (1 - smooth(ramp(t, 28.6, 30.0)))
    if z > 0: s_ += 0.07 * z; cx, cy = 540.0, 640.0
    if 30.0 <= t < 38.4: dx += 6.0 * math.sin((t - 30.0) * 0.9)
    for j, e in enumerate(EV):
        d = t - e
        if 0 <= d < 0.5:
            amp = 0.045 if j in FEAT else 0.012
            if j == NT - 1: amp = 0.0
            s_ += amp * math.exp(-d / 0.12)
            sh = (7.0 if j in FEAT else 3.0) * math.exp(-d / 0.10) * math.sin(d * 70)
            if TR[j]['win']: dx += sh
            else: dy += sh
    d = t - MONT1
    if 0 <= d < 1.0: s_ += 0.05 * math.exp(-d / 0.3)
    if 42.5 <= t: s_ += 0.03 * smooth(ramp(t, 42.5, 44.8)); cx, cy = 540.0, 700.0
    if s_ == 1.0 and dx == 0.0 and dy == 0.0: return img
    M = np.float32([[s_, 0, cx * (1 - s_) + dx], [0, s_, cy * (1 - s_) + dy]])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)

_TAGC = tuple(int(v) for v in mix(DIM, WH, 0.45))
def post_tag(img, t):
    a = ramp(t, 0.0, 0.4) * (1 - 0.0)
    if a <= 0.02: return img
    pi = Image.fromarray(img); d = ImageDraw.Draw(pi)
    c = tuple(int(v * a) for v in _TAGC)
    f = F('md', 24)
    d.text((40, 140), "Illustrative figures", font=f, fill=c, anchor='lm')
    d.text((40, 170), "Not financial advice", font=f, fill=c, anchor='lm')
    return np.array(pi)

_F0 = []
def _first_frame():
    if not _F0: _F0.append(render18(0.0))
    return _F0[0]

def render18(t):
    cv = Cv(BG)
    core.particles(cv, t)
    aUI = ramp(t, 1.4, 2.4)
    L = agent_levels12(t)
    draw_hook18(cv, t)
    if 3.0 <= t < 9.9:
        c10.draw_funnel(cv, ramp(t, 3.0, 3.4) * (1 - ramp(t, 9.3, 9.6)), t + 0.8)
    if 9.5 <= t < 11.5:
        c10.draw_scan10(cv, ramp(t, 9.5, 9.75) * (1 - ramp(t, 11.0, 11.3)), t + 0.4)
    if 11.1 <= t < 22.7:
        draw_trade12(cv, ramp(t, 11.1, 11.4) * (1 - ramp(t, 22.15, 22.4)), t)
    if 22.2 <= t < 38.7:
        draw_mont12(cv, ramp(t, 22.2, 22.5) * (1 - ramp(t, 38.1, 38.4)), t)
    if t >= 38.1:
        c10.draw_results(cv, ramp(t, 38.1, 38.5) * (1 - ramp(t, 42.1, 42.5)), t)
    draw_outro18(cv, t)
    pulse_ = max(0.0, math.sin(clamp((t - MONT1) / 1.2) * math.pi)) if t >= MONT1 else 0.0
    if aUI > 0:
        sh = Shift(cv, DYS)
        draw_strip18(sh, t, aUI * wt('strip', t))
        draw_feed18(sh, aUI * wt('feed', t), t)
        draw_profit18(sh, t, aUI * wt('profit', t), pulse_)
    ca = ramp(t, TB + 0.1, TB + 0.3) * (1 - ramp(t, TB + 1.4, TB + 1.6))
    sh = Shift(cv, DYS)
    if ca > 0.02: card_buy12(sh, ca)
    ca = ramp(t, TS + 0.1, TS + 0.3) * (1 - ramp(t, TS + 1.4, TS + 1.6))
    if ca > 0.02: card_sell12(sh, ca)
    ca = ramp(t, 20.0, 20.2) * (1 - ramp(t, 20.6, 20.8))
    if ca > 0.02: card_check12(sh, ca)
    ca = ramp(t, 20.8, 21.0) * (1 - ramp(t, 22.1, 22.3))
    if ca > 0.02: card_pnl12(sh, ca, easeout(ramp(t, 20.8, 21.8)))
    fx_buy(cv, t, TB)
    fx_sell(cv, t, TS, TR[0]['win'], 1)
    for k in range(2, NT + 1):
        e = EV[k - 1]
        if e - 0.3 <= t < e + 0.7:
            fx_buy(cv, t, e - 0.2)
            fx_sell(cv, t, e, TR[k - 1]['win'], k)
    lashd = {}
    for (to, ii) in ORD:
        d = t - to
        if 0 <= d < 0.35 and t < MONT0:
            dk = DOCK[ii]; u = easeout(d / 0.3)
            cv.poly([MOUTH, (MOUTH[0] + (dk[0] - MOUTH[0]) * u, MOUTH[1] + (dk[1] - 24 - MOUTH[1]) * u)], m(CY, 1 - d / 0.35), 4, glow=1.0 * (1 - d / 0.35))
            if d > 0.2:
                cv.ellipse((dk[0], dk[1]), (int(20 + 50 * (d - 0.2) / 0.15), int(14 + 34 * (d - 0.2) / 0.15)), m(CY, 1 - (d - 0.2) / 0.15), 2, glow=0.8)
        if 0 <= d < 0.5 and t < MONT0:
            kk = 0 if DOCK[ii][0] >= 540 else 4
            lashd[kk] = max(lashd.get(kk, 0.0), math.sin(math.pi * d / 0.5))
    # hook: 8 signals fire into the mother
    for i in range(8):
        ta = 0.45 + 0.05 * i; d = t - (ta + 0.35)
        if 0 <= d < 0.45:
            px_, py_ = mini_pos(i, t); u = easeout(d / 0.3)
            ex_ = px_ + (MOUTH[0] - px_) * u; ey_ = py_ + (MOUTH[1] - py_) * u
            cv.poly([(px_, py_ - 10), (ex_, ey_)], m(MCOL[i], 1 - d / 0.45), 3, glow=1.0 * (1 - d / 0.45))
            cv.circle((ex_, ey_), 7, m(WH, 1 - d / 0.45), -1, glow=1.0)
    da = aUI if aUI > 0 else ramp(t, 0.5, 1.0)
    cv.poly([(120, 470), (960, 470)], m(CYD, 0.7 * da), 2, glow=0.3 * da)
    for i in range(8):
        d = DOCK[i]
        cv.poly([(d[0] - 34, 470), (d[0] - 24, 462), (d[0] + 24, 462), (d[0] + 34, 470)], m(MCOL[i], 0.75 * da), 3, glow=0.5 * da * (0.3 + lvl(i, t)))
    draw_packets(cv, t)
    for i in range(8): draw_mini(cv, i, t)
    _sa = ramp(t, 2.6, 3.2)
    LG.put(cv, LG.emblem(), 72, 90, 62, _sa, 0.3)
    cv.text(116, 90, OC.NAME, 'b', 40, WH, _sa, 'lm', glow=0.4)
    ta_ = ramp(t, 2.6, 3.2)
    od = cur_order(t)
    if t >= MONT1:
        cv.text(960, 92, "MISSION", 'md', 24, DIM, ta_ * (1 - ramp(t, 42.3, 42.6)), 'rm')
        cv.text(960, 142, "COMPLETE", 'b', 44, GOLD, ta_ * (1 - ramp(t, 42.3, 42.6)), 'rm', glow=0.8)
        cv.text(960, 188, f"{NT} trades closed", 'md', 24, DIM, ta_ * (1 - ramp(t, 42.3, 42.6)), 'rm')
    elif od is not None:
        oc = MCOL[od[1]]
        fl = 1.0 if t - od[0] > 0.2 else 0.5 + 2.5 * (t - od[0])
        cv.text(960, 92, "ORDER", 'md', 24, DIM, ta_, 'rm')
        cv.text(960, 142, NAMES[od[1]], 'b', 46, oc, ta_ * min(1.0, fl), 'rm', glow=0.8)
        cv.text(960, 188, f"{ROLE[od[1]]}", 'md', 24, DIM, ta_, 'rm')
    # mother: target, mood, roar, reveal
    best = max(range(8), key=lambda i: lvl(i, t))
    tgt = None; lean = (0.0, 0.0); ecol = CY
    if lvl(best, t) > 0.3 and t < MONT1:
        px_, py_ = mini_pos(best, t)
        tgt = (px_, py_)
        lean = (clamp((px_ - MX) / 540.0, -1, 1) * 8, clamp((py_ - 400) / 1200.0, 0, 1) * 6)
        ecol = mix(CY, MCOL[best], 0.7 * lvl(best, t))
    roar = 0.0; under = None; squash = 1.0; flare = 0.0
    for j, e in enumerate(EV):
        d = t - e
        if 0 <= d < 0.6:
            w_ = TR[j]['win']
            if w_:
                ecol = mix(ecol, GR, 0.6 * (1 - d / 0.6))
                if j in FEAT or j == 0:
                    roar = max(roar, math.sin(math.pi * clamp(d / 0.6)) * 1.0); ecol = mix(ecol, GOLD, 0.8 * (1 - d / 0.6)); flare = max(flare, 1 - d / 0.6)
            else:
                k_ = math.exp(-d / 0.18)
                ecol = mix(ecol, RD, 0.7 * (1 - d / 0.6)); under = (0.9 * k_, 0.08 * k_, 0.15 * k_); squash = 1 - 0.03 * k_
                lean = (lean[0] + 4 * k_ * math.sin(d * 60), lean[1])
    d = t - TB
    if 0 <= d < 0.6: roar = max(roar, 0.6 * math.sin(math.pi * d / 0.6)); flare = max(flare, 0.7 * (1 - d / 0.6))
    if t >= MONT1:
        ecol = mix(CY, GOLD, ramp(t, MONT1, MONT1 + 0.3))
        d = t - MONT1
        if d < 0.8: roar = max(roar, math.sin(math.pi * d / 0.8)); flare = max(flare, 1 - d / 0.8)
    eyes = 1.0
    reveal = smooth(ramp(t, 0.35, 1.4))
    if t < 0.9: flare = max(flare, 1 - ramp(t, 0.5, 0.9))
    act = clamp(sum(L) / 4.0)
    open_ = 1.0
    draw_head18(cv, t, tgt, ecol, open_, lean, act, roar=roar, reveal=reveal, eyes=eyes, lash=lashd, under=under, squash=squash, flare=flare)
    if roar > 0.3:
        cv.ellipse((MX, MOUTH[1]), (int(80 + 520 * roar), int(30 + 160 * roar)), m(mix(CY, GOLD, 0.5), 0.5 * roar), 3, glow=0.8 * roar)
    if MONT1 <= t < MONT1 + 1.5:
        u = ramp(t, MONT1, MONT1 + 1.5)
        cv.flash = (1 - ramp(t, MONT1, MONT1 + 0.5)) * 0.9
        for k in range(28):
            ang = k * 2 * math.pi / 28 + 0.1
            r0 = 140 + 700 * easeout(u); r1 = r0 + 60 + 120 * (1 - u)
            cv.poly([(MX + r0 * math.cos(ang), MY + 30 + r0 * math.sin(ang) * 0.9), (MX + r1 * math.cos(ang), MY + 30 + r1 * math.sin(ang) * 0.9)],
                    m(CY if k % 2 else PU, (1 - u) * 0.9), 3, glow=1.0 * (1 - u))
    if abs(t - TS) < 0.12: cv.flash = max(cv.flash, 0.2)
    for j in FEAT:
        d = t - EV[j]
        if 0 <= d < 1.0:
            al = ramp(d, 0.0, 0.12) * (1 - ramp(d, 0.7, 1.0))
            col = GR if TR[j]['win'] else RD
            cv.rect(PX0 + 10, 650, PX1 - 10, 850, INK, 0.62 * al)
            cv.text(540, 722 - 26 * d, usd(TR[j]['pnl'], True), 'mono', 112, col, al, 'mm', glow=1.0)
            cv.text(540, 818, f"TRADE #{j + 1}  ·  ${TR[j]['token']}  ·  {TR[j]['ret'] * 100:+.1f}%", 'b', 30, WH, al, 'mm')
    draw_caps(cv, t)
    img = camera18(cv.finish(), t)
    k = smooth(ramp(t, 43.6, 44.78))
    if k > 0:
        base = _first_frame()
        img = (img.astype(np.float32) * (1 - k) + base.astype(np.float32) * k).astype(np.uint8)
    return post_tag(img, t) if t < 43.9 else img

# ---- 30 s cut: piecewise time warp (output -> engine), knots on the 150 BPM beat grid
OUTK = [0.0, 1.2, 2.4, 6.0, 14.4, 25.2, 27.6, 30.0]
ENGK = [0.0, 1.6, 3.2, 9.6, 22.4, 38.4, 42.5, 44.8]
TOTAL_OUT = 30.0
def warp(t): return float(np.interp(t, OUTK, ENGK))
def render19(t): return render18(warp(t))

def write_scene(name, t0, t1):
    n = int(round((t1 - t0) * FPS))
    tmp = f"{OUT}/s19_{name}.tmp.mp4"
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(FPS), tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(render19(t0 + f / FPS).tobytes())
    p.stdin.close()
    rc = p.wait()
    if rc == 0:
        os.rename(tmp, f"{OUT}/s19_{name}.mp4")
        print('done', name, n, 'frames')
    else:
        print('ffmpeg failed', rc); sys.exit(1)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'still':
        for ts in sys.argv[2:]:
            Image.fromarray(render19(float(ts))).save(f"{OUT}/v19_{ts}.png")
            print('saved', ts)
    elif mode == 'scene':
        write_scene(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))

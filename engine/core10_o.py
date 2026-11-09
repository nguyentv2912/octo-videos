import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
import sys, math, os, subprocess
sys.path.insert(0, _BASE)
import numpy as np, cv2
from PIL import Image
import core_o as core
from core_o import (W, H, FPS, OUT, CY, CYD, PU, PUD, MG, GR, RD, WH, DIM, GOLD, PANEL, INK, m, mix, clamp, smooth,
                  easeout, ramp, F, fit, Cv, BG, chamfer, bez, TR, TOKENS, AGN, AG_MAP, ext, check_icon,
                  arrow_marker, candle, agent_icon, T1O, T1H, T1L, T1C, T1MIN, T1MAX, R1, ENTRY, EXIT1,
                  MCL, MHI_N, MLO_N)

TOTAL = 45.0
SOLP = 150.0
import octocfg as OC
SCANNED = OC.SCANNED
STEP0 = 10.0; STEPD = 2.0
MONT0 = 26.0; MONT1 = 38.0
DT = (MONT1 - MONT0) / 29
TB = 16.5; TS = 20.4
EV = [TS] + [MONT0 + (k - 1) * DT for k in range(2, 31)]
NAMES = ["SCAN", "CHART", "WALLET", "BUY", "TRACK", "SELL", "CHECK", "PNL"]
STEPCOL = [CY, CY, PU, GR, PU, MG, CY, GR]
CUM = [0.0] + [tr['after'] - OC.START for tr in TR]

PX0, PX1, PY0, PY1 = 150, 930, 668, 1140
HX, HY = 540, 360

def usd(v, sign=False):
    s = f"${abs(v):,.0f}"
    return (("+" if v >= 0 else "-") + s) if sign else s
def solf(v, sign=False):
    s = v / SOLP
    txt = f"{abs(s):,.3f}" if abs(s) < 10 else f"{abs(s):,.2f}"
    return (("+" if s >= 0 else "-") + txt) if sign else txt
def moneyk(v):
    a = abs(v); sg = '-' if v < 0 else ''
    if a >= 10000: return f"{sg}${a / 1000:.0f}K"
    if a >= 1000: return f"{sg}${a / 1000:.1f}K"
    return f"{sg}${a:.0f}"

# ------------------------------------------------------------------ timeline
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
            down = 1 - smooth(ramp(t, 42.6 + 0.05 * i, 43.6 + 0.05 * i))
            e[i] = max(e[i] if t < MONT1 + 0.2 else 0.0, up * down)
    return e

def agent_levels(t, e):
    L = [0.0] * 6
    for i in range(6):
        ta = 1.6 + 0.45 * i
        base = 0.35 if t >= ta + 0.4 else 0.0
        act = math.sin(math.pi * clamp((t - ta) / 0.9)) ** 0.6 if ta <= t < ta + 0.9 else 0.0
        L[i] = max(base, act)
    if 4.0 <= t < 10.0:
        L[0] = max(L[0], 0.85 + 0.15 * math.sin(t * 6))
        L[1] = max(L[1], 0.3 + 0.7 * smooth(ramp(t, 5.5, 6.5)))
    for s in range(8):
        for a in AG_MAP[s]:
            L[a] = max(L[a], 0.35 + 0.65 * e[s])
    if t >= MONT1:
        for i in range(6):
            L[i] = max(L[i], 0.72 + 0.28 * math.sin(t * 4 + i))
    return L

def counters10(t):
    scanned = int(round(SCANNED * smooth(ramp(t, 4.6, 7.6))))
    done = sum(1 for ev in EV if t >= ev)
    wins = sum(1 for k in range(done) if TR[k]['win'])
    losses = done - wins
    prev = 1000.0 if done == 0 else TR[done - 1]['after']
    bal = prev
    if done < 30:
        u = easeout(ramp(t, EV[done] - 0.25, EV[done]))
        bal = prev + (TR[done]['after'] - prev) * u
    return scanned, done, wins, losses, bal

def nrev_t1(t):
    return float(np.interp(t, [12, 14, 16, 16.5, 18, 20, 22, 26], [0, 14, 14, 15, 15, 35, 35, 48]))

def profit_state(t):
    kd = sum(1 for ev in EV if t >= ev)
    live = CUM[kd]; xend = float(kd)
    if kd == 0:
        if t >= 18.0:
            nr = nrev_t1(t)
            i = min(int(nr - 1e-6), 47)
            live = 1000.0 * (T1C[i] - 1.0)
            xend = clamp((nr - 15) / 20.0)
        else:
            live = 0.0; xend = 0.0
    elif kd < 30:
        u = easeout(ramp(t, EV[kd] - 0.25, EV[kd]))
        live = CUM[kd] + (CUM[kd + 1] - CUM[kd]) * u
        xend = kd + u
    return kd, live, xend

# ------------------------------------------------------------------ Apex head
def build_head10():
    S = 2; w, h = 600, 420; ox, oy = 300, 275
    Hs, Ws = h * S, w * S
    P = lambda x, y: (int((x + ox) * S), int((y + oy) * S))
    PA = lambda pts: np.array([P(x, y) for x, y in pts], np.int32)
    sil = [(-230, 60), (-218, -20), (-185, -98), (-125, -152), (-80, -176), (-62, -222), (-30, -196), (0, -262),
           (30, -196), (62, -222), (80, -176), (125, -152), (185, -98), (218, -20), (230, 60), (190, 102),
           (120, 122), (0, 132), (-120, 122), (-190, 102)]
    pauL = [(-215, -5), (-292, -18), (-258, 30), (-290, 86), (-208, 80)]
    pauR = [(-x, y) for x, y in pauL]
    yy, xx = np.mgrid[0:Hs, 0:Ws].astype(np.float32)
    X = xx / S - ox; Y = yy / S - oy
    yn = np.clip((Y + 262) / 400, 0, 1)[..., None]
    img = np.array([46, 60, 108], np.float32) * (1 - yn) + np.array([8, 12, 30], np.float32) * yn
    img += np.array([120, 160, 230], np.float32) * (0.50 * np.exp(-(((X + 90) / 95) ** 2 + ((Y + 135) / 55) ** 2)))[..., None]
    img += np.array(CY, np.float32) * (0.30 * np.exp(-(((X + 215) / 40) ** 2 + ((Y - 0) / 120) ** 2)))[..., None]
    img += np.array(PU, np.float32) * (0.38 * np.exp(-(((X - 215) / 40) ** 2 + ((Y - 0) / 120) ** 2)))[..., None]
    img = np.ascontiguousarray(np.clip(img, 0, 255).astype(np.uint8))
    mask = np.zeros((Hs, Ws), np.uint8)
    cv2.fillPoly(mask, [PA(sil)], 255, cv2.LINE_AA)
    cv2.fillPoly(mask, [PA(pauL)], 255, cv2.LINE_AA)
    cv2.fillPoly(mask, [PA(pauR)], 255, cv2.LINE_AA)
    DK = (5, 8, 24); LC = (30, 200, 230); LD = (10, 70, 96); ST = (36, 48, 92)
    def seam(pts, th=1):
        p = PA(pts)
        cv2.polylines(img, [p], False, DK, (th + 3) * S, cv2.LINE_AA)
        cv2.polylines(img, [p], False, LD, (th + 1) * S, cv2.LINE_AA)
        cv2.polylines(img, [p], False, LC, th * S, cv2.LINE_AA)
    for sx in (-1, 1):
        pau = pauL if sx < 0 else pauR
        cv2.fillPoly(img, [PA(pau)], (14, 20, 44), cv2.LINE_AA)
        cv2.polylines(img, [PA(pau)], True, LC, 2 * S, cv2.LINE_AA)
        seam([(sx * 214, 4), (sx * 262, 20)]); seam([(sx * 212, 36), (sx * 254, 52)])
    cv2.line(img, P(0, -262), P(0, -134), DK, 4 * S, cv2.LINE_AA)
    cv2.line(img, P(0, -262), P(0, -134), LC, 1 * S, cv2.LINE_AA)
    for (ax, ay, a0, a1) in [(176, 150, 212, 328), (118, 98, 218, 322)]:
        cv2.ellipse(img, P(0, -6), (ax * S, ay * S), 0, a0, a1, DK, 4 * S, cv2.LINE_AA)
        cv2.ellipse(img, P(0, -6), (ax * S, ay * S), 0, a0, a1, LC, 1 * S, cv2.LINE_AA)
    for sx in (-1, 1):
        seam([(sx * 206, -14), (sx * 150, -112)]); seam([(sx * 190, 40), (sx * 140, -44)])
        seam([(sx * 120, -150), (sx * 78, -108)])
        for (rx, ry) in [(sx * 168, -70), (sx * 196, -6), (sx * 150, 8)]:
            cv2.circle(img, P(rx, ry), 4 * S, (14, 20, 46), -1, cv2.LINE_AA)
            cv2.circle(img, P(rx - 1, ry - 1), 1 * S + 1, (130, 170, 230), -1, cv2.LINE_AA)
    vis = [(-200, -22), (200, -22), (216, 30), (160, 66), (-160, 66), (-216, 30)]
    cv2.fillPoly(img, [PA(vis)], (3, 5, 16), cv2.LINE_AA)
    cv2.polylines(img, [PA(vis)], True, DK, 5 * S, cv2.LINE_AA)
    cv2.polylines(img, [PA(vis)], True, LC, 2 * S, cv2.LINE_AA)
    for sx in (-1, 1):
        brow = [(sx * 196, -38), (sx * 14, -4), (sx * 14, 12), (sx * 196, -16)]
        cv2.fillPoly(img, [PA(brow)], (18, 26, 56), cv2.LINE_AA)
        cv2.polylines(img, [PA(brow)], True, LC, 2 * S, cv2.LINE_AA)
    beak = [(-34, 66), (34, 66), (24, 106), (0, 136), (-24, 106)]
    cv2.fillPoly(img, [PA(beak)], (12, 18, 40), cv2.LINE_AA)
    cv2.polylines(img, [PA(beak)], True, LC, 2 * S, cv2.LINE_AA)
    cv2.line(img, P(0, 70), P(0, 130), LC, 1 * S, cv2.LINE_AA)
    for sx in (-1, 1):
        mand = [(sx * 34, 70), (sx * 92, 96), (sx * 56, 124), (sx * 26, 102)]
        cv2.fillPoly(img, [PA(mand)], (12, 18, 40), cv2.LINE_AA)
        cv2.polylines(img, [PA(mand)], True, LC, 2 * S, cv2.LINE_AA)
    cv2.polylines(img, [PA(sil)], True, DK, 6 * S, cv2.LINE_AA)
    cv2.polylines(img, [PA(sil)], True, CYD, 3 * S, cv2.LINE_AA)
    inner = [(x * 0.95, y * 0.95) for x, y in sil]
    cv2.polylines(img, [PA(inner)], True, PUD, 2 * S, cv2.LINE_AA)
    spr = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
    al = cv2.resize(mask, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
    return spr, al, ox, oy
HSPR, HAL, HOX, HOY = build_head10()

EYE_L = [(-142, 10), (-44, 24), (-58, 46), (-132, 40)]
LEDP = [(-150, -100), (-112, -126), (-72, -146), (72, -146), (112, -126), (150, -100)]

def draw_head10(cv, t, gain, eye_target, eye_col, scan, L, open_):
    x0 = HX - HOX; y0 = HY - HOY
    roi = cv.f[y0:y0 + HSPR.shape[0], x0:x0 + HSPR.shape[1]]
    al = HAL[..., None]
    roi[:] = (roi * (1 - al) + HSPR.astype(np.float32) * gain * al).astype(np.uint8)
    if gain < 0.3: return
    for i in range(6):
        x, y = LEDP[i]
        cv.circle((HX + x, HY + y), 7, m(AGN[i][1], 0.15 + 0.85 * L[i]), -1, glow=0.9 * L[i])
    pulse = 0.65 + 0.35 * math.sin(t * 3.2)
    cx, cy = HX, HY - 96
    hexp = [(cx + 36 * math.cos(math.radians(-90 + 60 * k)), cy + 36 * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    cv.fillpoly(hexp, (18, 8, 50), 1.0)
    cv.poly(hexp, m(PU, gain), 3, glow=0.9 * pulse, closed=True)
    hex2 = [(cx + 26 * math.cos(math.radians(-90 + 60 * k)), cy + 26 * math.sin(math.radians(-90 + 60 * k))) for k in range(6)]
    cv.poly(hex2, m(CY, 0.8 * gain), 2, glow=0.5, closed=True)
    cv.text(cx, cy + 1, "6", 'mono', 38, WH, gain, 'mm', glow=0.6)
    if open_ > 0.02:
        for sx in (-1, 1):
            pts = [(HX + sx * x, HY + 28 + (y - 28) * open_) for x, y in EYE_L]
            br = (0.78 + 0.22 * math.sin(t * 2.4 + sx)) * open_
            cv.fillpoly(pts, eye_col, min(1.0, br * gain))
            cv.poly(pts, m(WH, 0.6 * open_ * gain), 2, glow=0.9 * open_, closed=True)
            cv.g[:] = cv.g
            ctr = (sum(p[0] for p in pts) / 4, sum(p[1] for p in pts) / 4)
            off = (0.0, 0.0)
            if eye_target is not None:
                dx = eye_target[0] - ctr[0]; dy = eye_target[1] - ctr[1]
                n = math.hypot(dx, dy) + 1e-6
                off = (dx / n * 9, dy / n * 3)
            cv.ellipse((ctr[0] + off[0], ctr[1] + off[1]), (5, max(2, int(14 * open_))), INK, -1)
    if scan is not None:
        x = HX - 190 + 380 * scan
        cv.poly([(x, HY - 14), (x, HY + 60)], m(CY, 0.9 * gain), 3, glow=1.0)

# ------------------------------------------------------------------ tentacles
BASES10 = [np.array(p, np.float64) for p in
           [(360, 472), (405, 480), (450, 486), (495, 490), (720, 472), (675, 480), (630, 486), (585, 490)]]
SX = [-1, -1, -1, -1, 1, 1, 1, 1]
RESTS10 = [np.array(p, np.float64) for p in
           [(175, 626), (262, 640), (352, 648), (442, 650), (905, 626), (818, 640), (728, 648), (638, 650)]]
NODES10 = [(76, 735), (76, 845), (76, 955), (76, 1065), (1004, 735), (1004, 845), (1004, 955), (1004, 1065)]
TIPS10 = [np.array((NODES10[i][0] - SX[i] * 28.0, float(NODES10[i][1]))) for i in range(8)]

def draw_tentacle10(cv, i, e, t, grow, gain):
    base = BASES10[i]; sx = SX[i]; rest = RESTS10[i]; tgt = TIPS10[i]
    tip = rest + (tgt - rest) * e
    P1 = base + np.array([sx * (40 + 300 * e), 135.0 - 25 * e])
    P2 = tip + np.array([-sx * 8 * e, -64 * (1 - e) - 110 * e])
    N = 40
    sn = np.linspace(0, 1, N); s = sn * grow
    pts = bez(base, P1, P2, tip, s)
    d = np.gradient(pts, axis=0)
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    nrm /= (np.linalg.norm(nrm, axis=1, keepdims=True) + 1e-6)
    wa = 5 + 18 * 4 * e * (1 - e) + (2.5 if e > 0.98 else 0)
    ph = 2 * np.pi * (2.0 * sn - 1.6 * t + 0.3 * i)
    pts = pts + nrm * (wa * np.sin(ph) * np.sin(np.pi * sn))[:, None]
    r = (31 * (1 - sn) ** 0.8 + 6) * (1 - 0.34 * smooth(e))
    tan = pts[-1] - pts[-2]; tan = tan / (np.linalg.norm(tan) + 1e-6)
    hp = []; hr = []
    ang = 0.0; cur = pts[-1].copy()
    for j in range(1, 9):
        ang += -sx * 0.22
        c, s_ = math.cos(ang), math.sin(ang)
        dv = np.array([tan[0] * c - tan[1] * s_, tan[0] * s_ + tan[1] * c])
        cur = cur + dv * 7.0
        hp.append(cur.copy()); hr.append(max(1.0, r[-1] * (1 - j / 9.0)))
    Pp = np.vstack([pts, np.array(hp)]); R = np.concatenate([r, np.array(hr)])
    d2 = np.gradient(Pp, axis=0)
    NR = np.stack([-d2[:, 1], d2[:, 0]], 1)
    NR /= (np.linalg.norm(NR, axis=1, keepdims=True) + 1e-6)
    act = STEPCOL[i]; rim = mix((16, 96, 118), act, e)
    nseg = len(Pp) - 1
    for k in range(nseg + 1):
        u = k / nseg
        col = (int(26 - 10 * u), int(36 - 14 * u), int(76 - 28 * u))
        cv2.circle(cv.f, (int(round(Pp[k][0])), int(round(Pp[k][1]))), int(round(R[k] + 1)), m(col, gain), -1, cv2.LINE_AA)
    for k in range(0, nseg, 2):
        a_ = Pp[k]; b_ = Pp[k + 1]
        q = np.array([a_ + NR[k] * R[k], b_ + NR[k + 1] * R[k + 1], b_ - NR[k + 1] * R[k + 1], a_ - NR[k] * R[k]])
        u = k / nseg
        col = (int(40 - 16 * u), int(54 - 20 * u), int(104 - 38 * u))
        cv2.fillConvexPoly(cv.f, np.round(q).astype(np.int32), m(col, gain), cv2.LINE_AA)
    Lw = Pp + NR * R[:, None]; Rw = Pp - NR * R[:, None]
    cv.poly(Lw, m(rim, gain), 2, glow=0.7 * e * gain)
    cv.poly(Rw, m(rim, gain), 2, glow=0.7 * e * gain)
    for k in range(4, nseg, 4):
        cv.poly([Lw[k], Rw[k]], m(mix(CYD, act, e * 0.8), 0.9 * gain), 2)
    cv.poly(Pp[3:N], m(mix(CY, act, e), (0.35 + 0.6 * e) * gain), 2, glow=(0.15 + 0.85 * e) * gain)
    for k in range(5, N - 8, 5):
        side = 1 if (k // 5) % 2 == 0 else -1
        a0 = Pp[k] + NR[k] * R[k] * side
        tp = a0 + NR[k] * side * (R[k] * 0.9 + 12) + (Pp[k + 1] - Pp[k]) * 1.5
        c0 = Pp[k + 3] + NR[k + 3] * R[k + 3] * side
        tri = np.round(np.array([a0, tp, c0])).astype(np.int32)
        cv2.fillConvexPoly(cv.f, tri, m((16, 22, 48), gain), cv2.LINE_AA)
        cv2.polylines(cv.f, [tri], True, m(mix(CYD, act, e), gain), 1, cv2.LINE_AA)
    tipc = Pp[-1]
    cv.circle(tipc, 4, m(mix(WH, act, 0.5), gain), -1, glow=0.5 + 0.5 * e)

def draw_node10(cv, i, e, t, a):
    c = NODES10[i]; col = STEPCOL[i]
    cv.circle(c, 44, m(INK, a), -1)
    cv.circle(c, 38, m(col, a * (0.10 + 0.28 * e)), -1)
    cv.circle(c, 44, m(mix(CYD, col, e), a), 3, glow=0.9 * e * a)
    cv.text(c[0], c[1], NAMES[i], 'b', 17, mix(DIM, WH, e), a, 'mm')
    if e > 0.98:
        rot = t * 160
        for k in range(4):
            cv.ellipse(c, (58, 58), m(col, a), 3, glow=0.9, ang=0, a0=rot + k * 90, a1=rot + k * 90 + 48)

# ------------------------------------------------------------------ panels
def draw_panel10(cv, a, title, sub=None, subcol=CY):
    if a <= 0.02: return
    pts = chamfer(PX0, PY0, PX1, PY1, 26)
    cv.fillpoly(pts, PANEL, 0.88 * a)
    cv.poly(pts, m(CYD, a), 2, glow=0.35 * a, closed=True)
    cv.poly([(PX0 + 26, PY0), (PX0 + 90, PY0)], m(CY, a), 4, glow=0.9 * a)
    cv.poly([(PX1 - 26, PY1), (PX1 - 90, PY1)], m(PU, a), 4, glow=0.9 * a)
    cv.text(PX0 + 22, PY0 + 16, title, 'b', 27, WH, a)
    if sub:
        cv.text(PX1 - 22, PY0 + 20, sub, 'md', 24, subcol, a, 'ra')

def draw_intro_title(cv, t):
    a = ramp(t, 0.6, 1.3) * (1 - ramp(t, 3.3, 3.8))
    if a <= 0: return
    cv.text(540, 880, "OCTOPUS 6 AI", 'b', 118, WH, a, 'mm', glow=0.3)
    cv.text(540, 990, "MASTER V10 APEX", 'b', 66, PU, a, 'mm', glow=0.45)
    cv.text(540, 1060, "CINEMATIC AI TRADING SYSTEM  ·  SOLANA  ·  6 AI AGENTS", 'md', 24, CY, a * ramp(t, 1.0, 1.7), 'mm')

def draw_funnel(cv, a, t):
    if a <= 0.02: return
    draw_panel10(cv, a, "DATA INTAKE  ·  LIVE", "4 SOURCES  ·  SOLANA", CY)
    srcs = ["MEVX", "PUMP.FUN", "GMGN", "DEXSCREENER"]
    for i, s in enumerate(srcs):
        x0 = PX0 + 15 + i * 190; x1 = x0 + 180; y0 = PY0 + 62; y1 = y0 + 46
        ta = 4.0 + 0.3 * i; ai = ramp(t, ta, ta + 0.3) * a
        pulse = 0.5 + 0.5 * math.sin(t * 6 + i * 1.3)
        pts = chamfer(x0, y0, x1, y1, 10)
        cv.fillpoly(pts, mix(PANEL, CY, 0.2), 0.9 * ai)
        cv.poly(pts, m(mix(CYD, CY, pulse), ai), 2, glow=0.6 * pulse * ai, closed=True)
        cv.text((x0 + x1) / 2 + 6, (y0 + y1) / 2, s, 'b', 19, WH, ai, 'mm')
        cv.circle((x0 + 16, y0 + 23), 4, m(GR, ai * (0.4 + 0.6 * pulse)), -1, glow=0.8 * ai)
    n = int(SCANNED * smooth(ramp(t, 4.6, 7.6)))
    cv.text(540, PY0 + 124, "NEW TOKENS TODAY", 'b', 20, DIM, a * ramp(t, 4.4, 5.0), 'mm')
    cv.text(540, PY0 + 184, f"{n:,}", 'mono', 64, WH, a * ramp(t, 4.4, 5.0), 'mm', glow=0.5)
    ft, fb = PY0 + 240, PY0 + 450
    def hw(y): return 350 - (350 - 62) * (y - ft) / (fb - ft)
    outl = [(540 - hw(ft), ft), (540 - hw(fb), fb), (540 + hw(fb), fb), (540 + hw(ft), ft)]
    cv.fillpoly(outl, mix(PANEL, CY, 0.06), 0.9 * a)
    cv.poly([outl[0], outl[1]], m(CYD, a), 2, glow=0.4 * a)
    cv.poly([outl[3], outl[2]], m(CYD, a), 2, glow=0.4 * a)
    rng = np.random.default_rng(8)
    NP = 280
    xf = rng.uniform(-0.95, 0.95, NP); st = 4.8 + 2.8 * rng.uniform(0, 1, NP)
    r1 = rng.uniform(0, 1, NP); r2 = rng.uniform(0, 1, NP)
    y1s = ft + 0.36 * (fb - ft); y2s = ft + 0.7 * (fb - ft)
    v = 120.0
    for p in range(NP):
        tau = t - st[p]
        if tau < 0: continue
        y = ft + v * tau
        if y > fb + 14: continue
        x = 540 + xf[p] * hw(min(y, fb))
        col = CY; al = a; r = 3
        rej_y = None
        if r1[p] < 0.72: rej_y = y1s
        elif r2[p] < 0.65: rej_y = y2s
        if rej_y is not None and y > rej_y:
            dt_ = (y - rej_y) / v
            x = 540 + xf[p] * hw(rej_y) + np.sign(xf[p] + 1e-3) * 110 * dt_
            y = rej_y + 30 * dt_
            col = RD; al = a * max(0.0, 1 - dt_ * 1.6)
        elif rej_y is None:
            col = GR; r = 4
            x = 540 + xf[p] * hw(min(y, fb)) * (1 - 0.0)
        if al > 0.02:
            cv.circle((x, y), r, m(col, al), -1, glow=0.6 * al if col == GR else 0.0)
    for (yy, lab) in [(y1s, "LIQUIDITY  ·  RISK  ·  QUALITY"), (y2s, "CHART  +  MOMENTUM SIGNALS")]:
        la = a * ramp(t, 5.0, 5.6)
        cv.poly([(540 - hw(yy), yy), (540 + hw(yy), yy)], m(PU, la), 2, glow=0.8 * la)
        wdt = F('b', 18).getlength(lab)
        cv.rect(540 - wdt / 2 - 10, yy - 14, 540 + wdt / 2 + 10, yy + 14, INK, 0.85 * la)
        cv.text(540, yy, lab, 'b', 18, WH, la, 'mm')
    k = int(round(OC.SHORT * smooth(ramp(t, 7.8, 9.6))))
    pts = chamfer(PX0 + 170, PY0 + 476, PX1 - 170, PY0 + 526, 12)
    done = t >= 9.6
    col = GR if done else CY
    cv.fillpoly(pts, mix(PANEL, col, 0.22), 0.95 * a)
    cv.poly(pts, m(col, a), 3, glow=(0.9 if done else 0.4) * a, closed=True)
    cv.text(PX0 + 196, PY0 + 501, "SHORTLIST", 'b', 20, DIM, a, 'lm')
    cv.text(540, PY0 + 501, f"{k}", 'mono', 38, WH, a, 'mm', glow=0.5)
    cv.text(PX1 - 196, PY0 + 501, "PASSED", 'b', 20, col, a, 'rm')

def draw_scan10(cv, a, t):
    if a <= 0.02: return
    n = int(round(OC.SHORT * smooth(ramp(t, 10.2, 11.8))))
    draw_panel10(cv, a, "SCAN  ·  SCOUT + FILTER", f"Shortlist {n}/{OC.SHORT}", CY)
    rows = 10
    first = max(0, n - rows)
    for r in range(rows):
        k = first + r
        if k >= n: break
        y = PY0 + 98 + r * 46
        fade = 1.0 if n <= rows else (0.45 + 0.55 * r / (rows - 1))
        cv.text(PX0 + 26, y, f"{k + 1:02d}", 'mono', 20, DIM, a * fade, 'lm')
        cv.text(PX0 + 80, y, f"${TOKENS[k]}", 'mono', 26, WH, a * fade, 'lm')
        cv.text(PX0 + 270, y, "LIQ  ·  RISK", 'md', 18, DIM, a * fade, 'lm')
        check_icon(cv, PX0 + 440, y, 9, GR, a * fade, 3)
        cv.text(PX0 + 460, y, "PASS", 'mono', 18, GR, a * fade, 'lm')
    rc = (PX1 - 150, PY0 + 300); R = 135
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

def draw_grid10(cv, a, pmin, pmax, cx0, cx1, cy0, cy1):
    for k in range(5):
        y = cy0 + (cy1 - cy0) * k / 4
        cv.poly([(cx0, y), (cx1 + 6, y)], m(CYD, a * 0.35), 1)

def card_frame(cv, a, col, y0=992, y1=1128):
    pts = chamfer(PX0 + 14, y0, PX1 - 14, y1, 16)
    cv.fillpoly(pts, mix(PANEL, col, 0.22), 0.95 * a)
    cv.poly(pts, m(col, a), 3, glow=0.9 * a, closed=True)

def card_buy(cv, a):
    y0, y1 = 992, 1128
    card_frame(cv, a, GR, y0, y1)
    cv.fillpoly(chamfer(PX0 + 28, y0 + 16, PX0 + 168, y1 - 16, 10), GR, 0.95 * a)
    cv.text(PX0 + 98, (y0 + y1) / 2, "BUY", 'b', 46, INK, a, 'mm')
    cv.text(PX0 + 190, y0 + 34, "$NEBU  ·  entry 0.000420", 'md', 24, DIM, a, 'lm')
    txt = f"{solf(1000)} SOL  ≈  {usd(1000)}"
    cv.text(PX0 + 190, y0 + 82, txt, 'mono', fit(txt, 'mono', 40, 400), WH, a, 'lm', glow=0.4)
    check_icon(cv, PX1 - 72, y0 + 46, 14, GR, a, 4, glow=0.8)
    cv.text(PX1 - 72, y0 + 98, "CONFIRMED", 'b', 17, GR, a, 'mm')

def card_sell(cv, a):
    y0, y1 = 992, 1128
    tr = TR[0]
    card_frame(cv, a, MG, y0, y1)
    cv.fillpoly(chamfer(PX0 + 28, y0 + 16, PX0 + 168, y1 - 16, 10), MG, 0.95 * a)
    cv.text(PX0 + 98, (y0 + y1) / 2, "SELL", 'b', 46, INK, a, 'mm')
    cv.text(PX0 + 190, y0 + 34, "$NEBU  ·  exit 0.000557", 'md', 24, DIM, a, 'lm')
    txt = f"{solf(tr['after'])} SOL  ≈  {usd(tr['after'])}"
    cv.text(PX0 + 190, y0 + 82, txt, 'mono', fit(txt, 'mono', 40, 340), WH, a, 'lm', glow=0.4)
    cv.text(PX1 - 34, y0 + 36, usd(tr['pnl'], True), 'mono', 46, GR, a, 'rm', glow=0.8)
    cv.text(PX1 - 34, y0 + 76, f"{solf(tr['pnl'], True)} SOL", 'mono', 24, GR, a, 'rm')
    cv.text(PX1 - 34, y0 + 106, f"{tr['ret'] * 100:+.1f}%", 'mono', 24, WH, a, 'rm')

def card_check(cv, a):
    y0, y1 = 992, 1128
    card_frame(cv, a, CY, y0, y1)
    check_icon(cv, PX0 + 96, (y0 + y1) / 2, 30, GR, a, 8, glow=0.9)
    cv.text(PX0 + 170, y0 + 44, "TRADE VERIFIED", 'b', 44, WH, a, 'lm', glow=0.3)
    cv.text(PX0 + 170, y0 + 96, "LOGGER  ·  trade #1 recorded", 'md', 24, DIM, a, 'lm')

def card_pnl(cv, a, u):
    y0, y1 = 992, 1128
    tr = TR[0]
    card_frame(cv, a, GR, y0, y1)
    cv.text(PX0 + 36, y0 + 30, "TRADE #1  PNL", 'b', 22, DIM, a, 'lm')
    cv.text(PX0 + 36, y0 + 84, usd(tr['pnl'] * u, True), 'mono', 70, GR, a, 'lm', glow=0.9)
    cv.text(PX1 - 34, y0 + 52, f"{solf(tr['pnl'] * u, True)} SOL", 'mono', 40, GR, a, 'rm', glow=0.5)
    cv.text(PX1 - 34, y0 + 100, f"{tr['ret'] * 100 * u:+.1f}%", 'mono', 30, WH, a, 'rm')

def draw_trade1(cv, a, t):
    if a <= 0.02: return
    step = int((t - STEP0) // STEPD)
    caps = {2: "ANALYST reads the $NEBU chart", 1: "ANALYST reads the $NEBU chart", 2.5: "", 3: "EXECUTOR  ·  BUY",
            4: "RISK tracks the position", 5: "EXECUTOR  ·  SELL", 6: "LOGGER verifies the trade", 7: "LOGGER records PnL"}
    caps[2] = "RISK checks the wallet"
    draw_panel10(cv, a, "$NEBU / SOL  ·  1m", caps.get(step, ""), STEPCOL[step] if 0 <= step < 8 else CY)
    nrev = nrev_t1(t)
    cx0, cx1, cy0, cy1 = PX0 + 22, PX1 - 92, PY0 + 78, PY0 + 306
    draw_grid10(cv, a, ENTRY * T1MIN, ENTRY * T1MAX, cx0, cx1, cy0, cy1)
    n = 48; cw = (cx1 - cx0) / n
    yf = lambda p: cy1 - (p - T1MIN) / (T1MAX - T1MIN) * (cy1 - cy0)
    for i in range(n):
        if nrev <= i: break
        fr = clamp(nrev - i)
        o = T1O[i]; c = o + (T1C[i] - o) * fr
        h_ = max(o, c) + (T1H[i] - max(T1O[i], T1C[i])) * fr
        l_ = min(o, c) - (min(T1O[i], T1C[i]) - T1L[i]) * fr
        x = cx0 + (i + 0.5) * cw
        candle(cv, x, 8.5, yf(o), yf(h_), yf(l_), yf(c), c >= o, a, glow=0.5 if (i == int(nrev) and fr < 1.0) else 0.0)
    if nrev > 1:
        i = min(int(nrev - 1e-6), n - 1)
        fr = clamp(nrev - i); cl = T1O[i] + (T1C[i] - T1O[i]) * fr
        y = yf(cl)
        for xx in range(int(cx0), int(cx1), 14):
            cv.poly([(xx, y), (xx + 7, y)], m(WH, a * 0.55), 1)
        txt = f"{ENTRY * cl:.6f}"
        wd = F('b', 17).getlength(txt)
        cv.rect(cx1 + 8, y - 12, cx1 + 8 + wd + 12, y + 12, mix(CYD, INK, 0.2), a)
        cv.text(cx1 + 14, y, txt, 'b', 17, WH, a, 'lm')
    if t >= TB:
        arrow_marker(cv, cx0 + 14.5 * cw, yf(T1L[14]), True, GR, a, None, 0.6 + 0.4 * easeout((t - TB) / 0.25))
    if t >= TS:
        arrow_marker(cv, cx0 + 34.5 * cw, yf(T1H[34]), False, MG, a, f"SELL {EXIT1:.6f}", 0.6 + 0.4 * easeout((t - TS) / 0.25))
    if 14.0 <= t < 16.0:
        oa = a * min(ramp(t, 14.0, 14.4), 1 - ramp(t, 15.6, 16.0))
        bx0, by0 = PX0 + 26, PY0 + 84
        pts = chamfer(bx0, by0, bx0 + 360, by0 + 118, 14)
        cv.fillpoly(pts, INK, 0.9 * oa)
        cv.poly(pts, m(PU, oa), 2, glow=0.7 * oa, closed=True)
        cv.text(bx0 + 18, by0 + 22, "WALLET", 'b', 19, PU, oa, 'lm')
        cv.text(bx0 + 18, by0 + 62, f"{solf(1000)} SOL", 'mono', 38, WH, oa, 'lm', glow=0.4)
        cv.text(bx0 + 18, by0 + 98, f"≈ {usd(1000)}   ·   position {solf(1000)} SOL", 'md', 17, DIM, oa, 'lm')
    if 18.0 <= t < 22.0:
        oa = a * min(ramp(t, 18.0, 18.3), 1 - ramp(t, 21.6, 22.0))
        i = min(int(nrev - 1e-6), 47); pct = (T1C[i] - 1.0) * 100
        up = 1000.0 * (T1C[i] - 1.0)
        bx0, by0 = PX0 + 26, PY0 + 84
        pts = chamfer(bx0, by0, bx0 + 330, by0 + 70, 12)
        cv.fillpoly(pts, INK, 0.9 * oa)
        cv.poly(pts, m(PU, oa), 2, glow=0.6 * oa, closed=True)
        cv.text(bx0 + 16, by0 + 24, "OPEN PROFIT", 'md', 18, DIM, oa, 'lm')
        cv.text(bx0 + 314, by0 + 24, f"{pct:+.1f}%", 'mono', 28, GR if pct >= 0 else RD, oa, 'rm', glow=0.5)
        cv.text(bx0 + 314, by0 + 54, f"{usd(up, True)}  ·  {solf(up, True)} SOL", 'mono', 18, GR if up >= 0 else RD, oa, 'rm')
    ca = a * ramp(t, TB + 0.1, TB + 0.3) * (1 - ramp(t, TB + 1.4, TB + 1.6))
    if ca > 0.02: card_buy(cv, ca)
    ca = a * ramp(t, TS + 0.1, TS + 0.3) * (1 - ramp(t, TS + 1.4, TS + 1.6))
    if ca > 0.02: card_sell(cv, ca)
    ca = a * ramp(t, 22.0, 22.25) * (1 - ramp(t, 23.8, 24.0))
    if ca > 0.02: card_check(cv, ca)
    ca = a * ramp(t, 24.0, 24.25) * (1 - ramp(t, 25.7, 26.0))
    if ca > 0.02: card_pnl(cv, ca, easeout(ramp(t, 24.0, 25.0)))

SL = [(-1, (778.0, 96.0)), (0, (886.0, 96.0)), (1, (990.0, 58.0)), (2, (1054.0, 58.0)), (3, (1116.0, 0.0))]
def geom(x):
    for (a0, g0), (a1, g1) in zip(SL[:-1], SL[1:]):
        if a0 <= x <= a1:
            u = (x - a0) / (a1 - a0)
            return g0[0] + (g1[0] - g0[0]) * u, g0[1] + (g1[1] - g0[1]) * u
    return SL[-1][1]

def feed_card(cv, a, k, y0, h, hi):
    if h < 8 or a <= 0.02: return
    tr = TR[k - 1]; col = GR if tr['win'] else RD
    x0 = PX0 + 20
    pts = chamfer(x0, y0, x0 + 740, y0 + h, 12)
    cv.fillpoly(pts, mix(PANEL, col, 0.22 if hi else 0.12), 0.92 * a)
    cv.poly(pts, m(col, a), 3 if hi else 2, glow=(0.9 if hi else 0.2) * a, closed=True)
    pnl = tr['pnl']
    tag = "WIN" if tr['win'] else "LOSS"
    if h >= 80:
        cv.text(x0 + 22, y0 + 26, f"#{k}   ${tr['token']}   ·   BUY → SELL", 'b', 24, WH, a, 'lm')
        cv.text(x0 + 718, y0 + 26, tag, 'b', 24, col, a, 'rm', glow=0.5)
        txt = f"{solf(tr['before'])} SOL ≈ {usd(tr['before'])}  →  {solf(pnl, True)} SOL   {usd(pnl, True)}"
        cv.text(x0 + 22, y0 + 66, txt, 'mono', fit(txt, 'mono', 30, 696), col, a, 'lm', glow=0.4)
    else:
        txt = f"#{k} ${tr['token']}   {solf(tr['before'])} SOL → {solf(pnl, True)} SOL   {usd(pnl, True)}"
        cv.text(x0 + 20, y0 + h / 2, txt, 'mono', fit(txt, 'mono', 24, 640), mix(WH, col, 0.5), a, 'lm')
        cv.text(x0 + 720, y0 + h / 2, tag, 'b', 22, col, a, 'rm')

def draw_mont10(cv, a, t):
    if a <= 0.02: return
    kd = sum(1 for ev in EV if t >= ev)
    draw_panel10(cv, a, "SOLANA MARKET  ·  1m", f"{kd}/30 trades closed", CY)
    head = 60 + (t - MONT0) * 7.0
    n = 38
    hi_i = int(head); i0 = hi_i - n + 1
    his = np.array([max(MCL[j - 1], MCL[j]) * (1 + MHI_N[j]) for j in range(i0, hi_i + 1)])
    los = np.array([min(MCL[j - 1], MCL[j]) * (1 - MLO_N[j]) for j in range(i0, hi_i + 1)])
    pmin = los.min() * 0.97; pmax = his.max() * 1.03
    cx0, cx1, cy0, cy1 = PX0 + 22, PX1 - 92, PY0 + 74, PY0 + 204
    draw_grid10(cv, a, pmin, pmax, cx0, cx1, cy0, cy1)
    cw = (cx1 - cx0) / n
    yf = lambda p: cy1 - (p - pmin) / (pmax - pmin) * (cy1 - cy0)
    frac = head - hi_i
    for r, j in enumerate(range(i0, hi_i + 1)):
        o = MCL[j - 1]; c = MCL[j]; hh = his[r]; ll = los[r]
        fr = frac if j == hi_i else 1.0
        cc = o + (c - o) * fr
        x = cx0 + (r + 0.5) * cw - frac * cw
        if x < cx0: continue
        candle(cv, x, 10, yf(o), yf(max(o, cc) + (hh - max(o, c)) * fr), yf(min(o, cc) - (min(o, c) - ll) * fr), yf(cc), cc >= o, a)
    for k in range(2, 31):
        ev = EV[k - 1]
        age = t - (ev - 0.2)
        if age < 0 or age > 1.6: continue
        fa = a * (1.0 - 0.7 * ramp(age, 0.8, 1.6))
        sc = 0.5 * (0.6 + 0.4 * easeout(age / 0.2))
        jb = head - age * 7.0 - 0.0
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
    kcur = kd
    if kcur >= 1:
        u = easeout(ramp(t, EV[kcur - 1], EV[kcur - 1] + 0.2))
        for j in range(0, 4):
            kk = kcur - j
            if kk < 1: break
            x = j - (1 - u)
            y0, h = geom(x)
            al = 1.0 if 0 <= x <= 2 else (1 + x if x < 0 else max(0.0, 3 - x))
            feed_card(cv, a * clamp(al), kk, y0, h, hi=(j == 0))

_NW = sum(1 for _t in TR if _t['win']); _NL = len(TR) - _NW
RESULT_ROWS = [("Tokens scanned today", lambda u: f"{int(SCANNED * u):,}", WH),
               ("Shortlisted", lambda u: f"{int(round(OC.SHORT * u))}", WH),
               ("Trades", lambda u: f"{int(round(OC.NT * u))}", WH),
               ("Wins", lambda u: f"{int(round(_NW * u))}", GR),
               ("Losses", lambda u: f"{int(round(_NL * u))}", RD),
               ("Win rate", lambda u: f"{100.0 * _NW / OC.NT * u:.2f}%", CY),
               ("Starting balance", lambda u: f"{solf(OC.START)} SOL  ≈  {usd(OC.START)}", WH),
               ("Profit", lambda u: f"{usd(OC.PROFIT * u, True)}   {solf(OC.PROFIT * u, True)} SOL", GOLD),
               ("Ending balance", lambda u: f"{solf(OC.START + OC.PROFIT * u)} SOL  ≈  {usd(OC.START + OC.PROFIT * u)}", GOLD),
               ("ROI", lambda u: f"{100.0 * OC.PROFIT / OC.START * u:+,.1f}%", GOLD)]

def draw_results(cv, a, t):
    if a <= 0.02: return
    draw_panel10(cv, a, "FINAL RESULTS", "TODAY'S RUN", GOLD)
    for i, (lab, fn, col) in enumerate(RESULT_ROWS):
        ta = 38.4 + i * 0.3
        ra = ramp(t, ta, ta + 0.25) * a
        if ra <= 0: continue
        u = easeout(ramp(t, ta, ta + 1.1))
        y = PY0 + 90 + i * 45
        slide = (1 - easeout(ramp(t, ta, ta + 0.25))) * 40
        if i % 2 == 0:
            cv.rect(PX0 + 14, y - 21, PX1 - 14, y + 21, PUD, 0.22 * ra)
        cv.text(PX0 + 58 - slide, y, lab, 'md', 27, DIM if col not in (GOLD,) else WH, ra, 'lm')
        s = fn(u)
        cv.text(PX1 - 40 + slide, y, s, 'mono', fit(s, 'mono', 30, 480), col, ra, 'rm', glow=0.6 if col == GOLD else 0.0)
    if t > 41.5:
        y = PY0 + 90 + 9 * 45
        pu = 0.5 + 0.5 * math.sin((t - 41.5) * 5)
        cv.poly(chamfer(PX0 + 14, y - 21, PX1 - 14, y + 21, 8), m(GOLD, a * (0.5 + 0.5 * pu)), 2, glow=0.9 * pu, closed=True)

# ------------------------------------------------------------------ bottom UI
def draw_chips10(cv, t, L, a):
    for i in range(6):
        ai = a
        col = AGN[i][1]; lv = L[i]
        x0 = 40 + i * 166; y0 = 1156; w_, h_ = 160, 140
        pts = chamfer(x0, y0, x0 + w_, y0 + h_, 14)
        cv.fillpoly(pts, mix(PANEL, col, 0.28 * lv), 0.85 * ai)
        cv.poly(pts, m(mix(CYD, col, lv), ai), 2, glow=0.8 * lv * ai, closed=True)
        agent_icon(cv, i, (x0 + w_ / 2, y0 + 52), col, ai, lv)
        cv.text(x0 + w_ / 2, y0 + 106, AGN[i][0], 'b', 22, mix(DIM, WH, 0.35 + 0.65 * lv), ai, 'mm')
        st = "ACTIVE" if lv > 0.6 else ("READY" if lv > 0.3 else "STANDBY")
        cv.text(x0 + w_ / 2, y0 + 128, st, 'md', 15, col if lv > 0.6 else DIM, ai, 'mm')

def draw_profit(cv, t, a, pulse):
    if a <= 0.02: return
    kd, live, xend = profit_state(t)
    pts = chamfer(40, 1312, 1040, 1568, 18)
    gold = t >= MONT1 + 0.2
    col = GOLD if gold else (GR if live >= 0 else RD)
    cv.fillpoly(pts, mix(PANEL, col, 0.10), 0.9 * a)
    cv.poly(pts, m(col, a), 2, glow=(0.4 + 0.5 * pulse) * a, closed=True)
    cv.text(70, 1342, "LIVE PROFIT", 'b', 26, WH, a, 'lm')
    cv.text(70, 1378, f"≈ {solf(live, True)} SOL" if kd or t >= 18 else "waiting for first trade", 'mono' if kd or t >= 18 else 'md', 22, DIM, a, 'lm')
    sz = int(66 * (1 + 0.14 * pulse))
    cv.text(1010, 1352, usd(live, True), 'mono', sz, col, a, 'rm', glow=0.8)
    x0, x1, y0, y1 = 120, 1000, 1408, 1546
    xmax = max(1.0, xend)
    vals = CUM[:kd + 1] + [live]
    ymax = max(100.0, max(vals)) * 1.18
    ymin = min(0.0, min(vals)) * 1.3
    X = lambda x: x0 + x / xmax * (x1 - x0)
    Y = lambda v: y1 - (v - ymin) / (ymax - ymin) * (y1 - y0)
    step = 10 ** math.floor(math.log10(max(ymax, 1) / 3.0))
    for mult in (1, 2, 5, 10):
        if ymax / (step * mult) <= 4: step *= mult; break
    v = math.ceil(ymin / step) * step
    while v <= ymax:
        yy = Y(v)
        cv.poly([(x0, yy), (x1, yy)], m(CYD, a * (0.7 if abs(v) < 1e-9 else 0.3)), 1)
        cv.text(x0 - 10, yy, moneyk(v), 'md', 16, DIM, a, 'rm')
        v += step
    px = [(X(0), Y(0.0))] + [(X(j), Y(CUM[j])) for j in range(1, kd + 1)]
    if kd < 30 and (xend > kd + 1e-6 or kd == 0):
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
            cv.circle(px[j], 4, m(WH, a * 0.8), -1)
        hd = px[-1]
        cv.circle(hd, 8, m(GOLD if gold else WH, a), -1, glow=1.0 * a)
    cv.text(x1, y1 + 14, f"trade {min(30, int(round(xend)))}/30", 'md', 15, DIM, a, 'rm')

def draw_stats10(cv, t, a, vals):
    scanned, done, wins, losses, bal = vals
    tiles = [("TOKENS SCANNED", f"{scanned:,}", WH, None), ("TRADES", f"{done}/30", WH, None),
             ("WINS / LOSSES", None, None, None), ("BALANCE", usd(bal), CY, f"≈ {solf(bal)} SOL")]
    for i, (lab, val, col, sub) in enumerate(tiles):
        x0 = 40 + i * 252; x1 = x0 + 242; y0, y1 = 1584, 1706
        pts = chamfer(x0, y0, x1, y1, 14)
        cv.fillpoly(pts, PANEL, 0.85 * a)
        cv.poly(pts, m(CYD, a), 2, closed=True)
        cv.text(x0 + 16, y0 + 24, lab, 'b', 19, DIM, a, 'lm')
        if val is not None:
            sz = fit(val, 'mono', 44, 214)
            cv.text(x0 + 16, y0 + 70, val, 'mono', sz, col, a, 'lm', glow=0.35 if i == 3 else 0.0)
            if sub:
                cv.text(x0 + 16, y0 + 102, sub, 'mono', 21, DIM, a, 'lm')
        else:
            cv.text(x0 + 16, y0 + 70, f"{wins}", 'mono', 44, GR, a, 'lm', glow=0.35)
            wd = F('mono', 44).getlength(f"{wins}")
            cv.text(x0 + 16 + wd + 8, y0 + 70, "/", 'mono', 38, DIM, a, 'lm')
            cv.text(x0 + 16 + wd + 34, y0 + 70, f"{losses}", 'mono', 44, RD, a, 'lm', glow=0.35)

# ------------------------------------------------------------------ frame
def render10(t):
    cv = Cv(BG)
    core.particles(cv, t)
    e = tent_state(t)
    L = agent_levels(t, e)
    vals = counters10(t)
    aUI = ramp(t, 1.6, 3.2)
    cv.text(540, 52, "OCTOPUS 6 AI  ·  MASTER V10 APEX", 'sb', 24, DIM, ramp(t, 2.4, 3.2), 'mm')
    draw_intro_title(cv, t)
    if 3.7 <= t < 10.2:
        draw_funnel(cv, ramp(t, 3.7, 4.1) * (1 - ramp(t, 9.8, 10.1)), t)
    if 10.0 <= t < 12.4:
        draw_scan10(cv, ramp(t, 10.0, 10.25) * (1 - ramp(t, 11.9, 12.2)), t)
    if 12.0 <= t < 26.2:
        draw_trade1(cv, ramp(t, 12.0, 12.3) * (1 - ramp(t, 25.7, 26.0)), t)
    if 25.9 <= t < 38.2:
        draw_mont10(cv, ramp(t, 25.9, 26.2) * (1 - ramp(t, 37.8, 38.1)), t)
    if t >= 37.9:
        draw_results(cv, ramp(t, 37.9, 38.4), t)
    pulse = 0.0
    if t >= MONT1:
        pulse = max(0.0, math.sin(clamp((t - MONT1) / 1.2) * math.pi))
    if aUI > 0:
        for i in range(8):
            draw_node10(cv, i, e[i], t, aUI)
        draw_chips10(cv, t, L, aUI)
        draw_profit(cv, t, aUI, pulse)
        draw_stats10(cv, t, aUI, vals)
    cv.text(540, 1790, "Illustrative figures  ·  Not financial advice", 'md', 24, DIM, ramp(t, 0.0, 0.6) * 0.85, 'mm')
    grow = easeout(ramp(t, 0.5, 2.4))
    gain = easeout(ramp(t, 0.0, 1.4))
    for i in range(8):
        draw_tentacle10(cv, i, e[i], t, grow, gain)
    best = max(range(8), key=lambda i: e[i])
    et = NODES10[best] if e[best] > 0.15 else None
    ecol = mix(CY, STEPCOL[best], e[best]) if e[best] > 0.15 else CY
    for ev in EV:
        if ev <= t < ev + 0.25:
            ecol = RD; et = et or (540, 900)
    scan = None
    if 4.0 <= t < 10.0:
        scan = ((t - 4.0) % 1.1) / 1.1
    elif 0.8 <= t < 2.4:
        scan = ((t - 0.8) % 0.8) / 0.8
    open_ = easeout(ramp(t, 0.3, 0.9))
    draw_head10(cv, t, gain, et, ecol, scan, L, open_)
    if 0.5 <= t < 1.6:
        u = ramp(t, 0.5, 1.6)
        cv.ellipse((HX, HY + 20), (int(120 + 700 * easeout(u)), int(90 + 500 * easeout(u))), m(CY, 1 - u), 3, glow=1.0 * (1 - u))
    if MONT1 <= t < MONT1 + 1.5:
        u = ramp(t, MONT1, MONT1 + 1.5)
        cv.flash = (1 - ramp(t, MONT1, MONT1 + 0.5)) * 0.9
        for k in range(28):
            ang = k * 2 * math.pi / 28 + 0.1
            r0 = 140 + 700 * easeout(u); r1 = r0 + 60 + 120 * (1 - u)
            col = CY if k % 2 else PU
            cv.poly([(HX + r0 * math.cos(ang), HY + 30 + r0 * math.sin(ang) * 0.9),
                     (HX + r1 * math.cos(ang), HY + 30 + r1 * math.sin(ang) * 0.9)], m(col, (1 - u) * 0.9), 3, glow=1.0 * (1 - u))
        cv.ellipse((HX, HY + 20), (int(200 + 600 * easeout(u)), int(160 + 480 * easeout(u))), m(WH, (1 - u)), 4, glow=1.0 * (1 - u))
    for ev in EV:
        if TS <= ev <= t < ev + 0.12 and ev == TS:
            cv.flash = max(cv.flash, 0.2)
    out = cv.finish()
    if t >= MONT1:
        sh = 0.35 * smooth(ramp(t, MONT1, MONT1 + 2.0)) * (1 - smooth(ramp(t, 42.6, 44.0)))
        if sh > 0.01:
            out = np.array(out)
            ys = np.arange(560, 900)
            fac = 1 - sh * (1 - (ys - 560) / 340.0)
            out[560:900] = (out[560:900] * fac[:, None, None]).astype(np.uint8)
    return out

def write_scene(name, t0, t1):
    n = int(round((t1 - t0) * FPS))
    tmp = f"{OUT}/s10_{name}.tmp.mp4"
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS),
           '-i', '-', '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-r', str(FPS), tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n):
        p.stdin.write(render10(t0 + f / FPS).tobytes())
    p.stdin.close()
    rc = p.wait()
    if rc == 0:
        os.rename(tmp, f"{OUT}/s10_{name}.mp4")
        print('done', name, n, 'frames')
    else:
        print('ffmpeg failed', rc); sys.exit(1)

if __name__ == '__main__':
    mode = sys.argv[1]
    if mode == 'still':
        for ts in sys.argv[2:]:
            Image.fromarray(render10(float(ts))).save(f"{OUT}/v10_{ts}.png")
            print('saved', ts)
    elif mode == 'scene':
        write_scene(sys.argv[2], float(sys.argv[3]), float(sys.argv[4]))

"""OCTO AI V5 mother: armoured, faceted, cinematic. Reuses the oct3d renderer."""
import math
import numpy as np
from scipy.interpolate import CubicSpline
from oct3d import Surf, ellipsoid, smoothstep, _norm, rotm, render, composite, mini_surfaces

_PROF = np.array([[0, -238], [62, -234], [120, -214], [162, -178], [188, -132], [196, -88], [190, -46], [174, -8],
                  [150, 22], [118, 42], [64, 52], [0, 56]], float)
_s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(_PROF, axis=0), axis=1))])
_cr = CubicSpline(_s, _PROF[:, 0]); _cy = CubicSpline(_s, _PROF[:, 1])
_sd = np.linspace(0, _s[-1], 400); _YD = _cy(_sd); _RD = np.clip(_cr(_sd), 0, None)
ZF = 0.84; NF = 12; SEG = 2 * math.pi / NF; OFF = (SEG / 2 + math.pi / 2) % SEG

def facet(th):
    d = ((th + OFF) % SEG) - SEG / 2
    return math.cos(SEG / 2) / np.cos(d)

def head_rho(y): return np.interp(y, _YD, _RD)

def front_z(x, y):
    rho = head_rho(y)
    return -ZF * np.sqrt(np.maximum(rho * rho - x * x, 0)) * math.cos(SEG / 2)

def brow_y(x): return -112.0 - 0.30 * np.abs(x)

CY_ = np.array([0.10, 0.85, 1.0]); PU_ = np.array([0.70, 0.30, 1.0]); GO_ = np.array([1.0, 0.78, 0.25])

def mother_surfaces2(t, act, ecol, open_, look, pop=1.0, glowpulse=0.0, roar=0.0, reveal=1.0, lash=None, eyes=1.0):
    """reveal: 0..1 light sweep from bottom to top (intro). eyes: eye intensity independent of the body."""
    lash = lash or {}
    surfs = []
    yline = 330 - 660 * reveal               # visible where y > yline
    def rv(Y): return smoothstep(yline, yline + 70, Y) if reveal < 1 else 1.0
    nu, nv = 192, 110
    s_a = float(np.interp(-178, _YD, _sd)); s_b = float(np.interp(-56, _YD, _sd))
    sv = np.unique(np.round(np.concatenate([np.linspace(0, _s[-1], 80), np.linspace(s_a, s_b, 110)]), 3))
    rho = np.clip(_cr(sv), 0, None); yy = _cy(sv)
    th = np.linspace(0, 2 * math.pi, nu, endpoint=False)
    TH, RH = np.meshgrid(th, rho, indexing='ij')
    YY = np.broadcast_to(yy, TH.shape).copy()
    RHf = RH * facet(TH)
    X = RHf * np.cos(TH); Z = RHf * np.sin(TH) * ZF
    crest = np.exp(-((X / 14.0) ** 2)) * smoothstep(-150, -230, YY)
    YY = YY - 9.0 * crest
    fw = np.clip(-np.sin(TH), 0, 1) ** 0.6
    yb = brow_y(X)
    brow = np.exp(-((YY - yb) / 11.0) ** 2) * fw * (1 - smoothstep(130, 175, np.abs(X)))
    sock = np.exp(-((YY - (yb + 30)) / 16.0) ** 2) * fw * (1 - smoothstep(140, 175, np.abs(X)))
    Z = Z - 24.0 * brow + 7.0 * sock
    br = 1.0 + 0.014 * math.sin(t * 1.6)
    P = np.stack([X * br, YY * (1 + 0.010 * math.sin(t * 1.6 + 0.6)), Z * br], -1)
    ref = np.stack([np.zeros_like(X), YY, np.zeros_like(X)], -1)
    C = np.broadcast_to(np.array([0.030, 0.036, 0.065]), P.shape).copy()
    C *= (0.85 + 0.25 * smoothstep(-250, -60, YY))[..., None]
    E = np.zeros_like(P)
    d = np.abs(((TH + OFF) % SEG) - SEG / 2)
    edge = np.exp(-((SEG / 2 - d) / 0.012) ** 2)
    flow = 0.5 + 0.5 * np.sin(YY * 0.045 - t * 2.6 + TH * 3)
    breathe = 0.55 + 0.45 * (0.5 + 0.5 * math.sin(t * 1.6))
    topw = smoothstep(-240, -180, YY) * (1 - smoothstep(-120, -70, YY))
    side = np.round((TH + OFF) / SEG).astype(int) % 2
    ecolr = np.where(side[..., None] == 0, CY_, PU_)
    E += (edge * topw * (0.25 + 0.75 * flow) * breathe)[..., None] * ecolr * 0.75
    seam = np.exp(-((YY + 196) / 2.5) ** 2)
    E += (seam * 0.55 * breathe)[..., None] * PU_
    visor = np.exp(-((YY - (yb + 10)) / 3.6) ** 2) * fw * (1 - smoothstep(120, 165, np.abs(X)))
    E += visor[..., None] * CY_ * (0.8 + 0.6 * act)
    crestg = crest * np.exp(-((X / 4.0) ** 2))
    E += (crestg * (0.5 + 0.5 * math.sin(t * 3.0)))[..., None] * CY_ * 0.8
    m_ = rv(YY)
    if not np.isscalar(m_): m_ = m_[..., None]
    surfs.append(Surf(P, C * pop * m_, E * pop * m_, True, ref, spec=0.9, metal=1.0))

    # eyes
    ec = np.array(ecol, float) / 255.0
    for sg in (-1, 1):
        ex = sg * 78.0; ey = -86.0
        zf = float(front_z(ex, ey)) - 10.0
        a = 62.0; b = 17.0 * max(0.06, open_)
        Pe, re = ellipsoid((ex, ey, zf), (a, b, 10.0), 48, 22, tilt=-sg * 0.40)
        flick = 0.9 + 0.1 * math.sin(t * 2.4 + sg)
        Ce = np.broadcast_to(ec * 0.35, Pe.shape).copy()
        Ee = np.broadcast_to(ec * 1.5 * flick * open_ * eyes, Pe.shape).copy()
        ct, st = math.cos(-sg * 0.40), math.sin(-sg * 0.40)
        lx = (Pe[..., 0] - ex) * ct + (Pe[..., 1] - ey) * st
        ly = -(Pe[..., 0] - ex) * st + (Pe[..., 1] - ey) * ct
        core = np.exp(-((lx / 34.0) ** 2 + (ly / 7.0) ** 2))
        Ee = Ee + core[..., None] * 0.6 * eyes * open_
        pm = np.exp(-(((lx - look[0] * 20.0) / 6.5) ** 2 + ((ly - look[1] * 4.0) / (14.0 * max(0.2, open_))) ** 2)) * (Pe[..., 2] < zf - 4)
        Ce = Ce * (1 - pm[..., None]) + 0.01 * pm[..., None]
        Ee = Ee * (1 - pm[..., None])
        surfs.append(Surf(Pe, Ce, Ee, True, re, spec=1.2, metal=0.3, bias=40.0))

    # jaw plate with glowing slit (opens on roar)
    nj, nvj = 56, 14
    thj = np.linspace(-math.pi + 0.55, -0.55, nj)
    vj = np.linspace(0, 1, nvj)
    TJ, VJ = np.meshgrid(thj, vj, indexing='ij')
    yj = 26 + 56 * VJ + 18.0 * roar * smoothstep(0.45, 0.62, VJ)
    rj = (132 - 34 * VJ) * facet(TJ)
    Pj = np.stack([rj * np.cos(TJ), yj, rj * np.sin(TJ) * ZF - 6], -1)
    refj = np.stack([np.zeros_like(TJ), yj, np.zeros_like(TJ)], -1)
    Cj = np.broadcast_to(np.array([0.028, 0.034, 0.06]), Pj.shape).copy()
    slit = np.exp(-((VJ - 0.535) / 0.06) ** 2)
    Ej = (slit * (0.35 + 0.35 * glowpulse + 1.6 * roar))[..., None] * (CY_ * (1 - 0.5 * roar) + np.array([1, 1, 1]) * 0.5 * roar)
    Ej += (np.exp(-((VJ - 0.06) / 0.04) ** 2) * 0.35)[..., None] * PU_
    mj = rv(yj)
    if not np.isscalar(mj): mj = mj[..., None]
    surfs.append(Surf(Pj, Cj * pop * mj, Ej * pop * mj, False, refj, spec=1.4, metal=1.0, bias=8.0))

    # tentacles: armoured, segmented, suckers underneath
    phis = [-0.50, -0.17, 0.17, 0.50]
    nseg, sides = 72, 16
    for k in range(8):
        sd = 1 if k < 4 else -1
        phi = phis[k % 4]
        az = phi if sd == 1 else math.pi - phi
        o = np.array([math.cos(az), 0.0, math.sin(az) * 0.9]); o /= np.linalg.norm(o)
        pperp = np.array([-o[2], 0.0, o[0]])
        B = np.array([112.0 * math.cos(az), 34.0, 112.0 * 0.84 * math.sin(az)])
        front = (k % 4 == 0)
        L = (300.0 + 30.0 * math.sin(k * 1.7)) * (1.12 if front else 1.0)
        u = np.linspace(0, 1, nseg)
        lv = lash.get(k, 0.0)
        curl = 2.0 * (1 + 0.10 * math.sin(t * 0.9 + k) + 0.15 * act * math.sin(t * 2.4 + k * 0.7)) * (1 - 0.7 * lv)
        psi = 0.72 - 0.85 * u - curl * u * u - 0.6 * lv * u
        ds = L / (nseg - 1)
        dirs = np.cos(psi)[:, None] * o[None, :] + np.sin(psi)[:, None] * np.array([0.0, 1.0, 0.0])[None, :]
        Cc = B[None, :] + np.concatenate([np.zeros((1, 3)), np.cumsum(dirs[:-1] * ds, axis=0)], 0)
        wph = 2 * math.pi * 1.0 * u - (1.3 + 1.2 * act) * t + k * 1.9
        amp = (24.0 + 18.0 * act) * (1 - 0.6 * lv)
        Cc = Cc + (amp * (u ** 1.2) * np.sin(wph))[:, None] * pperp[None, :]
        Cc[:, 1] += 14.0 * (u ** 1.1) * np.sin(wph * 0.9 + 1.0)
        Tg = _norm(np.gradient(Cc, axis=0))
        n1 = _norm(np.cross(Tg, np.array([0.0, 0.0, 1.0]))); n2 = np.cross(Tg, n1)
        segm = 1 + 0.06 * np.clip(np.cos(u * 2 * math.pi * 13), 0, 1) ** 2
        rad = (5.0 + 33.0 * (1 - u) ** 1.15) * segm * (1.15 if front else 1.0)
        sh = np.linspace(0, 2 * math.pi, sides, endpoint=False)
        offs = (np.cos(sh)[:, None, None] * n1[None, :, :] + np.sin(sh)[:, None, None] * n2[None, :, :])
        Pt = Cc[None, :, :] + rad[None, :, None] * offs
        reft = np.broadcast_to(Cc[None, :, :], Pt.shape).copy()
        gcol = np.array([0.030, 0.040, 0.075]) * (1 - u[None, :, None]) + np.array([0.06, 0.10, 0.24]) * u[None, :, None]
        Ct = np.broadcast_to(gcol, Pt.shape).copy()
        down = np.clip(offs[..., 1], 0, 1)
        spots = (np.cos(u * 2 * math.pi * 13 + math.pi) > 0.55)[None, :] * (down > 0.55)
        Et = np.zeros_like(Pt)
        Et += (spots * (0.45 + 0.35 * math.sin(t * 3 + k)))[..., None] * PU_ * (1 - 0.5 * u[None, :, None])
        ringl = np.exp(-((np.cos(u * 2 * math.pi * 13) - 1) / 0.04) ** 2)[None, :] * (1 - u[None, :]) * 0.12
        Et += ringl[..., None] * CY_
        band = np.clip(1 - np.abs(((u * 5.0 - 2.0 * t + k * 0.37) % 1.0) - 0.5) / 0.08, 0, 1)
        Et += (band * (1 - u) * 0.7)[None, :, None] * CY_ * 0.7
        tip = smoothstep(0.82, 1.0, u)
        Et += (tip * (0.6 + 0.4 * math.sin(t * 4 + k)) + lv * 1.2 * u)[None, :, None] * PU_
        mt = rv(Cc[:, 1])
        if not np.isscalar(mt): mt = mt[None, :, None]
        surfs.append(Surf(Pt, Ct * pop * mt, Et * pop * mt, True, reft, spec=0.55, metal=0.9))
    return surfs

def eye_points():
    return [(sg * 78.0, -86.0, float(front_z(sg * 78.0, -86.0)) - 18.0) for sg in (-1, 1)]

def anchor_points():
    leds = []
    for k in range(6):
        x = (k - 2.5) * 38.0; y = -30.0
        leds.append((x, y, float(front_z(x, y)) - 4.0))
    emb = (0.0, -182.0, float(front_z(0.0, -182.0)) - 2.0)
    return leds, emb

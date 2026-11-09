"""Tiny software 3D renderer (numpy + OpenCV painter's algorithm) for the OCTO AI octopus.
Meshes are parametric grids; shading is per quad (key/rim/fill + spec + fresnel + env + emissive)."""
import math
import numpy as np
import cv2
from scipy.interpolate import CubicSpline


def rotm(yaw, pitch, roll=0.0):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cr, sr = math.cos(roll), math.sin(roll)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return Rz @ Rx @ Ry


def _norm(v):
    return v / (np.linalg.norm(v, axis=-1, keepdims=True) + 1e-9)


def grid_normals(P, wrapu, ref):
    du = np.roll(P, -1, 0) - np.roll(P, 1, 0) if wrapu else np.gradient(P, axis=0)
    dv = np.gradient(P, axis=1)
    n = np.cross(du, dv)
    l = np.linalg.norm(n, axis=2, keepdims=True)
    out = P - ref
    n = np.where(l > 1e-6, n / (l + 1e-12), _norm(out))
    s = np.sign(np.sum(n * out, axis=2, keepdims=True))
    s[s == 0] = 1
    return n * s


class Surf:
    def __init__(self, P, C, E, wrapu, ref, spec=1.0, metal=0.5, bias=0.0):
        self.bias = bias; self.P = P; self.C = C; self.E = E; self.wrapu = wrapu; self.ref = ref
        self.spec = spec; self.metal = metal


LIGHTS = dict(
    l1=_norm(np.array([-0.55, -0.55, -0.62])), c1=np.array([0.80, 0.93, 1.0]),
    l2=_norm(np.array([0.85, -0.25, 0.45])), c2=np.array([0.80, 0.38, 1.0]),
    l3=_norm(np.array([0.60, 0.50, -0.60])), c3=np.array([0.15, 0.85, 1.0]),
    rim=np.array([0.20, 0.85, 1.0]),
)


def render(surfs, R, scale, cx, cy, W_, H_, ss=2.0, D=1500.0, glow=None, glow_off=(0, 0), aoff=(0, 0, 0), rimk=0.42, rimcol=None, under=None, glowk=0.42):
    """Rasterise surfaces into an RGBA uint8 image (W_*H_), origin of the model at (cx, cy) in image px.
    glow: optional half-res uint8 buffer to add emissive quads to (image px + glow_off) / 2."""
    quads_pts = []; quads_col = []; quads_depth = []; em_pts = []; em_col = []
    Rt = R.T
    for s in surfs:
        P, C, E, ref = s.P, s.C, s.E, s.ref
        N = grid_normals(P, s.wrapu, ref)
        if s.wrapu:
            P = np.concatenate([P, P[:1]], 0); C = np.concatenate([C, C[:1]], 0)
            E = np.concatenate([E, E[:1]], 0); N = np.concatenate([N, N[:1]], 0)
        Pc = P @ Rt + np.array(aoff, float)
        Nc = N @ Rt
        z = Pc[..., 2] + D
        k = D / z
        X = (cx + scale * Pc[..., 0] * k) * ss
        Y = (cy + scale * Pc[..., 1] * k) * ss
        pos = np.stack([Pc[..., 0], Pc[..., 1], z], -1)

        def q4(a):
            return (a[:-1, :-1] + a[1:, :-1] + a[1:, 1:] + a[:-1, 1:]) * 0.25
        pq = q4(pos); nq = _norm(q4(Nc)); cq = q4(C); eq = q4(E)
        V = _norm(-pq)
        ndv = np.sum(nq * V, -1)
        keep = ndv > -0.02
        # shading
        L = LIGHTS
        d1 = np.clip(nq @ L['l1'], 0, 1); d2 = np.clip(nq @ L['l2'], 0, 1); d3 = np.clip(nq @ L['l3'], 0, 1)
        h1 = _norm(L['l1'] + V); h2 = _norm(L['l2'] + V)
        sp1 = np.clip(np.sum(nq * h1, -1), 0, 1) ** 44
        sp2 = np.clip(np.sum(nq * h2, -1), 0, 1) ** 26
        fr = (1 - np.clip(ndv, 0, 1)) ** 3
        r = 2 * ndv[..., None] * nq - V
        up = np.clip(-r[..., 1] * 0.5 + 0.5, 0, 1)[..., None]
        env = (np.array([0.35, 0.10, 0.55]) * (1 - up) + np.array([0.10, 0.55, 0.85]) * up)
        col = cq * (0.11 + 1.05 * d1[..., None] * L['c1'] + 1.0 * d2[..., None] * L['c2'] + 0.40 * d3[..., None] * L['c3'])
        col += (sp1[..., None] * L['c1'] * 0.95 + sp2[..., None] * L['c2'] * 0.55) * s.spec
        rc_ = L['rim'] if rimcol is None else np.asarray(rimcol, float)
        col += fr[..., None] * rc_ * rimk + env * (0.04 + 0.26 * fr[..., None]) * s.metal
        if under is not None:
            col += np.clip(nq[..., 1], 0, 1)[..., None] * np.asarray(under, float) * 0.55
        col += eq
        col = np.clip(col, 0, 1.6)
        col = np.clip(col / (1 + 0.18 * col), 0, 1) ** 0.92
        col8 = (col * 255).astype(np.uint8)
        pts = np.stack([q4(X) * 0 + 0, ], 0)  # placeholder to keep shapes explicit
        xs = np.stack([X[:-1, :-1], X[1:, :-1], X[1:, 1:], X[:-1, 1:]], -1)
        ys = np.stack([Y[:-1, :-1], Y[1:, :-1], Y[1:, 1:], Y[:-1, 1:]], -1)
        pq4 = np.stack([xs, ys], -1)  # (nu,nv,4,2)
        kk = keep.reshape(-1)
        quads_pts.append((pq4.reshape(-1, 4, 2)[kk]))
        quads_col.append(col8.reshape(-1, 3)[kk])
        quads_depth.append((pq[..., 2] - s.bias).reshape(-1)[kk])
        if glow is not None:
            em = (eq.max(-1) > 0.25).reshape(-1) & kk
            if em.any():
                em_pts.append(pq4.reshape(-1, 4, 2)[em])
                em_col.append(np.clip(eq.reshape(-1, 3)[em] * 255, 0, 255).astype(np.uint8))
    Ws, Hs = int(W_ * ss), int(H_ * ss)
    img = np.zeros((Hs, Ws, 4), np.uint8)
    if quads_pts:
        pts = np.concatenate(quads_pts); col = np.concatenate(quads_col); dep = np.concatenate(quads_depth)
        order = np.argsort(-dep)
        pts = np.round(pts * 4).astype(np.int32)[order]
        colw = np.concatenate([col, np.full((len(col), 1), 255, np.uint8)], 1)[order].tolist()
        for q in range(len(pts)):
            cv2.fillConvexPoly(img, pts[q], colw[q], cv2.LINE_8, 2)
    out = cv2.resize(img, (W_, H_), interpolation=cv2.INTER_AREA) if ss != 1 else img
    if glow is not None and em_pts:
        ep = np.concatenate(em_pts); ec = np.concatenate(em_col)
        ep = (ep / ss + np.array(glow_off, float)) / 2.0
        ep = np.round(ep * 4).astype(np.int32)
        for q in range(len(ep)):
            cv2.fillConvexPoly(glow, ep[q], tuple(int(v) for v in (ec[q] * glowk)), cv2.LINE_8, 2)
    return out


def composite(cvf, rgba, x0, y0, gain=1.0):
    h, w = rgba.shape[:2]
    X0 = max(0, x0); Y0 = max(0, y0); X1 = min(cvf.shape[1], x0 + w); Y1 = min(cvf.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    sub = rgba[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0]
    a = (sub[..., 3:4].astype(np.float32) / 255.0) * gain
    roi = cvf[Y0:Y1, X0:X1]
    roi[:] = (roi * (1 - a) + sub[..., :3].astype(np.float32) * a).astype(np.uint8)


# ---------------------------------------------------------------- primitives
def ellipsoid(c, ax, nu=20, nv=10, tilt=0.0, wrap=True):
    th = np.linspace(0, 2 * math.pi, nu, endpoint=False)
    ph = np.linspace(0.0, math.pi, nv + 1)
    TH, PH = np.meshgrid(th, ph, indexing='ij')
    x = ax[0] * np.sin(PH) * np.cos(TH); y = ax[1] * np.sin(PH) * np.sin(TH); z = ax[2] * np.cos(PH)
    ct, st = math.cos(tilt), math.sin(tilt)
    xr = x * ct - y * st; yr = x * st + y * ct
    P = np.stack([xr + c[0], yr + c[1], -z + c[2]], -1)  # +z axis toward viewer (negative z)
    ref = np.broadcast_to(np.array(c, float), P.shape).copy()
    return P, ref


def smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a + 1e-9), 0, 1)
    return t * t * (3 - 2 * t)


# ---------------------------------------------------------------- mother octopus
_PROF = np.array([[0, -250], [46, -246], [96, -230], [138, -198], [164, -152], [178, -102], [180, -56], [170, -12],
                  [148, 22], [112, 44], [60, 54], [0, 58]], float)
_s = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(_PROF, axis=0), axis=1))])
_csp_r = CubicSpline(_s, _PROF[:, 0]); _csp_y = CubicSpline(_s, _PROF[:, 1])
_ss_dense = np.linspace(0, _s[-1], 400)
_YD = _csp_y(_ss_dense); _RD = np.clip(_csp_r(_ss_dense), 0, None)
ZF = 0.84


def head_rho(y):
    return np.interp(y, _YD, _RD)


def head_front_z(x, y):
    rho = head_rho(y)
    zz = -ZF * np.sqrt(np.maximum(rho * rho - x * x, 0))
    fw = 1.0
    indent = 8.0 * smoothstep(-140, -105, y) * (1 - smoothstep(-75, -35, y))
    return zz + indent * fw


def mother_surfaces(t, act, ecol, open_, look, pop=1.0, glowpulse=0.0):
    """act: 0..1 activity (tentacle energy). ecol: eye RGB 0..255. look: (lx, ly) -1..1 pupil offset."""
    surfs = []
    nu, nv = 168, 104
    sv = np.linspace(0, _s[-1], nv)
    rho = np.clip(_csp_r(sv), 0, None); yy = _csp_y(sv)
    th = np.linspace(0, 2 * math.pi, nu, endpoint=False)
    TH, RH = np.meshgrid(th, rho, indexing='ij')
    YY = np.broadcast_to(yy, TH.shape).copy()
    # armour grooves (10 plates) + ribs
    ph = (TH * 5 / math.pi) % 1.0
    groove = np.exp(-((ph - 0.5) / 0.045) ** 2)
    topw = smoothstep(-235, -170, YY) * (1 - smoothstep(-20, 30, YY))
    RHm = RH * (1 - 0.016 * groove * topw)
    X = RHm * np.cos(TH); Z = RHm * np.sin(TH) * ZF
    # crest fin on top (front-back ridge)
    crest = np.exp(-((X / 70.0) ** 2)) * smoothstep(-160, -235, YY)
    YY = YY - 11.0 * crest
    # visor indent on the front
    fw = np.clip(-np.sin(TH), 0, 1) ** 0.5
    indent = 8.0 * smoothstep(-140, -105, YY) * (1 - smoothstep(-75, -35, YY)) * fw
    brow = np.exp(-((YY + 142) / 13.0) ** 2) * fw
    Z = Z + indent - 14.0 * brow
    breath = 1.0 + 0.016 * math.sin(t * 2.2)
    P = np.stack([X * breath, YY * (1 + 0.012 * math.sin(t * 2.2 + 0.6)), Z * breath], -1)
    ref = np.stack([np.zeros_like(X), YY, np.zeros_like(X)], -1)
    base = np.array([0.035, 0.055, 0.13])
    C = np.broadcast_to(base, P.shape).copy()
    # plate colour variation
    C *= (0.85 + 0.30 * (np.cos(TH * 5) * 0.5 + 0.5))[..., None] * (0.9 + 0.2 * smoothstep(-250, -50, YY))[..., None]
    E = np.zeros_like(P)
    flow = 0.5 + 0.5 * np.sin(YY * 0.05 - t * 3.0 + TH * 2)
    cy_ = np.array([0.10, 0.85, 1.0]); pu_ = np.array([0.65, 0.30, 1.0])
    bnd = np.round(TH * 5 / math.pi).astype(int) % 10
    bs = np.where((bnd == 7) | (bnd == 8), 1.0, np.where((bnd == 6) | (bnd == 9), 0.45, 0.10))
    E += (groove * topw * bs * (0.35 + 0.65 * flow))[..., None] * cy_ * 0.9
    ring = np.exp(-((YY - 40) / 5.0) ** 2) * (0.4 + 0.6 * (0.5 + 0.5 * math.sin(t * 3.2)))
    E += ring[..., None] * pu_ * 0.9
    visor = np.exp(-((YY + 122) / 3.0) ** 2) * fw
    E += visor[..., None] * cy_ * 0.55
    E *= pop
    surfs.append(Surf(P * 1.0, C * pop, E, True, ref, spec=1.0, metal=0.8))

    # eyes
    for sg in (-1, 1):
        ex = sg * 80.0; ey = -92.0
        zf = float(head_front_z(ex, ey)) - 6.0
        a = 60.0; b = 21.0 * max(0.05, open_)
        Pe, re = ellipsoid((ex, ey, zf), (a, b, 10.0), 44, 22, tilt=-sg * 0.30)
        ec = np.array(ecol, float) / 255.0
        flick = 0.88 + 0.12 * math.sin(t * 2.4 + sg)
        Ce = np.broadcast_to(ec * 0.35, Pe.shape).copy()
        Ee = np.broadcast_to(ec * 1.15 * flick * open_ * pop, Pe.shape).copy()
        # painted slit pupil (front-facing vertices only), follows `look`
        ct, st = math.cos(-sg * 0.30), math.sin(-sg * 0.30)
        lx = (Pe[..., 0] - ex) * ct + (Pe[..., 1] - ey) * st
        ly = -(Pe[..., 0] - ex) * st + (Pe[..., 1] - ey) * ct
        pm = np.exp(-(((lx - look[0] * 20.0) / 8.0) ** 2 + ((ly - look[1] * 4.0) / (17.0 * max(0.2, open_))) ** 2)) * (Pe[..., 2] < zf - 4)
        Ce = Ce * (1 - pm[..., None]) + 0.01 * pm[..., None]
        Ee = Ee * (1 - pm[..., None])
        surfs.append(Surf(Pe, Ce, Ee, True, re, spec=1.2, metal=0.3, bias=40.0))

    # siphon / mouth
    nm, nvm = 20, 6
    thm = np.linspace(0, 2 * math.pi, nm, endpoint=False)
    hv = np.linspace(0, 1, nvm)
    TM, HV = np.meshgrid(thm, hv, indexing='ij')
    rr = 26 - 14 * HV
    Pm = np.stack([rr * np.cos(TM), 64 + 44 * HV, -20 + rr * np.sin(TM) * 0.9 - 10 * HV], -1)
    refm = np.stack([np.zeros_like(TM), 64 + 44 * HV, np.full_like(TM, -20.0)], -1)
    Cm = np.full(Pm.shape, 0.03)
    Em = np.zeros_like(Pm)
    Em[:, -1, :] = np.array([0.1, 0.8, 1.0]) * (0.5 + 0.5 * glowpulse + 0.3 * act)
    surfs.append(Surf(Pm, Cm, Em, True, refm, spec=0.8, metal=0.6))

    # tentacles (8), wings splayed to the sides
    phis = [-0.50, -0.17, 0.17, 0.50]
    nseg, sides = 64, 16
    for k in range(8):
        side = 1 if k < 4 else -1
        phi = phis[k % 4]
        az = phi if side == 1 else math.pi - phi
        o = np.array([math.cos(az), 0.0, math.sin(az) * 0.9]); o /= np.linalg.norm(o)
        pperp = np.array([-o[2], 0.0, o[0]])
        B = np.array([105.0 * math.cos(az), 38.0, 105.0 * 0.84 * math.sin(az)])
        L = 290.0 + 30.0 * math.sin(k * 1.7)
        u = np.linspace(0, 1, nseg)
        curl = 2.0 * (1 + 0.10 * math.sin(t * 1.1 + k) + 0.18 * act * math.sin(t * 3.0 + k * 0.7))
        psi = 0.72 - 0.85 * u - curl * u * u
        ds = L / (nseg - 1)
        dirs = np.cos(psi)[:, None] * o[None, :] + np.sin(psi)[:, None] * np.array([0.0, 1.0, 0.0])[None, :]
        Cc = B[None, :] + np.concatenate([np.zeros((1, 3)), np.cumsum(dirs[:-1] * ds, axis=0)], 0)
        wph = 2 * math.pi * 1.1 * u - (1.7 + 1.4 * act) * t + k * 1.9
        amp = 26.0 + 22.0 * act
        Cc = Cc + (amp * (u ** 1.2) * np.sin(wph))[:, None] * pperp[None, :]
        Cc[:, 1] += 16.0 * (u ** 1.1) * np.sin(wph * 0.9 + 1.0)
        Tg = np.gradient(Cc, axis=0); Tg = _norm(Tg)
        ref0 = np.array([0.0, 0.0, 1.0])
        n1 = _norm(np.cross(Tg, ref0)); n2 = np.cross(Tg, n1)
        rad = 4.0 + 30.0 * (1 - u) ** 1.15
        sh = np.linspace(0, 2 * math.pi, sides, endpoint=False)
        Pt = (Cc[None, :, :] + rad[None, :, None] * (np.cos(sh)[:, None, None] * n1[None, :, :] + np.sin(sh)[:, None, None] * n2[None, :, :]))
        reft = np.broadcast_to(Cc[None, :, :], Pt.shape).copy()
        gcol = np.array([0.050, 0.080, 0.19]) * (1 - u[None, :, None]) + np.array([0.09, 0.20, 0.48]) * u[None, :, None]
        Ct = np.broadcast_to(gcol, Pt.shape).copy()
        band = np.clip(1 - np.abs(((u * 6.0 - 2.4 * t + k * 0.37) % 1.0) - 0.5) / 0.09, 0, 1)
        tip = smoothstep(0.80, 1.0, u)
        Et = np.zeros_like(Pt)
        Et += (band * (1 - u) * 0.9)[None, :, None] * cy_[None, None, :] * 0.8
        Et += (tip * (0.6 + 0.4 * math.sin(t * 4 + k)))[None, :, None] * pu_[None, None, :]
        Et *= pop
        surfs.append(Surf(Pt, Ct * pop, Et, True, reft, spec=1.0, metal=0.7))
    return surfs


def mother_anchor_points(t):
    """3D points (model space) for LED belt and forehead emblem."""
    leds = []
    for k in range(6):
        x = (k - 2.5) * 40.0; y = -26.0
        leds.append((x, y, float(head_front_z(x, y)) - 4.0))
    emb = (0.0, -178.0, float(head_front_z(0.0, -178.0)) - 2.0)
    return leds, emb


# ---------------------------------------------------------------- mini octopus (local units of the 2D sprite)
_MP = np.array([[0, -26], [13, -24], [25, -16], [32, -4], [33, 8], [30, 17], [18, 21], [0, 23]], float)
_ms = np.concatenate([[0], np.cumsum(np.linalg.norm(np.diff(_MP, axis=0), axis=1))])
_mr = CubicSpline(_ms, _MP[:, 0]); _my = CubicSpline(_ms, _MP[:, 1])


def mini_surfaces(t, i, col, lv, speed=0.0):
    c = np.array(col, float) / 255.0
    surfs = []
    nu, nv = 56, 26
    sv = np.linspace(0, _ms[-1], nv)
    rho = np.clip(_mr(sv), 0, None); yy = _my(sv)
    th = np.linspace(0, 2 * math.pi, nu, endpoint=False)
    TH, RH = np.meshgrid(th, rho, indexing='ij')
    YY = np.broadcast_to(yy, TH.shape).copy()
    X = RH * np.cos(TH); Z = RH * np.sin(TH) * 0.82
    YY = YY - 7.0 * np.exp(-((X / 9.0) ** 2)) * smoothstep(-6, -24, YY)
    P = np.stack([X, YY, Z], -1)
    ref = np.stack([np.zeros_like(X), YY, np.zeros_like(X)], -1)
    base = np.array([0.045, 0.07, 0.17]) * (1 - 0.30 - 0.2 * lv) + c * (0.30 + 0.2 * lv) * 0.55
    C = np.broadcast_to(base, P.shape).copy()
    E = np.zeros_like(P)
    groove = np.exp(-(((TH * 3 / math.pi) % 1.0 - 0.5) / 0.06) ** 2)
    E += (groove * smoothstep(-24, -8, YY) * (0.3 + 0.7 * lv))[..., None] * c * 0.8
    surfs.append(Surf(P, C, E, True, ref, spec=1.0, metal=0.6))
    ecl = np.minimum(c * 0.45 + 0.6, 1.0)
    for sg in (-1, 1):
        ex, ey = sg * 14.0, 4.5
        zf = -0.82 * math.sqrt(max(rho_at(ey) ** 2 - ex * ex, 0)) - 1.5
        Pe, re = ellipsoid((ex, ey, zf), (12.0, 5.5, 4.0), 20, 10, tilt=-sg * 0.28)
        surfs.append(Surf(Pe, np.broadcast_to(ecl * 0.4, Pe.shape).copy(),
                          np.broadcast_to(ecl * (0.9 + 0.5 * lv), Pe.shape).copy(), True, re, spec=1.0, metal=0.2))
    nseg, sides = 16, 8
    for a in range(6):
        xb = -22 + a * 8.8
        u = np.linspace(0, 1, nseg)
        sway = np.sin(t * 5.5 + i * 1.7 + a * 1.1 - u * 4.5) * (5 + 7 * lv) * u
        xx = xb * (1 + 0.9 * u + 0.5 * lv * u) + sway
        yy2 = 16 + 46 * u * (1 - 0.25 * lv) + (abs(xb) / 22) * 8 * u
        zz = 6.0 * np.sin(t * 4.0 + a * 1.3 - u * 3.0) * u + (a - 2.5) * 1.2
        Cc = np.stack([xx, yy2, zz], -1)
        Tg = _norm(np.gradient(Cc, axis=0)); ref0 = np.array([0.0, 0.0, 1.0])
        n1 = _norm(np.cross(Tg, ref0)); n2 = np.cross(Tg, n1)
        rad = 1.6 + 5.4 * (1 - u) ** 1.1
        sh = np.linspace(0, 2 * math.pi, sides, endpoint=False)
        Pt = Cc[None] + rad[None, :, None] * (np.cos(sh)[:, None, None] * n1[None] + np.sin(sh)[:, None, None] * n2[None])
        reft = np.broadcast_to(Cc[None], Pt.shape).copy()
        Ct = np.broadcast_to(np.array([0.05, 0.08, 0.18]) * (1 - u[None, :, None]) + c * 0.45 * u[None, :, None], Pt.shape).copy()
        Et = np.zeros_like(Pt)
        Et[:, -2:, :] = c * (0.5 + 0.8 * lv)
        surfs.append(Surf(Pt, Ct, Et, True, reft, spec=0.9, metal=0.5))
    return surfs


def rho_at(y):
    return float(np.interp(y, _my(np.linspace(0, _ms[-1], 100)), np.clip(_mr(np.linspace(0, _ms[-1], 100)), 0, None)))

"""OCTO AI logo: hex emblem with a neon octopus glyph + gradient wordmark. Pure numpy/OpenCV/PIL."""
import math
import numpy as np
import cv2
from PIL import Image, ImageDraw
import core_o as core

S = 1024
_cache = {}


def _bez(p0, p1, p2, p3, n=60):
    t = np.linspace(0, 1, n)[:, None]
    p0, p1, p2, p3 = [np.array(p, float) for p in (p0, p1, p2, p3)]
    return (1 - t) ** 3 * p0 + 3 * (1 - t) ** 2 * t * p1 + 3 * (1 - t) * t ** 2 * p2 + t ** 3 * p3


def _lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def _grad(h, w, stops):
    y = np.linspace(0, 1, h)[:, None]
    out = np.zeros((h, w, 3), np.float32)
    for k in range(len(stops) - 1):
        (y0, c0), (y1, c1) = stops[k], stops[k + 1]
        m = ((y >= y0) & (y <= y1)).astype(np.float32)
        tt = np.clip((y - y0) / (y1 - y0 + 1e-9), 0, 1)
        for c in range(3):
            out[..., c] += (m * (c0[c] + (c1[c] - c0[c]) * tt))
    return out


def emblem():
    if 'emb' in _cache: return _cache['emb']
    ss = 1  # draw straight at 1024 and area-downscale on use
    img = np.zeros((S, S, 4), np.float32)
    cx = cy = S / 2
    R = 470
    hexp = np.array([[cx + R * math.cos(math.radians(-90 + 60 * k)), cy + R * math.sin(math.radians(-90 + 60 * k))] for k in range(6)], np.int32)
    # hex plate
    plate = np.zeros((S, S), np.uint8)
    cv2.fillPoly(plate, [hexp], 255, cv2.LINE_AA)
    pg = _grad(S, S, [(0, (18, 26, 62)), (0.5, (8, 12, 34)), (1, (26, 12, 60))])
    pa = plate.astype(np.float32) / 255.0 * 0.96
    img[..., :3] = pg; img[..., 3] = pa
    # bevelled rings (gradient stroke cyan -> purple around the hex)
    ring = np.zeros((S, S), np.uint8)
    cv2.polylines(ring, [hexp], True, 255, 26, cv2.LINE_AA)
    ring2 = np.zeros((S, S), np.uint8)
    hex2 = np.array([[cx + (R - 46) * math.cos(math.radians(-90 + 60 * k)), cy + (R - 46) * math.sin(math.radians(-90 + 60 * k))] for k in range(6)], np.int32)
    cv2.polylines(ring2, [hex2], True, 255, 7, cv2.LINE_AA)
    yy, xx = np.mgrid[0:S, 0:S].astype(np.float32)
    ang = (np.arctan2(yy - cy, xx - cx) + math.pi) / (2 * math.pi)
    gc = np.stack([40 + 150 * np.abs(np.sin(ang * math.pi)), 225 - 150 * np.abs(np.sin(ang * math.pi)), 255 + 0 * ang], -1)
    for mk, al in ((ring, 1.0), (ring2, 0.7)):
        a = (mk.astype(np.float32) / 255.0 * al)[..., None]
        img[..., :3] = img[..., :3] * (1 - a) + gc * a
        img[..., 3:4] = np.maximum(img[..., 3:4], a)
    # inner highlight on the top edge of the ring (bevel)
    hl = np.zeros((S, S), np.uint8)
    cv2.polylines(hl, [hexp[[4, 5, 0, 1]]], False, 255, 6, cv2.LINE_AA)
    a = (hl.astype(np.float32) / 255.0 * 0.6)[..., None]
    img[..., :3] = img[..., :3] * (1 - a) + 255 * a

    # octopus glyph mask
    g = np.zeros((S, S), np.uint8)
    dome = [[cx + 175 * math.cos(th), 470 + 165 * math.sin(th)] for th in np.linspace(math.pi, 2 * math.pi, 60)]
    dome += [[cx + 150, 520], [cx - 150, 520]]
    cv2.fillPoly(g, [np.array(dome, np.int32)], 255, cv2.LINE_AA)
    # crest fin
    cv2.fillPoly(g, [np.array([[cx - 38, 330], [cx, 262], [cx + 38, 330]], np.int32)], 255, cv2.LINE_AA)
    for sx, sgn in ((-1, 1), (1, 1)):
        pass
    # tentacles: 3 per side, tapered, curling outward
    xs = [-120, -70, -20]
    for side in (-1, 1):
        for k, x0 in enumerate(xs):
            x0 = x0 * (1 if side == 1 else -1) * -1 if False else side * abs(x0)
            end_x = side * (150 + 70 * (2 - k)) + (0)
            p = _bez((cx + x0, 505), (cx + x0 * 1.1, 640 + 20 * k), (cx + end_x * 0.8, 760 + 25 * k), (cx + end_x, 700 + 25 * (2 - k) if k < 2 else 770))
            n = len(p)
            for i, (px, py) in enumerate(p):
                r = 26 - 20 * (i / (n - 1))
                cv2.circle(g, (int(px), int(py)), max(2, int(r)), 255, -1, cv2.LINE_AA)
    MG_ = cv2.getRotationMatrix2D((512, 540), 0, 1.30); MG_[1, 2] -= 14
    g = cv2.warpAffine(g, MG_, (S, S), flags=cv2.INTER_LINEAR)
    # glyph colour: vertical gradient + rim light
    gm = g.astype(np.float32) / 255.0
    gcol = _grad(S, S, [(0, (255, 255, 255)), (0.28, (110, 240, 255)), (0.55, (60, 150, 255)), (1, (170, 90, 255))])
    er = cv2.erode(g, np.ones((13, 13), np.uint8)).astype(np.float32) / 255.0
    rim = np.clip(gm - er, 0, 1)[..., None]
    body = gcol * 0.60 * (0.55 + 0.45 * er[..., None])
    gl = body + rim * np.array([200, 255, 255], np.float32) * 0.95
    # soft specular on the dome
    sp = np.exp(-(((xx - (cx - 70)) / 60) ** 2 + ((yy - 380) / 36) ** 2))[..., None]
    gl += sp * 120
    a = gm[..., None]
    img[..., :3] = img[..., :3] * (1 - a) + np.clip(gl, 0, 255) * a
    img[..., 3:4] = np.maximum(img[..., 3:4], a)
    # eyes (dark cut with bright slit)
    eyes = np.zeros((S, S, 3), np.float32); em = np.zeros((S, S), np.uint8)
    for sg in (-1, 1):
        pts = np.array([[cx + sg * 118, 438], [cx + sg * 22, 470], [cx + sg * 26, 500], [cx + sg * 104, 488]], np.int32)
        cv2.fillPoly(em, [pts], 255, cv2.LINE_AA)
    em = cv2.warpAffine(em, MG_, (S, S), flags=cv2.INTER_LINEAR)
    ea = (em.astype(np.float32) / 255.0)[..., None]
    img[..., :3] = img[..., :3] * (1 - ea) + np.array([8, 12, 32], np.float32) * ea
    em2 = cv2.erode(em, np.ones((15, 15), np.uint8)).astype(np.float32) / 255.0
    img[..., :3] = img[..., :3] * (1 - em2[..., None]) + np.array([90, 255, 255], np.float32) * em2[..., None]
    out = np.clip(img, 0, 255)
    out = np.dstack([out[..., :3], img[..., 3:4] * 255]).astype(np.uint8)
    _cache['emb'] = out
    return out


def wordmark(size, text='OCTO AI', track=0.10):
    key = ('wm', size, text)
    if key in _cache: return _cache[key]
    f = core.F('b', size)
    adv = [f.getlength(ch) + track * size for ch in text]
    w = int(sum(adv)) + 40; h = int(size * 1.5)
    base = Image.new('L', (w, h), 0); d = ImageDraw.Draw(base)
    x = 20
    for ch, a in zip(text, adv):
        d.text((x, h // 2), ch, font=f, fill=255, anchor='lm'); x += a
    m = np.array(base).astype(np.float32) / 255.0
    gr = _grad(h, w, [(0.15, (255, 255, 255)), (0.5, (170, 240, 255)), (0.85, (90, 180, 255))])
    # "AI" gets the purple end of the gradient
    xs = np.linspace(0, 1, w)[None, :, None]
    ai0 = (sum(adv[:5]) + 20) / w
    pg = np.clip((xs - ai0) / 0.05, 0, 1)
    gr = gr * (1 - pg) + np.array([190, 120, 255], np.float32) * pg * (0.8 + 0.2 * np.linspace(1, 0.6, h)[:, None, None])
    # top-edge bevel highlight
    er = cv2.erode((m * 255).astype(np.uint8), np.ones((3, 3), np.uint8)).astype(np.float32) / 255.0
    rim = np.clip(m - er, 0, 1)[..., None]
    col = np.clip(gr * 0.95 + rim * 90, 0, 255)
    out = np.dstack([col, m * 255]).astype(np.uint8)
    _cache[key] = out
    return out


def _resize(img, w):
    h = int(img.shape[0] * w / img.shape[1])
    return cv2.resize(img, (max(2, int(w)), max(2, h)), interpolation=cv2.INTER_AREA)


def put(cv, rgba, cx, cy, width, alpha=1.0, glow=0.5, shine=None, squeeze=1.0, rot=0.0):
    """Composite an RGBA sprite onto cv.f (+ blurred copy into the glow buffer)."""
    if alpha <= 0.01: return
    im = _resize(rgba, width)
    if squeeze != 1.0:
        im = cv2.resize(im, (max(2, int(im.shape[1] * squeeze)), im.shape[0]), interpolation=cv2.INTER_AREA)
    h, w = im.shape[:2]
    rgb = im[..., :3].astype(np.float32); a = im[..., 3:4].astype(np.float32) / 255.0
    if shine is not None:  # diagonal highlight sweep, shine in 0..1
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        u = (xx + 0.45 * yy) / (w + 0.45 * h)
        band = np.exp(-((u - (shine * 1.5 - 0.25)) / 0.028) ** 2)[..., None]
        rgb = rgb + band * 80 * a
    x0 = int(cx - w / 2); y0 = int(cy - h / 2)
    X0 = max(0, x0); Y0 = max(0, y0); X1 = min(cv.f.shape[1], x0 + w); Y1 = min(cv.f.shape[0], y0 + h)
    if X1 <= X0 or Y1 <= Y0: return
    sa = a[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0] * alpha
    sr = np.clip(rgb[Y0 - y0:Y1 - y0, X0 - x0:X1 - x0], 0, 255)
    roi = cv.f[Y0:Y1, X0:X1]
    roi[:] = (roi * (1 - sa) + sr * sa).astype(np.uint8)
    if glow > 0:
        gx0, gy0, gx1, gy1 = X0 // 2, Y0 // 2, X1 // 2, Y1 // 2
        if gx1 > gx0 and gy1 > gy0:
            sm = cv2.resize((sr * sa).astype(np.float32), (gx1 - gx0, gy1 - gy0), interpolation=cv2.INTER_AREA)
            cv.g[gy0:gy1, gx0:gx1] = np.clip(cv.g[gy0:gy1, gx0:gx1].astype(np.float32) + sm * glow, 0, 255).astype(np.uint8)

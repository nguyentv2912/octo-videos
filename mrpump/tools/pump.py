"""pump.py - Mr PUMP: replay video (9:16, 20s, music) from real Solana wallet trades.

  python3 -I pump.py prep RAW.json DATA.json
  python3 -I pump.py render DATA.json OUT.mp4 --token HODLER --quote HODL --wallet-short "8oaw...hyXDKV" --logo-dir DIR
  python3 -I pump.py render DATA.json OUT.mp4 ... --keys 4.7 8 10.5     (preview PNGs only)

RAW.json: {"sup": float, "trades": [{"side": "BUY"|"SELL", "t": unix, "sol": float, "tok": float, "usd": float,
           "pre": wallet SOL before, "post": wallet SOL after}], "samples": [[unix, price_usd_per_token], ...]}
Needs: Pillow, numpy, ffmpeg, Inter fonts in /usr/share/fonts/opentype/inter. Up to 4 sell groups, any number of buys.
"""
import json, math, sys, subprocess, os, datetime, random, argparse, wave
from functools import lru_cache

MODE = sys.argv[1] if len(sys.argv) > 1 else ''

def prep(raw_path, out_path):
    R = json.load(open(raw_path)); SUP = R['sup']
    trades = sorted(R['trades'], key=lambda x: x['t'])
    buys = [x for x in trades if x['side'] == 'BUY']; sells = [x for x in trades if x['side'] == 'SELL']
    sol_buy = sum(x['usd'] for x in buys) / sum(x['sol'] for x in buys)
    sol_sell = sum(x['usd'] for x in sells) / sum(x['sol'] for x in sells)
    for x in trades:
        x['px'] = x['usd'] / x['tok']; x['mc'] = x['px'] * SUP; x['wb'] = [x['pre'], x['post']]
    pts = {}
    for t, p in sorted(R['samples']): pts[int(t) // 300] = p
    for x in trades: pts[x['t'] // 300] = x['px']          # real trade price wins in its 5-min bucket
    lo, hi = min(pts), max(pts)
    series = []
    for b in range(lo, hi + 1):
        if b in pts: series.append((b, pts[b]))
        else:
            a = max(k for k in pts if k < b); c = min(k for k in pts if k > b)
            series.append((b, pts[a] + (pts[c] - pts[a]) * (b - a) / (c - a)))
    m5 = []; prev = None
    for b, v in series:
        o = prev if prev is not None else v
        m5.append(dict(t=b * 300, o=o, h=max(o, v), l=min(o, v), c=v)); prev = v
    json.dump(dict(trades=trades, m5=m5, SUP=SUP, SOL_BUY=sol_buy, SOL_SELL=sol_sell), open(out_path, 'w'))
    print('data ok: %d buys, %d sells, %d bars' % (len(buys), len(sells), len(m5)))

if MODE == 'prep':
    prep(sys.argv[2], sys.argv[3]); sys.exit(0)
assert MODE == 'render', 'usage: pump.py prep|render ...'
ap = argparse.ArgumentParser()
ap.add_argument('mode'); ap.add_argument('data'); ap.add_argument('out')
ap.add_argument('--token', default='TOKEN'); ap.add_argument('--quote', default='SOL')
ap.add_argument('--wallet-short', default='wallet'); ap.add_argument('--logo-dir', default='logo')
ap.add_argument('--trending', default=None); ap.add_argument('--keys', nargs='*', type=float, default=[])
ap.add_argument('--no-audio', action='store_true'); ap.add_argument('--keydir', default='.')
ARGS = ap.parse_args()
TOKEN, QUOTE, WSHORT = ARGS.token, ARGS.quote, ARGS.wallet_short
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

W, H, FPS, DUR = 1080, 1920, 30, 20.0
OUT = ARGS.out
KEY = ARGS.keys
LG = ARGS.logo_dir.rstrip('/') + '/'

D = json.load(open(ARGS.data))
trades = D['trades']
M15 = [dict(t=c['t'], o=c['o'], h=c['h'], l=c['l'], c=c['c']) for c in D['m5']]
M1 = []
buys = [t for t in trades if t['side'] == 'BUY']
sells = [t for t in trades if t['side'] == 'SELL']
SUP = D['SUP']; SOL_BUY, SOL_SELL = D['SOL_BUY'], D['SOL_SELL']
INVESTED = sum(t['sol'] for t in buys); REALIZED = sum(t['sol'] for t in sells)
TOK = sum(t['tok'] for t in buys)
ENTRY_PX = sum(t['usd'] for t in buys) / TOK
SOLD_TOK = sum(t['tok'] for t in sells)
AVG_SELL_PX = sum(t['usd'] for t in sells) / SOLD_TOK
PNL_SOL = REALIZED - INVESTED
ROI = PNL_SOL / INVESTED * 100
MULT = REALIZED / INVESTED

BG = (7, 9, 13); PANEL = (16, 20, 27); LINE = (34, 41, 52)
MINT = (52, 232, 160); RED = (255, 84, 98); TXT = (240, 244, 248); DIM = (126, 137, 152); GOLD = (255, 200, 80)
CYAN = (60, 220, 255); PURP = (170, 90, 255)
F = '/usr/share/fonts/opentype/inter/Inter-%s.otf'
@lru_cache(maxsize=None)
def font(w, s):
    p = '/usr/share/fonts/opentype/inter/InterDisplay-%s.otf' % w if s >= 40 else F % w
    if not os.path.exists(p): p = F % w
    return ImageFont.truetype(p, s)
_o_text = ImageDraw.ImageDraw.text; _o_bbox = ImageDraw.ImageDraw.textbbox
def _text(self, xy, text, *a, **kw):
    kw.setdefault('features', ['tnum', 'kern']); return _o_text(self, xy, text, *a, **kw)
def _bbox(self, xy, text, *a, **kw):
    kw.setdefault('features', ['tnum', 'kern']); return _o_bbox(self, xy, text, *a, **kw)
ImageDraw.ImageDraw.text = _text; ImageDraw.ImageDraw.textbbox = _bbox
f_logo = font('ExtraBold', 38); f_big = font('ExtraBold', 104); f_h1 = font('Bold', 36)
f_h2 = font('SemiBold', 30); f_sm = font('Medium', 25); f_xs = font('Medium', 21)
f_num = font('Bold', 50); f_chip = font('Bold', 29); f_mark = font('ExtraBold', 20)
f_tile = font('Bold', 46)

def ease(x): x = max(0, min(1, x)); return 1 - (1 - x) ** 3
def eio(x): x = max(0, min(1, x)); return 3 * x * x - 2 * x ** 3
def lerp(a, b, k): return a + (b - a) * k
def lerpc(a, b, k): return tuple(int(lerp(a[i], b[i], k)) for i in range(3))
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))

# ---------------- timeline ----------------
HOME_END = 1.45
TAP_MIHAO = 2.0
PUSH0, PUSH1 = 2.45, 2.85
LINE0, LINE1 = 2.7, 3.2
TAP_BUY = 3.35
CH0, CH1 = 3.9, 4.1
RW0, RW1 = 3.55, 3.95
def snap(x): return 0.2 + 0.5 * math.ceil((x - 0.2) / 0.5 - 1e-9)     # 120 BPM grid
NB, NS = len(buys), len(sells)
BUY_T = [snap(4.7 + 0.5 * i) for i in range(NB)]
B_START = BUY_T[-1] + 1.0
NG = min(NS, 4)
_q, _r = divmod(NS, NG)
GROUPS = []; _i = 0
for _g in range(NG):
    _n = _q + (1 if _g < _r else 0); GROUPS.append(list(range(_i, _i + _n))); _i += _n
FS = snap(B_START + (4.5 if NB == 1 else 3.5))
GAP = 0.0 if NG == 1 else max(1.0, min(2.5, math.floor((13.8 - FS) / (NG - 1) / 0.5) * 0.5))
G_T = [FS + GAP * g for g in range(NG)]
SUM_T = G_T[-1] + 2.5
B_END = FS - 1.0
DIP0, DIP1 = 99.0, 99.0
SELL_T = [0.0] * NS
for _g, _ix in enumerate(GROUPS):
    for _i in _ix: SELL_T[_i] = G_T[_g]
T_BUY = buys[0]['t']; S0 = sells[0]['t']
_segs = []
for _i in range(1, NB): _segs.append((BUY_T[_i] - 0.4, BUY_T[_i], buys[_i - 1]['t'], buys[_i]['t'], False))
_segs.append((B_START, G_T[0], buys[-1]['t'], sells[GROUPS[0][0]]['t'], True))
for _g in range(NG - 1):
    _segs.append((G_T[_g] + min(0.5, GAP * 0.3), G_T[_g + 1], sells[GROUPS[_g][0]]['t'], sells[GROUPS[_g + 1][0]]['t'], True))
def mt15(t):
    if t < BUY_T[0]: return lerp(T_BUY - 1500, T_BUY, clamp((t - 3.9) / (BUY_T[0] - 3.9)))
    m = T_BUY
    for t0, t1, m0, m1, e in _segs:
        if t >= t1: m = m1
        elif t > t0:
            k = (t - t0) / (t1 - t0); return lerp(m0, m1, eio(k) if e else k)
        else: break
    return m
mt1 = mt15
events = [(BUY_T[i], buys[i]) for i in range(NB)] + [(SELL_T[i], sells[i]) for i in range(NS)]
events.sort(key=lambda e: e[0])
clusters = []
for _g, _ix in enumerate(GROUPS):
    mem = [sells[i] for i in _ix]
    sol = sum(m['sol'] for m in mem); tok = sum(m['tok'] for m in mem); usd = sum(m['usd'] for m in mem)
    clusters.append(dict(side='SELL', k=_g + 1, tt=G_T[_g], n=len(_ix), sol=sol, tok=tok, mc=usd / tok * SUP, px=usd / tok, t=mem[0]['t'], wb=(mem[0]['wb'][0], mem[-1]['wb'][1])))
for _i, _b in enumerate(buys): _b['k'] = _i + 1
events2 = [(BUY_T[i], buys[i]) for i in range(NB)] + [(c['tt'], c) for c in clusters]
events2.sort(key=lambda e: e[0])

def held_at(t):
    h = 0; inv = 0; rea = 0; last = None
    for tt, tr in events:
        if t >= tt:
            if tr['side'] == 'BUY': h += tr['tok']; inv += tr['sol']
            else: h -= tr['tok']; rea += tr['sol']
            last = tr
    return h, inv, rea, last

def view_of(t): return '15m'

def visible(t):
    tm = mt15(t)
    out = []
    for c in M15:
        if c['t'] > tm: break
        if c['t'] + 300 > tm:
            f = (tm - c['t']) / 300.0
            c = dict(c); c['c'] = c['o'] + (c['c'] - c['o']) * f
            c['h'] = max(c['o'], c['c']); c['l'] = min(c['o'], c['c'])
        out.append(c)
    return out, 300

NF = int(DUR * FPS)
RANGE = []
lo_s = hi_s = None
prev_view = None
for f in range(NF):
    t = f / FPS
    vis, step = visible(t)
    v = view_of(t)
    if vis:
        lo = min(c['l'] for c in vis); hi = max(c['h'] for c in vis)
    else:
        lo, hi = ENTRY_PX * 0.8, ENTRY_PX * 1.2
    for tt, tr in events:
        if t >= tt:
            lo = min(lo, tr['px']); hi = max(hi, tr['px'])
    tl = math.log(lo) - 0.10; th = math.log(hi) + 0.14
    if lo_s is None or v != prev_view:
        lo_s, hi_s = tl, th
    else:
        k = 0.16
        lo_s += (tl - lo_s) * k; hi_s += (th - hi_s) * k
    RANGE.append((lo_s, hi_s)); prev_view = v

# ---------------- helpers ----------------
def rr(d, b, r, fill, outline=None, w=2): d.rounded_rectangle(b, r, fill=fill, outline=outline, width=w)

def fmt_usd(v):
    if v >= 1e6: return '$%.2fM' % (v / 1e6)
    if v >= 1e3: return '$%.1fK' % (v / 1e3)
    return '$%.0f' % v
def fmt_tok(v): return '%.2fM' % (v / 1e6) if v >= 1e6 else '%.1fK' % (v / 1e3)

def elapsed(sec):
    sec = int(max(0, sec)); dd = sec // 86400; hh = sec % 86400 // 3600; mm = sec % 3600 // 60
    if dd: return '%dd %02dh' % (dd, hh)
    if hh: return '%dh %02dm' % (hh, mm)
    return '%dm' % mm

def sized(path, s):
    im = Image.open(path).convert('RGBA')
    return im.resize((s, s), Image.LANCZOS)
def _logo(name, fallback_text):
    p = LG + name
    if os.path.exists(p): return Image.open(p).convert('RGBA')
    S = 512; g = Image.new('RGB', (S, S)); px = g.load()
    for y in range(S):
        for x in range(S): px[x, y] = lerpc((20, 60, 40), (52, 232, 160), (x + y) / (2.0 * S))
    m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, S - 1, S - 1), 110, fill=255)
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); im.paste(g, (0, 0), m)
    ImageDraw.Draw(im).text((S / 2, S / 2), fallback_text, font=font('ExtraBold', 150), fill=(255, 255, 255), anchor='mm')
    return im
ICON_FULL = _logo('mrpump_app_icon.png', 'PUMP')
ICON_SM = _logo('mrpump_icon_small.png', 'PUMP')
HEAD = _logo('mrpump_avatar_head.png', 'MR')
def make_avatar(S=512):
    g = Image.new('RGB', (S, S)); px = g.load()
    for y in range(S):
        for x in range(S): px[x, y] = lerpc((30, 190, 255), (150, 70, 255), (x + y) / (2.0 * S))
    m = Image.new('L', (S, S), 0); ImageDraw.Draw(m).ellipse((0, 0, S - 1, S - 1), fill=255)
    im = Image.new('RGBA', (S, S), (0, 0, 0, 0)); im.paste(g, (0, 0), m)
    d = ImageDraw.Draw(im)
    d.ellipse((8, 8, S - 9, S - 9), outline=(255, 255, 255, 255), width=10)
    pts = [(.30, .30), (.70, .30), (.84, .45), (.50, .80), (.16, .45)]
    P = [(x * S, y * S) for x, y in pts]
    d.polygon(P, fill=(235, 250, 255, 250))
    for a, b in (((.16, .45), (.84, .45)), ((.30, .30), (.40, .45)), ((.70, .30), (.60, .45)), ((.40, .45), (.50, .80)), ((.60, .45), (.50, .80)), ((.50, .30), (.40, .45)), ((.50, .30), (.60, .45))):
        d.line([(a[0] * S, a[1] * S), (b[0] * S, b[1] * S)], fill=(60, 120, 230, 255), width=5)
    return im
CAT = make_avatar()
@lru_cache(maxsize=None)
def img_s(name, s):
    return {'full': ICON_FULL, 'sm': ICON_SM, 'head': HEAD, 'cat': CAT}[name].resize((s, s), Image.LANCZOS)
def put(img, name, s, x, y, a=1.0):
    im = img_s(name, int(s))
    if a < 1:
        im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * a)))
    img.paste(im, (int(x), int(y)), im)

SX = 1080 / 1188.0; SY = 1920 / 2576.0
def sx(v): return v * SX
def sy(v): return v * SY

def status_bar(d, col=TXT):
    d.text((90, 64), '9:41', font=font('Bold', 40), fill=col, anchor='lm')
    for i in range(4):
        h = 10 + i * 7
        d.rounded_rectangle((780 + i * 15, 84 - h, 790 + i * 15, 84), 2, fill=col if i < 3 else col[:3] + (90,) if len(col) == 3 else col)
    d.arc((850, 54, 906, 100), 215, 325, fill=col, width=5)
    d.arc((862, 68, 894, 100), 215, 325, fill=col, width=5)
    d.ellipse((874, 82, 882, 90), fill=col)
    d.rounded_rectangle((930, 52, 1010, 84), 10, outline=col, width=3)
    d.rounded_rectangle((935, 57, 1003, 79), 6, fill=col)

def finger(d, x, y, rad=56, a=1.0):
    d.ellipse((x - rad, y - rad, x + rad, y + rad), fill=(255, 255, 255, int(90 * a)), outline=(255, 255, 255, int(210 * a)), width=3)

def glow_text(img, xy, text, fnt, fill, glow, anchor='la', blur=10, spread=1.0):
    pad = 60
    bb = ImageDraw.Draw(img).textbbox(xy, text, font=fnt, anchor=anchor)
    x0, y0, x1, y1 = int(bb[0]) - pad, int(bb[1]) - pad, int(bb[2]) + pad, int(bb[3]) + pad
    lay = Image.new('RGBA', (x1 - x0, y1 - y0), (0, 0, 0, 0))
    ld = ImageDraw.Draw(lay)
    ld.text((xy[0] - x0, xy[1] - y0), text, font=fnt, fill=glow + (255,), anchor=anchor, stroke_width=2)
    g = lay.filter(ImageFilter.GaussianBlur(blur))
    if spread > 1:
        g = Image.alpha_composite(g, g)
    base = img.crop((x0, y0, x1, y1)).convert('RGBA')
    base.alpha_composite(g)
    ImageDraw.Draw(base).text((xy[0] - x0, xy[1] - y0), text, font=fnt, fill=fill, anchor=anchor)
    img.paste(base.convert('RGB'), (x0, y0))

# ---------------- scene A: home screen -> app open ----------------
ICX, ICY, ICS = 540, 880, 230
APP_SLOTS = []
def make_home_bg():
    im = Image.new('RGB', (W, H))
    px = im.load()
    top, mid, bot = (22, 30, 70), (62, 34, 96), (12, 70, 78)
    for y in range(H):
        k = y / (H - 1)
        c = lerpc(top, mid, k / 0.55) if k < 0.55 else lerpc(mid, bot, (k - 0.55) / 0.45)
        for x in range(W): px[x, y] = c
    d = ImageDraw.Draw(im, 'RGBA')
    for i in range(5):
        d.ellipse((60 + i * 190, 260 + (i % 2) * 340, 460 + i * 190, 660 + (i % 2) * 340), fill=(255, 255, 255, 12))
    status_bar(d)
    for cx, cy, name, ini in APP_SLOTS:
        if ini is not None:
            fn = LG + 'icon_' + name.lower() + '.png'
            m = Image.new('L', (800, 800), 0); ImageDraw.Draw(m).rounded_rectangle((0, 0, 799, 799), 180, fill=255); m = m.resize((200, 200), Image.LANCZOS)
            if os.path.exists(fn):
                tile = Image.open(fn).convert('RGB').resize((200, 200), Image.LANCZOS)
            else:   # neutral placeholder tile (swap in the real icon file icon_<name>.png)
                tile = Image.new('RGB', (200, 200))
                tp = tile.load()
                for yy in range(200):
                    cc = lerpc((74, 80, 104), (36, 40, 58), yy / 199)
                    for xx in range(200): tp[xx, yy] = cc
                ImageDraw.Draw(tile).text((100, 100), ini, font=font('ExtraBold', 104), fill=(235, 238, 248), anchor='mm')
            im.paste(tile, (cx - 100, cy - 100), m)
        if ini is not None:
            ImageDraw.Draw(im).text((cx, cy + ICS // 2 + 38), name, font=font('SemiBold', 32), fill=(240, 243, 250), anchor='mm')
    return im
HOME_BG = make_home_bg()

def splash_image(a_fade=1.0):
    s = Image.new('RGB', (W, H), (3, 5, 8))
    d = ImageDraw.Draw(s, 'RGBA')
    for r, al in ((520, 14), (400, 18), (300, 22)):
        d.ellipse((W / 2 - r, H / 2 - 40 - r, W / 2 + r, H / 2 - 40 + r), fill=(52, 232, 160, al))
    s = s.filter(ImageFilter.GaussianBlur(30))
    put(s, 'full', 560, W / 2 - 280, H / 2 - 320)
    return s
SPLASH = splash_image()

def hook(scr, a):
    if a <= 0: return scr
    ov = scr.copy()
    glow_text(ov, (W / 2, 250), '%.2f SOL  →  %.1f SOL' % (INVESTED, REALIZED), font('ExtraBold', 66), (255, 255, 255), MINT, anchor='mm', blur=12, spread=2)
    glow_text(ov, (W / 2, 340), '%.1fx  ·  real on-chain trade' % MULT, font('Bold', 40), (255, 226, 150), (255, 170, 40), anchor='mm', blur=8)
    return Image.blend(scr, ov, a)

def draw_home(t):
    scr = HOME_BG.copy(); d = ImageDraw.Draw(scr, 'RGBA')
    ha = ease(t / 0.15) * (1 if t < 0.55 else 1 - ease((t - 0.55) / 0.3))
    press = 0.9 if 0.4 <= t < 0.6 else 1.0
    if t < 0.6:
        sz = ICS * press
        put(scr, 'sm', sz, ICX - sz / 2, ICY - sz / 2)
        d.text((ICX, ICY + ICS // 2 + 44), 'Mr PUMP', font=font('SemiBold', 36), fill=(240, 243, 250), anchor='mm')
        if 0.05 <= t < 0.6:
            k = ease((t - 0.05) / 0.35)
            rad = 62 if t < 0.35 else 62 - 16 * min(1, (t - 0.35) / 0.1)
            finger(d, lerp(820, ICX, k), lerp(1500, ICY + 10, k), rad)
        return scr
    k = ease((t - 0.6) / 0.4)
    x0 = lerp(ICX - ICS / 2, 0, k); y0 = lerp(ICY - ICS / 2, 0, k)
    x1 = lerp(ICX + ICS / 2, W, k); y1 = lerp(ICY + ICS / 2, H, k)
    m = Image.new('L', (W, H), 0)
    ImageDraw.Draw(m).rounded_rectangle((x0, y0, x1, y1), int(lerp(36, 0, k)), fill=255)
    scr.paste(SPLASH.copy(), (0, 0), m) if k >= 1 else None
    if k < 1:
        solid = Image.new('RGB', (W, H), (3, 5, 8))
        scr.paste(solid, (0, 0), m)
        sz = lerp(ICS, 560, k); cx = lerp(ICX, W / 2, k); cy = lerp(ICY, H / 2 - 40, k)
        put(scr, 'sm', sz, cx - sz / 2, cy - sz / 2, a=1 - ease((t - 0.85) / 0.25))
        put(scr, 'full', sz, cx - sz / 2, cy - sz / 2, a=ease((t - 0.85) / 0.25))
    return scr

# ---------------- scene B: trade tab ----------------
FIRST_PX = M15[0]['o']
_TR_DEFAULT = [{"sym": "mihao", "price": 0.01735, "mc": 16326532, "h24": 2380}, {"sym": "CLAUDIA", "price": 0.005524, "mc": 5227818, "h24": -29.48},
               {"sym": "STANK", "price": 0.003546, "mc": 3546588, "h24": 14.15}, {"sym": "DacityCoin", "price": 0.00355, "mc": 3445245, "h24": 237},
               {"sym": "FLOAT", "price": 0.00984, "mc": 9831294, "h24": -5.98}]
TR = json.load(open(ARGS.trending)) if ARGS.trending else _TR_DEFAULT
LIVE_PX = M15[-1]['c']; LIVE_MC = LIVE_PX * SUP; H24 = (LIVE_PX / M15[0]['o'] - 1) * 100
TR[0] = dict(TR[0], sym=TOKEN, price=LIVE_PX, mc=LIVE_MC, h24=H24)
def fmt_price(p): return '$%.4f' % p if p >= 0.001 else '$%.6f' % p
def fmt_pct(v): return ('{:+,.0f}%' if abs(v) >= 100 else '{:+,.2f}%').format(v)
AV_COL = [(96, 120, 210), (210, 120, 70), (80, 170, 110), (160, 90, 200), (60, 150, 200)]
def pill(d, box, fill, outline=None, w=2): d.rounded_rectangle(box, (box[3] - box[1]) / 2, fill=fill, outline=outline, width=w)

_EV = sorted([(BUY_T[i], buys[i]['wb'], 'BUY') for i in range(NB)] + [(c['tt'], c['wb'], 'SELL') for c in clusters], key=lambda e: e[0])
BAL_START = _EV[0][1][0]; BAL_END = _EV[-1][1][1]
_bal_keys = []; BAL_TAGS = []            # keys (time, value, ramp); tags (t0, t1, signed SOL)
_pp = None; _pt = None
for _t, _wb, _side in _EV:
    if _pp is not None and abs(_wb[0] - _pp) > 0.02:
        if _t - _pt >= 2.0: _ot, _rp = _pt + 1.3, 0.7; _t1 = min(_t + 0.5, _ot + _rp + 1.6)
        else: _ot, _rp, _t1 = _t - 0.45, 0.25, _t - 0.45 + 0.65
        _bal_keys.append((_ot, _wb[0], _rp)); BAL_TAGS.append((_ot, _t1, _wb[0] - _pp))
    _bal_keys.append((_t, _wb[1], 0.3 if _side == 'BUY' else 0.4)); _pp = _wb[1]; _pt = _t
_bal_keys.sort()
def bal_at(t):
    v = BAL_START
    for tt_, val, ramp in _bal_keys:
        k = clamp((t - tt_) / ramp)
        if k > 0: v = lerp(v, val, ease(k)) if k < 1 else val
    return v

def draw_trade(t, tapped=0.0):
    img = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(img, 'RGBA')
    status_bar(d)
    put(img, 'head', sx(110), sx(55), sy(185))
    for lab, (a, b), act in (('Home', (188, 386), False), ('Trade', (410, 604), True), ('Predict', (628, 851), False)):
        box = (sx(a), sy(185), sx(b), sy(295))
        pill(d, box, MINT if act else (28, 28, 30))
        d.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), lab, font=font('SemiBold', 40), fill=(5, 20, 14) if act else (205, 205, 210), anchor='mm')
    d.text((sx(55), sy(418)), 'Hot Markets', font=font('Bold', 62), fill=TXT, anchor='lm')
    d.text((sx(55), sy(500)), 'Trending 24h · via DexScreener', font=font('Medium', 34), fill=(190, 190, 196), anchor='lm')
    rr(d, (sx(640), sy(372), sx(1132), sy(500)), 34, (24, 28, 34), (52, 60, 70), 2)
    d.text((sx(886), sy(414)), 'WALLET BALANCE', font=font('SemiBold', 27), fill=(150, 160, 175), anchor='mm')
    d.text((sx(886), sy(466)), '%.2f SOL' % BAL_START, font=font('ExtraBold', 44), fill=TXT, anchor='mm')
    # hot card with press scale
    sc = 1 - 0.03 * tapped
    cx0, cy0, cx1, cy1 = sx(55), sy(568), sx(933), sy(922)
    ccx, ccy = (cx0 + cx1) / 2, (cy0 + cy1) / 2
    bx = (ccx - (ccx - cx0) * sc, ccy - (ccy - cy0) * sc, ccx + (cx1 - ccx) * sc, ccy + (cy1 - ccy) * sc)
    rr(d, bx, 40, (26, 26, 28))
    put(img, 'cat', sx(86) * sc, bx[0] + sx(55) * sc, bx[1] + sy(62) * sc)
    d.text((bx[0] + sx(167) * sc, bx[1] + sy(83) * sc), TOKEN, font=font('Bold', 44), fill=TXT, anchor='lm')
    d.text((bx[0] + sx(167) * sc, bx[1] + sy(130) * sc), fmt_usd(LIVE_MC) + ' MC', font=font('Medium', 33), fill=(190, 190, 196), anchor='lm')
    pill(d, (bx[0] + sx(610) * sc, bx[1] + sy(70) * sc, bx[0] + sx(823) * sc, bx[1] + sy(136) * sc), (18, 70, 48))
    d.text((bx[0] + sx(716) * sc, bx[1] + sy(103) * sc), fmt_pct(H24), font=font('Bold', 38), fill=MINT, anchor='mm')
    d.line([(bx[0] + sx(55) * sc, bx[1] + sy(199) * sc), (bx[2] - sx(55) * sc, bx[1] + sy(199) * sc)], fill=(48, 48, 52), width=2)
    d.ellipse((bx[0] + sx(50) * sc, bx[1] + sy(262) * sc, bx[0] + sx(68) * sc, bx[1] + sy(280) * sc), fill=MINT)
    d.text((bx[0] + sx(100) * sc, bx[1] + sy(272) * sc), '73 people viewing', font=font('Medium', 34), fill=(205, 205, 210), anchor='lm')
    for i, col in enumerate([(240, 130, 90), (140, 120, 220), (250, 200, 80)]):
        ex = bx[2] - sx(150) * sc + i * sx(34) * sc
        d.ellipse((ex, bx[1] + sy(240) * sc, ex + sx(62) * sc, bx[1] + sy(240) * sc + sx(62) * sc), fill=col, outline=(26, 26, 28), width=3)
    # second card peeking
    rr(d, (sx(957), sy(568), sx(1250), sy(922)), 40, (26, 26, 28))
    d.ellipse((sx(1010), sy(632), sx(1090), sy(712)), fill=(240, 240, 240)); d.text((sx(1050), sy(672)), TR[1]['sym'][0], font=font('Bold', 40), fill=(10, 10, 10), anchor='mm')
    d.text((sx(1110), sy(651)), TR[1]['sym'][:6], font=font('Bold', 40), fill=TXT, anchor='lm')
    d.text((sx(55), sy(1057)), 'Explore Markets  ›', font=font('Bold', 62), fill=TXT, anchor='lm')
    d.ellipse((sx(55), sy(1128), sx(165), sy(1238)), fill=(28, 28, 30)); d.text((sx(110), sy(1183)), '♥', font=font('Bold', 46), fill=TXT, anchor='mm')
    for lab, (a, b), act in (('Trending', (188, 462), True), ('Perps', (485, 693), False), ('Memes', (717, 956), False), ('New Ma', (980, 1250), False)):
        pill(d, (sx(a), sy(1128), sx(b), sy(1238)), (230, 230, 232) if act else (28, 28, 30))
        d.text(((sx(a) + sx(b)) / 2, sy(1183)), lab, font=font('SemiBold', 40), fill=(10, 10, 10) if act else (205, 205, 210), anchor='mm')
    rows = []
    for i, r_ in enumerate(TR):
        rows.append((r_['sym'][:9], fmt_usd(r_['mc']) + ' MC', fmt_price(r_['price']), fmt_pct(r_['h24']), MINT if r_['h24'] >= 0 else RED,
                     'cat' if i == 0 else AV_COL[i % len(AV_COL)], i + 1 if i < 3 else 0))
    for i, (nm, mc, pr, ch, cc, av, rk) in enumerate(rows):
        cy = sy(1357 + i * 193)
        if av == 'cat': put(img, 'cat', sx(110), sx(55), cy - sx(55))
        else:
            d.ellipse((sx(55), cy - sx(55), sx(165), cy + sx(55)), fill=av)
            d.text((sx(110), cy), nm[0], font=font('Bold', 46), fill=(255, 255, 255), anchor='mm')
        if rk:
            bc = [(255, 200, 40), (200, 200, 205), (230, 110, 60)][rk - 1]
            d.regular_polygon((sx(143), cy + sx(38), sx(27)), 6, fill=bc)
            d.text((sx(143), cy + sx(38)), str(rk), font=font('Bold', 28), fill=(10, 10, 10), anchor='mm')
        d.text((sx(190), cy - sy(32)), nm, font=font('Bold', 50), fill=TXT, anchor='lm')
        d.text((sx(190), cy + sy(37)), mc, font=font('Medium', 38), fill=(190, 190, 196), anchor='lm')
        d.text((sx(1131), cy - sy(30)), pr, font=font('Medium', 50), fill=TXT, anchor='rm')
        d.text((sx(1131), cy + sy(37)), ch, font=font('Medium', 40), fill=cc, anchor='rm')
    pill(d, (sx(55), sy(2250), sx(1132), sy(2330)), (10, 10, 10), (50, 50, 54))
    d.text((W / 2, sy(2290)), 'Show More', font=font('Medium', 34), fill=(190, 190, 196), anchor='mm')
    pill(d, (sx(55), sy(2350), sx(965), sy(2480)), (28, 28, 30))
    d.text((sx(180), sy(2415)), 'Search Mr PUMP', font=font('Medium', 46), fill=(120, 120, 126), anchor='lm')
    d.ellipse((sx(1000), sy(2350), sx(1132), sy(2482)), fill=MINT)
    d.text((sx(1066), sy(2416)), '+', font=font('Medium', 90), fill=(5, 20, 14), anchor='mm')
    return img

# ---------------- scene C: token page ----------------
LINE_PTS = [c['c'] for c in M15] + [LIVE_PX]
P24 = LIVE_PX / (1 + H24 / 100.0)
LP0, LP1 = min(LINE_PTS), max(LINE_PTS)
def draw_token(t, buy_press=0.0, rew=None):
    img = Image.new('RGB', (W, H), (0, 0, 0)); d = ImageDraw.Draw(img, 'RGBA')
    status_bar(d)
    pill(d, (sx(546), sy(182), sx(642), sy(202)), (110, 110, 114))
    put(img, 'cat', sx(110), sx(55), sy(222))
    d.ellipse((sx(790), sy(222), sx(900), sy(332)), fill=(28, 28, 30)); d.text((sx(845), sy(277)), '♡', font=font('Bold', 52), fill=TXT, anchor='mm')
    pill(d, (sx(922), sy(227), sx(1132), sy(326)), (44, 44, 46))
    d.text((sx(975), sy(276)), '⇪', font=font('Bold', 52), fill=TXT, anchor='mm'); d.text((sx(1080), sy(272)), '···', font=font('Bold', 52), fill=TXT, anchor='mm')
    d.text((sx(55), sy(412)), TOKEN, font=font('Bold', 86), fill=TXT, anchor='lm')
    d.text((sx(600), sy(425)), QUOTE + ' pool', font=font('Medium', 40), fill=(150, 150, 156), anchor='lm')
    p = ease((t - LINE0) / (LINE1 - LINE0)) if rew is None else rew
    nshow = max(2, int(1 + p * (len(LINE_PTS) - 1)))
    cur = LINE_PTS[nshow - 1]
    d.text((sx(55), sy(560)), fmt_price(cur), font=font('Bold', 100), fill=TXT, anchor='lm')
    d.text((sx(740), sy(566)), '⇆ Price', font=font('SemiBold', 40), fill=(170, 170, 176), anchor='lm')
    chg = (cur / P24 - 1) * 100
    d.text((sx(55), sy(675)), '%s$%.4f (%s)' % ('+' if chg >= 0 else '-', abs(cur - P24), fmt_pct(chg)), font=font('SemiBold', 44), fill=MINT if chg >= 0 else RED, anchor='lm')
    # line chart
    x0, x1 = 0, W - 70; y0, y1 = sy(790), sy(1450)
    pts = []
    for i in range(nshow):
        pts.append((x0 + (x1 - x0) * i / (len(LINE_PTS) - 1), y1 - (LINE_PTS[i] - LP0) / (LP1 - LP0) * (y1 - y0)))
    gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
    gd.line(pts, fill=MINT + (255,), width=14, joint='curve')
    gl = gl.crop((0, int(y0) - 60, W, int(y1) + 60)).filter(ImageFilter.GaussianBlur(12))
    base = img.crop((0, int(y0) - 60, W, int(y1) + 60)).convert('RGBA'); base.alpha_composite(gl)
    img.paste(base.convert('RGB'), (0, int(y0) - 60))
    d = ImageDraw.Draw(img, 'RGBA')
    d.line(pts, fill=MINT, width=7, joint='curve')
    ex, ey = pts[-1]
    pr = 12 + 4 * math.sin(t * 9)
    d.ellipse((ex - pr * 1.8, ey - pr * 1.8, ex + pr * 1.8, ey + pr * 1.8), fill=MINT + (50,))
    d.ellipse((ex - 11, ey - 11, ex + 11, ey + 11), fill=MINT)
    # timeframes
    d.text((sx(75), sy(1547)), '•', font=font('Bold', 40), fill=(190, 190, 196), anchor='lm'); d.text((sx(97), sy(1547)), 'LIVE', font=font('SemiBold', 40), fill=(190, 190, 196), anchor='lm')
    pill(d, (sx(211), sy(1515), sx(355), sy(1580)), (34, 34, 36))
    for lab, xx in (('1D', 283), ('1W', 437), ('1M', 593), ('1Y', 748), ('ALL', 903)):
        d.text((sx(xx), sy(1547)), lab, font=font('SemiBold', 40), fill=TXT if lab == '1D' else (190, 190, 196), anchor='mm')
    for q, (hh_, cc_) in enumerate(((16, 0), (26, 12))):
        qx = sx(1040) + q * 20
        d.line([(qx, sy(1547) - hh_ - 6), (qx, sy(1547) + hh_ + 6)], fill=(190, 190, 196), width=3)
        d.rectangle((qx - 7, sy(1547) - hh_ + cc_, qx + 7, sy(1547) + hh_ - 4 + cc_ // 2), outline=(190, 190, 196), width=3)
    pill(d, (sx(55), sy(1652), sx(1132), sy(1785)), (24, 24, 26), (44, 44, 48))
    d.text((W / 2, sy(1718)), 'Receive', font=font('SemiBold', 54), fill=(170, 170, 176), anchor='mm')
    d.text((sx(55), sy(1940)), 'Live Chat  ›', font=font('Bold', 62), fill=TXT, anchor='lm')
    d.ellipse((sx(932), sy(1932), sx(950), sy(1948)), fill=MINT); d.text((sx(1131), sy(1940)), '74 here', font=font('Medium', 52), fill=MINT, anchor='rm')
    rr(d, (sx(55), sy(2028), sx(1132), sy(2215)), 50, (24, 24, 26))
    d.ellipse((sx(110), sy(2090), sx(178), sy(2152)), fill=(40, 40, 42)); d.text((sx(144), sy(2121)), '🔥'[0] if False else '!', font=font('Bold', 40), fill=GOLD, anchor='mm')
    d.text((sx(212), sy(2122)), 'gm, ' + TOKEN + ' looking strong', font=font('Medium', 48), fill=(225, 225, 228), anchor='lm')
    # bottom bar
    d.text((sx(70), sy(2404)), fmt_usd(cur * SUP) + ' market cap', font=font('SemiBold', 38), fill=TXT, anchor='lm')
    sc = 1 - 0.05 * buy_press
    bb = (sx(602), sy(2338), sx(1100), sy(2470)); bcx, bcy = (bb[0] + bb[2]) / 2, (bb[1] + bb[3]) / 2
    pill(d, (bcx - (bcx - bb[0]) * sc, bcy - (bcy - bb[1]) * sc, bcx + (bb[2] - bcx) * sc, bcy + (bb[3] - bcy) * sc), MINT)
    d.text((bcx, bcy), 'Buy', font=font('Bold', 56), fill=(5, 20, 14), anchor='mm')
    return img, (bcx, bcy)

# ---------------- scene E: neon PNL card ----------------
def card_bg():
    im = Image.new('RGB', (W, H)); px = im.load()
    for y in range(H):
        k = y / (H - 1)
        c = lerpc((4, 7, 30), (22, 8, 54), k)
        for x in range(W): px[x, y] = c
    d = ImageDraw.Draw(im, 'RGBA')
    hz = 1560
    for i in range(-14, 15):
        d.line([(W / 2 + i * 40, hz), (W / 2 + i * 190, H)], fill=(120, 80, 255, 70), width=2)
    yy = hz
    step = 14
    while yy < H:
        d.line([(0, yy), (W, yy)], fill=(70, 200, 255, 60), width=2); yy += step; step *= 1.32
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    gd.ellipse((-200, 40, 700, 440), fill=(150, 60, 255, 90)); gd.ellipse((500, 700, 1300, 1200), fill=(30, 220, 120, 50))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    base = im.convert('RGBA'); base.alpha_composite(glow)
    return base.convert('RGB')
CARD_BG = card_bg()
def chart_bg():
    im = Image.new('RGB', (W, H)); px = im.load()
    for y in range(H):
        c = lerpc((8, 10, 18), (12, 9, 24), y / (H - 1))
        for x in range(W): px[x, y] = c
    gl = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(gl)
    gd.ellipse((-260, 120, 620, 760), fill=(120, 60, 255, 70)); gd.ellipse((520, 900, 1340, 1560), fill=(30, 220, 140, 52))
    gd.ellipse((-200, 1300, 500, 1900), fill=(40, 120, 255, 34))
    gl = gl.filter(ImageFilter.GaussianBlur(110))
    base = im.convert('RGBA'); base.alpha_composite(gl)
    return base.convert('RGB')
CHART_BG = chart_bg()
FLASH_MASK = Image.new('L', (W, H), 0)
_fd = ImageDraw.Draw(FLASH_MASK)
for q in range(40):
    _fd.rectangle((q * 3, q * 3, W - q * 3, H - q * 3), outline=int(255 * (1 - q / 40.0) ** 2), width=3)
FLASH_MASK = FLASH_MASK.filter(ImageFilter.GaussianBlur(18))
FLASH_G = Image.new('RGB', (W, H), MINT); FLASH_R = Image.new('RGB', (W, H), RED)

def neon_panel(w, h, col, r=36, poly=None, glow=16, lw=5):
    pad = glow * 2
    lay = Image.new('RGBA', (w + 2 * pad, h + 2 * pad), (0, 0, 0, 0))
    g = Image.new('RGBA', lay.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
    def shape(dr, **kw):
        if poly: dr.polygon([(x + pad, y + pad) for x, y in poly], **kw)
        else: dr.rounded_rectangle((pad, pad, pad + w, pad + h), r, **kw)
    shape(gd, outline=col + (255,), width=lw * 2)
    lay.alpha_composite(g.filter(ImageFilter.GaussianBlur(glow / 2)))
    ld = ImageDraw.Draw(lay)
    shape(ld, fill=(6, 14, 24, 238), outline=col + (255,), width=lw)
    return lay, pad

def solana_logo(d, x, y, s):
    for i in range(3):
        yy = y + i * s * 0.36
        col = lerpc((20, 240, 190), (170, 90, 255), i / 2)
        d.polygon([(x + s * 0.18, yy), (x + s, yy), (x + s * 0.82, yy + s * 0.26), (x, yy + s * 0.26)] if i != 1 else [(x, yy), (x + s * 0.82, yy), (x + s, yy + s * 0.26), (x + s * 0.18, yy + s * 0.26)], fill=col)

PANELS = {}
def build_panels():
    # header pills (static)
    # token + wallet panel
    p, pad = neon_panel(980, 150, CYAN, 34)
    d = ImageDraw.Draw(p)
    solana_logo(d, pad + 30, pad + 40, 76)
    cat = img_s('cat', 90); p.paste(cat, (pad + 128, pad + 30), cat)
    d.ellipse((pad + 128, pad + 30, pad + 218, pad + 120), outline=(255, 255, 255, 255), width=3)
    d.text((pad + 238, pad + 52), TOKEN + ' / ' + QUOTE, font=font('SemiBold', 32), fill=TXT, anchor='lm')
    d.text((pad + 238, pad + 98), 'Solana Token', font=font('Medium', 26), fill=(170, 175, 200), anchor='lm')
    d.line([(pad + 530, pad + 30), (pad + 530, pad + 120)], fill=(120, 130, 160, 200), width=2)
    d.rounded_rectangle((pad + 560, pad + 46, pad + 624, pad + 104), 10, fill=(160, 110, 255), outline=(230, 210, 255), width=3)
    d.text((pad + 648, pad + 54), 'Wallet (Solscan)', font=font('SemiBold', 28), fill=TXT, anchor='lm')
    d.text((pad + 648, pad + 98), WSHORT, font=font('Bold', 27), fill=CYAN, anchor='lm')
    d.rounded_rectangle((pad + 906, pad + 56, pad + 938, pad + 88), 6, outline=TXT, width=4)
    d.line([(pad + 920, pad + 74), (pad + 942, pad + 52)], fill=TXT, width=4)
    PANELS['token'] = (p, pad)
    # buy tile
    p, pad = neon_panel(470, 180, MINT, 30)
    d = ImageDraw.Draw(p)
    d.line([(pad + 70, pad + 50), (pad + 70, pad + 112)], fill=MINT, width=10); d.polygon([(pad + 40, pad + 90), (pad + 100, pad + 90), (pad + 70, pad + 124)], fill=MINT)
    d.line([(pad + 36, pad + 140), (pad + 104, pad + 140)], fill=MINT, width=9)
    d.text((pad + 290, pad + 52), 'TOTAL BUY', font=font('ExtraBoldItalic', 40), fill=TXT, anchor='mm')
    PANELS['buy'] = (p, pad)
    p, pad = neon_panel(470, 180, (255, 80, 130), 30)
    d = ImageDraw.Draw(p)
    d.line([(pad + 70, pad + 124), (pad + 70, pad + 60)], fill=(255, 100, 140), width=10); d.polygon([(pad + 40, pad + 84), (pad + 100, pad + 84), (pad + 70, pad + 50)], fill=(255, 100, 140))
    d.line([(pad + 36, pad + 140), (pad + 104, pad + 140)], fill=(255, 100, 140), width=9)
    d.text((pad + 290, pad + 52), 'TOTAL SELL', font=font('ExtraBoldItalic', 40), fill=TXT, anchor='mm')
    PANELS['sell'] = (p, pad)
    # pnl panel (cut corners)
    w, h, c = 980, 400, 60
    poly = [(c, 0), (w - c, 0), (w, c), (w, h - c), (w - c, h), (c, h), (0, h - c), (0, c)]
    p, pad = neon_panel(w, h, MINT, poly=poly, glow=20, lw=6)
    d = ImageDraw.Draw(p)
    for k, (cx, cy) in enumerate(((120, 250), (160, 190), (110, 190))):
        for q in range(3):
            yy = pad + cy + 30 - q * 22
            d.ellipse((pad + cx - 50, yy - 18, pad + cx + 50, yy + 18), fill=lerpc((70, 130, 230), (130, 70, 200), q / 2), outline=(190, 235, 255), width=2)
    d.line([(pad + 252, pad + 70), (pad + 252, pad + 330)], fill=(230, 235, 245, 220), width=3)
    d.text((pad + 400, pad + 80), 'PNL', font=font('ExtraBoldItalic', 84), fill=TXT, anchor='mm')
    d.line([(pad + 600, pad + 100), (pad + 760, pad + 80), (pad + 860, pad + 36)], fill=MINT, width=14, joint='curve')
    d.polygon([(pad + 905, pad + 14), (pad + 856, pad + 20), (pad + 838, pad + 78)], fill=(150, 255, 90))
    PANELS['pnl'] = (p, pad)
    # roi bar
    p, pad = neon_panel(980, 140, MINT, 40)
    d = ImageDraw.Draw(p)
    for sgn, x0 in ((-1, 70), (1, 910)):
        for q in range(2):
            xx = pad + x0 + sgn * q * 26
            d.line([(xx - sgn * 18, pad + 40), (xx + sgn * 18, pad + 70), (xx - sgn * 18, pad + 100)], fill=(120, 255, 100), width=11)
    PANELS['roi'] = (p, pad)
build_panels()

def with_alpha(im, a):
    if a >= 1: return im
    im = im.copy(); im.putalpha(im.getchannel('A').point(lambda v: int(v * a))); return im

def slide(img, name_or_im, x, y, t, t0, dx=0, dy=0, dur=0.32):
    p = ease((t - t0) / dur)
    if p <= 0: return
    im = name_or_im
    img.paste(with_alpha(im, p).convert('RGBA'), (int(x + (1 - p) * dx), int(y + (1 - p) * dy)), with_alpha(im, p))

CONF = None
def make_conf():
    rng = random.Random(5)
    return [(rng.uniform(0, W), rng.uniform(-400, 0), rng.uniform(260, 620), rng.uniform(-60, 60), rng.choice([MINT, GOLD, (255, 255, 255), CYAN, (255, 90, 150)]), rng.uniform(10, 20), rng.uniform(0, 6)) for _ in range(90)]
CONF = make_conf()

def draw_card(img, t):
    a = ease((t - SUM_T) / 0.28)
    if a < 1: base = Image.blend(img, CARD_BG, a)
    else: base = CARD_BG.copy()
    img = base
    d = ImageDraw.Draw(img, 'RGBA')
    # header
    hp = ease((t - (SUM_T + 0.05)) / 0.3)
    if hp > 0:
        off = int((1 - hp) * -120)
        ring = Image.new('RGBA', (300, 300), (0, 0, 0, 0)); ImageDraw.Draw(ring).ellipse((30, 30, 270, 270), outline=MINT + (255,), width=10)
        ring = ring.filter(ImageFilter.GaussianBlur(9))
        img.paste(ring, (30 + off, 100), ring)
        put(img, 'head', 230, 65 + off, 135, a=hp)
        d.ellipse((60 + off, 130, 300 + off, 370), outline=MINT, width=5)
        glow_text(img, (330 + off, 160), 'MR PUMP', font('ExtraBoldItalic', 128), (255, 232, 160), (255, 190, 60), anchor='lm', blur=10)
        pill(d, (330 + off, 255, 1040 + off, 325), (14, 8, 40, 235), PURP + (255,), 4)
        d.text((685 + off, 290), 'REAL ON-CHAIN TRADE', font=font('ExtraBoldItalic', 38), fill=TXT, anchor='mm')
        pill(d, (330 + off, 345, 1040 + off, 415), CYAN + (255,))
        d.text((600 + off, 380), 'VERIFIED ON SOLANA', font=font('ExtraBoldItalic', 38), fill=(6, 20, 36), anchor='mm')
        for q in range(3): d.polygon([(930 + off + q * 28, 358), (958 + off + q * 28, 380), (930 + off + q * 28, 402), (942 + off + q * 28, 380)], fill=(6, 20, 36))
    def paste_panel(name, x, y, t0, dx=0, dy=0):
        p, pad = PANELS[name]
        pr = ease((t - t0) / 0.32)
        if pr <= 0: return None
        im = with_alpha(p, pr)
        px, py = int(x - pad + (1 - pr) * dx), int(y - pad + (1 - pr) * dy)
        img.paste(im, (px, py), im)
        return px + pad, py + pad, pr
    paste_panel('token', 50, 450, SUM_T + 0.2, dx=-400)
    r = paste_panel('buy', 50, 640, SUM_T + 0.3, dx=-400)
    if r: glow_text(img, (r[0] + 290, r[1] + 128), '%.2f SOL' % INVESTED, font('ExtraBoldItalic', 56), (190, 255, 150), MINT, anchor='mm', blur=8)
    r = paste_panel('sell', 560, 640, SUM_T + 0.3, dx=400)
    if r: glow_text(img, (r[0] + 290, r[1] + 128), '%.2f SOL' % REALIZED, font('ExtraBoldItalic', 52), (255, 160, 180), (255, 70, 120), anchor='mm', blur=8)
    cnt = ease((t - (SUM_T + 0.55)) / 1.25)
    r = paste_panel('pnl', 50, 880, SUM_T + 0.42, dy=200)
    if r:
        pv = PNL_SOL * cnt
        glow_text(img, (r[0] + 600, r[1] + 270), '+%.2f SOL' % pv, font('ExtraBoldItalic', 94), (190, 255, 120), MINT, anchor='mm', blur=12, spread=2)
    r = paste_panel('roi', 50, 1320, SUM_T + 0.55, dy=200)
    if r:
        rv = ROI * cnt
        glow_text(img, (r[0] + 270, r[1] + 70), 'ROI:', font('ExtraBoldItalic', 86), TXT, CYAN, anchor='mm', blur=6)
        glow_text(img, (r[0] + 640, r[1] + 70), '+{:,.1f}%'.format(rv), font('ExtraBoldItalic', 86), (190, 255, 120), MINT, anchor='mm', blur=10, spread=2)
    d = ImageDraw.Draw(img, 'RGBA')
    mp = ease((t - (SUM_T + 0.7)) / 0.3)
    if mp > 0:
        mv = 1 + (MULT - 1) * cnt
        d.text((W / 2, 1500), 'MULTIPLE  %.1fx   \u00b7   HELD  %s' % (mv, elapsed(sells[-1]['t'] - buys[0]['t'])), font=font('Bold', 38), fill=GOLD + (int(255 * mp),), anchor='mm')
        wv = BAL_START + (BAL_END - BAL_START) * cnt
        d.text((W / 2, 1552), 'WALLET BALANCE   %.2f  →  %.2f SOL' % (BAL_START, wv), font=font('ExtraBold', 38), fill=(190, 240, 255, int(255 * mp)), anchor='mm')
        put(img, 'full', 250, (W - 250) / 2, 1595 + int((1 - mp) * 40), a=mp)
    # confetti when the numbers land
    ct = t - (SUM_T + 1.8)
    if ct > 0:
        for (cx, cy0, vy, vx, col, sz, ph) in CONF:
            y = cy0 + vy * ct + 300 * ct * ct * 0.3
            if y > H + 40: continue
            x = cx + vx * ct + 18 * math.sin(ct * 6 + ph)
            d.rectangle((x, y, x + sz, y + sz * 0.5), fill=col + (int(220 * clamp(1.6 - ct)),))
    return img

# ---------------- scene D: candle chart ----------------
CX0, CY0, CX1, CY1 = 30, 345, 1050, 1500
PX0, PX1 = 150, 905
PY0, PY1 = CY0 + 70, CY1 - 90

def solusd_at(mtime):
    return lerp(SOL_BUY, SOL_SELL, clamp((mtime - T_BUY) / (S0 - T_BUY)))

def draw_chart(fi):
    t = fi / FPS
    img = CHART_BG.copy()
    for tt_, tr_ in events2:
        ag = t - tt_
        if 0 <= ag < 0.45:
            m_ = FLASH_MASK.point(lambda v, a_=(1 - ag / 0.45) * (0.40 if tr_['side'] == 'BUY' else 0.26): int(v * a_))
            img.paste(FLASH_G if tr_['side'] == 'BUY' else FLASH_R, (0, 0), m_)
    d = ImageDraw.Draw(img, 'RGBA')
    h, inv, rea, last = held_at(t)
    v = view_of(t)
    vis, step = visible(t)
    if v == '15m': mtime = mt15(t)
    else: mtime = mt1(t)

    if vis: price = vis[-1]['c']
    else: price = ENTRY_PX
    if t < B_START and last is not None: price = last['px']
    mc = price * SUP
    peak_px = max([c['h'] for c in vis] + [ENTRY_PX]) if vis else ENTRY_PX
    since = (price / ENTRY_PX - 1) * 100
    peak_x = peak_px / ENTRY_PX

    # header: bull head + wordmark
    put(img, 'head', 58, 36, 42)
    d.text((110, 52), 'Mr PUMP', font=f_logo, fill=TXT)
    rr(d, (700, 50, 1044, 108), 29, PANEL, LINE)
    d.text((872, 79), TOKEN + ' \u00b7 ' + elapsed(mtime - buys[0]['t']), font=f_h2, fill=TXT, anchor='mm')
    d.text((36, 140), fmt_usd(mc), font=f_big, fill=TXT)
    d.text((40, 262), 'Market cap · USD', font=f_h2, fill=DIM)
    # PNL block (SOL only): position value while holding, realized PNL once selling
    sol_usd = solusd_at(mtime)
    hv = h * price / sol_usd if h > 1 else 0
    sold_tok = sum(tr['tok'] for tt, tr in events if tr['side'] == 'SELL' and t >= tt)
    real_pnl = rea - INVESTED * (sold_tok / TOK) if rea else 0
    mult = (rea / inv) if (rea and inv) else 0
    if rea:
        d.text((1044, 150), 'REALIZED PNL', font=f_xs, fill=DIM, anchor='ra')
        d.text((1044, 178), '%+.1f SOL' % real_pnl, font=f_num, fill=MINT, anchor='ra')
        d.text((1044, 246), 'ROI %+.0f%%' % (real_pnl / INVESTED * 100), font=f_h1, fill=MINT, anchor='ra')
        d.text((1044, 296), 'sold %.0f%% of bag' % (sold_tok / TOK * 100), font=f_xs, fill=DIM, anchor='ra')
    else:
        d.text((1044, 150), 'POSITION', font=f_xs, fill=DIM, anchor='ra')
        d.text((1044, 178), '%.1f SOL' % hv, font=f_num, fill=TXT, anchor='ra')
        d.text((1044, 296), ('held %s' % fmt_tok(h)) if h > 1 else '', font=f_xs, fill=DIM, anchor='ra')

    ch = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    cdw = ImageDraw.Draw(ch)
    rr(cdw, (CX0, CY0, CX1, CY1), 26, PANEL + (232,), LINE + (255,))
    lo_s, hi_s = RANGE[fi]
    def Y(p): return PY1 - (math.log(p) - lo_s) / (hi_s - lo_s) * (PY1 - PY0)
    for lv, lb in ((5e4, '$50K'), (1e5, '$100K'), (2e5, '$200K'), (3e5, '$300K'), (5e5, '$500K'), (1e6, '$1M'), (2e6, '$2M')):
        p = lv / SUP
        if math.log(p) < lo_s + 0.05 or math.log(p) > hi_s - 0.05: continue
        y = Y(p)
        cdw.line([(PX0, y), (PX1 + 6, y)], fill=LINE + (255,), width=1)
        cdw.text((PX0 - 14, y - 10), lb, font=font('SemiBold', 22), fill=TXT + (235,), anchor='rm')
        cdw.text((PX0 - 14, y + 13), ('$%.5f' % p) if p >= 0.001 else ('$%.6f' % p), font=font('Medium', 17), fill=DIM + (255,), anchor='rm')
    for gx in range(PX0, PX1, 86): cdw.line([(gx, PY0 - 10), (gx, PY1 + 10)], fill=LINE + (70,), width=1)
    slots = min(36, max(16, len(vis) + 4))
    first_t = M15[0]['t']
    cw = (PX1 - PX0) / slots
    def X(ts): return PX0 + (ts - first_t) / 300.0 * cw + cw / 2
    if len(vis) > 2:
        gpts = [(X(c['t']), Y(c['c'])) for c in vis]
        gl = Image.new('RGBA', (CX1 - CX0, CY1 - CY0), (0, 0, 0, 0))
        ImageDraw.Draw(gl).line([(x - CX0, y - CY0) for x, y in gpts], fill=(MINT if vis[-1]['c'] >= vis[0]['c'] else RED) + (170,), width=9, joint='curve')
        gl = gl.filter(ImageFilter.GaussianBlur(11))
        ch.alpha_composite(gl, (CX0, CY0))
    cdw = ImageDraw.Draw(ch)
    late = []
    ye = Y(ENTRY_PX)
    elab = 'ENTRY ' + fmt_usd(ENTRY_PX * SUP)
    EX0 = PX1 - 252
    if PY0 - 5 < ye < PY1 + 5:
        for xx in range(PX0, PX1, 16): cdw.line([(xx, ye), (xx + 8, ye)], fill=MINT + (170,), width=2)
        late.append(lambda: (rr(cdw, (EX0, ye - 17, EX0 + 246, ye + 17), 9, (12, 58, 42, 255), MINT + (255,), 1), cdw.text((EX0 + 12, ye), elab, font=f_xs, fill=MINT + (255,), anchor='lm')))
    else:
        late.append(lambda: (rr(cdw, (EX0, PY1 - 56, EX0 + 246, PY1 - 22), 9, (12, 58, 42, 255), MINT + (255,), 1), cdw.text((EX0 + 12, PY1 - 39), '\u25bc ' + elab, font=f_xs, fill=MINT + (255,), anchor='lm')))
    if t >= clusters[-1]['tt'] + 0.3:
        ya = Y(AVG_SELL_PX)
        if PY0 < ya < PY1:
            for xx in range(PX0, PX1, 16): cdw.line([(xx, ya), (xx + 8, ya)], fill=RED + (170,), width=2)
            cy_ = ya if abs(ya - (PY0 + 40)) > 56 else PY0 + 40 + 60
            rr(cdw, (PX0 + 6, cy_ - 17, PX0 + 276, cy_ + 17), 9, (70, 16, 24, 255), RED + (255,), 1)
            cdw.text((PX0 + 18, cy_), 'AVG SELL ' + fmt_usd(AVG_SELL_PX * SUP), font=f_xs, fill=RED + (255,), anchor='lm')
    bw = max(1.5, cw * 0.68)
    for c in vis:
        x = X(c['t']); up = c['c'] >= c['o']
        colr = MINT if up else RED
        cdw.line([(x, Y(c['h'])), (x, Y(c['l']))], fill=colr + (255,), width=1 if bw < 4 else 2)
        y1, y2 = Y(max(c['o'], c['c'])), Y(min(c['o'], c['c']))
        if y2 - y1 < 1.5: y2 = y1 + 1.5
        cdw.rectangle((x - bw / 2, y1, x + bw / 2, y2), fill=colr + (255,))
    for fn_ in late: fn_()
    if vis:
        yl = Y(price); lc = MINT if vis[-1]['c'] >= vis[-1]['o'] else RED
        for xx in range(PX0, PX1, 14): cdw.line([(xx, yl), (xx + 7, yl)], fill=lc + (160,), width=1)
        rr(cdw, (PX1 + 1, yl - 21, 1043, yl + 21), 11, lc + (70,))
        rr(cdw, (PX1 + 4, yl - 17, 1040, yl + 17), 9, lc + (255,))
        cdw.text((1034, yl), fmt_usd(price * SUP).replace('.00', ''), font=font('Bold', 21), fill=BG + (255,), anchor='rm')
        cdw.text((1034, yl + 31), fmt_price(price), font=font('Medium', 17), fill=DIM + (255,), anchor='rm')
    # markers
    for bi, bb_ in enumerate(buys):
        if t < BUY_T[bi]: continue
        a_ = ease((t - BUY_T[bi]) / 0.2)
        xb = X((bb_['t'] // 300) * 300) + (bi - (NB - 1) / 2.0) * 34 * (1 if NB > 1 else 0)
        py_ = Y(bb_['px']); yb = py_ + 74 + (bi % 2) * 40
        cdw.line([(xb, py_ + 6), (xb, yb - 22)], fill=MINT + (200,), width=2)
        cdw.ellipse((xb - 5, py_ - 5, xb + 5, py_ + 5), fill=(255, 255, 255, 255))
        r_ = 23 * (0.4 + 0.6 * a_)
        cdw.ellipse((xb - r_, yb - r_, xb + r_, yb + r_), fill=MINT + (255,))
        cdw.text((xb, yb - 1), 'B%d' % (bi + 1), font=f_mark, fill=BG + (255,), anchor='mm')
        cdw.text((xb, yb + 40), '%.2f SOL' % bb_['sol'], font=font('Bold', 21), fill=MINT + (int(255 * a_),), anchor='mm', stroke_width=3, stroke_fill=PANEL + (255,))
        bage = t - BUY_T[bi]
        if 0 <= bage < 0.5:
            rr_ = 24 + 70 * ease(bage / 0.5)
            cdw.ellipse((xb - rr_, yb - rr_, xb + rr_, yb + rr_), outline=MINT + (int(230 * (1 - bage / 0.5)),), width=4)
    RY = PY0 + 40
    for ci, cl in enumerate(clusters):
        if t >= cl['tt']:
            x = 330 + ci * 66
            a = ease((t - cl['tt']) / 0.2)
            r = 21 * (0.4 + 0.6 * a)
            xc, yc = X((cl['t'] // 300) * 300), Y(cl['px'])
            cdw.line([(xc - 11, yc), (xc + 11, yc)], fill=RED + (255,), width=3)
            cdw.ellipse((xc - 4, yc - 4, xc + 4, yc + 4), fill=(255, 255, 255, 255))
            cdw.ellipse((x - r, RY - r, x + r, RY + r), fill=RED + (255,))
            cdw.text((x, RY - 1), 'S%d' % cl['k'], font=f_mark, fill=BG + (255,), anchor='mm')
            cdw.text((x, RY - 36), '%.1f' % cl['sol'], font=font('Bold', 19), fill=(255, 200, 205, int(255 * a)), anchor='mm', stroke_width=3, stroke_fill=PANEL + (255,))
            age = t - cl['tt']
            if age < 0.5:
                rr_ = 22 + 56 * ease(age / 0.5)
                cdw.ellipse((x - rr_, RY - rr_, x + rr_, RY + rr_), outline=RED + (int(230 * (1 - age / 0.5)),), width=4)
    lines = [(tt, tr) for tt, tr in events2 if t >= tt]
    if lines:
        pw_, ph_ = 540, 30 * len(lines) + 14
        px0_, py0_ = PX1 - 4 - pw_, PY1 - ph_ - 44
        rr(cdw, (px0_, py0_, px0_ + pw_, py0_ + ph_), 14, (10, 14, 20, 232), LINE + (255,), 1)
        for i, (tt, tr) in enumerate(lines):
            al = int(255 * ease((t - tt) / 0.2)); yy = py0_ + 7 + i * 30 + 15
            c = MINT if tr['side'] == 'BUY' else RED
            tag_ = ('BUY #%d' if tr['side'] == 'BUY' else 'SELL #%d') % tr['k']
            cdw.text((px0_ + 14, yy), tag_, font=font('ExtraBold', 21), fill=c + (al,), anchor='lm')
            cdw.text((px0_ + 108, yy), '%.2f SOL' % tr['sol'], font=font('Bold', 21), fill=TXT + (al,), anchor='lm')
            cdw.text((px0_ + 236, yy), fmt_tok(tr['tok']) + ' tok', font=font('Medium', 20), fill=DIM + (al,), anchor='lm')
            cdw.text((px0_ + 372, yy), '@ ' + fmt_usd(tr['mc']), font=font('Bold', 21), fill=c + (al,), anchor='lm')
    # dissolve
    if DIP0 <= t < DIP1:
        k = (t - DIP0) / (DIP1 - DIP0)
        a = abs(2 * k - 1) ** 1.2
    else: a = 1.0
    if a < 1:
        ch.putalpha(ch.getchannel('A').point(lambda x: int(x * a)))
    # shake on every sell cluster
    dx = dy = 0
    for cl in clusters:
        age = t - cl['tt']
        if 0 <= age < 0.28:
            amp = 5 * (1 - age / 0.28); dx += int(amp * math.sin(age * 110)); dy += int(amp * 0.6 * math.cos(age * 95))
    img.paste(ch, (dx, dy), ch)
    d = ImageDraw.Draw(img, 'RGBA')
    if B_START <= t < B_END and hv > 0:
        ka = min(ease((t - B_START) / 0.5), ease((B_END - t) / 0.5)) * 0.5
        tmp = img.copy()
        glow_text(tmp, (W / 2, 800), '%.0f SOL' % hv, font('ExtraBold', 150), (255, 255, 255), MINT, anchor='mm', blur=16, spread=2)
        ImageDraw.Draw(tmp, 'RGBA').text((W / 2, 700), 'POSITION VALUE', font=font('Bold', 30), fill=(190, 255, 225), anchor='mm')
        ImageDraw.Draw(tmp, 'RGBA').text((W / 2, 905), 'holding ' + elapsed(mtime - buys[-1]['t']), font=font('SemiBold', 34), fill=(200, 208, 220), anchor='mm')
        img = Image.blend(img, tmp, ka)
        d = ImageDraw.Draw(img, 'RGBA')
    d.text((CX0 + 26, CY0 + 22), '5m price \u00b7 rebuilt from on-chain swaps', font=f_xs, fill=DIM)
    # pulsing LIVE dot
    pa = 0.5 + 0.5 * math.sin(t * 8)
    for q in range(2):
        xx = CX1 - 142 + q * 14
        d.polygon([(xx + 12, CY0 + 23), (xx, CY0 + 31), (xx + 12, CY0 + 39)], fill=GOLD + (int(150 + 105 * pa),))
    d.text((CX1 - 108, CY0 + 31), 'REPLAY', font=font('Bold', 21), fill=GOLD, anchor='lm')
    if DIP0 <= t < DIP1 and 0.25 < (t - DIP0) / (DIP1 - DIP0) < 0.8:
        d.text((W / 2, 880), 'zoom ▸ 1 minute', font=font('ExtraBold', 54), fill=TXT + (230,), anchor='mm')
    # order ticket: which order, how much, at what price
    rec = [(tt, tr) for tt, tr in events2 if t >= tt and t - tt < 2.3]
    if rec:
        tt, tr = rec[-1]
        sl = ease((t - tt) / 0.18); fade = 1 if t - tt < 2.0 else max(0, (2.3 - (t - tt)) / 0.3)
        al = int(255 * sl * fade)
        yy = CY1 - 114 + int((1 - sl) * 16)
        c = MINT if tr['side'] == 'BUY' else RED
        rr(d, (50, yy, 1030, yy + 98), 28, (20, 26, 36, al), c + (al,), 3)
        d.ellipse((70, yy + 20, 128, yy + 78), fill=c + (al,))
        d.text((99, yy + 48), 'B' if tr['side'] == 'BUY' else 'S', font=font('ExtraBold', 30), fill=BG + (al,), anchor='mm')
        if tr['side'] == 'BUY':
            l1 = ('BOUGHT #%d of %d' % (tr['k'], NB) if NB > 1 else 'BOUGHT') + ' \u00b7 %.2f SOL' % tr['sol']
            l2 = '%s %s @ %s MC \u00b7 %s / token' % (fmt_tok(tr['tok']), TOKEN, fmt_usd(tr['mc']), fmt_price(tr['px']))
        else:
            l1 = 'SOLD #%d of %d' % (tr['k'], NG) + (' (%d orders)' % tr['n'] if tr['n'] > 1 else '') + ' \u00b7 %.2f SOL' % tr['sol']
            l2 = '%s %s @ %s MC \u00b7 %s / token' % (fmt_tok(tr['tok']), TOKEN, fmt_usd(tr['mc']), fmt_price(tr['px']))
        d.text((150, yy + 33), l1, font=font('Bold', 34), fill=TXT + (al,), anchor='lm')
        d.text((150, yy + 71), l2, font=font('Medium', 25), fill=(170, 178, 192, al), anchor='lm')
        wb = tr['wb']
        d.text((1010, yy + 33), 'WALLET  %.2f \u2192 %.2f' % (wb[0], wb[1]), font=font('Bold', 27), fill=c + (al,), anchor='rm')
    # tiles (all SOL)
    ty = 1530; tw = 326
    tiles = [('Invested', '%.2f SOL' % inv, 'SOL in', TXT),
             ('Realized', '%.1f SOL' % rea, 'SOL out', MINT if rea else TXT),
             ('Multiple', ('%.1fx' % mult) if mult else '—', 'realized ÷ invested', GOLD if mult else TXT)]
    for i, (a_, b_, c_, col_) in enumerate(tiles):
        x0 = 30 + i * (tw + 21)
        rr(d, (x0, ty, x0 + tw, ty + 190), 24, PANEL, LINE)
        d.text((x0 + 24, ty + 20), a_, font=f_xs, fill=DIM)
        d.text((x0 + 24, ty + 62), b_, font=f_tile, fill=col_)
        d.text((x0 + 24, ty + 134), c_, font=f_xs, fill=DIM)
    rr(d, (30, 1744, 1050, 1840), 24, PANEL, LINE)
    bv = bal_at(t)
    rising = t >= SELL_T[0]
    d.text((56, 1756), 'WALLET BALANCE', font=font('SemiBold', 21), fill=DIM)
    d.text((56, 1807), '%.2f SOL' % bv, font=font('ExtraBold', 40), fill=MINT if rising else TXT, anchor='lm')
    d.text((1024, 1768), 'START  %.2f SOL' % BAL_START, font=font('SemiBold', 24), fill=DIM, anchor='rm')
    for tg0, tg1, tg_v in BAL_TAGS:
        if tg0 <= t < tg1:
            al_ = int(255 * min(ease((t - tg0) / 0.2), ease((tg1 - t) / 0.2)))
            d.text((440, 1792), ('+%.2f SOL in' % tg_v) if tg_v > 0 else ('\u2212%.2f SOL moved out' % -tg_v), font=font('Bold', 28), fill=(MINT if tg_v > 0 else GOLD) + (al_,), anchor='lm')
    d.text((1024, 1806), WSHORT, font=font('Medium', 24), fill=DIM, anchor='rm')
    return img

def vhs(img, k):
    if k <= 0.01: return img
    r, g, b = img.split()
    r = ImageChops.offset(r, int(10 * k), 0); b = ImageChops.offset(b, -int(10 * k), 0)
    out = Image.merge('RGB', (r, g, b))
    d = ImageDraw.Draw(out, 'RGBA')
    for y in range(0, H, 6): d.line([(0, y), (W, y)], fill=(0, 0, 0, int(70 * k)), width=2)
    for q in range(3):
        yy = (int(t_glob[0] * 900) + q * 610) % H
        band = out.crop((0, yy, W, min(H, yy + 40)))
        out.paste(band, (int(26 * k * (1 if q % 2 else -1)), yy))
    return out
t_glob = [0.0]

def draw_frame(fi):
    t = fi / FPS
    t_glob[0] = t
    if t < 1.1:
        return draw_home(t)
    if t < HOME_END:
        tr = draw_trade(t)
        return Image.blend(SPLASH, tr, ease((t - 1.1) / (HOME_END - 1.1)))
    if t < CH0:
        tap = 0.0
        tapx, tapy = None, None
        if t < PUSH1:
            tp = draw_trade(t, tapped=ease((t - (TAP_MIHAO + 0.3)) / 0.1) if t >= TAP_MIHAO + 0.3 else 0)
            if TAP_MIHAO - 0.45 <= t < TAP_MIHAO + 0.4:
                k = ease((t - (TAP_MIHAO - 0.45)) / 0.4)
                fd = ImageDraw.Draw(tp, 'RGBA')
                finger(fd, lerp(880, 420, k), lerp(1500, 520, k), 56 if t < TAP_MIHAO + 0.25 else 44, 1 - ease((t - (TAP_MIHAO + 0.4 - 0.12)) / 0.12) if t > TAP_MIHAO + 0.28 else 1)
        rw = (1 - ease((t - RW0) / (RW1 - RW0))) if t >= RW0 else None
        tk, (bx, by) = draw_token(t, buy_press=ease((t - (TAP_BUY + 0.25)) / 0.1) if TAP_BUY + 0.25 <= t < TAP_BUY + 0.5 else 0, rew=rw)
        if t < PUSH0: return tp
        if t < PUSH1:
            k = ease((t - PUSH0) / (PUSH1 - PUSH0))
            out = Image.new('RGB', (W, H), (0, 0, 0))
            out.paste(tp, (int(-k * 260), 0))
            dark = Image.new('RGB', (W, H), (0, 0, 0)); out = Image.blend(out, dark, 0.45 * k)
            out.paste(tk, (int((1 - k) * W), 0))
            return out
        fd = ImageDraw.Draw(tk, 'RGBA')
        if TAP_BUY - 0.5 <= t < TAP_BUY + 0.42:
            k = ease((t - (TAP_BUY - 0.5)) / 0.45)
            a = 1.0 if t < TAP_BUY + 0.3 else max(0, 1 - (t - (TAP_BUY + 0.3)) / 0.12)
            finger(fd, lerp(300, bx, k), lerp(1500, by, k), 56 if t < TAP_BUY + 0.25 else 44, a)
        if t >= RW0:
            k = ease((t - RW0) / 0.12)
            tk = vhs(tk, k)
            td = ImageDraw.Draw(tk, 'RGBA')
            td.rounded_rectangle((300, 1000, 780, 1090), 45, fill=(8, 12, 18, 220), outline=GOLD + (255,), width=3)
            for q in range(2):
                xx = 345 + q * 32
                td.polygon([(xx + 26, 1030), (xx, 1045), (xx + 26, 1060)], fill=GOLD)
            td.text((560, 1045), 'REWIND', font=font('ExtraBold', 40), fill=TXT, anchor='mm')
        return tk
    if t < CH1:
        tk, _ = draw_token(t, buy_press=0, rew=0.0)
        tk = vhs(tk, 1 - ease((t - CH0) / (CH1 - CH0)))
        return Image.blend(tk, draw_chart(fi), ease((t - CH0) / (CH1 - CH0)))
    ch = draw_chart(fi)
    if 3.95 <= t < 4.8:
        a_ = ease((t - 3.95) / 0.15) * (1 - ease((t - 4.4) / 0.3))
        ov = Image.new('RGBA', (W, H), (0, 0, 0, 0)); od = ImageDraw.Draw(ov)
        od.rounded_rectangle((150, 820, 930, 940), 60, fill=(8, 12, 18, int(235 * a_)), outline=GOLD + (int(255 * a_),), width=3)
        for q in range(2):
            xx = 215 + q * 34
            od.polygon([(xx + 28, 855), (xx, 880), (xx + 28, 905)], fill=GOLD + (int(255 * a_),))
        od.text((580, 880), 'REPLAYING WALLET TRADES', font=font('ExtraBold', 40), fill=TXT + (int(255 * a_),), anchor='mm')
        ch = Image.alpha_composite(ch.convert('RGBA'), ov).convert('RGB')
    if t >= SUM_T:
        return draw_card(ch, t)
    return ch

def make_audio(wav_path, BUY_T, SELL_T, BSTART, FS_, SUM):
    import numpy as np
    BRK = FS_ - 1.0
    SR=44100; DUR=20.0; N=int(SR*DUR)
    t=np.arange(N)/SR
    rng=np.random.default_rng(11)
    BEAT=0.5; G0=0.2                    # 120 BPM, grid chosen so the sells (12.2 + 0.5*i) and the PNL hit (17.2) land on beats
    M0=1.2
    mus=np.zeros(N); kick_bus=np.zeros(N); drums=np.zeros(N); fx=np.zeros(N)
    def add(buf,sig,start,gain=1.0):
        i=int(round(start*SR))
        if i<0 or i>=N: return
        j=min(N,i+len(sig)); buf[i:j]+=sig[:j-i]*gain
    def env_t(d): return np.arange(0,int(d*SR))/SR
    # ---------- drum sounds ----------
    def kick(amp=1.0):
        x=env_t(0.35)
        return (np.sin(2*np.pi*(46*x+(120-46)*(1-np.exp(-x*28))/28))*np.exp(-x*9.5)+0.25*np.sin(2*np.pi*90*x)*np.exp(-x*40))*amp
    def clap(amp=1.0):
        x=env_t(0.22); n=rng.standard_normal(len(x))
        n=n-np.concatenate(([0],n[:-1]))*0.85               # crude high-pass
        e=np.exp(-x*22)+0.7*np.exp(-np.clip(x-0.012,0,None)*30)*(x>0.012)+0.5*np.exp(-np.clip(x-0.024,0,None)*30)*(x>0.024)
        return n*e*0.30*amp
    def hat(amp=1.0,open_=False):
        x=env_t(0.28 if open_ else 0.06); n=rng.standard_normal(len(x)); n=n-np.concatenate(([0],n[:-1]))*0.9
        return n*np.exp(-x*(10 if open_ else 70))*0.20*amp
    def crash(d=1.6,amp=1.0):
        x=env_t(d); n=rng.standard_normal(len(x)); n=n-np.concatenate(([0],n[:-1]))*0.8
        return n*np.exp(-x*2.6)*0.30*amp
    def pluck(f,d,dec,amp,harm=10):
        x=env_t(d); s=np.zeros(len(x))
        for k in range(1,harm+1):
            s+= (1.0/k)*np.exp(-x*dec*(1+0.35*k))*np.sin(2*np.pi*f*k*x+ k)
        return s*amp
    def bass(f,d,amp):
        x=env_t(d)
        saw=sum((1.0/k)*np.sin(2*np.pi*f*k*x) for k in range(1,7))*np.exp(-x*5)
        sub=np.sin(2*np.pi*f*x)
        return (saw*0.45+sub*0.8)*np.minimum(1,x*200)*amp
    CH=[(220.0,261.63,329.63),(174.61,220.0,261.63),(261.63,329.63,392.0),(196.0,246.94,293.66)]  # Am F C G
    ROOT=[55.0,43.65,65.41,49.0]
    def sect(tt):
        if tt<M0: return 0
        if tt<3.9: return 1
        if tt<BRK: return 2
        if tt<FS_: return 3
        if tt<SUM: return 4
        return 5
    # ---------- sequencer on a 16th grid ----------
    step=BEAT/4
    nsteps=int((DUR-G0)/step)
    for j in range(nsteps):
        tt=G0+j*step
        if tt<M0 or tt>19.6: continue
        sc=sect(tt); bar=int((tt-G0)//(BEAT*4))%4; beat_i=int(round((tt-G0)/BEAT)) if abs(((tt-G0)/BEAT)-round((tt-G0)/BEAT))<1e-6 else None
        pos=j%16                      # 16th inside the bar
        onbeat = (pos%4==0); off8=(pos%4==2)
        # kick
        if onbeat and sc in (1,2,4,5):
            amp={1:0.55,2:0.85,4:1.0,5:1.0}[sc]
            if not (tt>=BRK and tt<FS_): add(kick_bus,kick(amp),tt)
        # clap on 2 and 4
        if pos in (4,12) and sc in (2,4,5) and not (BRK<=tt<FS_): add(drums,clap(1.0 if sc>=4 else 0.7),tt)
        # hats
        if sc in (2,4,5):
            if sc==4 and (pos%2==0 or True): add(drums,hat(0.8 if pos%4 else 0.55),tt)
            elif off8: add(drums,hat(0.9,open_=(pos==14 and sc>=4)),tt)
            if sc==2 and pos%2==0 and not off8: add(drums,hat(0.35),tt)
        # snare roll in the break/build (accelerating)
        # bass
        if sc in (2,4,5) and not (BRK<=tt<FS_) and pos%2==0:
            r=ROOT[bar]*(2 if pos%4==2 else 1)
            if sc==2 and tt<7.9 and pos%8: pass
            add(mus,bass(r,0.24,0.55 if sc==4 else 0.42),tt)
        # arp (pluck), richer in the drop
        ch=CH[bar]
        if sc in (1,2,4,5):
            arp_pat=[0,1,2,1,2,1,0,1] if sc!=4 else [0,2,1,2,0,2,1,2]
            if sc==1 and pos%2: continue
            k=arp_pat[(pos//(1 if sc==4 else 2))%8] if sc!=1 else [0,1,2,1][(pos//4)%4]
            f=ch[k]*(2 if sc in (4,5) else 1)
            a={1:0.12,2:0.16,4:0.22,5:0.22}[sc]
            add(mus,pluck(f,0.35,6.5,a),tt)
            if sc in (4,5) and pos%4==2: add(mus,pluck(ch[(k+1)%3]*4,0.25,9,0.07),tt)
        # chord stabs on offbeats in the drop
        if sc in (4,5) and pos in (6,14):
            x=env_t(0.18)
            for f in ch: add(mus,np.sin(2*np.pi*f*2*x)*np.exp(-x*16)*0.10+np.sign(np.sin(2*np.pi*f*x))*np.exp(-x*16)*0.03,tt)
    # snare roll 9.9 -> 12.2 (accelerating, rising)
    rt=FS_-2.3
    while rt<FS_:
        p=(rt-(FS_-2.3))/2.3
        gap=0.25 if p<0.4 else (0.125 if p<0.75 else 0.0625)
        add(drums,clap(0.35+0.9*p),rt); rt+=gap
    # ---------- pad (always there, swells) ----------
    pad=np.zeros(N)
    for bi in range(0,12):
        b0=G0+bi*BEAT*4
        if b0>19.6: break
        ch=CH[bi%4]; x=env_t(BEAT*4+0.3)
        e=np.minimum(1,x/0.4)*np.minimum(1,(BEAT*4+0.3-x)/0.3)
        seg=sum(np.sin(2*np.pi*f*x*(1+0.003*np.sin(2*np.pi*0.4*x)))+0.4*np.sin(2*np.pi*f*2*x) for f in ch)*e*0.05
        add(pad,seg,b0)
    pad*= np.clip((t-M0)/1.0,0,1)
    # ---------- risers / impacts ----------
    sk0,sk1=BSTART,BRK
    m=(t>=sk0)&(t<sk1); prog=np.clip((t-sk0)/(sk1-sk0),0,1)**1.6
    ph=2*np.pi*np.cumsum(np.where(m,220+prog*2200,0))/SR
    fx+=np.where(m,np.sin(ph)*0.09*prog+rng.standard_normal(N)*0.03*prog,0)
    add(fx,crash(1.8,1.0),FS_); add(fx,crash(2.4,1.1),SUM)
    add(kick_bus,kick(1.2),FS_)
    # ---------- sfx ----------
    def tone(f,d,dec,amp,harm=0.35):
        x=env_t(d); return (np.sin(2*np.pi*f*x)+harm*np.sin(2*np.pi*2*f*x))*np.exp(-x*dec)*amp
    def click(at,amp=0.45):
        x=env_t(0.06); add(fx,np.sin(2*np.pi*180*x)*np.exp(-x*60)*amp+rng.standard_normal(len(x))*np.exp(-x*90)*0.18,at)
    click(0.5)
    sw=env_t(0.45)
    add(fx,np.sin(2*np.pi*np.cumsum(300+1700*(sw/0.45)**2)/SR)*np.sin(np.pi*sw/0.45)*0.22+rng.standard_normal(len(sw))*np.sin(np.pi*sw/0.45)*0.05,0.6)
    for f in (523.25,783.99,1046.5): add(fx,np.sin(2*np.pi*f*env_t(0.5))*np.exp(-env_t(0.5)*7)*0.16,1.0)
    click(2.3); click(3.6,0.55)
    pw=env_t(0.4); add(fx,rng.standard_normal(len(pw))*np.sin(np.pi*pw/0.4)*0.07,2.45)
    rw=env_t(0.4)
    add(fx,np.sin(2*np.pi*np.cumsum(2200-1900*(rw/0.4))/SR)*np.sin(np.pi*rw/0.4)*0.22+rng.standard_normal(len(rw))*np.sin(np.pi*rw/0.4)*0.06,3.55)
    for i,x in enumerate(BUY_T):
        s=2**(i*2/12)
        add(fx,tone(659.25*s,0.35,11,0.34),x); add(fx,tone(987.77*s,0.40,9,0.32),x+0.07)
    for i,x in enumerate(SELL_T):
        s=2**(i*1.2/12)
        if True:      # full ka-ching on #1 #4 #7 #9
            tk=env_t(0.04); add(fx,rng.standard_normal(len(tk))*np.exp(-tk*80)*0.32,x)
            add(fx,tone(90,0.22,16,0.55,0),x)
            add(fx,tone(1760*s,0.6,6,0.30,0.5),x+0.03); add(fx,tone(2349*s,0.6,5,0.26,0.4),x+0.11)
            if i in (0,len(SELL_T)-1):
                for q,f in enumerate((1568,1976,2349,3136)): add(fx,tone(f*s,0.25,14,0.13,0.2),x+0.16+q*0.06)
        else:                    # light coin plink
            tk=env_t(0.03); add(fx,rng.standard_normal(len(tk))*np.exp(-tk*90)*0.18,x)
            add(fx,tone(2093*s,0.22,12,0.20,0.4),x+0.02); add(fx,tone(2794*s,0.18,14,0.14,0.3),x+0.07)
    # PNL card: boom, count-up ticks, landing chord
    bt=env_t(1.6)
    add(fx,np.sin(2*np.pi*(55*bt+20*(1-np.exp(-bt*6))))*np.exp(-bt*2.2)*0.9,SUM)
    for q in range(14): add(fx,tone(1200+q*55,0.05,60,0.10,0),SUM+0.55+q*0.088)
    for f in (261.63,329.63,392.0,523.25): add(fx,np.sin(2*np.pi*f*bt)*np.exp(-bt*1.5)*0.14,SUM+1.8)
    add(fx,tone(1318.5,0.9,4,0.2),SUM+1.8); add(fx,tone(1975.5,0.9,4,0.17),SUM+1.85)
    # ---------- mix: sidechain pump on melodic bus, duck under signals ----------
    tb=((t-G0)%BEAT)
    pump=1-0.6*np.exp(-tb/0.11); pump=np.where(t<M0,1,pump)
    melodic=(mus+pad)*pump
    sig_t=BUY_T+SELL_T+[2.3,3.6]
    duck=np.ones(N)
    for x in sig_t:
        i=int(x*SR); j=min(N,i+int(0.35*SR)); duck[i:j]=np.minimum(duck[i:j],0.6)
    duck=np.convolve(duck,np.ones(int(0.03*SR))/int(0.03*SR),mode='same')
    music=(melodic*1.0+kick_bus*0.9+drums*0.8)*duck
    # gentle low-pass in the intro so the track "opens up" at the buys
    def onepole(x,a):
        y=np.empty_like(x); acc=0.0
        for i in range(len(x)): acc+=a*(x[i]-acc); y[i]=acc
        return y
    seg=slice(int(M0*SR),int(3.9*SR)); lp=onepole(music[seg],0.12); music[seg]=lp*0.9+music[seg]*0.1
    out=music*0.85+fx*1.0
    out*=np.clip((DUR-t)/0.5,0,1)
    out=np.tanh(out*1.1)                                  # soft clip glue
    out=out/np.max(np.abs(out))*0.9
    rm=np.sqrt(np.mean((music*0.85)**2)); rf=np.sqrt(np.mean(fx**2))
    print('rms music %.3f fx %.3f'%(rm,rf))
    w=wave.open(wav_path,'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR); w.writeframes((out*32767).astype(np.int16).tobytes()); w.close()
    print('ok')


def encode(path):
    tmp = path + '.part.mp4'
    cmd = ['ffmpeg', '-y', '-v', 'error', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', '%dx%d' % (W, H), '-r', str(FPS), '-i', '-',
           '-c:v', 'libx264', '-crf', '18', '-preset', 'veryfast', '-pix_fmt', 'yuv420p', '-t', str(DUR), '-f', 'mp4', tmp]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(NF): p.stdin.write(draw_frame(i).tobytes())
    p.stdin.close(); rc = p.wait()
    if rc == 0: os.rename(tmp, path)
    return rc

if KEY:
    for ts in KEY: draw_frame(int(round(ts * FPS))).save(os.path.join(ARGS.keydir, 'pump_key_%s.png' % ts))
    sys.exit(0)
silent = OUT + '.silent.mp4'
rc = encode(silent)
if rc == 0 and not ARGS.no_audio:
    wav = OUT + '.wav'
    make_audio(wav, BUY_T, sorted(set(G_T)), B_START, FS, SUM_T)
    subprocess.check_call(['ffmpeg', '-y', '-v', 'error', '-i', silent, '-i', wav, '-map', '0:v', '-map', '1:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k', '-shortest', OUT + '.mux.mp4'])
    os.rename(OUT + '.mux.mp4', OUT); os.remove(wav); os.remove(silent)
elif rc == 0:
    os.rename(silent, OUT)
print('rc', rc, 'timeline: buys', BUY_T, 'sell groups', G_T, 'card', SUM_T)

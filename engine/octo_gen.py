import numpy as np

def make_params(seed):
    r = np.random.default_rng(seed)
    return dict(seed=seed,
                shortlist=int(r.integers(30, 51)),          # tokens passing the filter today (30-50)
                scanned=int(r.integers(6000, 10001)),       # new tokens scanned today
                start=int(r.integers(500, 1001)),           # starting capital USD
                profit=int(r.integers(5000, 20001)),        # final profit USD
                trades=int(r.integers(24, 37)),             # trades shown (24-36)
                winrate=float(r.uniform(0.65, 0.78)))

def make_trades(p):
    """Deterministic trade list. Sum of PnL == profit exactly, first and last trade win."""
    r = np.random.default_rng(p['seed'] + 1)
    n = p['trades']; start = float(p['start']); target = start + p['profit']
    nw = max(2, int(round(n * p['winrate']))); nl = n - nw
    order = np.array([1] * nw + [0] * nl); r.shuffle(order)
    if order[0] == 0:
        j = int(np.where(order == 1)[0][0]); order[0], order[j] = order[j], order[0]
    if order[-1] == 0:
        j = int(np.where(order == 1)[0][-1]); order[-1], order[j] = order[j], order[-1]
    w = r.uniform(0.35, 1.0, nw); l = -r.uniform(0.07, 0.20, nl)
    lo, hi = 0.0, 50.0
    for _ in range(200):                                    # bisection on win scale k
        mid = (lo + hi) / 2
        if start * np.prod(1 + mid * w) * np.prod(1 + l) < target: lo = mid
        else: hi = mid
    k = (lo + hi) / 2
    ret = np.zeros(n); wi = li = 0
    for i in range(n):
        if order[i]: ret[i] = k * w[wi]; wi += 1
        else: ret[i] = l[li]; li += 1
    bal = [start]
    for i in range(n): bal.append(round(bal[-1] * (1 + ret[i]), 2))
    bal[-1] = target                                        # exact end balance
    tr = []
    for i in range(n):
        pnl = bal[i + 1] - bal[i]
        tr.append(dict(win=bool(order[i]), pnl=pnl, before=bal[i], after=bal[i + 1], ret=pnl / bal[i]))
    return tr

if __name__ == '__main__':
    bad = 0
    for seed in range(300):
        p = make_params(seed); tr = make_trades(p)
        s = sum(t['pnl'] for t in tr)
        ok = (abs(s - p['profit']) < 0.01 and tr[0]['win'] and tr[-1]['win']
              and all(t['ret'] > -0.25 for t in tr) and tr[0]['ret'] < 1.5)
        mx = max(t['ret'] for t in tr)
        if not ok: bad += 1; print('BAD', seed, p, round(s, 2), round(mx, 2))
    print('bad', bad, 'of 300')
    rr = [max(t['ret'] for t in make_trades(make_params(s))) for s in range(300)]
    print('max single-trade return: median %.2f  p95 %.2f  max %.2f' % (np.median(rr), np.percentile(rr, 95), max(rr)))

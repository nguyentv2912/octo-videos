import os as _os
_BASE = _os.path.dirname(_os.path.abspath(__file__))
import json, os, sys
sys.path.insert(0, _BASE)
import numpy as np
import octo_gen
_p = os.environ.get('OCTO_CFG', _os.path.join(_BASE, 'octo_cfg.json'))
CFG = json.load(open(_p))
SEED = CFG['seed']; START = float(CFG['start']); PROFIT = float(CFG['profit']); TARGET = START + PROFIT
NT = CFG['trades']; SHORT = CFG['shortlist']; SCANNED = CFG['scanned']; NAME = CFG.get('name', 'OCTO AI')
_NAMES = ["NEBU", "PUMPKY", "KRAKI", "ZAPPY", "MOONPIE", "GLITCH", "VOLTA", "SHRIMPY", "BYTEY", "NOVAX",
          "TIDAL", "ORBIT", "PIXLE", "COSMO", "DRIFT", "FLUXO", "QUARK", "SPARKO", "LUMEN", "TURBO7",
          "COBALT", "MANTA", "HYPERX", "RIPPLY", "ECHOZ", "BLITZY", "ASTRO9", "NEONY", "OCTAVE", "PLASMA",
          "JELLYX", "BOLTIE", "MIRAGE", "TOFFY", "ZENIQ", "KOALAX", "FIZZLE", "NIMBUS", "CRISPY", "WOBBLE",
          "YETIX", "PRISMO", "GLIMMR", "OZZIE", "TANGO7", "SPUDDY", "MOCHIX", "RUMBLE", "SNAPPY", "FROSTY"]
def tokens():
    r = np.random.default_rng(SEED + 7)
    names = list(_NAMES); r.shuffle(names)
    return names
def build_trades(tokens_):
    tr = octo_gen.make_trades(CFG)
    for i, t in enumerate(tr): t['token'] = tokens_[i]
    return tr

CTA = CFG.get('cta', 'OCTO')

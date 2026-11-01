"""PROTOTYPE, throw away. Is the tuner's score diluted by cells both sounds leave silent?

Applies audible faults to the target itself, so the true answer is known: identical except for the fault.
"""
import json, sys
from pathlib import Path

import numpy as np

import patch as p
import tune as t

scratch = Path(sys.argv[1])
p.BASE = scratch / "base.pkl"
key = json.loads((scratch / "key.json").read_text())


def floor_share(f, g):
    out = {}
    for k in f:
        both = (f[k] <= t.FLOOR + 1e-6) & (g[k] <= t.FLOOR + 1e-6)
        out[k] = round(float(both.mean()) * 100)
    return out


for job, label in sorted(key.items(), key=lambda kv: kv[1]):
    a = np.load(scratch / "jobs" / job / "target.npy")
    f = t.features(a)
    st = json.loads((scratch / "jobs" / job / "state.json").read_text())
    r = json.loads((scratch / "jobs" / job / "rules.json").read_text())
    note = r["note"]
    g = t.features(t.render_values(r["design"], r["values"], note))
    quiet = t.score(t.features(a * 0.5), f)
    ramp = np.minimum(np.arange(a.shape[1]) / (0.25 * 44100), 1.0)
    slow = t.score(t.features(a * ramp), f)
    cut = a.copy()
    cut[:, 66150:] *= np.exp(-np.arange(a.shape[1] - 66150) / 2205)
    short = t.score(t.features(cut), f)
    print(label)
    print(f"   6 dB quieter scores {quiet:.2f}; 0.25 s attack {slow:.2f}; note cut at 1.5 s {short:.2f}; rules result {t.score(g, f):.2f}")
    print("   parts of the rules result: " + str({k: round(v, 2) for k, v in t.parts(g, f).items()}))

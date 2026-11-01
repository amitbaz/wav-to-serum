"""PROTOTYPE, throw away. Why can the tuner's score be near zero while the gap is 20?

Synthetic patches only. No test sound.
"""
import sys
from pathlib import Path

import numpy as np

import compare as c
import loop
import patch as p
import tune as t

scratch = Path(sys.argv[1])
p.BASE = scratch / "base.pkl"


def terms(a, b):
    f, g = t.features(a), t.features(b)
    return {k: round(float(np.abs(f[k] - g[k]).mean()), 2) for k in f}


def by_level(a, b, n_fft=2048, hop=512):
    x, y = c.spec_db(a, n_fft, hop), c.spec_db(b, n_fft, hop)
    top = max(x.max(), y.max())
    level = top - np.maximum(x, y)
    rows = []
    d = np.abs(x - y)
    total = d[level < 60].sum()
    for lo, hi in [(0, 20), (20, 30), (30, 40), (40, 50), (50, 60)]:
        k = (level >= lo) & (level < hi)
        rows.append(f"{lo}-{hi}dB down: {k.mean()*100:4.1f}% of bins, mean diff {d[k].mean() if k.any() else 0:5.1f}, {d[k].sum()/total*100:3.0f}% of gap")
    return rows


if __name__ == "__main__":
    for i in (0, 1):
        d, v, note = loop.SYNTHETIC[i]
        target = t.render_values(d, v, note)
        tuner = t.Tuner(scratch, target, note)
        s, best, used, _ = tuner.tune(d, 1500, 1, {n: st for n, (_, st) in p.knobs(d).items()})
        tuner.close()
        audio = t.render_values(d, best, note)
        print(f"patch {i}: score {s:.2f} gap {c.gap(target, audio):.2f} residual {c.residual_db(target, audio):.1f} dB rms {np.sqrt((audio**2).mean())/np.sqrt((target**2).mean()):.3f}x")
        print("  terms", terms(target, audio))
        print("  gap at floors", {fl: round(c.gap(target, audio, floor=fl), 2) for fl in (20, 30, 40, 50, 60)})
        print("  knob error", {n: round(best[n] - v.get(n, st), 2) for n, (_, st) in p.knobs(d).items() if abs(best[n] - v.get(n, st)) > 0.1})
        for r in by_level(target, audio):
            print("  ", r)
        nudged = t.render_values(d, {**v, "master": v.get("master", p.knobs(d)["master"][1]) + 0.004}, note)
        print(f"  same patch, 0.1 dB level change: gap {c.gap(target, nudged):.2f}")
        f1 = dict(v)
        f1["osc0_fine"] = v.get("osc0_fine", 0.5) + 0.002
        print(f"  same patch, 0.1 cent pitch change: gap {c.gap(target, t.render_values(d, f1, note)):.2f}, score {t.score(t.features(target), t.features(t.render_values(d, f1, note))):.2f}")

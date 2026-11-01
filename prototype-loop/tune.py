"""PROTOTYPE, throw away. Score a render against a target, and search knob values with CMA-ES.

The tuner sees only numbers and a score. The gap is reported, never searched on.
"""
import time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np
from scipy.signal import stft

import compare

SR = 44100
FLOOR = -70.0
_fb = {}


def mel_bank(n_fft, n=64):
    if n_fft not in _fb:
        hz = np.fft.rfftfreq(n_fft, 1 / SR)
        mel = lambda f: 2595 * np.log10(1 + f / 700)
        pts = 700 * (10 ** (np.linspace(mel(30), mel(18000), n + 2) / 2595) - 1)
        fb = np.zeros((n, len(hz)))
        for i in range(n):
            a, b, c = pts[i : i + 3]
            fb[i] = np.clip(np.minimum((hz - a) / (b - a), (c - hz) / (c - b)), 0, None)
        _fb[n_fft] = fb / (fb.sum(axis=1, keepdims=True) + 1e-9)
    return _fb[n_fft]


def _mel_db(x, n_fft):
    _, _, z = stft(x, nperseg=n_fft, noverlap=n_fft - n_fft // 4, boundary=None, padded=False)
    return np.maximum(10 * np.log10(mel_bank(n_fft) @ (np.abs(z) ** 2) + 1e-12), FLOOR)


def features(a):
    mono, side = a.mean(axis=0), (a[0] - a[1]) / 2
    f = {f"m{n}": _mel_db(mono, n) for n in (256, 1024, 4096)}
    f["s1024"] = _mel_db(side, 1024)
    _, _, z = stft(mono, nperseg=8192, noverlap=6144, boundary=None, padded=False)
    f["fine"] = np.maximum(20 * np.log10(np.abs(z[:800]) + 1e-6), FLOOR)  # pitch, up to 4.3 kHz
    e = (mono**2 + side**2)
    n = len(e) // 220
    f["env"] = np.maximum(10 * np.log10(e[: n * 220].reshape(n, 220).mean(axis=1) + 1e-12), FLOOR)
    return f


WEIGHTS = {"m256": 1.0, "m1024": 1.0, "m4096": 1.0, "fine": 1.0, "s1024": 0.25, "env": 1.0}


def score(f, g):
    return float(sum(w * np.abs(f[k] - g[k]).mean() for k, w in WEIGHTS.items()) / sum(WEIGHTS.values()))


# Workers ----------------------------------------------------------------------------

_target = {}


def _init(base, feats, note):
    import patch

    patch.BASE = base
    _target.update(feats=feats, note=note)


def _eval(job):
    import patch, render

    design, values = job
    a = render.render_tree(patch.build(design, values), _target["note"])
    if not np.isfinite(a).all() or abs(a).max() > 8:
        return 1e3
    return score(features(a), _target["feats"])


class Tuner:
    def __init__(self, scratch, target_audio, note, workers=8):
        self.base = Path(scratch) / "base.pkl"
        self.note = note
        self.feats = features(target_audio)
        self.pool = get_context("spawn").Pool(workers, _init, (self.base, self.feats, note))
        self.workers = workers

    def close(self):
        self.pool.close()
        self.pool.join()

    def tune(self, design, budget, seed, start=None, log=None):
        """Returns (best score, best {name: 0..1}, evaluations used, history)."""
        import patch

        spec = patch.knobs(design)
        names = list(spec)
        x0 = [float(np.clip((start or {}).get(n, spec[n][1]), 0.02, 0.98)) for n in names]
        es = cma.CMAEvolutionStrategy(x0, 0.18, {"bounds": [0, 1], "popsize": max(16, 4 + 2 * len(names) // 2), "seed": seed + 1, "verbose": -9, "CMA_diagonal": 40})
        best, used, hist = float("inf"), 0, []
        best_x = x0
        while used < budget and not es.stop():
            xs = es.ask()
            fs = self.pool.map(_eval, [(design, dict(zip(names, map(float, x)))) for x in xs], chunksize=1)
            es.tell(xs, fs)
            used += len(xs)
            i = int(np.argmin(fs))
            if fs[i] < best:
                best, best_x = fs[i], [float(v) for v in xs[i]]
            hist.append((used, round(best, 3)))
            if log:
                log(used, best)
        return best, dict(zip(names, best_x)), used, hist


def render_values(design, values, note, velocity=100):
    import patch, render

    return render.render_tree(patch.build(design, values), note, velocity)

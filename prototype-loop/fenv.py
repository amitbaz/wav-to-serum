"""PROTOTYPE, throw away. "Step 4: add a filter envelope", method 2's filter envelope piece.

Reads the cutoff knob frame by frame from the target, against the candidate's own table frame, then fits Env 2's shape and
amount to that track. Measured on renders: the cutoff knob moves by amount/100 times Env 2's level, up or down.
"""
import functools, json

import numpy as np

import analyse as an
import parts as pt
import step2 as s2

SR, HOP, WIN = 44100, 441, 4096
OFF = 2.0  # note-off, seconds: the render holds the note 2 s
SLOPE = {"MgL6": 6, "MgL12": 12, "MgL18": 18, "MgL24": 24, "LadderMg": 24}
LO = 1.6  # below this harmonic the fundamental hides the corner
# v2: every harmonic up to 16 kHz (at most 96), not the library's 24: with 24, 6 of 10 adjust sweeps were never seen.
NH = lambda f0: int(min(96, 16000 / f0))
HI = lambda f0: 0.8 * NH(f0)  # above this the table runs out


def _map():
    """Corner the reader finds (Hz) -> cutoff knob, per type, from still saws (fenv_cal.py)."""
    out = {}
    for typ, rows in json.load(open("step4_corner.json")).items():
        f = lambda n: 440 * 2 ** ((n - 69) / 12)
        r = np.array([(k, hz) for k, n, hz, _ in rows if k > 0.05 and LO < hz / f(n) < HI(f(n))])
        for _ in range(2):
            p = np.polyfit(np.log2(r[:, 1]), r[:, 0], 3)
            r = r[abs(r[:, 0] - np.polyval(p, np.log2(r[:, 1]))) < 0.1]
        out[typ] = p
    return out


try:
    MAP = _map()
except FileNotFoundError:  # while calibrating
    MAP = None


def harm_db(x, f0, nh):
    s = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    b = f0 * len(x) / SR
    w = max(1, int(0.25 * b))
    return np.array([20 * np.log10(s[max(0, int(round(k * b)) - w) : int(round(k * b)) + w + 1].max() + 1e-9) for k in range(1, nh + 1)])


@functools.lru_cache(maxsize=64)
def _frames_of(table):
    return pt.table_frames(an.TABLES / table)


def table_db(table, pos, nh):
    """The table frame at pos, a linear blend of the two nearest frames as Serum morphs, in dB per harmonic."""
    F = _frames_of(table)
    f = pos * (len(F) - 1); i = int(f); w = f - i
    m = np.abs(np.fft.rfft((1 - w) * F[i] + w * F[min(i + 1, len(F) - 1)]))[1 : nh + 1]
    d = 20 * np.log10(m + 1e-9)
    return np.maximum(d - d.max(), -90)


def frames(target, f0):
    """Harmonic levels in dB per 10 ms frame over the held note, and each frame's loudness."""
    mono, nh = target.mean(axis=0), NH(f0)
    hs, lv, ts = [], [], []
    for i in range(0, int(OFF * SR) - WIN, HOP):
        x = mono[i : i + WIN]
        hs.append(harm_db(x, f0, nh)); lv.append(10 * np.log10((x**2).mean() + 1e-14)); ts.append((i + WIN / 2) / SR)
    return np.array(ts), np.array(hs), np.array(lv)


def track(F, frame_db, slope, peak_db=0.0):
    """Corner per frame (harmonics): the low-pass with a resonant peak that best turns the table frame into the frame heard."""
    nh = F.shape[1]
    kc = np.geomspace(0.5, nh * 1.5, 200)
    k = np.log2(np.arange(1, nh + 1))
    lk = np.log2(kc)[:, None]
    shapes = -slope * np.maximum(k - lk, 0) + peak_db * np.exp(-0.5 * ((k - lk) / 0.2) ** 2)
    out = []
    for h in F:
        keep = (h > h.max() - 60) & (frame_db > -60)
        d = (h - frame_db)[keep][None, :] - shapes[:, keep]
        d = d - d.mean(axis=1, keepdims=True)
        err = np.sqrt((np.clip(d, -30, 30) ** 2).mean(axis=1))
        out.append(kc[int(np.argmin(err))])
    return np.array(out)


def curve(A, D, S, t):
    """Env 2's level while the note is held, read off sweeps with known settings: like the amp envelope (parts.adsr_curve),
    sustain S moves the cutoff by S squared and the decay is squared; the attack is squared too."""
    x = np.clip((t - A) / D, 0, 1)
    return np.where(t < A, (t / max(A, 1e-4)) ** 2, S**2 + (1 - S**2) * (1 - x) ** 2)


def fit(ts, knob, w):
    """knob(t) = k0 + amount/100 * curve(t): grid over the shape, least squares for k0 and amount."""
    best = (np.inf, None)
    for A in np.geomspace(5e-4, 1.0, 14):
        for D in np.geomspace(0.03, 4.0, 18):
            for S in np.linspace(0, 1, 21):
                E = curve(A, D, S, ts)
                X = np.stack([np.ones_like(E), E], axis=1) * w[:, None]
                coef, *_ = np.linalg.lstsq(X, knob * w, rcond=None)
                err = float((((X @ coef) - knob * w) ** 2).sum())
                if err < best[0]:
                    best = (err, (A, D, S, float(coef[0]), float(coef[1]) * 100))
    A, D, S, k0, amt = best[1]
    return {"attack": float(A), "decay": float(D), "sustain": float(S), "k0": float(np.clip(k0, 0, 1)), "amount": float(np.clip(amt, -100, 100))}


def read(target, f0, table, pos, typ, peak_db=0.0, cache=None):
    """The candidate's filter knob and Env 2, read from the target."""
    ts, F, lv = cache if cache is not None else frames(target, f0)
    kc = track(F, table_db(table, pos, F.shape[1]), SLOPE[typ], peak_db)
    knob = np.clip(np.polyval(MAP[typ], np.log2(kc * f0)), 0, 1)
    w = ((lv > lv.max() - 40) & (kc > LO) & (kc < HI(f0))).astype(float)
    if w.sum() < 5:  # nothing to read: a still filter
        return None
    return fit(ts, knob, w) | {"track": knob, "ts": ts, "w": w}

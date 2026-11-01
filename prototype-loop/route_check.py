"""PROTOTYPE, throw away. Mac route or DawDreamer: which is closer to Ableton, on the four sounds they differ on?

Rule from the ticket: if Mac is clearly further from Ableton than DawDreamer is, and outside Ableton's
own variation, stop. Clearly further means more than 0.25 dB past DawDreamer, the margin from
"Compare renders with Serum in a DAW". Scored on the whole 3 s, and on the last 1 s for how it ends.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

import compare as c

SCRATCH, BOUNCES = Path(sys.argv[1]), Path.home() / "Desktop/w2s-bounces"
SOUNDS = ["Lead_2", "Lead_3", "Synth_2", "Synth_3"]


def wav(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    assert sr == 44100, f"{path.name} is {sr} Hz"
    assert a.shape[1] == 2, f"{path.name} is not stereo"
    return a.T


def aligned(a, b):
    """Remove the small latency offset: b moved earlier to line up with a, both trimmed."""
    k = c.offset(a, b)
    b = b[:, k:]
    n = min(a.shape[1], b.shape[1])
    return a[:, :n], b[:, :n], k


rows = []
for s in SOUNDS:
    A, B = wav(BOUNCES / f"{s}.a.wav"), wav(BOUNCES / f"{s}.b.wav")
    print(f"{s}: lengths {A.shape[1]/44100:.3f}s {B.shape[1]/44100:.3f}s peak {abs(A).max():.3f}")
    self_gap = c.gap(A, B)
    self_tail = c.gap(A[:, 88200:], B[:, 88200:])
    res = {}
    for route in ("mac", "daw"):
        r = np.load(SCRATCH / "routes" / f"{s}.{route}.npy")
        scores, tails, offs = [], [], []
        for L in (A, B):
            x, y, k = aligned(L, r)
            scores.append(c.gap(x, y))
            tails.append(c.gap(x[:, 88200:], y[:, 88200:]))
            offs.append(k)
        res[route] = (float(np.mean(scores)), float(np.mean(tails)), offs)
    m, d = res["mac"], res["daw"]
    limit = max(1.0, self_gap + 0.25)
    further = m[0] > d[0] + 0.25 and m[0] > limit
    further_tail = m[1] > d[1] + 0.25 and m[1] > max(1.0, self_tail + 0.25)
    print(f"  Ableton vs itself {self_gap:.2f} (tail {self_tail:.2f})  Mac {m[0]:.2f} (tail {m[1]:.2f}, offset {m[2]})  DawDreamer {d[0]:.2f} (tail {d[1]:.2f}, offset {d[2]})")
    print(f"  Mac clearly further: {further}, in the tail: {further_tail}")
    rows.append(further or further_tail)
print("STOP: move to DawDreamer" if any(rows) else "Mac route stands")

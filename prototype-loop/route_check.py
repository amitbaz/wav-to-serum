"""PROTOTYPE, throw away. Mac route or DawDreamer: which is closer to Ableton, on the four sounds they differ on?

Rule from the ticket: if Mac is clearly further from Ableton than DawDreamer is, and outside Ableton's
own variation, stop. Clearly further means more than 0.25 dB past DawDreamer, the margin from
"Compare renders with Serum in a DAW". Only the held first 2 s are scored: in these bounces the note
never ended, so they say nothing about how a sound ends. Live against itself is the floor.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

import compare as c

SCRATCH, BOUNCES = Path(sys.argv[1]), Path.home() / "Desktop/w2s-bounces"
SOUNDS = ["Lead_2", "Lead_3", "Synth_2", "Synth_3"]
END = 2 * 44100


def wav(path):
    a, sr = sf.read(path, dtype="float32", always_2d=True)
    assert sr == 44100 and a.shape[1] == 2, path.name
    return a.T


stop = False
for s in SOUNDS:
    A, B = wav(BOUNCES / f"{s}_a.wav")[:, :END], wav(BOUNCES / f"{s}_b.wav")[:, :END]
    full = {r: np.load(SCRATCH / "routes" / f"{s}.{r}.npy") for r in ("mac", "daw")}
    own = c.gap(A, B)
    mac, daw = [float(np.mean([c.gap(L, full[r][:, :END]) for L in (A, B)])) for r in ("mac", "daw")]
    further = mac > daw + 0.25 and mac > max(1.0, own + 0.25)
    stop |= further
    print(f"{s}: Live vs itself {own:.2f}  Mac {mac:.2f}  DawDreamer {daw:.2f}  limit {max(1.0, own + 0.25):.2f}  "
          f"Mac vs DawDreamer: first 2 s {c.gap(full['mac'][:, :END], full['daw'][:, :END]):.2f}, last 1 s {c.gap(full['mac'][:, END:], full['daw'][:, END:]):.2f}  clearly further: {further}")
print("STOP: move to DawDreamer" if stop else "Mac route stands on the first 2 s")

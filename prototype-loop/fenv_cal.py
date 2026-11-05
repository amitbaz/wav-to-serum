"""PROTOTYPE, throw away. Calibrates fenv.py's reader: still saws at a grid of cutoff knobs, per type and note, and the corner
the reader finds on each (median over frames). Writes step4_corner.json: type -> [(knob, note, corner_hz)]."""
import json, os, pickle
os.environ.setdefault("SET", "scratch4")
import numpy as np
import fenv, render as rd, step4 as s4

TB = "Analog/MB Saw.wav"
env = {"attack": 0.001, "decay": 1, "sustain": 1, "release": 0.1}
out = {}
for typ in fenv.SLOPE:
    out[typ] = []
    for note in (36, 48, 60):
        f0 = 440 * 2 ** ((note - 69) / 12)
        for k in np.arange(0, 1.001, 0.025):
            a = rd.render_tree(s4._build(TB, 0.0, env, {"type": typ, "knob": float(k), "reso": 0.0, "cutoff_hz": 0}), note)
            ts, F, lv = fenv.frames(a, f0)
            kc = fenv.track(F[ts > 0.2], fenv.table_db(TB, 0.0, F.shape[1]), fenv.SLOPE[typ])
            out[typ].append((round(float(k), 3), note, round(float(np.median(kc) * f0), 1), 1))
        print(typ, note, out[typ][-41::5], flush=True)
json.dump(out, open("step4_corner.json", "w"))

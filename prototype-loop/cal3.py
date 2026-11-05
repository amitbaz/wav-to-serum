"""PROTOTYPE, throw away. Resonance knob -> peak height (dB) at the cutoff, per filter type: a saw at C1, cutoff near harmonic 8."""
import json, numpy as np, analyse as an, patch, render as rd, step2 as s2
f0 = 440 * 2 ** ((24 - 69) / 12)
def tree(typ, reso):
    t = patch.blank(); patch.pp(t["Env0"])["kParamSustain"] = 1.0
    if typ: s2.set_filter(t, {"type": typ, "knob": s2.hz_to_knob(8 * f0, typ), "reso": reso})
    return t
harm = lambda a: an.harmonics(a.mean(axis=0)[22050:22050 + 65536], f0)[0]
out = {}
for typ in s2.TYPES:
    base = harm(rd.render_tree(tree(typ, 0.0), 24)); rows = []
    for reso in range(0, 101, 10):
        d = harm(rd.render_tree(tree(typ, float(reso)), 24)) - base
        d = d - d[0]
        rows.append((reso, round(float(d[3:16].max()), 1), int(np.argmax(d[3:16]) + 4)))
    out[typ] = rows; print(typ, rows, flush=True)
json.dump(out, open("step2_reso.json", "w"))

"""PROTOTYPE, throw away. Does the score prefer a flat sound to the true movement slightly retimed?

retimed: every LFO rate, detune and fine offset x1.12. Same character, the wobble drifts out of step.
flat:    LFO routes at 0, fine offsets and detune at 0. Movement gone.
"""
import copy, csv, sys
from pathlib import Path
import numpy as np, soundfile as sf
import serum2_preset_loader as s
import compare as c, render as r, tune as t

work = Path(sys.argv[1])
paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
NOTES = {"Bass": 36, "Lead": 60, "Synth": 48}
LFO_SRC = range(6, 16)


def pp(n):
    return n["plainParams"] if isinstance(n.get("plainParams"), dict) else {}


def variant(tree, how):
    x = copy.deepcopy(tree)
    for k, n in x.items():
        if not isinstance(n, dict):
            continue
        if k.startswith("LFO") and how == "retimed" and "kParamRate" in pp(n):
            pp(n)["kParamRate"] *= 1.12
        if k.startswith("Oscillator"):
            for q in ("kParamFine", "kParamDetune"):
                if q in pp(n):
                    pp(n)[q] = pp(n)[q] * 1.12 if how == "retimed" else 0.0
        if k.startswith("ModSlot") and how == "flat" and n.get("source") and n["source"][0] in LFO_SRC:
            pp(n)["kParamAmount"] = 0.0
    return x


print("sound    variant   score  near  (parts)")
for label in sys.argv[2:]:
    _, tree = s.decode_preset_file(paths[label])
    note = NOTES[label.split()[0]]
    T = r.render_tree(tree, note)
    f = t.features(T)
    for how in ("retimed", "flat"):
        a = r.render_tree(variant(tree, how), note)
        p = t.parts(t.features(a), f)
        print(f"{label:8} {how:8} {t.score(t.features(a), f):6.2f} {c.near(T, a):6.2f}  " + " ".join(f"{k}={v:.1f}" for k, v in p.items()), flush=True)
        sf.write(work / "oracle" / f"{label.replace(' ', '')}_{how}.wav", a.T, 44100, subtype="FLOAT")

"""PROTOTYPE, throw away. Does the writer do what it says?

1. A blank tree renders like Serum with nothing loaded.
2. Every knob and every choice changes the sound; a knob with no effect means a wrong key.
"""
import copy, hashlib, json, os, pickle, subprocess, sys
from pathlib import Path

import numpy as np
import serum2_preset_loader as s

import compare as c
import patch as p
import render as r

SCRATCH = Path(sys.argv[1])
p.BASE = SCRATCH / "base.pkl"
NOTE = 48
listed = {x["sha256"] for x in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}


def make_base():
    found = subprocess.run(["mdfind", 'kMDItemFSName == "*.SerumPreset"'], capture_output=True, text=True).stdout.split("\n")
    for path in sorted((x for x in found if x and "Serum 2 Presets" in x), key=os.path.getsize):
        if hashlib.sha256(Path(path).read_bytes()).hexdigest() in listed:
            continue
        header, t = s.decode_preset_file(path)
        if all(not (isinstance(t[f"Oscillator{i}"].get("plainParams"), dict) and "kParamType" in t[f"Oscillator{i}"]["plainParams"]) for i in range(3)):
            pickle.dump(t, open(p.BASE, "wb"))
            pickle.dump(header, open(SCRATCH / "header.pkl", "wb"))
            return


FULL = {
    "osc": [
        {"table": "S2 Tables/Default Shapes.wav", "octave": 0, "warp": "kSync", "unison": True},
        {"table": "Analog/Basic Shapes.wav", "octave": -1, "warp": None, "unison": False},
    ],
    "sub": True, "noise": True, "filter": "MgL24",
    "routes": ["filter_env", "table_env", "table_lfo", "pitch_lfo", "cutoff_lfo"],
    "fx": [p.DIST, p.CHORUS, p.DELAY, p.REVERB],
}


def render(d, v):
    return r.render_tree(p.build(d, v), NOTE)


if __name__ == "__main__":
    make_base()
    t, fresh = r.render_tree(p.blank(), NOTE), r.render_tree(None, NOTE)
    print("blank peak", round(float(abs(t).max()), 3), "fresh peak", round(float(abs(fresh).max()), 3), "gap", round(c.gap(t, fresh), 3), "residual dB", round(c.residual_db(t, fresh), 1))
    d = copy.deepcopy(FULL)
    start = {n: s_ for n, (_, s_) in p.knobs(d).items()}
    start.update(cutoff=0.25, filter_env_amt=0.45)  # keep the filter off its stop so routes can be heard
    base = render(d, start)
    print("full design peak", round(float(abs(base).max()), 3), "knobs", len(start))
    dead = []
    for n in start:
        v = dict(start)
        v[n] = 1.0 if start[n] < 0.5 else 0.0
        out = render(d, v)
        g = c.gap(base, out)
        if g < 0.02:
            dead.append(n)
        print(f"  {n:18s} gap {g:6.2f}")
    print("DEAD:", dead)

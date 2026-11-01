"""PROTOTYPE, throw away. Render targets, hidden notes and the wrong-sound yardstick. No tuning.

Jobs get random letters so the designer cannot tell which sound it has. Renders stay in the scratchpad.
"""
import csv, json, random, sys
from pathlib import Path

import numpy as np

import compare as c
import render as r

scratch = Path(sys.argv[1])
SOUNDS = ["Bass 1", "Lead 1", "Synth 1", "Bass 2", "Lead 4", "Synth 4"]
listing = json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]
kinds = {x["label"]: x["kind"] for x in listing if x["set"] == "test"}
paths = dict(csv.reader(open(scratch / "paths.tsv"), delimiter="\t"))
letters = random.Random(18).sample("ABCDEF", 6)
key = {}
for label, job in zip(SOUNDS, letters):
    d = scratch / "jobs" / job
    d.mkdir(parents=True, exist_ok=True)
    note = r.NOTES[kinds[label]]
    np.save(d / "target.npy", r.render_file(paths[label], note))
    hidden = scratch / "hidden" / job
    hidden.mkdir(parents=True, exist_ok=True)
    np.save(hidden / "down.npy", r.render_file(paths[label], note - 12))
    np.save(hidden / "up.npy", r.render_file(paths[label], note + 12))
    np.save(hidden / "soft.npy", r.render_file(paths[label], note, 40))
    others = [c.near(np.load(d / "target.npy"), r.render_file(paths[o], note)) for o in kinds if o != label]
    key[job] = label
    (hidden / "wrong.json").write_text(json.dumps({"near_median": float(np.median(others)), "near_min": float(min(others))}))
    print(label, job, "wrong sound near: median", round(float(np.median(others)), 2), "closest", round(min(others), 2), flush=True)
(scratch / "key.json").write_text(json.dumps(key))

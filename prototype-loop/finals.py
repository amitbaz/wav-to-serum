"""PROTOTYPE, throw away. After both arms finish: retune with 3 seeds, hidden notes, listening files.

  python finals.py SCRATCH JOB [JOB ...]

Listening files go to ~/Desktop/w2s-listen under random names. The key stays in the scratchpad.
Hidden notes run once here and are never shown to either arm.
"""
import json, random, sys
from pathlib import Path

import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import analyse as an
import compare as c
import loop
import patch as p
import rules
import tune as t

SEEDS = (11, 12, 13)


def arm_result(job, arm):
    if arm == "rules":
        r = json.loads((job / "rules.json").read_text())
        return r["design"], r["values"], r["first_near"]
    st = json.loads((job / "state.json").read_text())
    return st["best"]["design"], st["best"]["values"], st["first_near"]


def main():
    scratch = Path(sys.argv[1])
    p.BASE = scratch / "base.pkl"
    key = json.loads((scratch / "key.json").read_text())
    listen = Path.home() / "Desktop/w2s-listen"
    listen.mkdir(exist_ok=True)
    out, ears, names = {}, {}, random.Random(1802)
    pool = names.sample(range(100, 999), 200)
    for name in sys.argv[2:]:
        job = scratch / "jobs" / name
        audio = np.load(job / "target.npy")
        target = loop.report(audio)
        note = int(round(target["midi"]))
        ranking = an.rank_tables(target["harmonics_db"], scratch)
        wrong = json.loads((scratch / "hidden" / name / "wrong.json").read_text())
        row = {"sound": key[name], "wrong": wrong["near_median"]}
        sf.write(listen / f"{name}_target.wav", audio.T, 44100, subtype="FLOAT")
        for arm in ("rules", "designer"):
            d, v, first = arm_result(job, arm)
            tuner = t.Tuner(scratch, audio, note)
            seeds = []
            for seed in SEEDS:
                _, sv, _, _ = tuner.tune(d, loop.BUDGET, seed, rules.start_values(target, d, ranking))
                seeds.append(c.near(audio, t.render_values(d, sv, note)))
            tuner.close()
            a = t.render_values(d, v, note)
            hidden = {}
            for label, n, vel in (("down", note - 12, 100), ("up", note + 12, 100), ("soft", note, 40)):
                hidden[label] = round(c.near(np.load(scratch / "hidden" / name / f"{label}.npy"), t.render_values(d, v, n, vel)), 2)
            row[arm] = {"start": round(first, 2), "final": round(c.near(audio, a), 2), "full_gap": round(c.gap(audio, a), 2), "seeds": [round(x, 2) for x in seeds],
                        "median": round(float(np.median(seeds)), 2), "spread": round(max(seeds) - min(seeds), 2), "hidden": hidden, "design": d}
            tag = pool.pop()
            ears[f"{name}_{tag}"] = arm
            sf.write(listen / f"{name}_{tag}.wav", a.T, 44100, subtype="FLOAT")
            tree = p.build(d, v)
            s.write_preset_file(str(scratch / "out" / f"{name}_{arm}.SerumPreset"), {"presetName": f"prototype {name} {arm}", "presetAuthor": "wav-to-serum prototype", "presetDescription": "", "tags": []}, tree) if False else None
        out[name] = row
        print(json.dumps(row), flush=True)
    (scratch / "finals.json").write_text(json.dumps(out, indent=1))
    (scratch / "ears_key.json").write_text(json.dumps(ears, indent=1))


if __name__ == "__main__":
    main()

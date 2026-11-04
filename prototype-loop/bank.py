"""PROTOTYPE, throw away. "Can trained guessers pick a structure the tuner can finish from?": the bank, and its coverage.

Bank: every wavetable-only .SerumPreset under the Presets folder, packs included. Dropped by hash: all 22 listed presets,
so nothing sealed is decoded. Dropped by overlap: anything sharing 60% of settings with one of the 12 test sounds.

  python bank.py build      bank.pkl: [(path, structure)]
  python bank.py coverage   each test sound's true structure next to the bank, part by part
"""
import csv, hashlib, json, pickle, sys
from collections import Counter
from pathlib import Path

import serum2_preset_loader as s

import pick  # before retrieve, which puts testset/ (with its own pick.py) first on the path
import retrieve as rv
import structure as st

ROOT = Path("/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets")
ALL12 = [f"{k} {i}" for k in ("Bass", "Lead", "Synth") for i in range(1, 5)]


def files():
    seen = set()
    import os
    found = [Path(d) / n for d, _, ns in os.walk(ROOT, followlinks=True) for n in ns if n.endswith(".SerumPreset")]
    for f in sorted(found):
        r = f.resolve()
        if r not in seen:
            seen.add(r)
            yield r


def family(table):
    return table.split("/")[0] if table and "/" in table else (table or "none")


def parts(x):
    """A structure as five sets of parts, the units the guessers answer and the bound matches on."""
    return {"tables": {o["table"] for o in x["osc"]},
            "mods": set(x["mods"]),
            "fx": {f for r in x["fx"] for f in r},
            "filters": set(x["filters"]),
            "voices": {f"osc{len(x['osc'])}", f"uni{max([o['unison'] for o in x['osc']] or [1]) > 1}", f"sub{x['sub']}", f"noise{x['noise']}"}}


def jac(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def sim(a, b):
    pa, pb = parts(a), parts(b)
    return sum(jac(pa[k], pb[k]) for k in pa) / len(pa)


def build():
    listed = {p["sha256"] for p in json.loads((rv.REPO / "testset/testset.json").read_text())["presets"]}
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    truth = [rv.settings(s.decode_preset_file(paths[x])[1]) for x in ALL12]
    bank, gone = [], Counter()
    for f in files():
        if hashlib.sha256(f.read_bytes()).hexdigest() in listed:
            gone["listed"] += 1; continue
        try:
            tree = s.decode_preset_file(str(f))[1]
        except Exception:
            gone["unreadable"] += 1; continue
        if not rv.wavetable_only(tree):
            gone["not_wavetable"] += 1
        elif max(rv.overlap(rv.settings(tree), v) for v in truth) >= 0.6:
            gone["near_copy"] += 1
        else:
            bank.append((str(f), st.of_tree(tree)))
    pickle.dump(bank, open("bank.pkl", "wb"))
    distinct = len({json.dumps(x, sort_keys=True) for _, x in bank})
    print("bank", len(bank), "distinct structures", distinct, dict(gone), flush=True)


def coverage():
    bank = pickle.load(open("bank.pkl", "rb"))
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    have = {k: Counter() for k in ("tables", "mods", "fx", "filters", "voices")}
    for _, x in bank:
        for k, v in parts(x).items():
            have[k].update(v)
    for snd in ALL12:
        true = st.of_tree(s.decode_preset_file(paths[snd])[1])
        pt = parts(true)
        best = max(bank, key=lambda b: sim(true, b[1]))
        pb = parts(best[1])
        row = {"sound": snd, "closest": Path(best[0]).stem, "sim": round(sim(true, best[1]), 2)}
        for k in pt:
            row[k] = f"{len(pt[k] & pb[k])}/{len(pt[k])} in closest, {sum(have[k][v] > 0 for v in pt[k])}/{len(pt[k])} anywhere"
        row["missing_anywhere"] = sorted(v for k in pt for v in pt[k] if not have[k][v])
        print(json.dumps(row), flush=True)


def align(tree, note, target):
    """Shift every oscillator by whole octaves so the tree's heard pitch at this note matches the target's.
    The pitch is heard, so this uses no truth."""
    import loop, render as r
    want, got = loop.report(target)["midi"], loop.report(r.render_tree(tree, note))["midi"]
    if want and got and (k := round((want - got) / 12)):
        import patch
        for i in range(5):
            if f"Oscillator{i}" in tree:
                p = patch.pp(tree[f"Oscillator{i}"])
                p["kParamOctave"] = float(p.get("kParamOctave", 0) + k)
    return tree


def bound(budget, sounds):
    """The bank structure most like each true structure, tuned from its own values then random restarts.
    Uses the truth to pick, so it is a bound on matching the bank, not a method."""
    import time
    import numpy as np
    import oracle as o, render as r, tune as t
    bank = pickle.load(open("bank.pkl", "rb"))
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    pick.OUT.mkdir(exist_ok=True)
    for label in sounds:
        tag = f"{label.replace(' ', '')}_bound"
        if (pick.OUT / f"{tag}.json").exists():
            continue
        note = o.NOTES[label.split()[0]]
        true = s.decode_preset_file(paths[label])[1]
        path, x = max(bank, key=lambda b: sim(st.of_tree(true), b[1]))
        target = r.render_tree(true, note)
        feats = t.features(target)
        tree = align(s.decode_preset_file(path)[1], note, target)
        tree = rv.level_up(tree, r.render_tree(tree, note), target)
        rng, t0 = np.random.default_rng(1), time.time()
        own = lambda kn: [[o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in kn]]
        S, knobs = pick.run(tree, note, feats, own, budget, rng)
        pick.save(tag, {"sound": label, "arm": "bound", "from": Path(path).stem, "sim": round(sim(st.of_tree(true), x), 2),
                        "knobs": len(knobs), "secs": round(time.time() - t0)}, tree, knobs, S, note, target, feats)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "bound":
        bound(int(sys.argv[2]), sys.argv[3:])
    else:
        {"build": build, "coverage": coverage}[cmd]()

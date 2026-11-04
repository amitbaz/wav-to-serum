"""PROTOTYPE, throw away. "Can we pick a sound's structure from the audio?"

  python pick.py OLDWORK rescan                         rank the library by pitch-matched score into pick_scan.pkl (no truth: pitch is heard)
  python pick.py OLDWORK factory BUDGET K SOUND [...]   the K closest factory structures (scan.pkl, no truth), BUDGET/K renders each,
                                                        restarts from each preset's own values, then from random starts
  python pick.py OLDWORK swap:PART BUDGET SOUND [...]   the true structure with one PART swapped for the rules' choice, restarts
                                                        PART: none | tables | filter | mods | fx | voices
Truth is used only to report (and, for swaps, as the structure under test).
"""
import copy, csv, json, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import compare as c
import oracle as o
import patch
import render as r
import retrieve as rv
import routes as R
import tune as t

OUT = Path(__import__("os").environ.get("OUT", "pick"))


def _rescan(job):
    """Play a library preset at the note whose heard pitch matches each target's heard pitch."""
    import loop
    try:
        heard = loop.report(r.render_file(job, 48))["midi"]
    except Exception:
        return None
    if not heard:
        return None
    out = {}
    for x, (want, tf, ta) in rv._w["targets"].items():
        note = int(np.clip(round(want - (heard - 48)), 12, 108))
        try:
            a = r.render_file(job, note)
        except Exception:
            return None
        if not np.isfinite(a).all() or abs(a).max() < 1e-3 or abs(a).max() > 8:
            return None
        out[x] = (note, t.score(t.features(rv.gain_match(a, ta)), tf))
    return job, out


def rescan(work):
    import loop
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    targets = {}
    for x in rv.SOUNDS:
        a = r.render_file(paths[x], o.NOTES[x.split()[0]])
        targets[x] = (loop.report(a)["midi"], t.features(a), a)
    keep = rv.library(work)
    t0 = time.time()
    with get_context("spawn").Pool(8, rv._scan_init, (None, targets)) as pool:
        rows = [x for x in pool.imap_unordered(_rescan, keep, chunksize=2) if x]
    print("rescanned", len(rows), "of", len(keep), "in", round(time.time() - t0), "s", flush=True)
    pickle.dump(rows, open(work / "pick_scan.pkl", "wb"))
    for x in rv.SOUNDS:
        top = sorted(rows, key=lambda w: w[1][x][1])[:3]
        print(x, "heard", round(targets[x][0], 1), [(Path(p).stem, v[x][0], round(v[x][1], 2)) for p, v in top], flush=True)


def rules_design(old, sound):
    finals = json.load(open(old / "finals.json"))
    return next(f["rules"]["design"] for f in finals.values() if f["sound"] == sound)


def swap(tree, part, d):
    t2 = copy.deepcopy(tree)
    wt_on = [i for i in range(3) if i == 0 or o.is_on(t2, f"Oscillator{i}", t2[f"Oscillator{i}"])]
    if part == "tables":
        for j, i in enumerate(wt_on):
            t2[f"Oscillator{i}"][f"WTOsc{i}"]["relativePathToWT"] = d["osc"][min(j, len(d["osc"]) - 1)]["table"]
    elif part == "filter":
        p0 = patch.pp(t2["VoiceFilter0"])
        if d["filter"]:
            p0["kParamEnable"], p0["kParamType"] = 1.0, d["filter"]
            p0.setdefault("kParamFreq", 0.7)
        else:
            p0["kParamEnable"] = 0.0
        patch.pp(t2["VoiceFilter1"])["kParamEnable"] = 0.0
    elif part == "mods":
        for k in t2:
            if k.startswith("ModSlot"):
                t2[k] = {"plainParams": "default"}
    elif part == "fx":
        mid = {"Distortion": dict(kParamDrive=20.0, kParamWet=50.0), "Chorus": dict(kParamWet=20.0, kParamRate=0.3, kParamDepth=8.0),
               "Delay": dict(kParamWet=15.0, kParamFeedback=30.0, kParamTimeL=0.1, kParamTimeR=0.1, kParamBeatSync=0.0),
               "Reverb": dict(kParamWet=20.0, kParamSize=40.0, kParamType="kHall")}
        for rk in ("FXRack0", "FXRack1", "FXRack2"):
            t2[rk]["FX"] = []
        t2["FXRack0"]["FX"] = [{f"FX{n}": {"plainParams": {"kParamEnable": 1.0, **mid[n]}}, "kUIParamMixOrGain": 0.0, "type": patch.FX_TYPE[n]} for n in d["fx"]]
    elif part == "voices":
        for j, i in enumerate(wt_on):
            g = d["osc"][min(j, len(d["osc"]) - 1)]
            patch.pp(t2[f"Oscillator{i}"])["kParamUnison"] = 4.0 if g.get("unison") else 1.0
        for i, on in ((4, d["sub"]), (3, d["noise"])):
            p = patch.pp(t2[f"Oscillator{i}"])
            p["kParamEnable"] = 1.0 if on else 0.0
            if on and not p.get("kParamVolume"):
                p["kParamVolume"] = 0.3
    elif part != "none":
        raise SystemExit(f"unknown part {part}")
    return t2


def run(tree, note, feats, x0s, budget, rng):
    """Restarts on one structure. x0s: starts to use before falling back to random ones."""
    knobs = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(tree)]
    n = len(knobs)
    with get_context("spawn").Pool(8, R._init, (tree, knobs, feats, note)) as pool:
        S = R.Search(pool, budget)
        pop, starts = None, list(x0s(knobs))
        while S.left() > 0:
            x0 = starts.pop(0) if starts else rng.uniform(0.15, 0.85, n)
            pop = S.cma(x0, 0.2, popsize=pop) * 2
    return S, knobs


def save(tag, res, tree, knobs, S, note, target, feats):
    got = r.render_tree(o.apply(tree, knobs, S.bx), note)
    res.update(score_final=round(S.best, 3), near=round(c.near(target, got), 2), evals=S.used,
               parts={k: round(v, 2) for k, v in t.parts(t.features(got), feats).items()}, hist=S.hist[:: max(1, len(S.hist) // 10)])
    (OUT / f"{tag}.json").write_text(json.dumps(res))
    pickle.dump({"tree": o.apply(tree, knobs, S.bx), "x": S.bx.tolist(), "knobs": knobs}, open(OUT / f"{tag}.pkl", "wb"))
    sf.write(OUT / f"{tag}.wav", got.T, 44100, subtype="FLOAT")
    print(json.dumps({k: v for k, v in res.items() if k not in ("hist", "parts")}), flush=True)


def main():
    old, arm = Path(sys.argv[1]), sys.argv[2]
    if arm == "rescan":
        return rescan(Path("."))
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    OUT.mkdir(exist_ok=True)
    budget = int(sys.argv[3])
    k = int(sys.argv[4]) if arm == "factory" else 1
    sounds = sys.argv[5:] if arm == "factory" else sys.argv[4:]
    rows = pickle.load(open("pick_scan.pkl", "rb")) if arm == "factory" else None
    for label in sounds:
        tag = f"{label.replace(' ', '')}_{arm.replace(':', '-')}"
        if (OUT / f"{tag}.json").exists():  # done before a pause: keep it
            continue
        note = o.NOTES[label.split()[0]]
        _, true = s.decode_preset_file(paths[label])
        target = r.render_tree(true, note)
        feats = t.features(target)
        sf.write(OUT / f"{label.replace(' ', '')}_target.wav", target.T, 44100, subtype="FLOAT")
        rng = np.random.default_rng(1)
        t0 = time.time()
        if arm.startswith("swap:"):
            tree = swap(true, arm[5:], rules_design(old, label))
            S, knobs = run(tree, note, feats, lambda kn: [rng.uniform(0.15, 0.85, len(kn))], budget, rng)
            save(tag, {"sound": label, "arm": arm, "knobs": len(knobs), "secs": round(time.time() - t0)}, tree, knobs, S, note, target, feats)
            continue
        seen, tops = set(), []
        for p, v in sorted(rows, key=lambda w: w[1][label][1]):
            if p not in seen:
                seen.add(p); tops.append((p, *v[label]))
            if len(tops) == k:
                break
        best = None
        for rank, (path, pnote, s0) in enumerate(tops):
            tree = rv.level_up(s.decode_preset_file(path)[1], r.render_file(path, pnote), target)
            own = lambda kn: [[o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in kn]]
            S, knobs = run(tree, pnote, feats, own, budget // k, rng)
            row = {"rank": rank, "from": Path(path).stem, "note": pnote, "scan_score": round(s0, 2), "knobs": len(knobs), "score": round(S.best, 3)}
            print(json.dumps({"sound": label, **row}), flush=True)
            if best is None or S.best < best[0].best:
                best = (S, knobs, tree, pnote, row)
            tops[rank] = row
        S, knobs, tree, pnote, row = best
        S.used = budget  # the whole budget, across the K structures
        save(tag, {"sound": label, "arm": arm, "picked": row["from"], "picked_note": pnote, "true_note": note, "tried": tops, "secs": round(time.time() - t0)},
             tree, knobs, S, pnote, target, feats)


if __name__ == "__main__":
    main()

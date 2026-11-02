"""PROTOTYPE, throw away. Start from the closest factory preset instead of a blank template.

Library: factory .SerumPreset files, wavetable-only. Dropped by hash: all 22 listed presets, so nothing sealed is
decoded or rendered. Dropped by overlap: anything sharing 60% of settings with one of the six sounds.
Key is not leaked: every preset plays on five Cs, and the best (preset, note) pair wins.

  python retrieve.py WORK scan            render the library, score against the six targets
  python retrieve.py WORK tune BUDGET K   tune the top K per sound from their own values
"""
import csv, hashlib, json, os, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import compare as c
import oracle as o
import render as r
import tune as t

REPO = Path("/Users/amitbaz/.superset/worktrees/wav-to-serum/relic-port-cde7f201")
LIB = Path("/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets/Factory")
SOUNDS = ["Bass 1", "Bass 2", "Lead 1", "Lead 4", "Synth 1", "Synth 4"]
NOTES = (24, 36, 48, 60, 72)
sys.path.insert(0, str(REPO / "testset"))


def settings(node, path=""):
    out = {}
    if isinstance(node, dict):
        for k, v in node.items():
            out.update(settings(v, f"{path}/{k}"))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.update(settings(v, f"{path}/{i}"))
    else:
        out[path] = node
    return out


def overlap(a, b):
    keys = a.keys() | b.keys()
    return sum(a.get(k) == b.get(k) for k in keys) / max(len(keys), 1)


def wavetable_only(tree):
    for i in range(3):
        n = tree.get(f"Oscillator{i}", {})
        p = n.get("plainParams")
        if isinstance(p, dict) and p.get("kParamType") and p.get("kParamEnable", i == 0):
            return False
    return True


def library(work):
    listed = {p["sha256"] for p in json.loads((REPO / "testset/testset.json").read_text())["presets"]}
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    truth = {x: settings(s.decode_preset_file(paths[x])[1]) for x in SOUNDS}
    keep, gone = [], {"listed": 0, "near_copy": 0, "not_wavetable": 0, "unreadable": 0}
    for f in sorted(LIB.rglob("*.SerumPreset")):
        if hashlib.sha256(f.read_bytes()).hexdigest() in listed:
            gone["listed"] += 1
            continue
        try:
            tree = s.decode_preset_file(str(f))[1]
        except Exception:
            gone["unreadable"] += 1
            continue
        if not wavetable_only(tree):
            gone["not_wavetable"] += 1
        elif max(overlap(settings(tree), v) for v in truth.values()) >= 0.6:
            gone["near_copy"] += 1
        else:
            keep.append(str(f))
    print("library", len(keep), gone, flush=True)
    return keep


def gain_match(a, target):
    return a * np.sqrt((target**2).mean() / max((a**2).mean(), 1e-12))


_w = {}


def _scan_init(feats, targets):
    _w.update(feats=feats, targets=targets)


def _scan(job):
    path, note = job
    try:
        a = r.render_file(path, note)
    except Exception:
        return None
    if not np.isfinite(a).all() or abs(a).max() < 1e-3 or abs(a).max() > 8:
        return None
    return path, note, {x: t.score(t.features(gain_match(a, _w["targets"][x])), _w["feats"][x]) for x in SOUNDS}


def scan(work):
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    targets = {x: r.render_file(paths[x], o.NOTES[x.split()[0]]) for x in SOUNDS}
    feats = {x: t.features(a) for x, a in targets.items()}
    keep = library(work)
    jobs = [(p, n) for p in keep for n in NOTES]
    t0 = time.time()
    pool = get_context("spawn").Pool(int(os.environ.get("W", 8)), _scan_init, (feats, targets))
    rows = [x for x in pool.imap_unordered(_scan, jobs, chunksize=4) if x]
    pool.close()
    pool.join()
    print("rendered", len(rows), "of", len(jobs), "in", round(time.time() - t0), "s", flush=True)
    pickle.dump(rows, open(work / "scan.pkl", "wb"))
    for x in SOUNDS:
        top = sorted(rows, key=lambda w: w[2][x])[:5]
        print(x, "true note", o.NOTES[x.split()[0]], [(Path(p).parent.name, n, round(v[x], 2)) for p, n, v in top], flush=True)


def _tune_init(tree, knobs, feats, note, target):
    _w.update(tree=tree, knobs=knobs, feats=feats, note=note, target=target)


def _eval(x):
    a = r.render_tree(o.apply(_w["tree"], _w["knobs"], x), _w["note"])
    if not np.isfinite(a).all() or abs(a).max() > 8:
        return 1e3
    return t.score(t.features(a), _w["feats"])


def level_up(tree, a, target):
    """Set master volume so the start matches the target's level before tuning."""
    g = float(np.sqrt((target**2).mean() / max((a**2).mean(), 1e-12)))
    p = tree["Global0"].setdefault("plainParams", {})
    if not isinstance(p, dict):
        tree["Global0"]["plainParams"] = p = {}
    # master volume reads as amplitude^(1/2)-like; a rough step is enough, the tuner finishes it
    p["kParamMasterVolume"] = float(np.clip(p.get("kParamMasterVolume", 0.7) * g**0.5, 0.02, 1.0))
    return tree


def tune_all(work, budget, k):
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    rows = pickle.load(open(work / "scan.pkl", "rb"))
    out = work / "retrieved"
    out.mkdir(exist_ok=True)
    only = sys.argv[5:] or SOUNDS
    for x in only:
        target = r.render_file(paths[x], o.NOTES[x.split()[0]])
        feats = t.features(target)
        tag = x.replace(" ", "")
        sf.write(out / f"{tag}_target.wav", target.T, 44100, subtype="FLOAT")
        best = None
        seen, tops = set(), []
        for p, n, v in sorted(rows, key=lambda w: w[2][x]):  # distinct presets
            if p not in seen:
                seen.add(p)
                tops.append((p, n, v[x]))
            if len(tops) == k:
                break
        for rank, (path, note, s0) in enumerate(tops):
            tree = level_up(s.decode_preset_file(path)[1], r.render_file(path, note), target)
            knobs = [(q, kn, v, *o.mapper(kn, v)) for q, kn, v in o.walk(tree)]
            x0 = [o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs]
            start = r.render_tree(o.apply(tree, knobs, x0), note)
            pool = get_context("spawn").Pool(8, _tune_init, (tree, knobs, feats, note, target))
            es = cma.CMAEvolutionStrategy(x0, 0.08, {"bounds": [0, 1], "popsize": max(24, len(knobs) // 2), "seed": 7, "verbose": -9, "CMA_diagonal": True})
            b, bx, used = t.score(t.features(start), feats), x0, 0
            first = b
            while used < budget and not es.stop():
                xs = es.ask()
                fs = pool.map(_eval, [list(map(float, y)) for y in xs], chunksize=1)
                es.tell(xs, fs)
                used += len(xs)
                i = int(np.argmin(fs))
                if fs[i] < b:
                    b, bx = fs[i], [float(y) for y in xs[i]]
            pool.close()
            pool.join()
            got = r.render_tree(o.apply(tree, knobs, bx), note)
            row = {"sound": x, "rank": rank, "from": Path(path).parent.name, "note": note, "knobs": len(knobs), "start_score": round(first, 2), "final_score": round(b, 2),
                   "start_near": round(c.near(target, start), 2), "near": round(c.near(target, got), 2), "parts": {q: round(w, 2) for q, w in t.parts(t.features(got), feats).items()}}
            print(json.dumps(row), flush=True)
            if best is None or b < best[0]:
                best = (b, o.apply(tree, knobs, bx), got, row, start, path)
        pickle.dump({"tree": best[1], "row": best[3], "source": best[5]}, open(out / f"{tag}.pkl", "wb"))
        sf.write(out / f"{tag}_tuned.wav", best[2].T, 44100, subtype="FLOAT")
        sf.write(out / f"{tag}_start.wav", best[4].T, 44100, subtype="FLOAT")


if __name__ == "__main__":
    w = Path(sys.argv[1])
    if sys.argv[2] == "scan":
        scan(w)
    else:
        tune_all(w, int(sys.argv[3]), int(sys.argv[4]))

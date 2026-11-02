"""PROTOTYPE, throw away. "Find out why close numbers still sound wrong": the oracle test.

Keep a known preset's real structure (tables, routes, FX, filter types) and hide only its knob values,
then tune. The true preset is a point in this search with score 0, so:
  final score well above 0         -> the search cannot get there
  final score near 0, sounds wrong -> the score cannot hear the difference
  sounds right                     -> score and search are fine; the fault is the template or the choices

  python oracle.py WORK BUDGET SEED SOUND [SOUND ...]
"""
import copy, csv, json, math, os, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import compare as c
import render as r
import tune as t

NOTES = {"Bass": 36, "Lead": 60, "Synth": 48}
LOGS = {"kParamAttack", "kParamHold", "kParamDecay", "kParamRelease", "kParamRate", "kParamPortamentoTime"}
SKIP = ("Enable", "Octave", "Unison", "KeyTrack", "BeatSync", "Mode", "Type", "Dotted", "Triplets", "Rate10x", "Curve", "Pad", "PitchRatio",
        "Mono", "Toggle", "Compat", "Limit", "Porta", "Direction", "Grid", "RandomPhase", "ModWheel", "Bipolar", "Curve", "Smooth", "Fall")
KEEP_UNISON = {"kParamUnisonStereo"}


def is_on(tree, name, node):
    if name.startswith("Oscillator"):
        i = int(name[-1])
        return i == 0 or bool(node.get("plainParams", {}).get("kParamEnable", 0)) if isinstance(node.get("plainParams"), dict) else i == 0
    return True


def mapper(name, v):
    """(lo, hi, is_log): wide ranges around the musical scale, not around the truth."""
    if name in LOGS:
        return max(min(v, 1.0) / 100, 1e-4), max(v * 10, 8.0), True
    if name.endswith("Freq") and v > 1:
        return 20.0, 20000.0, True
    if 0 <= v <= 1:
        return 0.0, 1.0, False
    if abs(v) <= 100:
        return (-100.0, 100.0, False) if v < 0 else (0.0, 100.0, False)
    return v / 4, v * 4, False


def walk(tree):
    """Every numeric knob the true preset sets. Absent ones keep Serum's default."""
    out = []

    def params(path, node):
        pp = node.get("plainParams")
        if isinstance(pp, dict):
            for k, v in pp.items():
                if isinstance(v, (int, float)) and not isinstance(v, bool) and (k in KEEP_UNISON or not any(x in k for x in SKIP)):
                    out.append((path, k, float(v)))

    for name, node in tree.items():
        if not isinstance(node, dict):
            continue
        if name.startswith("Oscillator"):
            if not is_on(tree, name, node):
                continue
            params((name,), node)
            for sub, n in node.items():
                if isinstance(n, dict):
                    params((name, sub), n)
        elif name.startswith(("Env", "LFO", "VoiceFilter", "ModSlot")):
            if name.startswith("VoiceFilter") and not node.get("plainParams", {}) if isinstance(node.get("plainParams"), dict) else False:
                continue
            params((name,), node)
        elif name == "Global0":
            params((name,), node)
        elif name.startswith("FXRack"):
            for i, fx in enumerate(node.get("FX", [])):
                for sub, n in fx.items():
                    if sub.startswith("FX") and isinstance(n, dict):
                        params((name, "FX", i, sub), n)
    return out


def to_unit(v, lo, hi, lg):
    u = (math.log(max(v, lo)) - math.log(lo)) / (math.log(hi) - math.log(lo)) if lg else (v - lo) / (hi - lo)
    return float(np.clip(u, 0, 1))


def from_unit(u, lo, hi, lg):
    return lo * (hi / lo) ** u if lg else lo + (hi - lo) * u


def apply(tree, knobs, x):
    t2 = copy.deepcopy(tree)
    for (path, k, _, lo, hi, lg), u in zip(knobs, x):
        n = t2
        for step in path:
            n = n[step]
        n["plainParams"][k] = from_unit(float(u), lo, hi, lg)
    return t2


_w = {}


def _init(tree, knobs, feats, note):
    _w.update(tree=tree, knobs=knobs, feats=feats, note=note)


def _eval(x):
    a = r.render_tree(apply(_w["tree"], _w["knobs"], x), _w["note"])
    if not np.isfinite(a).all() or abs(a).max() > 8:
        return 1e3
    return t.score(t.features(a), _w["feats"])


def main():
    work, budget, seed = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    out = work / "oracle"
    out.mkdir(exist_ok=True)
    for label in sys.argv[4:]:
        note = NOTES[label.split()[0]]
        _, tree = s.decode_preset_file(paths[label])
        target = r.render_tree(tree, note)
        feats = t.features(target)
        knobs = [(p, k, v, *mapper(k, v)) for p, k, v in walk(tree)]
        truth = [to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs]
        rebuilt = r.render_tree(apply(tree, knobs, truth), note)
        rng = np.random.default_rng(seed)
        near = float(os.environ.get("NEAR", 0))  # start this close to the truth, in 0..1 units
        x0 = (np.clip(np.array(truth) + rng.normal(0, near, len(knobs)), 0, 1) if near else rng.uniform(0.15, 0.85, len(knobs))).tolist()
        pool = get_context("spawn").Pool(8, _init, (tree, knobs, feats, note))
        es = cma.CMAEvolutionStrategy(x0, near or 0.2, {"bounds": [0, 1], "popsize": max(24, len(knobs) // 2), "seed": seed + 1, "verbose": -9, "CMA_diagonal": True})
        best, bx, used, t0, hist = float("inf"), x0, 0, time.time(), []
        while used < budget and not es.stop():
            xs = es.ask()
            fs = pool.map(_eval, [list(map(float, x)) for x in xs], chunksize=1)
            es.tell(xs, fs)
            used += len(xs)
            i = int(np.argmin(fs))
            if fs[i] < best:
                best, bx = fs[i], [float(v) for v in xs[i]]
            hist.append((used, round(best, 3)))
        pool.close()
        pool.join()
        got = r.render_tree(apply(tree, knobs, bx), note)
        tag = label.replace(" ", "") + f"_s{seed}" + (f"_near{near}" if near else "")
        res = {"sound": label, "knobs": len(knobs), "evals": used, "secs": round(time.time() - t0), "score_truth_rebuilt": round(t.score(t.features(rebuilt), feats), 3),
               "score_final": round(best, 3), "near": round(c.near(target, got), 2), "gap": round(c.gap(target, got), 2),
               "parts": {k: round(v, 2) for k, v in t.parts(t.features(got), feats).items()}, "hist": hist[:: max(1, len(hist) // 8)]}
        (out / f"{tag}.json").write_text(json.dumps(res))
        pickle.dump({"tree": apply(tree, knobs, bx), "x": bx, "knobs": knobs}, open(out / f"{tag}.pkl", "wb"))
        sf.write(out / f"{tag}.wav", got.T, 44100, subtype="FLOAT")
        sf.write(out / f"{label.replace(' ', '')}_target.wav", target.T, 44100, subtype="FLOAT")
        print(json.dumps({k: v for k, v in res.items() if k != "hist"}), flush=True)


if __name__ == "__main__":
    main()

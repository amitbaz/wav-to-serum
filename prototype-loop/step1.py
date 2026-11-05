"""PROTOTYPE, throw away. "Step 1: one oscillator and an amp envelope".

  python step1.py make [N]             N made sounds (default 20): one wavetable oscillator, a random factory table and
                                       position, a random amp envelope, nothing else. Half adjust the method, half are held out.
  python step1.py match BUDGET [NAME]  pitch, wavetable and envelope pieces set the start, the tuner finishes. Truth only scores.
  python step1.py truth BUDGET [NAME]  check 2: the true table from a random start (run only if the step fails)
  python step1.py near BUDGET [NAME]   check 3: the true table from a start near the true knobs
Rerun resumes: finished sounds are skipped.
"""
import copy, json, os, pickle, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

import analyse as an
import oracle as o
import parts as pt
import patch
import pick
import render as rd
import retrieve as rv
import tune as t

patch.BASE = "base.pkl"
OUT = Path("step1")
pick.OUT = OUT
SR = 44100

# The old ranges sit around the start value, so a table position below 100 could never reach 256.
_mapper = o.mapper
o.SKIP = o.SKIP + ("CoarsePit",)  # pitch is set by the pitch piece, not tuned
# Envelope times got a range of start/100 to 8 s, so one tuner step was 10x in time. Fixed musical ranges instead.
FIXED = {"kParamTablePos": (1.0, 256.0, False), "kParamAttack": (1e-4, 4.0, True), "kParamDecay": (1e-3, 16.0, True), "kParamRelease": (1e-3, 8.0, True)}
o.mapper = lambda k, v: FIXED.get(k) or _mapper(k, v)


def run(tree, note, feats, x0, budget, rng, sigma=0.08):
    """Score the start itself first (CMA only samples around it), tune from it with a small step, then random restarts."""
    from multiprocessing import get_context
    import routes as R
    knobs = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(tree)]
    x0 = np.array(x0(knobs)[0], float)
    with get_context("spawn").Pool(8, R._init, (tree, knobs, feats, note)) as pool:
        S = R.Search(pool, budget)
        S.f([x0])
        pop = S.cma(x0, sigma) * 2
        while S.left() > 0:
            pop = S.cma(rng.uniform(0.15, 0.85, len(knobs)), 0.2, popsize=pop) * 2
    return S, knobs


def build(table, pos, env):
    tree = patch.blank()
    pt.set_table(tree["Oscillator0"], 0, table, pos)
    pt.set_env(tree, env)
    return tree


def make(n, seed=38):
    OUT.mkdir(exist_ok=True)
    rng = np.random.default_rng(seed)
    tables, out = an.table_list(), []
    while len(out) < n:
        s = {"table": str(rng.choice(tables)), "pos": round(float(rng.uniform(0, 1)), 3), "note": int(rng.choice([36, 48, 60])),
             "env": {"attack": float(np.exp(rng.uniform(np.log(5e-4), np.log(1.0)))), "decay": float(np.exp(rng.uniform(np.log(0.05), np.log(4.0)))),
                     "sustain": round(float(rng.uniform(0, 1)), 3), "release": float(np.exp(rng.uniform(np.log(0.01), np.log(1.0))))}}
        tree = build(s["table"], s["pos"], s["env"])
        a = rd.render_tree(tree, s["note"])
        if not np.isfinite(a).all() or abs(a).max() < 1e-3:
            continue
        s["name"] = f"S{len(out) + 1:02d}"
        s["split"] = "adjust" if len(out) < n // 2 else "held_out"
        again = rd.render_tree(tree, s["note"])
        s["repeat_score"] = round(t.score(t.features(again), t.features(a)), 3)  # the comparer's floor on this sound
        sf.write(OUT / f"{s['name']}_target.wav", a.T, SR, subtype="FLOAT")
        pickle.dump(tree, open(OUT / f"{s['name']}_true.pkl", "wb"))
        out.append(s)
        print(json.dumps(s), flush=True)
    json.dump(out, open(OUT / "sounds.json", "w"), indent=1)


def dense_lib(steps=65):
    """Every table at `steps` positions, each a linear blend of the two nearest frames, which is how Serum morphs
    (1.4 dB from a render, against 6.1 dB for the nearest frame alone). The old library kept at most 32 frames."""
    H = pt.H
    names, pos, rows = [], [], []
    for tb in an.table_list():
        F = pt.table_frames(an.TABLES / tb)
        n = len(F)
        for u in np.linspace(0, 1, steps if n > 1 else 1):
            f = u * (n - 1); i = int(f); w = f - i
            m = np.abs(np.fft.rfft((1 - w) * F[i] + w * F[min(i + 1, n - 1)]))[1 : H + 1]
            d = 20 * np.log10(m + 1e-9)
            names.append(tb); pos.append(float(u)); rows.append(np.maximum(d - d.max(), -90).astype(np.float32))
    return names, np.array(pos), np.stack(rows)


def load_lib():
    f = OUT / "lib.pkl"
    if not f.exists():
        pickle.dump(dense_lib(), open(f, "wb"))
    return pickle.load(open(f, "rb"))


def heard(a):
    """analyse(), with its octave errors fixed: while every odd harmonic sits 30 dB under the even ones, the pitch
    reader has found half the real fundamental, so double it. Harmonics are then taken on the right grid."""
    r = an.analyse(a)
    for _ in range(3):
        h = np.array(r["harmonics_db"])
        if not r["f0_hz"] or h[0::2].max() > h[1::2].max() - 30:
            break
        f0 = 2 * r["f0_hz"]
        harm, _ = an.harmonics(pt.steady(a, r), f0)
        r = {**r, "f0_hz": f0, "midi": 69 + 12 * np.log2(f0 / 440), "harmonics_db": [float(x - harm.max()) for x in harm]}
    return r


def read(a, note, lib):
    r = heard(a)
    return {"pitch": pt.pitch(a, note, r), "wavetable": pt.wavetable(a, note, r, lib, top=12), "envelope": pt.envelope(a, note, r)}


def align(tree, note, target):
    """Shift the oscillator so its heard pitch matches the target's: whole octaves, then semitones. A table frame can be
    one high harmonic (a sine heard 31 semitones up), which whole octaves alone cannot reach. Pitch is heard: no truth."""
    want, got = heard(target)["midi"], heard(rd.render_tree(tree, note))["midi"]
    if want and got and (k := round(want - got)):
        p = patch.pp(tree["Oscillator0"])
        p["kParamOctave"], p["kParamCoarsePit"] = float(round(k / 12)), float(k - 12 * round(k / 12))
    return tree


def ready(tree, note, target):
    tree = align(tree, note, target)
    return rv.level_up(tree, rd.render_tree(tree, note), target)


def own(kn):
    return [[o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in kn]]


def match(budget, s, target, lib, rng):
    """Top 3 tables from the wavetable piece, each built with the envelope piece and screened; the best gets the rest."""
    note, feats = s["note"], t.features(target)
    P = read(target, note, lib)
    screen = int(os.environ.get("SCREEN", budget // 6))
    ranked = []  # one render each re-ranks the piece's top 12: near-sines tie on 24 harmonics, the score tells them apart
    for c in P["wavetable"]["ranked"][:12]:
        a = rd.render_tree(ready(build(c["table"], c["pos"], P["envelope"]), note, target), note)
        ranked.append((t.score(t.features(rv.gain_match(a, target)), feats), c))
    ranked.sort(key=lambda x: x[0])
    tried, best = [], None
    for _, c in ranked[:3]:
        tree = ready(build(c["table"], c["pos"], P["envelope"]), note, target)
        S, knobs = run(tree, note, feats, own, screen, rng)
        tried.append({"table": pt.norm(c["table"]), "pos": c["pos"], "first_render": round(next(x for x, y in ranked if y is c), 3), "score": round(S.best, 3)})
        if best is None or S.best < best[0].best:
            best = (S, knobs, tree, c)
    S0, knobs, tree, c = best
    bx = S0.bx.copy()
    S, knobs = run(tree, note, feats, lambda kn: [bx], budget - screen * len(tried), rng, sigma=0.04)
    if S0.best < S.best:
        S = S0
    S.used = budget
    env = P["envelope"]
    return S, knobs, tree, {"picked": pt.norm(c["table"]), "tried": tried,
                            "pieces": {"octave": P["pitch"]["octave"], "table_rank": next((i for i, x in enumerate(P["wavetable"]["ranked"]) if pt.norm(x["table"]) == pt.norm(s["table"])), None),
                                       "table_rank_after_render": next((i for i, (_, x) in enumerate(ranked) if pt.norm(x["table"]) == pt.norm(s["table"])), None),
                                       "pos": P["wavetable"]["ranked"][0]["pos"], "env": {k: round(env[k], 4) for k in ("attack", "decay", "sustain", "release")}}}


def check(budget, s, target, rng, near):
    """The true structure (table) from a random start, or from a start near the true knobs."""
    true = pickle.load(open(OUT / f"{s['name']}_true.pkl", "rb"))
    tree = ready(copy.deepcopy(true), s["note"], target) if not near else true
    feats = t.features(target)
    if near:
        x0s = lambda kn: [np.clip(np.array(own(kn)[0]) + rng.normal(0, 0.05, len(kn)), 0, 1)]
    else:
        x0s = lambda kn: [rng.uniform(0.15, 0.85, len(kn))]
    S, knobs = run(tree, s["note"], feats, x0s, budget, rng, sigma=0.05 if near else 0.2)
    return S, knobs, tree, {}


def main():
    cmd = sys.argv[1]
    if cmd == "make":
        return make(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    budget, only = int(sys.argv[2]), set(sys.argv[3:])
    sounds = json.load(open(OUT / "sounds.json"))
    lib = load_lib() if os.environ.get("LIB", "dense") == "dense" else pt.load_lib()[:3]
    for s in sounds:
        tag = f"{s['name']}_{cmd}"
        if (only and s["name"] not in only) or (OUT / f"{tag}.json").exists():
            continue
        target, _ = sf.read(OUT / f"{s['name']}_target.wav", dtype="float32", always_2d=True)
        target = target.T
        rng, t0 = np.random.default_rng(1), time.time()
        S, knobs, tree, extra = match(budget, s, target, lib, rng) if cmd == "match" else check(budget, s, target, rng, cmd == "near")
        res = {"sound": s["name"], "split": s["split"], "arm": cmd, "knobs": len(knobs), "knob_names": [k for _, k, *_ in knobs],
               "truth": {"table": pt.norm(s["table"]), "pos": s["pos"], "env": s["env"], "note": s["note"]}, **extra, "secs": round(time.time() - t0)}
        pick.save(tag, res, tree, knobs, S, s["note"], target, t.features(target))


if __name__ == "__main__":
    main()

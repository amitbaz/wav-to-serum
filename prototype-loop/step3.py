"""PROTOTYPE, throw away. "Step 3: filter or no filter".

  python step3.py make [N]             N made sounds (default 20): Step 2's sounds, half with the filter and half without, at random
                                       (5 and 5 in each split). A filter must be heard, as in Step 2.
  python step3.py match BUDGET [NAME]  Step 2's method 2, with one added choice: each table is also tried with no filter. After the
                                       screen, the best no-filter candidate wins unless a filter candidate beats it by more than MARGIN.
                                       METHOD=2 (default): then, if a filter is on, it is switched off at the tuned knobs with the level
                                       matched, and stays off unless that scores worse by more than MARGIN.
  python step3.py truth|near BUDGET [NAME]   checks 2 and 3: the true structure from a random or a near start
SET=step3b holds method 2's fresh sounds. SET=step1 or SET=step2b reruns those sounds, into step3/rerun-<set>[-m2]/. Rerun resumes: finished sounds are skipped.
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
import step1 as s1
import step2 as s2
import tune as t

SET = Path(os.environ.get("SET", "step3"))
METHOD = int(os.environ.get("METHOD", 2))
OUT = Path(os.environ.get("OUT") or (SET.name if SET.name.startswith("step3") else f"step3/rerun-{SET.name}" + ("-m2" if METHOD == 2 else "")))
s1.OUT, s2.OUT, pick.OUT = SET, OUT, OUT
s2.METHOD = 2
# v2, frozen before the held-out half: the screen is noisy (0.2 to 0.5 between candidates on one table), so a filter has to
# earn its place. v1 instead switched the filter off after tuning, which failed on H08: the tune had built around an open filter.
MARGIN = float(os.environ.get("MARGIN", 0.3))


def has_filter(tree):
    p = tree["VoiceFilter0"].get("plainParams")
    return isinstance(p, dict) and bool(p.get("kParamEnable"))


def make(n, seed=int(os.environ.get("SEED", 42)), prefix=os.environ.get("PREFIX", "H")):
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "lib.pkl").exists():
        (OUT / "lib.pkl").symlink_to((Path("step1") / "lib.pkl").resolve())
    rng = np.random.default_rng(seed)
    half = n // 2
    plan = [bool(x) for x in np.concatenate([rng.permutation([1] * (half // 2) + [0] * (half - half // 2)),
                                             rng.permutation([1] * ((n - half) // 2) + [0] * (n - half - (n - half) // 2))])]
    tables, out, dropped = an.table_list(), [], 0
    while len(out) < n:
        s = {"table": str(rng.choice(tables)), "pos": round(float(rng.uniform(0, 1)), 3), "note": int(rng.choice([36, 48, 60])),
             "env": {"attack": float(np.exp(rng.uniform(np.log(5e-4), np.log(1.0)))), "decay": float(np.exp(rng.uniform(np.log(0.05), np.log(4.0)))),
                     "sustain": round(float(rng.uniform(0, 1)), 3), "release": float(np.exp(rng.uniform(np.log(0.01), np.log(1.0))))}}
        f0 = 440 * 2 ** ((s["note"] - 69) / 12)
        typ = str(rng.choice(s2.TYPES))
        hz = min(f0 * 2 ** rng.uniform(0, 4.5), 8000.0)
        f = {"type": typ, "cutoff_hz": round(hz), "knob": round(s2.hz_to_knob(hz, typ), 4), "reso": round(float(rng.uniform(0, 75)), 1)}
        dry_tree = s1.build(s["table"], s["pos"], s["env"])
        dry = rd.render_tree(dry_tree, s["note"])
        if not np.isfinite(dry).all() or abs(dry).max() < 1e-3:
            continue
        if plan[len(out)]:
            tree = s2.build(s["table"], s["pos"], s["env"], f)
            a = rd.render_tree(tree, s["note"])
            if not np.isfinite(a).all() or abs(a).max() < 1e-3:
                continue
            s["filter"] = f
            s["filter_heard"] = round(t.score(t.features(rv.gain_match(dry, a)), t.features(a)), 2)
            if s["filter_heard"] < 2.5:
                dropped += 1
                continue
        else:
            tree, a = dry_tree, dry
        s["name"] = f"{prefix}{len(out) + 1:02d}"
        s["split"] = "adjust" if len(out) < half else "held_out"
        s["repeat_score"] = round(t.score(t.features(rd.render_tree(tree, s["note"])), t.features(a)), 3)
        sf.write(OUT / f"{s['name']}_target.wav", a.T, s1.SR, subtype="FLOAT")
        pickle.dump(tree, open(OUT / f"{s['name']}_true.pkl", "wb"))
        out.append(s)
        print(json.dumps(s), flush=True)
    json.dump(out, open(OUT / "sounds.json", "w"), indent=1)
    print(json.dumps({"made": n, "with_filter": sum(plan), "dropped_filter_not_heard": dropped}))


def filter_off(tree, knobs, S, note, feats):
    """The tuned preset with its filter switched off, master volume set so its level matches the tuned render."""
    on = o.apply(tree, knobs, S.bx)
    ref = rd.render_tree(on, note)
    off = copy.deepcopy(on)
    off["VoiceFilter0"] = copy.deepcopy(patch.blank()["VoiceFilter0"])
    for _ in range(6):  # level_up takes a rough step, so repeat it
        off = rv.level_up(off, rd.render_tree(off, note), ref)
    ko = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(off)]
    xo = np.array(s1.own(ko)[0], float)
    score = t.score(t.features(rd.render_tree(off, note)), feats)
    check = {"on": round(S.best, 3), "off": round(float(score), 3)}
    if score <= S.best + MARGIN:
        S.best, S.bx = float(score), xo
        return ko, off, check
    return knobs, tree, check


def match(budget, s, target, lib, rng):
    """Step 2's method 2, each table also tried with no filter, then the filter tried off."""
    note, feats = s["note"], t.features(target)
    P = s1.read(target, note, lib)
    r = s1.heard(target)
    f0 = r["f0_hz"] or 440 * 2 ** ((note - 69) / 12)
    P["wavetable"] = s2.wavetable2(target, note, r, lib, top=12)
    screen = int(os.environ.get("SCREEN", budget // 6))
    mk = lambda c: s1.ready(s2.build(c["table"], c["pos"], P["envelope"], c["filter"]) if c["filter"] else s1.build(c["table"], c["pos"], P["envelope"]), note, target)
    ranked = []  # 12 tables x (5 filter types + no filter), one render each
    for c0 in P["wavetable"]["ranked"][:12]:
        for typ in s2.TYPES + [None]:
            c = {**c0, "filter": s2.filter_piece2(c0, f0, typ) if typ else None}
            ranked.append((t.score(t.features(rv.gain_match(rd.render_tree(mk(c), note), target)), feats), c))
    ranked.sort(key=lambda x: x[0])
    tried, runs = [], []
    for _, c in ranked[:3]:
        tree = mk(c)
        S, knobs = s1.run(tree, note, feats, s1.own, screen, rng)
        tried.append({"table": pt.norm(c["table"]), "pos": c["pos"], "filter": c["filter"], "first_render": round(next(x for x, y in ranked if y is c), 3), "score": round(S.best, 3)})
        runs.append((S, knobs, tree, c))
    best = min(runs, key=lambda x: x[0].best)
    offs = [x for x in runs if not x[3]["filter"]]
    if offs and min(x[0].best for x in offs) <= best[0].best + MARGIN:
        best = min(offs, key=lambda x: x[0].best)
    S0, knobs, tree, c = best
    bx = S0.bx.copy()
    S, knobs = s1.run(tree, note, feats, lambda kn: [bx], budget - screen * len(tried), rng, sigma=0.04)
    if S0.best < S.best:
        S = S0
    S.used = budget
    prune = None
    if METHOD == 2 and c["filter"]:
        # Method 1 kept wide-open filters on 3 held-out sounds with none (H12, H15, H16): each scored better with it off.
        knobs, tree, prune = filter_off(tree, knobs, S, note, feats)
    truth_on = "filter" in s
    rank = lambda xs: next((i for i, x in enumerate(xs) if pt.norm(x["table"]) == pt.norm(s["table"])), None)
    return S, knobs, tree, {"picked": pt.norm(c["table"]), "picked_filter": c["filter"], "filter_off_check": prune, "filter_on": has_filter(tree),
                            "filter_right": has_filter(tree) == truth_on, "tried": tried,
                            "pieces": {"table_rank": rank(P["wavetable"]["ranked"]), "table_rank_after_render": rank([x for _, x in ranked]),
                                       "best_off_rank": next(i for i, (_, x) in enumerate(ranked) if not x["filter"])}}


def main():
    cmd = sys.argv[1]
    if cmd == "make":
        return make(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    OUT.mkdir(parents=True, exist_ok=True)
    budget, only = int(sys.argv[2]), set(sys.argv[3:])
    sounds = json.load(open(SET / "sounds.json"))
    lib = s1.load_lib()
    for s in sounds:
        tag = f"{s['name']}_{cmd}"
        if (only and s["name"] not in only) or (OUT / f"{tag}.json").exists():
            continue
        target, _ = sf.read(SET / f"{s['name']}_target.wav", dtype="float32", always_2d=True)
        target = target.T
        rng, t0 = np.random.default_rng(1), time.time()
        S, knobs, tree, extra = match(budget, s, target, lib, rng) if cmd == "match" else s1.check(budget, s, target, rng, cmd == "near")
        res = {"sound": s["name"], "split": s["split"], "arm": cmd, "knobs": len(knobs), "knob_names": [k for _, k, *_ in knobs],
               "truth": {k: s[k] for k in ("table", "pos", "env", "note", "filter") if k in s}, **extra, "secs": round(time.time() - t0)}
        res["truth"]["table"] = pt.norm(res["truth"]["table"])
        pick.save(tag, res, tree, knobs, S, s["note"], target, t.features(target))


if __name__ == "__main__":
    main()

"""PROTOTYPE, throw away. "Step 4: add a filter envelope".

  python step4.py make [N]             N made sounds (default 20): Step 2's sounds (every one filtered), plus Env 2 moving the
                                       cutoff with a random shape and a random amount up or down. The envelope must be heard: the
                                       same sound without it scores 2.5 or more against it.
  python step4.py match BUDGET [NAME]  Step 3's method 2 as it stands. Every filter candidate also carries Env 2 on the cutoff
                                       from a neutral start (amount 0), and the tuner gets its four knobs and the amount.
                                       METHOD=1 for that. METHOD=2 (default): fenv.py reads the cutoff's path from the target
                                       for each filter candidate and sets its cutoff knob and Env 2 start.
  python step4.py truth|near BUDGET [NAME]   checks 2 and 3: the true structure from a random or a near start
SET=step4b holds method 2's fresh sounds. SET=step1|step2b|step3b reruns those sounds, into step4/rerun-<set>/. Rerun resumes: finished sounds are skipped.
"""
import copy, json, os, pickle, sys, time
from pathlib import Path

import numpy as np
import soundfile as sf

import analyse as an
import fenv
import parts as pt
import pick
import render as rd
import retrieve as rv
import step1 as s1
import step2 as s2
import step3 as s3
import tune as t

SET = Path(os.environ.get("SET", "step4"))
OUT = Path(os.environ.get("OUT") or (SET.name if SET.name.startswith("step4") else f"step4/rerun-{SET.name}"))  # method 2 on K: OUT=step4/m2
s1.OUT, s2.OUT, pick.OUT, s3.SET, s3.OUT = SET, OUT, OUT, SET, OUT
s3.METHOD = 2
s1.FIXED["kParamAmount"] = (-100.0, 100.0, False)  # the mapper would keep the start's sign; the amount must be free to go up or down

# A real Env 2 -> filter cutoff slot, as factory presets store it ("BS - Kinetic"): source 3 is Env 2, node Env1.
SLOT = {"destModuleID": 0, "destModuleParamID": 3, "destModuleParamName": "kParamFreq", "destModuleTypeString": "VoiceFilter",
        "plainParams": {"kParamAmount": 0.0}, "source": [3, 0]}
NEUTRAL = {"attack": 1e-3, "decay": 0.5, "sustain": 0.5, "release": 0.1, "amount": 0.0}


def set_fenv(tree, e):
    p = s1.patch.pp(tree["Env1"])
    p.update(kParamAttack=e["attack"], kParamDecay=e["decay"], kParamSustain=e["sustain"], kParamRelease=e["release"])
    tree["ModSlot0"] = copy.deepcopy(SLOT)
    tree["ModSlot0"]["plainParams"]["kParamAmount"] = float(e["amount"])
    return tree


_build = s2.build
s2.build = lambda tb, pos, env, f: set_fenv(_build(tb, pos, env, f), f.get("fenv", NEUTRAL))  # what Step 3's match builds every filter candidate with

# ---- method 2 ------------------------------------------------------------------------
# Method 1 got 3 of 10 adjust sounds below 2.5. The true structure from a near start got 9 of 10, from a random start 2 of 10:
# the envelope needs a start, as every other part did. fenv.py reads the cutoff's path from the target against each candidate's
# table frame, and the fit sets that candidate's cutoff knob and Env 2. Nothing readable (the cutoff never where the harmonics
# show it): the neutral start, as in method 1.
METHOD = int(os.environ.get("METHOD", 2))
FORCE = os.environ.get("FORCE")  # check 1: "table" gives the true table, "filter" also the true filter, "fenv" also the true Env 2
_fp2, _CUR = s2.filter_piece2, {}  # v1 read only when the steady part showed a low-pass


# v2, from the adjust half: a sweep the reader cannot see (a cutoff below the fundamental moves only the level) got a neutral
# start and was screened as if still, so K09's true table fell from 2nd to 23rd. Unread candidates are now also screened with a
# down and an up start, and each tuned candidate first tries a small grid of envelope starts. The reader also runs when the
# steady part shows no low-pass: the filter may only be open while sustaining. v3: the grid only for unread candidates.
DOWN = {"attack": 1e-3, "decay": 0.3, "sustain": 0.5, "release": 0.1, "amount": -60.0}
UP = {**DOWN, "amount": 60.0}
GRID = [{"attack": 1e-3, "decay": d, "sustain": 0.5, "release": 0.1, "amount": a} for a in (-80, -40, 40, 80) for d in (0.08, 0.3, 1.2)]


# v5: an unread start moves the base cutoff so the sustained cutoff stays where the steady part read it (Env 2's level at
# sustain is S squared). Without it, K09's down starts closed an already low filter: every first render scored about 47.
# Dropped: the adjust half stayed at 5 of 10, K04 fell from 0.19 to 6.04 and K09 still rendered at about 50. Method 2 is v4.
def keep_sustain(knob, e):
    return knob


def filter_pieces4(c, f0, typ):
    """The candidate's filter start, as a list: the reader's, or with nothing read, neutral, down and up."""
    f = _fp2(c, f0, typ)
    if "frames" not in _CUR:
        _CUR["frames"] = fenv.frames(_CUR["target"], f0)
    r = fenv.read(_CUR["target"], f0, c["table"], c["pos"], typ, c.get("peak_db", 0.0), cache=_CUR["frames"])
    if r is None:
        f = {**f, "steady_knob": f["knob"]}
        return [f, {**f, "knob": keep_sustain(f["knob"], DOWN), "fenv": DOWN}, {**f, "knob": keep_sustain(f["knob"], UP), "fenv": UP}]
    return [{**f, "read": True, "knob": r["k0"], "fenv": {"attack": r["attack"], "decay": r["decay"], "sustain": r["sustain"], "release": NEUTRAL["release"], "amount": r["amount"]}}]


# v4, from the adjust half: tables were ranked on the steady part alone, where a moving filter on a low note leaves too few
# harmonics: K05's true table was 58th. Now each of 16 loud frames gets its own best low-pass and tables rank by the mean error
# over the note; the filter start keeps the steady part's shape. K01-K10, true table in the top 12: 8, was 7 (K05 58th to 1st).
_SH = []


def wavetable4(target, r, lib, f0, top=12):
    if not _SH:
        _SH.extend(s2.shapes2())
    names, pos, LF = lib

    def errs(tg):
        tg = np.maximum(tg, -70.0); keep = tg > -60
        if keep.sum() < 4:
            keep = np.arange(pt.H) < 4
        E = np.empty((len(_SH), len(LF)))
        for i, (*_, S) in enumerate(_SH):
            d = (tg - (LF + S))[:, keep]; d = d - d.mean(axis=1, keepdims=True)
            E[i] = np.sqrt((np.clip(d, -30, 30) ** 2).mean(axis=1))
        return E

    if "frames" not in _CUR:
        _CUR["frames"] = fenv.frames(target, f0)
    _, F, lv = _CUR["frames"]
    H = np.pad(F, ((0, 0), (0, max(0, pt.H - F.shape[1]))), constant_values=-90)[:, : pt.H]
    idx = np.where(lv > lv.max() - 30)[0]
    idx = idx[np.linspace(0, len(idx) - 1, 16).astype(int)]
    mean = np.mean([errs(H[i] - H[i].max()).min(axis=0) for i in idx], axis=0)
    st = errs(np.array(r["harmonics_db"]))
    out, seen = [], set()
    for i in np.argsort(mean):
        if names[i] in seen:
            continue
        seen.add(names[i])
        kc, slope, g, _ = _SH[int(st[:, i].argmin())]
        out.append({"table": names[i], "pos": round(float(pos[i]), 3), "residual_db": round(float(mean[i]), 2), "lp_harmonic": kc, "lp_slope": slope, "peak_db": g})
        if len(out) == top:
            break
    return {"ranked": out}


def env_start(tree, knobs, note, feats, knob0):
    """The candidate's own start, or the best of GRID on its envelope knobs, by one render each."""
    x = np.array(s1.own(knobs)[0], float)
    idx = {k: i for i, (p, k, *_) in enumerate(knobs) if p == ("Env1",)} | {"amount": next(i for i, (p, *_ ) in enumerate(knobs) if p == ("ModSlot0",))}
    best = (t.score(t.features(rd.render_tree(s3.o.apply(tree, knobs, x), note)), feats), x)
    fi = next((i for i, (_, k, *_) in enumerate(knobs) if k == "kParamFreq"), None)
    for g in GRID:
        y = x.copy()
        if fi is not None:
            y[fi] = s3.o.to_unit(keep_sustain(knob0, g), *knobs[fi][3:])
        for k, i in idx.items():
            v = g["amount"] if k == "amount" else g.get(k.removeprefix("kParam").lower())
            if v is not None:
                y[i] = s3.o.to_unit(v, *knobs[i][3:])
        sc = t.score(t.features(rd.render_tree(s3.o.apply(tree, knobs, y), note)), feats)
        if sc < best[0]:
            best = (sc, y)
    return best[1]


def match(budget, s, target, lib, rng):
    """Step 3's match (its method 2), with the filter envelope pieces above. METHOD=1: Step 3's match as it stands."""
    if METHOD == 1:
        return s3.match(budget, s, target, lib, rng)
    _CUR.update(target=target)
    _CUR.pop("frames", None)
    note, feats = s["note"], t.features(target)
    P = s1.read(target, note, lib)
    r = s1.heard(target)
    f0 = r["f0_hz"] or 440 * 2 ** ((note - 69) / 12)
    P["wavetable"] = wavetable4(target, r, lib, f0)
    if FORCE:  # check 1, each piece alone: the true table, at the position the wavetable piece fits for it
        P["wavetable"] = {"ranked": [x for x in wavetable4(target, r, lib, f0, top=400)["ranked"] if pt.norm(x["table"]) == pt.norm(s["table"])]}
    screen = int(os.environ.get("SCREEN", budget // 6))
    mk = lambda c: s1.ready(s2.build(c["table"], c["pos"], P["envelope"], c["filter"]) if c["filter"] else s1.build(c["table"], c["pos"], P["envelope"]), note, target)
    ranked = []
    for c0 in P["wavetable"]["ranked"][:12]:
        fx = FORCE in ("filter", "fenv")
        types = [s["filter"]["type"]] if fx else s2.TYPES
        fs = [x for typ in types for x in filter_pieces4(c0, f0, typ)]
        if FORCE == "fenv":  # and the true Env 2: only the amp envelope comes from the method
            fs = [{**fs[0], "read": True, "fenv": s["fenv"]}]
        for f in fs + ([] if fx else [None]):
            if fx:  # and the true filter: only the amp envelope and Env 2 come from the method
                f = {**f, "knob": s["filter"]["knob"], "reso": s["filter"]["reso"]} | ({"steady_knob": s["filter"]["knob"]} if "steady_knob" in f else {})
            c = {**c0, "filter": f}
            ranked.append((t.score(t.features(rv.gain_match(rd.render_tree(mk(c), note), target)), feats), c))
    ranked.sort(key=lambda x: x[0])
    tried, runs = [], []
    for _, c in ranked[:3]:
        tree = mk(c)
        # v3: the grid only where nothing was read. On read sweeps (v2), one render often preferred a grid start that then tuned
        # worse: K02 2.66 to 3.84, K08 0.76 to 2.34.
        x0 = (lambda kn, tree=tree, c=c: [env_start(tree, kn, note, feats, c["filter"]["steady_knob"])]) if c["filter"] and not c["filter"].get("read") else s1.own
        S, knobs = s1.run(tree, note, feats, x0, screen, rng)
        tried.append({"table": pt.norm(c["table"]), "pos": c["pos"], "filter": c["filter"], "first_render": round(next(x for x, y in ranked if y is c), 3), "score": round(S.best, 3)})
        runs.append((S, knobs, tree, c))
    best = min(runs, key=lambda x: x[0].best)
    offs = [x for x in runs if not x[3]["filter"]]
    if offs and min(x[0].best for x in offs) <= best[0].best + s3.MARGIN:
        best = min(offs, key=lambda x: x[0].best)
    S0, knobs, tree, c = best
    bx = S0.bx.copy()
    S, knobs = s1.run(tree, note, feats, lambda kn: [bx], budget - screen * len(tried), rng, sigma=0.04)
    if S0.best < S.best:
        S = S0
    S.used = budget
    prune = None
    if c["filter"]:
        knobs, tree, prune = s3.filter_off(tree, knobs, S, note, feats)
    rank = lambda xs: next((i for i, x in enumerate(xs) if pt.norm(x["table"]) == pt.norm(s["table"])), None)
    return S, knobs, tree, {"picked": pt.norm(c["table"]), "picked_filter": c["filter"], "filter_off_check": prune, "filter_on": s3.has_filter(tree),
                            "filter_right": s3.has_filter(tree) == ("filter" in s), "tried": tried,
                            "pieces": {"table_rank": rank(P["wavetable"]["ranked"]), "table_rank_after_render": rank([x for _, x in ranked])}}


def fenv_of(tree):
    p, a = tree["Env1"]["plainParams"], tree.get("ModSlot0", {}).get("plainParams")
    if not isinstance(a, dict) or not s3.has_filter(tree):
        return None
    return {k: round(float(p[f"kParam{k.title()}"]), 4) for k in ("attack", "decay", "sustain", "release")} | {"amount": round(float(a["kParamAmount"]), 1)}


def make(n, seed=int(os.environ.get("SEED", 44)), prefix=os.environ.get("PREFIX", "K")):
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "lib.pkl").exists():
        (OUT / "lib.pkl").symlink_to((Path("step1") / "lib.pkl").resolve())
    rng = np.random.default_rng(seed)
    tables, out, dropped = an.table_list(), [], {"filter": 0, "fenv": 0}
    # Up and down 5 and 5 in each half: drawn freely, 16 of 20 went down, since an upward sweep is heard less often.
    sign = np.concatenate([rng.permutation([1] * 5 + [-1] * 5), rng.permutation([1] * 5 + [-1] * 5)]) if n == 20 else rng.choice([-1, 1], n)
    logu = lambda lo, hi: float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
    while len(out) < n:
        s = {"table": str(rng.choice(tables)), "pos": round(float(rng.uniform(0, 1)), 3), "note": int(rng.choice([36, 48, 60])),
             "env": {"attack": logu(5e-4, 1.0), "decay": logu(0.05, 4.0), "sustain": round(float(rng.uniform(0, 1)), 3), "release": logu(0.01, 1.0)}}
        f0 = 440 * 2 ** ((s["note"] - 69) / 12)
        typ = str(rng.choice(s2.TYPES))
        hz = min(f0 * 2 ** rng.uniform(0, 4.5), 8000.0)
        s["filter"] = {"type": typ, "cutoff_hz": round(hz), "knob": round(s2.hz_to_knob(hz, typ), 4), "reso": round(float(rng.uniform(0, 75)), 1)}
        s["fenv"] = {"attack": logu(5e-4, 1.0), "decay": logu(0.05, 4.0), "sustain": round(float(rng.uniform(0, 1)), 3), "release": logu(0.01, 1.0),
                     "amount": round(float(sign[len(out)] * rng.uniform(10, 90)), 1)}
        plain = _build(s["table"], s["pos"], s["env"], s["filter"])  # filtered, no envelope
        tree = set_fenv(copy.deepcopy(plain), s["fenv"])
        a = rd.render_tree(tree, s["note"])
        if not np.isfinite(a).all() or abs(a).max() < 1e-3:
            continue
        dry = rd.render_tree(s1.build(s["table"], s["pos"], s["env"]), s["note"])
        s["filter_heard"] = round(t.score(t.features(rv.gain_match(dry, a)), t.features(a)), 2)
        s["fenv_heard"] = round(t.score(t.features(rv.gain_match(rd.render_tree(plain, s["note"]), a)), t.features(a)), 2)
        if s["filter_heard"] < 2.5 or s["fenv_heard"] < 2.5:
            dropped["filter" if s["filter_heard"] < 2.5 else "fenv"] += 1
            continue
        s["name"] = f"{prefix}{len(out) + 1:02d}"
        s["split"] = "adjust" if len(out) < n // 2 else "held_out"
        s["repeat_score"] = round(t.score(t.features(rd.render_tree(tree, s["note"])), t.features(a)), 3)
        sf.write(OUT / f"{s['name']}_target.wav", a.T, s1.SR, subtype="FLOAT")
        pickle.dump(tree, open(OUT / f"{s['name']}_true.pkl", "wb"))
        out.append(s)
        print(json.dumps(s), flush=True)
    json.dump(out, open(OUT / "sounds.json", "w"), indent=1)
    print(json.dumps({"made": n, "dropped_not_heard": dropped}))


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
        extra["fenv_picked"] = fenv_of(s3.o.apply(tree, knobs, S.bx))
        res = {"sound": s["name"], "split": s["split"], "arm": cmd, "knobs": len(knobs), "knob_names": [k for _, k, *_ in knobs],
               "truth": {k: s[k] for k in ("table", "pos", "env", "note", "filter", "fenv") if k in s}, **extra, "secs": round(time.time() - t0)}
        res["truth"]["table"] = pt.norm(res["truth"]["table"])
        pick.save(tag, res, tree, knobs, S, s["note"], target, t.features(target))


if __name__ == "__main__":
    main()

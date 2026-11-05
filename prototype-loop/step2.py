"""PROTOTYPE, throw away. "Step 2: add a filter".

  python step2.py make [N]             N made sounds (default 20): Step 1's sounds plus the voice filter, a random common
                                       low-pass type, cutoff and resonance. The filter must be heard: leaving it out scores 2.5 or more.
  python step2.py match BUDGET [NAME]  Step 1's method; the filter piece sets the type and cutoff start, the tuner also turns
                                       cutoff and resonance. Truth only scores.
  python step2.py table BUDGET [NAME]  check 1: the true table forced in, every other piece as it is
  python step2.py truth|near BUDGET [NAME]   checks 2 and 3: the true structure from a random or a near start
SET=step1 reruns Step 1's sounds with this method, into step2/rerun1/. Rerun resumes: finished sounds are skipped.
"""
import json, os, pickle, sys, time
from pathlib import Path

import numpy as np
import analyse as an
import soundfile as sf

import patch
import parts as pt
import pick
import render as rd
import retrieve as rv
import step1 as s1
import tune as t

SET = Path(os.environ.get("SET", "step2"))
s1.OUT = SET  # targets, truths and lib.pkl
OUT = Path(os.environ.get("OUT") or ("step2" if SET.name == "step2" else "step2/rerun1"))
METHOD = int(os.environ.get("METHOD", 1))  # 2: the wavetable fit also reads a resonant peak, and the cutoff start is the corner
pick.OUT = OUT
TYPES = ["MgL6", "MgL12", "MgL18", "MgL24", "LadderMg"]  # the common low-pass types in factory presets
s1.FIXED.update(kParamFreq=(0.0, 1.0, False), kParamReso=(0.0, 100.0, False))

# Cutoff knob -> Hz at -3 dB, per type, measured by cal2.py: log-linear between 100 Hz and 9 kHz.
_cal = json.load(open("step2_cutoff.json"))
FIT = {}
for typ, rows in _cal.items():
    u, hz = np.array([(a, b) for a, b, _ in rows if 100 <= b <= 9000]).T
    FIT[typ] = np.polyfit(u, np.log2(hz), 1)


def hz_to_knob(hz, typ):
    m, b = FIT[typ]
    return float(np.clip((np.log2(hz) - b) / m, 0, 1))


def set_filter(tree, f):
    p = patch.pp(tree["VoiceFilter0"])
    p["kParamEnable"], p["kParamFreq"], p["kParamReso"] = 1.0, float(f["knob"]), float(f["reso"])
    if f["type"] != "MgL12":  # MgL12 is Serum's default and is stored as absent
        p["kParamType"] = f["type"]
    return tree


def build(table, pos, env, f):
    return set_filter(s1.build(table, pos, env), f)


def make(n, seed=int(os.environ.get("SEED", 40)), prefix=os.environ.get("PREFIX", "F")):
    OUT.mkdir(parents=True, exist_ok=True)
    if not (OUT / "lib.pkl").exists():
        (OUT / "lib.pkl").symlink_to((Path("step1") / "lib.pkl").resolve())
    rng = np.random.default_rng(seed)
    tables, out, dropped = an.table_list(), [], 0
    while len(out) < n:
        s = {"table": str(rng.choice(tables)), "pos": round(float(rng.uniform(0, 1)), 3), "note": int(rng.choice([36, 48, 60])),
             "env": {"attack": float(np.exp(rng.uniform(np.log(5e-4), np.log(1.0)))), "decay": float(np.exp(rng.uniform(np.log(0.05), np.log(4.0)))),
                     "sustain": round(float(rng.uniform(0, 1)), 3), "release": float(np.exp(rng.uniform(np.log(0.01), np.log(1.0))))}}
        f0 = 440 * 2 ** ((s["note"] - 69) / 12)
        typ = str(rng.choice(TYPES))
        hz = min(f0 * 2 ** rng.uniform(0, 4.5), 8000.0)  # from the fundamental to about the 22nd harmonic
        s["filter"] = {"type": typ, "cutoff_hz": round(hz), "knob": round(hz_to_knob(hz, typ), 4), "reso": round(float(rng.uniform(0, 75)), 1)}
        tree = build(s["table"], s["pos"], s["env"], s["filter"])
        a = rd.render_tree(tree, s["note"])
        if not np.isfinite(a).all() or abs(a).max() < 1e-3:
            continue
        dry = rd.render_tree(s1.build(s["table"], s["pos"], s["env"]), s["note"])
        s["filter_heard"] = round(t.score(t.features(rv.gain_match(dry, a)), t.features(a)), 2)  # the dry sound, scored as a match
        if s["filter_heard"] < 2.5:
            dropped += 1
            continue
        s["name"] = f"{prefix}{len(out) + 1:02d}"
        s["split"] = "adjust" if len(out) < n // 2 else "held_out"
        s["repeat_score"] = round(t.score(t.features(rd.render_tree(tree, s["note"])), t.features(a)), 3)
        sf.write(OUT / f"{s['name']}_target.wav", a.T, s1.SR, subtype="FLOAT")
        pickle.dump(tree, open(OUT / f"{s['name']}_true.pkl", "wb"))
        out.append(s)
        print(json.dumps(s), flush=True)
    json.dump(out, open(OUT / "sounds.json", "w"), indent=1)
    print(json.dumps({"made": n, "dropped_filter_not_heard": dropped}))


def filter_piece(c, f0, typ=None):
    """The low-pass the wavetable fit took off this table, as a filter start. No low-pass: a wide-open filter.
    The type comes from the fit's slope unless given; the cutoff is the same Hz whatever the type."""
    slope = c["lp_slope"]
    typ = typ or ({6: "MgL6", 12: "MgL12", 18: "MgL18"}.get(int(slope), "MgL24") if slope else "MgL6")
    if not slope:
        return {"type": typ, "knob": 1.0, "reso": 10.0}
    return {"type": typ, "knob": hz_to_knob(max(c["lp_harmonic"], 1.0) * f0, typ), "reso": 10.0}


# ---- method 2 ------------------------------------------------------------------------
# cal3.py: at resonance r the peak stands about 0.34 r dB above the plain low-pass (r up to 70), the same for every type,
# and it sits at the corner, this many octaves above the -3 dB point the cutoff map holds.
DB_PER_RESO = 0.34
CORNER_OCT = {"MgL6": -0.42, "MgL12": 0.17, "MgL18": 0.46, "MgL24": 0.81, "LadderMg": 0.70}
PEAKS = (0, 5, 10, 15, 20, 25)


def shapes2():
    """Step 1's low-pass shapes, each also with a resonant peak of g dB at the corner kc."""
    k = np.log2(np.arange(1, pt.H + 1))
    out = []
    for kc, slope, sh in pt.lowpass_shapes():
        for g in PEAKS if slope else (0,):
            out.append((kc, slope, g, sh + g * np.exp(-0.5 * ((k - np.log2(max(kc, 1))) / 0.2) ** 2)))
    return out


def wavetable2(a, note, r, lib, top=12):
    """pt.wavetable with resonant shapes: a resonance peak no longer reads as the table's own harmonics."""
    tg = np.maximum(np.array(r["harmonics_db"]), -70.0)
    keep = tg > -60
    if keep.sum() < 4:
        keep = np.arange(pt.H) < 4
    names, pos, F = lib
    sh = shapes2()
    best = np.full(len(F), np.inf); bshape = np.zeros(len(F), int)
    for si, (_, _, _, S) in enumerate(sh):
        diff = (tg - (F + S))[:, keep]
        diff = diff - diff.mean(axis=1, keepdims=True)
        err = np.sqrt((np.clip(diff, -30, 30) ** 2).mean(axis=1))
        better = err < best
        best[better], bshape[better] = err[better], si
    out, seen = [], set()
    for i in np.argsort(best):
        if names[i] in seen:
            continue
        seen.add(names[i])
        kc, slope, g, _ = sh[bshape[i]]
        out.append({"table": names[i], "pos": round(float(pos[i]), 3), "residual_db": round(float(best[i]), 2), "lp_harmonic": kc, "lp_slope": slope, "peak_db": g})
        if len(out) == top:
            break
    return {"ranked": out}


def filter_piece2(c, f0, typ):
    if not c["lp_slope"]:
        return {"type": typ, "knob": 1.0, "reso": 10.0}
    hz = max(c["lp_harmonic"], 1.0) * f0 / 2 ** CORNER_OCT[typ]
    return {"type": typ, "knob": hz_to_knob(hz, typ), "reso": float(np.clip(c["peak_db"] / DB_PER_RESO, 0, 90)) if c["peak_db"] else 10.0}


def match(budget, s, target, lib, rng, force_table=False):
    """Step 1's match, with each table candidate carrying its own filter start."""
    note, feats = s["note"], t.features(target)
    P = s1.read(target, note, lib)
    f0 = s1.heard(target)["f0_hz"] or 440 * 2 ** ((note - 69) / 12)
    wt = wavetable2 if METHOD == 2 else pt.wavetable
    fp = filter_piece2 if METHOD == 2 else filter_piece
    if METHOD == 2:
        P["wavetable"] = wt(target, note, s1.heard(target), lib, top=12)
    if force_table:  # check 1, the other pieces alone: the true table, at the position the wavetable piece fits for it
        P["wavetable"] = wt(target, note, s1.heard(target), lib, top=400)
        P["wavetable"]["ranked"] = [x for x in P["wavetable"]["ranked"] if pt.norm(x["table"]) == pt.norm(s["table"])]
    screen = int(os.environ.get("SCREEN", budget // 6))
    mk = lambda c: s1.ready(build(c["table"], c["pos"], P["envelope"], c["filter"]), note, target)
    ranked = []  # v2: one render per table and filter type. The slope alone misreads the type under resonance (F05).
    for c0 in P["wavetable"]["ranked"][:12]:
        for typ in TYPES:
            c = {**c0, "filter": fp(c0, f0, typ)}
            ranked.append((t.score(t.features(rv.gain_match(rd.render_tree(mk(c), note), target)), feats), c))
    ranked.sort(key=lambda x: x[0])
    tried, best = [], None
    for _, c in ranked[:3]:  # frozen at v2. v3 (3 distinct tables) also passed the adjust half but scored worse on average
        tree = mk(c)
        S, knobs = s1.run(tree, note, feats, s1.own, screen, rng)
        tried.append({"table": pt.norm(c["table"]), "pos": c["pos"], "filter": c["filter"], "first_render": round(next(x for x, y in ranked if y is c), 3), "score": round(S.best, 3)})
        if best is None or S.best < best[0].best:
            best = (S, knobs, tree, c)
    S0, knobs, tree, c = best
    bx = S0.bx.copy()
    S, knobs = s1.run(tree, note, feats, lambda kn: [bx], budget - screen * len(tried), rng, sigma=0.04)
    if S0.best < S.best:
        S = S0
    S.used = budget
    rank = lambda xs: next((i for i, x in enumerate(xs) if pt.norm(x["table"]) == pt.norm(s["table"])), None)
    return S, knobs, tree, {"picked": pt.norm(c["table"]), "picked_filter": c["filter"], "slope_type": filter_piece(c, f0)["type"], "tried": tried,
                            "pieces": {"table_rank": rank(P["wavetable"]["ranked"]), "table_rank_after_render": rank([x for _, x in ranked])}}


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
        S, knobs, tree, extra = match(budget, s, target, lib, rng, cmd == "table") if cmd in ("match", "table") else s1.check(budget, s, target, rng, cmd == "near")
        res = {"sound": s["name"], "split": s["split"], "arm": cmd, "knobs": len(knobs), "knob_names": [k for _, k, *_ in knobs],
               "truth": {k: s[k] for k in ("table", "pos", "env", "note", "filter") if k in s}, **extra, "secs": round(time.time() - t0)}
        res["truth"]["table"] = pt.norm(res["truth"]["table"])
        pick.save(tag, res, tree, knobs, S, s["note"], target, t.features(target))


if __name__ == "__main__":
    main()

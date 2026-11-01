"""PROTOTYPE, throw away. One run of the loop: analyse, choose, tune, render, compare, repeat.

Usage:
  python loop.py SCRATCH synthetic            the self-test on patches from this template
  python loop.py SCRATCH rules JOB [JOB ...]  rules alone on prepared sounds
"""
import copy, json, sys, time
from pathlib import Path

import numpy as np

import analyse as an
import compare as c
import patch as p
import render as rd
import rules
import tune as t

BUDGET = 1500  # evaluations per tuning; 5 tunings per sound on either arm


def report(a):
    return an.analyse(a)


def side_by_side(target, got):
    """What a designer, or a match report, sees: the same numbers for both."""
    keys = [k for k in target if k not in ("harmonics_db",)]
    h = np.array(target["harmonics_db"]) - np.array(got["harmonics_db"])
    return {"target": {k: target[k] for k in keys}, "render": {k: got[k] for k in keys},
            "harmonic_error_db": round(float(np.sqrt((h[:16] ** 2).mean())), 1),
            "harmonics_target_minus_render_db": [round(float(x), 1) for x in h[:16]]}


def run_rules(scratch, target_audio, seed, log=print):
    target = report(target_audio)
    note = int(round(target["midi"]))
    ranking = an.rank_tables(target["harmonics_db"], scratch)
    tuner = t.Tuner(scratch, target_audio, note)
    d0 = rules.first_design(target, ranking)
    start = rules.start_values(target, d0, ranking)
    first_audio = t.render_values(d0, start, note)
    best_s, best_v, used, _ = tuner.tune(d0, BUDGET, seed, start)
    best_d, trace = d0, [("first", best_s)]
    first_near = c.near(target_audio, first_audio)
    for round_i in range(2):
        got = report(t.render_values(best_d, best_v, note))
        for n, d in enumerate(rules.revise(best_d, target, got, ranking)):
            s, v, u, _ = tuner.tune(d, BUDGET, seed + 10 * (round_i + 1) + n, best_v)
            used += u
            trace.append((f"r{round_i+1}.{n}", s))
            if s < best_s:
                best_s, best_v, best_d = s, v, d
        log(f"  round {round_i+1}: best score {best_s:.2f}, {used} evals")
    tuner.close()
    audio = t.render_values(best_d, best_v, note)
    return {"design": best_d, "values": best_v, "score": best_s, "near": c.near(target_audio, audio), "gap": c.gap(target_audio, audio), "first_near": first_near,
            "evals": used, "trace": trace, "note": note, "start_score": None}


SYNTHETIC = [
    # A plain filtered saw-like bass, a moving lead, and a wide pad-ish synth with space.
    ({"osc": [{"table": "Analog/Basic Shapes.wav", "octave": 0, "warp": None, "unison": False}], "sub": True, "noise": False,
      "filter": "MgL24", "routes": ["filter_env"], "fx": []},
     {"cutoff": 0.35, "reso": 0.3, "filter_env_amt": 0.7, "env2_decay": 0.4, "env2_sustain": 0.1, "osc0_pos": 0.3, "sub_vol": 0.5, "sustain": 0.7}, 36),
    ({"osc": [{"table": "S2 Tables/Analog/DM - OSCAR.wav", "octave": 0, "warp": None, "unison": True}], "sub": False, "noise": False,
      "filter": None, "routes": ["table_env", "pitch_lfo"], "fx": [p.DIST]},
     {"osc0_pos": 0.2, "table_env_amt": 0.8, "env2_decay": 0.5, "lfo_rate": 0.7, "pitch_lfo_amt": 0.4, "osc0_detune": 0.4, "dist_drive": 0.5}, 60),
    ({"osc": [{"table": "Analog/Basic Mini.wav", "octave": 0, "warp": None, "unison": True},
              {"table": "S2 Tables/Default Shapes.wav", "octave": 1, "warp": None, "unison": False}], "sub": False, "noise": True,
      "filter": "MgL12", "routes": ["cutoff_lfo"], "fx": [p.CHORUS, p.REVERB]},
     {"cutoff": 0.5, "lfo_rate": 0.4, "cutoff_lfo_amt": 0.5, "osc1_vol": 0.4, "noise_vol": 0.2, "reverb_wet": 0.5, "attack": 0.4, "release": 0.6}, 48),
]


def synthetic(scratch):
    for i, (d, v, note) in enumerate(SYNTHETIC):
        target = t.render_values(d, v, note)
        r = report(target)
        t0 = time.time()
        tuner = t.Tuner(scratch, target, note)
        random_start = {n: s for n, (_, s) in p.knobs(d).items()}
        s_true, v_true, used, hist = tuner.tune(d, BUDGET * 2, 1, random_start)
        audio = t.render_values(d, v_true, note)
        tuner.close()
        res = run_rules(scratch, target, 1, log=lambda *_: None)
        print(f"patch {i}: heard midi {r['midi']} (true {note})  true design tuned: score {s_true:.2f} gap {c.gap(target, audio):.2f}  "
              f"rules: score {res['score']:.2f} near {res['near']:.2f} first near {res['first_near']:.2f}  {time.time()-t0:.0f}s")
        print("   rules design", json.dumps({k: v2 for k, v2 in res["design"].items()})[:300])
        print("   trace", [(n, round(s, 2)) for n, s in res["trace"]])


if __name__ == "__main__":
    scratch = Path(sys.argv[1])
    p.BASE = scratch / "base.pkl"
    if sys.argv[2] == "synthetic":
        synthetic(scratch)
    elif sys.argv[2] == "rules":
        key = json.loads((scratch / "key.json").read_text())
        for job in sys.argv[3:]:
            audio = np.load(scratch / "jobs" / job / "target.npy")
            res = run_rules(scratch, audio, 1)
            (scratch / "jobs" / job / "rules.json").write_text(json.dumps(res))
            print(key[job], {k: (round(res[k], 2)) for k in ("score", "near", "gap", "first_near")}, res["design"], flush=True)

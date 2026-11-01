"""PROTOTYPE, throw away. The designer's only way in: what an MCP tool would give it.

  python designer_step.py SCRATCH JOB brief
  python designer_step.py SCRATCH JOB try designs.json

`try` takes a JSON list of designs: 1 design in round 1, then 2 per round, 5 tunings in all.
The target is audio only. Knob values stay inside the tool.
"""
import json, sys
from pathlib import Path

import numpy as np

import analyse as an
import compare as c
import loop
import patch as p
import rules
import tune as t

ROUNDS = [1, 2, 2]
WARPS = ["kSync", "kPD_OSC", "kFM_OSC", "kFM_SUB", "kPD_SUB", "kDistTube", "kFilterLPF"]
FILTERS = ["MgL6", "MgL12", "MgL18", "MgL24", "LadderMg", "LadderEMS", "LadderAcid"]
ROUTES = ["filter_env", "table_env", "table_lfo", "pitch_lfo", "cutoff_lfo"]


def check(d):
    assert 1 <= len(d["osc"]) <= 2, "1 or 2 oscillators"
    tables = set(an.table_list())
    for o in d["osc"]:
        assert o["table"] in tables, f'unknown table {o["table"]}'
        assert o.get("warp") in [None] + WARPS, f'unknown warp {o.get("warp")}'
        assert -3 <= o.get("octave", 0) <= 3
    assert d.get("filter") in [None] + FILTERS, "unknown filter"
    assert set(d.get("routes", [])) <= set(ROUTES), "unknown route"
    assert set(d.get("fx", [])) <= set(p.FX_TYPE), "unknown fx"
    return {"osc": d["osc"], "sub": bool(d.get("sub")), "noise": bool(d.get("noise")), "filter": d.get("filter"), "routes": d.get("routes", []), "fx": d.get("fx", [])}


def main():
    global ROUNDS
    scratch, job, cmd = Path(sys.argv[1]), Path(sys.argv[1]) / "jobs" / sys.argv[2], sys.argv[3]
    p.BASE = scratch / "base.pkl"
    audio = np.load(job / "target.npy")
    state_file = job / "state.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {"round": 0, "best": None, "log": []}
    target = loop.report(audio)
    ranking = an.rank_tables(target["harmonics_db"], scratch)

    if cmd == "brief":
        print(json.dumps({
            "target": target, "table_candidates": ranking, "budget": {"rounds": ROUNDS, "evaluations_per_design": loop.BUDGET},
            "request": (job / "request.txt").read_text() if (job / "request.txt").exists() else None,
            "choices": {"octave": "-3 to 3", "filter": FILTERS, "warp": WARPS, "routes": ROUTES, "fx": list(p.FX_TYPE), "tables": "any of the 288 factory tables; see tables.txt"},
            "design_shape": {"osc": [{"table": "Analog/Basic Shapes.wav", "octave": 0, "warp": None, "unison": False}], "sub": False, "noise": False, "filter": None, "routes": [], "fx": []},
        }, indent=1))
        return

    designs = [check(x) for x in json.load(open(sys.argv[4]))]
    r = state["round"]
    if (job / "rounds").exists():  # a request is one extra tuning, outside the arm comparison
        ROUNDS = json.loads((job / "rounds").read_text())
    assert r < len(ROUNDS), "no rounds left"
    assert len(designs) == ROUNDS[r], f"round {r+1} takes {ROUNDS[r]} design(s)"
    note = int(round(target["midi"]))
    tuner = t.Tuner(scratch, audio, note, workers=int(job.joinpath("workers").read_text()) if job.joinpath("workers").exists() else 8)
    results = []
    for n, d in enumerate(designs):
        start = dict(rules.start_values(target, d, ranking), **((state["best"] or {}).get("values") or {}))
        if state["best"] is None:
            state["first_near"] = c.near(audio, t.render_values(d, start, note))
        s, v, used, _ = tuner.tune(d, loop.BUDGET, state.get("seed", 1) + 10 * r + n, start)
        rendered = t.render_values(d, v, note)
        got = loop.report(rendered)
        tuned = {k: round(float(fn(v[k])), 3) for k, (fn, _) in p.knobs(d).items()}
        results.append({"design_index": n, "score": round(s, 2), "score_parts_db": {k: round(x, 2) for k, x in t.parts(t.features(rendered), t.features(audio)).items()},
                        "near": round(c.near(audio, rendered), 2), "tuned_knobs": tuned, **loop.side_by_side(target, got)})
        state["log"].append({"round": r + 1, "design": d, "score": s})
        if state["best"] is None or s < state["best"]["score"]:
            state["best"] = {"design": d, "values": v, "score": s}
    tuner.close()
    state["round"] = r + 1
    state_file.write_text(json.dumps(state))
    print(json.dumps({"round": r + 1, "rounds_left": len(ROUNDS) - r - 1, "best_score_so_far": round(state["best"]["score"], 2), "results": results}, indent=1))


if __name__ == "__main__":
    main()

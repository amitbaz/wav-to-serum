"""PROTOTYPE, throw away. The "rules alone" designer: fixed thresholds on the analysis, no model."""
import copy, math

import numpy as np

import patch as p

FILTER = "MgL24"


def inv_log(lo, hi, x):
    return float(np.clip(math.log(max(x, lo) / lo) / math.log(hi / lo), 0, 1))


def bright_ratio(r):
    c = r["centroid_hz"]
    return max(c["t0.05"], 1) / max(c["t1.0"], 1)


def first_design(r, ranking):
    d = p.default_design()
    d["osc"][0]["table"] = ranking[0]["table"]
    h = r["harmonics_db"]
    if ranking[0]["error_db"] > 6:
        d["osc"].append({"table": ranking[1]["table"], "octave": 0, "warp": None, "unison": False})
    d["sub"] = h[0] > -1 and h[1] < -10
    d["noise"] = r["noise_ratio"] > 0.1
    moves = bright_ratio(r) > 1.4
    if moves or np.mean(h[7:16]) < -30:
        d["filter"] = FILTER
    if moves:
        d["routes"].append("filter_env")
    if r["brightness_wobble"]["depth"] > 0.1:
        d["routes"].append("table_lfo")
    if r["pitch_spread_cents"] > 6:
        d["routes"].append("pitch_lfo")
    if r["stereo_side_db"] > -15:
        d["osc"][0]["unison"] = True
    if r["tail_db_below_peak"] < 45:
        d["fx"].append(p.REVERB)
    return d


def start_values(r, d, ranking):
    fine = 100 * (r["midi"] - round(r["midi"]))
    v = {
        "attack": inv_log(0.0005, 2.0, max(r["attack_s"], 0.0005)),
        "decay": inv_log(0.01, 8.0, max(r["decay_s"], 0.01)),
        "sustain": float(np.clip(10 ** (-r["sustain_db_below_peak"] / 20), 0, 1)),
        "release": inv_log(0.005, 4.0, max(r["release_s"] / 3, 0.005)),
        "osc0_fine": float(np.clip(0.5 + fine / 60, 0, 1)),
    }
    pos = {x["table"]: x["pos"] for x in ranking}
    for i, o in enumerate(d["osc"]):
        if o["table"] in pos:
            v[f"osc{i}_pos"] = pos[o["table"]]
    return v


def revise(d, target, got, ranking):
    """Two new designs from the largest gaps. Deterministic."""
    moves = []
    if abs(bright_ratio(target) - bright_ratio(got)) > 0.25 and "filter_env" not in d["routes"]:
        moves.append("filter_env")
    if target["noise_ratio"] - got["noise_ratio"] > 0.05 and not d["noise"]:
        moves.append("noise")
    if target["stereo_side_db"] - got["stereo_side_db"] > 6 and not d["osc"][0]["unison"]:
        moves.append("unison")
    if target["tail_db_below_peak"] - got["tail_db_below_peak"] < -8 and p.REVERB not in d["fx"]:
        moves.append("reverb")
    if target["brightness_wobble"]["depth"] > got["brightness_wobble"]["depth"] + 0.05 and "table_lfo" not in d["routes"]:
        moves.append("table_lfo")
    if target["pitch_spread_cents"] > got["pitch_spread_cents"] + 4 and "pitch_lfo" not in d["routes"]:
        moves.append("pitch_lfo")
    if len(d["osc"]) == 1:
        moves.append("second_osc")

    def apply(move):
        n = copy.deepcopy(d)
        if move == "noise":
            n["noise"] = True
        elif move == "unison":
            n["osc"][0]["unison"] = True
        elif move == "reverb":
            n["fx"].append(p.REVERB)
        elif move == "second_osc":
            used = {o["table"] for o in n["osc"]}
            n["osc"].append({"table": next(x["table"] for x in ranking if x["table"] not in used), "octave": 0, "warp": None, "unison": False})
        else:
            if move == "filter_env" and not n["filter"]:
                n["filter"] = FILTER
            n["routes"].append(move)
        return n

    used = {o["table"] for o in d["osc"]}
    swap = copy.deepcopy(d)
    swap["osc"][0]["table"] = next(x["table"] for x in ranking if x["table"] not in used)
    out = [apply(m) for m in moves[:1]] + [swap]
    if len(out) < 2 and len(moves) > 1:
        out.append(apply(moves[1]))
    return out

"""PROTOTYPE, throw away. "Can we pick a sound's structure from the audio?": a preset's structure, part by part.

Structure = which parts are on and how they are wired, with knob values left out.
  python structure.py OLDWORK      the rules' and the designer's choices next to each true structure
"""
import csv, json, sys
from pathlib import Path

import serum2_preset_loader as s

FX = {0: "Distortion", 1: "Flanger", 2: "Phaser", 3: "Chorus", 4: "Delay", 5: "Comp", 6: "Reverb", 7: "EQ", 8: "Filter", 9: "Hyper", 10: "Bode", 11: "Convolve", 12: "Utils"}
SRC = {2: "Env1", 3: "Env2", 4: "Env3", 5: "Env4", 6: "LFO1", 7: "LFO2", 8: "LFO3", 9: "LFO4"}  # 3 and 6 checked in check_writer.py; the rest guessed in order


def pp(node):
    p = node.get("plainParams") if isinstance(node, dict) else None
    return p if isinstance(p, dict) else {}


def table(path):
    return path.removeprefix("S2 Tables/")


def of_tree(t):
    osc = []
    for i in range(3):
        n = t.get(f"Oscillator{i}", {})
        p = pp(n)
        if not p.get("kParamEnable", i == 0) or p.get("kParamVolume", 0.75) == 0:
            continue
        kind = p.get("kParamType", "WT")
        wt = n.get(f"WTOsc{i}", {})
        w = pp(wt)
        osc.append({"kind": kind, "table": table(wt.get("relativePathToWT", "")) if kind == "WT" else None,
                    "warp": w.get("kParamWarpMenu"), "unison": int(p.get("kParamUnison", 1)), "octave": int(p.get("kParamOctave", 0))})
    on = lambda i: bool(pp(t.get(f"Oscillator{i}", {})).get("kParamEnable")) and pp(t.get(f"Oscillator{i}", {})).get("kParamVolume", 0.75) > 0
    filters = [pp(t[f"VoiceFilter{i}"]).get("kParamType", "MgL12") for i in range(2) if pp(t.get(f"VoiceFilter{i}", {})).get("kParamEnable")]
    mods = sorted({f"{SRC.get(v['source'][0], 'src' + str(v['source'][0]))}>{v['destModuleTypeString']}.{v['destModuleParamName'].removeprefix('kParam')}"
                   for k, v in t.items() if k.startswith("ModSlot") and isinstance(v, dict) and v.get("source")})
    fx = [[FX.get(x["type"], str(x["type"])) for x in t.get(f"FXRack{r}", {}).get("FX", []) or []] for r in range(3)]
    return {"osc": osc, "sub": on(4), "noise": on(3), "filters": filters, "mods": mods, "fx": fx}


ROUTE = {"filter_env": ["Env2>VoiceFilter.Freq"], "table_env": ["Env2>WTOsc.TablePos"], "table_lfo": ["LFO1>WTOsc.TablePos"],
         "pitch_lfo": ["LFO1>Oscillator.Fine"], "cutoff_lfo": ["LFO1>VoiceFilter.Freq"]}


def of_design(d):
    return {"osc": [{"kind": "WT", "table": table(o["table"]), "warp": o.get("warp"), "unison": 4 if o.get("unison") else 1, "octave": o.get("octave", 0)} for o in d["osc"]],
            "sub": d["sub"], "noise": d["noise"], "filters": [d["filter"]] if d["filter"] else [],
            "mods": sorted({m for r in d["routes"] for m in ROUTE[r]}), "fx": [list(d["fx"]), [], []]}


def diff(a, b):
    """Part-by-part: how a guessed structure b differs from the true one a."""
    ta, tb = [o["table"] for o in a["osc"]], [o["table"] for o in b["osc"]]
    return {"osc_count": f"{len(ta)} vs {len(tb)}", "tables_right": len(set(ta) & set(tb)), "tables_true": ta, "tables_guess": tb,
            "unison": f"{[o['unison'] for o in a['osc']]} vs {[o['unison'] for o in b['osc']]}",
            "warp": f"{[o['warp'] for o in a['osc']]} vs {[o['warp'] for o in b['osc']]}",
            "sub": f"{a['sub']} vs {b['sub']}", "noise": f"{a['noise']} vs {b['noise']}", "filters": f"{a['filters']} vs {b['filters']}",
            "mods_right": sorted(set(a["mods"]) & set(b["mods"])), "mods_missed": len(set(a["mods"]) - set(b["mods"])), "mods_extra": sorted(set(b["mods"]) - set(a["mods"])),
            "fx": f"{[x for r in a['fx'] for x in r]} vs {[x for r in b['fx'] for x in r]}"}


if __name__ == "__main__":
    old = Path(sys.argv[1])
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    finals = json.load(open(old / "finals.json"))
    for job, f in sorted(finals.items(), key=lambda kv: kv[1]["sound"]):
        true = of_tree(s.decode_preset_file(paths[f["sound"]])[1])
        print(f"== {f['sound']}\n true: {json.dumps(true)}")
        for who in ("rules", "designer"):
            print(f" {who}: {json.dumps(diff(true, of_design(f[who]['design'])))}")

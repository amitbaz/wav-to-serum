"""PROTOTYPE, throw away. Key names and value ranges across presets, leaving out all 22 listed presets by hash.

Writes the scratchpad's ranges.json. Keeps one fresh-instance state for a blank base.
"""
import collections, hashlib, json, statistics as st, subprocess, sys
from pathlib import Path

import numpy as np
import serum2_preset_loader as s

SCRATCH = Path(sys.argv[1])
listed = {p["sha256"] for p in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}
paths = [p for p in subprocess.run(["mdfind", 'kMDItemFSName == "*.SerumPreset"'], capture_output=True, text=True).stdout.split("\n") if p]
GROUPS = {"Oscillator0": "osc", "Oscillator1": "osc", "VoiceFilter0": "filter", "Env0": "env", "Env1": "env", "LFO0": "lfo", "Oscillator3": "noise", "Oscillator4": "sub", "Global0": "global"}
vals = collections.defaultdict(lambda: collections.defaultdict(list))
wt_keys, top_wt, tables, fx_seen, slot_ex, routing = collections.Counter(), collections.Counter(), collections.Counter(), {}, [], collections.Counter()
used = 0
for p in paths:
    if hashlib.sha256(Path(p).read_bytes()).hexdigest() in listed:
        continue
    _, t = s.decode_preset_file(p)
    used += 1
    for key, g in GROUPS.items():
        pp = t.get(key, {}).get("plainParams")
        if isinstance(pp, dict):
            for k, v in pp.items():
                vals[g][k].append(v)
    for i in (0, 1):
        o = t.get(f"Oscillator{i}", {})
        wt = o.get(f"WTOsc{i}")
        if isinstance(wt, dict):
            for k, v in wt.items():
                if k != "plainParams":
                    wt_keys[k] += 1
            pp = wt.get("plainParams")
            if isinstance(pp, dict):
                for k, v in pp.items():
                    vals["wt"][k].append(v)
            if len(slot_ex) < 1:
                pass
            for k, v in wt.items():
                if isinstance(v, str) and ("wav" in v.lower() or "wt" in k.lower() or "path" in k.lower()):
                    tables[v] += 1
    for rack in ("FXRack0",):
        for fx in t.get(rack, {}).get("FX", []) or []:
            for k, v in fx.items():
                if k.startswith("FX") and isinstance(v, dict) and fx["type"] not in fx_seen:
                    fx_seen[fx["type"]] = (k, list((v.get("plainParams") or {}).keys())[:14] if isinstance(v.get("plainParams"), dict) else v.get("plainParams"))
    for k, v in t.items():
        if k.startswith("ModSlot") and isinstance(v, dict) and len(slot_ex) < 3 and v.get("source"):
            slot_ex.append(v)
print("presets used", used)
out = {}
for g, d in vals.items():
    print("==", g)
    out[g] = {}
    for k, v in sorted(d.items(), key=lambda kv: -len(kv[1])):
        nums = [x for x in v if isinstance(x, (int, float))]
        if nums:
            q = np.percentile(nums, [0, 10, 50, 90, 100]).round(3).tolist()
            out[g][k] = {"n": len(v), "q": q}
            if len(v) >= 12:
                print(f"  {k} n={len(v)} {q}")
        else:
            c = collections.Counter(map(str, v)).most_common(6)
            out[g][k] = {"n": len(v), "top": c}
            if len(v) >= 12:
                print(f"  {k} n={len(v)} {c}")
print("WT non-plain keys", wt_keys.most_common(12))
print("tables", tables.most_common(5))
print("fx", json.dumps(fx_seen)[:1800])
print("slot", json.dumps(slot_ex, default=str)[:1200])
(SCRATCH / "ranges.json").write_text(json.dumps(out))

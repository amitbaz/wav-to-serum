"""PROTOTYPE, throw away. Show the shape of an init preset. Refuses any of the 22 listed presets."""
import hashlib, json, subprocess, sys
from pathlib import Path

import serum2_preset_loader as s

listed = {p["sha256"] for p in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}
found = subprocess.run(["mdfind", 'kMDItemFSName == "*.SerumPreset"'], capture_output=True, text=True).stdout.split("\n")
init = [p for p in found if p and "init" in Path(p).name.lower()]
print("init-like:", [Path(p).name for p in init][:20])
pkg = Path(s.__file__).parent
print("package presets:", [str(p.relative_to(pkg)) for p in pkg.rglob("*") if p.suffix in {".SerumPreset", ".json", ".cbor", ".bin"}][:20])


def shape(x, d=0, maxd=3):
    if isinstance(x, dict):
        for k, v in list(x.items())[:60]:
            if isinstance(v, (dict, list)) and d < maxd:
                print("  " * d + f"{k}: {type(v).__name__}[{len(v)}]")
                shape(v, d + 1, maxd)
            else:
                print("  " * d + f"{k}: {repr(v)[:70]}")
    elif isinstance(x, list) and x:
        print("  " * d + f"[0] of {len(x)}")
        shape(x[0], d + 1, maxd)


if init:
    p = init[0]
    assert hashlib.sha256(Path(p).read_bytes()).hexdigest() not in listed
    meta, tree = s.decode_preset_file(p)
    print("meta", repr(meta)[:300])
    shape(tree, 0, 2)
print("PARAMS", list(s.PARAMS)[:40] if hasattr(s.PARAMS, "__iter__") else s.PARAMS)

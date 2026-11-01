# /// script
# requires-python = ">=3.12"
# dependencies = ["cbor2", "zstandard", "numpy", "dawdreamer==0.9.0", "serum2-preset-loader==0.5.2"]
# ///
"""Pick the test set and the sealed set, then write testset.json.

Rules come from "What is in the first test set?" (issue 17). Reads every
.SerumPreset on this Mac; a pick stays private apart from its hash. Prints
counts only, and never a preset name or setting, so running this does not
unseal anything. Sealed picks are rendered once, for the silence check, and
only a pass or fail is kept. No audio is written.
"""
import hashlib, json, os, random, re, struct, subprocess, sys, tempfile
from collections import Counter
from pathlib import Path

import cbor2, zstandard

SEED = 28  # set before any pick was seen; never change it to get different picks
FACTORY = "/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Presets/Factory"
TABLES = "/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Tables"
OUT = Path(__file__).with_name("testset.json")
OSC_SUB = {"WT": "WTOsc", "kOsc_Sample": "SampleOsc", "kOsc_MultiSample": "MultiSampleOsc",
           "kOsc_Granular": "GranularOsc", "kOsc_Spectral": "SpectralOsc"}
OWN_PREFIX = {"LD": "lead", "BS": "bass", "BA": "bass", "SY": "synth"}
# (set, kind, level, how many), in picking order: test set first.
PLAN = [("test", k, l, n) for k in ("bass", "lead", "synth") for l, n in (("Easy", 1), ("Medium", 3))]
PLAN += [("sealed", k, l, n) for k in ("bass", "lead") for l, n in (("Easy", 1), ("Medium", 3))]
PLAN += [("sealed", "synth", "Medium", 2)]
HEARD_NOTE = {"bass": 36, "synth": 48, "lead": 60}  # MIDI 48 is C3
SILENT_PEAK = 10 ** (-60 / 20)  # below -60 dBFS on the whole 3 s render
# Near-copy: at least this share of two presets' settings is identical, ignoring
# boilerplate (a setting and value found in at least half of all presets). Set
# from settings alone. Numbered preset families outside the pool score either
# >= 0.60 or <= 0.19, and the pool's own pairs score 0.79, then 0.54 and below.
NEAR_COPY = 0.60


def decode(path):
    """A .SerumPreset is a JSON header, then zstd-compressed CBOR settings."""
    b = open(path, "rb").read()
    assert b[:9] == b"XferJson\0", "magic"
    n = struct.unpack_from("<Q", b, 9)[0]
    size = struct.unpack_from("<I", b, 17 + n)[0]
    raw = zstandard.ZstdDecompressor().decompress(b[25 + n:], max_output_size=max(size, 1 << 20))
    return hashlib.sha256(b).hexdigest(), cbor2.loads(raw)


def plain(module):
    p = module.get("plainParams") if isinstance(module, dict) else None
    return p if isinstance(p, dict) else {}


def analyse(tree):
    """What is heard, moving and working, read from settings. Same rules as the census in issue 15."""
    macro = [plain(tree[f"Macro{i}"]).get("kParamValue", 0) for i in range(8)]
    used = [s for s in (tree[f"ModSlot{i}"] for i in range(64)) if "source" in s and "destModuleTypeString" in s]
    driven = {s["destModuleID"] for s in used if s["destModuleTypeString"] == "Macro"}

    def inert(s):
        p = plain(s)
        if p.get("kParamAmount", 0) == 0 or p.get("kParamBypass"):
            return True
        c, a = s["source"][0], s["source"][1]
        if 25 <= c <= 32 and macro[c - 25] == 0 and (c - 25) not in driven:
            return True
        return 25 <= a <= 32 and macro[a - 25] == 0 and (a - 25) not in driven and not p.get("kParamAuxInverted")

    live = [s for s in used if not inert(s)]
    moving = [s for s in live if 2 <= s["source"][0] <= 15]  # 2-5 envelopes, 6-15 LFOs

    def volume_modulated(i):
        return any(s["destModuleTypeString"] == "Oscillator" and s["destModuleID"] == i
                   and s["destModuleParamName"] == "kParamVolume" for s in live)

    heard = []
    for i in range(3):
        osc, p = tree[f"Oscillator{i}"], plain(tree[f"Oscillator{i}"])
        if p.get("kParamEnable", 1.0 if i == 0 else 0.0) != 1.0:
            continue
        if p.get("kParamVolume", 0.75) == 0 and not volume_modulated(i):
            continue
        ty = p.get("kParamType", "WT")
        heard.append((ty, osc[f"{OSC_SUB[ty]}{i}"]))

    sends = [any(plain(tree[f"RoutingSlot{i}"]).get(k, 0) > 0 for i in range(7))
             for k in ("kParamFXBus1Level", "kParamFXBus2Level")]
    fx = 0
    for rack in range(3):
        for unit in tree[f"FXRack{rack}"]["FX"]:
            name = next((k for k in unit if k.startswith("FX") and isinstance(unit[k], dict)), None)
            p = plain(unit.get(name, {}))
            if p.get("kParamEnable", 1.0) == 0 or (rack and not sends[rack - 1]):
                continue
            if p.get("kParamWet") == 0 and not any(s["destModuleTypeString"] == name and s["destModuleParamName"] == "kParamWet" for s in live):
                continue
            fx += 1
    return heard, len(moving), fx


def level(moving, fx):
    if moving <= 2 and fx <= 2:
        return "Easy"
    return "Medium" if moving <= 5 and fx <= 3 else None


def kind(path):
    if path.startswith(FACTORY):
        return {"Bass": "bass", "Lead": "lead", "Synth": "synth"}.get(path[len(FACTORY) + 1:].split("/")[0])
    m = re.match(r"\s*([A-Za-z]{1,8})\s*[-_ ]", os.path.basename(path))
    return OWN_PREFIX.get(m.group(1).upper()) if m else None


def uses_factory_tables(heard, factory):
    for _, sub in heard:
        if "embeddedWTData" in sub:
            return False
        table = sub.get("relativePathToWT") or sub.get("pathToWT")
        if table and os.path.basename(table.replace("\\", "/")).lower() not in factory:
            return False  # no path at all means the init table
    return True


def settings(node, path=""):
    """Every stored setting as (path, value), so two presets can be compared as sets."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from settings(v, f"{path}/{k}")
    elif isinstance(node, (list, tuple)):
        for i, v in enumerate(node):
            yield from settings(v, f"{path}/{i}")
    elif node is not None:
        yield path, round(node, 3) if isinstance(node, float) else node


def pool():
    """Every eligible preset as {hash: (kind, level, path, settings)}, in hash order."""
    factory = {f.lower() for _, _, fs in os.walk(TABLES, followlinks=True) for f in fs if f.endswith(".wav")}
    assert len(factory) == 288, f"expected the 288 factory tables, found {len(factory)}"
    paths = subprocess.run(["mdfind", 'kMDItemFSName == "*.SerumPreset"'], capture_output=True, text=True).stdout.split("\n")
    found, seen, counts = {}, set(), Counter()
    for path in filter(None, paths):
        digest, tree = decode(path)
        if digest in seen:
            continue
        seen.add(digest)
        stored = set(settings(tree))
        counts.update(stored)
        k = kind(path)
        heard, moving, fx = analyse(tree)
        lv = level(moving, fx)
        if k and lv and 1 <= len(heard) <= 2 and all(ty == "WT" for ty, _ in heard) and uses_factory_tables(heard, factory):
            found[digest] = (k, lv, path, stored)
    boilerplate = {s for s, n in counts.items() if n >= len(seen) / 2}
    print("decoded", len(seen), "eligible", sorted(Counter(v[:2] for v in found.values()).items()))
    return {h: (k, lv, path, stored - boilerplate) for h, (k, lv, path, stored) in sorted(found.items())}


def overlap(a, b):
    return len(a & b) / max(1, len(a | b))


def peak(path, note, velocity):
    """Render one note fresh: 2 s held, 1 s tail. Silence first, as the DAW comparison requires."""
    import dawdreamer, numpy, serum2_preset_loader
    with tempfile.NamedTemporaryFile() as state:
        state.write(serum2_preset_loader.convert_preset_file(path))
        state.flush()
        engine = dawdreamer.RenderEngine(44100, 512)
        synth = engine.make_plugin_processor("s", "/Library/Audio/Plug-Ins/VST3/Serum2.vst3")
        engine.load_graph([(synth, [])])
        synth.load_state(state.name)
    synth.add_midi_note(note, velocity, 1.0, 2.0)
    engine.render(4.0)
    return float(numpy.abs(engine.get_audio()[:, 44100:44100 + 132300]).max())


def silent_renders(path, k):
    n = HEARD_NOTE[k]
    renders = {"heard": (n, 100), "octave down": (n - 12, 100), "octave up": (n + 12, 100), "soft": (n, 40)}
    return [name for name, (note, velocity) in renders.items() if peak(path, note, velocity) < SILENT_PEAK]


def main():
    presets = pool()
    queues = {}
    for h, (k, lv, _, _) in presets.items():
        queues.setdefault((k, lv), []).append(h)
    for stratum, queue in queues.items():
        random.Random(f"{SEED}:{stratum[0]}:{stratum[1]}").shuffle(queue)

    picks, swaps, numbers = [], [], Counter()
    for set_name, k, lv, wanted in PLAN:
        queue, got = queues[(k, lv)], 0
        while got < wanted:
            if not queue:
                sys.exit(f"ran out of {lv} {k} for the {set_name} set, nothing written: a person has to decide")
            h = queue.pop(0)
            path, stored = presets[h][2:]
            twin = max(picks, key=lambda p: overlap(stored, presets[p["sha256"]][3]), default=None)
            score = overlap(stored, presets[twin["sha256"]][3]) if twin else 0
            if score >= NEAR_COPY:
                swaps.append({"dropped": h, "reason": "near-copy", "of": twin["label"], "overlap": round(score, 3)})
                continue
            silent = silent_renders(path, k)
            if silent:
                swaps.append({"dropped": h, "reason": "silent", "on": silent})
                continue
            numbers[k] += 1
            picks.append({"label": f"{k.title()} {numbers[k]}", "set": set_name, "kind": k, "level": lv, "sha256": h})
            got += 1

    OUT.write_text(json.dumps({"seed": SEED, "presets": picks, "swaps": swaps}, indent=2) + "\n")
    print("picked", sorted(Counter((p["set"], p["kind"], p["level"]) for p in picks).items()), "swaps", len(swaps))


if __name__ == "__main__":
    main()

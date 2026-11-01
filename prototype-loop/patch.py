"""PROTOTYPE, throw away. Turn a design plus knob values into a preset tree.

A design holds the choices (tables, modules, routes, FX). Knobs are numbers the tuner sets,
all carried as 0..1 and mapped here to musical ranges. Ranges come from the 718 presets
outside the 22 listed ones (ranges.json).
"""
import copy, math, pickle

ENV2, LFO1 = 3, 6  # modulation source ids, found by experiment in check_writer.py

DIST, CHORUS, DELAY, REVERB = "Distortion", "Chorus", "Delay", "Reverb"
FX_TYPE = {DIST: 0, CHORUS: 3, DELAY: 4, REVERB: 6}


def lin(lo, hi):
    return lambda v: lo + (hi - lo) * v


def log(lo, hi):
    return lambda v: lo * (hi / lo) ** v


def stepped(lo, hi):
    return lambda v: float(round(lo + (hi - lo) * v))


def default_design():
    return {
        "osc": [{"table": "S2 Tables/Default Shapes.wav", "octave": 0, "warp": None, "unison": False}],
        "sub": False,
        "noise": False,
        "filter": None,
        "routes": [],  # any of filter_env, table_env, table_lfo, pitch_lfo, cutoff_lfo
        "fx": [],
    }


def knobs(d):
    """Ordered {name: (mapping, start 0..1)} for this design."""
    k = {
        "master": (log(0.05, 1.0), 0.65),
        "attack": (log(0.0005, 2.0), 0.15),
        "decay": (log(0.01, 8.0), 0.6),
        "sustain": (lin(0.0, 1.0), 0.8),
        "release": (log(0.005, 4.0), 0.4),
    }
    for i, o in enumerate(d["osc"]):
        k[f"osc{i}_vol"] = (lin(0.0, 1.0), 0.75)
        k[f"osc{i}_pos"] = (lin(1.0, 256.0), 0.0)
        k[f"osc{i}_fine"] = (lin(-30.0, 30.0), 0.5)
        if o.get("warp"):
            k[f"osc{i}_warp"] = (lin(0.0, 1.0), 0.2)
        if o.get("unison"):
            k[f"osc{i}_voices"] = (stepped(2, 7), 0.2)
            k[f"osc{i}_detune"] = (log(0.002, 0.5), 0.5)
            k[f"osc{i}_width"] = (lin(0.0, 100.0), 0.7)
    if d["sub"]:
        k["sub_vol"] = (lin(0.0, 1.0), 0.3)
    if d["noise"]:
        k["noise_vol"] = (lin(0.0, 0.6), 0.2)
    if d["filter"]:
        k["cutoff"] = (lin(0.2, 1.0), 0.7)
        k["reso"] = (lin(0.0, 90.0), 0.15)
        k["drive"] = (lin(0.0, 60.0), 0.1)
    r = d["routes"]
    if "filter_env" in r or "table_env" in r:
        k["env2_attack"] = (log(0.0005, 1.0), 0.1)
        k["env2_decay"] = (log(0.01, 6.0), 0.5)
        k["env2_sustain"] = (lin(0.0, 1.0), 0.2)
    if "filter_env" in r:
        k["filter_env_amt"] = (lin(-60.0, 100.0), 0.6)
    if "table_env" in r:
        k["table_env_amt"] = (lin(-100.0, 100.0), 0.7)
    if any(x.endswith("_lfo") for x in r):
        k["lfo_rate"] = (log(0.1, 12.0), 0.6)
    if "table_lfo" in r:
        k["table_lfo_amt"] = (lin(0.0, 100.0), 0.2)
    if "pitch_lfo" in r:
        k["pitch_lfo_amt"] = (lin(0.0, 30.0), 0.1)
    if "cutoff_lfo" in r:
        k["cutoff_lfo_amt"] = (lin(0.0, 60.0), 0.2)
    if DIST in d["fx"]:
        k["dist_drive"] = (lin(0.0, 80.0), 0.2)
        k["dist_wet"] = (lin(0.0, 100.0), 0.5)
    if CHORUS in d["fx"]:
        k["chorus_wet"] = (lin(0.0, 70.0), 0.3)
        k["chorus_rate"] = (log(0.01, 1.4), 0.4)
        k["chorus_depth"] = (lin(0.0, 25.0), 0.3)
    if DELAY in d["fx"]:
        k["delay_wet"] = (lin(0.0, 60.0), 0.2)
        k["delay_fb"] = (lin(0.0, 85.0), 0.3)
        k["delay_time"] = (log(0.01, 0.35), 0.5)
    if REVERB in d["fx"]:
        k["reverb_wet"] = (lin(0.0, 70.0), 0.2)
        k["reverb_size"] = (lin(0.0, 100.0), 0.4)
    return k


def blank():
    def wipe(x):
        if isinstance(x, dict):
            return {k: ("default" if k == "plainParams" else wipe(v)) for k, v in x.items()}
        return [wipe(v) for v in x] if isinstance(x, list) else x

    with open(BASE, "rb") as f:
        t = wipe(pickle.load(f))
    for r in ("FXRack0", "FXRack1", "FXRack2"):
        t[r]["FX"] = []
    w = t["Oscillator0"]["WTOsc0"]
    w["relativePathToWT"] = "S2 Tables/Default Shapes.wav"
    t["presetName"], t["presetAuthor"] = "wav-to-serum prototype", ""
    return t


BASE = None  # set by the caller to the scratchpad's base.pkl


def pp(node):
    if not isinstance(node.get("plainParams"), dict):
        node["plainParams"] = {}
    return node["plainParams"]


def build(d, values, names=None):
    """values: {name: 0..1}, missing names take their start value."""
    spec = knobs(d)
    v = {n: f(values.get(n, s)) for n, (f, s) in spec.items()}
    t = blank()
    pp(t["Global0"])["kParamMasterVolume"] = v["master"]
    e = pp(t["Env0"])
    e["kParamAttack"], e["kParamDecay"], e["kParamSustain"], e["kParamRelease"] = v["attack"], v["decay"], v["sustain"], v["release"]

    for i, o in enumerate(d["osc"]):
        node = t[f"Oscillator{i}"]
        p = pp(node)
        p["kParamEnable"], p["kParamVolume"] = 1.0, v[f"osc{i}_vol"]
        p["kParamOctave"], p["kParamFine"] = float(o.get("octave", 0)), v[f"osc{i}_fine"]
        if o.get("unison"):
            p["kParamUnison"] = v[f"osc{i}_voices"]
            p["kParamDetune"], p["kParamDetuneWid"] = v[f"osc{i}_detune"], v[f"osc{i}_width"]
        wt = node[f"WTOsc{i}"]
        wt["relativePathToWT"] = o["table"]
        wp = pp(wt)
        wp["kParamTablePos"] = v[f"osc{i}_pos"]
        if o.get("warp"):
            wp["kParamWarpMenu"], wp["kParamWarp"] = o["warp"], v[f"osc{i}_warp"]
    if d["sub"]:
        p = pp(t["Oscillator4"])
        p["kParamEnable"], p["kParamVolume"] = 1.0, v["sub_vol"]
    if d["noise"]:
        p = pp(t["Oscillator3"])
        p["kParamEnable"], p["kParamVolume"] = 1.0, v["noise_vol"]
    if d["filter"]:
        p = pp(t["VoiceFilter0"])
        p["kParamEnable"], p["kParamFreq"], p["kParamReso"], p["kParamDrive"] = 1.0, v["cutoff"], v["reso"], v["drive"]
        if d["filter"] != "MgL12":
            p["kParamType"] = d["filter"]

    r, slots = d["routes"], []
    if "filter_env" in r or "table_env" in r:
        e = pp(t["Env1"])
        e["kParamAttack"], e["kParamDecay"], e["kParamSustain"] = v["env2_attack"], v["env2_decay"], v["env2_sustain"]
    if any(x.endswith("_lfo") for x in r):
        p = pp(t["LFO0"])
        p["kParamRate"], p["kParamBeatSync"] = v["lfo_rate"], 0.0
    if "filter_env" in r:
        slots.append((ENV2, "VoiceFilter", 0, "kParamFreq", 3, v["filter_env_amt"]))
    if "cutoff_lfo" in r:
        slots.append((LFO1, "VoiceFilter", 0, "kParamFreq", 3, v["cutoff_lfo_amt"]))
    for i in range(len(d["osc"])):
        if "table_env" in r:
            slots.append((ENV2, "WTOsc", i, "kParamTablePos", 6, v["table_env_amt"]))
        if "table_lfo" in r:
            slots.append((LFO1, "WTOsc", i, "kParamTablePos", 6, v["table_lfo_amt"]))
        if "pitch_lfo" in r:
            slots.append((LFO1, "Oscillator", i, "kParamFine", 5, v["pitch_lfo_amt"]))
    for n, (src, kind, mod, name, pid, amt) in enumerate(slots):
        t[f"ModSlot{n}"] = {
            "destModuleID": mod,
            "destModuleParamID": pid,
            "destModuleParamName": name,
            "destModuleTypeString": kind,
            "plainParams": {"kParamAmount": amt},
            "source": [src, 0],
        }

    def fx(name, **params):
        return {f"FX{name}": {"plainParams": {"kParamEnable": 1.0, **params}}, "kUIParamMixOrGain": 0.0, "type": FX_TYPE[name]}

    rack = []
    for name in d["fx"]:
        if name == DIST:
            rack.append(fx(DIST, kParamDrive=v["dist_drive"], kParamWet=v["dist_wet"]))
        elif name == CHORUS:
            rack.append(fx(CHORUS, kParamWet=v["chorus_wet"], kParamRate=v["chorus_rate"], kParamDepth=v["chorus_depth"]))
        elif name == DELAY:
            rack.append(fx(DELAY, kParamWet=v["delay_wet"], kParamFeedback=v["delay_fb"], kParamTimeL=v["delay_time"], kParamTimeR=v["delay_time"], kParamBeatSync=0.0))
        elif name == REVERB:
            rack.append(fx(REVERB, kParamWet=v["reverb_wet"], kParamSize=v["reverb_size"], kParamType="kHall"))
    t["FXRack0"]["FX"] = rack
    return t

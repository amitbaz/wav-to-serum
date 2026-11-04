"""PROTOTYPE, throw away. "Can per-part pieces pick a structure and a start the tuner can finish from?"

Seven pieces, each reading one part of the sound from the audio alone, with no training data.
  python parts.py lib                  wavetable library from the .wav files (log-magnitude harmonics per frame),
                                       and the filter cutoff knob's map to Hz, from renders of filtered noise
  python parts.py alone [N]            every piece on the 12 test sounds and N bank presets, scored on its own part only
Truth is used only to score.
"""
import csv, json, math, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import stft

import analyse as an

SR = 44100
OFF = 2.0  # the harness holds every note 2 s. The pieces never use it: they find note-off themselves
H = 24  # harmonics compared
LIB = Path("parts")


# ---- 1. Pitch and octave ---------------------------------------------------------------

def pitch(a, note, r):
    """Heard pitch, then the whole-octave shift from the played note. Same as bank.align."""
    k = round((r["midi"] - note) / 12) if r["midi"] else 0
    return {"midi": r["midi"], "note": note, "octave": int(k), "fine_cents": round(100 * (r["midi"] - round(r["midi"])), 1) if r["midi"] else 0.0}


# ---- 2. Wavetable ----------------------------------------------------------------------

def table_frames(path):
    x, _ = sf.read(path, dtype="float32", always_2d=True)
    x = x[:, 0]
    raw = open(path, "rb").read(400)
    i = raw.find(b"<!>")
    size = int(raw[i + 3 : i + 7]) if i >= 0 and raw[i + 3 : i + 7].isdigit() else 2048
    n = len(x) // size
    return x[: n * size].reshape(n, size)


def build_lib(per=32):
    """For every table, up to `per` frames evenly spread: dB of harmonics 1..H, top at 0."""
    rows = []
    for tb in an.table_list():
        fr = table_frames(an.TABLES / tb)
        idx = np.unique(np.linspace(0, len(fr) - 1, min(per, len(fr))).round().astype(int))
        m = np.abs(np.fft.rfft(fr[idx], axis=1))[:, 1 : H + 1]
        db = 20 * np.log10(m + 1e-9)
        db = np.maximum(db - db.max(axis=1, keepdims=True), -90)
        for j, d in zip(idx, db):
            rows.append((tb, float(j / max(len(fr) - 1, 1)), d.astype(np.float32)))
    return rows


def wt_path(name):
    """How a preset names a table: factory ones under S2 Tables/, the rest from the Tables root."""
    return name if name.startswith("S2 Tables/") else "/" + name


def norm(name):
    return (name or "").removeprefix("S2 Tables/").lstrip("/") or "Default Shapes.wav"


def set_table(node, i, name, pos):
    import patch
    w = node[f"WTOsc{i}"]
    w["relativePathToWT"] = wt_path(name)
    patch.pp(w)["kParamTablePos"] = 1 + 255 * pos


def lowpass_shapes():
    """A filter the fit may take off the table: flat to harmonic kc, then `slope` dB per octave."""
    k = np.log2(np.arange(1, H + 1))
    out = [(0.0, 0.0, np.zeros(H))]
    for kc in np.arange(1, H, 0.5):
        for slope in (6, 12, 18, 24, 36):
            out.append((float(kc), float(slope), -slope * np.maximum(k - np.log2(kc), 0)))
    return out


def wavetable(a, note, r, lib, top=5):
    """Match the steady part's harmonics to every frame, after the best low-pass and gain each frame allows.
    The residual says whether one table explains the sound at all."""
    t = np.maximum(np.array(r["harmonics_db"]), -70.0)
    keep = t > -60
    if keep.sum() < 4:
        keep = np.arange(H) < 4
    names, pos, F = lib
    shapes = lowpass_shapes()
    S = np.stack([s for _, _, s in shapes])  # (nshape, H)
    best = np.full(len(F), np.inf); bshape = np.zeros(len(F), int)
    for si in range(len(S)):
        diff = (t - (F + S[si]))[:, keep]  # target minus filtered frame
        diff = diff - diff.mean(axis=1, keepdims=True)  # gain is free
        err = np.sqrt((np.clip(diff, -30, 30) ** 2).mean(axis=1))  # a missing harmonic costs at most 30 dB
        better = err < best
        best[better], bshape[better] = err[better], si
    order, seen, out = np.argsort(best), set(), []
    for i in order:
        if names[i] in seen:
            continue
        seen.add(names[i])
        kc, slope, _ = shapes[bshape[i]]
        out.append({"table": names[i], "pos": round(float(pos[i]), 3), "residual_db": round(float(best[i]), 2), "lp_harmonic": kc, "lp_slope": slope})
        if len(out) == top:
            break
    resid = t - (F[order[0]] + S[bshape[order[0]]])
    resid = resid - resid[keep].mean()
    return {"ranked": out, "h1_under_db": round(float(resid[0]), 1)}


# ---- 3. Voices ------------------------------------------------------------------------

def steady(a, r):
    """Mono slice from 0.3 s after the peak to just before note-off."""
    mono = a.mean(axis=0)
    i0 = int((0.3 + 0.01 * np.argmax(an.rms_db(a))) * SR)
    i1 = max(int((r["note_off_s"] - 0.05) * SR), i0 + SR // 4)
    return mono[i0:i1]


def voices(a, note, r, wt):
    x = steady(a, r)
    f0 = r["f0_hz"] or 1.0
    # unison: how far each harmonic's energy spreads in cents, on harmonics where a bin is a few cents
    n = 8 * len(x)
    s = np.abs(np.fft.rfft(x * np.hanning(len(x)), n)) ** 2
    hz = np.fft.rfftfreq(n, 1 / SR)
    lo, hi = max(200.0, f0), 4000.0
    spreads, weights = [], []
    for k in range(1, 200):
        c = k * f0
        if c < lo:
            continue
        if c > hi:
            break
        m = (hz > c * 2 ** (-40 / 1200)) & (hz < c * 2 ** (40 / 1200))
        p = s[m]
        if p.sum() <= 0:
            continue
        cents = 1200 * np.log2(hz[m] / c)
        mu = (p * cents).sum() / p.sum()
        spreads.append(np.sqrt((p * (cents - mu) ** 2).sum() / p.sum())); weights.append(p.sum())
    spread = float(np.average(spreads, weights=weights)) if spreads else 0.0
    window_cents = 1200 * np.log2(1 + 2 * SR / len(x) / max(lo, 1))  # what one steady voice spreads anyway
    # noise: short frames flicker on noise and stay steady on harmonics, however close they sit
    _, _, z = stft(x, nperseg=1024, noverlap=768, boundary=None, padded=False)
    m = np.abs(z)
    band = (np.fft.rfftfreq(1024, 1 / SR) > 4000) & (np.fft.rfftfreq(1024, 1 / SR) < 12000)
    mb = m[band]
    loud = mb.mean(axis=1) > mb.mean() * 0.05
    # hop to hop change: noise is new every 6 ms, a slow LFO or envelope barely moves in that time
    flicker = float(np.median(np.abs(np.diff(mb[loud], axis=1)).mean(axis=1) / (mb[loud].mean(axis=1) + 1e-12))) if loud.any() else 0.0
    hfe = 10 * np.log10((m[band] ** 2).sum() / ((m ** 2).sum() + 1e-12) + 1e-12)
    h = np.array(r["harmonics_db"])
    odd, even = h[2:12:2].mean(), h[1:12:2].mean()
    out = {"spread_cents": round(spread, 1), "window_cents": round(window_cents, 1), "flicker": round(flicker, 3), "hf_db": round(float(hfe), 1),
           "h1_under_db": wt["h1_under_db"], "odd_minus_even_db": round(float(odd - even), 1)}
    out["unison"] = bool(spread / max(window_cents, 1) > TH["unison"])
    out["detune_cents"] = round(spread, 1)
    out["noise"] = bool(flicker * (hfe > -70) > TH["noise"])
    out["sub"] = bool(max(wt["h1_under_db"], -(odd - even) - 6) > TH["sub"])
    return out


# ---- 4. Amp envelope ------------------------------------------------------------------

def adsr_curve(A, D, S, R, off, n):
    """Serum's amp envelope as measured on a blank preset: straight segments, squared, so sustain S sounds at S squared."""
    t = np.arange(n) * 0.01
    lvl = np.where(t < A, t / max(A, 1e-4), 0.0)
    dec = S**2 + (1 - S**2) * np.clip(1 - (t - A) / D, 0, 1) ** 2
    lvl = np.where(t >= A, dec, lvl)
    at_off = np.interp(off, t, lvl)
    rel = at_off * np.clip(1 - (t - off) / R, 0, 1) ** 2
    return np.where(t >= off, rel, lvl)


def low_level_db(a, f0):
    """Level of the lowest few harmonics only, so a closing filter does not pass for amp decay."""
    mono = a.mean(axis=0)
    n = len(mono) // 441
    z = np.fft.rfft(mono[: n * 441].reshape(n, 441) * np.hanning(441), 4096, axis=1)
    hz = np.fft.rfftfreq(4096, 1 / SR)
    band = hz < max(3.5 * (f0 or 100), 150)
    return 10 * np.log10((np.abs(z[:, band]) ** 2).sum(axis=1) + 1e-12)


def envelope(a, note, r):
    """RMS over 10 ms, fitted to attack, decay, sustain and release in dB. Note-off is found, not told."""
    env = low_level_db(a, r["f0_hz"])
    env = env - env.max()
    n, off = len(env), r["note_off_s"]
    y = np.maximum(env, -60)
    best = (np.inf, None)
    As, Ds, Rs = np.geomspace(5e-4, 2, 18), np.geomspace(0.01, 8, 22), np.geomspace(5e-3, 4, 20)
    Ss = np.linspace(0, 1, 21)
    held = slice(0, int(off * 100))
    for A in As:  # attack, decay and sustain on the held part
        for D in Ds:
            for S in Ss:
                c = 20 * np.log10(adsr_curve(A, D, S, 1.0, 99, n)[held] + 1e-6)
                e = np.abs(np.maximum(c, -60) - y[held]).mean()
                if e < best[0]:
                    best = (e, (A, D, S))
    A, D, S = best[1]
    bestR = (np.inf, 0.1)
    for R in Rs:  # then release on the tail
        c = 20 * np.log10(adsr_curve(A, D, S, R, off, n) + 1e-6)
        e = np.abs(np.maximum(c, -60) - y)[int(off * 100):].mean()
        if e < bestR[0]:
            bestR = (e, R)
    fit = 20 * np.log10(adsr_curve(A, D, S, bestR[1], off, n) + 1e-6)
    return {"attack": float(A), "decay": float(D), "sustain": float(S), "release": float(bestR[1]), "fit_err_db": round(float(best[0]), 2),
            "tail_over_fit_db": round(float((y[-30:] - np.maximum(fit[-30:], -60)).mean()), 1)}


# ---- 5. Movement ----------------------------------------------------------------------

def movement(a, note, r, env):
    """Which measure moves (level, brightness, pitch), how fast and how far: an envelope or an LFO."""
    mono = a.mean(axis=0)
    off = r["note_off_s"]
    rate = SR / 1024
    cent = np.log2(an.centroid_track(mono) + 1)
    i0, i1 = int(0.05 * rate), int((off - 0.05) * rate)
    c = cent[i0:i1]
    out = {}
    # brightness: a one-way move early on is an envelope, a wobble is an LFO
    early = c[: int(0.15 * rate)].mean() - c[int(0.8 * rate) : int(1.6 * rate)].mean() if len(c) > int(1.6 * rate) else 0.0
    out["bright_env_oct"] = round(float(early), 2)
    hz, depth = an.mod_peak(c[int(0.3 * rate):], rate) if len(c) > int(1.0 * rate) else (0.0, 0.0)
    out["bright_lfo"] = {"hz": round(hz, 2), "depth_oct": round(depth, 3)}
    # level: what the amp envelope fit leaves, wobbling
    lv = low_level_db(a, r["f0_hz"])
    lv = lv - lv.max()
    fit = 20 * np.log10(adsr_curve(env["attack"], env["decay"], env["sustain"], env["release"], off, len(lv)) + 1e-6)
    res = (lv - fit)[30 : int(off * 100) - 5]
    hz2, d2 = an.mod_peak(res, 100) if len(res) > 90 else (0.0, 0.0)
    out["level_lfo"] = {"hz": round(hz2, 2), "depth_db": round(d2, 2)}
    # pitch: early drop is an envelope, spread on the held part an LFO
    f0 = r["f0_hz"]
    first = an.f0_of(mono[: max(int(0.08 * SR), int(3.2 * SR / f0))], f0) if f0 else 0.0
    out["pitch_env_cents"] = round(1200 * math.log2(first / f0), 1) if first and f0 else 0.0
    out["pitch_spread_cents"] = r["pitch_spread_cents"]
    routes = []
    if abs(early) > TH["bright_env"]:
        routes.append("Env>VoiceFilter.Freq")
    if depth > TH["bright_lfo"]:
        routes.append("LFO>VoiceFilter.Freq")
    if d2 > TH["level_lfo"]:
        routes.append("LFO>Oscillator.Volume")
    if r["pitch_spread_cents"] > TH["pitch_lfo"]:
        routes.append("LFO>Oscillator.Fine")
    if abs(out["pitch_env_cents"]) > TH["pitch_env"]:
        routes.append("Env>Oscillator.CoarsePit")
    out["routes"] = routes
    # ambiguous pair: a brightness move may be the filter or the table position. Both are offered.
    out["alternatives"] = [x.replace("VoiceFilter.Freq", "WTOsc.TablePos") for x in routes if "VoiceFilter.Freq" in x]
    return out


# ---- 6. Filter ------------------------------------------------------------------------

def filt(a, note, r, wt, cutoff_map):
    """Type and cutoff from the low-pass the wavetable fit had to take off; brightness over time is movement's."""
    b = wt["ranked"][0]
    kc, slope = b["lp_harmonic"], b["lp_slope"]
    if not slope:
        return {"type": None, "cutoff_hz": None}
    hz = kc * (r["f0_hz"] or 100.0)
    return {"type": "MgL12" if slope <= 15 else "MgL24", "cutoff_hz": round(float(hz)), "knob": hz_to_knob(hz, cutoff_map)}


def hz_to_knob(hz, cutoff_map):
    """Log-linear through the measured points that sit inside the 24 harmonics the calibration can see."""
    k, h = np.array(cutoff_map["knob"]), np.array(cutoff_map["hz"])
    ok = (h > h.min()) & (h < 20000)
    slope, icept = np.polyfit(k[ok], np.log2(h[ok]), 1)
    return float(np.clip((math.log2(hz) - icept) / slope, 0, 1))


# ---- 7. Width and effects -------------------------------------------------------------

def width_fx(a, note, r, env):
    """Stereo width from mid and side. Reverb or delay only where the tail outlasts the release fit."""
    mono = a.mean(axis=0)
    off = int(r["note_off_s"] * SR)
    tail = an.rms_db(a)[int(r["note_off_s"] * 100):]
    out = {"side_db": r["stereo_side_db"], "tail_over_fit_db": env["tail_over_fit_db"]}
    # echoes: the tail's level envelope repeats at the delay time
    t = tail - np.convolve(tail, np.ones(25) / 25, "same") if len(tail) > 40 else np.zeros(80)
    t = t[5:-5] if len(t) > 40 else np.zeros(80)
    ac = np.correlate(t, t, "full")[len(t) - 1 :]
    ac = ac / (ac[0] + 1e-12)
    lag = int(np.argmax(ac[5:70])) + 5 if len(ac) > 70 else 0
    out["echo"] = {"lag_s": round(lag * 0.01, 2), "corr": round(float(ac[lag]) if lag else 0.0, 2)}
    out["delay"] = bool(out["echo"]["corr"] > TH["delay"])
    out["reverb"] = bool(env["tail_over_fit_db"] > TH["reverb"])
    return out


# ---- all pieces ---------------------------------------------------------------------

# One threshold per yes/no answer. Physical guesses until `alone` sets them on bank presets (never the test sounds).
TH = {"unison": 1.5, "noise": 0.3, "sub": 6.0, "bright_env": 0.35, "bright_lfo": 0.08, "level_lfo": 1.5, "pitch_lfo": 15.0, "pitch_env": 60.0,
      "delay": 0.3, "reverb": 12.0}
if (LIB / "thresholds.json").exists():
    TH.update(json.load(open(LIB / "thresholds.json")))

MEASURE = {  # the number each threshold cuts, from a read
    "unison": lambda p: p["voices"]["spread_cents"] / max(p["voices"]["window_cents"], 1),
    "noise": lambda p: p["voices"]["flicker"] * (p["voices"]["hf_db"] > -70),
    "sub": lambda p: max(p["voices"]["h1_under_db"], -p["voices"]["odd_minus_even_db"] - 6),
    "bright_env": lambda p: abs(p["movement"]["bright_env_oct"]), "bright_lfo": lambda p: p["movement"]["bright_lfo"]["depth_oct"],
    "level_lfo": lambda p: p["movement"]["level_lfo"]["depth_db"], "pitch_lfo": lambda p: p["movement"]["pitch_spread_cents"],
    "pitch_env": lambda p: abs(p["movement"]["pitch_env_cents"]), "delay": lambda p: p["width_fx"]["echo"]["corr"], "reverb": lambda p: p["width_fx"]["tail_over_fit_db"]}


def calibrate(rows):
    """Per answer, the cut that does best on these rows. Bigger always means yes."""
    out = {}
    for q, f in MEASURE.items():
        v = np.array([f(p) for _, p, _ in rows], float); tv = [t[q] for _, _, t in rows]
        cuts = np.unique(np.quantile(v, np.linspace(0.02, 0.98, 49)))
        accs = [bal(v > c, tv) or 0 for c in cuts]
        out[q] = float(cuts[int(np.argmax(accs))])
    return out


def decide(p):
    """Re-take every yes/no answer from its measure at the current thresholds."""
    v = p["voices"]
    for q in ("unison", "noise", "sub"):
        v[q] = bool(MEASURE[q](p) > TH[q])
    m = p["movement"]
    m["routes"] = [r for q, r in (("bright_env", "Env>VoiceFilter.Freq"), ("bright_lfo", "LFO>VoiceFilter.Freq"), ("level_lfo", "LFO>Oscillator.Volume"),
                                  ("pitch_lfo", "LFO>Oscillator.Fine"), ("pitch_env", "Env>Oscillator.CoarsePit")) if MEASURE[q](p) > TH[q]]
    m["alternatives"] = [x.replace("VoiceFilter.Freq", "WTOsc.TablePos") for x in m["routes"] if "VoiceFilter.Freq" in x]
    for q in ("delay", "reverb"):
        p["width_fx"][q] = bool(MEASURE[q](p) > TH[q])
    return p

def read(a, note, lib, cutoff_map):
    r = an.analyse(a)
    wt = wavetable(a, note, r, lib)
    env = envelope(a, note, r)
    return {"pitch": pitch(a, note, r), "wavetable": wt, "voices": voices(a, note, r, wt), "envelope": env,
            "movement": movement(a, note, r, env), "filter": filt(a, note, r, wt, cutoff_map), "width_fx": width_fx(a, note, r, env)}


def load_lib():
    rows = pickle.load(open(LIB / "lib.pkl", "rb"))
    return [x[0] for x in rows], np.array([x[1] for x in rows]), np.stack([x[2] for x in rows]), json.load(open(LIB / "cutoff.json"))


# ---- truth, only to score -----------------------------------------------------------

import guess as g  # noqa: E402  (after the pieces, so they never touch it)
import structure as st  # noqa: E402


def truth(tree):
    x = st.of_tree(tree)
    P = lambda n: tree.get(n, {}).get("plainParams") if isinstance(tree.get(n, {}).get("plainParams"), dict) else {}
    e = P("Env0")
    slots = [v for k, v in tree.items() if k.startswith("ModSlot") and isinstance(v, dict) and v.get("source") and v.get("destModuleTypeString")]
    moving = lambda kinds, dests: any(g.SRC_KIND.get(v["source"][0], "").rstrip("1") in kinds and f"{v['destModuleTypeString']}.{v['destModuleParamName'].removeprefix('kParam')}" in dests
                                     and abs((v.get("plainParams") or {}).get("kParamAmount", 0) if isinstance(v.get("plainParams"), dict) else 0) > 1 for v in slots)
    wet_moved = {v["destModuleTypeString"] for v in slots if v["destModuleParamName"] == "kParamWet"}
    def fx_on(name):
        for rk in ("FXRack0", "FXRack1", "FXRack2"):
            for f in tree.get(rk, {}).get("FX", []) or []:
                if st.FX.get(f["type"]) == name:
                    p = f.get(f"FX{name}", {}).get("plainParams")
                    p = p if isinstance(p, dict) else {}
                    if p.get("kParamWet", 50) > 0 or f"FX{name}" in wet_moved:
                        return True
        return False
    f0 = P("VoiceFilter0")
    oct_ = min([o["octave"] for o in x["osc"]] or [0])
    return {"octave": oct_, "tables": [g.norm_table(o["table"]) for o in x["osc"]],
            "unison": max([o["unison"] for o in x["osc"]] or [1]) > 1, "sub": x["sub"], "noise": x["noise"],
            "attack": e.get("kParamAttack", 0.0005), "decay": e.get("kParamDecay", 1.0), "sustain": e.get("kParamSustain", 1.0), "release": e.get("kParamRelease", 0.005),
            "bright_env": moving({"Env"}, {"VoiceFilter.Freq", "WTOsc.TablePos"}), "bright_lfo": moving({"LFO"}, {"VoiceFilter.Freq", "WTOsc.TablePos"}),
            "level_lfo": moving({"LFO"}, {"Oscillator.Volume"}), "pitch_lfo": moving({"LFO"}, {"Oscillator.Fine", "Global.MasterTuning"}),
            "pitch_env": moving({"Env"}, {"Oscillator.CoarsePit"}),
            "filter": g.filt(f0.get("kParamType", "MgL12")) if f0.get("kParamEnable") else "none", "cutoff": f0.get("kParamFreq") if f0.get("kParamEnable") else None,
            "reverb": fx_on("Reverb"), "delay": fx_on("Delay")}


def lib_cmd():
    import patch, render as rd
    LIB.mkdir(exist_ok=True)
    t0 = time.time()
    pickle.dump(build_lib(), open(LIB / "lib.pkl", "wb"))
    patch.BASE = "base.pkl"
    names, pos, F, _ = (*load_lib()[:3], None)
    saw = -20 * np.log10(np.arange(1, H + 1))
    i = int(np.argmin(np.abs(F[[norm(n) == "Default Shapes.wav" and n.startswith("S2") for n in names]] - saw).mean(axis=1)))
    tpos = pos[[norm(n) == "Default Shapes.wav" and n.startswith("S2") for n in names]][i]
    d = patch.default_design()
    v0 = {"osc0_pos": tpos, "sustain": 1.0, "reso": 0.0, "drive": 0.0}
    f0 = 440 * 2 ** ((36 - 69) / 12)
    harm = lambda a: an.harmonics(a.mean(axis=0)[4410 : 4410 + 32768], f0)[0]
    flat = harm(rd.render_tree(patch.build(d, v0), 36))
    d["filter"] = "MgL12"
    knobs, hzs = [], []
    for u in np.linspace(0, 1, 11):
        rel = harm(rd.render_tree(patch.build(d, {**v0, "cutoff": u}), 36)) - flat
        rel = rel - rel[0]
        k = np.flatnonzero(rel < -3)
        knobs.append(0.2 + 0.8 * u); hzs.append(float((k[0] + 1) * f0) if len(k) else 20000.0)
    json.dump({"knob": knobs, "hz": hzs}, open(LIB / "cutoff.json", "w"))
    print(json.dumps({"tables": len(an.table_list()), "frames": len(pickle.load(open(LIB / "lib.pkl", "rb"))), "cutoff_map": [(round(k, 2), round(h)) for k, h in zip(knobs, hzs)], "secs": round(time.time() - t0)}), flush=True)


# ---- each piece alone ---------------------------------------------------------------

_w = {}


def _init():
    _w["lib"] = load_lib()


def _one(job):
    import render as rd, serum2_preset_loader as s
    label, path, note = job
    tree = s.decode_preset_file(path)[1]
    a = rd.render_tree(tree, note)
    if not np.isfinite(a).all() or abs(a).max() < 1e-3:
        return None
    lib = _w["lib"]
    return label, read(a, note, lib[:3], lib[3]), truth(tree)


def bank_jobs(n, seed=37):
    bank = pickle.load(open("bank.pkl", "rb"))
    crash = set(json.loads(Path("guess/crashers.json").read_text()))
    rng = np.random.default_rng(seed)
    out = []
    for i in rng.permutation(len(bank)):
        if int(i) in crash:
            continue
        p = Path(bank[i][0])
        note = 36 if p.stem.startswith("BA") else 60 if p.stem.startswith("LD") else 48
        out.append((p.stem, str(p), note))
        if len(out) == n:
            break
    return out


def bal(pred, true):
    """Balanced accuracy over yes/no answers; None when one class is missing."""
    pred, true = np.array(pred, bool), np.array(true, bool)
    if true.all() or not true.any():
        return None
    return round(float(((pred & true).sum() / true.sum() + (~pred & ~true).sum() / (~true).sum()) / 2), 2)


def score(rows):
    P, T = [x[1] for x in rows], [x[2] for x in rows]
    out = {"n": len(rows)}
    out["octave_right"] = round(float(np.mean([p["pitch"]["octave"] == t["octave"] for p, t in zip(P, T)])), 2)
    out["pitch_class_right"] = round(float(np.mean([abs((p["pitch"]["midi"] - p["pitch"]["note"] + 6) % 12 - 6) < 0.5 for p in P])), 2)
    for k in (1, 5, 20):
        out[f"table_top{k}"] = round(float(np.mean([bool(set(t["tables"]) & {norm(x["table"]) for x in p["wavetable"]["ranked"][:k]}) for p, t in zip(P, T)])), 2) if k <= 5 else None
    out["table_chance_top5"] = round(5 / 288, 3)
    out["table_family_right"] = round(float(np.mean([g.fam(norm(p["wavetable"]["ranked"][0]["table"])) in {g.fam(x) for x in t["tables"]} for p, t in zip(P, T)])), 2)
    fams = [g.fam(x) for t in T for x in t["tables"]]
    out["table_family_chance"] = round(max(fams.count(f) for f in set(fams)) / len(fams), 2)  # always guessing the commonest
    for q, f in (("unison", lambda p: p["voices"]["unison"]), ("sub", lambda p: p["voices"]["sub"]), ("noise", lambda p: p["voices"]["noise"]),
                 ("bright_env", lambda p: any(r.startswith("Env>VoiceFilter") for r in p["movement"]["routes"])),
                 ("bright_lfo", lambda p: any(r.startswith("LFO>VoiceFilter") for r in p["movement"]["routes"])),
                 ("level_lfo", lambda p: "LFO>Oscillator.Volume" in p["movement"]["routes"]), ("pitch_lfo", lambda p: "LFO>Oscillator.Fine" in p["movement"]["routes"]),
                 ("pitch_env", lambda p: "Env>Oscillator.CoarsePit" in p["movement"]["routes"]),
                 ("filter_on", lambda p: p["filter"]["type"] is not None), ("reverb", lambda p: p["width_fx"]["reverb"]), ("delay", lambda p: p["width_fx"]["delay"])):
        tv = [t["filter"] != "none" if q == "filter_on" else t[q] for t in T]
        out[q] = {"bal_acc": bal([f(p) for p in P], tv), "true_share": round(float(np.mean(tv)), 2)}
    # envelope: error in octaves of time (sustain in dB), against always guessing the bank's median
    for k in ("attack", "decay", "release", "sustain"):
        tv = np.array([t[k] for t in T], float); pv = np.array([p["envelope"][k] for p in P], float)
        if k == "sustain":
            dbv = lambda v: 20 * np.log10(np.maximum(v, 1e-3))
            e, base = np.abs(dbv(pv) - dbv(tv)), np.abs(dbv(np.median(tv)) - dbv(tv))
        else:
            e, base = np.abs(np.log2(np.maximum(pv, 1e-4) / np.maximum(tv, 1e-4))), np.abs(np.log2(np.median(tv) / np.maximum(tv, 1e-4)))
        out[f"env_{k}"] = {"median_err": round(float(np.median(e)), 2), "median_err_constant_guess": round(float(np.median(base)), 2), "unit": "dB" if k == "sustain" else "octaves"}
    pairs = [(p["filter"]["knob"], t["cutoff"]) for p, t in zip(P, T) if p["filter"]["type"] and t["cutoff"] is not None]
    if len(pairs) > 4:
        from scipy.stats import spearmanr
        out["cutoff_rank_corr"] = {"rho": round(float(spearmanr(*zip(*pairs))[0]), 2), "n": len(pairs), "median_knob_err": round(float(np.median([abs(a - b) for a, b in pairs])), 3)}
    return out


def side(label, p, t):
    """One sound: each piece's answer next to the truth."""
    return {"sound": label, "octave": [p["pitch"]["octave"], t["octave"]], "tables": [[norm(x["table"]) for x in p["wavetable"]["ranked"][:3]], t["tables"]],
            "resid": p["wavetable"]["ranked"][0]["residual_db"], "uni": [p["voices"]["unison"], t["unison"], p["voices"]["spread_cents"], p["voices"]["window_cents"]],
            "sub": [p["voices"]["sub"], t["sub"]], "noise": [p["voices"]["noise"], t["noise"], p["voices"]["flicker"], p["voices"]["hf_db"]], "routes": p["movement"]["routes"],
            "true_moves": [k for k in ("bright_env", "bright_lfo", "level_lfo", "pitch_lfo", "pitch_env") if t[k]],
            "env": [round(p["envelope"][k], 3) for k in ("attack", "decay", "sustain", "release")], "true_env": [round(t[k], 3) for k in ("attack", "decay", "sustain", "release")],
            "filter": [p["filter"].get("type"), p["filter"].get("knob") and round(p["filter"]["knob"], 2), t["filter"], t["cutoff"] and round(t["cutoff"], 2)],
            "fx": [p["width_fx"]["reverb"], p["width_fx"]["delay"], t["reverb"], t["delay"], p["width_fx"]["tail_over_fit_db"], p["width_fx"]["echo"]["corr"]]}


def alone(n):
    import csv
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    test = [(x, paths[x], {"Bass": 36, "Lead": 60, "Synth": 48}[x.split()[0]]) for x in [f"{k} {i}" for k in ("Bass", "Lead", "Synth") for i in range(1, 5)]]
    t0, res = time.time(), {}
    with get_context("spawn").Pool(8, _init) as pool:
        for name, jobs in (("bank", bank_jobs(n)), ("test", test)):
            rows, lost = [], 0
            for j, h in [(j, pool.apply_async(_one, (j,))) for j in jobs]:
                try:
                    x = h.get(timeout=120)
                    if x:
                        rows.append(x)
                except Exception:
                    lost += 1
            res[name] = rows
            if name == "bank":
                TH.update(calibrate(rows))
                json.dump(TH, open(LIB / "thresholds.json", "w"))
                print(json.dumps({"thresholds": {k: round(v, 3) for k, v in TH.items()}}), flush=True)
            rows[:] = [(l, decide(p), t) for l, p, t in rows]
            print(json.dumps({"set": name, "lost": lost, "note": "thresholds set on this set" if name == "bank" else "held out", **score(rows)}), flush=True)
    pickle.dump(res, open(LIB / "alone.pkl", "wb"))
    for label, p, t in res["test"]:
        print(json.dumps(side(label, p, t)), flush=True)
    print("secs", round(time.time() - t0))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "lib":
        lib_cmd()
    elif cmd == "alone":
        alone(int(sys.argv[2]) if len(sys.argv) > 2 else 120)


# ---- tuning: each piece's worth, and all pieces together --------------------------------

def target_of(label):
    import csv, render as rd, serum2_preset_loader as s
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    note = {"Bass": 36, "Lead": 60, "Synth": 48}[label.split()[0]]
    true = s.decode_preset_file(paths[label])[1]
    return note, true, rd.render_tree(true, note)


def set_env(tree, e):
    import patch
    p = patch.pp(tree["Env0"])
    p.update(kParamAttack=e["attack"], kParamDecay=e["decay"], kParamSustain=e["sustain"], kParamRelease=e["release"])
    return {("Env0",) + (k,) for k in ("kParamAttack", "kParamDecay", "kParamSustain", "kParamRelease")}


def moving_slot(v):
    return isinstance(v, dict) and g.SRC_KIND.get((v.get("source") or [None])[0]) is not None


def add_routes(tree, routes, D, n_osc):
    """Routes from the movement piece, each slot copied from a bank preset that has it (so its ids are real)."""
    import copy
    slot = 0
    while f"ModSlot{slot}" in tree and isinstance(tree[f"ModSlot{slot}"].get("plainParams"), dict) and tree[f"ModSlot{slot}"].get("source"):
        slot += 1
    for rt in routes:
        if rt not in D["slot"]:
            continue
        v = D["slot"][rt]
        src = {"Env": 3, "LFO": 6}[rt.split(">")[0]]
        for m in (range(n_osc) if v["destModuleTypeString"] in ("Oscillator", "WTOsc") else [0]):
            tree[f"ModSlot{slot}"] = {**copy.deepcopy(v), "destModuleID": m, "source": [src, 0]}
            slot += 1


def set_lfo(tree, mv):
    import patch
    hz = max(mv["bright_lfo"]["hz"], mv["level_lfo"]["hz"]) or 2.0
    if isinstance(tree.get("LFO0"), dict):
        p = patch.pp(tree["LFO0"])
        p.update(kParamRate=float(hz), kParamBeatSync=0.0)
        return {("LFO0", "kParamRate")}
    return set()


def worth_tree(true, piece, P, D):
    """The true structure with one part taken from its piece. Returns the tree and the knobs the piece set."""
    import copy, patch
    import pick
    t, fixed = copy.deepcopy(true), set()
    on = [i for i in range(3) if i == 0 or __import__("oracle").is_on(t, f"Oscillator{i}", t[f"Oscillator{i}"])]
    if piece == "tables":
        b = P["wavetable"]["ranked"][0]
        for i in on:
            set_table(t[f"Oscillator{i}"], i, b["table"], b["pos"]); fixed.add((f"Oscillator{i}", f"WTOsc{i}", "kParamTablePos"))
    elif piece == "voices":
        v = P["voices"]
        t = pick.swap(t, "voices", {"osc": [{"unison": v["unison"]}], "sub": v["sub"], "noise": v["noise"]})
    elif piece == "filter":
        f = P["filter"]
        t = pick.swap(t, "filter", {"filter": f["type"]})
        if f["type"]:
            patch.pp(t["VoiceFilter0"])["kParamFreq"] = f["knob"]; fixed.add(("VoiceFilter0", "kParamFreq"))
    elif piece == "fx":
        w = P["width_fx"]
        t = pick.swap(t, "fx", {"fx": [x for x, on_ in (("Delay", w["delay"]), ("Reverb", w["reverb"])) if on_]})
    elif piece == "movement":
        for k in [k for k in t if k.startswith("ModSlot") and moving_slot(t[k])]:  # static routes (macros, velocity) stay
            t[k] = {"plainParams": "default"}
        add_routes(t, P["movement"]["routes"], D, len(on))
        fixed |= set_lfo(t, P["movement"])
    elif piece == "envelope":
        fixed |= set_env(t, P["envelope"])
    else:
        raise SystemExit(f"unknown piece {piece}")
    return t, fixed


def starts(fixed, rng):
    """First start: the piece's own knobs where it set them, random elsewhere. Then random restarts."""
    import oracle as o
    def f(kn):
        x = rng.uniform(0.15, 0.85, len(kn))
        for j, (path, k, v, lo, hi, lg) in enumerate(kn):
            if path + (k,) in fixed:
                x[j] = o.to_unit(v, lo, hi, lg)
        return [x]
    return f


def build_whole(P, D, table, alt=False):
    """All pieces in one preset: a blank one, modules copied from bank presets that have them, then the pieces' knob values."""
    import choose as ch, patch
    mv = P["movement"]
    routes = [r for r in mv["routes"] if "VoiceFilter.Freq" not in r] + (mv["alternatives"] if alt else [r for r in mv["routes"] if "VoiceFilter.Freq" in r])
    f = P["filter"]["type"]
    d = {"osc": [table["table"]], "unison": int(P["voices"]["unison"]), "sub": P["voices"]["sub"], "noise": P["voices"]["noise"],
         "filter": f or "none", "fx": [x for x, on_ in (("Delay", P["width_fx"]["delay"]), ("Reverb", P["width_fx"]["reverb"])) if on_], "routes": []}
    tree = ch.build(d, D)
    add_routes(tree, routes, D, 1)
    set_table(tree["Oscillator0"], 0, table["table"], table["pos"])
    set_env(tree, P["envelope"])
    if f:
        patch.pp(tree["VoiceFilter0"]).update(kParamEnable=1.0, kParamFreq=P["filter"]["knob"])
    if any(r.startswith("LFO") for r in routes):
        set_lfo(tree, mv)
    return tree, d, routes


def tune_cmd(mode, piece, budget, sounds):
    import pick, choose as ch, bank as bk, retrieve as rv, render as rd, serum2_preset_loader as s
    import patch
    patch.BASE = "base.pkl"
    pick.OUT = LIB
    lib = load_lib()
    D = ch.donors()
    for label in sounds:
        tag = f"{label.replace(' ', '')}_{mode}" + (f"-{piece}" if piece else "")
        if (LIB / f"{tag}.json").exists():  # done before a pause: keep it
            continue
        note, true, target = target_of(label)
        feats = __import__("tune").features(target)
        sf.write(LIB / f"{label.replace(' ', '')}_target.wav", target.T, SR, subtype="FLOAT")
        P = decide(read(target, note, lib[:3], lib[3]))
        rng, t0 = np.random.default_rng(1), time.time()
        if mode == "worth":
            tree, fixed = worth_tree(true, piece, P, D)
            S, knobs = pick.run(tree, note, feats, starts(fixed, rng), budget, rng)
            pick.save(tag, {"sound": label, "arm": f"worth:{piece}", "knobs": len(knobs), "secs": round(time.time() - t0)}, tree, knobs, S, note, target, feats)
            continue
        # whole: the top tables and, where brightness moves, filter or table position, are candidates. A short
        # screen of each picks one, which then gets the rest of the budget.
        cands = []
        for tb in P["wavetable"]["ranked"][:3]:
            for alt in ([False, True] if P["movement"]["alternatives"] else [False]):
                tree, d, routes = build_whole(P, D, tb, alt)
                tree = bk.align(tree, note, target)
                tree = rv.level_up(tree, rd.render_tree(tree, note), target)
                cands.append((tb["table"], routes, tree))
        screen = int(__import__("os").environ.get("SCREEN", 800))
        tried, best = [], None
        for name, routes, tree in cands:
            S, knobs = pick.run(tree, note, feats, lambda kn: [[__import__("oracle").to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in kn]], screen, rng)
            tried.append({"table": name, "routes": routes, "score": round(S.best, 3)})
            print(json.dumps({"sound": label, "screen": tried[-1]}), flush=True)
            if best is None or S.best < best[0].best:
                best = (S, knobs, tree, name, routes)
        S0, knobs, tree, name, routes = best
        left = budget - screen * len(cands)
        x_best = S0.bx.copy()
        S, knobs = pick.run(tree, note, feats, lambda kn: [x_best], left, rng)
        if S0.best < S.best:
            S = S0
        S.used = budget
        true_x = st.of_tree(true)
        res = {"sound": label, "arm": "whole", "picked": name, "routes": routes, "tried": tried, "knobs": len(knobs), "secs": round(time.time() - t0),
               "vs_truth": st.diff(true_x, st.of_tree(tree))}
        pick.save(tag, res, tree, knobs, S, note, target, feats)


if __name__ == "__main__" and sys.argv[1] in ("worth", "whole"):
    if sys.argv[1] == "worth":
        tune_cmd("worth", sys.argv[2], int(sys.argv[3]), sys.argv[4:])
    else:
        tune_cmd("whole", None, int(sys.argv[2]), sys.argv[3:])

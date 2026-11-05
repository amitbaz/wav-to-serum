"""PROTOTYPE, throw away. Cutoff knob -> Hz, per filter type: a saw at C0 (harmonics every 16 Hz) through the voice filter, -3 dB point."""
import json, numpy as np, patch, render as rd
patch.BASE = "base.pkl"
def tree(typ, u, reso=0.0):
    t = patch.blank()
    if typ:
        f = patch.pp(t["VoiceFilter0"]); f["kParamEnable"], f["kParamFreq"], f["kParamReso"] = 1.0, u, reso
        if typ != "MgL12": f["kParamType"] = typ
    patch.pp(t["Env0"])["kParamSustain"] = 1.0
    return t
N, f0 = 65536, 440 * 2 ** ((12 - 69) / 12)
fr = f0 * np.arange(1, int(20000 / f0))
def spec(a):  # power at each harmonic
    X = np.abs(np.fft.rfft(a.mean(axis=0)[22050:22050 + N] * np.hanning(N))) ** 2
    b = np.round(fr * N / 44100).astype(int)
    return np.array([X[i - 2:i + 3].max() for i in b])
flat = spec(rd.render_tree(tree(None, 0), 12))
out = {}
for typ in ["MgL6", "MgL12", "MgL18", "MgL24", "LadderMg"]:
    rows = []
    for u in np.linspace(0, 1, 21):
        r = 10 * np.log10(spec(rd.render_tree(tree(typ, u), 12)) / flat + 1e-12)
        sm = np.convolve(r, np.ones(3) / 3, "same"); ref = np.median(sm[fr < 50])
        k = np.flatnonzero((sm < ref - 3) & (fr > 40))
        rows.append((round(float(u), 2), round(float(fr[k[0]])) if len(k) else 22050, round(float(ref), 1)))
    out[typ] = rows; print(typ, rows, flush=True)
json.dump(out, open("step2_cutoff.json", "w"))

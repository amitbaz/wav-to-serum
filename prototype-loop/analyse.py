"""PROTOTYPE, throw away. Measure a target WAV, and rank factory wavetables against it.

Only ever sees audio. Plain numpy and scipy.
"""
import json, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from scipy.signal import stft

SR = 44100
TABLES = Path("/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Tables")
POSITIONS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]  # knob values for osc_pos
N_HARM = 24


def rms_db(a, win=441):
    m = (a**2).mean(axis=0)
    n = len(m) // win
    e = m[: n * win].reshape(n, win).mean(axis=1)
    return 10 * np.log10(e + 1e-12)


def f0_of(x, near=None):
    """Autocorrelation on a windowed slice; x is mono. Returns Hz. near limits it to a semitone of that Hz."""
    x = x[: 16384] - x[: 16384].mean()  # a bass can carry enough DC to hide every peak
    x = x * np.hanning(len(x))
    spec = np.fft.rfft(x, 2 * len(x))
    ac = np.fft.irfft(np.abs(spec) ** 2)[: len(x)]
    lo, hi = int(SR / 2000), int(SR / 12)  # basses here sit at 16 Hz, two octaves under the key
    if near:
        lo, hi = int(SR / (near * 1.06)) - 1, int(SR / (near / 1.06)) + 2
    # only true local peaks count: a smooth bass stays high at short lags without being periodic there
    peaks = [i for i in range(lo + 1, hi - 1) if ac[i] >= ac[i - 1] and ac[i] >= ac[i + 1]]
    if not peaks:
        return 0.0
    top = max(ac[i] for i in peaks)
    # the first peak nearly as strong as the best: 0.97 so an octave partial cannot pass for the note
    for i in peaks:
        if ac[i] > 0.97 * top:
            a, b, c = ac[i - 1], ac[i], ac[i + 1]
            return SR / (i + 0.5 * (a - c) / (a - 2 * b + c))
    return 0.0


def harmonics(x, f0):
    """Amplitude in dB of harmonics 1..N_HARM, and the share of energy between harmonics."""
    x = x[: 32768]
    w = np.hanning(len(x))
    s = np.abs(np.fft.rfft(x * w)) ** 2
    hz = np.fft.rfftfreq(len(x), 1 / SR)
    bin_hz = hz[1]
    out, mask = [], np.zeros(len(s), bool)
    width = max(2, int(0.06 * f0 / bin_hz))
    for k in range(1, N_HARM + 1):
        c = int(round(k * f0 / bin_hz))
        if c + width >= len(s):
            out.append(-120.0)
            continue
        out.append(10 * np.log10(s[c - width : c + width + 1].sum() + 1e-14))
        mask[c - width : c + width + 1] = True
    top = int(min(len(s) - 1, (N_HARM + 0.5) * f0 / bin_hz))
    noise = s[1:top][~mask[1:top]].sum() / (s[1:top].sum() + 1e-14)
    return np.array(out), float(noise)


def centroid_track(mono, n_fft=2048, hop=1024):
    _, _, z = stft(mono, nperseg=n_fft, noverlap=n_fft - hop, boundary=None, padded=False)
    m = np.abs(z) ** 2
    f = np.fft.rfftfreq(n_fft, 1 / SR)
    return (m * f[:, None]).sum(axis=0) / (m.sum(axis=0) + 1e-12)


def mod_peak(track, rate):
    """Strongest slow wobble in a track sampled at `rate` Hz: (Hz, depth relative to mean)."""
    t = track - np.polyval(np.polyfit(np.arange(len(track)), track, 2), np.arange(len(track)))
    s = np.abs(np.fft.rfft(t * np.hanning(len(t)), 8 * len(t))) * 2 / (len(t) * 0.5)
    f = np.fft.rfftfreq(8 * len(t), 1 / rate)
    keep = (f >= 0.5) & (f <= 15)
    i = np.argmax(s[keep])
    return float(f[keep][i]), float(s[keep][i])


def analyse(a):
    """a: stereo float array (2, n), note starting at sample 0."""
    mono = a.mean(axis=0)
    side = (a[0] - a[1]) / 2
    env = rms_db(a)  # 10 ms frames
    peak_i = int(np.argmax(env))
    peak = float(env[peak_i])
    above = np.where(env > peak - 50)[0]
    start = int(above[0])
    # attack: 10% to 90% of peak amplitude
    t10 = int(np.argmax(env >= peak - 20))
    t90 = int(np.argmax(env >= peak - 1))
    # the note ends at the steepest fall in the last part; the WAV does not say when
    d = np.diff(np.convolve(env, np.ones(5) / 5, "same"))
    off = int(np.argmin(d[peak_i + 20 :])) + peak_i + 20 if len(d) > peak_i + 40 else len(env) - 1
    if d[off] > -0.8:
        off = min(200, len(env) - 1)
    sus_lo, sus_hi = max(peak_i + 10, off - 50), max(off - 5, peak_i + 12)
    sustain = float(env[sus_lo:sus_hi].mean())
    dropped = np.where(env[peak_i:off] < peak - 0.5 * max(peak - sustain, 1e-3))[0]
    decay = float(dropped[0] * 0.01) if len(dropped) and peak - sustain > 1 else 0.0
    after = env[off:]
    below = np.where(after < sustain - 40)[0]
    release = float(below[0] * 0.01) if len(below) else float(len(after) * 0.01)
    tail_level = float(env[-20:].mean() - peak)

    i0 = max(peak_i, start + 5) * 441
    body = mono[i0 : i0 + 32768]
    f0 = f0_of(body)
    midi = 69 + 12 * np.log2(f0 / 440) if f0 > 0 else 0.0
    harm, noise = harmonics(body, f0)

    cent = centroid_track(mono)
    rate = SR / 1024
    at = lambda s: float(cent[min(int(s * rate), len(cent) - 1)])
    m_end = int(off * 0.01 * rate)
    wob_hz, wob = mod_peak(np.log(cent[int(0.3 * rate) : m_end] + 1), rate) if m_end > int(0.8 * rate) else (0.0, 0.0)
    amp_hz, amp = mod_peak(env[30:off], 100) if off > 90 else (0.0, 0.0)

    hop = 512
    pitch = []
    win = max(4096, int(4 * SR / max(f0, 1)))
    for i in range(int(0.2 * SR), int(off * 441) - win, 2048):
        f = f0_of(mono[i : i + win], f0)
        if f:
            pitch.append(1200 * np.log2(f / f0))
    pitch = np.array(pitch) if len(pitch) > 8 else np.zeros(9)
    vib = float(np.percentile(pitch, 90) - np.percentile(pitch, 10))

    return {
        "f0_hz": round(float(f0), 2),
        "midi": round(float(midi), 2),
        "peak_db": round(20 * float(np.log10(abs(a).max() + 1e-9)), 1),
        "rms_peak_db": round(peak, 1),
        "attack_s": round((t90 - t10) * 0.01, 3),
        "decay_s": round(decay, 3),
        "sustain_db_below_peak": round(peak - sustain, 1),
        "note_off_s": round(off * 0.01, 2),
        "release_s": round(release, 3),
        "tail_db_below_peak": round(-tail_level, 1),
        "centroid_hz": {"t0.05": round(at(0.05)), "t0.3": round(at(0.3)), "t1.0": round(at(1.0)), "t1.8": round(at(1.8))},
        "noise_ratio": round(noise, 3),
        "stereo_side_db": round(10 * float(np.log10(((side**2).mean() + 1e-12) / ((mono**2).mean() + 1e-12))), 1),
        "brightness_wobble": {"hz": round(wob_hz, 2), "depth": round(wob, 3)},
        "level_wobble": {"hz": round(amp_hz, 2), "depth_db": round(amp, 2)},
        "pitch_spread_cents": round(vib, 1),
        "harmonics_db": [round(float(h - harm.max()), 1) for h in harm],
    }


# Wavetable library -------------------------------------------------------------------


def table_list():
    return sorted(str(p.relative_to(TABLES)) for p in TABLES.rglob("*.wav"))


def _render_table(args):
    import patch, render

    table, pos = args
    d = patch.default_design()
    d["osc"][0]["table"] = table
    a = render.render_tree(patch.build(d, {"osc0_pos": pos, "sustain": 1.0, "decay": 0.5, "attack": 0.1}), 48)
    body = a.mean(axis=0)[8820:8820 + 32768]
    f0 = 130.81
    h, noise = harmonics(body, f0)
    return table, pos, h.tolist()


def _init(base):
    import patch

    patch.BASE = base


def build_library(scratch, workers=8):
    jobs = [(t, p) for t in table_list() for p in POSITIONS]
    t0 = time.time()
    with get_context("spawn").Pool(workers, _init, (Path(scratch) / "base.pkl",)) as pool:
        rows = pool.map(_render_table, jobs, chunksize=8)
    json.dump(rows, open(Path(scratch) / "tables.json", "w"))
    print(f"{len(table_list())} tables, {len(jobs)} renders, {time.time()-t0:.0f}s")


def rank_tables(harm_db, scratch, top=8):
    """Closest tables by harmonic shape after removing a smooth tilt, which a filter could explain."""
    rows = json.load(open(Path(scratch) / "tables.json"))
    x = np.log2(np.arange(1, N_HARM + 1))
    target = np.maximum(np.array(harm_db), -70.0)
    keep = target > -60
    if keep.sum() < 6:  # a near-sine target: use the first few harmonics whatever their level
        keep = np.arange(N_HARM) < 6
    best = {}
    for table, pos, h in rows:
        h = np.array(h)
        h = np.maximum(h - h.max(), -70.0)  # a missing harmonic counts as very quiet, not as unknown
        diff = target[keep] - h[keep]
        fit = np.polyval(np.polyfit(x[keep], diff, 2), x[keep])
        err = float(np.sqrt(((diff - fit) ** 2).mean()))
        if table not in best or err < best[table]["error_db"]:
            best[table] = {"table": table, "pos": pos, "error_db": round(err, 2)}
    return sorted(best.values(), key=lambda r: r["error_db"])[:top]


if __name__ == "__main__":
    build_library(sys.argv[1])

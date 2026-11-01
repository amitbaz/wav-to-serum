"""PROTOTYPE, throw away. The gap from "Compare renders with Serum in a DAW", rebuilt.

That ticket records the idea, not the settings: mean absolute dB difference between
two spectrograms, over bins within 60 dB of the loudest. n_fft and hop here are guesses,
checked against the published route gaps in gap_check.py.
"""
import numpy as np
from scipy.signal import stft


def spec_db(a, n_fft=2048, hop=512):
    mono = a.mean(axis=0) if a.ndim == 2 else a
    _, _, z = stft(mono, nperseg=n_fft, noverlap=n_fft - hop, window="hann", boundary=None, padded=False)
    return 20 * np.log10(np.abs(z) + 1e-9)


def gap(a, b, n_fft=2048, hop=512, floor=60.0):
    n = min(a.shape[-1], b.shape[-1])
    x, y = spec_db(a[..., :n], n_fft, hop), spec_db(b[..., :n], n_fft, hop)
    keep = np.maximum(x, y) > max(x.max(), y.max()) - floor
    return float(np.abs(x - y)[keep].mean())


def near(a, b):
    """The gap over the top 30 dB only. The full gap proves two renders are the same sound, but on
    a close match most of it comes from bins 40-60 dB down, which says little about what is heard."""
    return gap(a, b, floor=30.0)


def offset(a, b, span=2048):
    """Samples by which b is late against a, by cross-correlation of the first 200 ms of signal."""
    x, y = a.mean(axis=0)[:8820], b.mean(axis=0)[:8820 + span]
    c = np.correlate(y, x, "full")[len(x) - 1 : len(x) + span]
    return int(np.argmax(c))


def residual_db(a, b):
    n = min(a.shape[-1], b.shape[-1])
    d = a[..., :n] - b[..., :n]
    e = np.sqrt((d**2).mean())
    return -np.inf if e == 0 else float(20 * np.log10(e / np.sqrt((a[..., :n] ** 2).mean())))

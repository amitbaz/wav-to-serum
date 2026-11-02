"""PROTOTYPE, throw away. What differs between each rated POC result and its target, in plain measures."""
import json
from pathlib import Path
import numpy as np, soundfile as sf
from scipy.signal import stft
from scipy.fft import dct
from scipy.stats import spearmanr
import compare as c, tune as t

L = Path.home() / "Desktop/w2s-listen"
ratings = json.loads((L / "run2/w2s-ratings.json").read_text())["ratings"]
key = json.loads((L / "run2/key.json").read_text()); arms = json.loads((L / "run2/ears_key.json").read_text())
SR = 44100

def rms_db(a):
    return 10 * np.log10((a**2).mean() + 1e-12)

def track(a):
    """Per 23 ms frame: level dB, centroid Hz in log2, flatness, with 4096 window."""
    m = a.mean(axis=0)
    _, _, z = stft(m, nperseg=2048, noverlap=1024, boundary=None, padded=False)
    p = np.abs(z)**2
    hz = np.fft.rfftfreq(2048, 1/SR)
    lvl = 10*np.log10(p.sum(0)+1e-12)
    cen = (p*hz[:,None]).sum(0)/(p.sum(0)+1e-12)
    return lvl, np.log2(cen+20)

def attack(lvl):
    pk = lvl.argmax(); i = np.argmax(lvl >= lvl[pk]-3)
    j = np.argmax(lvl >= lvl[pk]-30) if (lvl >= lvl[pk]-30).any() else 0
    return (i-j)*1024/SR

def mfcc(a, n=20):
    m = a.mean(axis=0)
    return dct(t._mel_db(m, 1024), axis=0, norm="ortho")[1:n]

def modspec(a):
    """Depth of level and brightness wobble, 0.5-30 Hz, over the held part."""
    lvl, cen = track(a)
    h = slice(int(.15*SR/1024), int(1.95*SR/1024))
    x = lvl[h]-lvl[h].mean(); y = cen[h]-cen[h].mean()
    d = lambda v: float(np.std(v - np.convolve(v, np.ones(15)/15, "same")))  # fast part only
    return d(x), d(y)

rows = []
for name, r in sorted(ratings.items()):
    job = name[0]
    T, _ = sf.read(L/f"{job}_target.wav", always_2d=True); G, _ = sf.read(L/f"{name}.wav", always_2d=True)
    T, G = T.T, G.T
    lt, ct = track(T); lg, cg = track(G)
    n = min(len(lt), len(lg)); s = lt[:n] > lt.max()-40
    gn = G * 10**((rms_db(T)-rms_db(G))/20)
    sideT = 10*np.log10(((T[0]-T[1])**2).mean()/( (T[0]+T[1])**2 ).mean()+1e-9); sideG = 10*np.log10(((G[0]-G[1])**2).mean()/( (G[0]+G[1])**2 ).mean()+1e-9)
    mt, mg = mfcc(T), mfcc(gn)
    wt, wg = modspec(T), modspec(G)
    rows.append(dict(id=name, sound=key[job], arm=arms[name][:1], ear=r["rating"], lvl=round(rms_db(G)-rms_db(T),1),
        near=round(c.near(T,G),2), near_norm=round(c.near(T,gn),2),
        bright=round(float(np.abs(ct[:n]-cg[:n])[s].mean())*12,1), bright_bias=round(float((cg[:n]-ct[:n])[s].mean())*12,1),
        env=round(float(np.abs(lt[:n]-lg[:n]-(lt[:n]-lg[:n])[s].mean())[s].mean()),1),
        atkT=round(attack(lt)*1000), atkG=round(attack(lg)*1000), side=round(sideG-sideT,1),
        mfcc=round(float(np.abs(mt-mg).mean()),1), mfcc_mean=round(float(np.abs(mt.mean(1)-mg.mean(1)).mean()),1),
        wob_lvl=(round(wt[0],2),round(wg[0],2)), wob_bri=(round(wt[1],3),round(wg[1],3))))
print(*rows, sep="\n")
e = [x["ear"] for x in rows]
for k in ("near","near_norm","bright","env","mfcc","mfcc_mean"):
    print(k, "spearman with ear", round(spearmanr([x[k] for x in rows], e).statistic, 2))
print("abs lvl", round(spearmanr([abs(x["lvl"]) for x in rows], e).statistic, 2))

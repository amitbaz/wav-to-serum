"""PROTOTYPE, throw away. Blind round for "Step 3: filter or no filter", method 2. Key stays in the work folder.

Per held-out sound: the match, and one copy of it with its knobs pushed away until it scores near a set value
between 1.5 and 5, so the ratings also test whether "below 2.5 sounds right" holds on made sounds.
"""
import json, pickle, random
from pathlib import Path

import numpy as np
import soundfile as sf

import oracle as o
import render as rd
import step1 as s1
import step3  # its filter knob ranges (mapper) apply to the pushed copies
import tune as t

work = Path(__file__).parent
out = Path.home() / "Desktop/w2s-listen-step3-method2"
out.mkdir(exist_ok=True)
sounds = [s for s in json.load(open(work / "step3b/sounds.json")) if s["split"] == "held_out"]
rng, nrng = random.Random(4343), np.random.default_rng(43)
letters = rng.sample("ABCDEFGHJK", len(sounds))
ids = rng.sample(range(100, 999), 2 * len(sounds))
aims = list(np.linspace(1.5, 5.0, len(sounds))); rng.shuffle(aims)
key, page = {}, {}
rms = lambda a: np.sqrt((a**2).mean())
for s, letter, aim in zip(sounds, letters, aims):
    T, _ = sf.read(work / f"step3b/{s['name']}_target.wav", dtype="float32", always_2d=True)
    m = pickle.load(open(work / f"step3b/{s['name']}_match.pkl", "rb"))
    fT, x = t.features(T.T), np.array(m["x"])
    base = pickle.load(open(work / f"step3b/{s['name']}_match.pkl", "rb"))["tree"]
    best = None
    for sigma in np.geomspace(0.02, 0.6, 14):  # push every knob by sigma, keep the one nearest the aim
        for _ in range(3):
            a = rd.render_tree(o.apply(base, m["knobs"], np.clip(x + nrng.normal(0, sigma, len(x)), 0, 1)), s["note"])
            sc = t.score(t.features(a), fT)
            if best is None or abs(sc - aim) < abs(best[0] - aim):
                best = (sc, a)
    got, _ = sf.read(work / f"step3b/{s['name']}_match.wav", dtype="float32", always_2d=True)
    arms = {"match": (json.load(open(work / f"step3b/{s['name']}_match.json"))["score_final"], got), "pushed": (best[0], best[1].T)}
    sf.write(out / f"{letter}_target.wav", T, 44100, subtype="PCM_24")
    names = list(arms); rng.shuffle(names); page[letter] = []
    for arm in names:
        sc, a = arms[arm]
        g = rms(T) / max(rms(a), 1e-9); a = np.clip(a * g, -1, 1); n = ids.pop()
        page[letter].append(n)
        key[f"{letter}_{n}"] = {"sound": s["name"], "arm": arm, "score": round(float(sc), 2), "gain_db": round(float(20 * np.log10(g)), 1)}
        sf.write(out / f"{letter}_{n}.wav", a, 44100, subtype="PCM_24")
    print(s["name"], letter, {k: v["score"] for k, v in key.items() if v["sound"] == s["name"]}, flush=True)
(work / "step3b/listen_key.json").write_text(json.dumps(key, indent=1))
h = (work / "listen_template.html").read_text().replace("__SOUNDS__", json.dumps(dict(sorted(page.items()))))
h = h.replace("w2s-ratings-pieces", "w2s-ratings-step3-method2")
(out / "listen.html").write_text(h)
print(len(key), "results in", out)

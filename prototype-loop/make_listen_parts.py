"""PROTOTYPE, throw away. Blind round for "Can per-part pieces pick a structure...". Key stays in the work folder."""
import json, random, re
from pathlib import Path
import numpy as np, soundfile as sf

work = Path(__file__).parent
out = Path.home() / "Desktop/w2s-listen-pieces"
out.mkdir(exist_ok=True)
SOUNDS = ["Bass 1", "Bass 2", "Lead 1", "Lead 4", "Synth 1", "Synth 4"]
rng = random.Random(3737)
letters = rng.sample("ABCDEF", 6)
ids = rng.sample(range(100, 999), 20)
key, sounds = {}, {}
rms = lambda a: np.sqrt((a**2).mean())
for label, letter in zip(SOUNDS, letters):
    tag = label.replace(" ", "")
    T, _ = sf.read(work / f"parts/{tag}_target.wav", always_2d=True)
    arms = {"pieces": work / f"parts/{tag}_whole.wav", "true_restarts": work / f"routes/{tag}_restarts_s1.wav"}
    sf.write(out / f"{letter}_target.wav", T, 44100, subtype="PCM_24")
    names = list(arms); rng.shuffle(names); sounds[letter] = []
    for arm in names:
        a, _ = sf.read(arms[arm], always_2d=True)
        g = rms(T) / rms(a); a = np.clip(a * g, -1, 1); n = ids.pop()
        sounds[letter].append(n)
        key[f"{letter}_{n}"] = {"sound": label, "arm": arm, "gain_db": round(float(20 * np.log10(g)), 1)}
        sf.write(out / f"{letter}_{n}.wav", a, 44100, subtype="PCM_24")
(work / "listen_pieces_key.json").write_text(json.dumps(key, indent=1))
h = (work / "listen_template.html").read_text().replace("__SOUNDS__", json.dumps(sounds))
(out / "listen.html").write_text(h)
print(sounds, len(key))

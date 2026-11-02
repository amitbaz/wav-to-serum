"""PROTOTYPE, throw away. Blind round for "Find out why close numbers still sound wrong". Key stays in the scratchpad."""
import json, random, re
from pathlib import Path
import numpy as np, soundfile as sf

work = Path(__file__).parent
old = Path.home() / "Desktop/w2s-listen"
out = Path.home() / "Desktop/w2s-listen-2"
out.mkdir(exist_ok=True)
POC = {"Bass 1": "B_765", "Bass 2": "F_432", "Lead 1": "A_372", "Lead 4": "E_960", "Synth 1": "D_315", "Synth 4": "C_364"}
rng = random.Random(3232)
letters = rng.sample("ABCDEF", 6)
ids = rng.sample(range(100, 999), 40)
key, sounds = {}, {}


def rms(a):
    return np.sqrt((a**2).mean())


for label, letter in zip(POC, letters):
    tag = label.replace(" ", "")
    T, _ = sf.read(work / f"oracle/{tag}_target.wav", always_2d=True)
    arms = {"poc_best": old / f"{POC[label]}.wav", "true_random": work / f"oracle/{tag}_s1.wav",
            "true_near05": work / f"oracle/{tag}_s1_near0.05.wav", "library": work / f"retrieved/{tag}_tuned.wav"}
    sf.write(out / f"{letter}_target.wav", T, 44100, subtype="PCM_24")
    names = list(arms)
    rng.shuffle(names)
    sounds[letter] = []
    for arm in names:
        a, _ = sf.read(arms[arm], always_2d=True)
        g = rms(T) / rms(a)
        a = np.clip(a * g, -1, 1)
        n = ids.pop()
        sounds[letter].append(n)
        key[f"{letter}_{n}"] = {"sound": label, "arm": arm, "gain_db": round(float(20 * np.log10(g)), 1)}
        sf.write(out / f"{letter}_{n}.wav", a, 44100, subtype="PCM_24")

(work / "listen2_key.json").write_text(json.dumps(key, indent=1))

h = (old / "listen.html").read_text()
h = re.sub(r"const SOUNDS = \{.*?\};", "const SOUNDS = " + json.dumps(sounds) + ";", h, count=1)
h = h.replace('STORE = "w2s-ratings"', 'STORE = "w2s-ratings-2"').replace('blank = { ratings:{}, presets:{ ok:"", note:"" } }', 'blank = { ratings:{} }')
h = h.replace('entry = f => state.ratings[f] ||= { rating:null, note:"" }', 'entry = f => state.ratings[f] ||= { rating:null, note:"", off:[] }')
h = h.replace("const [one, two] = files(l);\n", "")
# four results, each with one-click fault tags
h = h.replace('''placeholder="Note, if anything is obvious: wrong pitch, wrong attack, too quiet"''', '''placeholder="Anything else, optional"''')
h = h.replace('''<input type="text" data-note''', '''<div class="rate">${["tone","attack","movement"].map(t => `<button class="pick ${entry(f).off.includes(t) ? "on" : ""}" data-off="${f}" data-t="${t}">${t} wrong</button>`).join("")}</div>
    <input type="text" data-note''')
h = h.replace('${card(one, "Result 1", 1)}${card(two, "Result 2", 2)}', '${files(l).map((f, i) => card(f, `Result ${i + 1}`, i + 1)).join("")}')
h = re.sub(r"function lastPage\(\) \{.*?\n\}\nfunction show", '''function lastPage() {
  const all = LETTERS.flatMap(files), left = all.filter(f => !state.ratings[f]?.rating).length;
  return `<div class="card"><div class="name">Save</div>
    <p class="hint">${left ? `${left} of ${all.length} results still need a rating.` : `All ${all.length} results are rated.`}</p>
    <button id="save">Save ratings</button><p class="hint" id="saved"></p></div>`;
}
function show''', h, flags=re.S)
h = h.replace('''  if (d.ok) { state.presets.ok = d.ok; show(at); }\n''', '''  if (d.off) { const o = entry(d.off).off, i = o.indexOf(d.t); i < 0 ? o.push(d.t) : o.splice(i, 1); b.classList.toggle("on", i < 0); keep(); }\n''')
h = h.replace('''  if ("pnote" in t.dataset) state.presets.note = t.value;\n''', "")
h = h.replace('download:"w2s-ratings.json"', 'download:"w2s-ratings-2.json"').replace("as w2s-ratings.json", "as w2s-ratings-2.json")
h = h.replace('if (k === "1" || k === "2") play(files(l)[+k - 1]);', 'if ("1234".includes(k)) play(files(l)[+k - 1]);')
(out / "listen.html").write_text(h)
print(sounds, len(key))
print({k: v["gain_db"] for k, v in key.items()})

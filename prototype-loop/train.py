"""PROTOTYPE, throw away. Does a first-guess model get better with more renders? A learning curve.

Renders random knob settings of a sound's true structure in chunks saved to disk (a pause loses at most
one chunk), fits the model at each step, then tunes from its guess. Truth is used only to report.
  python train.py WORK TOTAL SOUND [SOUND ...]
"""
import csv, json, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import compare as c
import oracle as o
import render as r
import routes as R
import tune as t

import os
CHUNK, STEPS, TUNE = (50, (100,), 60) if os.environ.get("SMOKE") else (5000, (20000, 60000, 180000, 400000), 10000)


def view(v):
    """routes.compact with fine pitch pooled over the whole note, to keep 400K renders in memory."""
    return np.concatenate([v[:1401], v[1401:].reshape(400, 4).mean(axis=1)])


def fit(X, V, tv):
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler

    cut = int(len(X) * 0.95)  # last 5% held out to report how well it learned
    sc = StandardScaler().fit(V[:cut])
    m = MLPRegressor(hidden_layer_sizes=(512, 256), early_stopping=True, max_iter=200, random_state=0)
    m.fit(sc.transform(V[:cut]), X[:cut])
    return np.clip(m.predict(sc.transform(tv[None]))[0], 0, 1), float(m.score(sc.transform(V[cut:]), X[cut:]))


def main():
    work, total = Path(sys.argv[1]), int(sys.argv[2])
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    for label in sys.argv[3:]:
        tag = label.replace(" ", "")
        out = work / "train" / tag
        out.mkdir(parents=True, exist_ok=True)
        note = o.NOTES[label.split()[0]]
        _, tree = s.decode_preset_file(paths[label])
        target = r.render_tree(tree, note)
        feats = t.features(target)
        tv = view(R.compact(feats))
        knobs = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(tree)]
        n = len(knobs)
        truth = np.array([o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs])
        with get_context("spawn").Pool(8, R._init, (tree, knobs, feats, note)) as pool:
            for i in range(total // CHUNK):
                f = out / f"chunk_{i:03d}.npz"
                if f.exists():
                    continue
                t0 = time.time()
                xs = np.random.default_rng(1000 + i).uniform(0, 1, (CHUNK, n))
                res = pool.map(R._eval, [list(map(float, x)) for x in xs], chunksize=8)
                ok = [j for j, (_, v) in enumerate(res) if v is not None]
                np.savez(f.with_suffix(".tmp.npz"), X=xs[ok].astype(np.float32), V=np.stack([view(res[j][1]) for j in ok]).astype(np.float16),
                         S=np.array([res[j][0] for j in ok], np.float32))
                f.with_suffix(".tmp.npz").rename(f)  # only whole chunks count
                print(f"{label}: chunk {i + 1}/{total // CHUNK} in {time.time() - t0:.0f}s", flush=True)
                step = (i + 1) * CHUNK
                if step not in STEPS or (out / f"step_{step}.json").exists():
                    continue
                d = [np.load(out / f"chunk_{j:03d}.npz") for j in range(i + 1)]
                X, V, S = (np.concatenate([z[k] for z in d]) for k in ("X", "V", "S"))
                t0 = time.time()
                guess, r2 = fit(X, V.astype(np.float32), tv)
                fit_secs = round(time.time() - t0)
                del X, V, d
                Srch = R.Search(pool, TUNE)
                gscore = Srch.f([guess])[0]
                x = guess
                while Srch.left() > 0:
                    Srch.cma(x, 0.08, stall=2000)
                    x = Srch.bx.copy()
                got = r.render_tree(o.apply(tree, knobs, Srch.bx), note)
                res = {"sound": label, "renders": step, "knobs": n, "model_r2": round(r2, 3), "fit_secs": fit_secs,
                       "best_random": round(float(S.min()), 3), "guess_score": round(gscore, 3), "guess_err": round(float(np.abs(guess - truth).mean()), 3),
                       "guess_within5": round(float((np.abs(guess - truth) < 0.05).mean()), 2), "score_final": round(Srch.best, 3),
                       "near": round(c.near(target, got), 2), "knob_err": round(float(np.abs(Srch.bx - truth).mean()), 3)}
                (out / f"step_{step}.json").write_text(json.dumps(res))
                sf.write(out / f"step_{step}.wav", got.T, 44100, subtype="FLOAT")
                print(json.dumps(res), flush=True)


if __name__ == "__main__":
    main()

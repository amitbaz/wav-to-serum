"""PROTOTYPE, throw away. "Find a start the tuner can finish from": routes to below 2.5 with no truth.

True structure, knob values hidden, same random start as oracle.py's seed. Truth is used only to report.
  python routes.py WORK ARM BUDGET SEED SOUND [SOUND ...]     ARM: restarts | blocks | screen | model
"""
import csv, json, os, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import cma
import numpy as np
import serum2_preset_loader as s
import soundfile as sf

import compare as c
import oracle as o
import render as r
import tune as t

_w = {}


def _init(tree, knobs, feats, note):
    _w.update(tree=tree, knobs=knobs, feats=feats, note=note)


def compact(f):
    """Small fixed-size view of a render for the first-guess model."""
    pool = lambda m, n: np.stack([b.mean(axis=1) for b in np.array_split(m, n, axis=1)], axis=1).ravel()
    return np.concatenate([pool(f["m1024"], 16), pool(f["s1024"], 4), f["env"][::5], pool(f["fine"][:400], 4)])


def _eval(x):
    a = r.render_tree(o.apply(_w["tree"], _w["knobs"], x), _w["note"])
    if not np.isfinite(a).all() or abs(a).max() > 8:
        return 1e3, None
    f = t.features(a)
    return t.score(f, _w["feats"]), compact(f).astype(np.float32)


class Search:
    """Counts renders and keeps the best point. f(xs) scores full knob vectors."""

    def __init__(self, pool, budget):
        self.pool, self.budget, self.used, self.best, self.bx, self.hist = pool, budget, 0, float("inf"), None, []

    def left(self):
        return self.budget - self.used

    def f(self, xs, vecs=False):
        out = self.pool.map(_eval, [list(map(float, x)) for x in xs], chunksize=1)
        self.used += len(xs)
        for x, (v, _) in zip(xs, out):
            if v < self.best:
                self.best, self.bx = v, np.array(x, float)
        self.hist.append((self.used, round(self.best, 3)))
        return out if vecs else [v for v, _ in out]

    def cma(self, x0, sigma, idx=None, budget=None, popsize=None, stall=1500):
        """Full-covariance CMA on the knobs in idx (all if None); others held at x0."""
        x0 = np.array(x0, float)
        idx = np.arange(len(x0)) if idx is None else np.array(idx)
        cap = self.used + min(budget or self.left(), self.left())
        opts = {"bounds": [0, 1], "seed": int(self.used) + 7, "verbose": -9}
        if popsize:
            opts["popsize"] = popsize
        es = cma.CMAEvolutionStrategy(np.clip(x0[idx], 0.01, 0.99).tolist(), sigma, opts)
        best, last = float("inf"), self.used
        while self.used < cap and not es.stop():
            ys = es.ask()
            xs = []
            for y in ys:
                x = x0.copy(); x[idx] = y; xs.append(x)
            fs = self.f(xs)
            es.tell(ys, fs)
            if min(fs) < best * 0.99:
                best, last = min(fs), self.used
            if self.used - last > stall:
                break
        return es.popsize


def restarts(S, x0, rng, n):
    """IPOP: full CMA from the start, then from fresh random starts with double the population."""
    pop = None
    while S.left() > 0:
        pop = S.cma(x0, 0.2, popsize=pop) * 2
        x0 = rng.uniform(0.15, 0.85, n)


def blocks(S, x0, groups):
    """A few knobs at a time: one module per CMA, swept with shrinking steps."""
    x, sigma = np.array(x0, float), 0.2
    while S.left() > 0:
        for g in groups:
            S.cma(x, sigma, idx=g, budget=max(120, 30 * len(g)), stall=300)
            x = S.bx.copy()
            if S.left() <= 0:
                break
        sigma = max(sigma / 2, 0.03)


def screen(S, x0, rng, n, r=10, delta=0.25, k=16):
    """Fewer knobs: Morris screening at random points (no truth), tune the k that matter most, then all."""
    effects = np.zeros((r, n))
    for j in range(r):
        base = rng.uniform(0.1, 0.9, n)
        steps, cur = [base.copy()], base.copy()
        for i in rng.permutation(n):
            cur = cur.copy(); cur[i] += delta if cur[i] + delta <= 1 else -delta; steps.append(cur)
        fs = S.f(steps)
        for a in range(n):
            i = int(np.flatnonzero(steps[a + 1] != steps[a])[0])
            effects[j, i] = abs(fs[a + 1] - fs[a])
    mu = effects.mean(axis=0)
    top = np.argsort(-mu)[:k]
    S.cma(x0, 0.2, idx=top, budget=int(S.left() * 0.6))
    x = S.bx.copy()
    while S.left() > 0:
        S.cma(x, 0.1, stall=2000)
        x = S.bx.copy()
    return mu, top


def model(S, x0, rng, n, train=int(os.environ.get("TRAIN", 20000))):
    """First guess: train an inverse model on random renders of this structure, then tune from its guess."""
    from sklearn.neural_network import MLPRegressor
    from sklearn.preprocessing import StandardScaler

    X, V = [], []
    for _ in range(0, train, 400):
        xs = rng.uniform(0, 1, (400, n))
        out = S.f(xs, vecs=True)
        for x, (_, v) in zip(xs, out):
            if v is not None:
                X.append(x); V.append(v)
    X, V = np.array(X), np.array(V)
    sc = StandardScaler().fit(V)
    m = MLPRegressor(hidden_layer_sizes=(512, 256), early_stopping=True, max_iter=300, random_state=0).fit(sc.transform(V), X)
    tv = _w_target_vec
    guess = np.clip(m.predict(sc.transform(tv[None]))[0], 0, 1)
    gscore = S.f([guess])[0]
    held = float(m.score(sc.transform(V[-2000:]), X[-2000:]))
    x = guess
    while S.left() > 0:
        S.cma(x, 0.08, stall=2000)
        x = S.bx.copy()
    return guess, gscore, held


def main():
    global _w_target_vec
    work, arm, budget, seed = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    out = work / "routes"
    out.mkdir(exist_ok=True)
    for label in sys.argv[5:]:
        if (out / f"{label.replace(' ', '')}_{arm}_s{seed}.json").exists():  # done before a pause: keep it
            continue
        note = o.NOTES[label.split()[0]]
        _, tree = s.decode_preset_file(paths[label])
        target = r.render_tree(tree, note)
        feats = t.features(target)
        _w_target_vec = compact(feats)
        knobs = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(tree)]
        n = len(knobs)
        truth = np.array([o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs])
        rng = np.random.default_rng(seed)
        x0 = rng.uniform(0.15, 0.85, n)  # the same start oracle.py drew for this seed
        t0 = time.time()
        extra = {}
        with get_context("spawn").Pool(8, _init, (tree, knobs, feats, note)) as pool:
            S = Search(pool, budget)
            if arm == "restarts":
                restarts(S, x0, rng, n)
            elif arm == "blocks":
                names = [kn[0][0] if not kn[0][0].startswith("FXRack") else f"FX{kn[0][2]}" for kn in knobs]
                groups = [[i for i, g in enumerate(names) if g == u] for u in dict.fromkeys(names)]
                single = [g[0] for g in groups if len(g) == 1]  # CMA needs 2 or more knobs: pool the loners
                groups = [g for g in groups if len(g) > 1] + ([single] if len(single) > 1 else [])
                if len(single) == 1:
                    groups[-1] += single
                extra["groups"] = [len(g) for g in groups]
                blocks(S, x0, groups)
            elif arm == "screen":
                mu, top = screen(S, x0, rng, n)
                extra["top"] = [knobs[i][0][0] + ":" + knobs[i][1] for i in top]
                extra["top_share"] = round(float(mu[top].sum() / mu.sum()), 2)
            elif arm == "model":
                guess, gscore, held = model(S, x0, rng, n)
                extra.update(guess_score=round(gscore, 3), guess_err=round(float(np.abs(guess - truth).mean()), 3), model_r2=round(held, 3),
                             guess_within5=round(float((np.abs(guess - truth) < 0.05).mean()), 2))
        got = r.render_tree(o.apply(tree, knobs, S.bx), note)
        tag = f"{label.replace(' ', '')}_{arm}_s{seed}"
        res = {"sound": label, "arm": arm, "knobs": n, "evals": S.used, "secs": round(time.time() - t0), "score_final": round(S.best, 3),
               "near": round(c.near(target, got), 2), "knob_err": round(float(np.abs(S.bx - truth).mean()), 3), **extra,
               "parts": {k: round(v, 2) for k, v in t.parts(t.features(got), feats).items()}, "hist": S.hist[:: max(1, len(S.hist) // 10)]}
        (out / f"{tag}.json").write_text(json.dumps(res))
        pickle.dump({"tree": o.apply(tree, knobs, S.bx), "x": S.bx.tolist(), "knobs": knobs}, open(out / f"{tag}.pkl", "wb"))
        sf.write(out / f"{tag}.wav", got.T, 44100, subtype="FLOAT")
        sf.write(out / f"{label.replace(' ', '')}_target.wav", target.T, 44100, subtype="FLOAT")
        print(json.dumps({k: v for k, v in res.items() if k not in ("hist", "parts")}), flush=True)


if __name__ == "__main__":
    main()

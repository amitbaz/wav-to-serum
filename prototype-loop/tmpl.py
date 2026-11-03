"""PROTOTYPE, throw away. Run a route from routes.py on the POC template instead of the true structure.

Designs are the final rules and designer designs from "Prove the whole loop on a few simple sounds".
  python tmpl.py OLDWORK ARM BUDGET SEED JOB [JOB ...]
"""
import json, pickle, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import soundfile as sf

import compare as c
import patch
import routes as R
import tune as t

_w = {}


def _init(base, design, feats, note):
    patch.BASE = base
    _w.update(design=design, names=list(patch.knobs(design)), feats=feats, note=note)


def _eval(x):
    a = t.render_values(_w["design"], dict(zip(_w["names"], map(float, x))), _w["note"])
    if not np.isfinite(a).all() or abs(a).max() > 8:
        return 1e3, None
    f = t.features(a)
    return t.score(f, _w["feats"]), R.compact(f).astype(np.float32)


class Search(R.Search):
    def f(self, xs, vecs=False):
        out = self.pool.map(_eval, [list(map(float, x)) for x in xs], chunksize=1)
        self.used += len(xs)
        for x, (v, _) in zip(xs, out):
            if v < self.best:
                self.best, self.bx = v, np.array(x, float)
        self.hist.append((self.used, round(self.best, 3)))
        return out if vecs else [v for v, _ in out]


def group(name):
    if name in ("master", "attack", "decay", "sustain", "release"):
        return "amp"
    for p in ("osc0", "osc1", "osc2", "env2", "lfo", "dist", "chorus", "delay", "reverb"):
        if name.startswith(p):
            return p
    return {"cutoff": "filter", "reso": "filter", "drive": "filter", "filter_env_amt": "env2", "table_env_amt": "env2"}.get(name, "misc")


def main():
    old, arm, budget, seed = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3]), int(sys.argv[4])
    finals = json.load(open(old / "finals.json"))
    base = old / "base.pkl"
    patch.BASE = base
    out = Path("tmpl")
    out.mkdir(exist_ok=True)
    for job in sys.argv[5:]:
        target = np.load(old / "jobs" / job / "target.npy")
        import loop; note = int(round(loop.report(target)["midi"]))  # the pitch the old loop heard, as it played it
        feats = t.features(target)
        R._w_target_vec = R.compact(feats)
        for who in ("rules", "designer"):
            if (out / f"{job}_{who}_{arm}_s{seed}.json").exists():  # done before a pause: keep it
                continue
            design = finals[job][who]["design"]
            names = list(patch.knobs(design))
            n = len(names)
            rng = np.random.default_rng(seed)
            x0 = rng.uniform(0.15, 0.85, n)
            t0, extra = time.time(), {}
            with get_context("spawn").Pool(4, _init, (base, design, feats, note)) as pool:
                S = Search(pool, budget)
                if arm == "restarts":
                    R.restarts(S, x0, rng, n)
                elif arm == "blocks":
                    g = [group(k) for k in names]
                    groups = [[i for i, x in enumerate(g) if x == u] for u in dict.fromkeys(g)]
                    single = [x[0] for x in groups if len(x) == 1]
                    groups = [x for x in groups if len(x) > 1] + ([single] if len(single) > 1 else [])
                    if len(single) == 1:
                        groups[-1] += single
                    R.blocks(S, x0, groups)
                elif arm == "screen":
                    R.screen(S, x0, rng, n, k=min(16, n - 1))
                elif arm == "model":
                    guess, gscore, held = R.model(S, x0, rng, n)
                    extra.update(guess_score=round(gscore, 3), model_r2=round(held, 3))
            values = dict(zip(names, map(float, S.bx)))
            got = t.render_values(design, values, note)
            tag = f"{job}_{who}_{arm}_s{seed}"
            res = {"job": job, "sound": finals[job]["sound"], "design_from": who, "arm": arm, "knobs": n, "evals": S.used, "secs": round(time.time() - t0),
                   "score_final": round(S.best, 3), "near": round(c.near(target, got), 2), **extra,
                   "parts": {k: round(v, 2) for k, v in t.parts(t.features(got), feats).items()}}
            (out / f"{tag}.json").write_text(json.dumps(res))
            pickle.dump({"design": design, "values": values}, open(out / f"{tag}.pkl", "wb"))
            sf.write(out / f"{tag}.wav", got.T, 44100, subtype="FLOAT")
            print(json.dumps({k: v for k, v in res.items() if k != "parts"}), flush=True)


if __name__ == "__main__":
    main()

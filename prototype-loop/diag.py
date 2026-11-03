"""PROTOTYPE, throw away. Where is a random-start result's error? Set each knob to its true value alone
and see how much the score drops.  python diag.py WORK SOUND [SOUND ...]"""
import csv, json, pickle, sys
from multiprocessing import get_context
from pathlib import Path

import numpy as np
import serum2_preset_loader as s

import oracle as o
import render as r
import tune as t

_w = {}


def _init(tree, knobs, feats, note):
    _w.update(tree=tree, knobs=knobs, feats=feats, note=note)


def _eval(x):
    a = r.render_tree(o.apply(_w["tree"], _w["knobs"], x), _w["note"])
    return t.score(t.features(a), _w["feats"])


def main():
    work = Path(sys.argv[1])
    paths = dict(csv.reader(open(work / "paths.tsv"), delimiter="\t"))
    for label in sys.argv[2:]:
        note = o.NOTES[label.split()[0]]
        _, tree = s.decode_preset_file(paths[label])
        feats = t.features(r.render_tree(tree, note))
        res = pickle.load(open(work / "old_oracle" / f"{label.replace(' ', '')}_s1.pkl", "rb"))
        knobs, x = res["knobs"], np.array(res["x"])
        truth = np.array([o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs])
        jobs = [x.tolist()]
        for i in range(len(knobs)):
            y = x.copy(); y[i] = truth[i]; jobs.append(y.tolist())
        with get_context("spawn").Pool(8, _init, (tree, knobs, feats, note)) as pool:
            f = pool.map(_eval, jobs, chunksize=1)
        base = f[0]
        rows = sorted(((base - f[i + 1], abs(x[i] - truth[i]), "/".join(map(str, knobs[i][0])) + ":" + knobs[i][1]) for i in range(len(knobs))), reverse=True)
        gains = np.array([g for g, _, _ in rows])
        print(json.dumps({"sound": label, "score": round(base, 2), "knobs": len(knobs), "mean_err": round(float(np.abs(x - truth).mean()), 3),
                          "top5_gain": round(float(gains[:5].clip(0).sum()), 2), "all_gain": round(float(gains.clip(0).sum()), 2),
                          "top": [(round(g, 2), round(d, 2), n) for g, d, n in rows[:6]]}), flush=True)


if __name__ == "__main__":
    main()

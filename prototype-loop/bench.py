"""PROTOTYPE, throw away. How long does one render take, alone and in parallel?

Prints no preset names. Renders go nowhere.
"""
import csv, json, sys, time
from multiprocessing import get_context
from pathlib import Path

import numpy as np

import render as r

SCRATCH = Path(sys.argv[1])
kinds = {p["label"]: p["kind"] for p in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}
paths = dict(csv.reader(open(SCRATCH / "paths.tsv"), delimiter="\t"))


def one(args):
    label, n = args
    t = time.perf_counter()
    out = []
    for _ in range(n):
        a = r.render_file(paths[label], r.NOTES[kinds[label]])
        out.append((time.perf_counter() - t, float(abs(a).max()), a.tobytes().__hash__()))
        t = time.perf_counter()
    return label, out


if __name__ == "__main__":
    label, res = one(("Bass 1", 11))
    ts = [x[0] for x in res[1:]]
    print(f"one process: median {np.median(ts):.3f}s, max {max(ts):.3f}s, first {res[0][0]:.3f}s, identical {len({x[2] for x in res})==1}")
    for label in paths:
        _, res = one((label, 1))
        print(label, f"{res[0][0]:.3f}s peak {res[0][1]:.3f}")
    for workers in (2, 4, 8):
        t = time.perf_counter()
        with get_context("spawn").Pool(workers) as pool:
            out = pool.map(one, [("Bass 1", 20)] * workers)
        wall = time.perf_counter() - t
        ts = [x[0] for _, res in out for x in res[1:]]
        hashes = {x[2] for _, res in out for x in res}
        print(f"{workers} workers: {workers*20/wall:.1f} renders/s, median {np.median(ts):.3f}s each, identical across workers {len(hashes)==1}")

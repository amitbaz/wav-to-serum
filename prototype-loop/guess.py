"""PROTOTYPE, throw away. "Can trained guessers pick a structure the tuner can finish from?"

  python guess.py data N               N training renders into guess/data/: bank structures in turn, knobs random, notes random.
                                       Resumable in shards of 500. Labels come from the randomised tree, so a part that is
                                       silent after randomising is labelled off.
  python guess.py ear N [N ...]        guesser accuracy on held-out structures (whole structures, never single renders),
                                       CLAP against our own features, trained on the first N renders
Truth is used only to report and for the bound.
"""
import json, pickle, sys, time
from collections import Counter
from multiprocessing import get_context
from pathlib import Path

import numpy as np
from scipy.signal import resample_poly

import pick  # before retrieve, which puts testset/ (with its own pick.py) first on the path
import bank as bk
import oracle as o
import render as r
import serum2_preset_loader as s
import structure as st
import tune as t

import os
MODE = os.environ.get("MODE", "random")  # random: knobs anywhere; own: each preset's own values, nudged
DATA = Path("guess/data" if MODE == "random" else f"guess/data_{MODE}")
SHARD = 500
SRC_KIND = {2: "Env1", 3: "Env", 4: "Env", 5: "Env", 6: "LFO", 7: "LFO", 8: "LFO", 9: "LFO"}  # moving sources; the rest are static on one note
FILTERS = ["none", "MgL12", "MgL24", "MgL18", "Ladder", "HP12"]
FAMILIES = ["Default", "Analog", "Digital"]
UNISON = [(1, 1), (2, 3), (4, 7), (8, 16)]


def moving_routes(tree):
    out = set()
    for k, v in tree.items():
        if k.startswith("ModSlot") and isinstance(v, dict) and v.get("source") and v.get("destModuleTypeString"):
            kind = SRC_KIND.get(v["source"][0])
            if kind:
                out.add(f"{kind}>{v['destModuleTypeString']}.{v['destModuleParamName'].removeprefix('kParam')}")
    return out


def norm_table(tb):
    tb = (tb or "").lstrip("/")
    return tb or "Default Shapes.wav"


def fam(tb):
    tb = norm_table(tb)
    return "Default" if tb == "Default Shapes.wav" else tb.split("/")[0] if tb.split("/")[0] in FAMILIES else "other"


def filt(f):
    return "none" if not f else "Ladder" if f.startswith("Ladder") else f if f in FILTERS else "other"


def labels(tree):
    x = st.of_tree(tree)
    uni = max([oo["unison"] for oo in x["osc"]] or [1])
    return {"osc": min(len(x["osc"]), 3), "sub": int(x["sub"]), "noise": int(x["noise"]),
            "unison": next(i for i, (lo, hi) in enumerate(UNISON) if lo <= min(uni, 16) <= hi),
            "filter": filt(x["filters"][0] if x["filters"] else None),
            "fx": sorted({f for rk in x["fx"] for f in rk}), "routes": sorted(moving_routes(tree)),
            "families": sorted({fam(oo["table"]) for oo in x["osc"]}), "tables": sorted({norm_table(oo["table"]) for oo in x["osc"]})}


def randomise(tree, knobs, rng):
    """Random knobs, but every moving route keeps a depth well away from zero, so a route marked on can be heard."""
    moving = {k for k, v in tree.items() if k.startswith("ModSlot") and isinstance(v, dict) and SRC_KIND.get((v.get("source") or [None])[0])}
    u = rng.uniform(0.15, 0.85, len(knobs))
    for j, (path, k, _, lo, hi, _) in enumerate(knobs):
        if k == "kParamAmount" and path[0] in moving:
            u[j] = 0.5 + rng.choice([-1, 1]) * rng.uniform(0.2, 0.45) if lo < 0 else rng.uniform(0.4, 0.95)
    return o.apply(tree, knobs, u)


def nudge(tree, knobs, rng, sd=0.05):
    """Each preset's own knob values, moved a little: parts stay as audible as their designer set them."""
    u = [o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in knobs]
    return o.apply(tree, knobs, np.clip(np.array(u) + rng.normal(0, sd, len(u)), 0, 1))


def summary(a):
    """Our own features as one fixed-length vector: tone, its movement, width, envelope and attack."""
    f = t.features(a)
    m = f["m1024"]
    ix = lambda v, n: np.interp(np.linspace(0, len(v) - 1, n), np.arange(len(v)), v)
    p = 10 ** (m / 10)
    cent = (p * np.arange(len(m))[:, None]).sum(0) / (p.sum(0) + 1e-12)
    env = f["env"] - f["env"].max()
    return np.concatenate([m.mean(1) - m.mean(), m.std(1), np.abs(np.diff(m, axis=1)).mean(1), f["s1024"].mean(1) - m.mean(1),
                           ix(env, 40), ix(f["onset"] - f["env"].max(), 20), ix(cent, 20)]).astype(np.float32)


def clap_audio(a):
    mono = a.mean(axis=0)
    mono = resample_poly(mono, 160, 147).astype(np.float32)  # 44.1 to 48 kHz
    return mono / max(np.abs(mono).max(), 1e-6) * 0.5


_w = {}


def _init():
    _w["bank"] = pickle.load(open("bank.pkl", "rb"))


def _one(i):
    rng = np.random.default_rng(1000 + i)
    j = i % len(_w["bank"])
    path = _w["bank"][j][0]
    try:
        tree = s.decode_preset_file(path)[1]
        knobs = [(p, k, v, *o.mapper(k, v)) for p, k, v in o.walk(tree)]
        tree = randomise(tree, knobs, rng) if MODE == "random" else nudge(tree, knobs, rng)
        note = int(rng.integers(28, 77))
        a = r.render_tree(tree, note)
    except Exception:
        return i, None
    if not np.isfinite(a).all() or np.abs(a).max() < 1e-3:
        return i, None
    return i, {"group": j, "note": note, "labels": labels(tree), "own": summary(a), "audio": clap_audio(a)}


class Clap:
    def __init__(self):
        import torch
        from transformers import ClapModel, ClapProcessor
        self.torch, self.dev = torch, "mps" if torch.backends.mps.is_available() else "cpu"
        self.m = ClapModel.from_pretrained("laion/larger_clap_music").eval().to(self.dev)
        self.p = ClapProcessor.from_pretrained("laion/larger_clap_music")

    def __call__(self, audios):
        with self.torch.no_grad():
            i = {k: v.to(self.dev) for k, v in self.p(audio=audios, sampling_rate=48000, return_tensors="pt").items()}
            e = self.m.get_audio_features(**i)
            e = getattr(e, "pooler_output", e)
        return e.float().cpu().numpy()


def data(n):
    DATA.mkdir(parents=True, exist_ok=True)
    clap = Clap()
    todo = [k for k in range(0, n, SHARD) if not (DATA / f"{k:06d}.pkl").exists()]
    crash_file = DATA.parent / "crashers.json"  # bank structures that crashed Serum once: skipped from then on
    crashers = set(json.loads(crash_file.read_text())) if crash_file.exists() else set()
    nb = len(pickle.load(open("bank.pkl", "rb")))
    with get_context("spawn").Pool(8, _init) as pool:
        for k in todo:
            t0, rows, lost = time.time(), [], 0
            # one task per render: a preset that crashes Serum kills its worker and its task, which would hang imap
            jobs = [(i, pool.apply_async(_one, (i,))) for i in range(k, min(k + SHARD, n)) if i % nb not in crashers]
            for i0, job in jobs:
                try:
                    i, row = job.get(timeout=15)
                except Exception:
                    lost += 1; crashers.add(i0 % nb); continue
                if row:
                    rows.append({"i": i, **row})
            for b in range(0, len(rows), 64):
                emb = clap([x["audio"] for x in rows[b : b + 64]])
                for x, e in zip(rows[b : b + 64], emb):
                    x["clap"] = e
                    del x["audio"]
            pickle.dump(rows, open(DATA / f"{k:06d}.pkl", "wb"))
            crash_file.write_text(json.dumps(sorted(crashers)))
            print(json.dumps({"shard": k, "kept": len(rows), "lost": lost, "secs": round(time.time() - t0)}), flush=True)


def load(n):
    rows = []
    for f in sorted(DATA.glob("*.pkl")):
        rows += [x for x in pickle.load(open(f, "rb")) if x["i"] < n]
    return sorted(rows, key=lambda x: x["i"])


def questions(rows, min_groups=20):
    """The yes/no and pick-one questions, each kept only if enough structures answer it both ways."""
    qs = {"osc": "multi", "sub": "bin", "noise": "bin", "unison": "multi", "filter": "multi"}
    per = {}
    for x in rows:
        L = x["labels"]
        for key, pre in (("fx", "fx:"), ("routes", "route:"), ("families", "family:")):
            for v in L[key]:
                per.setdefault(pre + v, set()).add(x["group"])
    groups = len({x["group"] for x in rows})
    for q, g in per.items():
        if min_groups <= len(g) <= groups - min_groups:
            qs[q] = "bin"
    return qs


def answer(L, q):
    if ":" not in q:
        return L[q]
    pre, v = q.split(":", 1)
    return int(v in L[{"fx": "fx", "route": "routes", "family": "families"}[pre]])


def fit(X, y, kind):
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    return make_pipeline(StandardScaler(), LogisticRegression(C=0.1, max_iter=2000, class_weight="balanced")).fit(X, y)


def ear(ns):
    from sklearn.metrics import balanced_accuracy_score
    from sklearn.model_selection import GroupKFold
    for n in ns:
        rows = load(n)
        qs = questions(rows)
        g = np.array([x["group"] for x in rows])
        feats = {"clap": np.stack([x["clap"] for x in rows]), "own": np.stack([x["own"] for x in rows])}
        feats["both"] = np.hstack([feats["clap"], feats["own"]])
        out = {"renders": len(rows), "structures": len(set(g))}
        for q, kind in qs.items():
            y = np.array([answer(x["labels"], q) for x in rows])
            if len(set(y)) < 2:
                continue
            res = {}
            for name, X in feats.items():
                pred = np.empty(len(y), dtype=y.dtype)
                for tr, te in GroupKFold(5).split(X, y, g):
                    if len(set(y[tr])) < 2:
                        pred[te] = y[tr][0]; continue
                    pred[te] = fit(X[tr], y[tr], kind).predict(X[te])
                res[name] = round(balanced_accuracy_score(y, pred), 3)
            base = Counter(y.tolist()).most_common(1)[0][1] / len(y)
            out[q] = {**res, "share_of_commonest": round(base, 2)}
            print(json.dumps({"mode": MODE, "n": n, "q": q, **out[q]}), flush=True)
        Path(f"guess/ear_{n}" + ("" if MODE == "random" else f"_{MODE}") + ".json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "data":
        data(int(sys.argv[2]))
    elif cmd == "ear":
        ear([int(v) for v in sys.argv[2:]])

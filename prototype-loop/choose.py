"""PROTOTYPE, throw away. "Can trained guessers pick a structure the tuner can finish from?": from guesses to a preset.

  python choose.py guesses N            train every guesser on the first N renders, guess the 6 targets, print the guesses
                                        next to the truth (truth only to report)
  python choose.py tune WAY BUDGET N    WAY: match (rank the bank's real structures by fit to the guesses) or
                                        build (write the guessed parts into a blank preset). Top 3 to the tuner,
                                        BUDGET renders across the 3, the best wins.
"""
import copy, csv, json, pickle, sys, time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import pick  # before retrieve, which puts testset/ (with its own pick.py) first on the path
import bank as bk
import guess as g
import loop
import oracle as o
import patch
import render as r
import retrieve as rv
import serum2_preset_loader as s
import tune as t

SOUNDS = ["Bass 1", "Bass 2", "Lead 1", "Lead 4", "Synth 1", "Synth 4"]
UNI_VOICES = [1, 3, 5, 9]  # one representative voice count per unison bucket
patch.BASE = "base.pkl"


def feature_choice(n):
    """Per question, the feature set that did best on held-out structures."""
    ear = json.loads(Path(f"guess/ear_{n}.json").read_text())
    return {q: max(("clap", "own", "both"), key=lambda k: v[k]) for q, v in ear.items() if isinstance(v, dict)}


def train(n):
    rows = g.load(n)
    choice = feature_choice(n)
    X = {"clap": np.stack([x["clap"] for x in rows]), "own": np.stack([x["own"] for x in rows])}
    X["both"] = np.hstack([X["clap"], X["own"]])
    models = {}
    for q, kind in g.questions(rows).items():
        if q not in choice:
            continue
        y = np.array([g.answer(x["labels"], q) for x in rows])
        models[q] = (choice[q], g.fit(X[choice[q]], y, kind))
    tables = (X["clap"] / np.linalg.norm(X["clap"], axis=1, keepdims=True), [x["labels"]["tables"] for x in rows])
    return models, tables


def guess_target(models, tables, a, k=50):
    own, clap = g.summary(a), g.Clap()([g.clap_audio(a)])[0]
    feats = {"clap": clap, "own": own, "both": np.concatenate([clap, own])}
    out = {q: dict(zip(m.classes_.tolist(), m.predict_proba(feats[f][None])[0].round(3).tolist())) for q, (f, m) in models.items()}
    E, T = tables
    near = np.argsort(-(E @ (clap / np.linalg.norm(clap))))[:k]
    votes = Counter()
    for rank, i in enumerate(near):
        for tb in T[i]:
            votes[tb] += 1 / (1 + rank)
    out["tables"] = [tb for tb, _ in votes.most_common(6)]
    return out


def loglik(G, L):
    """How well one structure's answers fit the guesses."""
    return sum(np.log(max(p.get(g.answer(L, q), 0.0), 1e-3)) for q, p in G.items() if q != "tables")


# ---- build: the guessed parts written into a blank preset, each part copied from a bank preset that has it

def donors():
    d = defaultdict(dict)
    fx_pos = defaultdict(list)
    for path, _ in pickle.load(open("bank.pkl", "rb")):
        tree = s.decode_preset_file(path)[1]
        for i in range(3):
            n = tree.get(f"Oscillator{i}", {})
            p = n.get("plainParams")
            if isinstance(p, dict) and p.get("kParamEnable", i == 0) and p.get("kParamVolume", 0.75) > 0:
                tb = g.norm_table(n.get(f"WTOsc{i}", {}).get("relativePathToWT", ""))
                d["osc"].setdefault(tb, (i, n))
        for i, key in ((4, "sub"), (3, "noise")):
            n = tree.get(f"Oscillator{i}", {})
            if isinstance(n.get("plainParams"), dict) and n["plainParams"].get("kParamEnable") and n["plainParams"].get("kParamVolume", 0.75) > 0:
                d[key].setdefault(0, n)
        for i in range(2):
            p = tree.get(f"VoiceFilter{i}", {}).get("plainParams")
            if isinstance(p, dict) and p.get("kParamEnable"):
                d["filter"].setdefault(g.filt(p.get("kParamType", "MgL12")), tree[f"VoiceFilter{i}"])
        for rk in ("FXRack0", "FXRack1", "FXRack2"):
            rack = tree.get(rk, {}).get("FX", []) or []
            for j, fx in enumerate(rack):
                name = bk.st.FX.get(fx["type"], str(fx["type"]))
                d["fx"].setdefault(name, fx)
                fx_pos[name].append(j / max(len(rack) - 1, 1))
        for k, v in tree.items():
            if k.startswith("ModSlot") and isinstance(v, dict) and v.get("source") and v.get("destModuleTypeString"):
                kind = g.SRC_KIND.get(v["source"][0])
                if kind and not v["destModuleTypeString"].startswith("FX"):  # FX destinations index the rack in ways not yet worked out
                    d["slot"].setdefault(f"{kind}>{v['destModuleTypeString']}.{v['destModuleParamName'].removeprefix('kParam')}", v)
        for node in ("Env0", "Env1", "LFO0"):
            p = tree.get(node, {}).get("plainParams")
            if isinstance(p, dict) and len(p) >= 3:
                d["mod"].setdefault(node, tree[node])
    d["fx_order"] = {k: float(np.mean(v)) for k, v in fx_pos.items()}
    return d


def design(G, flip=None):
    """The most likely answer to every question; flip: one question to take its second answer on."""
    def pickq(q):
        ranked = sorted(G[q], key=lambda c: -G[q][c])
        return ranked[1] if q == flip and len(ranked) > 1 else ranked[0]
    on = lambda q: q in G and pickq(q) == 1
    fams = [q.split(":", 1)[1] for q in G if q.startswith("family:") and on(q)]
    tabs = [tb for tb in G["tables"] if g.fam(tb) in fams] or G["tables"]
    n = max(int(pickq("osc")), 1)
    if flip == "tables":
        tabs = tabs[1:] + tabs[:1]
    return {"osc": [tabs[i % len(tabs)] for i in range(n)], "unison": int(pickq("unison")), "sub": on("sub"), "noise": on("noise"),
            "filter": pickq("filter"), "fx": sorted(q[3:] for q in G if q.startswith("fx:") and on(q)),
            "routes": sorted(q[6:] for q in G if q.startswith("route:") and on(q))}


def alternatives(G, k=3):
    """The best design, then the designs that flip the least certain questions."""
    margin = {q: (lambda ps: ps[0] - (ps[1] if len(ps) > 1 else 0))(sorted(p.values(), reverse=True)) for q, p in G.items() if q != "tables"}
    margin["tables"] = 0.5  # always worth one try with the next table
    out, seen = [], set()
    for flip in [None] + sorted(margin, key=margin.get):
        d = design(G, flip)
        key = json.dumps(d, sort_keys=True)
        if key not in seen:
            seen.add(key); out.append(d)
        if len(out) == k:
            break
    return out


def build(d, D):
    tree = patch.blank()
    for node in ("Env0", "Env1", "LFO0"):
        if node in D["mod"]:
            tree[node] = copy.deepcopy(D["mod"][node])
    if isinstance(tree["LFO0"].get("plainParams"), dict):
        tree["LFO0"]["plainParams"]["kParamBeatSync"] = 0.0
    for j, tb in enumerate(d["osc"]):
        i, n = D["osc"].get(tb) or D["osc"]["Default Shapes.wav"]
        n = copy.deepcopy(n)
        n[f"WTOsc{j}"] = n.pop(f"WTOsc{i}")
        p = patch.pp(n)
        p.update(kParamEnable=1.0, kParamUnison=float(UNI_VOICES[d["unison"]]))
        p.setdefault("kParamVolume", 0.7)
        if d["unison"]:
            p.setdefault("kParamDetune", 0.1)
        tree[f"Oscillator{j}"] = n
    for key, i in (("sub", 4), ("noise", 3)):
        if d[key] and 0 in D[key]:
            tree[f"Oscillator{i}"] = copy.deepcopy(D[key][0])
    f = d["filter"] if d["filter"] in D["filter"] else None
    if f and f != "none":
        tree["VoiceFilter0"] = copy.deepcopy(D["filter"][f])
    tree["FXRack0"]["FX"] = [copy.deepcopy(D["fx"][x]) for x in sorted(d["fx"], key=lambda x: D["fx_order"].get(x, 0.5)) if x in D["fx"]]
    slot = 0
    for rt in d["routes"]:
        if rt not in D["slot"]:
            continue
        v = D["slot"][rt]
        kind = rt.split(">")[0]
        src = {"Env1": 2, "Env": 3, "LFO": 6}[kind]  # every Env route shares Env 2, every LFO route LFO 1
        mods = range(len(d["osc"])) if v["destModuleTypeString"] in ("Oscillator", "WTOsc") else [0]
        for m in mods:
            tree[f"ModSlot{slot}"] = {**copy.deepcopy(v), "destModuleID": m, "source": [src, 0]}
            slot += 1
    return tree


def report_truth(label, G):
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    L = g.labels(s.decode_preset_file(paths[label])[1])
    right = {q: max(p, key=p.get) == g.answer(L, q) for q, p in G.items() if q != "tables"}
    return {"right": sum(right.values()), "of": len(right), "wrong": sorted(q for q, v in right.items() if not v),
            "true_tables": L["tables"], "guessed_tables": G["tables"][:3]}


def targets():
    paths = dict(csv.reader(open("paths.tsv"), delimiter="\t"))
    for label in SOUNDS:
        note = o.NOTES[label.split()[0]]
        yield label, note, r.render_tree(s.decode_preset_file(paths[label])[1], note)


def guesses(n):
    models, tables = train(n)
    out = {}
    for label, note, a in targets():
        out[label] = guess_target(models, tables, a)
        print(json.dumps({"sound": label, **report_truth(label, out[label])}), flush=True)
    Path(f"guess/guesses_{n}.json").write_text(json.dumps(out, indent=1))


def tune(way, budget, n):
    G_all = json.loads(Path(f"guess/guesses_{n}.json").read_text())
    pick.OUT.mkdir(exist_ok=True)
    if way == "match":
        bank = [(p, g.labels(s.decode_preset_file(p)[1])) for p, _ in pickle.load(open("bank.pkl", "rb"))]
    else:
        D = donors()
    for label, note, target in targets():
        tag = f"{label.replace(' ', '')}_{way}"
        if (pick.OUT / f"{tag}.json").exists():
            continue
        G, feats = G_all[label], t.features(target)
        if way == "match":
            top = sorted(bank, key=lambda b: -loglik(G, b[1]))[:3]
            cands = [(Path(p).stem, s.decode_preset_file(p)[1]) for p, _ in top]
        else:
            cands = [(json.dumps(d), build(d, D)) for d in alternatives(G)]
        rng, t0, best, tried = np.random.default_rng(1), time.time(), None, []
        for name, tree in cands:
            tree = bk.align(tree, note, target)
            tree = rv.level_up(tree, r.render_tree(tree, note), target)
            own = lambda kn: [[o.to_unit(v, lo, hi, lg) for _, _, v, lo, hi, lg in kn]]
            S, knobs = pick.run(tree, note, feats, own, budget // len(cands), rng)
            tried.append({"from": name, "knobs": len(knobs), "score": round(S.best, 3)})
            print(json.dumps({"sound": label, "way": way, **tried[-1]}), flush=True)
            if best is None or S.best < best[0].best:
                best = (S, knobs, tree, name)
        S, knobs, tree, name = best
        S.used = budget
        pick.save(tag, {"sound": label, "arm": way, "picked": name, "tried": tried, "secs": round(time.time() - t0)},
                  tree, knobs, S, note, target, feats)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "guesses":
        guesses(int(sys.argv[2]))
    elif cmd == "tune":
        tune(sys.argv[2], int(sys.argv[3]), int(sys.argv[4]))

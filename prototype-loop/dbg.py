"""PROTOTYPE, throw away. Pieces on the cached 12 test renders, next to the truth."""
import json, pickle, parts as P
lib = P.load_lib()
rows = []
for x, (a, note, tree) in pickle.load(open("parts/test_audio.pkl", "rb")).items():
    p, t = P.read(a, note, lib[:3], lib[3]), P.truth(tree)
    rows.append((x, p, t)); print(json.dumps(P.side(x, p, t)))
print(json.dumps(P.score(rows)))

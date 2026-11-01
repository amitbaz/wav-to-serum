"""PROTOTYPE, throw away. Does the rebuilt gap reproduce the published Mac-against-DawDreamer table?"""
import csv, json, sys
from pathlib import Path

import numpy as np

import compare as c
import render as r

SCRATCH = Path(sys.argv[1])
kinds = {p["label"]: p["kind"] for p in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}
paths = dict(csv.reader(open(SCRATCH / "paths.tsv"), delimiter="\t"))
PUBLISHED = {"Lead 2": 4.28, "Lead 3": 0.80, "Synth 2": 0.88, "Synth 3": 0.57, "Bass 3": 0.01, "Lead 4": 0.00}

if __name__ == "__main__":
    print("published", PUBLISHED)
    for n_fft, hop in [(1024, 256), (2048, 512), (4096, 1024), (2048, 256)]:
        row = {}
        for label in PUBLISHED:
            mac = r.render_file(paths[label], r.NOTES[kinds[label]])
            daw = np.load(SCRATCH / "routes" / f"{label.replace(' ', '_')}.daw.npy")
            row[label] = round(c.gap(mac, daw, n_fft, hop), 2)
            if n_fft == 2048 and hop == 512:
                np.save(SCRATCH / "routes" / f"{label.replace(' ', '_')}.mac.npy", mac)
        print(n_fft, hop, row)

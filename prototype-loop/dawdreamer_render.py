"""PROTOTYPE, throw away. Maintainer-only check, run in its own venv: render through DawDreamer.

The recipe from "Compare renders with Serum in a DAW". Output stays in the scratchpad.
Sealed presets are never read: paths.tsv only holds test entries.
"""
import csv, json, sys, tempfile
from pathlib import Path

import dawdreamer as daw
import numpy as np
import serum2_preset_loader as s

SCRATCH, labels = Path(sys.argv[1]), sys.argv[2:]
kinds = {p["label"]: p["kind"] for p in json.load(open(Path(__file__).parents[1] / "testset/testset.json"))["presets"]}
NOTES = {"bass": 36, "synth": 48, "lead": 60}
paths = dict(csv.reader(open(SCRATCH / "paths.tsv"), delimiter="\t"))
out = SCRATCH / "routes"
out.mkdir(exist_ok=True)

for label in labels:
    state = Path(tempfile.mktemp(suffix=".state"))
    state.write_bytes(s.convert_preset_file(paths[label]))
    engine = daw.RenderEngine(44100, 512)
    synth = engine.make_plugin_processor("s", "/Library/Audio/Plug-Ins/VST3/Serum2.vst3")
    engine.load_graph([(synth, [])])
    synth.load_state(str(state))
    synth.add_midi_note(NOTES[kinds[label]], 100, 1.0, 2.0)
    engine.render(4.0)
    audio = engine.get_audio()[:, 44100:44100 + 132300].astype(np.float32)
    np.save(out / f"{label.replace(' ', '_')}.daw.npy", audio)
    print(label, float(abs(audio).max()))
    state.unlink()

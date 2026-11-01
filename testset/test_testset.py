"""Run with: python3 testset/test_testset.py"""
import hashlib, json, re, sys, tempfile
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from find import MANIFEST, find


def test_manifest_matches_the_plan():
    manifest = json.loads(MANIFEST.read_text())
    presets = manifest["presets"]
    assert Counter((p["set"], p["kind"], p["level"]) for p in presets) == {
        ("test", "bass", "Easy"): 1, ("test", "bass", "Medium"): 3,
        ("test", "lead", "Easy"): 1, ("test", "lead", "Medium"): 3,
        ("test", "synth", "Easy"): 1, ("test", "synth", "Medium"): 3,
        ("sealed", "bass", "Easy"): 1, ("sealed", "bass", "Medium"): 3,
        ("sealed", "lead", "Easy"): 1, ("sealed", "lead", "Medium"): 3,
        ("sealed", "synth", "Medium"): 2,
    }
    assert all(re.fullmatch("[0-9a-f]{64}", p["sha256"]) for p in presets)
    assert len({p["sha256"] for p in presets}) == 22
    assert len({p["label"] for p in presets}) == 22


def test_manifest_holds_no_names():
    allowed = {"label", "set", "kind", "level", "sha256"}
    assert all(set(p) == allowed for p in json.loads(MANIFEST.read_text())["presets"])


def test_find_matches_by_content_not_name():
    with tempfile.TemporaryDirectory() as d:
        wanted, other = Path(d, "renamed.SerumPreset"), Path(d, "other.SerumPreset")
        wanted.write_bytes(b"a"), other.write_bytes(b"b")
        digest = hashlib.sha256(b"a").hexdigest()
        assert find([{"sha256": digest, "label": "Bass 1"}], [wanted, other]) == {"Bass 1": wanted}


if __name__ == "__main__":
    for name, test in list(globals().items()):
        if name.startswith("test_"):
            test()
    print("ok")

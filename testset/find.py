"""Find the presets in testset.json on this Mac, by file hash.

Prints each test preset's label and path. Sealed presets stay out unless you
pass --sealed, which is only for the one run after the tool is frozen.
"""
import hashlib, json, subprocess, sys
from pathlib import Path

MANIFEST = Path(__file__).with_name("testset.json")


def find(presets, paths):
    """Return {label: path} for every preset whose sha256 matches one of the paths."""
    labels = {p["sha256"]: p["label"] for p in presets}
    found = {}
    for path in paths:
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if digest in labels:
            found[labels[digest]] = path
    return found


def main():
    sealed = "--sealed" in sys.argv
    presets = [p for p in json.loads(MANIFEST.read_text())["presets"] if sealed or p["set"] == "test"]
    found_paths = subprocess.run(["mdfind", 'kMDItemFSName == "*.SerumPreset"'], capture_output=True, text=True).stdout
    found = find(presets, filter(None, found_paths.split("\n")))
    for preset in presets:
        print(f'{preset["label"]}\t{found.get(preset["label"], "not on this Mac")}')


if __name__ == "__main__":
    main()

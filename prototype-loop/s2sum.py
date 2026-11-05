"""PROTOTYPE, throw away. One line per matched sound in a Step 2 results folder."""
import glob, json, sys
d = sys.argv[1] if len(sys.argv) > 1 else "step2"
for f in sorted(glob.glob(f"{d}/*_match.json")):
    r = json.load(open(f)); tf = r["truth"].get("filter"); pf = r["picked_filter"]
    print(r["sound"], r["split"][:4], r["score_final"], "| table", "true" if r["picked"] == r["truth"]["table"] else f"{r['truth']['table'][:22]} -> {r['picked'][:22]}",
          "| type", (tf["type"] if tf else "-"), "->", pf["type"], f"(slope said {r.get('slope_type')})", "|", r["secs"], "s")

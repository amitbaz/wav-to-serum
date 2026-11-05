"""PROTOTYPE, throw away. One line per matched sound in a Step 3 results folder."""
import glob, json, sys
d = sys.argv[1] if len(sys.argv) > 1 else "step3"
n = ok = below = 0
for f in sorted(glob.glob(f"{d}/*_match.json")):
    r = json.load(open(f)); tf = r["truth"].get("filter"); pf = r["picked_filter"]
    n += 1; below += r["score_final"] < 2.5; ok += r["filter_right"]
    print(r["sound"], r["split"][:4], r["score_final"], "| filter", tf["type"] if tf else "off", "->", pf["type"] if pf else "off", "RIGHT" if r["filter_right"] else "WRONG",
          "| table", "true" if r["picked"] == r["truth"]["table"] else "other", "| screen", [(x["filter"]["type"] if x["filter"] else "off", x["score"]) for x in r["tried"]], r["secs"], "s")
print(f"below 2.5: {below} of {n}; filter right: {ok} of {n}")

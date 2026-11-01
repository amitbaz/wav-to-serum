# Prototype plan: fixed before any test sound was tuned

Throwaway. Answers "Prove the whole loop on a few simple sounds".

## Sounds

Fixed by rule, not by ear: all three Easy sounds, plus the first Medium of each kind that both render
routes agree on: **Bass 1, Lead 1, Synth 1, Bass 2, Lead 4, Synth 4**. No sealed preset is touched.
Lead 2, Lead 3, Synth 2 and Synth 3 are only used for the render route check.

## Arms

Both get the same analyser, the same table ranking, the same tuner and the same budget: 5 tunings of
1,500 evaluations each, in rounds of 1, 2 and 2.

- **Rules**: fixed thresholds in `rules.py`.
- **Designer**: a language model that sees the analysis, candidates and the comparison after each
  round, and picks the designs. It gets anonymous sound ids, no preset names and no hidden notes. It
  never sets knobs.

## Measures

All three use the **near gap**: the gap from "Compare renders with Serum in a DAW", limited to bins within
30 dB of the loudest. Changed from the full gap before any test sound was tuned. On synthetic patches
with the true design, 85 to 94% of the full gap came from bins 40 to 60 dB down, so the full gap read 20
on a sound whose top 30 dB matched to 0.46. The full gap stays for proving two renders are the same.

- **Start**: near gap of the first guess, before tuning.
- **Wrong sound**: median near gap between the target and the other 11 test presets on the same note.
- **Final**: near gap after the loop. The tuner searches a separate score, so it can't be gamed
  directly.
- **Seeds**: each arm's final design is retuned with 3 seeds. The reported value is the median.
- **Ears**: the maintainer rates target against result, 1 to 5, blind to the arm. 3 means recognisably
  similar, which is where the best published systems land.

## Run 2

Run 1 finished before anyone listened, and is archived. All three designers who looked at it said the score
barely moved, and it missed faults a person would hear. Tested on the targets themselves: 48 to 99% of its
cells were silent in both sounds, and a 0.25 s attack added to a perfect match cost only 0.16 to 0.39. The
tuner's score now counts only cells with sound, and has an onset term. The pass rules below did not change.
The designer also gets tuned knob values and the score by part, which run 1's designers all asked for.

## Does the loop get clearly closer?

A sound passes when Final is at most half of the smaller of Start and Wrong sound, the worst seed
still beats Start, and the ears give it 3 or more.

- **4 or more of 6, with at least one Medium**: the loop works.
- **3 of 6**: the maintainer decides.
- **2 or fewer**: stop and rethink before anything is built.

## Does a language model add anything?

Matching: a sound counts for an arm only when the two medians differ by more than the larger of the two
seed spreads. The designer adds matching if it wins at least 4 of 6 and loses at most 1.

Readability and following requests are recorded, not scored by a threshold:

- **Readability**: modules on that do nothing audible, and the maintainer's read of the explanation.
- **Requests**: on two sounds, a producer's request is added. Record whether it was followed, and
  what it cost in gap.

If the designer adds nothing on any of the three, the first release is the CLI alone, as the map says.

## Also recorded

The full gap, render speed, hidden note near gaps (octave down, octave up, soft) and whether the written `.SerumPreset`
opens in Serum 2.

## Ordering

The four Ableton bounces and the route check come before any tuning on a test sound.

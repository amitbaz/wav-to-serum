# Glossary

wav-to-serum is for a producer who finds a synth sound they like in a WAV and wants it as a Serum 2 preset for their own production, without reverse engineering it by hand. They can trust it to do a good job: the result is a real, playable preset they can open, understand and tweak.

## Language

### The sound

**Target**:
The WAV the user wants recreated. It never goes into the preset.
_Avoid_: Reference, source

**Render**:
A WAV made by playing a preset through Serum.
_Avoid_: Bounce, output

**Known preset**:
An existing preset used as a test case, so the true settings and the true sound on every note are known.
_Avoid_: Ground truth

**Heard note**:
The one note of a target that the tool is given to match. Every other note is hidden from it.

**Test set**:
The known presets the tool is built against and judged on while it is being made.

**Sealed set**:
Known presets nobody hears or scores until the tool is frozen for release, then run once. Published scores come from this run.
_Avoid_: Held-out set

### The preset

**Knob**:
A setting with a clear minimum and maximum, such as cutoff or attack.
_Avoid_: Continuous parameter

**Choice**:
A setting with no scale between its options, such as a waveform or a filter type.
_Avoid_: Discrete parameter, categorical parameter

**Candidate**:
One ranked option for a choice, offered with the evidence for it.

### The four tests

**Sounds right**:
The preset matches the target on the note heard.

**Plays right**:
The preset behaves like a synth across the keyboard.

**Reads right**:
The preset is built the way a producer would build it, with nothing messy or unused.

**Works in a track**:
The preset can be used in a real production: sensible levels, no clicks or clipping, reasonable CPU use, and steady behaviour on sustained and repeated notes.

### Trust

**Match report**:
What the tool tells the producer about a result: how close it came, and where it fell short.

### The pipeline

**Piece**:
One thin, separately tested step, such as the analyser or the tuner. Pieces never call each other.

**Job record**:
The shared record of one run. Each piece reads what it needs from it and adds only its own result.
_Avoid_: Context, state

**Designer**:
The role that makes choices, shapes the preset and explains it. A language model fills it.
_Avoid_: Agent, orchestrator

**Tuner**:
The piece that searches for the best knob values. It sees only numbers and a score.
_Avoid_: Optimizer

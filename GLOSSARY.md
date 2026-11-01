# Glossary

wav-to-serum turns a WAV of a synthesized sound into a real, playable Serum 2 preset that a producer could open, understand and tweak.

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

### The preset

**Knob**:
A setting with a clear minimum and maximum, such as cutoff or attack.
_Avoid_: Continuous parameter

**Choice**:
A setting with no scale between its options, such as a waveform or a filter type.
_Avoid_: Discrete parameter, categorical parameter

**Candidate**:
One ranked option for a choice, offered with the evidence for it.

### The three tests

**Sounds right**:
The preset matches the target on the note heard.

**Plays right**:
The preset behaves like a synth across the keyboard.

**Reads right**:
The preset is built the way a producer would build it, with nothing messy or unused.

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

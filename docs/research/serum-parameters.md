# What a Serum 2 preset consists of, and what is hard to infer from audio

Research date: 2026-11-01. Nothing here assumes any recreation approach works.

## Evidence tags

| Tag | Meaning |
|---|---|
| **[V-Xfer]** | Verified: stated in an Xfer document I read. |
| **[V-local]** | Verified: seen on this Mac from file names, counts or plist metadata. Preset contents were not decoded. |
| **[V-3p]** | Verified that a third-party source says it, in code or docs I read. I did not test it. It remains that project's reverse-engineering claim. |
| **[I]** | Inferred by me from the sources. |
| **[U]** | Unverified, or sources conflict. |

Page numbers `p.N` refer to the Serum 2 User Guide PDF ([S1](#sources)). It covers Serum 2.0.18, manual 1.0.3.

## Main findings

1. **A preset is a tree of about 175 top-level keys, not a flat knob list.** The loader's test preset is about 8 KB of CBOR, and a sample-heavy preset file reached 160 MB. [V-3p]
2. **About 400 host parameters out of 2,622 are the instrument.** 2,048 of the rest are MIDI CC channel slots and 128 are mod-matrix automation. FX settings are not directly exposed to the host, only through 48 proxy slots. [V-3p, count by me]
3. **Discrete choices dominate the search space.** There are 5 oscillator types, about 100 filter types, about 70 warp modes (88 on spectral), 288 factory wavetables, 16 FX types in any order, and 64 mod slots. [V-Xfer, V-local, V-3p; counts below]
4. **Much of a preset cannot be heard in one rendered note.** That covers velocity, key tracking, macros, mod wheel, voicing, portamento and unused clips. [I]
5. **The format can be read and written, but it is undocumented and version-dependent.** Serum loads edited files, the tools have only partial semantics, and bad values can crash the host. [V-3p]
6. **The EULA copy I found prohibits reverse engineering in general terms.** Its text says nothing specific about preset files or automation. The copy is old and comes from a distributor. Section 8 quotes it without interpretation.

---

## 1. Signal structure

Oscillators A, B, C, plus SUB and NOISE, feed Filter 1, Filter 2, Main, Direct or None. Each source can also send to Bus 1 and Bus 2. The Main, Bus 1 and Bus 2 FX racks then feed the output. [V-Xfer p.31-32, p.145-151]

Defaults: OSC A routes through Filter 1, and the others route to Main. Filter 1 is not enabled in new presets. [V-Xfer p.31]

Filters can run in series or in parallel. [V-Xfer What's New p.10]

---

## 2. Parameter families

Kind key: **C** continuous, **D** discrete list, **F** file reference, **S** structural.

### 2.1 Oscillators A, B, C

Mode selector, **D**, 5 values: Wavetable, Multisample, Sample, Granular, Spectral. [V-Xfer p.17]

Stored as `Oscillator{i}.plainParams.kParamType`, values `kOsc_WT`, `kOsc_Sample`, `kOsc_Granular`, `kOsc_MultiSample`, `kOsc_Spectral`. An absent key means WT. [V-3p serum-mcp §8]

| Control group | Kind | Detail | Tag |
|---|---|---|---|
| Enable, level, pan | C, boolean | Level 0..1, pan -50..50 stored | V-3p schema |
| Octave, semi, fine, coarse | C or stepped | Octave ±4, pitch ±12, fine ±80 cents, coarse ±72 semitones (continuous) | V-3p schema, V-Xfer p.30 |
| Tuning mode | D, 3 or 4 | Semitones, Harmonics, Ratio, Step (Step needs MTS-ESP) | V-Xfer p.30 |
| Pitch track | Boolean | | V-3p |
| Unison voices | Stepped | 1 to 16 | V-Xfer p.45 |
| Unison detune mode | D, 5 | Linear, Super, Exp, Inv, Random | V-Xfer p.46-47 |
| Unison stack | D, 9 entries | Off, 12 (1-3x), 12+7 (1-3x), Center-12, Center-24 | V-Xfer p.47; count 9 is I from that list, and serum2vital reports 9 for Serum 1 |
| Unison width, range, detune, blend | C | Blend default 75% | V-Xfer p.47-48 |
| Unison WT pos, warp 1, warp 2 spread | C | Sample modes have start and span instead of WT pos | V-Xfer p.48, p.83 |
| Warp 1 and 2 | D + C each | See 2.2 | V-Xfer p.49 |
| Warp var | C | Shown for Sync (soft sync amount) | V-Xfer p.50 |
| Phase, random phase | C | 0-360°, 0-100%. WT default 180° and 100% | V-3p loader |
| Phase memory | D, 3 | All Voices, Contiguous, Per Voice | V-Xfer p.44 |
| Filter routing and balance, Bus 1 and 2 send | D + C | See 2.8 | V-Xfer p.31-32 |

#### Mode-specific controls

| Mode | Source reference | Own controls | Tag |
|---|---|---|---|
| Wavetable | Table file or embedded data | WT pos, smooth interpolation option | V-Xfer p.45 |
| Multisample | SFZ instrument | Envelope override with delay and AHDSR, velocity track, random, timbre -64..64 | V-Xfer p.61-63; V-3p loader |
| Sample | Audio file | Start, end, scan (±200, 400 or 800%), reverse, 5 loop modes plus 3 loop options, loop points, crossfade, slicing | V-Xfer p.72-83 |
| Granular | Audio file | Density (3 modes), length (3 modes), window amount, skew and shape, 6 per-grain randoms, X/Y target, max grains | V-Xfer p.91-102 |
| Spectral | Audio file | Scan, cut, drawn or wavetable spectral filter, mix, freq low and high, phase lock, transients | V-Xfer p.116-121 |

Window shapes: the manual lists 9 and the format list has 10, because `kWindowExpDecRev` is extra. [V-Xfer p.91-92, V-3p schema]

Maximum grains conflict: "up to 256 grains" [V-Xfer What's New p.9] against a schema bound of 64 marked uncertain. [V-3p]

Parameter counts in `schema.py`: Oscillator 17, WTOsc 7, Sample 5, Granular 34, Spectral 15, MultiSample 17. These are the ones serum-mcp models, not proven totals. [V-3p]

### 2.2 Warp modes, D + C, two lanes per oscillator

| Category | Modes | Count |
|---|---|---|
| Off | Off | 1 |
| Sync | Sync | 1 |
| Alt warp | Bend + / - / +-, PWM, Asym + / - / +-, Flip, Mirror, Remap 1-4, Quantize, Odd/Even | 15 |
| Filter | LPF, HPF | 2 |
| Distortion | Tube, Soft Clip, Hard Clip, Diode 1, Diode 2, Linear Fold, Sine Fold, Zero-Square, Asym, Rectify, Sine Shaper, Stomp Box, Tape Sat, Soft Sat | 14 |
| FM | Thru-Zero, Exp, Linear, each from 6 sources | 18 |
| PD | 6 sources plus Self | 7 |
| AM | 6 sources | 6 |
| RM | 6 sources | 6 |

- The mode names are [V-Xfer p.50-56].
- The total of **70** is [I]. It is my count from that table, and it matches the format lists: `kFM_*`, `kFMX_*`, `kFMP_*` give 18.
- serum-mcp's WT enum has only 53 observed values, so it is incomplete. [V-3p]
- FM, PD, AM and RM modes need another module enabled, even if it is turned down. [V-Xfer p.54-56] An oscillator's timbre can therefore depend on a different module's enable state. [V-3p §4]
- **Spectral warp list: 88 values.** 35 are spectral-only (no-warp, Detune, Smear, Robotize, Peak and Shepard families, 6 Mask, 6 Vocode) and 53 are general. [V-3p `_SPECTRAL_WARP_MODES`] The manual points to the common table only. [V-Xfer p.121] The extracted text of both Xfer PDFs has no Mask or Vocode warp, so Xfer confirmation of those modes is missing. [U]

### 2.3 Sub and noise

**Sub** [V-Xfer p.124-127]: waveform **D**, 6 listed in the manual (Sine, Rounded Rect, Triangle, Saw, Square, Pulse). Octave, coarse, phase, pan and level are **C**.

The format enum `kParamShape` has 5 observed values without Sine, which is presumably the default. [V-3p, I]

**Noise** [V-Xfer p.128-132]: the module is a stereo sample player.

| Control | Kind | Detail |
|---|---|---|
| Sample | F | 217 factory noise files on this install [V-local] |
| Colour | D, 4 | White, Pink, Brown, Geiger, with Stereo and Filter controls |
| One-shot or loop | Boolean | |
| Start, random, pitch, fine, pan, level | C | |

### 2.4 Filters, two modules

| Item | Kind | Detail | Tag |
|---|---|---|---|
| Type | D | See counts below | |
| Cutoff | C | Stored 0..1. 0.5 shows 425 Hz, 0.25 gives about 59 Hz | V-3p |
| Res, drive, var, pan, mix, level | C | Clean Mode is a separate option on drive | V-Xfer p.142-143 |
| Keytrack | Boolean | | V-Xfer p.141 |
| Source switches | Boolean, 5 | S, A, B, C, N | V-Xfer p.134 |
| PZ SVF curve | F or S | Factory filter files plus a drawn filter | V-Xfer p.139, V-local |

**The type count is unsettled.** [U]

| Evidence | Count |
|---|---|
| Rows in the manual's table, expanded by me | About 80 [I] |
| `schema.py` enum, accumulated from real presets | 97 [V-3p] |
| Serum 1 current builds | 96 [V-3p serum2vital] |
| Host default `MG Low 12` stored as 0.009434, or 1/106, if index 1 of an even grid | **107** [I] |

The VAR knob changes meaning per type, for example Fat, Freq, Morph, Damp, Boeuf, Width, Scream, Pain. [V-Xfer p.135-139] On comb filters it can be a primary timbre control. [V-3p §4]

### 2.5 Envelopes, 4

ENV 1 is the amp envelope and is always active. [V-Xfer p.185-186]

Controls are ATK, HOLD, DEC, SUS, REL, plus attack, decay and release curves, all **C**. Curve shape is mouse-only in the GUI but stored as `kParamCurve1..3`. [V-Xfer p.186, V-3p]

Stored bounds: attack up to 10 s, hold up to 5.2 s, decay and release up to 32 s, sustain 0..1. [V-3p schema] Those bounds were corrected after real files exceeded earlier values, so they are observed rather than guaranteed. [V-3p]

Also: MS or BPM timing and Legato Inverted. [V-Xfer p.185]

### 2.6 LFOs, 10

[V-Xfer p.188-193]

| Control | Kind | Detail |
|---|---|---|
| Type | D, 5 | Normal, Path, Chaos Lorenz, Chaos Rossler, S&H |
| Mode | D, 3 | Free, Retrig, Envelope |
| Direction | D, 3 | Forward, Reverse, Ping Pong |
| Mono, Host, BPM/Hz, Trip, Dot, 10x | Boolean | |
| Grid | Stepped | Independent X and Y |
| Rate, Rise, Delay, Smooth, Phase | C | |
| Shape | S | Drawn points, or a preset from 38 factory shape files and 14 factory path files [V-local] |

Shape data is `curveData` or `pathData`, with `xVals`, `yVals`, `curveVals`, `numPoints`. [V-3p] Individual LFO points can also be modulated through 16 `LFOPointModBus` modules. [V-Xfer p.198, V-3p]

Chaos LFOs may have a second output: `source` id 40 was read as "LFO 2 Y". [V-3p §6]

### 2.7 Modulation

**Sources and macros** [V-Xfer p.206-211]: 8 macros, which can also be destinations. Velocity and Note curves are user-drawn. Oscillator and filter outputs can be mod sources.

**Matrix: 64 slots.** [V-Xfer p.209]

| Row field | Kind |
|---|---|
| Source, aux source | D. 49 named picker entries plus context-dependent ones [V-3p §6] |
| Destination | D, module + parameter |
| Amount, output scale | C, amount -100..100 |
| Polarity, aux invert, bypass | Boolean |
| Curve in, aux curve | C or S, can be a drawn curve |

Further stored fields exist: delay offset, smooth rise and fall. Their meaning is marked uncertain. [V-3p schema]

Aux combination was reported as `amount * (aux/100)`, or `* (1 - aux/100)` when inverted. [V-3p §5, §6]

Stored row shape, as `ModSlotN`: `source: [id, aux_id]`, `destModuleTypeString`, `destModuleID`, `destModuleParamName`, `destModuleParamID`, `plainParams`, optional `flex`. [V-3p]

FX destinations encode rack in the ID: rack × 100 + position. [V-3p §4] The destination therefore depends on FX order.

### 2.8 Routing and mixer

`RoutingSlot0-4` hold the five oscillators, and `RoutingSlot5-6` the two filters. [V-3p §5 items 11, 15-17]

| Item | Kind | Detail |
|---|---|---|
| Destination | D, 4 | Filter, Main, Direct, None [V-Xfer p.146; ordinals 0-3 V-3p] |
| Filter balance | C | Between Filter 1 and 2 |
| Bus 1 and 2 send | C | |
| ENV 1 gating of Main or Direct route | Boolean | [V-Xfer p.146] `kParamViaEnv1`; always 0 in 49 samples [V-3p] |
| Bus routing, levels, FX bypass | D, C | Bus volumes can exceed 1.0 [V-3p] |

Filters can route to the other filter, which is how series routing is expressed. [V-Xfer p.149]

### 2.9 Effects

**Three racks**: Main, Bus 1, Bus 2, each an ordered list. Duplicates are allowed. [V-Xfer p.152-156]

The manual's body says 13 FX. What's New says 13 effects and 3 splitters, for **16 FX types**, which matches format `type` 0-15. [V-Xfer What's New p.3, V-3p]

The Bode, Chorus and similar chapters are in the manual, p.161-182.

| `type` | Module | Stored parameter table size [V-3p loader] | Notable discrete or structural items |
|---|---|---|---|
| 0 | Distortion | 11 | Mode list, filter off, pre, post; X-Shaper curves |
| 1 | Flanger | 9 | BPM sync |
| 2 | Phaser | 12 | Poles, BPM sync |
| 3 | Chorus | 12 | BPM sync |
| 4 | Delay | 14 | Normal, Ping-Pong, Tap->Delay; High Quality; BPM or MS; Link |
| 5 | Compressor | 35 | Single or Multiband; Limit at max ratio |
| 6 | Reverb | 16 | See below |
| 7 | Equalizer | 10 | 2 bands, each 3 types |
| 8 | Filter | 13 | Full filter type list |
| 9 | Hyper/Dimension | 10 | Voices 1-7, Retrig |
| 10 | Bode | 15 | BPM sync, mono input |
| 11 | Convolve | 12 | **F**: 111 impulse files [V-local]; `relativePathToIR` [V-3p] |
| 12 | Utility | 11 | Polarity, mono bass |
| 13 | Splitter L/H | 7 | **S**: following FX entries belong to bands |
| 14 | Splitter L/M/H | 10 | **S** |
| 15 | Splitter M/S | 6 | **S** |

Those table sizes total 193 parameters. [I, sum]

- **Splitters:** `kParamModuleCount1..3` say how many following entries in the flat list belong to each band. This held on 77 of 77 examples. [V-3p §5 item 5] The manual describes them as nested racks. [V-Xfer p.178]
- **Distortion modes:** manual says 13 [V-Xfer p.167]. What's New adds Overdrive and a DC bias control. `schema.py` lists 17 observed. [V-3p] Serum 1 data gives 16. [V-3p]
- **Reverb types:** manual lists 5: Plate, Hall, Vintage, Nitrous, Basin. [V-Xfer p.175-177] The format list has `kAbyss`, `kHall`, `kSpace`, `kVintage`. The mapping of Nitrous and Basin to Space and Abyss is **[U]**.
- **Nitrous mode**: 5 values, Space, Marble, Rectangle, Hexagon, Box. [V-Xfer p.177]
- **Per-voice note:** FX run after the voices are summed, so per-voice sources behave differently on FX. [V-Xfer p.159]

### 2.10 Global, voice and performance

| Family | Items | Kind | Tag |
|---|---|---|---|
| Voicing | Mono, Legato, Poly count, voice priority (5) | Boolean, stepped, D | V-Xfer p.216-217 |
| Portamento | Time, curve, Always, Scaled | C, boolean | V-Xfer p.218 |
| Pitch | Bend up and down, transpose, tuning A4, tuning file, MTS-ESP | C, F | V-Xfer p.320; V-3p |
| Quality | Draft 1x, High 2x, Ultra 4x; S1 Compatibility; Disable Smoothing | D, boolean | V-Xfer p.319-320 |
| Voice control | Up to 8 steps of per-voice values, random Pan, Detune, Cutoff, Envs, env and LFO scaling | C, S | V-Xfer p.316-318 |
| Keyboard | Key and scale quantizer, swing, oscillator mapping | D, C | V-Xfer p.267-273 |
| Arp | 12 clips, patterns, transpose graphs, many playback settings | S | V-Xfer p.246-263; V-3p |
| Clips | 12 MIDI clip slots with piano-roll note data | S | V-Xfer p.220 |
| MIDI and MPE | CC map, MPE config | S | V-Xfer p.201; V-3p |
| Display | Metadata, GUI state, macro names | Text | V-3p |

### 2.11 Factory content counts on this Mac

Installed Serum 2 is **2.0.20**. [V-local]

| Content | Count | Tag |
|---|---|---|
| Factory presets | 626 | V-local |
| Wavetables | **288**: Analog 42, Digital 56, Spectral 35, Vowel 11, S2 Tables 144 | V-local |
| Multisample instruments | 140 SFZ, 3,977 FLAC | V-local |
| Tonal samples | 211 files | V-local |
| Non-tonal samples | 655 files, including 217 noise files | V-local |
| Impulses | 111 files | V-local |
| Single-FX and rack preset files | 163 and 57 | V-local |
| LFO shapes | 169 `.XferShape` across all uses | V-local |
| PZ filter files | 26 single, 5 multi | V-local |

---

## 3. Where values live in the format

### 3.1 Container

```
b"XferJson\x00"
uint64 LE  JSON metadata length
bytes      JSON metadata
uint32 LE  uncompressed CBOR size
uint32 LE  format version (2)
bytes      zstd frame holding CBOR
```

[V-3p packager, loader]

serum-mcp describes the length as uint32 plus a zero uint32, which is the same bytes for normal sizes. [I]

Metadata and top-level CBOR share `presetName`, `tags` and others. Serum's browser reads the header, and Serum's loader reads the tree. The filename is what the browser displays. `hash` is the MD5 of the compressed CBOR. Whether preset loading checks it is untested, and setState accepted mismatches. [V-3p]

### 3.2 Tree

| Top-level keys | Contents |
|---|---|
| `Oscillator0..4` | A, B, C, Noise, Sub. Nested `WTOsc{i}`, `SampleOsc{i}`, `GranularOsc{i}`, `MultiSampleOsc{i}`, `SpectralOsc{i}`; `NoiseOsc3`; `SubOsc4` |
| `VoiceFilter0,1`, `Env0..3`, `LFO0..9`, `LFOPointModBus0..15` | As named |
| `Macro0..7`, `ModSlot0..63` | Macros, matrix |
| `RoutingSlot0..6`, `Global0`, `VoicePanel0`, `RetriggerState0`, `PitchQuantizer0` | Routing and global |
| `FXRack0..2` | Each has `FX`, an ordered list of `{type, FX<Name>...}` |
| `Arp0`, `ArpClip0..11`, `MidiClip0..11`, `ClipPlayer*` | Sequencing |
| `SerumGUI`, `Filter`, `Osc`, `WTOsc`, `GranularOsc`, `MultiSampleOsc`, `SpectralOsc` | UI or template state |
| `scalars`, `mpe*`, `lock*`, metadata keys | Misc |

An init preset from PySerum has 175 top-level keys. I read that from the repo's JSON. [V-3p] The loader reports 175 preset keys against 163 processor-state keys. [V-3p]

### 3.3 Value rules [V-3p]

- `plainParams` is the string `"default"` or a map of **only non-default** values. A consumer needs its own defaults table.
- Values are in stored units, often seconds, Hz or percent, and sometimes text such as `MgL6`. They are not uniformly 0..1.
- Each oscillator keeps a submodule for every type. Only the one selected by `kParamType` has effect.
- Booleans and integers inside `plainParams` must be CBOR floats. Native CBOR booleans crashed Serum in FL Studio.
- Outside `plainParams`, some fields are native integers or booleans.
- **Absent is not always the same as default-valued.** serum-mcp reports writing `kParamWet = 100` sounds different from leaving it out, for four filter fields as well. The mechanism is a guess in that source.
- `flex` curves sit on LFOs, mod routes, FX units and `WTOsc`. Flat `plainParams` comparison misses them.

### 3.4 Wavetables and other files

**Reference form:** sibling fields of `plainParams` in `WTOsc{i}`. [V-3p, seen in PySerum's init JSON]

```
relativePathToWT: "S2 Tables/Default Shapes.wav"
numFrames: 18432      (total samples, 9 × 2048) [I]
sampleRate: 44100
numChannels: 1
```

Those metadata must match the file, or Serum may misread it. [V-3p]

Other references: `samplePathRelative`, `relativePathToNoiseSample`, `relativePathToIR`, `sfzPathRelative`. [V-3p]

Example: `Organics/AC hum1.wav` resolves under `Samples/Factory Non-Tonal/Noises/`. [V-local for the file, I for the base path]

**Embedded form:** a table can live inside the preset. [V-Xfer p.22, p.302-303]

- Observed keys: `embeddedWTData` (a float list), `interpolateAfterLoad`, `tableDisplayName`, and no path. [V-3p, in a serum-mcp test fixture said to copy real Factory structure]
- "Serum embeds the interpolation type rather than the interpolated waveforms." [V-Xfer p.38]
- I found no project that writes a new `embeddedWTData` and confirms Serum loaded it. **[U]**
- Full sample embedding is likely [I]: a 160 MB preset decodes to about 41 million floats. [V-3p] The key name for that was not identified. **[U]**

**Multisample:** `MultiSampleOsc{i}` stores `embedded_sfz` text, a `files` map and `sfzPathRelative`. [V-3p]

**Wavetable file format:** mono 32-bit float WAV at 44100 Hz, with 2048-sample frames and a `clm ` chunk reading `<!>2048 01000000 wavetable (www.xferrecords.com)`. [V-3p] Up to 256 frames. [V-Xfer p.38]

Serum loads a wavetable at 2048 samples per frame. [V-Xfer p.38] Tables can be custom-generated this way, but the frames must be single cycles to play correctly at pitch. [I]

Position scale conflict: `kParamTablePos` is called 1..256 by the loader and 0..256 by serum-mcp. **[U]**

---

## 4. What the tools can and cannot do today

| Tool | Read | Write | Render | Limits | Licence |
|---|---|---|---|---|---|
| [serum-preset-packager](https://github.com/KennethWussmann/serum-preset-packager) (65-line CLI) | Yes, to JSON | Yes, from JSON | No | Says valid properties are unknown. `pack` writes metadata as given and does not recompute `hash` [read from code]. Uses 64-bit floats | **None in repo** [gh API] |
| [serum2-preset-loader](https://github.com/wiillownet/serum2-preset-loader) 0.5.2 | Yes | Yes, with hash, key order and float widths kept. Edited factory preset loaded in 2.1.5 | Makes VST3 state for DawDreamer | Only 29 parameters in `set_param`. Direct `setState` of preset bytes silently gives init | MIT |
| [PySerum](https://github.com/ThatMajd/PySerum) | JSON | JSON, then needs the packager | No | README covers oscillators, filters and modulation only. No FX listed | **None in repo** [gh API] |
| [serum-render](https://github.com/wiillownet/serum-render) 0.6.0 | Via loader | No | Yes, batch, needs licensed Serum | Python 3.11-3.12, macOS or Windows. Non-deterministic issues below | GPL-3.0-or-later |
| [serum-mcp](https://github.com/Celian-mrc/serum-mcp) (not on your list) | Yes | Yes, broad: all 5 engines, 16 FX, matrix, arp | Not in the server | Targets 2.0.11. Text to preset. Lists audio-to-preset as V2, "not started" | MIT |
| [serum2vital](https://github.com/btesser/serum2vital) (not on your list) | Yes | Writes Vital | Has Serum host tools | Conversion, not Serum writing | GPL-3.0 |
| [node-serum2-preset-packager](https://github.com/CharlesBT/node-serum2-preset-packager) | Yes | Yes | No | Same format research, TypeScript | MIT |

**Render-path constraints:**

- Host parameters: dump has 2,622 entries, 414 after removing the MIDI-channel (CC, aftertouch, pitch bend) and Mod slots. Oscillator `Param34-55` are unnamed. [V-3p dump, I for the split] The dump dates from March 2025.
- A fast FX edit therefore needs a state reload rather than a host parameter set. [I]
- State injection differs from GUI load in small ways. Pre-2.1.5 presets load with two compat flags on. [V-3p loader] serum-mcp found unset filter routing bypassed filters under state injection, while the GUI routed through them. [V-3p §5]
- Serum keeps state between presets. Across 1,491 presets, 97% showed audible differences mid-batch, fixed by one process per render. [V-3p serum-render]
- Sample-heavy presets can render partly loaded: 9 of 10 renders at peak 0.25, one at 0.05. A fresh process does not fix it. [V-3p]
- Random phase and unison mean renders are not bit-identical. [V-3p loader]
- Malformed values can crash the host, such as bad FX types and proxy links. [V-3p loader]
- Version markers: PySerum's init is 2.0.24 with `version` 9.0. The loader targets 2.1.5 with 11.0 and uses them for migration. This Mac has 2.0.20. A 2.1.x install would need testing. [V-3p, V-local, I]

---

## 5. What is hard to infer from audio

All of this section is **[I]** unless tagged. It is reasoning from the structure above, not measured performance.

### Cannot be known from one rendered note

The information is simply absent unless the WAV exercises it.

- Velocity and note curves, key tracking, aftertouch, mod wheel, pitch bend, MPE.
- Macros: values are heard, but assignments and names are not.
- Mono, legato, polyphony, portamento, voice priority.
- Disabled modules, unused LFOs, unused matrix rows.
- Unused arp and clip slots.
- Behaviour above or below the rendered pitch, such as multisample zones and filter keytrack.

Several of these could become observable if the input were several notes or velocities, but that would change the input contract.

### Many settings give the same sound

| Heard effect | Possible causes |
|---|---|
| Brightness | Wavetable frame, warp, filter cutoff, drive, FX, or EQ |
| Thickness | Oscillator unison, Hyper, chorus, a second oscillator, or voice-control detune |
| Timbre sweep | WT pos modulation, warp, filter envelope, LFO, Spectral filter, or a sample's own evolution |
| Fast decay | ENV 1, a filter envelope, or a sample's natural decay |
| Stereo width | Unison width, pan, filter pan, Utility, reverb, Dimension |
| Harmonic series | One table plus FM, or a different table with none |

An exact sonic match therefore does not identify the original preset. A preset can match while being musically different to edit. Exact-parameter recovery should not be assumed possible.

### Discrete choices with no smooth path

- Which of 288 tables, plus user tables, and which frames.
- Filter type (about 100), where VAR changes meaning per type.
- Warp lanes (about 70 each, so about 4,900 pairs), including cross-module FM.
- FX selection and order, including splitter membership.
- Mod routes: 64 slots across 49+ sources and hundreds of destinations.

### File references

- Multisample, sample, granular, spectral and noise modes depend on the actual audio file.
- If the source audio isn't in the library, an exact reference is impossible, and only an approximation or a new user file is possible.
- A wavetable can be estimated from a periodic sound, which is a generation problem, not a parameter problem. Phase, frames and interpolation would be estimates.
- 3.6% of factory oscillator slots use spectral and 4.0% granular, against 53.6% wavetable and 15.8% multisample. Sample use was undercounted at 2.2%. [V-3p §8] So non-wavetable engines are not rare.

### Randomness and drift

- Default random phase is 100% on wavetable oscillators. [V-3p]
- Noise, Random unison, granular randomisation, chaos LFOs, note-on random sources and voice randomisation all vary per note. [V-Xfer]
- Compare statistics rather than samples when these are in play.

### Hidden character

Evidence that small unmodelled items dominate perception, from one project's reports. [V-3p §5]

Recreations of real presets were judged wrong, one as "nothing like the original", and these were among the causes that project found:

- S&H LFO type.
- A second FX rack.
- A second warp lane (193 slots across 886 presets).
- Comb filter VAR.
- `flex` curves on a distortion.
- Routing to the wrong filter.
- Writing default values instead of omitting them.

Per-route curves appear on about 3-4% of real routes. [V-3p §6]

### Relative difficulty

| Likely easier | Likely harder |
|---|---|
| Pitch, level, overall envelope of a simple sound | Exact wavetable and frame |
| Rough filter shape, broad brightness | Filter type identity when other spectral shaping exists |
| Presence of noise, reverb tail, delay echoes | FX order, delay and reverb parameters when mixed with the source |
| Unison voice presence | Voice count and exact detune mode |
| LFO rate when clearly periodic | LFO shape, target, and multiple modulators |
| Whether a sound is likely sample-based | Which sample |

---

## 6. Family summary

| Family | Kind | Approx. size | Stored in | Tools can write | Audio inference |
|---|---|---|---|---|---|
| Osc mode | D | 5 | `Oscillator*.kParamType` | Yes | Moderate |
| Wavetable | F + C | 288+ tables, up to 256 frames | `WTOsc*` | Reference yes, embed U | Hard |
| Warp | D + C | About 70 or 88, 2 lanes | `*Osc*.kParamWarpMenu` | Yes, enums partial | Hard |
| Unison | C + D | 16 voices, 5 modes, 9 stacks | `Oscillator*` | Partly | Moderate |
| Sub, noise | D, F, C | 6 shapes, 217 files | `SubOsc4`, `NoiseOsc3` | Yes | Moderate |
| Filters | D + C | About 100 types, 2 modules | `VoiceFilter*` | Yes | Moderate to hard |
| Envelopes | C | 4 × 8 | `Env*` | Yes | Amp easier, others harder |
| LFOs | D, C, S | 10 with drawn shapes | `LFO*`, `curveData` | Mostly, curves partly | Hard |
| Mod matrix | S | 64 slots | `ModSlot*`, `flex` | Yes, curves partly | Very hard |
| Routing | D + C | 7 slots | `RoutingSlot*`, `Global0` | Yes | Hard |
| FX | S + C + F | 16 types, 3 racks, 193 stored params | `FXRack*` | Yes | Hard |
| Voice, global | C, D | Dozens | `Global0`, `VoicePanel0` | Mostly | Mostly unknowable |
| Arp, clips | S | 12 each | `Arp*`, `MidiClip*` | Arp partly, clips not found | Depends on input |

---

## 7. Conflicts and open items

| Topic | Conflict | Status |
|---|---|---|
| Filter type count | 80, 97, 96, 107 by source | U |
| Distortion modes | 13, 16, 17 | U |
| Reverb names | Nitrous and Basin against kSpace and kAbyss | U |
| Embedding | serum-mcp docstrings say Serum always stores custom tables separately. Xfer's manual and serum-mcp's own test fixture show embedding exists | The docstring is wrong as a general claim [I] |
| Embed on factory content | Manual says unavailable for factory-supplied content. A fixture claims a Factory preset has an embedded table | U, may be different cases |
| `kParamTablePos` | 1..256 or 0..256 | U |
| Oscillator type name | serum2vital reads `kOsc_Wavetable`, others `kOsc_WT` | U, likely a default string only [I] |
| Serum 2.1 changes | No changelog found. Xfer's guide is 2.0.18, and third-party tools cite 2.1.5 | U |
| Xfer opening the format | A 2025 podcast note reports Steve Duda wants to open it eventually [V-3p]. No public spec found | U |

---

## 8. Licence and terms: quotes only

No legal opinion is given. Whether any clause applies to any activity is a question for a qualified person.

**EULA text.** Source: a Xfer Records EULA PDF from Japanese distributor Crypton Future Media, PDF created 2016-02-17, retrieved from a Wayback capture dated 2020-05-11, because the live URL returned HTTP 503 today. It is not confirmed to be the Serum 2 EULA. Xfer's page `xferrecords.com/license` requires sign-in, so I could not read it.

> (a) This software is intended to be used only by the individual who purchased it, hereafter referred to as "Licensee".

> (b) Licensee may install this software on multiple computers, provided that every machine is under personal ownership and care of Licensee. Licensee may make personal copies of materials within the package or otherwise related only as required for backup purposes.

> (c) Licensee is prohibited from reverse engineering, decompiling, translating, disassembling, deciphering, decrypting, or otherwise attempting to discover the source code of this material.

> (d) Licensee may not remove, alter, deface, overprint or otherwise obscure Licensee patent, trademark, service mark or copyright notices.

> (e) Licensee may not share, publish or distribute the software without prior consent from Xfer Records.

That copy has no clause naming automation, scripting, headless use, preset formats, wavetables or factory presets.

**Serum 2 User Guide, p.2:**

> No part of this document may be reproduced or transmitted in any form or for any purpose without the express written consent of Xfer Records.

**Serum 2 User Guide, p.22:**

> Note that the option to embed a wavetable or sample into a preset is not available for factory-supplied content.

**Steve Duda, Xfer forum, 2021-02-24** ([thread](https://xferrecords.com/forums/posts/76418)):

> With a Serum license, you're allowed to do use Serum in any sound design capacity. Of course with that said, some third party presets could be restricted and you should check accordingly or use original content. If you are creating your own sounds / not using 3rd party Noise files or wavetables, you will be in the clear.

**Steve Duda, 2017-01-20** ([thread](https://xferrecords.com/forums/general/serum-licences)):

> The license is for an individual. You can install Serum on multiple computers you personally own. It can't be shared with others so e.g. a musical partner needs to purchase a separate license for his computer.

**Reported, second-hand** (0xdevalias's gist, quoting another person's note about contacting Xfer):

> Unfortunately, the .fxp file format is completely dependent on the source code, and he can't release a spec for it without making the code open source.

That is about Serum 1 `.fxp`, not `.SerumPreset`.

**Facts about method for a reviewer to weigh, with no conclusion drawn:**

- serum-mcp says it extracted printable strings from the installed plugin binary.
- serum-mcp, serum2vital and the loader read or hosted real Serum content to build their tables.
- Data derived from these projects inherits how it was obtained.
- The packager and PySerum have no licence file.
- Copying factory tables or samples into a repository or package is a separate question from referencing them by path on a licensed machine.

---

## 9. What I did not do, and could not verify

- **Did not decode the 626 installed factory presets.** Doing so would give firm enum lists, but it wasn't in the brief, and the reverse-engineering clause should be read first. The Filter and Warp gaps above would close quickly with that step or a Serum GUI menu capture.
- **Did not inspect the Serum binary**, or load or run Serum.
- **Did not run any third-party package.** I read sources from tarballs in a temp folder. My own short scripts parsed PDFs, text and JSON only.
- **Could not read:** the current Serum 2 EULA, Xfer's sign-in licence page, a Serum 2.1 changelog, or any official format spec.
- **Could not confirm:** the true filter, warp and distortion counts; the Nitrous and Basin keys; the embedded sample key; whether a newly written `embeddedWTData` loads; and full semantics for many fields marked uncertain in `schema.py`.
- Third-party docs are single-project reports, some self-revised, and I treated them as claims.

---

## Sources

**Xfer**

- S1. Serum 2 User Guide, 2.0.18, manual 1.0.3: <https://xferrecords.com/manual/serum-2> (also shipped locally as `/Library/Audio/Presets/Xfer Records/Serum 2 Presets/Serum 2 User Guide.pdf`, an earlier revision)
- S2. What's New in Serum 2: <https://static.xferrecords.com/Serum%202%20What's%20New.pdf>
- S3. Forum, selling sounds: <https://xferrecords.com/forums/posts/76418>
- S4. Forum, licences: <https://xferrecords.com/forums/general/serum-licences>
- S5. Forum, licence transfer: <https://xferrecords.com/forums/general/can-you-sell-or-transfer-your-serum-license>

**EULA copy**

- S6. <https://ec.crypton.co.jp/download/pdf/eula_xferrecords.pdf>, via <https://web.archive.org/web/20200511102815/https://ec.crypton.co.jp/download/pdf/eula_xferrecords.pdf>

**Format and tools**

- S7. serum-preset-packager: <https://github.com/KennethWussmann/serum-preset-packager>
- S8. serum2-preset-loader: <https://github.com/wiillownet/serum2-preset-loader>, <https://pypi.org/project/serum2-preset-loader/>
- S9. PySerum: <https://github.com/ThatMajd/PySerum>
- S10. serum-render: <https://github.com/wiillownet/serum-render>
- S11. 0xdevalias gists: <https://gist.github.com/0xdevalias/5a06349b376d01b2a76ad27a86b08c1b>, <https://gist.github.com/0xdevalias/135a18e979ac8e302ebbc700a50a8d74>
- S12. Serum 2 VST3 parameter dump: <https://gist.github.com/KennethWussmann/5b58e4de728680a0bf8906a8b113103d>
- S13. serum-mcp, including `docs/PARAMETER_SCHEMA.md` and `src/serum_mcp/preset/schema.py`: <https://github.com/Celian-mrc/serum-mcp>
- S14. serum2vital, including `docs/FORMATS.md`: <https://github.com/btesser/serum2vital>
- S15. node-serum2-preset-packager: <https://github.com/CharlesBT/node-serum2-preset-packager>

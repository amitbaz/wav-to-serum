# Audio analysis for synth reconstruction: what can be measured

Date: 2026-11-01. Scope: which properties of a recorded synth WAV can be extracted reliably, by what method, and what audio does not contain. End-to-end neural sound matching and Serum parameter facts belong to the sibling reports; they appear here only where they bear on measurement.

## Evidence labels

Every claim carries one label.

| Label | Meaning |
|---|---|
| **[V]** | Verified from a source read this session (paper text or table, repo, docs, registry) |
| **[M]** | Measured this session on synthetic signals with known truth. See Appendix A. These are small checks, not benchmarks |
| **[I]** | Inferred from signal theory or from the sources, not stated by them |
| **[U]** | Unverified: only a snippet or abstract was seen, or the check could not be done |

## Main findings

1. **Stationary, periodic, single-voice measurements are close to solved.** Pitch, harmonic amplitudes, a single-cycle wavetable, amplitude envelope, LFO rate and stereo statistics can all be computed exactly enough with plain FFT code that runs in any language. **[M]**
2. **A single static note cannot separate oscillator from filter.** Only the product of the two is present. A filter becomes identifiable once the cutoff moves or a second pitch is played, because the source then cancels. **[M]** I found no published method for filter-type classification from audio. **[U]**
3. **Unison is measurable only while the signal matches the assumed model.** The one published estimator reports 0.67% error on N on ideal supersaws **[V]**. My rough reimplementation lost most of its accuracy with a 1-cent f0 error, a louder centre voice, or a 1 kHz low-pass **[M]**.
4. **Effect work is the weakest area.** Published detection reaches about 79% across five effects on non-synth instruments, and dry-signal recovery falls quickly as effects stack. Chorus and delay removal remain hard. **[V]** Detect effects from measured signatures and do not plan to remove them.
5. **Parameter recovery is ill-posed by construction.** "Many audio synthesizers can produce the same signal given different parameter configurations." **[V]** Tools should report measurements and candidate sets, and the final check should be a render-and-compare. Peladeau and Peeters found that accurate parameters do not guarantee close audio. **[V]**
6. **Almost all the DSP is language-neutral.** Python is required only for the neural models that have no maintained Node port: RemFX, MT3, DDSP and modulation discovery. Pitch and transcription can run in Node. **[V/I]** See section 11.

## Reliability summary

"Grade" is my judgement of how far an LLM can trust a number from this tool on a real synth recording. **[I]**

| Property | Best method | Open tool (licence, language) | Grade |
|---|---|---|---|
| Mono f0 | pYIN or CREPE, then harmonic refinement | librosa (ISC, Python), torchcrepe (MIT, Python), PESTO (LGPL-3.0, Python, ONNX export) | High, except low sub and inharmonic tones |
| Chord notes | Basic Pitch | basic-pitch (Apache-2.0, Python and TS) | Medium, needs a ghost-note check |
| Note segmentation | Basic Pitch notes, or RMS and onset novelty | same; madmom weights are CC BY-NC-SA | Medium, weak on slow pads |
| Single cycle | f0-synchronous harmonic DFT | own code | High if periodic; flag when not |
| Wavetable over time | Framewise harmonic spectra | own code; DWTS for learned tables | Medium: gives the sound, not Serum's table or position curve |
| Library match | Phase-free log-magnitude matching, filter-tolerant | own code | Medium, shortlist only |
| Harmonics vs noise | Harmonic-model subtraction with known f0 | Essentia HpsModelAnal/SpsModelAnal (AGPL-3.0, C++/JS), sms-tools (AGPL-3.0, Python) | High for tones; unison reads as noise |
| Amp envelope | RMS over 1 to 2 periods | own code | High at mid and high pitch, limited at low pitch |
| Filter envelope | Spectral centroid or rolloff curves | own code, Meyda (MIT, TS) | Medium: shows movement, not its cause |
| LFO rate and shape | Spectrum of envelope or centroid | own code; LFO-net for effect LFOs (MPL-2.0, Python) | High for rate with 2+ cycles; beats can fake it |
| Filter type and cutoff | Differential fit across cutoff or pitch change | own code | Low for one static note; medium with movement |
| Unison count and detune | Peak-comb cost function | own code from Matsumoto and Yatabe | High only on bright, clean, ideal saws |
| Stereo width | M/S ratio, band correlation, cross-correlation lag | own code | High |
| Reverb, delay | Tail decay, cepstrum or autocorrelation | own code | Medium for presence; low for parameters |
| Compression | Blind wet-only methods exist | dasp-pytorch (Apache-2.0, Python) | Low from one note |
| Distortion | Intermodulation on chords and unison | own code; CNN classifiers for guitar | Low to medium |
| FM, RM | Inharmonicity, sideband spacing | own code | Medium to detect; low to invert |

---

## 1. Pitch and note segmentation

**Mono: best methods.** Use pYIN (classical) or CREPE and PESTO (neural).

| Model | Licence, language | Published raw pitch accuracy at 50 cents | Notes |
|---|---|---|---|
| pYIN | librosa ISC, Python | RWC-synth 99.0%, MDB-stem-synth 91.9% | **[V]** CREPE paper table; librosa docs |
| SWIPE | not checked | 96.3%, 92.5% | **[V]** same table |
| CREPE | MIT, Python | 99.9%, 96.7%; at 10 cents 99.5%, 90.9% | **[V]** range 32.70 to 1975.5 Hz, 22.2M params |
| PESTO | LGPL-3.0, Python | MDB-stem-synth 94.6 to 95.5%; 28.9k params | **[V]** ONNX export documented, about 0.7 ms per inference |

"Synth" in those dataset names does not mean synth patches. RWC-synth is a fixed sum of a few sinusoids, and MDB-stem-synth is analysis/synthesis of real stems for exact pitch labels. **[V]** The wide standard deviations, up to 0.129 for pYIN on MDB-stem-synth, suggest failures cluster in particular tracks. **[I]**

**Noise.** CREPE fell from 97.8% clean to 84.8% at 0 dB against background music. PESTO trained with background noise fell to 83.1%, and without it to 50.0%. **[V]**

**Measured on synth tones.** pYIN (frame 4096, fmin 20) gave 0% gross error on saw, square, low-passed saw, high-passed saw with weak fundamental, 7-voice supersaw, drive, reverb, integer-ratio FM, and saw with noise at -6 dB. **[M]** Three failure modes matter:

- **Inharmonic tones produce confident nonsense.** FM at 1:1.414 returned 44.38 Hz with 99% of frames voiced. A pitch of "220 Hz" does not exist in that signal, and the tracker does not say so. **[M]** Pair every f0 with an inharmonicity or harmonic-fit score. Essentia has an `Inharmonicity` algorithm. **[V]**
- **Low sub-bass.** A 41.2 Hz sine read 18.7 cents sharp with a 4096-sample frame. **[M]** CREPE's lowest bin is 32.70 Hz. **[V]** Sub material below that is outside its range. **[I]**
- **Quantised output.** librosa's pYIN defaults to 0.1 semitone resolution **[V]** and returned 109.92 Hz for 110, a 1.3-cent bias **[M]**. That is too coarse for the unison analysis in section 6, so refine f0 by maximising harmonic energy. **[I]**

**Chords.** The practical tool is Basic Pitch (Apache-2.0, Python and TypeScript). **[V]**

| Model | Dataset | Note F no-offset | Frame |
|---|---|---|---|
| Basic Pitch (NMP) | Slakh | .42 | Acc .44 |
| Basic Pitch (NMP) | GuitarSet | .79 | Acc .70 |
| MT3 (mixture) | Slakh2100, full mixes | Onset F1 .76 | Frame F1 .79 |

**[V]** These rows use different test splits and metrics, so they are not directly comparable. **[I]** Slakh is rendered with sample-based virtual instruments, so neither figure describes supersaws or FM. **[V]** Basic Pitch states it "works best on one instrument at a time". **[V]** MT3 (Apache-2.0, Python) targets multi-instrument mixes and is more than a single-sound task needs. **[I]**

In 11 stationary synthetic chords, Basic Pitch recovered every true note, including octave stacks and a supersaw triad. **[M]** It added two ghost notes: an A1 below a low-passed min7 chord, and an A5 on 1:1 FM at index 4, where a strong harmonic read as a note. **[M]** The set is tiny and easy, so the conclusion is limited to this: treat extra notes as suspect. Known fundamentals let harmonics be explained away. **[I]**

Other options are Essentia `MultiPitchKlapuri` and `MultiPitchMelodia` (AGPL-3.0). **[V]** I did not test them or find accuracy figures for synths. **[U]**

**Segmentation.** Basic Pitch returns note events with pitch bends. **[V]** For onsets, Essentia includes SuperFlux; madmom's code is BSD-style, but its model files are CC BY-NC-SA 4.0, which restricts commercial use. **[V]** Offset detection is inherently weak: Basic Pitch's authors chose onset-only F as their main metric because offsets are less objective, partly due to reverberation. **[V]** Slow-attack pads have no sharp onset. **[I]**

## 2. Single cycles, wavetables and library matching

**Single cycle.** With an accurate f0, take the DFT at exact harmonic frequencies over a stationary segment, then inverse-transform to one cycle at the target length. **[I]** Resynthesis error is the honesty signal, measured as the residual after fitting one period **[M]**:

| Signal | Residual | Reading |
|---|---|---|
| Saw | -170 dB | Fully captured |
| FM 1:1 and 1:2, RM 3:2 | -171 to -174 dB | A single cycle reproduces them exactly |
| Saw with noise at -30 dB | -30 dB | Residual equals the noise level |
| Unison N7, 0.05 st | -9 dB | Not periodic |
| Unison N7, 0.2 st | -2.9 dB | One cycle explains almost nothing |
| FM 1:1.414, RM 1:1.7 | 0 dB | No period exists at f0 |

This one number tells the model whether a wavetable can represent the sound at all. A high residual on a pitched sound points to unison, noise or inharmonic modulation. **[I]** A real preset measurement of this was not run. **[U]**

**Wavetable over time.** Repeat per frame to get a harmonic-amplitude matrix. This reproduces the sound but does not recover the original table, because frames also carry filter and envelope movement. **[I]**

- Differentiable Wavetable Synthesis (Shan et al.) learns a dictionary of single-cycle tables; 10 to 20 were enough on NSynth, against 100 sinusoids in an additive synth. **[V]** These are dictionaries learned across a dataset, not Serum tables, and I found no licensed official implementation. **[U]**
- Modulation Discovery uses a learnable 16-position, 1024-sample wavetable and found wavetable modulation harder to extract than envelope and filter modulation. **[V]**
- Serum 2 has its own "Frequency Estimation" sample-to-wavetable conversion. Xfer advises samples with clear harmonic content and notes that shorter samples convert more predictably. **[V]** It does not publish the algorithm. **[U]**

**Library matching.** Compare log-magnitude harmonics, never waveforms: two saws with the same magnitudes and random phases correlated only 0.57 as waveforms, with 0.0 dB magnitude difference. **[M]**

An unknown low-pass shifts the match. On a synthetic library of 300 ragged random tables, top-1 was 89% on raw log-magnitude and 100% after liftering out the smooth envelope along the harmonic axis. **[M]** That library favours liftering: real tables with smooth spectra, such as saw and square morphs, differ mainly in the part liftering removes, so expect worse. **[I]** I found no paper evaluating retrieval against a commercial wavetable library. **[U]** Use it to produce a shortlist with distances. **[I]**

## 3. Harmonic content and noise

**Best method.** With f0 known, measure harmonics directly, subtract them, and describe the residual as filtered noise. This is the sines-plus-noise model. **[V]** DDSP's harmonic-plus-filtered-noise synth is the differentiable version (Apache-2.0, Python), used with 100 harmonics and 65 noise bands in Modulation Discovery. **[V]**

- **Tools.** Essentia lists `HarmonicPeaks`, `HpsModelAnal`, `SpsModelAnal`, `SprModelAnal`, `Tristimulus`, `OddToEvenHarmonicEnergyRatio`, `Inharmonicity` (AGPL-3.0). **[V]** sms-tools is AGPL-3.0, Python. **[V]**
- **HPSS is the wrong tool.** librosa's `hpss` follows Fitzgerald 2010 and Driedger 2014 **[V]** and splits sustained from transient energy, not tonal from noise. It is useful only for separating click attacks. **[I]**
- **Spectral flatness** is available in Meyda and Essentia. **[V]** It is a coarse proxy and depends on overall spectrum shape. **[I]**

**Failure mode.** Detuned unison leaves a large residual (-2.9 dB at N7, 0.2 st **[M]**) that a harmonic model will call noise. Check residual structure before reporting a noise oscillator: unison residual is concentrated around harmonics, and real noise fills the gaps between them. **[I]**

**Odd and even harmonics** are a simple reliable discriminator for square-like sources. **[I]** The Instrumental preprint uses the even-to-odd ratio and spectral flatness as initialisation. **[V]** That paper tests one target sound, so it is weak evidence. **[V]**

## 4. Envelopes and LFOs

**Amplitude envelope.** Use RMS with a window of one or two periods, then fit attack, decay, sustain and release. Essentia has `Envelope` and `LogAttackTime`. **[V]**

Attack accuracy is limited by pitch, because the window must span a period. With a 2-period window **[M]**:

| True attack | 55 Hz | 110 Hz | 440 Hz |
|---|---|---|---|
| 1 ms | 16.4 ms | 5.2 ms | 2.7 ms |
| 5 ms | 17.8 ms | 12.1 ms | 6.5 ms |
| 20 ms | 30.4 ms | 27.5 ms | 20.7 ms |
| 100 ms | 109.5 ms | 102.1 ms | 100.3 ms |

Treat fast attacks at low pitch as an upper bound. **[I]**

**Release is confounded by reverb.** A 100 ms release T60 with a 1.2 s reverb fitted as 393 ms at 5% mix, 907 ms at 15%, and 1042 ms at 30%. **[M]** Reverb tail measurement and release measurement are one measurement unless the decay shows two slopes. **[I]**

**Filter envelope.** Spectral centroid and rolloff curves show movement (Meyda, MIT, TS). **[V]** They cannot attribute it. Modulation Discovery found the subtractive and envelope modules "make similar perceptual changes", and discovered modulations spread across modules. **[V]**

**LFO rate and shape.** Take the spectrum of the envelope or centroid curve. Rate came out within 0.03 Hz of 4.3 Hz at 0.5 to 4 s. Waveform shape showed in overtones: triangle gave h3/h1 0.10 (theory 0.11), and square gave 0.30 (theory 0.33). **[M]** These are clean single-target tones.

- **Beats fake LFOs.** Two sines ±0.1 st at 110 Hz gave a 1.27 Hz envelope peak with no LFO. **[M]** A real LFO moves all harmonics together; beats scale with harmonic number. **[I]**
- **Less than one cycle.** A slow LFO over a short sample is indistinguishable from an envelope. **[I]**
- **Neural extraction.** LFO-net (MPL-2.0, Python) extracts LFOs from phaser, flanger and chorus with about 3% L1 error, rising to 13 to 16% on saw LFOs after distortion and 10.3% on combined modulations. **[V]** It was evaluated at 0.5 to 3 Hz rates. **[V]** That paper covers effects, not synth voices. **[V]**
- **Modulation Discovery on real Serum audio.** Using 880 "Bass (Hard)" preset renders, correlation between discovered modulation and proxy features was about 0.41 to 0.54 with the two wavetable-based DDSP synths. **[V]** The figure is against RMS and spectral flatness proxies because true curves were unknown. **[V]** The authors note about 98% of Serum presets use modulation. **[V]** Modulations are therefore the normal case, and exact curves remain an open problem. **[I]**

## 5. Filter type and cutoff

**Can a filter be told apart from its source?** For one static note, no. A harmonic tone samples the product S(k)·H(k·f0) at harmonic k, so any output has the exact explanation "this wavetable, no filter". **[I]** When I fitted filters to static tones while assuming a saw source, a saw source returned the right type, but a random wavetable returned the wrong type in 4 of 5 cases. **[M]** With a known source a static fit worked; the failure comes entirely from not knowing the source. **[I]**

**What makes it identifiable.**

- **Moving cutoff.** The log-spectrum difference between two frames cancels the source: `log|X2(k)| - log|X1(k)| = log|H2(k·f0)| - log|H1(k·f0)|`. Using two stationary segments at different cutoffs, the fit returned the right type in all 10 cases across both sources (LP12, LP24, resonant LP12, BP, HP), with cutoffs inside the 9% grid step. **[M]** The test was noise-free and tried only five types. It assumes the wavetable position did not move at the same time. **[I]**
- **Second pitch.** With a fixed-cutoff filter and a pitch-tracking wavetable, harmonic k moves across H, so two notes cancel the source in the same way. **[I]** Not measured. Key tracking breaks this unless modelled. **[I]**
- **Resonance.** A peak that moves with the sweep, stays still across notes and sits between or across harmonics points to a filter, not a table. **[I]** Low f0 samples the peak more densely, so resonance is easiest to read on low notes. **[I]**
- **Noise source.** Noise excites all frequencies continuously, so the residual reveals H directly. **[I]**

**Literature.**

- I found no paper on classifying filter type from audio, or on blind source-filter separation for synths. **[U]** That is a search result, not proof that none exists.
- Instrumental maps spectral rolloff to cutoff as a starting point, and its own limitation note is that it tests a single target. **[V]** Its abstract says CMA-ES beat gradient descent on this non-convex landscape, and constraining parameters was needed to avoid "deceptive minima". **[V]**
- InverSynth treats cutoff and resonance as parameters of one synth. **[U]** snippet only. Timoney, Avci and Lazzarini (AES 2019) note there had been no specific analysis of subtractive filter resonances. **[U]**
- Differentiable routes exist: Modulation Discovery uses a learnable time-varying biquad. **[V]**

**Expect the type label to be weak.** Serum has many filter models. **[U]** Different models with the same nominal type differ in drive and resonance character, so one fit gives slope and peak shape, not a model name. **[I]**

## 6. Unison, detune and stereo width

**Unison.** The only directly relevant source I found is Matsumoto and Yatabe (2022, Japanese, Acoustical Society of Japan proceedings). **[V]** Rendered pages were read directly. It estimates voice count N and detune d from a mono supersaw with f0 known, by scoring the spectrum at all expected peak positions, for single notes and six chord types.

Reported on synthetic signals, 44.1 kHz, 0.3 and 0.5 s, roots 220 to 880 Hz, N 2 to 16, d 0.05 to 0.50 semitones: N error rate 0.67% overall, 0.0079% for d ≥ 0.2, 8.1% at d = 0.05; detune mean error 2.8×10⁻⁵ and maximum 2.6×10⁻⁴ semitones. **[V]** Signals had no filter or amplitude change, which the authors call a first step, and used equal-amplitude voices with log-uniform spacing. **[V]** Error grew with short data, high f0, large N, small d and more chord notes. **[V]**

**Stress test.** I reimplemented the three-stage search (`exp3.py`) with an equal-loudness voice set, f0 220 to 880 Hz, N 3 to 9, 48 cases per row. It reached lower accuracy than the paper on clean signals, so read this as sensitivity to model mismatch, not as an evaluation of their method. **[M]**

| Condition (0.5 s) | N correct at d = .05 / .1 / .2 / .5 |
|---|---|
| Clean | 58 / 83 / 83 / 92% |
| Clean, 2 s | 75 / 83 / 100 / 100% |
| f0 off by 1 cent | 0 / 25 / 33 / 33% |
| f0 off by 3 cents | 0 / 0 / 0 / 0% |
| LP24 at 4 kHz | 33 / 50 / 67 / 83% |
| LP24 at 1 kHz | 0 / 8 / 25 / 8% |
| Reverb 25% mix | 75 / 58 / 83 / 100% |
| Noise at -20 dB | 58 / 83 / 83 / 92% |
| Drive (tanh 3) | 50 / 50 / 83 / 83% |
| Centre voice +6 dB | 0 / 0 / 0 / 0% |
| Linear voice spacing | 58 / 83 / 67 / 0% |

Median detune error on clean signals was about 0.0001 semitones at d ≥ 0.1. At d = 0.05 it was about 0.05 semitones at 0.5 s, meaning the search failed, and near zero at 2 s. **[M]**

Conclusions:

- **Search f0 jointly.** A 1-cent error destroys the estimate, and pYIN's own quantisation bias was 1.3 cents. **[M]**
- **The voice model matters more than noise or reverb.** A boosted centre voice and linear spacing broke the cost function, and Serum's blend and unison modes are likely to violate the assumptions. **[I]** I could not confirm how Serum spaces or weights voices. **[U]**
- **Peaks need separating in time.** Adjacent-voice spacing is about k·f0·(2^(2d/(12(N-1))) - 1) at harmonic k, and a Hann window on T seconds resolves about 4/T Hz. **[I]** For N7, d 0.2, f0 110 and T 0.5, that means harmonic 19 or higher, near 2 kHz. A 1 kHz low-pass removes the evidence, which fits the table. **[I]**

Reporting a detune range and a voice-count range is more honest than one number. Spectral width at high harmonics, growing in proportion to k, is the robust signal that unison is present. **[I]** In the Instrumental preprint's ablation, adding unison and noise floor cut matching loss by 49%, on one target sound. **[V]**

**Stereo.** Standard DSP, no library needed. Metrics: mid/side energy, L/R correlation per band, cross-correlation peak lag. **[I]**

| Signal | Correlation | S/M | Peak lag |
|---|---|---|---|
| Unison pan spread 0 | +1.000 | none | 0 |
| Spread 0.5 | +0.865 | -11.4 dB | 0 |
| Spread 1.0 | +0.514 | -4.9 dB | 0 |
| Alternating voices hard L/R | -0.011 | +0.1 dB | meaningless |
| Haas 15 ms | -0.376 | +3.4 dB | +15.00 ms |
| Polarity flipped | -1.000 | very high | not applicable |

**[M]** Correlation alone misleads: Haas delay looks wide with a negative correlation here, and the value depends on the signal. Report lag and band correlation together. **[I]** Width cannot attribute its cause among unison spread, chorus, Haas delay, reverb or a stereo widener, except by the lag and by per-band behaviour. **[I]**

## 7. Effects

**Realistic position.** Detect presence from signatures, give coarse estimates, and do not attempt removal as a step in the pipeline. No source below used synth presets as input data. **[V]**

**General detection and removal.** RemFX (Rice et al., Apache-2.0, Python) covers distortion, compression, reverb, chorus and delay on singing voice, guitar, bass and drums. **[V]**

- Detection accuracy: distortion 78.0%, compression 80.7%, reverb 84.5%, chorus 75.1%, delay 74.3%, average 78.6%. **[V]**
- Single-effect removal SI-SDR, input to best: distortion 16.4 to 24.4 dB, compression 15.6 to 20.1, reverb 9.3 to 13.6, chorus 8.3 to 11.1, delay 11.3 to 13.5. **[V]** Authors state chorus and delay remain challenging. **[V]**
- Stacking collapses quality: RemFX Detect SI-SDR is 16.67 dB with one effect, 10.47 with two, 6.96 with three, 4.80 with four and 2.61 with five, from inputs of 11.52, 6.24, 3.29, 1.31 and -0.33 dB. **[V]**
- The full system is up to 192M parameters. **[V]**

**Chain estimation with dry recovery.** Take et al. (DAFx 2024) estimate the last effect, undo it, and iterate. On guitar, per step: effect type accuracy 0.695, parameter MSE 0.034, and SI-SDR rising from 10.57 dB to 13.63 dB. **[V]** Reapplying the estimated chain to the true dry signal scored low, 3.49 dB SI-SDR on average. **[V]**

**Blind parameter estimation.** Peladeau and Peeters estimate an equaliser, compressor and clipper chain from wet audio only. **[V]** Minimising audio error gave better audio, and minimising parameter error gave better parameters, so accurate parameters do not imply matching audio. **[V]** dasp-pytorch (Apache-2.0, Python) provides differentiable effects. **[V]**

**By effect.**

| Effect | Measure | State |
|---|---|---|
| **Reverb** | Tail decay after note-off, wet decay per band | Presence is easy on a staccato note. Blind RT60 is much harder on music: Callens and Cernak found music less suitable than speech, since notes rarely stop abruptly. **[U]** Ratnam-style blind RT60 fails outside free decay. **[U]** ACE and FINS-style work targets speech and rooms. **[I]** Removal: WPE (nara_wpe, MIT) is built for speech. **[V]** |
| **Delay** | Autocorrelation or cepstrum peaks of the envelope, echo after note-off | Time and feedback are simple on staccato notes, hard on sustained sound. **[I]** Removal stays hard. **[V]** |
| **Chorus, flanger, phaser** | Slow LFO-driven comb movement | LFO-net extracts the LFO to 3 to 5% L1, given a chosen effect class. **[V]** Static unison and chorus overlap heavily. **[I]** |
| **Distortion** | Harmonics added on a single note look like a brighter wavetable. Intermodulation at sum and difference frequencies appears only with two or more tones. | The chord or unison case is the discriminator. **[I]** FxNet classified 13 distortion plugin emulations on guitar around 86 to 91% when train and test sets match, and SetNetCond estimated gain and tone at MAE about 0.04. **[V]** The data is guitar only, with overdrive, distortion and fuzz plugins. **[V]** |
| **Compression** | Attack overshoot, reduced dynamic range, level-dependent gain | Wet-only recovery from one note is weak. Sheng and Fazekas found threshold and ratio estimable from features, but attack and release need specialised ones; they use a reference. **[U]** Colonel and Reiss recover parameters from dry and wet pairs. **[U]** On one note, compression is an amp envelope. **[I]** |
| **EQ** | Same as filter | Inseparable from source and filter on a static note. **[I]** |

**Phase-aware note.** Static phase matters once distortion follows. Two saws with identical magnitudes differed by 0.94, 3.73 and 6.34 dB log-spectral distance after tanh at drive 1, 3 and 8. **[M]** So a matched magnitude table can still mis-sound after Serum's distortion. **[I]**

## 8. FM, ring modulation and oscillator interactions

**Key simplification.** If modulator and carrier frequencies are in an integer ratio, the output is periodic, so one wavetable cycle reproduces each moment exactly, with a residual of -171 dB. **[M]** Chowning describes integer c/m ratios as harmonic. **[U]** The tool does not need to identify FM to reproduce it statically. It matters only when the sound's spectrum evolves in a way that depends on index movement, or the ratio is inharmonic.

**Detection.**

- **Inharmonicity first.** Non-integer ratios leave a 0 dB single-cycle residual and fool the pitch tracker. **[M]** Fit partial frequencies, then look for regular spacing. **[I]**
- **Sideband spacing.** Partials at c ± n·m indicate FM or PM; a single pair c ± m with no carrier indicates ring modulation. **[I]** Spacing gives the ratio; Bessel-shaped amplitudes constrain the index. **[I]** Chowning describes the sidebands and their Bessel amplitudes. **[U]**
- **Sine carrier only: Hilbert analysis.** Envelope variation vs instantaneous-frequency variation separates the cases cleanly **[M]**:

| Signal | Envelope CV | Instantaneous frequency std |
|---|---|---|
| FM I=1 | 0.002 | 77.7 Hz |
| AM depth .5 | 0.354 | 0.0 Hz |
| RM | 0.483 | 1614.7 Hz (phase flips) |
| Saw FM I=1 | 0.568 | 572.4 Hz |
| Saw AM | 0.702 | 558.2 Hz |

With a saw carrier the method stops working, because a Hilbert envelope needs one component. **[M]** Serum's wavetable FM and RM usually use rich waves, so this test rarely applies directly. **[I]** Band-limiting to one partial first might help; not tested. **[U]**

- **Phase separates mechanisms, not magnitudes.** An FM tone and a random-phase additive tone with identical magnitudes differ only in phase. **[M]** On a magnitude spectrum alone they are the same. **[I]**

**Parameter recovery.**

- DDX7 (Apache-2.0, Python) fits FM by fixing the routing and frequency ratios, then learning envelopes, because only then can gradient methods work. **[V]** Spectral losses give poor gradients on pitch, per Turian et al. **[V]** Indices were also limited since Bessel functions are not monotonic. **[V]** It needs pitch and loudness conditioning and trains per instrument. **[V]**
- The DDSP review states unconstrained sinusoidal frequency optimisation is non-convex and not directly solvable by plain gradient descent on an audio loss. **[V]**
- Sound2Synth reports state of the art on Dexed, but I saw no numbers. **[U]**
- Bispectrum or bicoherence could detect phase-coupled partials from nonlinear interaction. **[U]** I found no synth-specific evaluation.

**Other interactions.** Hard sync produces periodic output at master pitch and is therefore a wavetable-sweep case when sync ratio moves. **[I]** My hard-sync test used a non-band-limited wave, so its number was invalid and is excluded. Ring modulation with integer ratios is also periodic (-174 dB). **[M]**

---

## 9. Ambiguities: different settings, same or nearly same sound

**Exact equivalences.**

| A | B | Why |
|---|---|---|
| Wavetable plus filter, static | Wavetable with those amplitudes baked in | Product of S and H **[M]** |
| FM or RM at integer ratio, static | A wavetable frame | Periodic signal **[M]** |
| Oscillator A with voice set X, B with voice set Y | Swapped | k! permutations; Hayes et al. **[V]** |
| Two detuned oscillators | One with 2-voice unison | Same partials **[I]** |

**Near-equivalences (separable only with extra evidence).** Evidence needed appears in the right column. **[I]** unless noted.

| A | B | Evidence that separates them |
|---|---|---|
| Filter sweep | Wavetable position sweep | Moving peak shape; smooth slope vs ragged change |
| Filter before a soft shaper | Filter after it | Hayes et al. call this approximate: "perceptually similar, but not identical" **[V]** |
| Filter envelope | Amp envelope | Modulation Discovery reports they make similar perceptual changes **[V]**; separate by centroid movement |
| Long release | Reverb | Two-slope decay, stereo decorrelation, measured in section 4 **[M]** |
| Unison | Chorus | Static partial split vs slow moving comb |
| Unison spread | Haas delay or stereo reverb | Peak lag and band correlation **[M]** |
| Distortion | Brighter table | Intermodulation on two or more tones |
| Beating detune | Tremolo LFO | Rate scales with harmonic number **[M]** |
| LFO on filter | LFO on wavetable position | Peak-shape movement |
| Envelope, LFO and DAW automation | Each other | Repeating across notes, retrigger behaviour |
| Noise oscillator | Dense unison residual | Energy between harmonics |
| Compressor | Amp envelope | Needs notes at different levels |
| Sub oscillator | Fundamental in the table | No difference unless detuned or differently enveloped |

## 10. What audio does not contain

**[I]** unless marked.

- **Which control produced a change.** Macros, mod matrix routing, velocity or aftertouch sources and DAW automation are not in the waveform. The output only shows the resulting movement.
- **Parameter names and values as stored.** Only effects on sound exist. Filter model, wavetable name and preset category are at best candidates.
- **Original stored table phase** when a filter sits after it, since filter phase mixes in, and when only magnitude is analysed. Phase is audible in some cases: Laitinen et al. found listeners are not phase-deaf, with aligned phases buzzier than random. **[U]**
- **Per-note random state.** Unison and oscillator random phase, noise oscillator content and free-running LFO phase differ per render, so a sample-exact null test against the reference is the wrong success measure.
- **The MIDI performance behind a single note.** Note-off time, velocity, glide and key tracking need multiple notes or an unambiguous tail. Note-off time and release are confounded without a known length.
- **Tempo sync.** A WAV gives a rate in Hz, not whether it was 1/8 at some tempo, unless the tempo is supplied.
- **Oscillator count and assignment**, beyond distinct behaviour. Silent or fully masked modules leave no evidence.
- **Effects hidden by order.** Reverb followed by distortion and the reverse are different sounds in principle; recovery of order is a low-accuracy estimate. **[V]** for chain accuracy above.
- **Anything above Nyquist or below the noise floor,** including whether oversampling was on.
- **Rate at under one cycle.** An LFO with less than one cycle in the sample cannot be told from an envelope.
- **Voicing behaviour.** Polyphony limits, legato and retrigger need specific performance data.

**Capture advice for the tool chain.** Most of the above improves with better input: a low note and a high note, a staccato and a held note, and a dry render where possible. **[I]** If the user controls the reference, ask for it; if not, report what was not observable.

## 11. Python-only vs Node

| Capability | Node route | Python-only? |
|---|---|---|
| WAV read/write | wavefile, node-wav (MIT) **[V]** | No |
| FFT | fft.js (MIT per npm; GitHub reports no licence) **[V]** | No |
| Spectral features | Meyda 5.6.3 (MIT): RMS, centroid, flatness, rolloff, slope, flux, MFCC, chroma **[V]** | No |
| Harmonic DFT, single cycle, envelopes, LFO, stereo, unison cost, filter fit, library match | Own code on an FFT; numpy here, but no special library is required **[I]** | No |
| IIR filter design for fitting | No standard scipy equivalent; write biquad formulas **[I]** | No, a small effort |
| Mono f0, classical | pitchy (McLeod; npm MIT, GitHub 0BSD), pitchfinder (GPL-3.0), essentia.js `PitchYinProbabilistic` **[V]** | No |
| Mono f0, neural | PESTO to ONNX, then onnxruntime-node (MIT) **[V]**; the export step is Python, and weights are LGPL-3.0. Cache is handled by hand **[V]** | Export only. Not run in Node here **[U]** |
| CREPE | onnxcrepe (MIT) targets Python and was last updated 2022 **[V]** | Node untested **[U]** |
| Polyphonic notes | `@spotify/basic-pitch` 1.0.1 (Apache-2.0, TypeScript) **[V]**; last pushed 2023 **[V]** | No. Parity with Python is not confirmed **[U]** |
| Harmonic plus noise | essentia.js `HpsModelAnal`, `SpsModelAnal`; `HarmonicModelAnal` and `SineModelAnal` are absent from its core API (AGPL-3.0) **[V]** | No, or own code |
| Stem separation | demucs.onnx (MIT) gives ONNX inference **[V]**; Node use untested **[U]** | Only needed for mixes |
| MT3 | none found **[U]** | Yes in practice |
| RemFX, LFO-net, Modulation Discovery, DDX7, DDSP, dasp-pytorch, nara_wpe | none found **[U]** | Yes |

**Licences that shape the choice.** AGPL-3.0 applies to Essentia, essentia.js and sms-tools. GPL-3.0 applies to aubio, Parselmouth, pitchfinder and pedalboard. **[V]** madmom weights forbid commercial use. **[V]** Permissive: librosa, CREPE, torchcrepe, Basic Pitch, Meyda, onnxruntime, DDSP, DDX7, RemFX, dasp-pytorch. **[V]**

**Reading.** A Node toolset could cover every high and medium item in the summary using MIT and Apache code plus Basic Pitch and optionally PESTO. **[I]** Python would add neural effect work, which section 7 suggests is not yet reliable enough to justify the dependency for this input type. **[I]**

## 12. What I could not verify

- **Real Serum renders were not used.** All [M] results are synthetic numpy signals with simple assumptions. Serum's filters, unison spacing, wavetable interpolation and effects were not tested.
- **Accuracy of any method on real synth presets**, except Modulation Discovery's proxy correlations. Published pitch and note numbers come from other material.
- **Serum 2 internals.** The Xfer web manual's section index was seen, but not wavetable frame sizes, unison spacing or the Frequency Estimation algorithm. A forum thread indicates 2048-sample cycles work. See the Serum parameter report.
- **Abstract or snippet-only sources:** Chowning 1973, Laitinen 2013, Sheng and Fazekas, Colonel and Reiss, Sound2Synth, Timoney et al., Callens and Cernak, Ratnam. They are cited with [U] where the claim relies on them.
- **Negative findings** (no filter-type classifier, no FM-vs-RM audio paper, no commercial wavetable retrieval study) rest on a few searches.
- **Node runtime parity:** I did not run any model in Node. Basic Pitch ran here in Python 3.11 with the CoreML model.
- **SerumRNN** was found (arXiv 2104.03876) but not read; it is a sound-matching and effect-programming result, so it is left to the sibling report.

## Appendix A: session experiments

The scripts behind these experiments were throwaway and are not kept in this repo.

- `exp1.py`: filter/source, phase, single-cycle residual, library match, AM/FM/RM, envelopes, LFO, stereo (numpy, scipy).
- `exp2.py`: pYIN at frame 4096 and Basic Pitch on 12 mono and 11 chord signals (librosa, basic-pitch in Python 3.11).
- `exp3.py`: my reimplementation of Matsumoto and Yatabe's search. It uses zero-padded nearest-bin lookup, not their non-uniform FFT, and it did not reproduce their clean accuracy.

Results from `exp1.py` section E3 are discarded: that estimator took the global cost minimum and picks voice subsets, as the paper warns. The hard-sync row in E4 is discarded because the test signal aliased.

## Appendix B: sources

Papers read in full or by table:

- CREPE, Kim et al.: https://arxiv.org/abs/1802.06182
- PESTO, Riou et al.: https://arxiv.org/abs/2309.02265
- Basic Pitch, Bittner et al.: https://arxiv.org/abs/2203.09893
- MT3, Gardner et al.: https://arxiv.org/abs/2111.03017
- Differentiable Wavetable Synthesis, Shan et al.: https://arxiv.org/abs/2111.10003
- Modulation Extraction for LFO-driven Audio Effects: https://arxiv.org/abs/2305.13262
- Modulation Discovery with DDSP: https://arxiv.org/abs/2510.06204
- General Purpose Audio Effect Removal: https://arxiv.org/abs/2308.16177
- Blind estimation of audio effects: https://arxiv.org/abs/2310.11781
- Guitar effects recognition, Comunità et al.: https://arxiv.org/abs/2012.03216
- Audio effect chain estimation, Take et al.: https://dafx.de/paper-archive/2024/papers/DAFx24_paper_53.pdf
- DDX7, Caspe et al.: https://arxiv.org/abs/2208.06169
- Review of DDSP, Hayes et al.: https://arxiv.org/abs/2308.15422
- Synthesizer inversion in symmetric spaces, Hayes et al.: https://arxiv.org/abs/2506.07199
- Instrumental, Bogdan: https://arxiv.org/abs/2603.15905
- Unison estimation, Matsumoto and Yatabe: https://web.tuat.ac.jp/~yatabe/papers/matsumoto_2022_9.pdf

Snippet or abstract only:

- InverSynth: https://arxiv.org/abs/1812.06349
- SerumRNN: https://arxiv.org/abs/2104.03876
- Sound2Synth: https://www.ijcai.org/proceedings/2022/682
- Callens and Cernak: https://arxiv.org/abs/2010.11167
- Ratnam-based blind_rt60: https://pypi.org/project/blind-rt60/
- Laitinen et al., JAES 2013: https://aes2.org/publications/elibrary-page/?id=17068
- Timoney et al., AES 2019: https://aes2.org/publications/elibrary-page/?id=20310
- Colonel and Reiss: https://www.eecs.qmul.ac.uk/~josh/documents/2022/21915.pdf
- Sheng and Fazekas: https://qmro.qmul.ac.uk/xmlui/handle/123456789/40945
- Chowning 1973: https://ccrma.stanford.edu/papers/synthesis-of-complex-audio-spectra-means-of-frequency-modulation
- ACE challenge: https://arxiv.org/abs/1606.03365 (fetched, used only for scope)

Docs and code:

- librosa pYIN: https://librosa.org/doc/0.11.0/generated/librosa.pyin.html
- librosa HPSS: https://librosa.org/doc/0.11.0/generated/librosa.decompose.hpss.html
- Essentia reference: https://essentia.upf.edu/algorithms_reference.html
- essentia.js core API: https://github.com/MTG/essentia.js
- Meyda: https://github.com/meyda/meyda
- Basic Pitch: https://github.com/spotify/basic-pitch and https://github.com/spotify/basic-pitch-ts
- PESTO: https://github.com/SonyCSLParis/pesto
- CREPE: https://github.com/marl/crepe, torchcrepe: https://github.com/maxrmorrison/torchcrepe
- onnxcrepe: https://github.com/yqzhishen/onnxcrepe
- RemFX: https://github.com/mhrice/RemFx
- mod_extraction: https://github.com/christhetree/mod_extraction, mod_discovery: https://github.com/christhetree/mod_discovery
- DDSP: https://github.com/magenta/ddsp, DDX7: https://github.com/fcaspe/ddx7
- dasp-pytorch: https://github.com/csteinmetz1/dasp-pytorch
- nara_wpe: https://github.com/fgnt/nara_wpe
- sms-tools: https://github.com/MTG/sms-tools
- demucs.onnx: https://github.com/sevagh/demucs.onnx
- madmom licence: https://github.com/CPJKU/madmom/blob/main/LICENSE
- Julius Smith on sines plus noise: https://ccrma.stanford.edu/~jos/sasp/Spectral_Modeling_Synthesis.html
- Serum 2 conversion: https://support.xferrecords.com/article/59-converting-samples-to-wavetables
- Serum 2 manual: https://xferrecords.com/web-manual/serum-2/welcome

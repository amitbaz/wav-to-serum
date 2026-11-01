# Recovering synthesizer parameters from audio: what the evidence says

Survey date: 2026-11-01. Written for a project that wants to rebuild a synthesized WAV as a Serum 2 preset.

**Marks used on claims**

- **[V]** verified: I read it in the primary source (paper PDF, code, or page) linked in that row or paragraph.
- **[I]** inferred: my own reading or calculation from verified facts.
- **[U]** unverified: only a search excerpt, vendor copy, or a secondhand mention.
- **[SYN]** the result was measured only on sounds the same synth rendered, usually from the authors' own sampling. It says little about real input.

## 1. Bottom line

1. **No published work runs search on Serum 2.** Sound2Serum is the only Serum 2 study I could read, and it uses a neural network with no search. So the practitioner's claim cannot be tested directly from the literature. Everything below is by analogy from Dexed, Surge XT, Helm, Massive, OP-1, TorchSynth and custom synths. [V for what I found; absence is a search result, not proof]
2. **The claim is half right.** Search on a fixed template does stall, and discrete choices do break the two most common continuous tools, gradients and CMA-ES. But discrete choices are not a wall: genetic search handles them natively, and supervised classifiers get mean categorical accuracy of 81 to 87% on commercial-style synths [SYN].
3. **The larger bottleneck is reachability, with waveforms as one part of it.** The search space omits what made the sound. Wavetables are one piece. Modulation routing, effects, filters and oscillator modes are bigger pieces, and most research setups switch them off. About 98% of presets in Serum 1's default library use modulation [V](https://arxiv.org/abs/2510.06204). Sound2Serum dropped all of it.
4. **The strongest recent results are hybrids.** A trained model proposes a whole program, then rendered audio from the real synth corrects it. On NSynth, this cut wMFCC from 10.04 to 5.96 on Dexed (n=200) [V](https://arxiv.org/abs/2608.03032). The neural stage alone did worse than that combination. No paper pits search alone against it on the same synth.
5. **Sound2Serum's bad score is not evidence about the method.** It trained for 3 epochs on 40K pairs. Comparable work uses 1 to 2 million pairs. Its failure measures under-training and a narrow parameter set.
6. **Expect "recognisably similar", not "identical".** The best human scores on input the synth did not render are about 3 to 3.5 out of 5 (SynthRL 3.01; AutoSynth 3.54 on generated audio, 2.80 on real recordings) and 65.8 out of 100 (Synplant 2).
7. **No study measures what a language model adds over a plain optimizer on synth matching.** The nearest evidence is audio effects, where a model picks modules and order far better than non-LLM baselines but sets continuous values no better.
8. **Commercial claims are untested.** I found no independent accuracy test of MicroMusic Replicate. Its KVR page shows 0 reviews. The one independent measurement of any commercial matcher is Synplant 2 inside the Sound2Serum listening test.
9. **Scores are not yet close to hearing for near matches.** Timbre metrics agree with human triplets about 70% of the time, on sounds that differ widely. I found no human similarity data for near-miss synth sounds. See section 11.

## 2. Testing the practitioner's claim

Claim as given: search alone was not enough, and waveforms and other non-min-max choices were the hard part. I could not find where this claim was published, so I tested the idea rather than the experiment.

### Evidence for

| Evidence | Finding | Limit |
|---|---|---|
| [Hayes et al. 2025](https://arxiv.org/abs/2506.07199) [V] [SYN] | Surge Simple (92 params, no discrete, no routing): MSS 3.18, wMFCC 5.57. Surge Full (165 params, many discrete, routing, effects): MSS 6.13, wMFCC 9.63. Error roughly doubles. | Confounded: Full also has a wider sonic range. The share due to discrete parameters is unknown. [I] |
| [Instrumental 2026](https://arxiv.org/abs/2603.15905) [V] | CMA-ES hit a floor: the target had H3 > H2, which a saw and square mix cannot produce. The author blames oscillator type. Adding FM (+17%) or Chebyshev waveshaping (+29%) made 10K-evaluation results worse. | n=1 target, custom 28-parameter synth, single-author preprint. |
| [Sound2Serum 2026](https://projekter.aau.dk/sound2serum-neural-sound-matching-system-for-serum-2-6027defd.html) [V] | Classification head reached about 0.09 validation accuracy across wavetable, sub and noise choices. The author says a wrong wavetable sets the whole spectral character. | From the ablation runs on 1/3 of the data, after minimal training. Neural, not search. Chance for 144 wavetables is 0.7%, so 0.09 is above chance. [I] |
| [White Box Search 2023](https://pixl.cs.princeton.edu/pubs/Yang_2023_WBS/yang-white-box-2023.pdf) [V] | Saw and square discontinuities and categorical waveform choice break normal autodiff, so a special gradient rule was needed. | Applies to gradient methods only. |
| [DiffMoog 2024](https://arxiv.org/abs/2401.12570) [V] | Used Gumbel-Softmax for categorical parameters. Spectral loss alone failed systematically and FM chains refused to converge. High precision remained "a formidable challenge". | Failure is attributed to frequency gradients, not to discreteness. |
| [DDSynth-RL 2026](https://arxiv.org/abs/2608.03032) [V] | Flow matching was worse than discrete models on Dexed (wMFCC 7.83 vs 6.30 and 6.65 in-domain). Authors blame relaxing discrete controls into continuous space. | Their interpretation. n=200. Hayes's flow model beats regression on Surge, so relaxation is not fatal. |

### Evidence against

| Evidence | Finding | Limit |
|---|---|---|
| [Yee-King et al. 2018](https://research.gold.ac.uk/22516/1/myk_lf_vsti_programming.pdf) [V] [SYN] | On 180 Dexed items, a plain hill climber tied the best network: total MFCC error 3769 vs 3765. GA 5399, MLP 5557, LSTM 5455. Both leaders put about 25% of matches in the close band. | Routing algorithm held fixed, so structure was not searched. Up to 7 hours for 1000 epochs. Authors call their GA simplistic. |
| [PresetGen 2016](https://research.chalmers.se/en/publication/540193) | NSGA-II on the OP-1 was reported as human-competitive against 3 designers [V from abstract]. Slide summary: 8 targets, 14 listeners, about 17% more similar, and 7 engines [U]. | 5 hours on 50 cores for 2 s of sound, per [Yee-King](https://research.gold.ac.uk/22516/1/myk_lf_vsti_programming.pdf) [V]. I could not open the paper, so how it searched discrete choices is unverified. |
| [Hagiwara et al. 2022](https://arxiv.org/abs/2210.10857) [V] | On ESC-50 animal sounds with TorchSynth: GA 0.633, Metropolis 0.658, Bayesian optimization 0.737, differential evolution 0.738, random 0.861, CMA-ES 0.891, Adam 1.553, encoder 2.131. Population search won; gradient and encoder lost. | Short 6-page paper. CMA-ES capped at 200 iterations. Non-musical targets. |
| [InverSynth II 2023](https://archives.ismir.net/ismir2023/paper/000076.pdf) [V] [SYN] | Mean categorical accuracy: FM 94.04%, DX7 86.74%, TAL-NoiseMaker 81.17%. | Averages include easy switches and no majority-class baseline is given. [I] |
| [DDSynth-RL](https://arxiv.org/abs/2608.03032), [AutoSynth](https://arxiv.org/abs/2610.10774), [InverSynth](https://arxiv.org/abs/1812.06349) [V] | All three turn continuous knobs into bins (25 or 128) and treat everything as discrete tokens, and they work. Discreteness itself is tractable for a sequence model. | Needs millions of training pairs. |

### Verdict

- **Search alone on a fixed template:** the claim holds. Instrumental reached 90% of its gain in the first 10K evaluations, and the other 90K gave about 0.07 loss. [V] It then sat at an "architectural floor". The optimizer ran out of things to change, not out of evaluations.
- **Discrete choices as the hard part:** partly. They are hard for gradients and for CMA-ES, which assumes continuous variables. [I] They are natural for genetic search and for classifiers. The cost is budget and data, not a theoretical block.
- **What the claim misses:** wavetable choice is one structural decision among several. Instrumental's own floor is an expressivity problem, and picking from a fixed list only helps if the list contains something close. [I] Sound2Serum notes this directly: a target with no good table in the pool matches badly however well other parameters are set. [V]

## 3. The real bottlenecks, in order

This ordering is my judgement. [I] The facts under each one are verified unless marked.

1. **Reachability of the sound.**
   - Sound2Serum froze modulation, used no filters and no effects, and picked 8 test sounds with little modulation or effect. [V]
   - It started with 177 parameters including random modulation routing, and generated presets "bore no resemblance" to the target. [V]
   - Hayes 2026 disables Surge effects even in its newest off-manifold test. [V]
   - AutoSynth, which models variable-length modulation routes, led on the acoustic metrics other than RMS on FSD50K, which its authors say may reflect that wider expressive capacity. [V, their hedge] The comparison uses different synths per system.
2. **Audio feedback from the real synth.** Parameter loss treats a wrong wavetable and a wrong sustain alike. [V, Sound2Serum] Moving to render-based reward gave SynthRL a 17.9% mean gain on out-of-domain sounds, and took DDSynth-RL's NSynth MSS from 4.41 to 3.11. [V]
3. **Data and compute.** 40K pairs (Sound2Serum) vs 1M for 16 parameters (Bruford), 2M (Hayes, AutoSynth), and "months" of training (Genopatch). [V] That is 25 to 50 times the data, for many more parameters than Bruford. [I]
4. **The metric.** See section 6. An optimizer exploits whatever the loss misses. Instrumental's 29-parameter run drifted detune to +24 semitones and "cheated" the loss. [V]
5. **Serum 2's render path.**
   - Modulation routing, wavetable data and LFO shapes cannot be set through exposed VST parameters. Each candidate needs a preset file reload through a bank toggle. [V, Sound2Serum]
   - The thesis measured 10K 5-second clips in 11 m 20 s including preset generation, with up to 8 workers. [V] That is about 15 per second. [I]
   - So 10K evaluations cost about 11 minutes and 100K about 2 hours. [I] Instrumental's custom synth did 553 per second. [V] Vital via `vita` renders a 3-second note in 0.05 s on one core, per the [synth-rl README](https://github.com/luwux/synth-rl). [V, repo claim]
6. **Ambiguity.** Many presets give one sound, and swapped oscillators are identical. [V, Hayes 2025] Serum 2 has three interchangeable wavetable oscillators, so parameter error is a poor target. [I]

## 4. Methods compared

| Method | Discrete choices | Continuous | Best result seen | Synth and conditions |
|---|---|---|---|---|
| Hill climber | Can step them | Good with budget | Tied best on Dexed, 180 items [V] [SYN] | Fixed routing, up to 7 h per 1000 epochs |
| Genetic algorithm | Native | Slow | Best on TorchSynth, weak in Yee-King [V] | Results depend strongly on implementation and budget |
| NSGA-II (PresetGen) | Reported on 7 engines [U] | Yes | Human-competitive vs 3 designers [V abstract] | OP-1, 5 h on 50 cores |
| CMA-ES | Poor; Instrumental avoids them with continuous mix weights [V] | Strong | Loss 2.09, beat Adam 4.60 [V] | n=1, custom synth. Lost to random search at 200 iterations in Hagiwara |
| Learned evolution strategy | Not established | Good | Best of those tried in [CTAG](https://arxiv.org/abs/2406.00294) [V] | Text target, 78-parameter synth, 300 iterations |
| Bayesian optimization | Not tested on synth categoricals | Middling | 0.737 in Hagiwara [V] | One baseline. I found no mixed-variable study |
| Neural regression or classification | Softmax heads | Binned or scalar | AST on Massive: SC 0.616 vs MLP 4.608 [V] [SYN] | 1M pairs, 16 continuous params, no categoricals |
| Differentiable synth (DDSP) | Gumbel or special rules | Good for simple chains | Works on basic chains, FM fails [V] | Must rewrite the synth; not possible for closed Serum |
| Neural proxy | Via proxy | Via proxy | Compact audio embeddings help, cost is high [V] | Dexed, Diva, TAL-NM; 10M synthetic presets |
| Flow matching | One-hot, relaxed | Strong | Surge Full: MSS 6.13 vs AST 14.73 [V] [SYN] | 2M pairs, 165 params |
| Joint flow matching | One-hot | Strong | Surge real audio: MSS 7.68 vs baseline 15.50 [V] | 10K real test clips; no listening test. SOT is worse (0.317 vs 0.232) |
| Discrete diffusion | Native tokens | 25 bins | Near autoregressive, no fixed order needed [V] [SYN] | Dexed, n=200 |
| Autoregressive program model plus RL | Native tokens, routes included | 128 bins | Listeners rated it above both baselines [V] | Helm, 2M pairs, 10 listeners |
| RL fine-tuning | Native if the policy is discrete | Works | Out-of-domain MOS 3.01 vs Sound2Synth 1.94 [V] | Dexed, Surge presets as targets, 64 raters |

## 5. Key papers

**[Sound2Serum, Hansen 2026](https://projekter.aau.dk/projekter/files/835339029/Master_Thesis_Kevin_Thor_Hansen.pdf)** (Aalborg master's thesis, supervisor Cumhur Erkut). [V] Multi-modal net adapted from Sound2Synth. 45 parameters: 40 regression, each as 256 bins, and 5 classification (three wavetables from 144, sub shape from 6, noise from 93). Dataset: 40K pairs, C3 only, mono, four categories, 70/20/10 split, all synthetic. Training stopped at a 12-hour limit after 3 epochs, and the loss curve had not flattened.

Test: 8 Splice one-shots with little modulation or effect. 19 listeners ran MUSHRA, 7 were excluded by screening, and results barely changed. Screened means: reference 98.7, Synplant 2 65.8, 300 Hz low-pass anchor 39.9, Sound2Serum 19.9. The model scored below the anchor in 82% of trials, even though each stimulus was the best of several candidates by MFCCD. Synplant 2 won on multi-scale spectral loss on 8 of 8 and on MFCCD on 7 of 8. Agreement between metrics and listeners was rank order only, across a large gap, with no correlation computed. The author leaves finer agreement open.

**[Synth Permutations, Hayes et al., ISMIR 2025](https://arxiv.org/abs/2506.07199).** [V] Permutation-aware conditional flow matching on Surge XT with 2M pairs per dataset. Out-of-domain for the Full model: NSynth MSS 11.04, FSD50K MSS 15.40. Code base for [synth-setter](https://github.com/tinaudio/synth-setter), which defaults to Surge XT and whose README shows no Serum results.

**[Off-manifold robustness, Hayes, ISMIR 2026](https://arxiv.org/abs/2609.29320).** [V] Models audio and parameters jointly, so it learns around the synth's output manifold rather than only on it. Surge real audio: MSS 7.68 vs 15.50, wMFCC 9.37 vs 14.91. Dexed real audio: 7.98 vs 13.03. Surprise: adding 617,016 unlabeled real clips barely helped; the joint formulation did the work. Author asks for human evaluation and failure-mode analysis. None is reported yet.

**[DDSynth-RL, Wu et al., ISMIR 2026](https://arxiv.org/abs/2608.03032).** [V] Masked discrete diffusion, then GRPO reward fine-tuning through the black-box synth. On NSynth: wMFCC 10.04 to 5.96, MSS 4.41 to 3.11. In-domain got worse, 6.65 to 10.92, because training moved toward NSynth. The authors also report that slight overfitting to human presets gave better listening quality with worse metrics, and suggest human presets may suit this task better than random sampling.

**[AutoSynth, Wu et al., Oct 2026](https://arxiv.org/abs/2610.10774).** [V] Preprint. Predicts MIDI, then parameters, then variable-length modulation routes, as one token sequence with a grammar mask. Trained from 2M perturbations of Helm's 274 presets, then GRPO with eight rewards. Listener alignment, 1 to 5, read from extracted figure labels: 3.54 (AutoSynth), 1.32 (Synth Permutations), 2.62 (DDSynth-RL) on generated audio, and 2.80, 1.44, 2.20 on FSD50K. Ten listeners, 20 questions. Each system uses a different synth, and the first author also led DDSynth-RL.

**[SynthRL, Shin and Lee, IJCAI 2025](https://www.ijcai.org/proceedings/2025/1129.pdf).** [V] Dexed, 84 numeric and 60 categorical parameters, about 30K human presets. Listening: 64 raters and 64 targets for MOS, 96 raters for ABX. In-domain MOS 4.29. Surge presets as out-of-domain targets: 3.01, against 1.94 for Sound2Synth.

**[Bruford et al., DAFx 2024](https://arxiv.org/abs/2407.16643).** [V] [SYN] Native Instruments. 1M Massive pairs, 16 hand-picked continuous parameters sampled from factory preset distributions, rendered in about 24 hours on one Mac mini. Failure mode: detuned oscillators, where a small parameter error is a large audible error. No categoricals by design, so it says nothing about waveforms.

**[Syntheon](https://github.com/gudgud96/syntheon).** [V from code] No paper. Vital only. Its model `WTSv2` has a wavetable synth module, wavetable and attention outputs, and multi-scale FFT. That suggests it learns wavetables instead of picking from a list. [I] Its 138-times-worse score in Instrumental was a synth mismatch, as that paper says. It is not a fair test. [V]

**[SerumRNN, 2021](https://arxiv.org/abs/2104.03876).** [V for scope] Serum 1, effects only: five effects chosen and set step by step. Not oscillator recovery. I did not extract its numbers.

**Wavetable learning.** [Differentiable Wavetable Synthesis](https://arxiv.org/abs/2111.10003) reaches high fidelity with 10 to 20 learned tables. [V] Sound2Serum warns that a learned table has no name or identity, which weakens editability. [V]

## 6. Metrics

Measures that have some human evidence:

| Metric | Human evidence | Weakness |
|---|---|---|
| MFCC distance | 68.7% agreement with human timbre triplets, beating many trained models, per [2608.18226](https://arxiv.org/abs/2608.18226) [V] | Weak on pitch, per [Turian and Henry](https://arxiv.org/abs/2012.04572) [V]. Yee-King's cutoffs (under 10 very close, under 20 close) rest on informal listening [V] |
| wMFCC (DTW-aligned) | Standard since Hayes 2025; no direct human validation found | Forgives timing, so pair it with an envelope check |
| Multi-resolution STFT (MSS) | Agreed with listeners in rank at a coarse gap only (Sound2Serum) [V] | Pointwise, so blind along frequency [V, Hayes 2025] |
| Spectrogram MAE alone | SynthRL shows it rewarding a transient match to a sustained target, scoring lower than a near-identical pair [V] | Do not use alone |
| Spectral convergence | [Reported as less correlated with human perception](https://archives.ismir.net/ismir2023/paper/000076.pdf) [V, secondhand within that paper] | Still widely reported |
| SOT | Added for pitch sensitivity (Hayes). Human validation not found | Energy-invariant |
| CLAP embedding | 70.8 to 71.8% on triplets [V]. But CTAG's better CLAP did not make it rank higher with listeners (AutoSynth) [V] | Measures meaning more than match |
| Mixed reward | SynthRL's three-part reward: Pearson 0.85 with MOS (120 raters, 30 per pair) [V] | The best number here. Not validated beyond that setup |
| Parameter error | [Not a quality measure](https://research.gold.ac.uk/22516/1/myk_lf_vsti_programming.pdf): many presets give one sound [V] | Fine as a diagnostic: [2608.27698](https://arxiv.org/abs/2608.27698) agrees with listeners on the top loss in 5 of 7 scenarios [V] |

General findings:

- No universal loss exists. [Salimi et al.](https://arxiv.org/abs/2506.22628) ran 16 synth and loss pairs with 300 runs each, and the best loss depended on the synth. Automatic measures generally agreed with two blinded author-listeners, but occasional divergence means manual checks are still needed. [V]
- Listeners and metrics do split. Listeners preferred AutoSynth despite DDSynth-RL's higher RMS similarity. [V]
- Report several metrics, including one for pitch and one for envelope, and listen. Fit across several pitches, as Instrumental does, to avoid overfitting one note. [V for the method, I for the advice]

## 7. Language models driving the process

- **No published comparison exists** of a language model with tools against a plain optimizer on synth matching. [V for what I found]
- **[LLM2Fx-Tools, ICLR 2026](https://arxiv.org/abs/2512.01559)** is the closest, and it covers effects chains from dry and wet audio pairs, not synths. [V]

| System | Module accuracy | Order correlation | Param MAE |
|---|---|---|---|
| LLM2Fx-Tools | 80% | 0.56 | 0.23 |
| Gemini 2.5 Flash | 78% | 0.54 | 0.32 |
| MultiTask | 61% | 0.00 | 0.23 |
| Regression | 55% | -0.03 | 0.20 |

  Removing chain-of-thought dropped module accuracy to 67%. Perceptual distance was close to MultiTask and much worse than DeepAFx-ST (3.13 vs 1.75), which trains on audio directly. So the language model added discrete planning, and no continuous precision. [V for numbers, I for the reading]
- **[synth-rl](https://github.com/luwux/synth-rl)** is built for this exact question on Vital, including a muted-audio control. Its README says current models "are not good at this, especially when the answer is only in the audio". It publishes no result table. [V]
- **[serum-mcp](https://github.com/Celian-mrc/serum-mcp)** writes Serum 2 presets from text and does not render or hear audio, so it has no match loop. [V] Its `sample_source` slices a file into a wavetable. [V] That is a possible way around picking from a fixed list. [I]
- **[sound-to-patch](https://github.com/Akurganow/sound-to-patch)** is an early release with no matching results. It records Audio Flamingo as "judged weak on synth attributes". [V]
- **Note on GRPO:** DDSynth-RL and AutoSynth use GRPO, a reward method from language model training, but no language model is involved. [V]

Likely role for a language model [I]: choose the template, the structure and which wavetables to try, read metric reports, and diagnose. It should leave continuous values to an optimizer. This fits the effects result but has not been tested on a synth.

## 8. Commercial tools

| Tool | How it appears to work | Vendor claims | Independent evidence |
|---|---|---|---|
| [MicroMusic Replicate](https://www.kvraudio.com/product/replicate-by-micromusic) | Unknown. [Synthtopia](https://www.synthtopia.com/content/2024/05/13/micromusic-ai-powered-synth-preset-generator-recreates-patches-from-audio/) says ML finds parameters [V]. One listing says it compares to a preset database, then calculates parameters [U] | "Multiple specialized AI models", Vital and Serum, stem splitting, $89.99 subscription, v2.0.2 [V from KVR] | None found. KVR shows 0 reviews [V]. One Synthtopia commenter said misses still gave nice patches. Anecdote, 2024, Vital-only era |
| [Synplant 2 Genopatch](https://cdm.link/2023/10/the-road-to-synplant-2/) | Neural nets inverse-trained on semi-random sounds from its own synth, with months of training and deliberately low confidence settings, so early guesses are wild. Its engine is designed to mutate well [V, developer interview] | Interview only | Best evidence available: 65.8 out of 100 in Sound2Serum, 8 sounds, 12 screened listeners, different synth from Serum [V]. [MusicTech](https://musictech.com/reviews/plug-ins/sonic-charges-synplant-2-review/) 8/10. Non-synthetic sounds less accurate per [MusicRadar](https://www.musicradar.com/reviews/sonic-charge-synplant-2-review) [U, via search excerpt] |
| [Audial sound2serum](https://glama.ai/mcp/servers/AudialAI/audial-mcp/tools/sound2serum) | Hosted function, [merged to its SDK on 2026-10-30](https://github.com/AudialAI/audial-sdk/pull/7) [V]. Method not stated | One dry note, 1 to 4 s; result summary may say the match is weak [V] | None found |
| [Preset Mutator](https://kreativsound.com/posts/audio-alchemy-free-launch-2026-04-02) | Local audio analysis, three preset variations; Serum 2 in beta [V] | Starting points | None found |
| UnPack | Unknown | "Any audio into a Serum preset in seconds" [U, search excerpt; page blocked] | None found |

The design lesson from Genopatch: it controls its own engine and was built to reward mutation. [V] A Serum matcher has neither advantage. [I]

## 9. What this means for the project

Recommendations, all [I]:

1. **Do not treat wavetable choice as one more search dimension.** Rank tables with a cheap offline step, such as spectra or embeddings of pre-rendered tables, then run continuous search inside the top few. Test a custom table cut from the target as a second route.
2. **Search structure and values separately.** Use an outer choice of template (routing, filter, effects) and an inner continuous optimizer. Budget about 10K evaluations per candidate, the point where Instrumental's returns collapsed. At Serum's 15 per second this allows only a few candidates per hour, so the outer step must be selective.
3. **Constrain ranges to musical values** before optimizing. Instrumental converged reliably only after this.
4. **Score with a mix:** multi-resolution mel, wMFCC, SOT, RMS envelope, a pitch term and a semantic embedding. Normalise loudness first.
5. **Copy Sound2Serum's listening test but fix the anchor.** Its 300 Hz anchor sat too high on basses. The thesis suggests a random preset. Synplant 2 at 65.8 is the bar to beat, on a test set that includes modulated sounds.

## 10. Not verified

- **The practitioner's experiment.** I could not locate it, so I do not know the synth, budget or metric.
- **Any search on Serum 2.** None found.
- **The share of error caused by wavetable choice.** No paper isolates it. Hayes's Simple vs Full gap is confounded.
- **Replicate's method and accuracy.** Its site renders empty to my fetcher. I did not test the tool. The aidive page returned 403. KVR forum and Reddit searches found no user reports.
- **PresetGen.** The PDF failed and the text file is gone, so I have the abstract and a search summary of slides. Its handling of discrete engines is unconfirmed.
- **Christian Tapp's Serum Agent post.** The page renders empty. A search excerpt describes a tool-calling agent writing presets. No evaluation seen.
- **MusicRadar's text.** My direct parse failed, so that claim comes from a search excerpt.
- **AutoSynth's listener values** come from figure labels in PDF text. The order is inferred from the legend, though the text confirms AutoSynth led.
- **Hagiwara's sample size** is not in the parts I read.
- **Not read in full:** Masuda and Saito, Le Vaillant, Faronbi, Sound2Synth's result tables, SerumRNN's numbers, and neural proxies' numeric tables.
- **Peer review status.** AutoSynth and Instrumental are preprints. The two ISMIR 2026 papers carry proceedings headers on arXiv, and I did not confirm them elsewhere.

## 11. How close can a score get to what a person hears?

### Short answer

- **Across clearly different timbres:** about 70% triplet agreement with human ratings. MFCC, a simple feature, stays competitive with trained models. [V]
- **Across random synth pairs:** one mixed reward reached Pearson 0.85 with listener scores (SynthRL). [V] Random pairs are the easy case, because most differ a lot. [I]
- **Among near matches, which is the project's real risk:** unknown. I found no human similarity data for this case. Sound2Serum says the same about its own results: agreement was only shown across a large quality gap. [V]
- **What purpose-built data can do:** in other domains, a judge trained on human comparisons clearly beats embeddings. Speech emotion went from 65.51% (best plain cosine) to 74.96% on about 3,000 comparisons. [V] Vision reached a reported 96.16%. [U]

### 11.1 Perceptual metrics and how well they predict people

| Measure | Test | Result | Limits |
|---|---|---|---|
| [CDPAM](https://arxiv.org/abs/2102.05109) | Speech quality scores, 8 datasets in its table | Spearman 0.61 to 0.93 [V] | Tested on speech, not on instruments or synths in the paper |
| CDPAM on timbre | [timbremetrics](https://arxiv.org/abs/2507.07764) | "Does not adapt well to musical timbre" [V] | Trained on low-level speech distortion. Exact score is in a figure |
| MFCC | timbremetrics | 68.7% in [2608.18226](https://arxiv.org/abs/2608.18226) [V]; 72.4% (cosine) in the [package README](https://github.com/tiianhk/timbremetrics) [V] | The two numbers differ, likely from settings [I]. Weak on pitch [V] |
| LAION-CLAP | timbremetrics, via 2608.18226 | 70.8 to 71.8% [V] | Plain embedding |
| CLAP style embedding (Huang) | timbremetrics | Best of 18 representations, "markedly superior" [V] | Value is only in a figure, which I could not read |
| Style embedding from a Vital sound-matching model | timbremetrics | Clearly above its base embedding [V] | 10-parameter Vital model, 500K samples. Its task embedding overfits with training [V] |
| FM encoders | timbremetrics | 68 to 71%, trained only on DX7 sounds [V] | Near MFCC |
| PANNs | timbremetrics | 61.4%, below MFCC [V] | |
| MSS | timbremetrics | Underperforms [V] | Exact score is in a figure |
| JTFS | timbremetrics | Moderate rank scores, poor absolute scale [V] | |
| [MFCC distance on NSynth](https://www.dafx.de/paper-archive/2024/papers/DAFx24_paper_76.pdf) | Subjective listening | Useful overall, but often missed envelope and modulation errors [V] | The paper's reading of its listening, no rating study |
| CLAP and MuQ on [Slakh ABX](https://arxiv.org/abs/2601.19109) | 281 listeners | 71.9% and 72.4% for full mixes across tracks. About 66% on guitar, against 75.8% for a human-tuned model [V] | Music segments, not single synth notes |
| CLAP in [MATCHA](https://arxiv.org/abs/2609.00987) | 83 experts | Correlates strongly with timbre judgments [V] | Music excerpts. Human timbre agreement was lower than for melody |

**Timbre space studies.** The 21 datasets total 334 sounds and 2,614 ratings, so the authors use them for testing, not training. [V] They were built with pitch, loudness and duration held fixed. [V] A real preset match does not hold those fixed, and these sets were not designed around near misses. [I]

**Synth-specific sets inside timbremetrics.** [V for the list]

- Vahidi 2020: 15 subtractive sounds, 35 raters.
- McAdams 1995: 18 FM-simulated and hybrid sounds, 22 raters.
- Zacharakis: 24 acoustic and synth sounds, 20 and 33 raters.

Per-dataset scores are not printed in the paper, so **I cannot give a synth-only score for any metric**. The package can compute one. [I]

**[Vahidi et al. 2020](https://arxiv.org/abs/2009.11706) is the closest synth study.** [V] It used saw or pulse sources, optional FM, and an enveloped low-pass filter, all at A4 and 1 second. A four-dimensional space fit well (Stress-1 .047, R² .91). Dimension 1 tracked spectral flux, complexity and log-attack time, which were entangled by the filter envelope. So for synths, movement of the spectrum is a main perceptual axis. Plain time-averaged features would miss it. [I]

**Warnings for the project.**

- Similarity learned for one kind of change may not transfer to another, citing DreamSim. [V, Tian et al.]
- A task embedding lost alignment with human ratings as training went on. [V] A sound-matching model getting better is not proof that its internal distances are getting more human. [I]

### 11.2 Has a measure been trained on human judgments of synth sounds?

**I found none trained on human A/B or triplet judgments of synthesizer sounds.** That is a result of the searches listed in 11.5, not proof that none exists.

Nearest work:

| Work | Sounds | Judgments | Public? | Trained on them? |
|---|---|---|---|---|
| [timbremetrics](https://github.com/tiianhk/timbremetrics) | 334, a few synth-related | 2,614 averaged ratings | Audio and ratings in the repo [V]; no license file found by the GitHub API [V] | No, test only |
| [Esling et al. 2018](https://arxiv.org/abs/1805.08501) | Instrument notes | Ratings from timbre studies | Not checked | Used to regularize a VAE space [V] |
| [Lostanlen et al. 2020](https://arxiv.org/abs/2007.10926) | 78 instrumental notes | 31 people free-sorted them | [Yes](https://github.com/mathieulagrange/lostanlen2020jasmp) [V, per paper] | Yes, a linear metric over scattering features [V]. Not synths |
| SynthRL reward | Dexed and Surge | 120 raters, 30 per pair | Not checked | Hand-designed, then validated. Not trained on ratings [V] |
| [Inst-Sim-ABX](https://arxiv.org/abs/2502.02138) | Slakh stems and mixes | 26,898 valid answers, 586 sessions, 281 unique subjects, 480 ABX items [V] | [Yes](https://github.com/zume06/Inst-Sim-ABX-Dataset) [V, per paper] | Yes, used to fine-tune Cascade and D-CSN [V]. Slakh is rendered music, not preset comparison |
| [Synth1B1](https://arxiv.org/abs/2104.12922) | Synth presets | None; the authors report lacking a perceptually accurate distance [U, search excerpt] | Audio yes | No |
| [Audio Doppelgängers](https://proceedings.iclr.cc/paper_files/paper/2025/file/b43a0e8a35b1c044b18cd843b9771915-Paper-Conference.pdf) | Perturbed synth sounds | None visible in what I read | Not checked | Contrastive, no human labels [I, from a partial read] |

How much data others needed:

| Dataset | Domain | Size | Note |
|---|---|---|---|
| [SES-Bench](https://arxiv.org/abs/2609.32504) | Speech emotion | 2,974 train and 848 test triplets, 5 annotators each [V] | About 15K training ratings [I]. Took accuracy to 74.96% |
| [MATCHA](https://arxiv.org/abs/2609.00987) | Music | 1,105 assessments, 83 experts, 300 cases [V] | Public [V], one subset pending. An evaluation set |
| [NIGHTS](https://arxiv.org/abs/2306.09344) | Images | 20K [V, via Tian] | Reported 96.16% [U] |
| [DPAM](https://arxiv.org/abs/2001.04460) | Speech | About 55K pairs, 1,812 valid sessions [V] | Authors later said it needs too many labels [V, CDPAM paper] |
| [VoxSim](https://arxiv.org/abs/2407.18505) | Voices | Nearly 70K [U] | |
| THINGS | Images | 4.7M [V, via Tian] | |

### 11.3 Reporting similarity per sound-design aspect

**I found no published system that scores one match across tone, voicing, filter, envelope, movement and effects.** Scope is in 11.5. Coverage by aspect:

| Aspect | Closest published work | What it gives | Gap |
|---|---|---|---|
| Tone | [Timbre traits, 2026](https://arxiv.org/abs/2606.30369) | 20 traits per sound from CLAP. r = 0.66 against human ratings; human inter-rater estimate .698 [V] | Trained on 31 RWC instruments. Scores one sound, not a pair, though two profiles could be diffed [I] |
| Filter | [Partial Parameter Distance](https://arxiv.org/abs/2608.27698) | Recovery of cutoff, compared with blinded listening [V] | Compares losses across scenarios. Not a per-preset report |
| Envelope | RMS-envelope cosine (Hayes, AutoSynth) [V] | Loudness envelope only | Dataset averages. Filter envelope not separate |
| Movement | [Modulation Discovery](https://arxiv.org/abs/2510.06204) | L1, PCC and shape metrics per curve, for envelope, filter and wavetable modulation [V] | Works in DDSP synths, on known modulators |
| Effects | [SerumRNN](https://arxiv.org/abs/2104.03876), LLM2Fx-Tools | Which effect, in what order [V] | Predicts effects, does not score them |
| Voicing | None found | | Unison, detune and stereo width are unscored in what I read |

Partial precedents for a report format:

- **AutoSynth** names what each metric stands for: semantics (CLAP), spectral envelope (wMFCC), energy distribution (SOT), time-frequency structure (MSS), loudness envelope (RMS). [V] But it reports dataset averages.
- **Sound2Serum** shows a per-metric breakdown in its app: MFCCD and MSS. [V] That is two distances, not aspects.
- **[sound-to-patch](https://github.com/Akurganow/sound-to-patch)** writes an aspect report for one stem: level, spectrum, band edge, stereo image, glides, vibrato. [V] It is not a comparison and has no human validation.
- **MATCHA** collects human judgments per attribute, including timbre, with an A, B or Neither choice. [V] This is the best template for labels, though at music level.
- **SonicBench** tests 12 attributes separately, including brightness and reverberation. [V] Useful as a checklist.

Caution: [Vohra and Akama](https://arxiv.org/abs/2601.19109) tried similarity as a weighted sum of instrument stems, and it consistently did worse than the full mix (84.6% down to 83.2% in one setup). [V] A sum of parts may lose to the whole. So aspect scores should explain a result and not automatically replace the overall score. [I]

### 11.4 Audio language models as judges

**I found no test of an audio language model judging timbre similarity against human similarity ratings.** Scope is in 11.5. Closest evidence:

| Study | Task | Humans | Models |
|---|---|---|---|
| [SonicBench](https://arxiv.org/abs/2601.11039) timbre | Instrument identity, comparison and recognition. Differences well above human limits | 1.00 and 0.93 (3 people, 240 items) | Qwen3-Omni 0.70 and 0.75; Kimi-Audio 0.49 and 0.68; GPT-4o-Audio 0.43 and 0.49 |
| SonicBench brightness | Same design | 0.93 and 0.93 | Qwen3-Omni 0.92 and 0.83; Kimi-Audio 0.81 and 0.81; GPT-4o-Audio 0.68 and 0.78 |
| SonicBench overall | 12 attributes, 36 systems | 91% | Best 72%; about half near chance |
| [SES-Bench](https://arxiv.org/abs/2609.32504) | Speech emotion, reference vs two candidates | Ground truth | Gemini 3.8 Flash 60.63%, below plain embedding cosine at 63.46 to 65.51% and the trained judge at 74.96%. Qwen3-Omni 3.15%, so far below chance that output failure seems likely [I] |
| [Speaking style](https://arxiv.org/abs/2506.05984), [full-duplex voice](https://arxiv.org/abs/2607.07985) | Speech | Human agreement | Roughly human on many dimensions, weaker on audio clarity (about 0.25 vs 0.47) [U, search excerpts] |
| [MATCHA](https://arxiv.org/abs/2609.00987) | Human vs metrics | | No language model tested in what I read |

Key points:

- SonicBench found that models lack the comparison advantage humans show. [V] Comparison is exactly what a judge must do.
- Linear probes on the same frozen audio encoders reached at least 0.60 even when the full models failed. The authors place the bottleneck in alignment and decoding, not in hearing. [V] So a small trained head on an encoder may beat prompting the whole model. [I]
- Speech judging results do not carry over to timbre. The strong speech results are in the domain these models are trained on. [I]
- [synth-rl](https://github.com/luwux/synth-rl) has `--mute-audio` and `--blind` controls that would test whether a model really listens on Vital, but it publishes no scores. [V]
- All of this is prompted use. I found no study of an audio language model fine-tuned on timbre comparisons. [V for what I found]

### 11.5 What I searched

Search run on 2026-11-01 with the WebSearch tool, English only. Queries covered:

- timbremetrics and triplet agreement with human timbre ratings
- CDPAM and learned perceptual metrics on music and synth sounds
- learning a metric from human triplets on synth sounds, and crowdsourced timbre datasets
- human similarity judgments of synth presets, including odd-one-out
- synth timbre spaces, MDS, and neural embedding correlation
- per-aspect or per-attribute scoring in sound matching, disentangled similarity, per-metric reports
- audio language models on pairwise timbre, Qwen, Audio Flamingo, Gemini, GPT-4o
- language models as judges of music or sound similarity
- paired-comparison sample sizes and small-data calibration

I also read the 2507.07764 dataset table, 2608.18226's table and the `timbremetrics` repo. One reference lead, "Not Too Generative, Not Too Discriminative", turned out to be about images and was dropped.

Not covered: direct searches of Google Scholar, IEEE Xplore, ACM DL, Zenodo or Hugging Face datasets; paging through ISMIR, DAFx, ICASSP or Timbre conference proceedings; non-English work; theses other than those named; commercial tools' internal evaluations. MMAU, MMAR and RAIL were seen in results, but I did not check them for a pairwise timbre task. A small study in a timbre or psychoacoustics venue could easily have been missed. Each "I found none" above is limited to this scope.

### 11.6 Where the project could do something new

All [I]. In the scope searched, the combination below appears unpublished.

**The gap:** human judgments on near-miss synth sounds, drawn from a real matching pipeline, with labels per sound-design aspect.

1. **Build near-miss triplets from the pipeline's own output.** Use one target and two rendered candidates that existing metrics rank close together. Prioritise pairs where metrics disagree, since those carry the most information. Rate A, B or Same, as in MATCHA and SES-Bench. No dataset I found targets this case.
2. **Ask for the overall choice, then one or two aspects.** "Which is closer overall?" then "Closer on envelope?", and so on. This gives per-aspect ground truth, which I could not find anywhere for synths.
3. **Measure before training.** Run about 300 triplets with 5 raters: 1,500 judgments, about 5 hours of listening at 12 seconds each. Score MFCC, wMFCC, MSS, SOT, RMS and CLAP style embeddings on it. This alone would be a new measure of how large the gap is.
4. **Then calibrate lightly.** Fit a small ranking model over those features rather than a deep net, holding out whole target sounds. About 3,000 triplets is the only domain precedent at this scale (SES-Bench). With 5 raters that is about 50 hours of listening, so it needs a plan for raters.
5. **Test the judge's reach.** Keep a set of targets, and preset families, that the calibration never saw. Similarity may not transfer between types of change, so test that directly.
6. **Benchmark an audio language model on the same triplets,** with muted audio as a control. Expect it to help more by naming a difference than by scoring. That is a hypothesis from the effects result, not a finding.
7. **Use `timbremetrics` as a quick sanity check.** Report results on the synth-related sets for any candidate score.

Risks:

- Raters may disagree most on near matches. MATCHA found lower agreement on timbre than melody. If near-miss agreement is weak, that sets a hard limit on any score, and the project should measure it first.
- Screening is costly: Sound2Serum dropped 7 of 19 listeners.
- Calibration can overfit to one sound style, so the held-out split in step 4 matters.

## 12. Direct answers to the three perceptual questions

Sections 11.2 to 11.4 hold the longer evidence. This section gives the direct answers, adds the dataset behind 2608.18226, and adds what a second search round found.

### 12.1 Trained or calibrated from human A/B or triplet judgments of synth sounds?

**Answer: I found none.** That covers the searches in 12.4 only, and it does not mean it was never done. Humans have rated synth sounds, and other domains have trained on such judgments, but I found no measure trained on human comparisons of synth sounds.

**The dataset behind [2608.18226](https://arxiv.org/abs/2608.18226) has no human judgments in training.** [V]

| Item | Fact |
|---|---|
| Training data | DX7AllTheWeb, a [public DX7 preset collection](https://bobbyblues.recup.ch/yamaha_dx7/dx7_patches.html). 31,443 presets after removing duplicates and filtering |
| Rendering | 2 seconds, one note: C4, velocity 85 |
| Splits | By algorithm: 15,370 train, 9,233 validation, 6,840 test |
| Objective | SLAP joint embedding of audio and parameters. The pairing comes from the synth, not from people |
| Human data | Evaluation only: timbremetrics, 334 samples, 2,614 averaged ratings. Result 68 to 71% triplet agreement |
| Listeners in the paper | None collected |
| Code | [SynAPSE](https://github.com/DBraun/SynAPSE). I did not check whether a filtered preset list is released |

Synth or synth-adjacent human data, with counts:

| Data | Sounds | Judgments | Listeners | Public? | Used to train? |
|---|---|---|---|---|---|
| [Vahidi 2020](https://arxiv.org/abs/2009.11706) | 15 subtractive | 120 ratings each, about 4,200 in total [I]; 105 unique pairs [I] | 35 [V] | Audio in [timbremetrics](https://github.com/tiianhk/timbremetrics) [V]; rating matrix expected there, as for the other sets, but I did not open that file. Averages only [V] | No, test only |
| [McAdams 1995](https://arxiv.org/abs/2507.07764) | 18 FM-simulated and hybrid | Not extracted | 22 [V] | Same repo [V] | No |
| [Zacharakis](https://arxiv.org/abs/2507.07764) | 24 acoustic and synth | Not extracted | 33 and 20 [V] | Same repo [V] | No |
| [SynthRL](https://www.ijcai.org/proceedings/2025/1129.pdf) validation | Dexed and Surge pairs | 30 ratings per pair; pair count not extracted | 120 [V] | Not found | No, the reward was hand-designed [V] |
| [Sound2Serum](https://projekter.aau.dk/projekter/files/835339029/Master_Thesis_Kevin_Thor_Hansen.pdf) | 8 targets, 4 stimuli each | 19 × 32 = 608 ratings [V]. MUSHRA scores, not comparisons | 19, 12 after screening [V] | Not found | No |
| [AutoSynth](https://arxiv.org/abs/2610.10774) | Sampled from test sets | 20 questions each [V] | 10 [V] | Not checked | No |
| [Semantic FM Synth](https://zenodo.org/record/4609790) | FM patches vs 9 reference patches | Ratings on 27 semantic descriptors, -10 to 10 [V] | Not stated on the page | Yes, CC BY 4.0, CSV [V] | Not for similarity, as far as I found. Describes direction of change, not closeness |

Calibration closest in spirit, none on synth sounds:

- [Thoret et al. 2020](https://link.springer.com/article/10.1038/s41562-020-00987-5) learned metrics from timbre ratings on 17 datasets and found generic and experiment-specific correlates. [U, search excerpt]
- [Lostanlen et al. 2020](https://arxiv.org/abs/2007.10926) fit a linear metric to free sorting by 31 people on 78 instrument notes. [V]
- [Inst-Sim-ABX](https://arxiv.org/abs/2502.02138) has 26,898 answers on rendered music, and [fine-tuning used it](https://arxiv.org/abs/2503.18486). [V] This is the largest music-side A/B set I read, and it is public.

One conflict: a review summary cites about 330 triplets for Inst-Sim-ABX after filtering. [U] The paper states 480 items. [V] Filtering by agreement probably explains it. [I]

### 12.2 Similarity reported per sound-design aspect?

**Answer: I found no published system that does this for synth matches across the six aspects.** Scope is 12.4.

| Aspect | Nearest published measure | Per match? | Human-validated? |
|---|---|---|---|
| Tone | Timbre traits, r = 0.66 [V]; wMFCC, SOT | Traits score per sound; metrics are averaged | Traits yes, on instruments |
| Voicing | None found | No | No |
| Filter | Partial Parameter Distance [V] | No, per scenario | Blinded listening, 5 of 7 top ranks agree [V] |
| Envelope | RMS-envelope cosine [V] | Averaged in papers | No direct study found |
| Movement | Modulation Discovery curve metrics [V] | Per curve in its own experiments | Not found |
| Effects | SerumRNN, LLM2Fx-Tools [V] | Predicts effects, gives no similarity score | LLM-as-judge on text, not listening [V] |

Human per-aspect labels exist only at music level:

- [Inst-Sim-ABX](https://arxiv.org/abs/2502.02138) asks A or B on timbre, rhythm, melody and overall. The timbre answer matched the overall answer 74.3 to 75.6% of the time. [V] So overall similarity is not the same as timbre similarity, even for one instrument. [I]
- [MATCHA](https://arxiv.org/abs/2609.00987) covers melody, harmony, rhythm, voice and timbre. [V]

### 12.3 Audio language models as judges of timbre similarity?

**Answer: I found no test of an audio language model against human timbre similarity ratings.** Scope is 12.4. Evidence that comes closest:

- **Timbre as identity:** [SonicBench](https://arxiv.org/abs/2601.11039) asks which clip is an instrument. Humans scored 1.00 on comparison and 0.93 on recognition. Models scored 0.70 and 0.75 (Qwen3-Omni), 0.49 and 0.68 (Kimi-Audio), 0.43 and 0.49 (GPT-4o-Audio). [V] Three humans, 240 items. This tests naming, not similarity. [I]
- **Similarity on another attribute:** in [SES-Bench](https://arxiv.org/abs/2609.32504), Gemini 3.8 Flash reached 60.63% on speech emotion, below plain embedding cosine at 63.46 to 65.51% and a trained judge at 74.96%. [V]
- **Comparison in general:** SonicBench found models lack the human advantage on comparison tasks. [V]
- **Timbre skills in broad benchmarks:** [MMAU-Pro](https://arxiv.org/abs/2508.13992) appears to list a Music Timbre Perception skill. [U, search excerpt] I did not confirm its task format or any human baseline.

So the comparison with humans can only be made indirectly: humans clearly lead on timbre identity, and the one similarity study testing both (speech emotion) put plain embeddings ahead of the model judges. [I]

### 12.4 What was searched for these answers

Run on 2026-11-01, with WebSearch and direct page fetches, English only.

- **Round one:** the query families in 11.5.
- **Round two:**
  - Zenodo and Hugging Face web search for synth similarity ratings and triplets
  - Inst-Sim-ABX size and availability
  - fine-tuning from timbre ratings, naming Thoret and Pascal
  - Semantic FM Synth
  - Thoret's learned metrics
  - audio language model timbre tasks, naming MMAU-Pro and RAIL
- **Read directly:** 2608.18226 dataset and split sections, 2502.02138, 2503.18486 (excerpts), Zenodo pages for records 4609790, 15428026 and 19597311, and the timbremetrics file tree.

Checked and ruled out:

- [Hearing Test Sounds](https://zenodo.org/records/15428026): files are restricted, and no completed ratings are visible.
- [Adaptive Pairwise Comparisons](https://zenodo.org/records/19597311): hearing-aid music quality, and its listening data is restricted.
- [MERIT](https://arxiv.org/abs/2605.27346): built from generated audio and stems. The abstract shows no human validation.
- [dim-sim](https://zenodo.org/records/3889149): music triplets, not synth. Seen in results only.

Still not done: Google Scholar, IEEE Xplore and ACM DL direct searches, a site-native Zenodo or Hugging Face query (the Zenodo API returned 403), browsing proceedings, non-English work, and opening RAIL or the full MMAU-Pro task list. Any of these could change an "I found none".

# Does the runaway, and its fix, hold on FlyWire snapshot 783?

*Written 2026-09-23. Scripts, raw results and plots: `experiments/runaway_783/`
(`results/summary_stats.txt` has every number below in one place). Figure:
`experiments/runaway_783/plots/fig_runaway_783.png`.*

## The short version

- **The question.** FlyWire has published the fly's wiring diagram more than once; each
  release is a **snapshot**. All our work used snapshot 630, the one the Shiu et al. 2024
  paper used. Snapshot 783 is the current public release. Neurons that were edited between
  the two got new ID numbers, and some wiring changed. Our main finding, the **runaway**
  (the simulated brain locking into non-stop firing, about 8,500 neurons), and our fix for
  it, **"al_ln_literature"**, had only been tested on 630. The fix keeps the smell centre's
  excitatory local neurons excitatory but lets their chemical synapses reach only
  inhibitory neurons, and makes the 13 whose published transmitter is GABA or glutamate
  inhibitory. Before anything could be shared, both had to hold on 783. What "holds" would
  mean was written down before any 783 trial was run (section 1).
- **The runaway holds on 783. VALIDATED.** Smell input to the DM1 channel (its 68 smell
  neurons at 150 Hz, both sides) makes the published model run away in 90 of 90 trials,
  as on 630. Ten smell neurons firing once are still enough to set it off. It is the same
  state: 96-98% of the neurons that fire are the same cells as on 630.
- **The fix holds on 783. VALIDATED.** We ported it with our own copy of its rule, proven
  to reproduce the project's fix exactly on 630 (same connections, same spikes). We tried
  it two ways: the rule applied to 783's own labels, and the same 150 cells as in 630.
  Both stop every runaway: DM1 smell input 0 of 90 (published: 90 of 90), also with
  smell on one side only. Ir94e taste
  input (the paper's 18 Ir94e taste neurons at 200 Hz) 0 of 300 (published: 17 of 300).
- **The paper's feeding result is untouched. VALIDATED.** Sugar taste input (100 Hz)
  drives the feeding motor neuron MN9 to 68.5 spikes/s on 783 (630: 67.3). With the fix it
  is identical, spike for spike.
- **The way in is the same. PRELIMINARY (one seed per test).** On 783, as on 630,
  switching off the outputs of the 44 **eLNs** (excitatory local neurons of the antennal
  lobe, the fly's first smell centre) stops the small smell trigger. Three random groups
  of the same size do not. Strong smell input stops only when all 166 excitatory local
  neurons are switched off.
- **One difference: taste input tips 783 about half as often. PRELIMINARY.** Ir94e taste
  input tips 5.7% of trials on 783 against 11.1% on 630. That could still be chance:
  p = 0.095, where p (Fisher's exact test) is the chance of a difference at least this
  big if the true rates were equal. 783 sits a little further from the tipping point on
  the same cliff: with synapses 10% stronger, 63% of taste trials run away on 783 and 93%
  on 630.
- **The cells.** All 150 cells the fix changes in 630 exist in 783. The 783 model file makes
  16 more antennal-lobe local neurons excitatory than the 630 one (166 against 150). The
  rule catches them, and both versions of the fix work.

**Verdict: by the criteria fixed in advance, both the runaway and the fix hold on
snapshot 783, the current public release.** Sharing it is the author's decision (PLAN.md Phase 6
step 6); nothing was sent to anyone.

Labels: **VALIDATED** = 3 or more seeds (a seed is the starting number of the random
input; each seed gives a different set of trials), the code checked for bugs, and compared
with the 630 result. **PRELIMINARY** = at least one of those checks is missing (usually:
one seed only). **UNVERIFIED** = not checked.

---

## 1. Pre-registration (written before any snapshot-783 simulation was run)

This section was written after the labels had been looked up (step 0, which runs no
simulation) and before any whole-brain trial on snapshot 783. It is left exactly as
written; the results sections below are judged against it.

**What we expect.**

- **Published model, DM1 smell 150 Hz on both sides:** runaway in (nearly) every trial,
  as on snapshot 630 (90 of 90). Reasons: a public hobby project reports the same
  ~8,300-neuron state on 783 for every smell channel it tried, and all 44 excitatory
  local neurons of the loop are present in 783 with the same labels. Expected: at least
  80 of 90 trials.
- **Published model, Ir94e taste 200 Hz:** some runaways, rate uncertain (630: 10 of 90,
  11%). The route from taste to the smell centre is weak (3 steps of 5, 13 and 7
  synapses in 630), and the edits between the two snapshots could make it weaker or
  stronger. Expected: somewhere between 0% and about 25%. This is the weaker of the two
  tests, because runaways are rare here.
- **Fixed model ("al_ln_literature", ported), both inputs:** 0 runaways.
- **Sugar 100 Hz -> MN9:** the fix leaves it unchanged, spike for spike, as on 630,
  because no neuron of the sugar pathway is an antennal-lobe local neuron. We expect MN9
  in roughly the same range as on 630 (67.3 spikes/s), but not the same number, because
  the wiring of the two snapshots differs.

**What "holds" means (decided now).**

- *The runaway holds on 783* if the published model runs away in at least half of the
  DM1 trials (45 or more of 90), with the same two clearly separate kinds of trial as on
  630 (healthy trials far below 1,500 neurons firing per 10 ms slice, runaway trials far
  above). For Ir94e, it holds if at least 1 of 90 trials runs away; the rate is compared
  with 630's 10 of 90 (Fisher's exact test), and a different rate is reported, not
  counted as a failure.
- *The fix holds on 783* if, with the ported fix, DM1 runs away in 0 of 90 trials
  ("mostly holds" if 1-2 of 90, "fails" if more), Ir94e in 0 of 90, and sugar -> MN9 is
  unchanged: spike-for-spike identical on the checked trials, or, failing that, mean MN9
  within 1 spike/s of the published model on 783.
- The fix is ported in two ways, and the verdict "holds" without caveat needs both:
  (1) **rule**: the fix's rule applied to snapshot 783's own labels (the main version);
  (2) **same cells**: the fix applied to exactly the 150 cells it changes in 630, found
  in 783.
- The runaway rule is unchanged from Phase 6: a trial runs away if, in some 10 ms slice,
  more than 1,500 different neurons fire. Trials: 3 seeds x 30 one-second trials per
  input, the same seeds as the 630 runs.
- Recorded but not pass/fail: the share of Kenyon cells (learning centre) that fire
  under DM1 input with the fix (630: 3.6% per trial).

---

## 2. Finding the same cells in 783, and proving the port

**Why a port is needed.** The project's fix code (`sim/sign_fixes.py`) refuses any
snapshot but 630, and its labels are 630 labels. So we wrote our own copy of the fix's rule
(`experiments/runaway_783/common783.py`, about 20 lines). It needs only two facts per
neuron. Is it an antennal-lobe local neuron (a cell whose branches stay inside the
antennal lobe; the lobe's output cells are the projection neurons)? And what sign
(excite or inhibit) does its transmitter in the published literature give? That lets it
run on either snapshot. Nothing in `sim/` was changed.

**Proof that the copy is exact (VALIDATED).** Applied to snapshot 630, our copy gives the
same result as the project's own `build_brain(fix="al_ln_literature")`
(`results/port_check.txt`):

- the fixed connection lists are identical, entry by entry: 14,635,639 connections, with
  the same 51,539 removed and the same 10,455 sign-flipped;
- it picks the same 150 target cells;
- the two built brains hold identical internal arrays;
- the same seed gives exactly the same spikes, every spike at the same time step, in 10
  trials each of DM1 smell 150 Hz (363,114 spikes), Ir94e 200 Hz (74,006) and sugar 100 Hz
  (95,881), and the per-trial totals equal the saved Phase 7 run;
- on 783, our "published" brain (built from the connection arrays) is identical to the
  engine's own `FastBrain("783")`.

**The fix's cells in 783 (VALIDATED).** A neuron's **root ID** is FlyWire's ID number for
it, and it changes whenever the neuron is edited. So we looked up the 150 cells the fix
changes in 630 through their **supervoxel** instead. A supervoxel is a tiny fixed piece of
the microscope volume; FlyWire's label files list one inside each neuron, in both
snapshots, so it finds the same cell even under a new ID. All 150 were found. 101 kept
their root ID; 49 have a new one. Then we applied the rule to snapshot 783's own labels
and compared the two lists:

| | 630 | 783 |
|---|---:|---:|
| antennal-lobe local neurons (cell class ALLN) | 424 | 429 |
| ...that the published model makes excitatory | 150 | 166 |
| cells the rule makes inhibitory (literature GABA or glutamate) | 13 | 16 |
| cells whose chemical output the rule limits to inhibitory partners | 137 | 150 |
| connections removed / sign-flipped | 51,539 / 10,455 | 53,416 / 12,524 |
| literature-typed excitatory local neurons (eLNs, Shang et al. 2007) | 44 | 44 (the same 44 cells) |

- **149 of the 150 cells get the same treatment in 783.** The one exception (630 ID
  720575940619959174, 783 ID 720575940612305506, type CB1686) is already inhibitory in the
  783 model, so there is nothing to fix.
- **The 783 rule picks 17 more cells** (`results/extra_cells_783.csv`). 3 are lLN2P_b
  cells (literature: GABA) that the 630 model already makes inhibitory but the 783 model
  makes excitatory; the rule makes them inhibitory again. 12 are local neurons with no
  literature transmitter that the 630 model makes inhibitory but the 783 model file makes
  excitatory (11 of them have a machine transmitter guess of GABA or glutamate, 1
  acetylcholine). 2 are OA-VUMa5 octopamine cells that 783's labels call antennal-lobe
  local neurons (in 630 they had no class).
- A side observation (PRELIMINARY; the cause was not checked): the 783 model file follows
  the transmitter guess less closely than the 630 one. Neurons whose guess is GABA but
  which the model makes excitatory: 239 in 630, 1,348 in 783. Glutamate: 580 in 630, 2,941
  in 783 (`results/sign_vs_top_nt.csv`).

So we ran two versions of the fix on 783. **"Fix (rule)"** applies the rule to 783's own
labels (166 cells). **"Fix (same cells)"** applies it to exactly the 630 fix's cells as
found in 783 (149 cells changed).

**The inputs in 783 (VALIDATED).**

- DM1 smell neurons: FlyWire's 783 labels keep smell-neuron types in the `cell_type`
  column (630 keeps them in `hemibrain_type`). There are 68 (35 left, 33 right), exactly
  the 68 used on 630, found by supervoxel.
- Ir94e: all 18 of the paper's IDs exist unchanged in 783, so they were used as they are.
- Sugar: 20 of the paper's 21 IDs exist in 783. The 21st (720575940620900446) is
  720575940639259967 in 783. Two independent methods agree on that: Phase 3's
  connection-fingerprint match and our supervoxel lookup.
- MN9: 720575940660219265 exists unchanged in 783. (The paper's second MN9 does not, and is
  not needed here.)

---

## 3. Result: the runaway is in snapshot 783 too

Published model, unchanged, 3 seeds x 30 one-second trials per input, the same seeds as
the 630 runs (`results/table_runaway.csv`, `results/table_volleys.csv`). A **volley** means
a group of neurons is made to fire once, 5 ms into the trial, with no other input at all.

| Input | 630 | 783 |
|---|---|---|
| DM1 smell 150 Hz, both sides | **90 of 90** trials run away | **90 of 90** |
| Ir94e taste 200 Hz | 10 of 90 (per seed 4 / 5 / 1) | 4 of 90 (1 / 1 / 2) |
| volley: 10 DM1 smell neurons | runaway (444,790 spikes in 1 s) | runaway (464,459) |
| volley: the 44 eLNs | runaway (705,223) | runaway (718,558) |
| volley: all 685 antennal-lobe projection neurons | runaway (745,729) | runaway (773,167) |

- **Smell input: VALIDATED.** Every DM1 trial runs away on 783, as on 630, and ten smell
  neurons firing once are still enough to set it off.
- **It is the same state, slightly bigger.** Medians over the 90 DM1 trials, 630 -> 783:
  spikes per trial 465,528 -> 484,982; neurons that fire 8,278 -> 8,506; neurons still
  firing in the last 100 ms 7,769 -> 8,009; share of Kenyon cells (the learning centre)
  that fire 64.2% -> 65.4%. The two kinds of trial stay far apart. Across all 1,350
  trials of this step on 783 (every version and input, including section 7c), a healthy
  trial never had more than 557 neurons firing in one 10 ms slice, and a runaway never had
  fewer than 4,320. So the 1,500 cut-off does not matter.
- **Mostly the same neurons (VALIDATED).** In the 30 seed-0 DM1 trials, 8,715 neurons fire
  on 630 and 8,920 on 783. After looking up the 630 ones in 783, 8,564 are in both: 98% of
  630's set and 96% of 783's (`results/state_overlap.csv`). The 783 "core" (the 8,484
  neurons that fire in at least half of the runaway trials) contains 97% of the 6,760
  core neurons that Phase 6 found in the taste-triggered runaways on 630. Its biggest
  groups: 3,382 Kenyon cells, 2,830 central neurons without a class, 557 projection
  neurons, 450 lateral-horn local neurons, 423 smell sensory neurons, 361 antennal-lobe
  local neurons and 148 dopamine neurons.
- **Taste input tips 783 less often (PRELIMINARY).** 4 of 90 is lower than 630's 10 of 90,
  but with so few events the difference could be chance (p = 0.16). The
  4 runaways on 783 began late (667 to 957 ms into the trial) and were still going at the
  end, with 7,400-7,900 neurons firing in the last 100 ms. Section 7 adds more trials.

---

## 4. Result: the fix removes it on 783

| | DM1 150 Hz | Ir94e 200 Hz | volley: 10 DM1 neurons | volley: 44 eLNs | volley: all projection neurons | Kenyon cells firing (DM1) |
|---|---|---|---|---|---|---|
| 630 published | 90 of 90 | 10 of 90 | runaway | runaway | runaway | 64.2% |
| 630 fix | **0 of 90** | **0 of 90** | 31 spikes | 81 spikes | 3,589 spikes | 3.6% |
| 783 published | 90 of 90 | 4 of 90 | runaway | runaway | runaway | 65.4% |
| 783 fix (rule) | **0 of 90** | **0 of 90** | 31 spikes | 80 spikes | 4,366 spikes | 3.6% |
| 783 fix (same cells) | **0 of 90** | **0 of 90** | 30 spikes | 77 spikes | 4,419 spikes | 3.7% |

(Volley spike counts are totals over the whole second; "runaway" volleys have 440,000 or
more.)

- **Smell input: VALIDATED.** Both versions of the ported fix stop all 90 DM1 runaways
  (Fisher p = 2e-53 against the published 783 model). No volley ignites anything; the
  activity dies out within the second. With the fix, at most 557 neurons fire in any 10
  ms slice of a DM1 trial.
- **The Kenyon cell number carries over exactly.** Under the fix, DM1 input makes 3.6%
  of the Kenyon cells fire per trial on 783, the same as on 630 (real flies: roughly
  5-10%, per the Phase 7 audit).
- **Taste input: 0 of 90 with either version.** Against 4 of 90 in the published 783 model
  that alone is not a significant drop (p = 0.12). Section 7 adds 210 more trials.
- **The two versions behave alike.** The 17 extra cells that only the "rule" version
  touches change nothing visible here.

---

## 5. Result: the paper's taste result is untouched on 783

Sugar taste neurons at 100 Hz, reading MN9 (the feeding motor neuron), 3 seeds x 30 trials
(`results/table_taste.csv`):

| | MN9, spikes/s (mean; per seed) | Same as the published model? |
|---|---|---|
| 630 published | 67.28 (68.17 / 66.90 / 66.77) | |
| 630 fix | 67.28 | yes, every trial |
| 783 published | 68.52 (67.50 / 69.20 / 68.87) | |
| 783 fix (rule) | 68.52 | **yes, spike for spike** |
| 783 fix (same cells) | 68.52 | **yes, spike for spike** |

**VALIDATED.** In all 90 trials the fixed 783 models give the same spike total and the same
MN9 rate as the published 783 model, and in the 10 trials whose spikes were saved in full,
every spike of every neuron is at the same time step. The fix never reaches the sugar
pathway, on 783 as on 630. MN9 on 783 is 1.2 spikes/s higher than on 630, a small
difference that comes from the wiring edits between the two snapshots, not from the fix.

---

## 6. Where it starts on 783: the Phase 6 silencing test, repeated

On the published 783 model we **silenced** a group (set all its outgoing connections to
zero) and asked whether the runaway still happens. The control groups are random excitatory
neurons from outside the antennal lobe that take part in the 783 runaway (they fire in at
least half of the DM1 runaway trials), the same kind of control Phase 6 used on 630
(`results/table_localise.csv`, `results/localise_groups.json`).

| Silenced group | volley: 10 DM1 smell neurons fire once | DM1 smell 150 Hz, 30 trials |
|---|---|---|
| nothing | runaway (464,459 spikes) | 30 of 30 run away |
| the 44 eLNs | **no runaway (26 spikes)** | 30 of 30 (median 220,337 spikes) |
| 44 random excitatory runaway neurons outside the antennal lobe (3 different random sets) | runaway, all 3 | 30 of 30, all 3 |
| all 166 excitatory antennal-lobe local neurons | **no runaway (26 spikes)** | **0 of 30** (median 43,753 spikes) |
| 166 random excitatory runaway neurons outside the antennal lobe | runaway | 30 of 30 |

**PRELIMINARY (one seed per test, but every control behaves as the story predicts).** This
is the 630 picture again:

- the 44 eLNs are the **door**: without them, the small smell trigger (10 neurons firing
  once) no longer ignites anything, while three random groups of the same size change
  nothing;
- the wider set of excitatory local neurons is the **room**: strong smell input still runs
  away with only the eLNs silenced (as on 630, where the eLN-only fix still gave 90 of 90),
  and stops only when all 166 are silenced. A random group of 166 does not stop it.

Phase 6's third test, the Ir94e runaway rate with each group silenced, was not repeated:
on 783 the intact model runs away in only about 1 Ir94e trial in 18 (section 7), so
telling "fewer runaways" from chance would need about 300 trials per group.

---

## 7. Extra checks

### 7a. The taste-triggered runaway, with more trials

Seeds 3-9 were added for Ir94e 200 Hz (210 more one-second trials each), so the published
783 model and the fix (rule) have 300 trials each (`results/table_ir94e_extra.csv`). The
"95% range" is where the true rate lies with 95% confidence, given this many trials:

| | runaway trials | rate (95% range) |
|---|---|---|
| 630 published (Phase 7, 90 trials) | 10 of 90 | 11.1% (5.5-19.5%) |
| 783 published | 17 of 300 | 5.7% (3.3-8.9%) |
| 783 fix (rule) | **0 of 300** | 0% (0-1.2%) |

- **The fix removes the taste-triggered runaway on 783: VALIDATED** (0 of 300 against 17
  of 300, p = 0.000012). In the fixed model no Ir94e trial ever had more than 347
  neurons firing in a 10 ms slice.
- **On 783 the taste trigger is about half as likely (PRELIMINARY).** 5.7% against 11.1%,
  but p = 0.095, so this could still be chance.
- **783 sits a little further from the edge, on the same cliff (PRELIMINARY; one seed,
  30 trials per point).** Make every synapse 5% or 10% stronger and Ir94e trials tip far
  more often in both snapshots:

  | synapse strength | 630 | 783 |
  |---|---|---|
  | as published (0.275 mV) | 11% (10 of 90) | 6% (17 of 300) |
  | +5% | 57% (17 of 30) | 33% (10 of 30) |
  | +10% | 93% (28 of 30) | 63% (19 of 30) |

  So the taste route into the runaway exists in 783 too. It just needs a slightly bigger
  push. Phase 6 called this "the knife edge"; it is there in both snapshots.

### 7b. Is the fix itself on a knife edge? Synapse strength -10% / +10% / +20%

Phase 7 checked the fix on 630 with every synapse 10% weaker, or 10% or 20% stronger. The
same check on 783, fix (rule), one seed x 30 trials per cell (`results/table_wsyn.csv`):

| synapse strength | DM1 150 Hz runaways | Kenyon cells firing (DM1), 783 (630) | Ir94e 200 Hz runaways | sugar 100 Hz -> MN9, 783 (630) |
|---|---|---|---|---|
| -10% | 0 of 30 | 2.65% (2.72%) | 0 of 30 | 61.2 (59.1) |
| as published | 0 of 90 | 3.61% (3.62%) | 0 of 300 | 68.5 (67.3) |
| +10% | 0 of 30 | 4.60% (4.56%) | 0 of 30 | 75.2 (73.6) |
| +20% | 0 of 30 | 5.38% (5.38%) | 0 of 30 | 76.0 (77.4) |

**PRELIMINARY (one seed per strength), but clear:** the fix holds on 783 across the whole
range, just as on 630, and the Kenyon cell numbers match 630's almost to the decimal. For
comparison, the published 783 model with synapses 10% *weaker* still runs away in 30 of 30
DM1 trials. Weakening the synapses does not remove the runaway; the fix does.

### 7c. Smell on one side only

Phase 7 also ran DM1 smell input on the left side only (35 smell neurons) and the right
side only (33), 3 seeds x 30 trials each:

| | left only | right only |
|---|---|---|
| 630 published | 90 of 90 | 90 of 90 |
| 630 fix | 0 of 90 | 0 of 90 |
| 783 published | 90 of 90 | 90 of 90 |
| 783 fix (rule) | **0 of 90** | **0 of 90** |
| 783 fix (same cells) | **0 of 90** | **0 of 90** |

**VALIDATED.** Half the smell input is still enough to set off the runaway on 783, and the
fix still removes it. Kenyon cells firing under the fix: 2.1-2.2% per trial on both
snapshots. (Steering, the other Phase 7 read-out of these runs, was not measured here.)

---

## 8. Verdict, judged against the pre-registration (section 1)

| Pre-registered test | Needed | Result | Holds? |
|---|---|---|---|
| Runaway, DM1 smell, published 783 | 45 or more of 90, two clearly separate kinds of trial | 90 of 90; healthy trials at most 557 neurons per 10 ms slice, runaways at least 4,320 | **yes** |
| Runaway, Ir94e taste, published 783 | 1 or more of 90 | 4 of 90 (17 of 300 with more seeds); lower than 630's 10 of 90, p = 0.16 (0.095 with 300) | **yes**; the rate difference is reported, as planned |
| Fix, DM1, both versions | 0 of 90 | 0 of 90 and 0 of 90 | **yes** |
| Fix, Ir94e, both versions | 0 of 90 | 0 of 90 and 0 of 90 (rule version: 0 of 300) | **yes** |
| Fix leaves sugar -> MN9 unchanged | spike for spike, or within 1 spike/s | identical in every trial; every spike identical in the 10 trials checked in full | **yes** |

The expectations were also met: DM1 at least 80 of 90 (90); Ir94e between 0% and about 25%
(4.4%); MN9 in the same range as on 630 (68.5 against 67.3).

**Both the runaway and the fix hold on snapshot 783, and both versions of the fix pass
every test, so the verdict needs no caveat.** The one thing that differs, the taste
trigger being about half as likely on 783, is PRELIMINARY and does not change the
conclusion. For the question in docs/phase6-literature-check.md (section 5): the runaway
is not a quirk of the older snapshot the paper used. It is in the release everyone
downloads today. The fix carries over to it unchanged, and the silencing test points to
the same cells as on 630 (PRELIMINARY, one seed).

---

## 9. What was not verified

- **Brian2 was not run on 783.** Every 783 trial ran on the fast engine only. On 630 the
  fast engine reproduced Brian2 spike for spike, runaway included (Phase 6). The same
  comparison on 783 has never been done in this project (it was dropped for time and
  memory when the fast engine was built). The engine code is the same for both
  snapshots; only the connection list differs. UNVERIFIED for 783.
- **Only one smell channel.** The hobby project reports the runaway for all 53 smell
  channels on 783; we tested DM1 only (plus the one-off volleys). UNVERIFIED for the others.
- **783's labels were taken as FlyWire gives them.** In particular the 2 OA-VUMa5
  octopamine cells that 783's labels call antennal-lobe local neurons, and the 12 local
  neurons that the 783 model file makes excitatory even though their transmitter guess is
  mostly GABA or glutamate. Neither was checked against the literature. The fix works with
  and without them (the "same cells" version leaves them alone).
- **Why the 783 model file makes more neurons excitatory** was not traced. Brain-wide,
  neurons whose transmitter guess is GABA but which the model makes excitatory go from 239
  in 630 to 1,348 in 783 (glutamate: 580 to 2,941). How Shiu et al. derived the 783 signs
  was not re-derived here. PRELIMINARY.
- **The silencing test (section 6) and the synapse-strength test (section 7b) used one
  seed**, as Phase 6 and Phase 7 did. The Ir94e silencing test was not repeated (too few
  runaways on 783).
- **Why taste input tips 783 less often** was not traced to specific wiring changes.
- Everything about real flies is unchanged from Phases 6 and 7: the fix is based on
  published physiology (Yaksi & Wilson 2010) and transmitter data (Shang et al. 2007), and
  the extension from the 44 measured eLN types to all 166 excitatory local neurons remains
  an inference.
- Nothing was shared or sent. Whether to tell the model's authors is this project author's decision
  (PLAN.md Phase 6 step 6).

---

## Files

All under `experiments/runaway_783/` (nothing in `sim/`, `app/` or `tests/` was changed).

- `common783.py`: shared helpers. It holds the labels for either snapshot, our copy of the
  fix's rule, the supervoxel lookup (630 ID -> 783 ID), the trial runner and the runaway
  measure.
- `s0_labels_783.py`, `s0b_extra_cells.py`, `s0c_sign_vs_label.py`: finding the fix's cells
  and the input neurons in 783 -> `results/labels_783.txt`, `fix_cells_630_in_783.csv`,
  `fix_cells_783.csv`, `extra_cells_783.csv`, `sign_vs_top_nt.csv`, `input_sets_783.json`.
- `s1_port_check.py`: the proof that our copy of the fix is exact on 630 ->
  `results/port_check.txt`.
- `s2_runaway_783.py`: the main 783 runs (3 versions x 3 inputs x 90 trials, the volleys,
  and the left/right runs) -> `results/trials.csv`, `volleys.csv`, `active/` (which neurons
  fired in each trial), `spikes/` (every spike of 10 sugar trials per version),
  `build_info.json`, logs `s2_main.log`, `s2_lr.log`.
- `s3_localise_783.py`: the silencing test -> `results/localise_trials.csv`,
  `localise_groups.json` (the exact silenced cells).
- `s5_wsyn_783.py`: synapse strength -> `results/wsyn_trials.csv`.
- `s6_ir94e_783.py`: the extra Ir94e trials -> `results/ir94e_extra_trials.csv`.
- `s4_analyze.py`: all tables (`results/table_*.csv`, `state_overlap.csv`), the summary
  (`results/summary_stats.txt`) and `plots/fig_runaway_783.png`.
- `run_queue.sh`: ran steps 3, 6, 5 and the left/right runs one after another, so only one
  brain was in memory at a time.
- `log-entry.md`: the entry for EXPERIMENTS.md.

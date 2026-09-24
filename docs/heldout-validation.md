# Held-out validation: the antennal-grooming circuit and two feeding results

Status: **done for this session** (2026-09-23, about 17:40-19:35). Section 1 was
written before any simulation was run; nothing in `sim/` was changed.

Code and data: `experiments/heldout/` (scripts, `results/`, `plots/`, `log-entry.md`).

## The short version

A **held-out test** is a published result that none of the model changes was chosen or
checked on. Until now every change was judged on the same taste-to-MN9 results, so this
lane ran results the model had never been scored on: the paper's own antennal-grooming
results, real-fly grooming measurements the paper did not score, and two real-fly
feeding results the paper never used. The pass/fail rules were written down before any
simulation ran (section 1).

- **The published model reproduces the paper's grooming results.** For example aBN1, a
  grooming brain neuron, fires 73.0 / 72.7 / 72.7 Hz (three random seeds) when the
  antenna's JO-CE sensors are driven hard; the paper's own output file says 73.1. Every
  checked number lands within about 1 Hz of the authors' files. VALIDATED.
- **The paper's own silencing screen reproduces too.** Silencing each of the paper's 154
  non-sensory candidate neurons in turn, exactly the paper's three (aBN1, aDN2 and
  DNge220) cut aDN1 by more than 20%, in the paper's order (aDN1 left at 0.00 / 0.64 /
  0.80 of normal; paper 0.00 / 0.63 / 0.75). The matching "which neurons can drive
  aDN1 on their own" screen also gives exactly the paper's answer (aBN1 68.0 Hz, aDN2
  34.1 Hz; paper 68.5 / 33.6). VALIDATED.
- **It gets 2 of 5 scorable real-fly grooming results wrong** (Hampel et al. 2015, not
  scored by the paper): sensors of antennal zone F never reach aBN2 or aDN1 (0.0 and
  0.2 Hz; in flies both respond), and aBN2 excites the descending neuron aDN2 (8.8 Hz)
  where flies show inhibition. Both hold with synapses 20% weaker or stronger, weaker
  drive, and each aBN2 cell alone: VALIDATED as model behaviour, PRELIMINARY as a
  disagreement with flies (it depends on which FlyWire cells are "aBN2"; two papers
  disagree).
- **The recommended sign fix (al_ln_literature) cannot be judged by these tests.** None
  of the 150 smell neurons it changes fires in any grooming run, so every run is
  identical to the published model spike for spike (15 grooming runs; the 54 feeding
  runs are identical too). VALIDATED. It needs a held-out SMELL result. The same goes
  for the cell-type-parameter and gap-junction switches (identical in 15 and 14 of 15
  runs).
- **The other variants**: the dopamine/serotonin fix and distance-based delays hold
  (every number within about 1 Hz). Spike-frequency adaptation weakens the paper's key
  grooming contrast: zone-F sensors now drive aBN1 at 26% of the JO-CE response (limit
  set in advance: 25%; published model 7%), because the inhibitory cells that block them
  tire. PRELIMINARY. No variant fixes either grooming miss.
- **Feeding: the model gets the ISN result backwards.** Real flies drink more sugar and
  less water when the four ISN neurons are switched on. In the model, driving them
  roughly halves the response of MN9 (the motor neuron that extends the proboscis) to
  sugar (19.0 to 10.3 Hz) and raises its response to water by about 70% (10.6 to
  17.9 Hz). All five model versions run (the published model and four variants) show
  the same two directions (with adaptation the water rise falls just short of the line
  set in advance). PRELIMINARY (MN9 measures the start of feeding, not how much is
  drunk; only the source's abstract was readable). A second result, OA-VPM4 boosting
  proboscis extension, barely shows up (can't tell): by the source's own account those
  cells work by making the sugar sensors more sensitive, which this model cannot do
  (PRELIMINARY as the explanation).

---

## 1. Pre-registration (written before running anything)

### 1.1 Why this test

Every model change so far (the sign fix `al_ln_literature`, the neuromodulator fix
`al_ln_literature+da_5ht_literature`, the Phase 7 switches) was chosen or checked on
the same few Shiu et al. 2024 taste results: sugar, water, bitter and Ir94e taste
neurons driving MN9, the motor neuron for proboscis extension. A variant could look
good only because it was tuned on those tests. A **held-out test** is a published
result that none of the variants was chosen on. If a variant passes the old tests but
fails a held-out one, the fix does not generalise.

Shiu et al. 2024 (*Nature* 634:210-219) has one result outside feeding: the
**antennal-grooming circuit** (their Fig. 5 and Extended Data Fig. 4). Nothing in
this project has run it before (searched EXPERIMENTS.md, `sim/`, `tests/`, `app/`,
`experiments/`: no hits for aBN1, aDN1, JO-CE or grooming).

Terms used below:
- **JONs** (Johnston's organ neurons): the hearing / antenna-movement sensors in the
  antenna. Subgroups: **JO-CE** (zones C and E, vibration), **JO-F** (zone F),
  **JO-D/m**.
- **aBN1**, **aBN2**: antennal grooming *brain* interneurons.
- **aDN1**, **aDN2**: antennal grooming *descending* neurons (brain to nerve cord);
  activating either one makes a real fly groom its antennae (Hampel et al. 2015).
- **Calcium imaging**: a real-fly measurement of whether a neuron becomes active.
- **Sufficient**: driving neuron X alone makes the read-out fire. **Required**:
  silencing X (removing all its outputs) cuts the read-out by more than 20%.

### 1.2 Where every ID comes from (snapshot 630)

All IDs were copied from the paper's own code (`data/reference/figures.ipynb`,
"Figure 5" cells) and checked against FlyWire's annotations
(`experiments/heldout/ids.py`; the ID lists match the notebook exactly):

| Name | v630 root ID(s) | FlyWire annotation |
|---|---|---|
| JO-CE, 70 neurons | notebook `neu_JON_CE` | all 70 typed JO-C* / JO-E*, all one side (left) |
| JO-F, 60 neurons | notebook `neu_JON_F` | all 60 typed JO-F*, left |
| JO-D/m, 16 neurons | notebook `neu_JON_D_m` | JO-mz 7, JO-DP 5, JO-DA 4, left |
| aBN1 | 720575940630907434 | hemibrain type SAD093, left, acetylcholine |
| aDN1 | 720575940616185531 | DNge197 |
| aDN2 | 720575940629806974 | DNge078 |
| "Descending BN2_3" (the paper's aBN2) | 720575940611163610 | DNge220, a descending neuron |
| 3 inhibitory neurons (Ext. Data Fig. 4c) | 720575940636066222, 720575940609957315, 720575940624986407 | CB0443, CB0496, CB0496; all GABA |
| aBN2_1, aBN2_2, aBN2_3 (see below) | 720575940634683237, 720575940618961857, 720575940621355759 | no type; hemilineage LB23, left, acetylcholine |

The paper's text says 147 JONs; its code drives 146 (70 + 60 + 16). We use the code's 146.

**Two different "aBN2"s.** Shiu et al. counted DNge220 ("a descending member of the
BN2 class") as aBN2. A later paper from the same lab (Calle-Schuler, ..., Hampel,
Seeds et al., *eLife* 14, doi:10.7554/eLife.108044, PMC13246004, Fig. 13 legend)
names three *non-descending* LB23 neurons
as aBN2_1-3, matched by light-microscopy morphology to the aBN2 driver line of
Hampel et al. 2015: "The following are the flywire IDs for the different aBN2
neurons: aBN2_1 (720575940634683237), aBN2_2 (720575940618961857), aBN2_3
(720575940621355759)". All three IDs exist unchanged in snapshot 630. We report both
identities. Mapping confidence: high for aBN1, aDN1, aDN2 and the JON groups (named
by authors of the papers that defined them); **aBN2 is contested** between the two
papers; we treat the 2026 IDs as the better-supported match because that paper
matched them to the driver line itself.

### 1.3 What the paper and the real flies showed

Numbers below are the published model's output, read from the authors' own result
files in the Edmond archive (doi:10.17617/3.CZODIW; fetched by
`experiments/heldout/fetch_published.py`, summarised in
`results/published_summary.json` and `results/published_top300.csv`).

**Test A. JO-CE versus JO-F onto aBN1** (Fig. 5g; real-fly check Fig. 5h).
- Paper, model: "JO-CE neurons will elicit robust aBN1 activity, JO-F neurons will
  not, despite synapsing directly onto aBN1." aBN1 with JO-CE at 100 / 220 Hz:
  25.4 +/- 2.0 / 73.1 +/- 1.3 Hz. With JO-F: 0.9 / 4.6 Hz.
- Real flies (calcium imaging, Fig. 5h): "JO-CE activated aBN1 robustly, but JO-F
  neurons did not." Scored 2 of 2 correct in the paper's Supp. Table 10.
- **Reproduced / holds** if, in every seed: aBN1 with JO-CE is at least 10 Hz at
  100 Hz and at least 40 Hz at 220 Hz, AND aBN1 with JO-F is at most 25% of aBN1 with
  JO-CE at both 100 and 220 Hz. **Breaks** if either fails in any seed.
  (For the published model we also ask whether our means are within 10% or 1 Hz of
  the published means, whichever is larger.)

**Test B. Silencing three inhibitory neurons lets JO-F drive aBN1** (Ext. Data
Fig. 4c; a model prediction, never tested in flies: "this remains to be tested
empirically").
- Paper, model: aBN1 with JO-F plus the 3 GABA neurons silenced: 22.4 / 66.4 Hz at
  100 / 220 Hz (versus 0.9 / 4.6 without silencing).
- **Holds** if, in every seed: aBN1 with silencing is at least 5 times aBN1 without,
  and at least 10 Hz at 100 Hz and 40 Hz at 220 Hz.

**Test C. All 146 JONs activate aBN1, aDN1 and aDN2** (Fig. 5b; real flies:
Hampel et al. 2015, scored 3 of 3 in Supp. Table 10).
- Paper, model, at 100 / 140 / 220 Hz: aBN1 24.3 / 45.3 / 78.2 Hz; aDN1 3.2 / 16.7 /
  38.4; aDN2 3.6 / 17.1 / 38.6; DNge220 74.0 / 90.6 / 118.9. 855 neurons fired at
  some rate; 677 non-JON neurons at 220 Hz.
- **Holds** if, in every seed, aBN1, aDN1 and aDN2 each fire at least 5 Hz at 220 Hz
  and aDN1 at least 5 Hz at 140 Hz. We also report how similar the whole pattern is
  (correlation of every neuron's rate with the published rates).

**Test D. Only aBN1 and aDN2 can drive aDN1 on their own** (Fig. 5c; model result).
- Paper: of the 300 neurons that respond most to JONs, activated one at a time at
  25-200 Hz, "only four neurons, beyond aDN1 itself ... could elicit aDN1 activity:
  aBN1, aDN2 and two other neurons that elicited less than 2 Hz". Published maxima:
  aBN1 68.5 Hz, aDN2 33.6 Hz, 720575940644072483 1.07 Hz, 720575940653315489 0.33 Hz.
- Our protocol (cheaper): the same 300 IDs (the paper's own list), each driven alone
  at 200 Hz, 10 trials. **Holds** if the neurons other than aDN1 that drive aDN1 above
  2 Hz are exactly aBN1 and aDN2.

**Test E. Which neurons are required for aDN1** (Fig. 5d-f; real flies: aBN1 and aBN2
required, Hampel et al. 2015, scored 2 of 2).
- Paper: with all JONs at 140 Hz, silencing each of the 300 one at a time, "only
  three neurons, besides aDN1 itself, ... reduced aDN1 activity by more than 20%:
  aBN1; a descending member of the BN2 class; and aDN2". Published aDN1 relative to
  no silencing: aBN1 0.00, aDN2 0.63, DNge220 0.75. (Seven single JONs also cut aDN1
  by more than 20% in the published files, 0.52-0.78; the paper counted non-JON
  neurons only, Fig. 5e, and so do we.)
- Our protocol: all 146 JONs at 140 Hz, each of the same 300 silenced, 10 trials
  with the same random input as the no-silencing control (a paired comparison: the
  only difference between the two runs is the silencing). **Holds** if the non-JON
  neurons with more than a 20% cut are aBN1, aDN2 and DNge220, plus at most one other.

**Test F. Real-fly results about this circuit that Shiu et al. did NOT score**
(Hampel et al. 2015 *eLife* 4:e08758, Fig. 6: optogenetic activation of one cell
group while calcium-imaging another, in the dissected nervous system). Hampel et al.
2020 (*eLife* 9:e59976) states: "We previously discovered the aJO subpopulation of
JONs (Hampel et al., 2015), which we now rename as 'JO-F' neurons". So "aJO" below
means JO-F. aBN2 means aBN2_1-3 (2026 IDs); DNge220 is reported alongside.

| # | Real-fly result (Hampel 2015) | Model test | Right direction if |
|---|---|---|---|
| F1 | aJO (JO-F) activation gives "significant calcium responses in aBN1, aBN2, and aDN1" | JO-F 60 at 220 Hz | aBN1, aBN2 (mean of 3) and aDN1 each at least 2 Hz |
| F2 | ... "but only a weak response in aDN2 even with high-intensity red light" | same run | aDN2 below half of aDN1 (can't tell if aDN1 < 2 Hz) |
| F3 | "Activation of aBN1 induced a calcium response in aBN2" | aBN1 alone, 200 Hz | aBN2 mean at least 2 Hz |
| F4 | "only high-intensity red light activation of aBN2 could cause a weak calcium response in aBN1" | aBN2_1-3 together, 200 Hz | aBN1 fires, but less than it does from aBN2's strongest input (weak); wrong if aBN1 is silent AND if it is strong (more than 20 Hz) |
| F5 | "Activation of aBN1 induced a calcium response in the aDNs" | aBN1 alone, 200 Hz | aDN1 or aDN2 at least 2 Hz |
| F6 | "activation of aBN2 caused a mecamylamine-sensitive excitatory response in aDN1" | aBN2_1-3 together, 200 Hz | aDN1 at least 2 Hz |
| F7 | ... "yet decreased the basal fluorescence of GCaMP6s in aDN2" (inhibition through an unidentified inhibitory neuron; blocked by picrotoxin) | aBN2_1-3 together, 200 Hz; aDN2 voltage recorded | aDN2's average voltage below rest by at least 0.1 mV and aDN2 does not fire; wrong if above rest by 0.1 mV or it fires |

What we already knew before running (stated so the reader can judge the pre-registration):
the published all-JON file (Test C) contains no spikes at all from aBN2_1-3 at any rate,
so F1 was expected to fail for aBN2 in the published model. The wiring (read before
running) also shows JO-F -> aBN2_1-3 = 61 synapses, aBN1 -> aBN2_1-3 = 50,
aBN2_1-3 -> aDN1 = 77 and aBN2_1-3 -> aDN2 = 15 (excitatory, direct), and strong
input to aBN2_1-3 from the GABA types CB0496 and CB0443 (the same types as the three
inhibitory neurons of Test B). F4 is ill-posed ("weak" versus "none"), so it is
reported but not scored.

### 1.4 Seeds, trials, variants, and how variants are scored

- Seeds and trials: 3 seeds x 30 trials x 1 s for Tests A, B, C and F (same as the
  paper's 30 trials per condition); Tests D and E use 1 seed x 10 trials per neuron
  (300 neurons each), because they are 300 separate experiments.
- Stimulation: Poisson input at the stated rate, exactly as in the paper's code.
- Variants (built with `sim/sign_fixes.build_brain` or the Phase 7 builders):
  1. `none`: the published model.
  2. `al_ln_literature`: the recommended sign fix.
  3. `al_ln_literature+da_5ht_literature`: the version used for learning.
  4. If time allows, one Phase 7 switch at a time: distance-dependent delays,
     spike-frequency adaptation (both `sim/realism.py`, on the published model),
     cell-type parameters (`sim/celltype_params.py`, on the published model), gap
     junctions (`sim/gap_junctions.py`, on `al_ln_literature`, as defined there).
- Each variant, each test: **holds** (passes in every seed and the key numbers stay
  within 20% of the published model's), **changes** (passes, but a key number moves
  by more than 20%), **breaks** (fails the criterion in any seed).

### 1.5 Pre-registration, part 2: held-out FEEDING tests (written at 18:16, before running them)

Real-fly experiments on the proboscis-extension / feeding circuit that Shiu et al. did
NOT use. Neither cell type is among the 106 cell types of their Fig. 2
(`data/reference/sez_neurons.pickle`), and Shiu et al. cite Jourjine et al. 2016 only
for a desiccation method. Both cell types carry literature names in FlyWire's own
annotation (`data/cache/connectome_630_neurons.parquet`).

| # | Real-fly result (source) | FlyWire v630 IDs (mapping confidence) | Model test | Right direction if |
|---|---|---|---|---|
| G1 | "Thermogenetic activation of Gal4 lines containing OA-VPM4 promoted proboscis extension to sucrose, while optogenetic inactivation reduced extension" (Youn, Kirkhart, Chia & Scott 2018, *PLoS ONE* 13:e0198362; abstract, via web search) | OA-VPM4 = 720575940624971243, 720575940627702665 (hemibrain type OA-VPM4, octopamine). **Moderate**: the fly lines contained OA-VPM4 plus other cells; the paper attributes the effect to OA-VPM4. Readout = MN9, the paper's own proboscis-extension read-out: good match. | sugar GRNs (the paper's 21) at 40 Hz and 50 Hz (MN9 4.8 and 19.4 Hz in the published model), with and without OA-VPM4 driven at 50 and 100 Hz | MN9 with OA-VPM4 is higher than without by more than 20% and more than 1 Hz, in every seed. **Wrong**: lower by more than 20% and 1 Hz in every seed. Otherwise **can't tell**. |
| G2 | the inactivation half of G1 | same | silence OA-VPM4 during sugar 50 Hz | can only be tested if OA-VPM4 fires during sugar input in the model; otherwise **can't tell** (the model has no internal state to drive it) |
| G3 | ISNs: "Activation of these neurons promotes sugar consumption and restricts water consumption, whereas inactivation promotes water consumption and restricts sugar consumption" (Jourjine, Mullaney, Mann & Scott 2016, *Cell* 166:855; abstract only: the full text was blocked, PMC reCAPTCHA and Europe PMC PDF 403) | ISN = 720575940617785817, 720575940619731393, 720575940621212654, 720575940624153528 (FlyWire type "ISN"; the paper describes four neurons). **High** for the cells. Readout: **low-moderate**, because the paper measured consumption, and MN9 drives proboscis extension (starting to feed), not drinking volume. | sugar 40 and 50 Hz with and without the 4 ISNs driven at 50 and 100 Hz | MN9 higher with ISNs (same thresholds as G1) |
| G4 | the water half of G3 | same | water GRNs (the paper's 18) at 160 Hz (published MN9 10.0 Hz), with and without ISNs at 50 and 100 Hz | MN9 LOWER with ISNs by more than 20% and 1 Hz in every seed; **wrong** if higher by those amounts |
| G5 | the inactivation half of G3 | same | silence ISNs during sugar 50 Hz and water 160 Hz | as G2 |

Activation rates of 50 Hz follow the paper's own screen of central feeding cells (Fig. 2
used 50 Hz); 100 Hz is a second, stronger setting. 3 seeds x 30 trials each. Variants: the
same as section 1.4, as time allows. Script: `experiments/heldout/feeding_heldout.py`.

Scoring details (added at 18:24, before any feeding simulation had run). The read-out is
the paper's default MN9 (720575940660219265, the one opposite the stimulated taste cells).
Seeds are paired by position (first seed with first seed, and so on). G1, G3 and G4 each
have several pairs (two taste rates x two activation rates for G1 and G3; two activation
rates for G4). Each pair is scored on its own. A test is **right** if at least half of its
pairs are right and none is wrong, **wrong** if at least half are wrong and none is right,
**mixed** if some are right and some wrong, and otherwise **can't tell**. For G2 and G5,
"the cells fire during taste input" means a mean of at least 1 Hz in every seed; if they
do, silencing them scores right when MN9 moves the way the real-fly inactivation did
(lower for OA-VPM4 on sugar, lower for ISNs on sugar, higher for ISNs on water) by more
than 20% and 1 Hz in every seed, with the same wording for wrong and can't tell.

---

## 2. How it was run

- Engine: `sim/fast_engine.py` (the fast copy of the paper's Brian2 model), snapshot
  630, the paper's parameters, 1 s trials, Poisson input exactly as in the paper's code.
  Variants built with the project's own builders (`sim/sign_fixes.build_brain`,
  `sim/realism.build_realistic_brain`, `sim/celltype_params.CellTypeBrain`,
  `sim/gap_junctions.build_gap_brain`); nothing in `sim/` was edited.
- Every variant gets the same random input for the same condition and seed, so
  differences between variants are caused by the variant, not by chance.
- Scripts (all in `experiments/heldout/`): `ids.py` (every ID, checked against the
  paper's notebook), `fetch_published.py` (the paper's own output files, by byte-range
  download from the Edmond archive), `published_summary.py` (the targets),
  `run_heldout.py` (the simulations; saves each condition as it finishes),
  `check_changed.py` (which neurons each sign fix changes, and whether any of them
  fires here), `robustness.py` (the Phase 6 checks of section 3.5),
  `feeding_heldout.py` (the feeding tests), `isn_wiring.py` (the ISN wiring read-out),
  `analyze_heldout.py` (scoring, tables, plot), `queue.sh` (run order). Every number in
  section 3 is in `results/summary.md` / `results/summary.json`, regenerated by
  `analyze_heldout.py` from the saved runs.
- Deviations from section 1, decided before seeing any Test D or E result: the
  two 300-neuron screens ran the 154 non-JON neurons first, because the pass rules
  count only non-JON neurons; the 146 single-JON runs were left for last and dropped
  when time ran out (section 3 says which ran). The variants ran the rates the pass
  rules use (Test A at 100 and 220 Hz, Test C at 140 and 220 Hz), not the full
  curves.

## 3. Results

### 3.1 The published model reproduces the paper's grooming results (Tests A, B, C)

Numbers are Hz, one value per seed (30 trials each), next to the paper's own output.

| Test | Condition | aBN1, our 3 seeds | aBN1, paper | Verdict |
|---|---|---|---|---|
| A | JO-CE 60 Hz | 3.1 / 3.0 / 3.3 | 3.5 | |
| A | JO-CE 100 Hz | 26.1 / 25.8 / 25.8 | 25.4 | robust: passes |
| A | JO-CE 140 Hz | 47.3 / 47.1 / 46.6 | 47.2 | |
| A | JO-CE 220 Hz | 73.0 / 72.7 / 72.7 | 73.1 | robust: passes |
| A | JO-F 100 Hz | 1.0 / 0.7 / 0.7 | 0.9 | weak (3% of JO-CE): passes |
| A | JO-F 220 Hz | 5.3 / 4.6 / 5.1 | 4.6 | weak (7% of JO-CE): passes |
| B | JO-F 100 Hz + 3 GABA cells silenced | 22.1 / 22.4 / 22.3 | 22.4 | restored (29x): passes |
| B | JO-F 220 Hz + 3 GABA cells silenced | 66.4 / 66.2 / 65.8 | 66.4 | restored (13x): passes |

Test C (all 146 JONs), Hz, our 3 seeds vs the paper:

| Rate | aBN1 | aDN1 | aDN2 | DNge220 | aBN2_1-3 |
|---|---|---|---|---|---|
| 100 Hz | 25.2 / 24.6 / 24.6 (paper 24.3) | 3.4 / 3.1 / 3.2 (3.2) | 4.1 / 3.7 / 3.5 (3.6) | 73.8 / 74.0 / 73.7 (74.0) | 0 (0) |
| 140 Hz | 44.5 / 44.6 / 44.1 (45.3) | 15.5 / 15.7 / 15.6 (16.7) | 16.2 / 16.4 / 16.3 (17.1) | 91.4 / 90.8 / 91.2 (90.6) | 0 (0) |
| 220 Hz | 77.5 / 77.8 / 77.5 (78.2) | 38.2 / 38.2 / 37.9 (38.4) | 38.3 / 38.4 / 38.2 (38.6) | 119.5 / 119.8 / 119.9 (118.9) | 0 (0) |

Whole pattern at 220 Hz: 660-702 non-JON neurons fired per seed (paper: 677), and
every neuron's rate correlates with the paper's at r = 0.9999 (0.9994 on a log scale;
774 neurons). At 140 Hz: 473-478 neurons (paper 482), r = 0.9998.

**Verdict: A, B and C hold on the published model** (VALIDATED as a reproduction:
3 seeds, every number within about 1 Hz of the authors' own files, which were made with
Brian2 and different random input). This is also the first check of the fast engine
on a circuit outside feeding, and it passes.

What the real-fly half of Test A (Fig. 5h, JO-CE drives aBN1, JO-F does not) says
about biology is the paper's claim, and the model still makes it: VALIDATED by the
paper's own calcium imaging, not by us.

### 3.2 Real-fly results the paper did not score (Test F, Hampel et al. 2015)

Published model, 3 seeds x 30 trials. "aBN2" = aBN2_1-3 (the 2026 IDs); the last
column repeats the test with the paper's aBN2, DNge220.

| # | Real fly | Model (published) | Score | With DNge220 as aBN2 |
|---|---|---|---|---|
| F1 | JO-F drives aBN1, aBN2 and aDN1 | JO-F 220 Hz: aBN1 5.0 Hz, **aBN2 0.0, aDN1 0.2** (every seed; also 0 at 60-140 Hz) | **wrong** (2 of 3 cells silent) | DNge220 99 Hz: right |
| F2 | JO-F drives aDN2 only weakly | aDN1 0.2, aDN2 0.2 | can't tell (aDN1 silent) | same |
| F3 | aBN1 drives aBN2 | aBN1 alone 200 Hz: aBN2 11.2 Hz (11.0-11.4) | right | DNge220 0.0 Hz: wrong |
| F4 | aBN2 drives aBN1 only weakly | aBN1 0.0 Hz | not scored ("weak" vs "none" is ill-posed) | 0.0 |
| F5 | aBN1 drives the aDNs | aDN1 68.9, aDN2 67.9 Hz | right | - |
| F6 | aBN2 drives aDN1 | aBN2_1-3 200 Hz: aDN1 78.3 Hz | right | DNge220 alone: aDN1 0.0: wrong |
| F7 | aBN2 **inhibits** aDN2 (via an unidentified inhibitory cell) | aDN2 **fires 8.8 Hz** (8.2-9.3); average voltage -48.5 mV, 3.5 mV above rest | **wrong** (opposite sign) | aDN2 -51.95 mV, 0 Hz: can't tell |

Score for the published model with the 2026 aBN2 identity: **3 right (F3, F5, F6),
2 wrong (F1, F7), 1 can't tell, 1 not scored.** With the paper's own identity (DNge220):
1 right (F1), 2 wrong (F3, F6), the rest can't tell or not scored. Either way, the
model misses real-fly results in this circuit that the paper's scoring (7 of 7
grooming predictions correct) did not include. PRELIMINARY (Phase 6 checks in 3.5).

Why, in the model's wiring (read from the connection table, not a simulation):
- JO-F excites the three GABA cells of Test B (on average 7-74 Hz, depending on the
  rate, whenever JO-F or all JONs are driven; about 2 Hz with JO-CE alone), and those
  cells send strong inhibition to aBN1 and to the three aBN2s (CB0496 and CB0443 are
  among the largest inputs to aBN2_1-3: -130 and -72 synapses). This one mechanism explains both the correct Fig. 5h prediction (JO-F
  barely drives aBN1) and the F1 miss (JO-F never drives aBN2 or aDN1). With the three
  silenced, JO-F at 220 Hz does make aBN2 fire (1.0-1.1 Hz).
- aBN2_1-3 make 15 direct excitatory (acetylcholine) synapses onto aDN2, and the
  inhibitory two-step routes (for example through DNde006, glutamate) are weak, so the
  model can only excite aDN2 (F7).
- A consequence for the paper's own score: Shiu et al. counted "aBN2 is required for
  aDN1" as correct because silencing DNge220 cuts aDN1 by 25%. With the 2026 identity,
  aBN2_1-3 never fire during JON input in the model (Test C), so silencing them cannot
  change anything: the model predicts they are NOT required, while the real-fly
  silencing data say they are ("three neurons whose silencing disrupts antennal
  grooming", Calle-Schuler et al.; necessary for grooming evoked by thermogenetic JO
  activation, Hampel et al. 2015). That turns the paper's 2 of 2 into 1 of 2.

### 3.3 Do the fixes generalise? Tests A, B, C and F on each variant

The variants, in one line each:
- **al_ln_literature** (the project's recommended sign fix): changes what 150
  antennal-lobe local neurons (smell circuit) send to their partners.
- **al_ln_literature+da_5ht_literature**: the same, plus it removes the fast "push" of
  the 445 dopamine and serotonin neurons whose transmitter is known from the literature.
- **delays** (Phase 7): each spike also needs travel time, set by the distance between
  the two neurons.
- **adaptation** (Phase 7): every spike adds a slow brake, so a neuron driven for a
  long time slows down.
- **celltype** (Phase 7): cell types that someone has measured with an electrode get
  their measured settings (membrane time constant, rest, threshold gap); all
  other neurons keep the shared ones.
- **gap** (Phase 7): adds electrical synapses measured in the smell circuit
  (excitatory local neurons with projection neurons, and sister projection neurons),
  on top of al_ln_literature.

Hz, mean of 3 seeds (each seed within about 1 Hz of the mean unless stated). The same
seed means the same random input in every variant.

| Variant | A: aBN1 with JO-CE / JO-F, 220 Hz (JO-F as % of JO-CE) | B: JO-F + 3 GABA cells silenced, 100 / 220 Hz | C: all JONs 220 Hz, aBN1 / aDN1 / aDN2 (pattern r, log scale) | F: right / wrong | Verdict |
|---|---|---|---|---|---|
| published (none) | 72.8 / 5.0 (7%) | 22.3 / 66.1 (12-32x) | 77.6 / 38.1 / 38.3 (0.999) | 3 / 2 (F1, F7 wrong) | reproduces the paper |
| al_ln_literature | identical to published | identical | identical | identical | **holds, but the test cannot see it** (below) |
| al_ln_literature+da_5ht_literature | 72.8 / 5.1 (7%) | 22.3 / 66.1 | 77.7 / 38.1 / 38.2 (0.995) | 3 / 2, same cells | **holds** |
| delays | 72.2 / 5.0 (7%) | 22.2 / 65.8 | 77.1 / 37.9 / 38.0 (0.998) | 3 / 2, same cells | **holds** |
| adaptation | 56.5 / 14.8 (**25-27%** per seed; limit 25%) | 16.7 / 49.9 (only **3.3-3.9x**; limit 5x) | 67.0 / **23.1** / 23.5 (0.95) | 3 / 2, same cells | **breaks A (narrowly) and B**; C holds with aDN1 39% lower |
| celltype | not run | not run | identical to published | identical (F3-F7 conditions) | **holds; no effect here** |
| gap | not run | not run | 77.6 / 38.1 / 38.3 (0.999) | F3-F7 conditions identical; F7 aDN2 still fires | **holds; almost no effect** (14 of 15 runs identical, one run differs by one neuron) |

Plot: `experiments/heldout/plots/abn1_curves.png` (aBN1 against stimulation rate for
each variant, on top of the paper's curve; adaptation is the only one that falls off it).

Details:
- **al_ln_literature is invisible to this test.** None of its 150 changed neurons fires
  in any grooming condition of the published model (`check_changed.py`; they are smell
  cells, and nothing here drives them). A neuron that never fires sends nothing, so
  changing its outgoing synapses cannot change anything: all 15 condition-seed runs
  compared are identical spike for spike. So this is not evidence for or against the
  fix. Judging it needs a held-out SMELL result (section 4). VALIDATED (as a fact about
  this test).
- **da_5ht_literature**: in 16 of the 33 runs compared (the ones with strong input),
  1-5 of the monoamine neurons it changes do fire, so the output differs from the
  published model; every key rate moves by less than 1 Hz and every verdict is
  unchanged. VALIDATED (3 seeds, same input).
- **delays** changes every run a little (timing moves), but no number by more than
  about 1 Hz. VALIDATED (3 seeds).
- **adaptation** is the one switch that matters here. It weakens the paper's key
  contrast (JO-CE drives aBN1, JO-F does not): JO-F now drives aBN1 at 4.4 / 14.8 Hz
  (100 / 220 Hz input; published 0.8 / 5.0), which is 21% / 26% of the JO-CE response
  (published 3% / 7%). The mechanism, from the recorded rates: the three GABA cells
  that block JO-F slow down under adaptation (CB0443 79 to 64 Hz, the two CB0496 41 to
  31 and 58 to 45 Hz, JO-F at 220 Hz), so less inhibition reaches aBN1. Real flies
  showed no aBN1 response to JO-F (calcium imaging, Fig. 5h), so this moves the model
  AWAY from the real-fly result, though only just past the pre-registered line at 220 Hz
  and not past it at 100 Hz. PRELIMINARY: one adaptation strength (the Phase 7 default),
  3 seeds.
- **celltype and gap do nothing here.** celltype is identical to the published model
  in all 15 runs compared; gap in 14 of 15 (the other differs by one neuron firing
  or not, out of about 676). Identical output means the cells these switches change
  do not affect a single spike here (for gap they are smell-circuit cells, as with
  al_ln_literature), so these tests cannot judge them. Tests A and B were
  not run for them (time), and Test F's JO-F condition (F1) was not re-run; the other
  F conditions are identical.
- **Test F does not improve under any variant**: F1 (JO-F leaves aBN2 and aDN1 silent)
  and F7 (aBN2 excites aDN2; real flies show inhibition) are wrong in every variant run.
  aDN2 still fires with aBN2 driven: 8.8 Hz published, 8.5 delays, 3.3 adaptation.

### 3.4 Held-out feeding results (G1-G5, section 1.5)

MN9 (the proboscis-extension motor neuron) in Hz, published model, one value per seed
(30 trials each):

| Condition | MN9 without the extra cells | MN9 with them | Score |
|---|---|---|---|
| G1: sugar 40 Hz + OA-VPM4 50 / 100 Hz | 5.5 / 6.7 / 4.4 | 5.4 / 6.5 / 5.8 and 6.1 / 5.3 / 5.8 | can't tell (no change) |
| G1: sugar 50 Hz + OA-VPM4 50 / 100 Hz | 20.2 / 18.5 / 18.3 | 20.2 / 20.0 / 20.4 and 21.7 / 22.0 / 22.7 | can't tell (up 7-24%, not in every seed) |
| G3: sugar 40 Hz + ISNs 50 / 100 Hz | 5.5 / 6.7 / 4.4 | 2.8 / 3.0 / 3.7 and **2.6 / 1.9 / 2.3** | can't tell, then **wrong** (down) |
| G3: sugar 50 Hz + ISNs 50 / 100 Hz | 20.2 / 18.5 / 18.3 | 16.8 / 16.4 / 17.4 and **11.3 / 10.7 / 9.0** | can't tell, then **wrong** (down) |
| G4: water 160 Hz + ISNs 50 / 100 Hz | 10.2 / 11.3 / 10.3 | 11.8 / 12.1 / 12.0 and **17.2 / 19.1 / 17.4** | can't tell, then **wrong** (up) |
| OA-VPM4 or ISNs alone, 100 Hz | - | 0 / 0 / 0 | (information only) |

G2 and G5 (silencing): OA-VPM4 and the ISNs never fire during taste input in the model
(0 Hz in every seed), so silencing them changes nothing: **can't tell**, as
pre-registered.

**Published model: G1 can't tell, G2 can't tell, G3 wrong, G4 wrong, G5 can't tell.**
- The ISN result is reversed, both halves. In real flies, activating the four ISNs
  makes flies consume more sugar and less water. In the model, driving them at 100 Hz
  cuts the MN9 response to sugar roughly in half (19.0 to 10.3 Hz at sugar 50 Hz; 5.6
  to 2.3 Hz at 40 Hz) and raises the response to water by about 70% (10.6 to 17.9 Hz).
  At 50 Hz the direction is the same but smaller than the pre-registered 20% / 1 Hz
  line. PRELIMINARY: the readout differs (the paper measured how much flies drank; MN9
  is the start of feeding), the ISN mapping rests on the FlyWire cell-type name, and
  only the abstract of the source could be read. In the model the ISNs are
  acetylcholine cells (FlyWire's machine prediction, confidence 0.64-0.77); the paper
  shows they are regulated by a hormone and by osmolality, which the model does not
  have either, so this tests only what their wiring does when they fire.
- Why, in the wiring (`isn_wiring.py`, `results/isn_wiring.txt`; read from the
  connection table, not tested by silencing, so PRELIMINARY): the ISNs make no synapse
  onto MN9 and only two weak two-step routes to it. Their strongest targets are cells
  the model treats as inhibitory (glutamate or GABA: CB0453, four DNd01, DNge205,
  CB0296; 48% of their 5,923 output synapses), so driving them mostly spreads
  inhibition through the feeding centre, which fits the drop in the sugar response.
  The rise in the water response is not explained by a direct route; it probably runs
  through removal of inhibition (not traced).
- OA-VPM4 makes no synapse at all onto the 21 sugar neurons or MN9 in the connectome
  (4,280 output synapses elsewhere), which fits the paper's description of its
  terminals as lying "in close proximity to" the sugar-neuron axons rather than
  wired to them.
- OA-VPM4 barely moves MN9. That fits the source's own conclusion (abstract, re-read
  from Europe PMC at 18:36): OA-VPM4 "promotes feeding behavior by modulating the
  activity of sensory neurons" (octopamine acting through the OAMB receptor in the
  sugar neurons makes them respond more strongly to sucrose). In the model, the taste
  neurons are driven at a rate we set, and nothing can turn their sensitivity up (a
  synapse can only add or remove spikes), so a result that works this way cannot show
  up. That the model cannot represent
  it is VALIDATED (it follows from how the input is given); that this is why OA-VPM4
  does nothing here is PRELIMINARY.

Variants (mean MN9, Hz; sugar 50 Hz without / with ISNs 100 Hz; water 160 Hz without /
with ISNs 100 Hz; sugar 50 Hz with OA-VPM4 100 Hz):

| Variant | sugar, ISNs | water, ISNs | sugar, OA-VPM4 | G1 / G2 / G3 / G4 / G5 |
|---|---|---|---|---|
| published (none) | 19.0 to 10.3 | 10.6 to 17.9 | 19.0 to 22.1 | can't tell / can't tell / wrong / wrong / can't tell |
| al_ln_literature | identical | identical | identical | same |
| al_ln_literature+da_5ht_literature | 19.3 to 10.2 | 10.6 to 17.5 | 19.3 to 22.4 | same |
| delays | 21.2 to 11.9 | 9.9 to 17.1 | 21.2 to 25.1 | same |
| adaptation | 9.7 to 5.3 | 1.8 to 4.0 | 9.7 to 11.4 | G3 wrong; G4 can't tell (the water response still rises, but by only 1.0 Hz in one seed); the rest can't tell |

Every variant gives the same picture: the ISNs lower the sugar response and raise the
water response. Adaptation lowers all MN9 responses (sugar 50 Hz gives 9.7 Hz instead of
19.0), which is why its water result falls just under the 1 Hz line. VALIDATED that the
reversal does not depend on the variant (5 model versions, 3 seeds each; celltype and gap
were not run on the feeding tests); PRELIMINARY that it is a real disagreement with
flies (reasons above).

Only two real-fly feeding experiments (five tests) were mapped in the time available,
fewer than the three to six asked for. Other well-known feeding cells were searched for
by name in the FlyWire annotation table used here (Fdg, TH-VUM, PERin, IN1) and are not
named there, so mapping them would need anatomy work first.

### 3.5 Are the two grooming misses (F1, F7) real model behaviour? (Phase 6 checks)

PLAN.md Phase 6 says to re-check a surprise with parameter variations before believing
it. `robustness.py` re-ran the published model with every synapse 20% weaker and 20%
stronger (the paper's own robustness range; the input kick scales with it, but stays
far above threshold, so the driven cells still fire at the set rate), and ran F7 with
weaker aBN2 drive and with each aBN2 cell driven alone. Hz, mean of 3 seeds x 30 trials;
aDN2's resting voltage is -52 mV, so a mean voltage above -52 means aDN2 is being
pushed UP (excited), below means pushed down (inhibited).

| Check | Result | F1 / F7 |
|---|---|---|
| F1, synapses 20% weaker: JO-F 220 Hz | aBN2_1-3 0.0, aDN1 0.0 (aBN1 8.3) | still wrong |
| F1, synapses 20% stronger | aBN2_1-3 0.0, aDN1 0.4 (aBN1 2.3) | still wrong |
| F7, synapses 20% weaker: aBN2_1-3 200 Hz | aDN2 0.1 Hz, mean -48.6 mV (+3.4 mV) | still wrong |
| F7, synapses 20% stronger | aDN2 22.7 Hz, -49.0 mV | still wrong |
| F7, aBN2_1-3 at 100 / 50 Hz | aDN2 0 Hz; -49.8 / -51.0 mV (+2.2 / +1.0 mV) | still wrong |
| F7, one aBN2 cell at a time, 200 Hz | aDN2 0 Hz; -51.7 / -50.7 / -49.4 mV (all above rest) | still wrong |
| Test C, synapses 20% weaker / stronger | aBN1 69 / 83, aDN1 23 / 49, aDN2 23 / 41 Hz | holds |

In every check, aBN2 pushes aDN2 up, never down, and JO-F never reaches aBN2 or aDN1
(F6, aBN2 drives aDN1, stays right in every check: aDN1 3.5-93 Hz). So both misses are
robust model behaviour: VALIDATED as a property of the model. Whether they are real
disagreements with flies rests on two mappings: Hampel's "aJO" line = FlyWire JO-F
(Hampel et al. 2020 renamed it, so this is well supported), and aBN2 = the three 2026
IDs (supported by morphology matching, but the 2024 paper used a different cell).
So the mismatch itself stays PRELIMINARY.

### 3.6 Which neurons are required and sufficient for aDN1 (Tests D and E, published model)

**Test E (required), all 146 JONs at 140 Hz, each of the paper's 154 non-JON top-300
neurons silenced in turn**, 10 trials, the same random input as the unsilenced control
(aDN1 14.7 Hz). aDN1 relative to the control, ours versus the paper's file:

| Silenced | Ours | Paper |
|---|---|---|
| aBN1 | 0.00 | 0.00 |
| aDN2 | 0.64 | 0.63 |
| DNge220 (the paper's aBN2) | 0.80 | 0.75 |
| next two (unnamed) | 0.88, 0.91 | 0.85, 0.89 |

The same three neurons, in the same order, cross the 20% line, and no other: **holds**.
DNge220 only just crosses (a 20.4% cut, from 10 trials). The 146 single-JON silencings
were not run (they do not count toward the pass rule). The three 2026 aBN2 cells are not
among the paper's 300 neurons at all, because they never fire during JON input.
VALIDATED as a reproduction (one seed of 10 trials per neuron, paired with its control).

**Test D (sufficient), each of the same 154 neurons driven alone at 200 Hz**, 10 trials:
only aBN1 (aDN1 68.0 Hz; paper 68.5) and aDN2 (34.1; paper 33.6) drive aDN1 above 2 Hz,
and the only two below that are exactly the paper's two weak ones (720575940644072483:
1.1 Hz, paper 1.07; 720575940653315489: 0.3 Hz, paper 0.33). **Holds**, VALIDATED as a
reproduction (one seed of 10 trials per neuron; the 146 single-JON runs were not done).

## 4. What this means, and what to do next

1. **The reproduction is solid; the paper's grooming score is generous.** The fast
   engine reproduces the paper's grooming results almost exactly, a first check of it
   outside feeding. But the paper's "7 of 7 grooming predictions correct" did not
   include Hampel et al.'s own connectivity measurements. Against those, the model gets
   3 right and 2 wrong (F1, F7), and the two misses are robust. Both point at specific
   wiring: the three GABA cells that correctly stop zone-F sensors from driving aBN1
   (the paper's Fig. 5h success) also stop them reaching aBN2 and aDN1 (the F1 miss),
   and the model has no strong inhibitory route from aBN2 to aDN2 (F7).
2. **al_ln_literature has not been tested by a held-out result yet.** This lane shows
   the grooming and feeding circuits never activate the cells it changes. The next
   held-out test should be a published SMELL result that was not used to choose it
   (for example lateral inhibition between glomeruli in the antennal lobe, Olsen &
   Wilson 2008, *Nature* 452:956; not yet checked against what the fix was tuned on).
3. **Adaptation has a held-out cost.** Before making it the default, weigh the fact that
   it pushes the model away from a real-fly calcium-imaging result (JO-F does not drive
   aBN1). The effect is only just past the pre-registered line, and only one adaptation
   strength was tried.
4. **The ISN reversal is the most concrete new lead.** It is a real-fly result on the
   same feeding circuit the model was built for, and the model gets both halves
   backwards. Cheap next steps: read the full text of Jourjine et al. 2016 (blocked
   here) for the ISNs' transmitter and the exact behaviour measured; then silence the
   ISNs' main inhibitory targets (CB0453, DNd01, DNge205) in the model to find which
   route produces the reversal.
5. **Nothing here needed a change to `sim/`.** All scripts are in
   `experiments/heldout/`; every run saves as it goes and can be resumed.

## 5. What is not verified

- The paper says the Johnston's organ has 147 neurons; its code drives 146. We used
  146. Not checked why.
- The synapse counts onto aBN1 in the model's wiring table differ from those in the
  paper's text: JO-CE 77 and JO-F 69 here, "103 and 78 synapses, respectively" in the
  paper. Probably a snapshot or synapse-threshold difference. UNVERIFIED.
- aJO (Hampel et al. 2015) = FlyWire JO-F: based on Hampel et al. 2020 renaming aJO as
  JO-F; moderate confidence for the exact neuron set.
- aBN2's identity: two papers from the same lab disagree (DNge220 in 2024, three LB23
  cells in 2026); results are given for both.
- Feeding sources: only the abstract of Jourjine et al. 2016 could be read (full text
  blocked by a PMC reCAPTCHA and a Europe PMC 403); the Youn et al. 2018 abstract was
  read on Europe PMC. The readout (MN9) is not what either paper measured (consumption,
  proboscis extension to a sugar drop).
- The ISN wiring explanation is read from the connection table, not tested by
  silencing.

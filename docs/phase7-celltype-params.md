# Phase 7, upgrade 4: cell-type-specific neuron settings

Status: **PRELIMINARY.** Re-run with 3 random seeds (5 for the runaway tests) and with
variants of the two judgement calls, but the other PLAN.md Phase 6 steps (independent
review, sharing) have not been done.

Code: `sim/celltype_params.py` (the upgraded engine, `CellTypeBrain`).
Tests: `tests/test_celltype_params.py`.
The measured numbers: `experiments/phase7_celltype/celltype_params.csv` (one row per number,
with its paper, page or figure, recording conditions, and whether and how it is used).
Experiments: `experiments/phase7_celltype/` (`run_celltype.py` runs, `analyze.py`
summarises, `results/summary.md` has every number, `log-entry.md` is the EXPERIMENTS.md text).

## The short version

The published model gives all 127,400 neurons the same settings. This upgrade gives a
cell type its own settings wherever somebody has measured that cell type in a real fly with
an electrode and the number can be translated honestly into this model.

- **What changed: 5,477 neurons (4.3% of the brain), in four cell types.** Kenyon cells
  (the 5,177 neurons of the mushroom body, the fly's learning centre), 251 smell
  "projection neurons" of the antennal lobe, 42 P-EN neurons of the navigation centre, and
  7 large LNv clock neurons. Everything else keeps the shared values.
- **The sugar result and every other Phase 3 check hold, trivially.** In all five taste
  checks (3 seeds x 30 trials) every neuron fired exactly the same number of spikes as in
  the baseline. The reason: none of the 5,477 changed neurons fires at all in those
  experiments, in either model. The taste-to-MN9 pathway has no published electrode
  measurements we could find, so it was not touched.
- **Runaway activity: unchanged.** 6 of 150 trials (sugar 200 + Ir94e 200) and 19 of 150
  (Ir94e alone) in both models. The runaway loop runs through antennal-lobe local neurons,
  and no usable measurement exists for them.
- **Where it matters: the Kenyon cells.** Real Kenyon cells need a big push to fire (21.5 mV
  above rest, versus 7 mV in the model). With that measured value, when the smell centre is
  driven (DM1 smell neurons, the vinegar channel), 4.1% of Kenyon cells fire in a trial
  instead of 64%. Real flies: 6 +/- 5% (Turner et al. 2008). The mushroom-body output
  neurons that Kenyon cells drive drop from 70 firing at about 100 Hz to 25 at about 25 Hz.
  The antennal lobe itself still "catches fire" (the Phase 5/6 problem), because nothing
  in the antennal lobe changed.

**Verdict: passes the Phase 3 checks (identical results), does not break or fix the
runaway, and makes the Kenyon-cell layer sparse in the way real flies are. Keep it,
labelled PRELIMINARY; it matters most for Phase 8 (learning).**

## 1. What was measured, and what was used

The literature table has 27 rows (including "nothing found" rows and one benchmark). Every number used in the model was read in the paper
itself (full text), and the table says where. Page numbers are given where the paper
has them in the version read (Turner et al. 2008 is a PDF with page numbers; the others
were read as PubMed Central web pages, so the table gives section, figure or table).

| Cell group (FlyWire, snapshot 630) | Neurons | Time constant | Threshold above rest | Resting potential | Source (read) |
|---|---|---|---|---|---|
| Kenyon cells (`cell_class = Kenyon_Cell`) | 5,177 | **11.2 ms** (authors' one-compartment value, tuned to the measured 11.5 ms synaptic potential) | **21.5 mV** (+/- 5.6, 17 cells) | -57.8 mV | Turner, Bazhenov & Laurent 2008, J Neurophysiol 99:734, pp. 737 and 741, Fig. 3G |
| Smell projection neurons, one glomerulus each, cholinergic (`ALPN`, uniglomerular, acetylcholine) | 251 | **22.9 ms** (resistance x capacitance, 3 DM1 cells) | **10 mV** (18 DA1 cells) | -57.8 mV | Gouwens & Wilson 2009, J Neurosci 29:6239, Table 1, Fig. 7; Jeanne & Wilson 2015, Neuron 88:1014, Fig. 4C |
| P-EN neurons, central complex (`PEN_a`, `PEN_b`) | 42 | not measured: shared 20 ms | **12.0 mV** (mean of 8 recordings) | -46.1 mV | Turner-Evans et al. 2017, eLife 6:e23496, Supplementary file 1 |
| Large LNv clock neurons (`l-LNv`) | 7 | **3.66 ms** (305 MOhm x 12 pF) | not usable: shared 7 mV | -49 mV | Sheeba et al. 2008, J Neurophysiol 99:976, Results |
| everything else | 121,923 | 20 ms | 7 mV | -52 mV | Shiu et al. 2024 (shared values) |

Numbers found but **not used**, and why (details in the CSV):

- **Input resistance** of projection neurons (598 MOhm), Kenyon cells (>10 GOhm), P-ENs
  (1.9 GOhm), antennal-lobe local neurons (1-4 GOhm), clock neurons (305 MOhm): the model
  has no electrical current, see section 2.
- **Kenyon cell time constant at the cell body, >200 ms** (Turner 2008, p. 741): see
  section 2; run as a variant.
- **Antennal-lobe local neurons**: threshold -39 mV (Wilson & Laurent 2005) but no resting
  potential from the same cells, so no gap can be formed. This is the cell type at the
  heart of the runaway problem, so this gap in the literature matters.
- **Lateral horn neurons**: about 10 mV to threshold (Jeanne & Wilson 2015, Fig. 7A), but
  the paper does not say which FlyWire types were recorded, so no neuron can be assigned.
- **Large LNv threshold**: "typically between -40 and -50 mV" with rest at -49 mV, which
  allows any gap from 0 to 9 mV: too vague.
- **Giant fiber** (input resistance 50-100 MOhm): only seen quoted in a search result,
  the paper (von Reyn et al. 2014) was **not read**: UNVERIFIED, not used.
- **Nothing found** for MN9, other taste (SEZ) neurons, or mushroom-body output neurons
  (the two Hige et al. 2015 papers were searched; their Extended Data were not read).
- **Visual neurons**: not read; many recorded fly visual neurons signal with graded
  voltages instead of spikes, which a spike threshold cannot represent. UNVERIFIED.
- **Refractory period**: none of the papers read reports one, so every neuron keeps 2.2 ms.

## 2. How a measured number becomes a model setting

The model neuron is a "leaky bucket": input pours voltage in, the voltage leaks back to
rest, and when it passes a threshold the neuron fires and is reset. It has only four
settings that can differ between neurons.

- **Membrane time constant (how fast the bucket leaks).** Used directly. For projection
  neurons the paper gives the membrane's resistance and capacitance per square centimetre;
  multiplied together they are the time constant (8.3 x 2.6 = 21.6 ms, and so on; mean of
  3 cells 22.9 ms). For clock neurons: the whole cell's resistance x its capacitance.
- **Threshold, always as a gap above the neuron's own rest.** In this model every synapse
  adds a fixed number of millivolts, whatever the voltage is. So what decides whether a
  neuron fires is only how far threshold sits above rest, not where rest is. We therefore
  take threshold minus rest from the same recordings (21.5 mV for Kenyon cells, 10 mV for
  projection neurons, 12 mV for P-ENs). A test (`test_only_the_gap_matters_not_the_resting_level`)
  proves that moving rest alone changes no spike.
- **Resting potential.** Stored, but on its own it has no effect in this model (it would
  matter for the conductance synapses of upgrade 2, which are not stacked here).
- **Refractory period.** No measurement found; 2.2 ms for all.

What **cannot** be used:

- **Input resistance and threshold current.** In a real neuron a synapse delivers a
  current, and the voltage it causes is current x resistance. The model skips the current:
  each synapse is already "0.275 mV". Scaling that by each cell's resistance would be the
  obvious translation, but there is published evidence against it: in projection neurons
  the synapses are matched to the cell's resistance so that one input gives the same
  voltage in every type (Kazama & Wilson 2008, Neuron 58:401, Fig. 4). And for Kenyon cells
  the cell-body numbers do not fit a one-compartment neuron at all: about 10 pA to fire
  (Hige et al. 2015) x more than 10 GOhm would put threshold more than 100 mV above rest,
  while the directly measured gap is 21.5 mV. Real neurons have long thin branches; the
  cell body is not the whole story.
- **The Kenyon cell's slow cell-body time constant (>200 ms).** In a one-compartment model
  the time constant also sets how fast a single synaptic input fades. Measured Kenyon cell
  synaptic potentials fade in 11.5 ms, and the authors' own one-compartment model used
  11.2 ms to reproduce that. We use 11.2 ms and ran 200 ms as a variant.

A judgement call: the projection-neuron gap. Jeanne & Wilson measured 10 mV directly
(average voltage to spike threshold, 18 cells). Combining two other papers
(threshold near -40 mV, Wilson & Laurent 2005; seal-corrected rest -57.8 mV, Gouwens &
Wilson 2009) would give 17.8 mV. The main version uses the direct 10 mV; 17.8 mV is a variant.

Mapping to FlyWire: the recorded cells were DM1 and DA1 projection neurons, a mix of
Kenyon cell subtypes, P-ENs labelled by one driver line, and large LNvs. We extended each
value to its whole FlyWire class (all 251 cholinergic single-glomerulus projection neurons,
all 5,177 Kenyon cells, both FlyWire P-EN types, all 7 large LNvs). This assumes cells of one
class are alike, which is an approximation: Kazama & Wilson 2008 argue that projection
neurons with larger dendrites (larger glomeruli) have lower input resistance.

## 3. How it was built

`CellTypeBrain` is a subclass of the baseline engine with a copy of its compiled loop in
which rest, threshold, reset and time constant are looked up per neuron (neurons are
sorted into groups; group 0 = the shared values). `sim/fast_engine.py` was not edited.
The model with the upgrade off, or on with no measured values, gives the baseline's spikes
and voltages exactly, spike for spike (tests on small random networks and on the whole
brain). Other tests check that each group's time constant really produces the exact
textbook voltage curve, that a bigger gap blocks a spike the shared gap lets through, and
that neurons outside a changed group are untouched.

## 4. Checks against the Phase 3 baseline

3 seeds x 30 trials x 1 s per condition (seeds as in Phase 3/7). The baseline here
reproduced the Phase 7 baseline files exactly (20 of 20).

| Check (holds only if every seed passes) | baseline | upgrade |
|---|---|---|
| sugar 100 Hz drives MN9 (>= 20 Hz): 67.3 Hz | pass/pass/pass | pass/pass/pass (67.3 Hz) |
| sugar 200 Hz > sugar 100 Hz: 93.5 Hz | pass x3 | pass x3 (93.5 Hz) |
| MN9 on the opposite side > same side | pass x3 | pass x3 |
| water 200 Hz drives MN9, less than sugar: 30.8 Hz | pass x3 | pass x3 (30.8 Hz) |
| bitter alone: MN9 silent: 0 Hz | pass x3 | pass x3 (0 Hz) |
| sugar 100 + bitter 120: MN9 near 0: 1.4 Hz | pass x3 | pass x3 (1.4 Hz) |
| sugar 200 + Ir94e 200: lower than sugar, not abolished: 63.6 Hz | pass x3 | pass x3 (63.6 Hz) |

**Neuron by neuron.** In the five taste checks every neuron's spike count is identical
(correlation 1.000, top 50 identical, no neuron active in only one model). None of the
5,477 changed neurons fires in those conditions in either model, so they cannot change
anything downstream. For comparison, the same baseline model run with 3 new seeds
(`baseline_newseeds`, the noise floor) differs from itself more than that: correlation
0.99991-0.99998, 49-50 of the top 50 shared, and 6 to 29 neurons active in only one of the
two runs.

**Runaway (Phase 6 definition: more than 1,500 different neurons firing in one 10 ms
slice).**

| Condition | baseline | upgrade | p (Fisher) |
|---|---|---|---|
| sugar 200 + Ir94e 200 (150 trials) | 6 (4.0%) | 6 (4.0%) | 1 |
| Ir94e 200 alone (150 trials) | 19 (12.7%) | 19 (12.7%) | 1 |

The same trials run away, with two exceptions in the Ir94e set (one trial stops tipping,
another one starts). In the trials that do NOT run away, not a single projection neuron or
Kenyon cell fires, in either model, so the upgrade has nothing to act on there. Inside a
runaway trial the brain still ignites; the difference is in the mushroom body: over the 150
Ir94e trials, 3,353 different Kenyon cells fired in the baseline and 210 with the upgrade.

## 5. Where the upgrade does change things: smell and the mushroom body

The 68 DM1 smell receptor neurons (both antennae) at 150 Hz, 3 seeds x 30 trials x 1 s.
In both models every trial ignites the antennal lobe (the Phase 5/6 problem, untouched
here). What happens downstream:

| | baseline | upgrade |
|---|---|---|
| Kenyon cells firing per trial | 3,325 (64.2%) | 212 (4.1%) |
| Kenyon cells active in any of the 90 trials | 3,383 | 250 |
| Mushroom-body output neurons active (of 97) | 70, about 104 Hz | 25, about 25 Hz |
| Dopamine neurons active (of 326) | 141 | 17 |
| Projection neurons active (of 685) | 546 | 529 |
| Antennal-lobe local neurons active (of 424) | 354 | 348 |
| Spikes per trial (median) | 465,538 | 260,307 |

Real flies: 6 +/- 5% of Kenyon cells respond to a given odor (Turner et al. 2008, p. 739,
Fig. 2A legend, 71 cells; their criterion: firing rate more than 3.5 standard deviations
above the cell's baseline; ours: at least one spike in the 1 s trial, which is stricter
for a cell that never fires spontaneously, as in this model, so the two are close but
not identical). The Kenyon cells' measured high threshold alone brings
the model into that range, even while the antennal lobe above them is in its unrealistic
runaway state. The projection-neuron and antennal-lobe numbers barely move, which fits:
their inputs during ignition are huge, and the 3 mV larger projection-neuron gap does not
matter there.

## 6. Variants and which group does what

Two questions: which of the four groups causes the changes, and do the two judgement
calls (section 2) matter? Each version below was run on the two runaway conditions
(150 trials each) and on the DM1 smell condition (1 seed = 30 trials; baseline and main
version: 90 trials). The five taste checks were not re-run for these versions: the changed
neurons are silent there in every version tried, and in this model a slower leak or a
higher threshold cannot make a silent neuron fire (the average voltage a steady input
produces does not depend on the time constant).

| Version | What differs from the baseline | Runaway: sugar 200 + Ir94e / Ir94e alone | Kenyon cells firing per smell trial | DM1 projection neuron rate |
|---|---|---|---|---|
| baseline | nothing | 6/150, 19/150 | 64.2% | 283 Hz |
| **upgrade (main)** | all four groups | 6/150, 19/150 | **4.1%** | 261 Hz |
| projection neurons only | 251 PNs: gap 10 mV, 22.9 ms | 6/150, 19/150 | 53.4% | 260 Hz |
| Kenyon cells only | 5,177 KCs: gap 21.5 mV, 11.2 ms | 6/150, 19/150 | 9.0% | 284 Hz |
| PN gap 17.8 mV (two papers combined) | main, but PN gap 17.8 | 6/150, 19/150 | 1.4% | 227 Hz |
| KC time constant 200 ms (cell-body value) | main, but KC 200 ms | 6/150, 19/150 | 3.1% | 261 Hz |

Real flies: 6 +/- 5% of Kenyon cells (Turner et al. 2008).

- **The Kenyon cells' own threshold does most of the work** (64% -> 9%). The projection
  neurons' slightly higher threshold removes a bit more (9% -> 4.1%) and lowers the DM1
  projection neurons from 283 to 261 Hz. P-ENs and clock neurons never fired in any
  condition tested, so their values had no effect here (they are not on any pathway these
  experiments drive).
- **Both judgement calls leave the conclusion unchanged.** Every version with the measured
  Kenyon cell threshold lands between 1% and 9%, inside or near the real range; none
  changes the runaway rate (all p = 1).
- In the runaway conditions the Kenyon cell fractions per runaway trial follow the same
  order (projection neurons only 52%, Kenyon cells only 7.5-7.8%, PN gap 17.8 mV and
  KC 200 ms about 1%; `results/smell_and_kc.csv`).

## 7. Verdict

- **Does it break the sugar result? No.** Every Phase 3 check passes on every seed, with
  numbers identical to the baseline to the last spike. That is not a strong test of the
  upgrade: it passes because none of the measured cell types lies on the taste pathway.
  The honest reading is "no conflict with Phase 3", not "Phase 3 confirms these values".
- **Is it right?** For the one place where it can be compared with real flies, yes in
  direction and roughly in size: with measured Kenyon cell thresholds, 4% of Kenyon cells
  respond to a smell (real: 6 +/- 5%) instead of 64%. This holds for both judgement-call
  variants (1-9%).
- **What it does not do:** it does not stop the runaway / smell ignition. That lives in
  the antennal-lobe local neurons, for which no measurement usable in this model was
  found (their resting potential is missing), and in their transmitter labels (Phase 5/6).
- **Recommendation:** keep it as an optional switch, labelled PRELIMINARY; worth turning
  on for Phase 8 (mushroom-body learning), where a Kenyon-cell layer that fires 64% of the
  time for every smell would make every odor look the same. Before stacking it with other
  upgrades, each must pass on its own (it does) and the stack must be re-checked.

## 8. Limitations and what was not verified

- **Coverage is small and off the tested pathway.** 4.3% of neurons, none on the
  taste-to-MN9 pathway. So "the sugar result still holds" is true but says nothing about
  whether the measured values are right; the smell / Kenyon cell comparison is the only
  place the upgrade is tested against biology, and that comparison is made inside a
  runaway state that is itself unrealistic.
- **One recorded type stands for a whole class** (section 2).
- **Recording conditions differ**: whole-cell recordings in living flies (most), a brain
  explant at 24 C (clock neurons), male flies (Jeanne & Wilson), resting potentials
  corrected for the electrode's leak (Gouwens & Wilson) or not (Turner-Evans: liquid
  junction potential not corrected). Temperatures were not stated in the texts read,
  except Sheeba et al.
- **Derived numbers** (computed here from the papers' values, marked READ+DERIVED in the
  CSV): the projection neuron and clock neuron time constants, the Kenyon cell 11.2 ms,
  the P-EN means.
- **Not read**: von Reyn et al. 2014 (giant fiber), the supplementary figures of Wilson &
  Laurent 2005, the Extended Data of Hige et al. 2015, papers on visual neurons, and several
  papers behind paywalls (for example Seki et al. 2010 on antennal-lobe local neurons,
  J Neurophysiol, blocked to automated download). There may be usable measurements there,
  especially for the antennal-lobe local neurons.
- The upgrade was run on its own, not stacked with upgrades 1-3 or with any sign fix.
- PLAN.md Phase 6 steps 5-6 (write-up review, sharing) not done: **PRELIMINARY**.

## Files

- `sim/celltype_params.py`: the engine and the translation rules.
- `tests/test_celltype_params.py`: 18 tests (1 whole-brain).
- `experiments/phase7_celltype/celltype_params.csv`: the literature table.
- `experiments/phase7_celltype/run_celltype.py`, `analyze.py`; `results/` (raw `.npz`
  per run, `summary.md`, `readouts.csv`, `checks.csv`, `runaway.csv`, `per_neuron.csv`,
  `group_rates.csv`, `smell_and_kc.csv`, `top_changes.csv`, run logs).

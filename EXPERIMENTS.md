# Experiments log

Every experiment gets: the date, what was changed, what happened, and whether
the result was validated (see PLAN.md Phase 6). Newest entries at the bottom.

---

## 2026-09-22: Phase 0, environment check
- **Changed:** Created the Python 3.13 environment and installed numpy, pandas,
  pyarrow, matplotlib, brian2 2.10.1, scipy, pytest.
- **Happened:** One simulated neuron with a steady input fired 8 times in
  200 ms, which matches the hand calculation (it takes about 24 ms to charge up
  to threshold each time, and 200 / 24 is about 8).
- **Note:** This machine has no C++ compiler, so Brian2 falls back to its
  slower pure-Python (numpy) mode. That is fine for small networks but may be
  too slow for the whole brain. Decision needed before Phase 3.
- **Validated:** Yes, as an install check only. Not a scientific result.

## 2026-09-22: Phase 1, toy spiking network
- **Changed:** Built a 100-neuron test network (80 excitatory, 20 inhibitory,
  each wired at random to about 10 others) in `sim/toy_network.py`. The neuron
  model and all its numbers (rest and reset -52 mV, threshold -45 mV, 20 ms
  leak, 5 ms synapse decay, 2.2 ms rest after a spike, 1.8 ms delay, 0.275 mV
  per synapse) are copied from the reference paper's code, and a test checks
  they still match. Two switchable outside inputs: a steady excitatory
  "background", and a "test input" that can be excitatory, inhibitory or off.
  Toy-only choices (network size, wiring, input strengths, inhibitory
  connections 4 times stronger so activity cannot run away) are marked [TOY]
  in the code.
- **Happened (500 ms runs, seed 1):** no input: 0 spikes. Background only:
  1,010 spikes (20 per second per neuron). Background plus excitatory input:
  1,919 spikes (38 per second). Background plus inhibitory input: 80 spikes
  (1.6 per second). The same pattern held for 5 different seeds (excitation
  gave 1.8 to 1.9 times the baseline; inhibition cut it to 6 to 9 percent).
  Plots: `experiments/phase1/raster.png`, `experiments/phase1/voltage_trace.png`.
  Plain-English guide: `docs/phase1-explained.md`.
- **Validated:** Yes, for the Phase 1 checkpoint: `tests/test_toy_network.py`
  (5 tests, all pass) confirms excitatory input raises firing, inhibitory input
  lowers it, zero input gives zero spikes, results repeat exactly with the same
  seed, and the neuron numbers match the reference. This is a learning exercise,
  not a scientific result.

## 2026-09-22: Phase 2, load the real fly brain
- **Changed:** Added `sim/connectome.py`, which loads the FlyWire wiring
  diagram (release 783 by default; release 630, the one the Shiu et al. paper
  used, on request) from the reference paper's files, attaches per-neuron
  labels from Schlegel et al. 2024 (cell type, class, predicted
  neurotransmitter, 3D position; downloaded without an account, pinned by
  checksum), and gives a connection table plus a sparse connection matrix
  (weight = synapse count, sign from neurotransmitter: acetylcholine +,
  GABA and glutamate -, everything else +, the reference paper's assumption).
  Results are cached in `data/cache/`.
- **Happened:** Release 783 has 138,639 neurons, 15,091,983 connections and
  54,492,922 synapses. Published FlyWire numbers (Dorkenwald et al. 2024):
  139,255 neurons, 54.5 million synapses, 2,700,513 connections of 5+
  synapses between 134,181 neurons. Our 5+ counts match exactly
  (2,700,513 and 134,181), and every one of our 15,091,983 connections matches
  FlyWire's official Zenodo table pair for pair, synapse count for synapse
  count. The 616 missing neurons all have zero synapses with any other neuron,
  so leaving them out cannot change a simulation. Release 630 has 127,400
  neurons, the number the paper states. Our neurotransmitter-based signs agree
  with the reference file's signs for 95.6% of neurons (98.8% of connections,
  98.9% of synapses) in 783 and 98.5% of neurons in 630; the disagreements
  are almost all neurons whose neurotransmitter guess was low-confidence.
  The loader keeps both signs; Phase 3 will use the reference file's.
  Loading takes 5 to 13 s the first time and about 0.3 to 0.5 s from cache.
  The most connected neurons are giant inhibitory wide-field cells (CT1, APL,
  Li33, LPi15). 60% of synapses are excitatory, 40% inhibitory.
- **Validated:** Yes, as a data check (not a scientific result): counts
  match the published numbers, the connection list matches FlyWire's official
  table exactly, and 20 fast + 7 slow automated tests pass. Not verified:
  the exact rule the paper used to pick each neuron's sign (reproducing it
  needs the 9.5 GB per-synapse file, not downloaded); our closest
  re-derivation agrees for 96.9% of neurons.
- **Checkpoint:** PASS (counts match; cached load under half a second).
- Details: `docs/phase2-explained.md`, `experiments/phase2/summary.txt`,
  `experiments/phase2/crosscheck_zenodo.txt`.

## 2026-09-22: Fast whole-brain engine (no compiler needed)
- **Changed:** Added `sim/fast_engine.py`, a re-implementation of the paper's
  model (`data/reference/model.py`) that runs fast without a C compiler. Every
  rule is copied from the reference, and from what Brian2 actually does with it:
  the same equations, parameters, 0.1 ms step, 1.8 ms delay, 2.2 ms refractory
  period, reset, weights, Poisson input and silencing. It loads either
  connectome snapshot (`"630"`, the paper's, or `"783"`). This added numba
  0.67.0 and llvmlite 0.49.0 to the environment; they need pinning in
  requirements.txt.
- **Happened:**
  - **Speed.** One 1-second trial of the whole brain now takes 0.38 s on one
    core (sugar at 100 Hz) or 0.48 s (200 Hz). Brian2 without a compiler
    takes 21-55 s, so that is 45-145 times faster. The paper's 30-trial
    experiment takes about 7-10 s on two cores instead of 30-60 minutes.
  - **Small networks, same input as Brian2.** Four random networks, each
    firing 900-1,060 spikes. Every spike landed on the same 0.1 ms step as in
    the reference's own Brian2 code, and the voltage traces were identical to
    the last digit. Two bugs planted on purpose (letting input through during
    the refractory period; a one-step delay error) were both caught.
  - **Whole brain against the paper authors' own Brian2 output (v630,
    30 trials).** Rates across all neurons correlate at r = 0.9996-0.9998.
    99.4-100% of neurons agree within 3 standard errors (the random noise).
    MN9 with sugar at 100 Hz: 67.6 Hz here, 67.0 Hz in their file, 65.7 ± 3.3
    in the paper. At 200 Hz: 92.9 Hz here, 93.3 Hz in their file, 93.2 in the
    paper. The three silencing runs from the tutorial also match (MN9 within
    0.7 Hz).
  - **Against the Phase 3 Brian2 port (10 trials each).** Sugar at 100 Hz:
    r = 0.9992, MN9 69.7 vs 67.0 Hz. Water at 200 Hz: r = 0.9996, MN9 29.7 vs
    33.5 Hz. Both MN9 gaps are under 2 standard errors.
  - **Finding.** The reference file `results/example/sugarR.parquet` was made
    with **200 Hz** input, not 150 Hz: its stimulated neurons fire at
    196.75 Hz, which is what 200 Hz input gives. Do not compare 150 Hz runs
    against it.
- **Validated:** Yes. The engine matches Brian2 exactly on small networks. On
  the whole brain it matches, within random noise, both the authors' published
  output and our Brian2 port. Only the random input numbers differ from
  Brian2's, so single trials differ but averages agree. Not yet compared: the
  bitter and competition conditions, and v783. The Phase 3 port had not
  finished those; `compare_phase3.py` covers them when they are done.

## 2026-09-22: Phase 4, interactive explorer app

- **Built:** A small website that runs on this computer
  (`.venv\Scripts\python.exe -m app`, then open http://127.0.0.1:8765). You can
  choose the brain map (FlyWire snapshot 630, the paper's, or 783), search
  neurons by cell type, label or FlyWire id, and put them in Stimulate /
  Silence / Watch lists. You then run the whole brain for a chosen length,
  number of trials, seed and input rate, and get a replayed spike raster and a
  ranked table of the most active neurons. Runs happen in the background so
  the page never freezes. Setups are saved as small files in `app/setups/`.
  Each one holds every setting needed to re-run exactly, including the
  snapshot, the engine name and a fingerprint of its code. A ready-made setup,
  `sugar_grn_right`, holds the paper's sugar experiment: snapshot 630, the 21
  right-side sugar taste neurons from the reference notebooks, 100 Hz input
  (as in Phase 3's sugar_100Hz run), 1000 ms, 30 trials, seed 0, with both
  MN9 feeding motor neurons on the watch list.
- **Engine:** the app reaches the simulator only through
  `app/engine_adapter.py`. It uses `sim/fast_engine.py` (FastBrain, built once
  per snapshot when the app starts) and the Phase 2 neuron lists from
  `sim/connectome.py`. If the fast engine cannot be imported, the app uses the
  slow Brian2 port (`sim/shiu_model.py`) and says so. If no engine loads at
  all, Run is switched off and a yellow banner, which cannot be closed, says
  why. The app never makes up results. A stand-in engine exists only for the
  fast automated tests, and it is clearly labelled whenever it is on.
- **Happened (Phase 4 checkpoint):** the saved sugar setup was run twice with
  the same seed: straight through the fast engine, and through the app's own
  web requests. The answers matched exactly. MN9 (720575940660219265) fired
  at 67.63 Hz both ways, the other MN9 (720575940645521262) at 49.60 Hz both
  ways, and all 409 neurons that fired had the same rate (largest difference
  0.000000 Hz). Each run took 13 to 15 s. The web page, driven in a
  browser, showed the same 67.63 Hz. An earlier run of the same check on
  snapshot 783 (150 Hz) also matched exactly for all 435 neurons that fired.
- **Tests:** `tests/test_app.py`, 19 passed in 37 s, including one test marked
  "slow" that repeats the checkpoint against a separately built FastBrain.
  18 fast tests run in about 5 s.
- **Validated:** Yes for the Phase 4 checkpoint: the app and code give
  identical results. This is a check of the app, not a new scientific
  finding. The MN9 response itself comes from Phase 3.

## 2026-09-22: Phase 3, reproduce the published result (Brian2, snapshot 630)
- **Changed:** Ported the paper's own model code (`data/reference/model.py`) to
  `sim/shiu_model.py` so it runs on this laptop. Every equation, parameter, weight and sign
  rule is identical (a test checks this against their file). Five practical changes, none of
  which touch the maths: Brian2's pure-Python engine (no C++ compiler here), the brain is built
  once per experiment instead of once per trial, every trial has a recorded random seed,
  silencing is done with an equivalent faster method, and firing rates are computed exactly like
  their `utils.get_rate`. Used the paper's own wiring-diagram snapshot (630).
- **Ran:** 7 experiments, REDUCED protocol: 10 trials of 1 s for sugar 100 Hz, sugar 200 Hz,
  water 200 Hz, sugar 100 + bitter 120 Hz; 5 trials for bitter 200 Hz alone, sugar 100 +
  bitter 40 Hz, sugar 200 + Ir94e 200 Hz (the paper used 30 trials). Results, seeds and settings
  are in `experiments/phase3/results/v630/`.
- **Happened:** MN9, the feeding motor neuron, behaves as in the paper in all 12 checks:
  sugar 100 Hz 67.0 (paper 65.7), sugar 200 Hz 92.7 (93.2), water 33.5 (30.7), bitter alone
  0.0 (0.0), sugar + bitter 40 Hz 48.0 (45.3), sugar + bitter 120 Hz 0.9 (1.5), strong sugar +
  Ir94e 58.4 (64.3), all in spikes per second. Neuron by neuron, our sugar runs match the
  reference code's own saved 30-trial runs with correlation 0.9996 (200 Hz) and 0.9992 (100 Hz),
  and no neuron differs by more than noise would explain.
- **Surprise:** in 2 of 5 trials of "sugar 200 + Ir94e 200", the whole model suddenly switched
  into runaway activity (about 8,300 neurons firing non-stop, up to 364,000 spikes in a second,
  against about 21,000 normally). No other trial did this. Probably a real property of the model,
  not a bug, but not yet checked. Needs Phase 6 treatment (more seeds) before that experiment is
  used for anything.
- **Not done:** the snapshot 783 cross-check with Brian2 (dropped for time and memory; the fast
  engine covers 783). The paper's MN9 numbers for water, bitter and Ir94e were taken from
  `docs/reference-notes.md` and not re-checked here (UNVERIFIED); their directions were checked
  against the paper's text.
- **Validated:** Yes for the Phase 3 checkpoint (same neurons respond, same direction, similar
  strength), with the reduced trial count noted. The Ir94e runaway observation is NOT validated.
- **Explained in plain English:** `docs/phase3-explained.md`. Side-by-side table:
  `experiments/phase3/comparison_table.md`.

## 2026-09-22 — Phase 5 Sensitivity: do the three paper results survive ±20% changes? (PRELIMINARY)

**What was changed.** Nothing in the model itself. We re-ran the paper's three MN9 results (sugar
100 Hz turns MN9 on; water 200 Hz turns MN9 on; bitter 120 Hz added to sugar 100 Hz suppresses MN9)
with each of seven model settings changed on its own by -20%, -10%, +10% and +20%: synaptic weight
(input kick held fixed), threshold (the 7 mV rest-to-threshold **gap** was scaled, not the -45 mV
value), membrane time constant, synaptic time constant, refractory period, synaptic delay, and
Poisson input rate. We also gave every one of the 14.7 million connections its own random weight
change of up to ±20% (15 random patterns; 5 planned, 10 added after one landed on the water
cut-off). Every point: 3 seeds x 30 trials x 1 s, snapshot 630, fast engine; 12,420 one-second
trials in total. The same model with 3 new seeds was run to measure pure random noise (about 1%).

**Rule (fixed before the runs).** "MN9 on" = at least 5 Hz; "bitter suppresses" = MN9 with bitter at
most 50% of sugar alone (same seed) with sugar alone on. A variation "holds" only if every seed
agrees; one failing seed = "flips".

**What happened.**
- Sugar turns MN9 on: **holds in all 28 setting changes and all 15 jitter patterns**. MN9 ranged
  35-80 Hz (baseline 67.0): the direction is robust, the size is not (-47% to +19%).
- Bitter suppresses sugar: **holds everywhere**. MN9 with bitter never exceeded 10% of sugar alone.
- Water turns MN9 on: **fragile**. It flips at synaptic weight -20% (0.02 Hz), threshold gap +20%
  (0.3 Hz) and synaptic time constant -20% (0.4 Hz), and in 1 of 15 jitter patterns (5.1 Hz, on the
  cut-off). MN9 ranged 0-65 Hz (baseline 30.7). Likely reason: at 200 Hz water sits just above its
  own switch-on point (the paper puts water's onset near 130 Hz), so any change that weakens signal
  passing between neurons switches it off.
- Four settings dominate (synaptic weight, threshold gap, synaptic and membrane time constants);
  refractory period and delay barely matter (at most about 10% and 2.5%).
- The top-50 most active downstream neurons stay mostly the same (at least 35 of 50 kept), but
  their order shifts under the big four settings (Spearman down to 0.57 for sugar vs 0.996 from
  random noise alone).
- Changing the cut-offs (1 or 10 Hz; 25% or 75%) does not change which results are robust.

**Validated?** No: PRELIMINARY. This is Phase 6 step 1 only (seeds and parameter variations).
Not tested: two or more settings changed at once; other snapshots; other operating points.

**Plain English.** Two of the paper's three results (sugar switches on the feeding motor neuron;
bitter taste shuts that off) survive every 20% nudge to the model we tried, so by the plan's
standard they look trustworthy. The water result does not: nudging the synapse strength, the firing
threshold or the synaptic time constant by 20%, or randomly scrambling synapse counts by up to 20%,
can switch it off. Exact firing rates move a lot with the settings for every result, so only the
yes/no direction should be trusted, not the numbers. New reusable tool: `sim/validation.py` runs
this same check on any future result. Write-up with plots: `docs/phase5-sensitivity.md`.

## 2026-09-22: Phase 5, sugar to MN9 pathway: tracing and silencing (PRELIMINARY)

- **Changed:** Nothing in the model. We used the fast engine, snapshot 630 and the paper's
  settings. Everything lives in `experiments/phase5/sugar_pathway/`. The write-up is
  `docs/phase5-sugar-pathway.md`.
  - **(1) Pathway tracing** (wiring only): fewest-hop and strongest routes from the 21 sugar
    GRNs to each MN9. A connection's cost is minus the log of its share of the receiving
    neuron's input, and each route is marked for whether it passes an inhibitory neuron.
  - **(2) Silencing screen**, 344 neurons. These are all neurons firing at 1 Hz or more under
    100 Hz sugar, plus 1 more from the paper's own list. Each was silenced alone at 100 Hz and
    at 50 Hz sugar.
    - Statistics: paired Wilcoxon test against the normal run, which had identical random
      input (seed 0), with Benjamini-Hochberg correction (q < 0.05).
    - Classes: blocks (ratio <= 0.5), reduces strongly (0.5 to 0.8), reduces weakly,
      increases, or redundant.
    - Two-stage design, adopted part-way through to save time: 10 trials first. Re-run at
      30 trials if the change was more than 2 standard errors or outside 90-110%. The first
      137 neurons at 100 Hz had already been run at 30 trials.
  - **(3) Groups**: both members of the paper's named cell types, 100 FlyWire cell types, the
    relays on the traced routes, and the "top k" single hits together.
  - **(4) Seeds 1-3** for the blocking and strongly reducing results, plus the 5 largest per
    frequency.
  - **(5) w_syn +/-20%** for the Roundup and route-set blocks.
- **Happened:**
  - **Wiring.** The fewest hops is 2, through 13 relays for the main MN9 (5 of them
    inhibitory). Five of the 13 never fire under sugar, and silencing any of the other 8 lowers
    MN9 by at most 10%. The strongest route is sugar GRNs -> G2N-1 -> Roundup -> MN9. Named
    neurons on the 20 strongest excitatory routes: G2N-1, Zorro, FMIn, Clavicle, Roundup,
    Rounddown, Roundtree and Sternum. Not on them: Bract, Fdg, Phantom, Rattle and Usnea.
  - **Single silencing at 100 Hz** (MN9 67.6 Hz; paper 65.7): 0 block, 2 strongly reduce (the
    left and right Roundup, 0.74 and 0.78), 19 weakly reduce, 9 increase (8 of them
    inhibitory brakes; DNge031 1.38) and 314 are redundant.
  - **Single silencing at 50 Hz** (MN9 20.6 Hz): 3 block (right Roundup 0.36, sugar GRN
    sugar_l_12 0.47, CB0277 0.50), 24 strongly reduce, 7 weakly reduce, 10 increase and 300
    are redundant.
  - **Groups.** Both Roundups together give 0.35 (100 Hz) and 0.19 (50 Hz). The top 3
    singles together give 0.05 and 0.14. The 17 neurons on the strongest routes together give
    0 at both rates. Two cell types (CB0821, CB0087) change MN9 only when both members are
    silenced, and those changes are small.
  - **Against the paper's own screen** (198 shared neurons): r = 0.93 at both rates. The same
    2 neurons are below the 20% line at 100 Hz. At 50 Hz, 19 of the paper's 21 are also below
    it in ours.
  - **Against real flies.** Clavicle, G2N-1, Zorro and Rattle are needed, and Bract and
    Phantom are not; both the model and the flies agree on these. The model disagrees with the
    flies on Roundup (the model says it is the bottleneck; flies do not need it), Usnea and
    FMIn. The paper reported the same disagreements.
  - **Seeds 1-3** (52 results): all 52 keep the same direction, and 50 of 52 stay
    significant. All 12 at 100 Hz keep their class, and 30 of 40 at 50 Hz do; the rest sit on
    a 0.5 or 0.8 class line. Examples: both Roundups 0.34-0.35 (100 Hz) and 0.19-0.25
    (50 Hz); the strongest-route set 0 in every seed.
  - **w_syn -20% / +20%**: both Roundups 0.17 / 0.37 and the route set 0 / 0, so the blocks
    hold.
- **Validated:** Partly.
  - **Checked:** it reproduces the paper's own silencing screen; the blocking and strong
    results survive 3 new seeds, and the key blocks survive w_syn +/-20%; the controls pass
    (all GRNs silenced gives MN9 = 0; a silent neuron gives an identical run); IDs and signs
    check out.
  - **Still PRELIMINARY:** everything as a statement about real flies (the model disagrees
    with experiment on Roundup, FMIn and Usnea, as the paper also reported); every seed-0-only
    result (weak effects, the 100 cell-type groups, the Phantom disinhibition chain); and the
    10-trial "redundant" calls, which can miss effects under about 5-10%.
  - **No new finding**, so Phase 6 step 6 does not apply. Not done: the paper's other six
    sugar rates, an activation screen, and snapshot 783.

## 2026-09-22 — Phase 5: competition between tastes (sugar vs bitter, Ir94e, water)

**What was changed.** Nothing in the model. New scripts in `experiments/phase5/competition/`:
- `job_server.py` builds the whole brain once (snapshot 630, fast engine, 2 threads) and
  runs every Phase 5 script in that one process.
- `run_grid.py` runs the input-rate grids, `analyze_competition.py` makes the tables and
  plots, and `suppressors.py` and `suppressor_robustness.py` search for the brake neurons.
- `phase5_common.py` holds shared helpers. It reads the paper's ID lists out of
  `sim/shiu_model.py` without importing Brian2.
- Write-up: `docs/phase5-competition.md`.

**What happened.**
- **The paper's anchor points reproduce** (30 trials, seed 0). Sugar 100 Hz alone gives MN9
  67.6 Hz (paper 67.0). Adding bitter at 40 / 80 / 120 / 200 Hz gives 47.7 / 13.4 / 1.4 /
  0.0 Hz (paper 45.3 / 11.7 / 1.5 / 0.0). Sugar 200 + bitter 200 gives 10.7 (paper 11.2).
  Sugar 100 + Ir94e 200 gives 4.1 (paper 2.5), and sugar 200 + Ir94e 200 gives 65.0
  (paper 64.3). Sugar 40 + water 200 gives 61.8 (paper 61.2). Every point is within
  2.5 Hz of the paper.
- **Sugar x bitter grid** (sugar 50-200 Hz x bitter 0-200 Hz, 3 seeds x 30 trials). The
  seed-to-seed spread is 1 Hz or less. MN9 falls along a steep S-curve, not a switch.
  - The Hill steepness n is about 2.9 to 3.8.
  - Going from 10% suppressed to 90% suppressed takes a 3.2- to 4.6-fold rise in bitter.
  - The tipping point b50 (MN9 halved) scales with sugar: 23 / 54 / 83 / 112 Hz of
    bitter at sugar 50 / 100 / 150 / 200 Hz. So bitter wins at about half the sugar rate.
  - A fine 10 Hz sweep (seed 0) agrees: b50 56 Hz at sugar 100, 119 Hz at sugar 200.
- **The brake neuron.** 22 inhibitory neurons are switched on by bitter. Silencing one
  of them, CB0219-left (720575940624600840, glutamate), restores MN9 from 12.4 to
  65.7 Hz with sugar 100 + bitter 80 (98% recovery, 3 seeds). With bitter 200 it gives
  55% recovery. Silencing the top 3 gives about 100% even at bitter 200.
  - It gets 247 synapses directly from the bitter GRNs and none from the sugar GRNs.
  - It inhibits the sugar pathway's middle-stage cells (CB0393, CB0493, CB0762 x2,
    DNge080), not MN9 itself.
  - The result holds at w_syn 80% / 100% / 120% (74% / 98% / 102% recovery).
- **Sugar + Ir94e** (3 seeds). At sugar 100 Hz, Ir94e 0 / 50 / 100 / 200 Hz gives MN9
  67.0 / 46.8 / 17.1 / 3.6 Hz (b50 68 Hz, a bit weaker than bitter). At sugar 200 Hz,
  Ir94e 200 Hz only lowers MN9 to 64.7 Hz. It does not abolish strong sugar, as the paper
  found.
- **Sugar + water** (3 seeds). The inputs combine synergistically. Sugar 40 (5.5 Hz) plus
  water 100 (0 Hz) gives 45.3 Hz. Sugar 20 (0 Hz) plus water 200 (30.7 Hz) gives 45.6 Hz.
  It saturates near 86 Hz at sugar 100.

**Validated?**
- **Yes** for the reproduction of the paper's sugar + bitter points (3 seeds, paper
  match, biology direction).
- **PRELIMINARY** for the tipping-point shape and ratio: no real-fly dose-response surface
  was compared.
- **PRELIMINARY / surprising** for "one glutamatergic neuron carries most of the bitter
  suppression". Checks done: 3 seeds, w_syn +/-20%, IDs and signs. Literature: real flies
  also use presynaptic GABA_B inhibition (Chu et al. 2014) and peripheral suppression,
  which the model lacks. A quick web search found no published name for CB0219.
  Nobody has been contacted (Phase 6 step 6 is the owner's call).

**Plain English.** Mixing bitter into sugar turns the feeding motor neuron down smoothly
but quickly. Bitter needs to be about half as strong as sugar to cut the response in half.
In the model, most of that "stop eating" signal runs through one inhibitory neuron. That is
a testable prediction, but not yet a finding.

## 2026-09-22 — Phase 5: unexplored area, smell (DM1 vinegar / DA2 geosmin) and the left/right question

**What was changed.** Nothing in the project's model. New scripts in
`experiments/phase5/unexplored/`:
- `run_olfaction.py`: the simulations. Its "lnfix" option is an exploratory variant
  that makes 53 antennal-lobe local neurons inhibitory **for that run only**, inside our
  own process, then restores the model and checks the restore.
- `analyze_olfaction.py`: tables and plots.
- `olf_ignition.py`, `phase6_ignition_check.py` (includes an independent simple
  simulator) and `phase6_ignition_lesions.py`: the runaway checks.
- `al_wiring.py` and `olf_paths.py`: wiring only, no simulation.
- `steering_ids.py`: the steering neurons as 630 IDs.
- Write-up: `docs/phase5-olfaction.md`.

**Cell-type filters checked on the 630 labels.** In snapshot 630 the ORN types sit in
`hemibrain_type`, not `cell_type`, so the Phase 8 doc's filter finds nothing there.
Counts: ORN_DM1 68 (35 L / 33 R), ORN_DA2 39 (16 L / 22 R / 1 unlabelled), ALPN 685,
KC 5,177, MBON 97, DAN 326.

**What happened.**
1. **The published model's smell system runs away.** If 3 DM1 ORNs fire once each,
   about 8,150 neurons switch on and keep firing on their own for the full second.
   That includes 65% of all Kenyon cells. With 2 ORNs, nothing spreads. Sugar controls
   do not do this.
   - The effect survives seeds 0-2 and w_syn 80-120%.
   - It is reproduced by an independent, from-scratch simulator (8,031 vs 8,177
     neurons), so it is not a bug in our engine.
2. **The cause is 53 LNs.** These antennal-lobe local neurons (types lLN1 / lLN2T and
   others) have a low-confidence transmitter guess of serotonin or dopamine, so the
   model treats them as excitatory.
   - Silencing them stops the runaway (26 neurons fire, none at the end).
   - Making them inhibitory also stops it, and leaves sugar -> MN9 exactly unchanged
     (67.6 / 67.3 / 66.2 Hz).
3. **With that fix (exploratory):**
   - **DM1 (both antennae, 150 Hz)** drives its PNs at about 170-200 Hz, 4% of Kenyon
     cells (realistic sparseness), 32 of 97 MBONs and 92 descending neurons.
   - **DA2** goes mainly to the lateral horn, reaches no Kenyon cells and only weakly
     reaches 16 descending neurons.
4. **Left/right, fixed variant** (3 seeds x 30 trials, 150 Hz):
   - Left-only and right-only DM1 both drive the **left** DNa02 (42.5 vs 36.4 Hz).
     The right DNa02 stays at 0 either way.
   - The cause is a left/right see-saw in the lateral accessory lobe. The left AOTU019
     (GABA) fires about 112 Hz and silences the right DNa02. It starts at the first
     synapse: the left DM1 PN gets more ORN synapses from both antennae (the same in
     snapshots 630 and 783).
   - Real flies show a 30-50% same-side PN advantage (Gaudry et al. 2013). The model
     has none.
   - Among descending neurons, 55 of 100 active ones differ between left-only and
     right-only DM1, but not as mirror pairs.
   - Right-only DA2 reaches no descending neurons.
5. **Left/right, published model** (3 seeds x 30 trials, 150 Hz). These used 300 ms
   trials, because the runaway settles within 50 ms.
   - **DM1:** left-only and right-only give the same output. Only 2 of 169 active
     descending neurons differ consistently, by 3 Hz or less. The left DNa02 is at
     about 50 Hz for either side; the right one stays silent.
   - **DA2:** the right side ignites later and only in 20-24 of 30 trials, so its
     responses are weaker. The left DNa02 still wins either way.
   - DNg100 is under 1 Hz and DNp09 is at 0 in both versions.
   - **Conclusion:** the Phase 9 open risk is confirmed. Neither version gives
     mirror-image steering commands.

**Validated?**
- Every olfaction result is **PRELIMINARY**.
- The runaway and the fixed-side steering bias are **surprising**, and Phase 6 steps
  1-5 were done:
  - 1: seeds and w_syn +/-20%;
  - 2: independent simulator, IDs and signs;
  - 3: quick literature check;
  - 4: both contradict known biology, so we suspect the model;
  - 5: this write-up.
- The GABAergic identity of lLN1 / lLN2T is background knowledge, not re-read in this
  pass.
- The "lnfix" variant is not part of the project's model. Adopting it would be a
  Phase 7-style upgrade, and that is the owner's call. Nobody has been contacted.

**Plain English.** In the published model, a whiff of any strong smell sets the whole smell
system on fire. That traces back to 53 inhibitory cells mislabelled as excitatory. With
those fixed, smell responses look like a real fly's. But left and right smells still steer
the same way, because of a lopsided wiring pattern. Phase 9 cannot use a simple left-minus-
right steering rule without fixing or correcting this first.

## 2026-09-22: Phase 6, the "runaway activity" surprise (sugar 200 + Ir94e 200)

- **Question:** In Phase 3, 2 of 5 Brian2 trials of "sugar 200 Hz + Ir94e 200 Hz" switched the
  whole brain into non-stop firing (about 8,300 neurons, up to 364,000 spikes in 1 s). Real, bug,
  or artefact? PLAN.md Phase 6 steps 1-5.
- **Changed:** nothing in the model. All runs use the paper's model on the fast engine, snapshot
  630, from one long-lived process (`experiments/phase6/runaway/server.py`). Diagnostic "what-if"
  changes (silencing, sign flips, cutting some connections) were made in memory for single runs
  and undone afterwards; each was checked to be undone.
- **Runaway definition:** more than 1,500 different neurons firing in any 10 ms slice (healthy
  trials top out at 442, runaways never below 3,741). Agrees with the Phase 3 "5x median" rule on
  448 of 450 trials.
- **Ran and found:**
  - *Step 1, does it hold:* 150 trials each (30 x 5 seeds). sugar 200 + Ir94e 200: 6/150 (4%);
    sugar 200 alone: 0/150; Ir94e 200 alone: 20/150 (13%). It is a random tipping event (about
    4% per second): 3-second trials ran away 4/30 (13%), onsets spread from 0.8 to 2.3 s. Once
    started it never stops, even with all input switched off (9/9 still firing 1+ s later).
    Synapse strength +5%: 17/30 run away; +10%: 25/30 (Ir94e alone 28/30); sugar alone still 0.
    Grid of sugar 0-300 x Ir94e 0-300 Hz (20 trials each): only Ir94e >= 200 Hz triggers it
    (about 1 in 10 at 200 Hz, 1 in 3 at 300 Hz, whatever the sugar rate); sugar + bitter and
    sugar + water at 200 Hz: 0/20 each.
  - *Step 2, bug checks:* the Phase 3 Brian2 inputs replayed in the fast engine give
    spike-for-spike identical trials, runaways included (same onset, 778 and 237 ms). 2/5 vs 6/150
    is an unlucky draw (1.5% chance; Fisher p = 0.02). IDs, signs (100% equal to the reference
    file) and indexing verified. Note: FlyWire's later annotation types the paper's 18 "Ir94e"
    neurons as LB1e (11) and LB2a-c (7).
  - *Step 3, where and why:* every runaway starts in the antennal lobe (smell centre), not in the
    taste pathway, 10-20 ms before the explosion, in excitatory local neurons (lLN2T_c, v2LN30,
    lLN1_b/c) and projection neurons. Same state as the Phase 5 olfaction "ignition" (overlap
    0.90). Silencing the 38 eLNs (lLN1_b/c + lLN2T_a-c), or only the 8 lLN2T, drops Ir94e runaway
    from 9/60 to 0/60 and stops the smell trigger; 3 random size-matched control lesions change
    nothing (9, 9, 9 of 60). The self-sustaining engine is antennal-lobe excitatory local neurons
    plus projection neurons (silencing either stops even forced ignition); Kenyon cells and
    lateral horn are passengers. Coordinator's request: flipping the olfaction lane's 53
    "serotonin/dopamine" AL local neurons to inhibitory removes the taste runaway too (0/150 and
    0/60), MN9 unchanged; the 28 of them of types lLN1_b/c and lLN2T are the ones that matter.
  - *Step 4, literature:* no report of runaway in the Shiu paper, its repo issues, or Eon Systems'
    port. Real flies do not show this; seizure-like activity needs mutants, shocks or GABA block.
    Real eLNs excite projection neurons through gap junctions (Yaksi & Wilson 2010).
- **Verdict:** a real property of the published model (not a bug in our code), caused by missing
  or mislabelled biology in about 28-38 antennal-lobe local neurons; not a finding about flies.
  Two fixes both remove it and keep sugar -> MN9 exactly (67.63 spikes/s): make them inhibitory
  (if the olfaction lane is right that they are GABAergic) or keep their chemical output only
  onto inhibitory neurons (if FlyWire's "cholinergic" annotation is right; real eLNs use gap
  junctions onto projection neurons). Missing spike-frequency adaptation is a likely reason the
  state never ends (untested).
- **Validated:** Yes for "not a bug" (two engines identical) and for the mechanism (lesion tests
  with random controls). NOT validated: which of the two fixes matches biology (needs the real
  transmitter of lLN1_b/c and lLN2T); adaptation as a cure; snapshot 783.
- **For Phase 7:** add to its checkpoint "10 DM1 smell neurons firing once must not ignite the
  brain, and Ir94e 200 Hz must not run away". Any Phase 5 olfaction result that drives the smell
  system is suspect until then.
- **Explained in plain English:** `docs/phase6-runaway-activity.md`. Numbers:
  `experiments/phase6/runaway/results/summary_stats.txt`.

# EXPERIMENTS.md entries: Phase 7 upgrades 1-3

(Written by the Phase 7 lane for the main session to paste into EXPERIMENTS.md.
All numbers: snapshot 630, whole brain, `experiments/phase7/results/summary.md`.
Every entry is PRELIMINARY in the PLAN.md Phase 6 sense: 3 seeds and parameter
variants were run, but there has been no independent review.)

How every upgrade was checked: the Phase 3 conditions (sugar 100 and 200 Hz,
water 200 Hz, bitter 200 Hz, sugar 100 + bitter 120 Hz, and sugar 200 + Ir94e
200 Hz for runaway activity) were each run with 3 random seeds x 30 trials x
1 s (the runaway condition with 5 seeds = 150 trials), with the upgrade ON,
and compared with the unchanged baseline engine run on the same seeds. A
check "holds" only if it passes for every seed. "Noise floor" = how much the
baseline differs from itself when run with 3 new seeds.

## 2026-09-22 - Phase 7 upgrade 1: distance-dependent synaptic delays (PRELIMINARY)

**Source.** Synaptic part 1.8 ms: Paul et al. 2015, Front Cell Neurosci 9:29
(measured from the spike at the nerve terminal, so no travel time is in it).
Conduction speed 0.2 m/s: Kottmeier et al. 2020, Nat Commun 11:4491 (larval
axons 0.196 m/s motor, 0.129 m/s sensory); fast bound 2.07 m/s: Kadas et al.
2019, eNeuro (adult giant fiber). Positions: FlyWire anchor points (Schlegel
et al. 2024); there are no synapse positions for snapshot 630.

**What changed.** Each connection's delay = 1.8 ms + straight-line distance
between the two neurons' anchor points / 0.2 m/s (median 2.3 ms, longest
4.9 ms; baseline: all 1.8 ms). Switch `delays` in `sim/realism.py`.

**What happened to the baseline results.** All Phase 3 checks hold on all 3
seeds. MN9 (opposite side): sugar 100 Hz 67.3 -> 71.1 Hz (+6%, consistent
across seeds), sugar 200 Hz 93.5 -> 93.3, water 30.8 -> 31.0, bitter 0 -> 0,
sugar + bitter 1.4 -> 1.4, sugar 200 + Ir94e 200 63.6 -> 64.2. Neuron by
neuron: correlation 0.9988-1.0000 (noise floor 0.9999-1.0000), 49-50 of the
top 50 the same. Runaway in sugar 200 + Ir94e 200: 6/150 vs 5/150 (p = 1.0),
no change. Variants (0.129 m/s, 2.07 m/s, cell-body distances; 1 seed each)
agree.

**Plain English.** Signals now take longer to arrive the farther they travel,
half a millisecond extra on average. The brain's responses barely change, so
the paper's feeding result does not depend on the "every signal takes 1.8 ms"
shortcut.

## 2026-09-22 - Phase 7 upgrade 2: conductance-based synapses (PRELIMINARY, FAILS checks)

**Source.** Acetylcholine (nicotinic) reversal ~0 mV: Lee & O'Dowd 1999,
J Neurosci 19:5311; Su & O'Dowd 2003, J Neurosci 23:9246 (+8.9 mV). Chloride
(GABA-Rdl, GluCl) reversal -50 to -60 mV: Rohrbough & Broadie 2002,
J Neurophysiol 88:847; -45 to -50 mV McCarthy et al. 2011, J Neurosci
31:8181; -37 mV Su & O'Dowd 2003. All whole-cell recordings, so the in-vivo
value is uncertain. Used 0 and -60 mV; -70 mV as a variant.

**What changed.** A synapse's push now depends on the voltage's distance from
the channel's reversal potential. Weights rescaled explicitly so one synapse
moves a neuron at rest exactly as in the baseline: excitatory conductance
0.275/52 = 0.00529, inhibitory 0.275/8 = 0.0344 (in units of the leak
conductance). Switch `conductance`.

**What happened to the baseline results.** Three checks fail on all seeds:
sugar 100 Hz -> MN9 6.8 Hz (needs >= 20), water -> 0 Hz, sugar 200 + Ir94e
200 -> 0 Hz (abolished). Diagnosis: conductance-based excitation alone gives
53 Hz, inhibition alone 25 Hz, both 7 Hz (inhibitory shunting is the larger
cause). -70 mV: sugar 100 Hz 26 Hz but water still 0.1 Hz. Re-fitting the one
global synapse multiplier (as Shiu et al. did) peaks at 54 Hz at 2x and never
reaches the paper's 65.7 Hz. At 2x all seven MN9 checks pass (sugar 100 Hz
52.6 Hz, water 20.6, bitter 0, sugar + bitter 4.4, Ir94e 13.7), but the brain
becomes unstable: it runs away with water (19/90), bitter (4/90) and sugar
alone (2/90 each), never seen in the baseline, and resembles the baseline
less (correlation 0.64-0.95). Runaway: drop-in 0/150 (p = 0.06) is MASKING
(the whole network is weakened; a single forced kick to the eLNs still
ignites it); at 2x, 5/90 in sugar + Ir94e, and silencing the 38 antennal-lobe
eLNs removes most of the new runaways (water 7 -> 2, bitter 2 -> 0 of 30), so
the retune makes the existing eLN loop easier to trigger and adds at least
one other route. Neither is a fix of the sign problem.

**Plain English.** Making synapses behave like real ion channels is more
realistic, but with the baseline's synapse strengths it starves the feeding
pathway, and turning all strengths up to compensate makes the network
unstable. It needs a proper re-fit (separate excitatory and inhibitory
strengths, better chloride data), which was not done. Not stacked with the
other upgrades.

## 2026-09-22 - Phase 7 upgrade 3: spike-frequency adaptation (PRELIMINARY)

**Source.** Strength: Zhao & Wu 1997, J Neurosci 17:2187 (cultured Drosophila
central neurons, 600 ms steps at 2-3x threshold; "adaptive" = last rate below
0.7x the first). Time constant 100 ms: SK-channel pauses in Drosophila sensory
neurons, median 104 ms (Onodera et al. 2017, eLife 6:e29754); dSK in fly
neurons: Abou Tayoun et al. 2011, J Neurosci 31:13897. No direct measurement
for adult central brain neurons was found.

**What changed.** Every spike adds a brake current that fades with a 100 ms
time constant; 0.974 mV per spike, calibrated so one model neuron on the
Zhao & Wu protocol slows to exactly 0.7x. Same for every neuron. Switch
`adaptation`.

**What happened to the baseline results.** All Phase 3 checks hold on all 3
seeds, alone and together with upgrade 1. MN9 about a third lower: sugar
100 Hz 67.3 -> 43.9, sugar 200 Hz 93.5 -> 67.0, water 30.8 -> 11.0, bitter
0 -> 0, sugar + bitter 1.4 -> 3.2 (7% of sugar alone; check allows 10%),
sugar 200 + Ir94e 200 63.6 -> 32.0. Neuron by neuron: correlation
0.947-0.991, 38-47 of the top 50. Runaway: 0/150 vs 5/150 (p = 0.06).
Half strength and a 300 ms time constant also give 0/150 each (pooled
0/450 vs 5/150, p = 0.001). But a single forced kick to 10 DM1 smell neurons
or to the 38 antennal-lobe eLNs still ignites the whole brain with every
adaptation setting (about 30% fewer spikes), so the Phase 6 eLN loop is still
there: adaptation MASKS the sign/wiring problem, it does not fix it. Variants (half strength; 300 ms) pass the same checks, with a
smaller drop.

**Plain English.** Letting neurons tire during a long input, as many real fly
neurons do, keeps every yes/no behaviour of the paper but lowers all the
firing rates by about a third, so the paper's exact numbers depend on the
model having no adaptation.

## 2026-09-22/23 - Phase 7 upgrade 5: neurotransmitter sign audit and switchable sign fixes (PRELIMINARY)

**Question.** Phase 6 traced the runaway (the whole brain locking into non-stop firing) to
the antennal lobe's excitatory local neurons, "eLNs" (types lLN1_b/c and lLN2T). Earlier
lanes disagreed: one said they are really inhibitory (GABA), another said they are
excitatory (acetylcholine) but reach projection neurons mainly through electrical contacts,
which the model lacks. Which is right, and does fixing it remove the runaway without
breaking the paper's results?

**Sources.** Full text: Shang et al. 2007 (Cell 128:601), Yaksi & Wilson 2010 (Neuron
67:1034), Chou et al. 2010 (Nat Neurosci 13:439), Tobin et al. 2017 (eLife 6:e24838),
Schlegel et al. 2021 (eLife 10:e66018), Eckstein et al. 2024 (Cell 187:2574). Abstract only:
Huang et al. 2010 (Neuron 67:1021); the publisher blocked the full text. FlyWire v783
`known_nt` / `known_nt_source` columns, mapped to snapshot 630 by supervoxel (127,218 of
127,400 neurons matched).

**Findings from the papers.** The eLNs are cholinergic, i.e. excitatory: Shang et al. 2007
("a previously unidentified population of cholinergic local neurons"), Yaksi & Wilson 2010
(ChAT-positive, GABA-negative), FlyWire's literature entry for exactly 44 neurons, and
Eckstein et al. 2024 (their serotonin/dopamine guesses for these cells are probably wrong).
No source read supports "GABAergic". How they reach projection neurons is disputed: Yaksi &
Wilson 2010 found "mainly or purely electrical", with chemical synapses onto inhibitory
local neurons; Huang et al. 2010 (abstract) found chemical plus electrical.

**What changed.** New `sim/sign_fixes.py` builds the brain with a named fix, in memory only.
The engine and data files are unchanged. The fixes:
- `none`: the paper's model, identical spike for spike (tested).
- `eln_electrical`: the 44 eLNs' chemical synapses onto non-inhibitory neurons are removed
  (18,248 connections).
- `al_ln_literature` (recommended): 13 antennal-lobe local neurons with a literature
  GABA/glutamate entry become inhibitory, and all 137 remaining excitatory local neurons
  follow the eLN rule. This removes 51,539 connections and flips 10,455.
- `known_nt`: 1,334 neurons whose literature transmitter contradicts their model sign are
  flipped.
- `ln53_inhibitory`: Phase 5's fix, which makes the 53 serotonin/dopamine-guessed local
  neurons inhibitory.

Tests: `tests/test_sign_fixes.py`.

**What happened (3 seeds x 30 one-second trials per check).**
- **Taste results:** every Phase 3 taste result is unchanged under every fix. For
  `al_ln_literature` the spikes are identical, checked directly on 10 trials per
  condition. Sugar 100 Hz gives MN9 67.28 Hz.
- **Ir94e 200 Hz runaway:** 10 of 90 trials at baseline, 0 of 90 under every fix
  (p = 0.0015).
- **DM1 smell 150 Hz runaway:** 90 of 90 at baseline. Under `al_ln_literature` and
  `ln53_inhibitory` it was 0 of 90, but 90 of 90 under `eln_electrical` and under
  `known_nt`. So the 44 alone are not enough: the other ~100 excitatory local neurons keep
  the loop going.
- **Kenyon cells (DM1):** 64% at baseline, 3.6% under `al_ln_literature`. Real flies are
  roughly 5-10% (background, not re-read).
- **One-spike triggers** (10 smell neurons, the 44 eLNs, all 685 projection neurons): all
  three ignite at baseline and none under `al_ln_literature`.
- **Synapse strength 90%, 110% and 120%:** no runaway under `al_ln_literature`. The paper's
  model runs away in 28 of 30 trials at 110%.
- **Steering:** left-only and right-only smell both still give a "turn left" signal
  (+5.7 and +4.8 Hz), so Phase 5's finding stands. The right DNa02 now responds a little
  to a right odour (2.5 vs 0.9 Hz).

Wider audit: 1,334 literature disagreements, mostly visual system, none active in the taste
experiments. The monoamine-as-fast-excitation and histamine assumptions are listed, not
changed.

**Validated?** No: PRELIMINARY. Seeds and synapse strength were varied, and the bug checks
and literature were done. Not done: independent review; the Huang 2010 full text; the
papers FlyWire cites for the 13 cells; snapshot 783; Brian2. Extending the eLN measurement
to all 137 excitatory local neurons is an inference. The engine has no electrical synapses,
so the fix leaves the model with no lateral excitation at all. Details:
`docs/phase7-neurotransmitter-audit.md`.

**Plain English.** The cells blamed for the runaway really are excitatory. The papers
suggest they excite their neighbours mostly through direct electrical contacts rather than
ordinary synapses. The model cannot do electrical contacts, so the fix switches off their
ordinary excitatory synapses onto everything except inhibitory neurons. The same rule is
applied to the other excitatory local neurons in the smell centre. With that, the whole
brain stops locking up, the paper's taste results do not change at all, and the smell
centre recruits a realistic small fraction of the learning centre. The left/right smell
steering is still wrong.

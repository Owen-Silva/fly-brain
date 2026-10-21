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
those fixed, smell responses come closer to real-fly recordings (preliminary). But left and right smells still steer
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

## 2026-09-23 - Phase 7 upgrade 4: cell-type-specific neuron settings (PRELIMINARY)

**Sources (all read in full text; page/figure per number in
`experiments/phase7_celltype/celltype_params.csv`).** Kenyon cells: Turner, Bazhenov &
Laurent 2008, J Neurophysiol 99:734 (threshold 21.5 +/- 5.6 mV above rest, 17 cells,
p. 741 / Fig. 3G; holding potential -57.8 mV; the authors' one-compartment time constant
1.0 uF/cm2 / 0.089 mS/cm2 = 11.2 ms, tuned to the measured 11.5 ms synaptic potential,
p. 737). Projection neurons: Gouwens & Wilson 2009, J Neurosci 29:6239 (Table 1:
resistance x capacitance of 3 DM1 cells = 22.9 ms; seal-corrected rest -57.8 mV, Fig. 7);
Jeanne & Wilson 2015, Neuron 88:1014 (about 10 mV from average voltage to threshold, 18
DA1 cells, Fig. 4C). P-EN neurons: Turner-Evans et al. 2017, eLife 6:e23496
(Supplementary file 1: mean gap 12.0 mV over 8 recordings, rest -46.1 mV). Large LNv
clock neurons: Sheeba et al. 2008, J Neurophysiol 99:976 (305 MOhm x 12 pF = 3.66 ms;
rest -49 mV; explant, 24 C). Input resistances found but not used (the model has no
current; Kazama & Wilson 2008, Neuron 58:401, Fig. 4: projection-neuron synapses are
matched to each cell's resistance). Nothing found for MN9, taste interneurons or
mushroom-body output neurons; von Reyn et al. 2014 (giant fiber) and visual-neuron
papers NOT read (UNVERIFIED, not used).

**What changed.** 5,477 neurons (4.3%) get their measured values: 5,177 Kenyon cells
(gap 21.5 mV, time constant 11.2 ms), 251 cholinergic single-glomerulus projection neurons
(gap 10 mV, 22.9 ms), 42 P-ENs (gap 12 mV), 7 large LNvs (3.66 ms). Threshold is always
set as a gap above the cell's own rest (in this model only the gap matters). Everything
else keeps the shared values; refractory period 2.2 ms for all (none measured).
`sim/celltype_params.py`, `CellTypeBrain`; the baseline engine was not edited, and with no
measured values the new engine gives the baseline's spikes exactly (tests, incl. whole
brain).

**What happened to the baseline results.** All Phase 3 checks hold on all 3 seeds, and
the five taste checks are spike-for-spike identical to the baseline for every neuron
(correlation 1.000, top 50 identical): none of the 5,477 changed neurons fires in those
experiments in either model, so the sugar result is untouched (MN9: sugar 100 Hz 67.3,
sugar 200 Hz 93.5, water 30.8, bitter 0, sugar + bitter 1.4, sugar 200 + Ir94e 200 63.6
Hz, all unchanged). Runaway (Phase 6 definition, 150 trials each): 6 vs 6 (sugar 200 +
Ir94e 200) and 19 vs 19 (Ir94e alone), p = 1; the loop runs through antennal-lobe local
neurons, which have no usable measurement. The real change is in the mushroom body:
driving the DM1 smell neurons (150 Hz, 3 seeds x 30 trials), 4.1% of Kenyon cells fire per
trial instead of 64.2% (real flies: 6 +/- 5%, Turner 2008), and mushroom-body output
neurons drop from 70 active at about 100 Hz to 25 at about 25 Hz. The antennal lobe still
ignites in every smell trial (the Phase 5/6 problem is not fixed by this upgrade).
Which group does it: Kenyon cells alone 64% -> 9.0%, projection neurons alone 64% -> 53%
(both: 4.1%); P-ENs and clock neurons never fired in any condition tested. The two
judgement calls (projection-neuron gap 17.8 mV from two papers combined instead of the
directly measured 10 mV; Kenyon cell time constant 200 ms from the cell body instead of
11.2 ms) give 1.4% and 3.1%, and no version changes the runaway rate (all 6/150 and
19/150, p = 1). Noise floor (baseline with 3 new seeds): correlation 0.99991-0.99998,
6-29 neurons active in only one run; the upgrade in the taste checks: 1.000, 0 neurons.

**Validated?** Phase 3 checks: yes (3 seeds, identical). Runaway: 150 trials x 2
conditions. Variants of both judgement calls run. Not validated beyond that: coverage is
small and off the taste pathway, one recorded type stands for its whole class, and the
Kenyon cell comparison is made inside the (unrealistic) runaway state. **PRELIMINARY.**

**Plain English.** Where scientists have measured a fly cell type with an electrode, the
model now uses their numbers instead of one shared setting. Only four cell types had
numbers that fit this simple model, and none of them sits on the sugar-to-feeding
pathway, so the paper's feeding result comes out exactly the same. The big effect is in
the learning centre: real Kenyon cells need a large push before they fire, and with that
measured value only about 4% of them respond to a smell, as in real flies, instead of
two-thirds. Details: `docs/phase7-celltype-params.md`.

# EXPERIMENTS.md entry: Phase 8, learning in the mushroom body

(Written by the Phase 8 lane for the main session to paste into EXPERIMENTS.md. Full
write-up: `docs/phase8-learning.md`. Numbers: `experiments/phase8/results/`.)

## 2026-09-22/23 - Phase 8: dopamine-gated learning in the mushroom body (PRELIMINARY)

**Sources.** Learning rule, timing and the calibration target: Hige et al. 2015, Neuron
88:985 (one 1-s odor paired with PPL1-γ1pedc stimulation: MBON-γ1pedc>α/β synaptic current
-90%, spikes -80%; unpaired odor -25% spikes; backward pairing no change; α2 compartment
needs 1 min of pairing). Timing window: Handler et al. 2019, Cell 178:60. Separate
compartments: Cohn et al. 2015, Cell 163:1742. Which DAN teaches what: Aso & Rubin 2016,
eLife 5:e16135. Approach/avoid MBONs: Aso et al. 2014, eLife 3:e04580. Compartment of each
MBON/DAN type: hemibrain instance names (research doc 2.4).

**What changed.** New file `sim/plasticity.py` (the baseline engine is untouched). Every
Kenyon cell (KC) keeps an "active recently" tag (+1 per spike, time constant 1 s); every
compartment keeps a dopamine level (+1 per DAN spike per DAN cell, time constant 0.2 s,
chosen). Each time step, every KC -> MBON connection shrinks by exp(-eta x tag x dopamine x dt),
only in its own compartment and brain half. Only the 62,177 KC -> MBON connections can
change. eta calibrated once (seeds 900-904) to Hige's -90% current; α2/α3 learn 95x slower
(calibrated to Hige's α2 result). Decision on DAN outputs: by default their fast excitatory
synapses (the published model's +1 sign) are switched off for the 305 DANs with a known
compartment, so dopamine acts only through learning; the published treatment was run too.
Model: the mushroom-body circuit (all PNs, KCs, MBONs, DANs, APL, DPM; 570,433 connections,
copied unchanged from snapshot 630), odors = 2 non-overlapping sets of 4 glomeruli given to
their projection neurons (5.4% and 4.3% of KCs respond). Whole-brain runs as well (below).

**What happened (MB circuit, 5 seeds, change after vs before, net of a no-training run
with the same seeds).**
- Paired (odor A + PPL1-γ1pedc): MBON-γ1pedc>α/β input from A -91% (sd 6), from B -9%
  (sd 2); 5 of 5 seeds. Odors swapped: -89% vs -6%.
- Unpaired +0.2%, odor only +0.2%, DAN only 0.0%.
- Backward (DAN 0.5 s before odor): -9% (Hige: none). With a dopamine time constant of
  0.1 s instead of 0.2 s: -0.5%; with 0.5 s: -59% (eta re-calibrated each time). So Hige's
  backward result pins the dopamine signal to about 0.1 s in this rule.
- Reward: PAM-γ5 + PAM-β'2a paired with A: "avoid" MBON-γ5β'2a input from A -78%, from B
  -8%; PAM-α1: MBON-α1 -94% vs -12%. Approach-minus-avoidance input for the trained odor
  moves toward avoidance after punishment (-0.83) and toward approach after reward (+0.10).
- α2: 1-s pairing -10%, 60-s pairing -94% (partly built in by the calibration).
- Each DAN changed only its own compartment's MBONs. Published fast-DAN treatment: every
  number within 1 percentage point.
- Whole brain, recommended sign fix `al_ln_literature` (3 seeds, all 7 conditions): smell
  input sparse (4.9% / 4.2% of KCs). REWARD works: PAM-γ5 + PAM-β'2a paired with A,
  MBON-γ5β'2a input from A -98.5%, from B -4% (net of no training -97.5% vs -4.6%; 3 of 3
  seeds). PUNISHMENT cannot be seen: a sniff alone makes PPL1-γ1pedc fire about 16 spikes
  (the artificial punishment gives about 11; in the circuit a sniff gives 0), so every test
  sniff is itself a punishment trial; MBON-γ1pedc>α/β input from A goes 6,555 -> 46 from the
  first to the second sniff without any training, and all 7 conditions end at -100% for
  both odors. Trace of that drive (`trace_ppl1.py`): inside the circuit KC excitation and
  inhibition cancel (net about 0); the net push (about 4,000 synapse-weighted spikes per
  sniff) comes from outside, largest SMP384 (predicted transmitter dopamine, confidence
  0.63-0.65, counted excitatory by the published model), SMP504, CRE069. Lead only, not
  tested.
- No fix (published brain; paired and no-training only): smell runs away (62% of KCs,
  about 540,000 spikes and 490 PPL1-γ1pedc spikes per sniff); both conditions -100% (A) /
  about -97% (B); nothing can be read.
- `eln_electrical` (recommended on 2026-09-22, since superseded; 5 conditions): runaway
  (22% / 19% of KCs, about 180 PPL1-γ1pedc spikes per sniff); everything -100%, reward not
  odor-specific (-100% vs -93%). LN-fix `ln53_inhibitory` (comparison only; the audit found
  it wrong for 34 cells): like the recommended fix, punishment hidden, reward -98% vs -6%.
- Phase 3 check: learning on, no training, published, `al_ln_literature` and
  `eln_electrical` brains, sugar 100 and 200 Hz, 3 seeds x 10 trials each: MN9 identical
  spike for spike in all trials (68.3 and 93.3 Hz), no connection changed at all.

**Validated?** PRELIMINARY. 20 automated tests pass (`20 passed`, slow tests included) (learning off = baseline engine exactly;
only the right synapses change; one change matches the formula within 1%). Several seeds,
both odor assignments, both DAN treatments and a dopamine time-constant sweep were run; no
independent review. Chosen/unmeasured: dopamine time constant, spikes per light pulse,
compartment placement by lobe (not by real synapse position), MBON28's compartment.

**Plain English.** The simulated fly can now learn. Pair a smell with a "that hurt"
dopamine signal and the output neuron that says "go towards this" stops listening to that
smell (about 90% less input), just as in real flies, while its response to another smell
barely moves. Without pairing, nothing changes. Reward works the same way in the reward
compartments. This works in the mushroom-body circuit on its own. In the whole brain, with the recommended sign fix, reward learning works the same way.
Punishment learning cannot be tested there yet: in the whole brain the smell by itself
switches on the punishment neurons, so after a single sniff the fly "learns" that every
smell is bad. That signal comes from neurons outside the mushroom body. The biggest one
probably releases dopamine (a computer prediction, about 64% confident), but the model
treats it as a plain excitatory neuron; that is the next thing to check.

## 2026-09-23 — Phase 9, first steps: the closed brain-body loop (odor taxis)

**What was built**

- A separate environment, `.venv-body`: the same pinned packages as `.venv`, plus
  FlyGym 2.1.0 and its dependencies (`requirements-body.txt`). FlyGym's walking runs here.
  - `.venv-body/` is in `.gitignore` (added by another lane).
- Smell, added back to FlyGym 2.x with the published FlyGym 1.x rule: strength =
  peak × distance⁻² at 2 antennae + 2 palps (`sim/body/odor.py`). Source: the
  flygym-gymnasium 1.3.2 code, NeuroMechFly v2 (Wang-Chen et al. 2024).
- The closed loop (`sim/body/`), in 50 ms windows:
  1. antenna odor → firing rate of the left and right DM1 smell neurons;
  2. the whole brain runs for 50 ms, keeping its state between windows;
  3. the left and right DNa02/DNa01 spikes → a turn command → FlyGym's [left, right]
     drive;
  4. FlyGym's walking controller moves the body.
  - `FastBrain` cannot carry its state across windows. The workaround is a copy of its
    inner loop that keeps the state (`brain_stepper.py`). It is proven spike-for-spike
    identical to one uninterrupted FastBrain run, on small networks (tests) and once on
    the full brain (300 ms, 129,098 spikes).
- **Not brain-driven, and labelled so:** walking speed (fixed), all leg movement (FlyGym's
  controller), and the hand-written comparison rule.
- Controls:
  - (a) the read-out DNs silenced;
  - (b) FlyGym 1.x's hand-written taxis rule (NOT brain-driven);
  - (c) no odor.
- The DN → drive read-out is one swappable object (`DriveMapping`).
- Tests: `tests/test_body_loop.py`, 22 tests.

**What happened** (4 start layouts per condition, odor 15 mm away at ±45°/±90°, 3 s
each; `docs/phase9-body-loop.md`):

- **Recommended sign fix (`al_ln_literature`):** no read-out neuron fired a single
  spike in any window. The brain-driven fly walked straight, on exactly the same path
  as the silenced fly. It reached the odor 0 of 4 times, and 0 of 4 again with other
  brain seeds.
- **Same brain, with smell neurons 10× more sensitive:** the steering neurons fired, but
  almost only the LEFT DNa02. The fly turned left for odor on either side and reached the
  odor only when it was on its left (1 of 4).
- **Published model and the `eln_electrical` fix:** the smell system runs away. The fly
  spins in left circles (about 440° in 3 s) and reached the odor 0 of 4 times.
  - These flies *end* closer to the odor than the silenced fly only because they circle
    near the start. Their closest approach is the same.
- **Hand-written rule, same body (NOT brain-driven):** reached the odor 4 of 4 times, in
  1.6-1.9 s.
- **Silenced DNs and no odor:** walked straight, 0 of 4.
- **Answer:** the brain-driven fly does NOT approach the odor better than chance or
  better than the silenced fly. This matches the Phase 5 wiring finding: left-only and
  right-only DM1 smell both drive the LEFT DNa02. The PLAN.md Phase 9 checkpoint is
  **not passed**.

**Follow-up:** `docs/phase6-steering.md` appeared after the runs finished. It found no
DM1 steering read-out among all 463 left/right DN pairs. Following its recommendation, any
DM1 odor-taxis demo uses the hand-written rule, labelled "turning NOT brain-driven". Its
optional DA1 + DNpe002 route was not run. The loop supports it through two config
entries: `orn_type` and `drive_mapping`.

**Validated?** No. PRELIMINARY:

- n = 4 layouts per condition, one brain seed each (two for the recommended fix);
- no Phase 6 seed/parameter sweep;
- ORN/DN side labels not independently checked;
- the sensor → rate curve is a modelling choice.

## 2026-09-23 - Phase 6: the one-sided steering result ("either smell side says turn left") (PRELIMINARY)

**What was changed.** Nothing in the model. A Phase 6 investigation of the Phase 5/7/9
finding that left-only and right-only DM1 smell both make the LEFT DNa02 fire more.
(1) Side-label checks for ORNs, PNs, DNa02 and DNa01 from cell body positions, FlyWire
anchor points, 783 synapse locations (which antennal lobe / LAL the synapses sit in) and a
per-ORN wiring fingerprint, in snapshots 630 and 783. (2) Same-side vs other-side ORN -> PN
synapse counts for every glomerulus. (3) Simulations: DM1, DA1, DM4, DM2, VA2 and DA2 ORNs,
left-only vs right-only at 150 Hz, 3 seeds x 30 trials, with the validated
`al_ln_literature` fix (1 s trials) and the published model (300 ms trials), every
descending neuron recorded; 463 left/right DN pair types scanned for a turn signal that
flips with the smell's side. Checks on the one channel that worked (DA1): synapse strength
90/110%, 75 Hz input, il3LN6 silenced, and both-antennae gradients (150/150, 150/100,
100/150 Hz, also for DM1). An exploratory variant (not a model change) multiplied same-side
ORN -> PN connections by 1.4 (Gaudry et al. 2013). (4) Literature: Gaudry 2013, Tobin 2017,
Schlegel 2021, Taisz 2023, Rayshubskiy 2025 read in this pass.

**What happened.**
- No bug. PN cell bodies 684 of 685 on their labelled side; 672 of 683 PNs collect their
  smell input in the labelled side's antennal lobe (783); DNa02/DNa01 cell bodies and
  inputs (own-side LAL) all match. ORNs connect 1.51x more to same-side PNs and 1.62x more
  to other-side local neurons, both as in the literature; swapped ORN labels would reverse
  this. 630 and 783 give the same counts.
- Real wiring asymmetry. The left DM1 PN gets more ORN synapses from BOTH antennae (left
  ORNs 2,062 vs 1,175; right ORNs 1,662 vs 1,275): 52% more in total. Each PN still gets
  more from its own side. Across the lobe, only 32 of 51 glomeruli (783: 33 of 53) "mirror"
  at the first synapse; the 19 that do not have large left/right size differences (median
  20% vs 5%), 15 of them left-heavy. DM1, DM2, VA2 and DA2 fail; DM4 passes by 1 synapse;
  DA1 passes. With same-side synapses counted 1.4x, 42 of 51 would mirror.
- Simulations with the fix: DNa02 turn (left minus right) +5.7 / +4.8 Hz for DM1 left /
  right smell (d' 0.2), +16.1 / +16.3 for DM4; DM2 right, VA2 and DA2 reach no steering
  neuron. No DN pair flips for any of these. **DA1 mirrors**: DNa02 22.7/1.0 Hz for a left
  smell and 0.1/15.7 Hz for a right smell (all seeds), plus 15 other DN pairs (best:
  DNpe002, +45.9 / -46.3 Hz); robust to w_syn +/-10%, 75 Hz and il3LN6 silencing.
  Published model: every glomerulus runs away and DNa02 says "turn left" (+47 to +53 Hz)
  for every smell from every side, DA1 included.
- Gradients (both antennae smell): DNa02 has a fixed left offset for DA1 (+17.9 Hz at
  150/150) and turns the wrong way for 100/150 (+4.7 Hz). DNpe002 turns the right way in
  100% of 1 s trials for both 150/100 (+16.8 Hz) and 100/150 (-6.1 Hz). DM1: every read-out
  says left for every gradient.
- Exploratory same-side release x1.4: DM1 PNs now mirror (1.39x / 1.07x same-side), but DM1
  DNa02 still does not (+35.0 / +1.5 Hz).
- Why DNa02 is stuck: for DM1 the right DNa02 gets 1.3-1.8x more inhibition than excitation
  either way (left AOTU019, right LAL051); for DA1 a short same-side route via DNae007
  drives each DNa02.

**Validated?** Phase 6 steps 1-4 done (3 seeds x 30 trials, parameter variation for DA1,
bug checks in two snapshots, literature read). Not verified: whether DM1's left excess is
biology or reconstruction; ORN sides checked only indirectly; DNpe002's real function and
its accuracy in 50 ms windows; our DA1 synapse counts are lower than Taisz 2023's (filter
difference assumed). Nothing shared. **PRELIMINARY.** Verdict: real connectome property
plus model limitation, not a bug. Details and Phase 9 recommendation:
`docs/phase6-steering.md`; files in `experiments/phase6/steering/`.

**Plain English.** In this brain, the left vinegar glomerulus is simply bigger than the
right one, so whichever antenna smells vinegar, the left side of the brain hears it
louder. Real flies correct for this: each smell neuron releases more signal on its own
side, and the model cannot know that from a wiring diagram. The steering neurons then
work like a see-saw that is already tipped left, so the model always says "turn left".
One smell channel, the one for the pheromone cVA, does steer the right way when only one
antenna smells it. For the body simulation this means: turning toward vinegar must be
labelled as not coming from the brain; a brain-driven turn is only available for cVA.

## 2026-09-23 - Explorer app: model choices and per-group input rates

**What changed.** The explorer app (`.venv\Scripts\python.exe -m app`) can now run the
improved model versions, not just the published one:

- A **Model** box on the page: *Published model (Shiu et al. 2024)* (the default,
  unchanged) or the *Recommended neurotransmitter fix*, plus optional upgrades
  *distance-based delays*, *adaptation* and *measured cell-type settings*. Each has a
  one-line description and a link to its write-up. Only checked versions are offered;
  combinations that were never tested (an upgrade plus the fix, cell-type settings plus
  anything) are switched off, with the reason shown next to them.
- Each model's brain is built the first time it is used (2 to 5 seconds here) and kept;
  at most two are kept in memory, and the page says which one will be dropped. If a
  model cannot be built, the run fails with the reason, the banner says so, and no other
  model is run in its place.
- **Stimulus groups**: the neurons to stimulate can be split into groups with their own
  input rates, for example sugar at 100 Hz and bitter at 40 Hz in one run.
- Saved setups and results now record the exact model: its name, switches and a
  fingerprint of each code file it uses. Loading a setup whose code has changed since
  says which file changed. Setups saved before this (like the sugar one) load as the
  published model with one input rate.
- Two new ready-made setups: *sugar 100 Hz + bitter 40 Hz* and *DA1 smell, left antenna
  only, on the recommended fix*.

**What happened (all through the app, seed 0, 30 one-second trials).**

| Check | Result |
| --- | --- |
| Phase 4 checkpoint re-run (sugar setup, app vs code) | SAME RESULT: MN9 67.63 Hz both ways, all 409 active neurons identical |
| Sugar 100 Hz + bitter 40 Hz (published model) | MN9 47.70 Hz, app = code for all 428 neurons; Phase 5 got 47.7 Hz, the paper 45.3 Hz |
| DA1 left smell (recommended fix) | left DNa02 22.9 Hz vs right 0.8 Hz ("turn left"); app = code, and all 216 active neurons equal the saved Phase 6 run |
| Every offered model, 3 short sugar trials | MN9 67.3 (published), 71.7 (delays), 42.7 (adaptation), 45.0 (both), 67.3 (cell-type): in line with the Phase 7 write-ups |

**Validated?** The app itself: yes. The same recipe gives identical numbers through the
app and from code, for the published model and for the fix, and the new setups
reproduce the earlier Phase 5 and Phase 6 numbers exactly. The model versions
themselves keep the status their own write-ups give them (the fix: recommended; the
upgrades: preliminary). Tests: `tests/test_app.py`, fast tests with the stand-in engine
plus three slow tests on the real engine.

**Not verified.** Combining an upgrade with the fix is not offered; reading
`sim/realism.py` suggests its builder for that combination would fail with delays on
(it looks for a neuron-position file named after the fix). Not run; left for the owner
of `sim/`.

## 2026-09-23 - Phase 7 upgrade 5, neuromodulators: dopamine and serotonin cells as slow signals, and whole-brain punishment learning (PRELIMINARY)

**Question.** The published model treats every cell that does not use GABA or glutamate as a
fast "push" (excitation), including dopamine and serotonin cells. In Phase 8 this blocked
punishment learning in the whole brain: a smell alone made the punishment neurons
PPL1-γ1pedc fire about 16 spikes per sniff, more than the artificial punishment, so every
smell was "punished". Is that fast push real, and does removing it (where the evidence says
so) unblock punishment learning?

**Sources.** Receptors: every known fly dopamine and serotonin receptor is a slow receptor
working through chemical messengers inside the cell (Blenau et al. 2017; Tierney 2018, via
search summaries); no dopamine- or serotonin-gated fast channel is reported in flies (Jones
et al. 2010, via search summary). Fast co-release: dopamine neurons also release GABA or
glutamate, both brakes (Yamazaki et al. 2023, J Neurosci 43:8294), and nitric oxide (Aso et
al. 2019, eLife 8:e49257); octopamine cells release glutamate (Sherer et al. 2020, PLoS Genet
16:e1008609); the serotonin cell CSD probably also releases acetylcholine (Zhang & Gaudry
2016, eLife 5:e16836). Serotonin input to PPL1-γ1pedc in real flies is slow (5-HT2A) and
matters only for long-term memory (Scheunemann et al. 2018, Neuron 98:350). Identities:
FlyWire literature transmitter column (`known_nt`, v783; for SMP384/SMP504 it cites Chiang et
al. 2011, a shape match to a single-cell image in a serotonin-neuron genetic line, not
antibody staining). Checks and learning protocol: Phase 3, Phase 6 and Phase 8 (Hige et al.
2015, Neuron 88:985). Full list and plain-English write-up: `docs/phase7-neuromodulators.md`.

**Identity check.** The biggest outside pushes onto PPL1-γ1pedc during a sniff come from
SMP384 (machine guess dopamine, confidence 0.63-0.65, but literature **serotonin**) and
SMP504 (guess acetylcholine 0.82-0.84, literature **serotonin**); SMP384's cell bodies lie
among antibody-confirmed serotonin cells. So the question is "serotonin cells giving a fast
push", not "dopamine cells". The known serotonin input to these neurons (the SPN, cell type
DNg30) has no synapses onto them in this connectome.

**What changed.** Three new, optional fix names in `sim/sign_fixes.py` (additive: every old
fix, number, test and the default `al_ln_literature` are unchanged). Each starts from
`al_ln_literature` and removes all outgoing connections of the chosen cells (their fast
push); nothing else changes and no sign is flipped:
- `al_ln_literature+da_modulatory`: dopamine cells, 494 (378 from the literature, 116 guess
  only); 136,260 more connections (239,393 synapses) removed.
- `al_ln_literature+da_5ht_modulatory`: dopamine + serotonin cells, 997 (445 literature, 552
  guess only); 205,612 connections (402,094 synapses).
- `al_ln_literature+da_5ht_literature`: dopamine + serotonin cells known from the literature
  only, 445 (378 dopamine, 67 serotonin); 122,500 connections (220,590 synapses).
Rules: the literature decides first; the machine guess is used only when the literature names
no transmitter (not at all in the literature-only fix). Never touched: antennal-lobe local
neurons, guess-only sensory neurons (580), CSD, cells already brakes or without outputs (65),
octopamine/tyramine cells (fast glutamate co-release). New tests: `tests/test_neuromod.py`
(7 tests).

**What happened: checks against the paper** (each fix alone vs `al_ln_literature`, 3 seeds x
30 trials, same trials as the sign audit; MN9 in spikes/s):
- `+da_5ht_literature` passes every check: sugar 100 Hz 68.1 (was 67.3; paper 65.7), sugar
  200 Hz 94.1 (93.5), water 30.9 (30.8), bitter alone 0, sugar + bitter 1.48 (1.36), no
  runaway (0 of 90 for Ir94e 200 Hz and for DM1 150 Hz), Kenyon cells active under DM1
  3.1% (3.6%).
- `+da_modulatory` and `+da_5ht_modulatory` pass everything except water -> feeding, which
  is 26-28% weaker (22.3 and 22.9 vs 30.8); the cause is three taste-area cells (CB0573,
  CB0461, CB0088) whose "dopamine" label is only a machine guess.
- Phase 8's sugar -> MN9 check with learning switched on, for `+da_5ht_literature`:
  identical spikes in 60 of 60 trials (3 seeds x 10 trials x 2 rates), MN9 67.0 and 93.2,
  not one Kenyon-cell -> output-neuron connection changed. Passes.

**What happened: punishment learning in the whole brain** (Phase 8 rule and calibration
unchanged; 3 simulated flies; "net" = minus the same fly's no-training run):
- Dopamine cells alone: no help. PPL1-γ1pedc still fires 12.7 spikes per sniff and every
  condition still ends near -100%.
- Dopamine + serotonin cells: PPL1-γ1pedc fires 0.17 (guess-including fix) or 0 (literature
  fix) spikes per sniff. Removing only SMP384 and SMP504 (4 cells) is enough (0 spikes).
- `+da_5ht_literature`, approach neuron MBON-γ1pedc>α/β, input change after vs before:
  paired odor A + punishment: A -99.5%, B -47.2% (net -61% vs -9%); odors swapped: -98.8% vs
  -40.8% (net -60% vs -2%). The punished odor lost more than the other in all 6 runs; the
  net "learned" score (CS+ minus CS-) was -55% on average, below -20% in 5 of 6 runs (-30% to
  -90%); in the sixth (fly 2, odor A) the untrained fly already loses 76% of odor A's input,
  leaving little to learn (-10%).
- Controls (net learned score, mean and range): unpaired 0% (-8 .. +9), punishment only 0%
  (all 0), odor only -6% (-32 .. +10), backward -14% (-35 .. +8). One fly (fly 0) shows a
  -32% / -35% odor-specific drop in odor-only and backward training (circuit model: backward
  -9%; Hige et al.: none).
- Reward (PAM-γ5 + PAM-β'2a paired with A, "avoid" neuron MBON-γ5β'2a): A -98.8%, B -4.7%,
  3 of 3; unpaired +1.4% vs -0.5% (net learned score -1%, 0 of 3). Passes.
- Still off: with no training at all, the approach neuron's input over the 4 test sniffs of
  an odor after the (empty) training period is 39% lower than over the 4 before (3% to 76% by
  fly and odor; circuit model about 2%). Causes seen in the runs: PPL1-γ1pedc still fires a
  stray spike about once every 8-10 sniffs, and PPL1-γ1 (PPL102, also sending dopamine to
  part of this neuron's Kenyon-cell synapses) fires 2-3 spikes per sniff of odor B.
  PPL102 input trace (first sniff, learning off): 0 spikes for odor A, 3-5 for odor B in all
  3 flies; its input during odor B is about 2.5 times that during odor A, mostly from outside
  the mushroom-body circuit (biggest: LAL185, CRE011, SMP385, SMP177, CRE078; none is a
  literature dopamine or serotonin cell), so this fix cannot remove it.

**Verdict.** PLAN.md Phase 8 checkpoint in the whole brain with `+da_5ht_literature`: the fly
learns in the right direction for punishment and reward, odor-specifically, and does not
learn in the unpaired control; odor-only and backward controls are near zero on average
but not in every fly, and test sniffs alone weaken the read-out by about a third. **Passes,
PRELIMINARY, with those caveats.** The project default was NOT changed
(`RECOMMENDED_FIX = "al_ln_literature"`); switching is the owner's call.

**Validated?** No (PRELIMINARY). Phase 6 validation was not done. Unverified: that SMP384
and SMP504 really are serotonin cells (one shape-match source plus cell-body position); that
these cells have no fast co-transmitter; the slow effects themselves are not modelled (only
dopamine's effect on Kenyon-cell -> MBON synapses is); 3 seeds only; some literature sources
were used through abstracts or search summaries (marked in the doc).

**Files.** `sim/sign_fixes.py` (additive), `tests/test_neuromod.py`,
`experiments/phase7_neuromod/` (counts, identity tables, validation runs and tables),
`experiments/phase8_aversive/` (sniff traces, conditioning, regression, summaries, plot
`plots/aversive_compare.png`), `docs/phase7-neuromodulators.md`.

## 2026-09-23 - Phase 7 item 5: electrical synapses (gap junctions) in the antennal lobe (PRELIMINARY)

**Question.** The wiring diagram has no electrical synapses (gap junctions: pores that join
two cells so current flows between them both ways, instantly). The recommended sign fix
`al_ln_literature` removed the chemical synapses of excitatory antennal-lobe local neurons
(eLNs) onto projection neurons (PNs) *because* recordings say eLNs reach PNs electrically.
Adding those electrical connections back, only where recordings measured them: does the
model still pass the Phase 3 checks, and does it change the one-sided DM1 steering?

**Sources.** Full text + bar charts viewed: Yaksi & Wilson 2010 (Neuron 67:1034; eLN->PN
coupling coefficient about 0.010, 0.014 with chemical transmission blocked, abolished in the
*shakB2* gap-junction mutant; "each eLN is connected to most or all PNs"; sister DA1 PNs
coupled), Kazama & Wilson 2009 (Nat Neurosci 12:1136; sister DM6 PNs, electrical part about
0.016, other-glomerulus pairs about 0). Figures and abstract only: Huang et al. 2010 (Neuron
67:1021; eLN->PN about 0.015). Abstract only / searched, not used: Wu et al. 2011 (APL-DPM,
no strength), Liu et al. 2016 (Kenyon-cell dye coupling, no strength, cells unknown), Shyu et
al. 2019, Ammer et al. 2022 (visual VS/HS, UNVERIFIED). Bar-chart values were read by eye
(about +/-0.002).

**What changed.** New `sim/gap_junctions.py` (the engine file is not touched): a copy of the
compiled loop that adds `kappa x (v_partner - v_self)` to each coupled cell's voltage update
plus a small "spikelet" per partner spike, and `build_gap_brain()` = `al_ln_literature` +
junctions. kappa = junction conductance / the cell's own leak conductance; it is chosen so
the model, probed like the experiments (steady current into one cell of the coupled network),
gives the measured coupling coefficients: kappa 0.0145 (eLN-PN, target 0.013) and 0.0197
(sister PNs, target 0.016). Spikelet = kappa x 40 mV x 1 ms / 20 ms (spike width ASSUMED).
Pairs (no gap junctions in FlyWire, so chosen by rule): each of the 44 literature eLNs with
every uniglomerular PN of every glomerulus it touches (>= 5 shared chemical synapses):
7,371 pairs; every pair of same-glomerulus, same-side uniglomerular PNs: 703 pairs. Table
with a source per row: `experiments/phase7_gap/results/coupling_table.csv`. Tests:
`tests/test_gap_junctions.py` (zero junctions = the old engine spike for spike, on small
networks and on the whole brain; two coupled cells give kappa/(1+kappa); spikelet size).

**What happened.** Each run was 3 seeds x 30 trials, compared with `al_ln_literature`.
- Taste checks (Phase 3): identical. All 450 taste trials have the same spike totals, and
  MN9 is 67.28 / 93.53 / 30.79 / 0.00 / 1.36 Hz for sugar 100, sugar 200, water, bitter and
  sugar+bitter. Runaway: 0 of 90 trials for Ir94e 200 Hz, DM1 150 Hz and DA1 150 Hz.
  Kenyon cells under DM1: 3.62% before, 3.61% after. In 19 of 90 Ir94e trials a single
  projection-neuron spike no longer happens, which shifts that trial's total; re-running
  five of those trials confirmed this (`results/check_ir94e.txt`).
- Antennal lobe: each eLN is joined to about 170 cells that sit mostly at rest, so its input
  conductance is 3.5 times higher and it goes nearly quiet (DM1 smell: 16.9 -> 2.3 Hz). The
  lateral excitation of other glomeruli seen in flies does not appear: the other 309 uPNs
  stay at 0.15 -> 0.14 Hz.
- DM1 steering. Turn = left minus right DNa02, in Hz, for a left / right smell. Before:
  +5.7 / +4.8. After: +15.8 / +5.8. The signal now depends on the smell's side (d' 0.2 ->
  2.6), but a right smell still says "turn left". **The DM1 bias is not fixed.**
- Why the DM1 signal changes: eLN-PN junctions alone give +20.1 / +5.4, and sister-PN
  junctions alone give +3.4 / +4.7. No junctions with the 44 eLNs silenced gives
  +30.8 / +5.2. So the change comes from quieting the eLNs, not from electrical excitation
  of the projection neurons.
- DA1 steering is unchanged and still correct: +21.7 / -15.6 before, +21.5 / -15.6 after.
- At half and double strength, every conclusion above still holds (DM1 d' 1.0 and 1.9).
- Verdict: keep as an optional switch (`build_gap_brain`), not the default.

**Validated?** No. PRELIMINARY: 3 seeds and 0.5x/2x strength were run and the checks were
compared with the literature, but the calibration numbers are read by eye from bar charts,
the spike width is assumed, the model's junction cannot rectify, and the eLN "loading" has no
measurement to be checked against. Details: `docs/phase7-electrical-synapses.md`.

## 2026-09-23 - Phase 7 upgrade 2 again: conductance-based synapses on top of the sign fix (PRELIMINARY)

**Sources.** Reversal potentials (unchanged from the first attempt, `docs/phase7-realism.md`):
excitatory 0 mV (Lee & O'Dowd 1999, J Neurosci 19:5311; Su & O'Dowd 2003, J Neurosci
23:9246: +8.9 mV in cultured Kenyon cells); inhibitory -60 mV (Rohrbough & Broadie 2002, J
Neurophysiol 88:847: -50 to -60 mV; McCarthy et al. 2011, J Neurosci 31:8181; Su & O'Dowd 2003:
-37 mV; all whole-cell). New, read through a web tool that returns quoted key sentences (not line
by line): Groschner, Malis, Zuidinga & Borst 2022, Nature 603:119 (PMC8891015; T4 neurons in
vivo: GABA reversal -68 mV, glutamate -71 mV, leak -65 mV; GluCl loss raises input resistance
5.28 -> 6.70 GOhm); Gouwens & Wilson 2009, J Neurosci 29:6239 (PMC2709801; projection neurons
598 MOhm, rest about -55 to -60 mV in vivo, 10-50 release sites per ORN connection); Liu,
Davoudian, Lizbinski & Jeanne 2022, Curr Biol 32:559 (bioRxiv version; excitatory unitary
potentials 0.4-6.6 mV, predicted by synapse density and location; no inhibitory connections
recorded). No fly measurement of a single inhibitory synapse's strength was found. Sign fix:
`docs/phase7-neurotransmitter-audit.md` (`al_ln_literature`).

**What changed.** `sim/realism.py`, additions only (every old setting, default and test behaves
as before; `tests/test_realism.py` 18 fast + 1 whole-brain tests pass unchanged):
`cond_exc_scale` and `cond_inh_scale` (separate factors on the excitatory and inhibitory
conductances, default 1.0), `build_realistic_brain(fix)` (the realistic engine on a sign-fixed
brain), the preset `CONDUCTANCE_SEPARATE_SCALES` (excitatory x1.2, inhibitory x0.87, reversal
0 / -60 mV), and a fix so that a sign-fixed brain reads the plain snapshot's neuron positions
(before, "sign fix + distance delays" could not be built; reported by the app lane). Tests:
`tests/test_realism_conductance.py`. Runs: `experiments/phase7_cond/`.

**What happened.** (3 seeds x 30 one-second trials unless stated; runaway = more than 1,500
different neurons firing in some 10 ms slice.)

1. *Does the sign fix cure the x2 version's runaways?* Yes: one global scale x2 on the
   sign-fixed brain ran away in 0 of 90 trials each with water, bitter, sugar 100 Hz and sugar
   200 Hz alone (unfixed brain, Phase 7's rule: 19, 4, 2, 2 of 90). But MN9 stayed 20% below the paper (52.8 Hz
   at sugar 100 Hz against 65.7 Hz) and the brain stayed 1.1-2.8 times as busy as the fix-only
   model (water most), with neuron-by-neuron correlation 0.84-0.95. With the fix it now passes all six
   Phase 3 checks on every seed (sugar + bitter 4.2 Hz) and never runs away with Ir94e 200 Hz or
   DM1 150 Hz either (0 of 90 each), but it is 1.4-1.5 times as busy there too and differs most
   neuron by neuron under Ir94e (correlation 0.86, 17 of the top 50). One-spike triggers: no
   ignition (the projection-neuron kick briefly reaches 1,587 different neurons in 10 ms, above
   the 1,500 mark, but totals 2,943 spikes and is silent in the last 100 ms).
2. *Separate scales.* Tuned on sugar 100 Hz, seed 900 only (22 settings tried), to MN9 = 65.7
   Hz and the fix-only model's total activity: excitatory x1.2, inhibitory x0.87 (per synapse
   0.00635 and 0.0299 leak units; 66.2 Hz and 9,866 spikes per trial on the calibration seed).
3. *Held-out validation (3 seeds x 30).* All six Phase 3 checks pass on every seed: sugar 100
   Hz 66.1 Hz (fix-only 67.3), sugar 200 Hz 93.1 (93.5), water 25.1 (30.8), bitter 0 (0),
   sugar 100 + bitter 120 3.0 Hz = 5% of sugar alone (1.4 Hz = 2%). Runaway 0 of 90 in all 9
   conditions (the five taste inputs, Ir94e 200 Hz, DM1 150 Hz both / left / right). Spikes per
   trial 0.91-1.17 times the fix-only model. Neuron by neuron against the fix-only model:
   correlation 0.982-0.996, 42-48 of the top 50 (noise floor >= 0.999 and 47-50). One-spike
   triggers: none ignite (36, 85, 2,154 spikes). Kenyon cells 3.3% (fix-only 3.6%). Steering
   unchanged: both odour sides still say "turn left" (+4.9 / +3.7 Hz).
4. *Sensitivity (1 seed x 30 each).* Stability is robust: 0 runaways in 1,140 trials with either
   scale or both changed by 10% (Ir94e and DM1 included). The feeding checks sit on the balance
   between excitation and inhibition: excitation -10% -> water 1.4 Hz (fails, bar 5 Hz);
   excitation +10% -> sugar + bitter 15.5% of sugar alone (fails, bar 10%); inhibition -10% ->
   10.8% (fails, just); inhibition +10% and both scales +-10% pass everything. The paper's own
   synapses (the fix-only model rebuilt with far-away reversal potentials, which reproduces it:
   67.8 / 93.9 / 29.7 / 1.4 Hz against 68.2 / 94.7 / 29.7 / 1.3 Hz) fail the same two checks
   under the same excitation shifts (water 3.0 Hz; bitter 13.0%) and pass the inhibition shifts
   (7.4%; 0.7%). So the edge is inherited from the paper's model and made somewhat sharper (MN9
   at sugar 100 Hz -41% / +18% for excitation -/+10%, against -28% / +20%).

**Validated?** PRELIMINARY. Phase 6 step 1 (3 seeds; +-10% of each tuned scale), step 2 (tests,
spike-identity with the sign-fixed brain when every switch is off) and step 3 (literature) done;
no independent review; the inhibitory reversal potential was not varied; not stacked with
upgrades 1 or 3. The machine rebooted at 03:09 during the runs; everything resumed from saved
per-trial files, no trial was run twice.

**In plain English.** Real synapses push less as the voltage approaches the channel's own
"stop" voltage. Adding that to the model broke the feeding result the first time. With the
fixed antennal-lobe signs, the old "make every synapse twice as strong" repair no longer makes
the brain run away, but it still cannot reach the paper's feeding number and it makes the whole
brain much busier. Giving excitation and inhibition their own strengths (1.2x and 0.87x) fixes
both: every taste check passes on every seed, the brain never runs away, and it behaves almost
exactly like the fix-only brain neuron by neuron. The catch: those two strengths are fitted,
not measured (no fly study measures one inhibitory synapse next to one excitatory synapse), and
the water and bitter results depend on the balance between the two strengths: a 10% shift of
excitation breaks one of them, exactly as the same shift does in the paper's own model (a little
more sharply here). So it is a usable optional switch, not the new default. Details:
`docs/phase7-conductance.md`.

## 2026-09-23 - Phase 9: brain-driven steering with the cVA smell channel (DA1) in the body loop; checkpoint attempt (PARTIAL, PRELIMINARY)

**What was changed.** Nothing in the brain model. Additive options in the body loop
(`sim/body/mapping.py`: `SensorMapping(antennae="left_only"/"right_only")` covers one
antenna; `dna02_drive_mapping()` and `dnpe002_drive_mapping()` read and silence only that
descending-neuron pair; `DNPE002_IDS`; one line in `sim/body/loop.py`). Old behaviour
unchanged (`tests/test_body_loop.py`: 22 passed in `.venv-body`, 20 passed + 2 skipped in
`.venv`). Everything run with the sign fix `al_ln_literature`, snapshot 630.
(1) Biology first, written before any closed-loop run (docs/phase9-da1-demo.md section
1): virgin females walk toward cVA on a food background (Lebreton et al. 2014, Y-tube),
mated ones do not; cVA is an aggregation pheromone (Bartelt 1985); close to a real male
(2-5 mm) flies of both sexes turn away (Taisz et al. 2023); more DNa02 on one side turns
the fly to that side (Rayshubskiy et al. 2025). Expected: turn toward cVA. Pass rule
fixed in advance: PASS only for a normal fly with the DNa02 read-out; PARTIAL if only a
one-antenna fly or only the DNpe002 read-out (whose turning direction is our
assumption) works.
(2) Brain-only check (no body), 50 ms windows, 3 seeds: the DA1 rates the body produces.
(3) Closed loop, 1.5 s trials, source 6 mm away. Normal fly: source at +90, +45, 0, -45,
-90 degrees. One-antenna fly: left or right antenna only, source left or right. Brain
conditions (DNa02 or DNpe002 steers) with 3 seeds each; controls: no odor, DA1 smell
neurons silenced and DNa02 silenced (3 seeds), DNpe002 silenced (seed 0), the
hand-written FlyGym rule (NOT brain-driven, seed 0) and the published model (seed 0).
142 trials in all. Metrics: turn toward the source (or toward the smelling antenna) in
the first second, closest approach, reached / time to reach; Mann-Whitney, paired
Wilcoxon and sign tests.

**What happened.**
- Brain only: when both antennae smell, the left/right difference is 1-3 Hz of
  smell-neuron firing, smaller than the model's built-in left bias in both read-outs, so
  both say "turn left" for a source on either side. With one antenna covered both
  read-outs point to the smelling side (DNpe002 in 99-100% of windows; DNa02 only above
  about 100 Hz).
- Normal fly: the DNa02-driven fly turned LEFT in 15 of 15 trials whatever the source's
  side; it turned toward the source in 6 of 12 (chance) and got no closer than the
  silenced fly (closest approach 4.1 vs 4.2 mm, p = 0.87). DNpe002: 7 of 12, 4.2 mm.
  NOT passed.
- One-antenna fly, DNa02: the left-antenna fly turns left, the right-antenna fly turns
  right: 11 of 12 trials raw, 12 of 12 against the same-seed silenced fly, +31 degrees in
  the first second vs 0 (Mann-Whitney p = 0.0006 vs DA1 silenced and vs DNa02
  silenced, n = 12 vs 12; paired Wilcoxon p = 0.0005). Right turns are
  weaker than left (left DNa02 2.7-10.7 Hz, right 0.7-4.7 Hz). It did not reach the
  source (0 of 6 with the source on the smelling side).
- One-antenna fly, DNpe002 (direction assumed): 12 of 12, about 130 degrees, reached the
  source 6 of 6 times when it was on the smelling side.
- Every silenced / no-odor trial got the straight drive [1, 1] in every 50 ms window, and
  all control paths for one walking-rhythm seed were identical (0.0 mm apart).
- Hand-written rule (NOT brain-driven): reached the source 5 of 5 times.
- Published model (no fix), DNa02: runaway activity, left DNa02 38-53 Hz vs right 0-0.7 Hz;
  the fly spins left in all 5 layouts and reached the source only when it was on the
  left (2 of 5).

**Validated?** No: PRELIMINARY. Phase 6 steps done: several seeds (3 for the brain
conditions), bug checks (tests; drive and path checks on the controls), literature,
comparison with biology. Not done: parameter variations in the closed loop. Not
verified: the FlyWire fly's mating status, the ORN side labels, what DNpe002 does in a
real fly, how a one-antenna female responds to cVA specifically, and whether a static
1/distance² cVA cloud reaching 6 mm is realistic (real cVA acts within a few mm).
Nothing shared, no one contacted.

**Plain English.** We let the brain steer the virtual fly with the one smell channel
that the brain model can tell left from right with: the male pheromone cVA. A normal fly
smelling with both antennae does not find the cVA: the two antennae smell almost the same,
and the model's built-in preference for the left wins, so the fly curves left whatever
side the smell is on. When one antenna is covered (a standard lab trick), the fly turns
toward the side of the antenna that still smells, as a real fly is expected to, and that
turn vanishes when the smell neurons or the steering neurons (DNa02) are silenced. So
the Phase 9 checkpoint is met only partly: in a one-antenna fly, not in a normal fly.
Walking speed and the legs are not controlled by the brain in any of this; FlyGym's
built-in controller does that.

Files: `experiments/phase9_da1/` (open_loop_da1.py, run_da1.py, analyze_da1.py,
results/, plots/), `docs/phase9-da1-demo.md`.

## 2026-09-23 - Phase 9: a video of the brain-steered fly (four DA1 trials re-run exactly and rendered) (PRELIMINARY)

**What was changed.** Nothing in the brain model and nothing in how the body loop
behaves. One additive, read-only hook in `sim/body/loop.py`: `run_trial(...,
on_substep=f)` (passed on to `Body.step`) calls `f(body)` after every physics step so a
script can copy the fly's pose; left out, nothing changes. `tests/test_body_loop.py` after
the change: 22 passed in `.venv-body`, 20 passed + 2 skipped in `.venv`. New scripts in
`experiments/phase9_video/`: `simulate_clips.py` re-runs four trials of the DA1 (cVA) demo
using `run_da1.py`'s own settings (same condition, layout, seeds, 6 mm source, 1.5 s,
50 ms windows, sign fix `al_ln_literature`) and saves the fly's full pose every 1 ms;
`render_video.py` poses and photographs the fly from those saves (no re-simulation),
marks the source, draws the path, adds a caption bar, and writes H.264 videos. No new
package: the encoder (`imageio-ffmpeg==0.6.0`) was already pinned in
`requirements-body.txt`. The four trials, all replicate 0 (walking-rhythm and brain seed
0): (A) one antenna covered, DNa02 steers (`one_dna02`, `B_Lonly+90`); (B) the same with
DNa02 silenced (`one_dna02_off`); (C) normal fly, source front-right (`dna02`, `A-45`);
(D) the hand-written rule, NOT brain-driven (`hand_rule`, `A-45`).

**What happened.**
- The re-runs are the saved trials: every column of every 50 ms window (position,
  heading, antenna smell, smell-neuron rates, DNa02/DNpe002 firing, turn command, drive)
  equals `experiments/phase9_da1/results/da1_windows.csv` to within 1.4e-14 (rounding of
  the saved text), with the same number of windows (30, 30, 30, 13)
  (`results/path_check.csv`).
- The fly drawn in the video sits on the logged path to within 1.8e-15 mm and 1.3e-14
  degrees at every window start (`results/render_check.csv`). A first version of this
  check showed gaps of up to 0.003 mm / 0.08 degrees. The cause: right after a physics
  step, MuJoCo still reports body positions from before that step, so each logged
  position belongs to the pose 0.1 ms earlier. Compared with that pose, the match is
  exact.
- Output: `phase9_video.mp4` (1.49 MB, 48.2 s, 1280 x 1136, 30 fps,
  half speed; an intro card, a title card before each clip, a closing card with the
  PARTIAL verdict), the four clips as separate MP4s, and `poster.png` (clip A at 1.0 s).
- What the clips show (numbers from the saved trials): A turns left, toward the only
  antenna that smells, +73 degrees in the first second, but does not reach the source
  (closest 5.55 mm). B walks straight (+9 degrees, the body's own drift). C turns LEFT
  +72 degrees, away from a source on its front-right, while its two antennae smell
  almost the same. D turns right and reaches the source at 0.60 s.
- Every frame's caption shows the condition, the steering source ("Turning:
  brain-driven (DNa02)", "none from the brain (DNa02 silenced)" or "NOT brain-driven
  (hand-written rule)"), the fly time, the left/right DNa02 firing (averaged over the
  last 0.25 s), the left/right antenna smell, and the line "Legs, walking rhythm and
  speed: FlyGym's built-in controller, NOT brain-driven".

**Validated?** No new result: the video re-shows four saved trials of the DA1 demo, whose
status is unchanged (checkpoint PARTIAL, PRELIMINARY; docs/phase9-da1-demo.md). Clip A
is the second-strongest of the 12 one-antenna DNa02 trials (63 degrees more than the
same-seed silenced fly; the 12 range from 8 to 75), not a typical one: right-antenna
trials turned much less. Some things in the picture are not data: the colours, the ball and
ring marking the source and its 2 mm "reached" zone, and the path line (the thorax
averaged over one 83 ms stride); all listed in docs/phase9-video.md. Checked by looking
at still frames and frames decoded from the finished MP4s. Not checked: playback in the
results web page or on a phone. Nothing shared, no one contacted.

**Plain English.** We made a short video of the virtual fly walking, for the results
page. It replays four of the trials from the cVA experiment exactly. When one antenna is
covered, the brain turns the fly toward the side that can smell. When the brain's
steering neuron is silenced, the fly walks straight. A normal fly with both antennae
turns left even though the smell is on its right: that is the model's failure, shown
honestly. A simple hand-written rule, with no brain, walks straight to the smell. In
every clip the brain only picks left or right; the legs and the walking speed come from
the body simulator.

## 2026-09-23 - Phase 6: is FlyWire's left/right lean in other flies? BANC, maleCNS and hemibrain compared (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/` or `tests/`. New analysis
scripts in `experiments/banc_asymmetry/` and a write-up in `docs/banc-asymmetry.md`. Public
data from the BANC team's bucket
(`https://storage.googleapis.com/lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/`;
no login) went into `data/banc/` (about 4.2 GB, not committed). It has BANC v888 (a second
adult female fly), plus the hemibrain v1.2.1 and maleCNS v0.9 in the same column format.
`common.py` holds the ORN -> PN part of `experiments/phase6/steering/s1_anatomy.py`,
moved into a shared function unchanged. `a0_check_port_flywire.py` shows it reproduces
the saved FlyWire tables cell for cell (`glomerulus_map_630/783.csv`,
`pn_ipsi_contra_630/783.csv`) and every number in docs/phase6-steering.md section 3.
`a1`-`a6` then run BANC, the other two flies, the comparison, a per-ORN branch check and
the figure. Edge lists are streamed and filtered; peak memory stayed well under 1 GB.

**What happened.**
- Label matching: BANC ORN = `olfactory_receptor_neuron` with type `ORN_<glomerulus>`, side
  from the `nerve` column (as FlyWire: the nerve-entry side). PN = `antennal_lobe_projection_neuron`,
  uniglomerular by FlyWire's rule (50% of ORN input from one type, 20+ synapses). Proofread
  or roughly proofread neurons; every connection counted, even 1 synapse (the paper's v2
  synapses). BANC side checks pass: PN cell bodies 345/348 and 335/340 on their side;
  the ORN `side` column agrees with the nerve for 2,055 of 2,079; 2,546 of 2,790 ORNs
  favour their own side's PNs. The results hold with strict proofreading, all fragments,
  `side`-column ORN sides, and the v3 synapse detector (`results/banc_summary.csv`).
- As released, BANC mirrors at the first synapse in 46 of 46 glomeruli, with a median
  same-side/other-side ratio of 2.39 (FlyWire 32 of 51, 1.25). But 42.5% of BANC's ORNs
  have NO synapses onto the far side's PNs of their glomerulus (FlyWire 3.6%, maleCNS
  11.7%). That is 75.8% of roughly proofread ORNs and 28.4% of fully proofread ones
  (`results/orn_branch_check.csv`). Real ORNs nearly all branch to both sides, so this is
  a reconstruction gap that inflates the same-side ratio.
- Fair version (only ORNs with synapses on both sides; `results/complete_orns_summary.csv`):
  median same-side ratio FlyWire 1.27, BANC 1.63, maleCNS 1.62, hemibrain right lobe 1.72
  (22 glomeruli whose ORNs have a named antenna). Glomeruli where the size imbalance beats
  the same-side advantage: FlyWire 20 of 52, maleCNS 11 of 51, BANC 5 of 41. Median size
  imbalance: FlyWire 21%, BANC 12%, maleCNS 11%.
- DM1: the left side is bigger in BANC too, by 23% (FlyWire 49%, maleCNS 10%). But BANC's
  same-side factor (1.45) beats it: a right-only smell gives the right DM1 PNs 1,580 vs
  1,365 synapses, so DM1 mirrors. Share of the lobe's smell input: FlyWire left DM1 7.07%,
  against 4.11-5.83% in the other 5 lobes (FlyWire right 5.26%). So FlyWire's LEFT DM1 is
  the outlier. DA1 mirrors in every fly. BANC's DA1 is unreliable: only 12 of 113 left
  DA1 ORNs keep a crossing branch.
- Different glomeruli are lopsided in each fly (rank correlations of the size imbalance
  -0.21 / +0.34 / +0.07 signed, -0.09 / +0.17 / -0.01 unsigned). Which glomeruli have a
  strong same-side advantage does match between flies (+0.73 / +0.86 / +0.59, all
  p < 0.001). Swap test (41 glomeruli): FlyWire's sizes with BANC's same-side factors
  give 33 mirroring (actual 25); BANC's sizes with FlyWire's give 28 (actual 36).
- Label problems found in the harmonised copies: maleCNS `nerve` behaves like a random
  label for ORNs (same-side ratio 0.95), so its `side` column was used. The hemibrain's
  `nerve` is filled per ORN type, so the neuPrint `_L`/`_R` instance suffixes were used.
  BANC's `output_side_index` does not match its documented meaning; not used.
- Figure: `plots/fly_comparison.png` (4 panels, one dot per glomerulus, the exact
  "mirrors" wedge shaded).

**Validated?** No: PRELIMINARY. Done: the code port was checked exactly against FlyWire;
the two-factor split was checked in every glomerulus of every fly; BANC was re-run with
2 synapse detectors, 3 proofreading rules and 2 ORN-side sources; the BANC labels were
checked four ways. Not done: why BANC lacks the crossing branches; whether FlyWire's weak
same-side advantage is biology or reconstruction; whether "left" is the fly's true left
in every dataset (so "DM1's left is bigger in all 3 flies" is noted, not claimed). No
literature search on fly-to-fly glomerulus size variation. Nothing shared, no one
contacted.

**Plain English.** We checked the "always turns left" wiring in three other fly brains
that are free to download. In the second female fly, the left vinegar glomerulus is
also a bit bigger, but only half as much as in FlyWire. There, each side's smell
neurons favour their own side strongly enough that the fly would still steer
correctly. FlyWire's left vinegar glomerulus is the odd one out: bigger than any other
we measured. FlyWire also has the weakest same-side preference of the four flies. The
second fly's data has a gap: in almost half its smell neurons the branch that crosses to
the far side is missing. That makes it look perfect when it isn't, so we compared using
only complete neurons. Which glomeruli are lopsided differs from fly to fly, so the lean
is a FlyWire quirk, not a rule of fly wiring.

## 2026-09-23 - Phase 6 step 3: literature check of the bitter brake (CB0219), the runaway and the left/right imbalance (PRELIMINARY)

**What was changed.** Nothing in the model, code or data. New document
`docs/phase6-literature-check.md`. No simulations. Read-only look-ups:
- in local files: both FlyWire annotation tables, the snapshot 630 connection list, the
  snapshot 783 connection table, the model repository's list of named SEZ neurons, and
  the steering lane's per-glomerulus table;
- in the public Virtual Fly Brain database (its search index and graph database).

Papers were read through PubMed Central / Europe PMC full text, arXiv PDFs, abstracts
and GitHub READMEs. Each source is labelled full text or abstract in the doc.

**What happened.**
- **CB0219 is "Scapula" (KNOWN).**
  - The Scott lab's 2022 tracing of Scapula (Shiu et al. 2022, *eLife*; FAFB CATMAID
    16887116) best matches our CB0219-left by shape (NBLAST 0.81, Virtual Fly Brain) and
    next CB0219-right (0.66).
  - The FlyBase ontology class "adult CB0219 neuron" has the male CNS name GNG087.
  - The wiring matches the 2022 description: in 630 the model's 21 bitter GRNs give
    CB0219 359 synapses, the second-largest bitter input of any named type, and none
    come from sugar GRNs. It inhibits the premotor neurons Roundup (47/36 synapses),
    Rounddown (DNge080, 105/105) and Roundtree (CB0493, 142/141). It sends at most 8
    synapses to the other named sugar-pathway neurons.
  - The male CNS also predicts glutamate for GNG087 (0.72-0.79).
  - Shiu 2022 had already proposed "sugar and bitter tastes are integrated at feeding
    initiation premotor neurons", backed by calcium imaging (Roundup suppressed by
    bitter, G2N-1 not).
  - Jacobs et al. 2024 (*Cell Rep* 43:114782; abstract read, full text blocked) ran
    connectome simulations. Search excerpts say "bitter suppression of Roundup and MN9
    was abolished by silencing Scapula but not Mime or Marge". Marge = CB0812, our
    rank-5 candidate.
  - No real-fly experiment on Scapula itself was found. Bohra et al. 2018's pair of
    bitter SEZ interneurons (silencing: proboscis extension to sucrose + quinine 5% ->
    25%) may or may not be the same cells.
- **The runaway (PARTLY KNOWN).**
  - The paper, its 10 GitHub issues, the model author's 2025 review and later papers
    do not report it.
  - Some modellers expected instability and scaled weights down to avoid it (Wang et al.
    2025, Loihi 2; Pospisil et al. 2024).
  - A public, non-peer-reviewed project (Jadog1122/fly-with-a-real-brain, created
    2026-09-12, snapshot 783) reports the same state: all 53 glomeruli give "~8,300
    neurons active", the network is bistable, and they "did not localise the runaway".
  - Our cause (antennal-lobe eLNs) and fix were not found anywhere.
  - Transmitters: FlyWire v783 guesses for lLN1_bc are mixed and weak (11 acetylcholine
    / 12 dopamine / 7 serotonin, confidence about 0.3). The male CNS predictions (Berg
    et al. 2025, via Virtual Fly Brain) call 30 of 30 lLN1_bc and most lLN2T cells
    acetylcholine (0.7-0.8), confirming the Phase 7 audit.
- **The left/right imbalance (PARTLY KNOWN).**
  - Schlegel et al. 2024: FlyWire is "mostly" symmetric, and about 1 cell type in 6
    differs in number between the sides.
  - Also Schlegel et al. 2024: synapse completion differs by side and region, and
    dark-cytosol artefacts that hide synapses are "much" more common in sensory neurons
    (their example: a DM3 PN, dark on the left only).
  - No DM1-specific report was found.
  - DM1 has 35 left vs 33 right ORNs, so the 52% synapse gap is not an ORN-count gap.
    Across the 53 glomeruli of snapshot 783, synapse asymmetry follows ORN-count
    asymmetry only weakly (r = 0.16).
  - Real flies turn toward one-sided DM1 activation (Gaudry et al. 2013), so the model
    contradicts biology here.
- Citation fix spotted for docs/phase5-competition.md: French et al. 2015 is *J
  Neurosci* 35(9):3990-4004, not 35:9542.

**Validated?** PRELIMINARY as a whole.
- VALIDATED: the CB0219 = Scapula identification (shape, ontology, wiring and two papers
  agree). The old-to-new root-ID step needs a FlyWire login and was not done.
- PRELIMINARY: the Jacobs 2024 silencing claim (excerpts only), Bohra 2018 (abstract
  plus preprint extract), and the READMEs (not peer-reviewed; not reproduced by us).
- "Not found" means not found in Europe PMC, PubMed Central, arXiv, GitHub, Virtual Fly
  Brain and web search. Paywalled full texts and the FlyWire forum were not searched.
- Nothing shared, no one contacted.

**Plain English.** We checked whether our three surprises were already known. The
neuron that acts as the model's "bitter brake" was already named "Scapula" by a fly lab
in 2022. They predicted from the wiring that it stops feeding when food tastes bitter,
and at least one later modelling paper seems to have found what we found. So that one is
a confirmation, not a discovery. The model is getting a known answer, and the real-fly
test of that neuron still hasn't been done. The runaway, where smell input locks the
simulated brain into non-stop firing, has been noticed by at least one other hobbyist.
Nobody has explained it; our explanation and fix look new, and this is the finding
worth telling the model's authors about (the author's call). The left/right difference in the
smell centre isn't reported anywhere. The FlyWire authors warn that sensory neurons are
more prone to reconstruction problems on one side, so it may be a flaw in this one
reconstruction rather than a real difference; a second brain has to settle it.

## 2026-09-23 - Claims audit: do the numbers we quote match the saved results? (PRELIMINARY)

**What was changed.** Nothing in the model, the app, the tests or any existing doc. New:
`experiments/claims_audit/audit.py`, which recomputes every number quoted on the results
overview page and in the docs' short versions from the rawest saved files (every Phase 3
spike, per-trial tables, the raw connection lists via row-count metadata and two batched
column passes, the per-seed steering rates, the per-fly learning tables, the DA1 trial
table). It writes `results/audit.csv` (82 rows: claim, where quoted, quoted value,
recomputed value, source file, status, note). Write-up: `docs/claims-audit.md`. No
simulation was run and the whole brain was never loaded. The script waits for 1.5 GB of
free RAM before the connection-list passes. It runs in about a minute.

**What happened.**
- 65 requested claims: 51 MATCH, 1 MISMATCH, 6 AMBIGUOUS, 7 NO-SOURCE. 17 extra claims found
  on the way: 11 MATCH, 3 MISMATCH, 2 AMBIGUOUS, 1 NO-SOURCE.
- Every headline number reproduces from raw data. Phase 3 MN9 for all 7 experiments (sugar
  at 100 Hz: 67.00 Hz from the 10 trials' spikes). The paper's 65.7 / 93.2 match the paper's
  own Supplementary Table 1A (65.70 / 93.23). 12 of 12 direction checks, re-derived; two of
  them are the same comparison, so 11 are distinct. Counts from the raw data files: 127,400 /
  14,687,178 (630), 138,639 / 15,091,983 / 54,492,922 (783). CB0219 gets 247 synapses from
  bitter GRNs and 0 from sugar GRNs. DM1's left PN gets 3,724 receptor synapses vs the right
  PN's 2,450 (+52.0%). Silencing screen r = 0.9305 / 0.9334 over 198 neurons. Hill fit
  redone: b50/sugar 0.465-0.561. CB0219 rescue 12.36 -> 65.70 Hz (97.6%). Sugar holds in
  28/28 + 15/15, -47.2% to +18.7%; water flips in 3/28 + 1/15. DM1 90/90 vs 0/90, Ir94e
  10/90. DA1 22.69 vs 1.01 and 15.73 vs 0.14 Hz. All ten circuit learning numbers. Body demo
  counts and p-values (Mann-Whitney 0.00058). Clip A is 2nd of 12 (63.2 deg).
- The one requested MISMATCH is a label on the results page: the neuron that lost 91% is
  called the "avoid" output neuron. It is MBON-γ1pedc>α/β, the "approach" neuron in
  `docs/phase8-learning.md` and in the analysis code.
- AMBIGUOUS:
  - "12 of 12" for the one-antenna fly counts wins over the same-seed silenced fly; in
    absolute terms 11 of 12 turned toward the smelling side. The silenced fly's "0 deg" is
    exactly zero by design: its per-seed drift (+9.4, -6.8, -14.4 deg) is the same in every
    layout and cancels across mirrored layouts.
  - "Every runaway begins at the 38 eLNs": in the 50 ms before onset, the first neuron to
    fire is one of the 38 in 3 of the 6 traced runaways (another antennal-lobe local neuron
    in 1, an unlabelled neuron in 2). eLNs are 0-3 of the first 10 to fire; antennal-lobe
    local neurons of any kind are 5-7. Phase 7 found DM1 still runs away in 90/90 trials
    with only the eLNs fixed.
  - "About 8,300 neurons": the saved runaway trials give a median of about 8,200 that fire,
    and about 7,700 still firing at the end.
  - Brian2 "1-4 minutes": the 55 saved trials took 1.0-6.5 min (median 1.9).
  - "Hundreds of times faster" (page) vs "about 100 times" (fast-engine doc).
  - "Counts match FlyWire's": the synapse counts match, but the neuron count is 616 short
    (all of them zero-synapse neurons).
- NO-SOURCE: five of the paper's Phase 3 numbers (water 30.7, bitter 0.0, sugar+bitter 45.3
  and 1.5, sugar+Ir94e 64.3; the authors' result CSVs were never saved). The app-equals-code
  check (printed, not saved). Hige's 90% (literature; `calibration.json` shows the learning
  speed was fitted to a 90% drop, so the 91% match is by design). "211 tests pass" (no saved
  full-suite log).
- Extra MISMATCHes, all inside doc bodies: `docs/phase3-explained.md` "16 or 17 more active
  neurons" (at 100 Hz it is 12 more), and it names a `results/v783/` folder that does not
  exist; `docs/phase5-competition.md` "seeds differ by at most about 1 Hz" (up to 3.1 Hz).
- The page's "28,101 lines / 26 commits / 24 write-ups" are exact at commit 9bcdac4. HEAD
  has moved on since (29,339 / 27 / 25 when checked).

**Validated?** This is a check of reporting, not a new result. Each status was re-derived
by code from saved files. The audit's own mistakes were caught and fixed before the final
run: 18-digit neuron IDs losing precision through floats; a "first neuron" test that
picked up chance spikes hundreds of ms before onset; a claim that the silenced fly always
drifts left (it does not). Not checked: anything that needs a new simulation (the app
comparison, the full test suite), and the paper-side numbers with no local copy.

**Plain English.** We went back through every number on the results page and in the
write-ups' summaries and recomputed each one from the saved raw results. 51 of the 65 we
were asked to check come out exactly the same. One thing on the page is wrong: it calls
the learning neuron the "avoid" neuron when it is the "approach" one. A few others are
correct but worded in a way that can mislead, like "12 of 12" when, in plain terms, 11 of
12 flies turned toward the smell. Some numbers can't be checked because the file they came
from was never saved. The most important of these is the real-fly learning number, which
the model was tuned to match. None of this changes a conclusion; `docs/claims-audit.md`
lists the exact line and a suggested rewording for each.

## 2026-09-23 - Real-fly scorecard: 39 published real-fly measurements turned into model tests (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or any existing doc. New:
`experiments/scorecard/build_catalog.py`, which holds the 39 hand-written items and looks every
named cell type up in FlyWire's neuron tables (630 labels; 783 labels and literature synonyms
carried back to 630 by the same root ID, or by the same soma/anchor position within 2 um). It
writes `catalog.csv` (39 rows: real-fly result, measurement type, source and figure, full text
or abstract, model test, cell types, 630 IDs, mapping confidence, expected result, numeric
target, feasibility and reason, cost, first-batch rank) and `ids_630.csv` (3,125 ID rows, each
with how it was found). Run log: `build_log.txt`. Write-up: `docs/real-fly-scorecard.md`. No
simulation was run; the connection tables were never loaded. Papers were read through Europe
PMC abstracts and open full text (searched for the exact sentences), the NCBI BioC service, and
one eLife page summary.

**What happened.**
- 39 items. By area: taste and feeding 7, mechanosensation and grooming 4, smell 5, learning 5,
  steering and descending neurons 6, temperature and humidity 5, pheromones and female courtship
  5, vision 2. By feasibility: 20 YES, 13 PARTLY, 6 NO.
- Recommended first batch (all YES, all cheap): FC2 SAG -> pC1a >> pC1b > pC1c-e
  (Wang et al. 2020, Fig. 3d-f); FC5 cVA -> aSP-g 11/15, aSP-f 1/34, aSP-h 2/8 in females (Kohl
  et al. 2013); FC1 vpoEN and pC1 -> vpoDN (Wang et al. 2021); SD4 one-sided PFL3 -> same-side
  turn in about 92% of trials (Mussells Pires et al. 2024, Fig. 5e-h); TH3 cold -> TPN-II ->
  DN1a inhibition (Alpert et al. 2020, Fig. 5); TH2 with TH1 cool-to-warm crossover inhibition
  (Liu et al. 2015; 14/17 local neurons cool-excited, +6 +/- 1 mV when inhibition is blocked);
  OS4 sister projection neurons fire in sync, cross-glomerulus pairs barely (Kazama & Wilson
  2009); LL1 MBON11 (MVP2) activation suppresses M4/6 but not V2 odour responses (Perisse et
  al. 2016, Fig. 4A-B); SD1 with SD2
  LC16 -> MDN (Sen et al. 2017); TF4 Usnea water-only, Phantom both, Clavicle sugar (Shiu et
  al. 2022, Fig. 3). Reserves: FC3, OS1, TF6.
- Best areas: female courtship and temperature. Every cell is labelled in the 630 table, the
  circuits are small, and the model is a female brain. Weakest: mechanosensation (nerve cord,
  graded signals, unnamed relay cells) and vision (graded early neurons, no eyes).
- ID mapping: 2,039 rows from 630 labels, 805 from an unchanged root ID in 783, 20 by position
  (all at 0.00 um, so the same cells renumbered), 257 from project ID lists (the Shiu lab's SEZ
  list, `sim/shiu_model.py`, `experiments/heldout/ids.py`). 2 hearing sensory neurons could not
  be mapped (4 blank rows).
- Left out on purpose: results already covered (Shiu 2024 Phase 3 and silencing screen,
  Scapula, Hige 2015, Gaudry 2013, Hampel 2015 grooming, the held-out lane's ISN and OA-VPM4)
  and results the model was built from (Aso & Rubin 2016 sets the slow a2/a3 compartments in
  `sim/plasticity.py`; Turner et al. 2008 Kenyon-cell sparseness was already compared).
- Overlap found late: the olfaction lane (`docs/olfaction-vs-real-fly.md`, in progress) already
  scores OS2 (lateral inhibition), most of OS3 (amplification curve) and OS5 (APL). They are
  marked DUPLICATE in the catalogue and kept out of the first batch; OS1 and OS4 are not covered.
- Not found in FlyWire's annotations: TPN3 (bitter taste), oviEN (egg laying), wedge projection
  neurons (wind). Items that need them say so.

**Validated?** No: PRELIMINARY. This is a literature catalogue, not a result. 17 items were
checked against full text, 22 against abstracts only (their figures are "not checked"). IDs were
found by code and re-checked by hand for the position-matched ones. Moderate or low confidence:
Liu's cool-/warm-PN vs FlyWire types, TPN-II = VP3+_vPN, V2a/V2a' = MBON18/MBON16-17, the
aSP-f/g/h clusters. Possible overlap with the Shiu 2024 paper's own checks for TF1, TF4, TF5
(not checked in its figures).

**Plain English.** We made a list of 39 experiments done on real flies that our simulated brain
can be scored against: switch on these cells, watch those cells, and compare with what the fly
did. For each one we wrote down the exact neuron numbers in our model, the answer the fly gave,
and whether our model can run the test at all. 20 are fully runnable, 13 only partly (for
example because the fly used its nerve cord or slow brain chemicals), and 6 not at all. The ten
we suggest running first are small, cheap, and have clear answers, mostly from female-courtship
and temperature circuits, where every cell is already labelled in our data.

## 2026-09-23 - Held-out validation: the paper's grooming results, real-fly grooming and feeding results it never scored, and whether the fixes generalise (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or any existing doc. New:
`docs/heldout-validation.md` and the folder `experiments/heldout/` (`ids.py`,
`fetch_published.py`, `published_summary.py`, `run_heldout.py`, `check_changed.py`,
`robustness.py`, `feeding_heldout.py`, `isn_wiring.py`, `analyze_heldout.py`, `queue.sh`,
`results/`, `plots/abn1_curves.png`). Why: every fix so far was chosen or checked on the
same Shiu et al. 2024 taste-to-MN9 results, so nothing showed whether the fixes
generalise. This lane ran published results no variant was chosen on. Pass/fail rules
were written into the doc before any simulation ran (section 1; the feeding tests and
their scoring details were added at 18:16 and 18:24, before those runs). Sources: Shiu et
al. 2024 Fig. 5 and Ext. Data Fig. 4 (text from PMC11446845, code from
`data/reference/figures.ipynb`), the authors' own output files (Edmond
doi:10.17617/3.CZODIW; 61 small files fetched by byte range, not the 4 GB archive), Supp.
Table 10 (the paper's own scoring); Hampel et al. 2015 *eLife* 4:e08758 (Fig. 6
functional connectivity); Hampel et al. 2020 *eLife* 9:e59976 ("aJO" renamed JO-F);
Calle-Schuler et al. *eLife* 14, doi:10.7554/eLife.108044 (FlyWire IDs of aBN2_1-3);
Youn et al. 2018 *PLoS ONE* 13:e0198362 (OA-VPM4; abstract) and Jourjine et al. 2016
*Cell* 166:855 (ISNs; abstract only, the full text was blocked). Engine
`sim/fast_engine.py`, snapshot 630, 3 seeds x 30 trials x 1 s per condition, and the same
random input for every variant (same seed).

**What happened.**
- Published model, the paper's grooming results (Tests A-C): reproduced. aBN1 with the
  70 JO-CE sensors at 100 / 220 Hz: 26.1 / 25.8 / 25.8 and 73.0 / 72.7 / 72.7 Hz (paper
  25.4 / 73.1). With the 60 JO-F sensors: 0.7-1.0 and 4.6-5.3 Hz (paper 0.9 / 4.6). JO-F
  with the three GABA cells silenced: 22.1-22.4 and 65.8-66.4 (paper 22.4 / 66.4). All 146
  JONs at 220 Hz: aBN1 77.5-77.8 (78.2), aDN1 37.9-38.2 (38.4), aDN2 38.2-38.4 (38.6); 660-702
  non-JON neurons fire per seed (677); every neuron's rate correlates with the paper's at
  r = 0.9999.
- The paper's two 300-neuron screens, run on its 154 non-sensory neurons (1 seed x 10
  trials each; the 146 single-sensor runs were dropped for time). Required for aDN1
  (all JONs at 140 Hz, each neuron silenced): exactly aBN1, aDN2 and DNge220 cut aDN1 by
  more than 20% (to 0.00 / 0.64 / 0.80 of the control; paper 0.00 / 0.63 / 0.75), and
  the next two match too (0.88 / 0.91 vs 0.85 / 0.89). Sufficient (each driven alone at
  200 Hz): only aBN1 (68.0 Hz; paper 68.5) and aDN2 (34.1; 33.6) drive aDN1 above 2 Hz,
  and the only weak ones are the paper's two (1.1 and 0.3 Hz; paper 1.07 and 0.33).
- Real-fly grooming results the paper did not score (Test F, Hampel et al. 2015; aBN2 =
  the 2026 IDs): 3 right (F3, F5, F6), 2 wrong, 1 can't tell, 1 not scored. F1: JO-F at
  220 Hz leaves aBN2 at 0.0 Hz and aDN1 at 0.2 (flies: both respond). F7: driving aBN2
  makes aDN2 FIRE (8.8 Hz, mean -48.5 mV, 3.5 mV above rest; flies: inhibition). Both
  misses survive synapses 20% weaker and stronger, aBN2 drive at 50 and 100 Hz, and each
  aBN2 cell alone (`robustness.py`). With the paper's aBN2 (DNge220) instead: F1 right,
  F3 and F6 wrong. With the 2026 aBN2, the cells never fire during JON input, so the
  model also predicts aBN2 is NOT required for aDN1, the opposite of the fly silencing
  data the paper scored as correct.
- Variants on the grooming tests: `al_ln_literature` is identical to the published model
  spike for spike (15 runs compared; none of its 150 changed smell neurons fires in any
  grooming condition, and all 54 feeding runs are identical too), so these tests cannot
  judge it. `+da_5ht_literature`
  holds (16 of 33 runs differ, all key rates within 1 Hz). `delays` holds (within about
  1 Hz). `adaptation` breaks Test A narrowly (JO-F drives aBN1 at 25-27% of JO-CE per
  seed at 220 Hz; limit 25%; published 7%) and Test B (silencing raises aBN1 only 3.3-3.9x;
  limit 5x), because the three GABA cells slow down (CB0443 79 to 64 Hz); Test C holds
  with aDN1 39% lower. `celltype` is identical to the published model in all 15 runs
  compared and `gap` in 14 of 15 (one run differs by one neuron), so these tests cannot
  judge them either (Tests A and B not run for these two). No variant fixes F1 or F7.
- Held-out feeding (G1-G5, published model): ISNs, 4 cells, at 100 Hz cut MN9's sugar
  response from 19.0 to 10.3 Hz (sugar 50 Hz) and 5.6 to 2.3 Hz (sugar 40 Hz), and raise
  the water response from 10.6 to 17.9 Hz: both halves the reverse of real flies (G3,
  G4 wrong; at 50 Hz the same direction, below the 20% / 1 Hz line). OA-VPM4 at 50-100 Hz
  raises MN9 by at most 4.5 Hz and not past the 20% / 1 Hz line in every seed (G1 can't
  tell); the source says OA-VPM4 acts by making sugar neurons more sensitive, which the
  model cannot represent, and the connectome has no OA-VPM4 synapse onto sugar neurons
  or MN9. Neither cell type fires during taste
  input, so the silencing tests (G2, G5) can't tell. Same verdicts for `al_ln_literature`
  (identical, 54 rows), `+da_5ht_literature` and `delays`. `adaptation` lowers every MN9
  response (sugar 50 Hz: 9.7 instead of 19.0 Hz); ISNs still lower the sugar response
  (9.7 to 5.3, G3 wrong) and raise the water response (1.8 to 4.0), which misses the
  1 Hz line in one seed (G4 can't tell). In the wiring, 48% of the ISNs' output synapses
  go to cells the model treats as inhibitory, which fits the drop in the sugar response
  (not tested by silencing). Only two feeding experiments (five tests) could be mapped
  in the time, fewer than the three to six planned.

**Validated?** PRELIMINARY as a whole. VALIDATED: the published-model reproduction
(Tests A-C: 3 seeds, within about 1 Hz of the authors' own files; Tests D-E: the same
neurons as the paper, 1 seed x 10 trials each); al_ln_literature's invisibility
here (a proof from which neurons fire, plus exact identity); F1 and F7 as robust model
behaviour. PRELIMINARY: that F1 and F7 are real disagreements with flies (depends on
the aJO = JO-F and aBN2 mappings); the adaptation result (one strength, narrowly past
the line); the ISN reversal (different readout, abstract-only source, FlyWire type name
as the mapping). UNVERIFIED: the 147 vs 146 JON count; the paper's aBN1 synapse counts
(103 / 78) versus the model's table (77 / 69). Nothing was posted, emailed or shared,
and no one was contacted.

**Plain English.** Until now every change to the model was judged on the same few
taste tests. So we tested it on results it had never been scored on. The paper's own
grooming results come out almost exactly right. But real-fly grooming experiments the
paper did not score catch two robust mistakes in the grooming circuit: one group of
antenna sensors never reaches two neurons it reaches in flies, and one neuron excites a
cell that real flies show it inhibiting. The smell fix we recommend never touches these circuits, so these
tests can't say whether it is right; a smell experiment is needed for that. The option
that makes neurons tire (adaptation) makes one real-fly grooming result slightly worse.
And in the feeding circuit itself, four neurons that make real flies drink more sugar
and less water do the opposite in the model.

## 2026-09-23 - Phase 6: do the runaway and its fix hold on FlyWire snapshot 783? Yes (VALIDATED; extras PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or the data. New:
`experiments/runaway_783/` and `docs/runaway-783.md`. `common783.py` holds our own copy of
the `al_ln_literature` rule. It runs on either snapshot, because `sim/sign_fixes.build_brain`
accepts 630 only. The scripts are s0-s6 plus `run_queue.sh` (one brain in memory at a time;
free RAM checked before each build). The pass/fail criteria were written into the doc
(section 1) before any 783 trial ran.

**What happened.**
- Port proof on 630 (`results/port_check.txt`): our copy of the rule gives the same
  connection list as `build_brain(fix="al_ln_literature")`, entry by entry. That is
  14,635,639 connections, the same 51,539 removed and the same 10,455 flipped. It picks the
  same 150 cells, builds identical brains, and gives identical spikes in 10 trials each of
  DM1 150 Hz, Ir94e 200 Hz and sugar 100 Hz, equal to the saved Phase 7 run. The published
  783 brain built from arrays equals `FastBrain("783")`.
- Cells: all 150 cells the fix changes in 630 were found in 783 by supervoxel (101 kept
  their root ID, 49 have new ones). 149 get the same treatment. The other one (CB1686) is
  already inhibitory in the 783 model. The rule on 783's own labels picks 166 cells (16
  made inhibitory, 150 limited). The 17 extra: 3 lLN2P_b (GABA); 12 local neurons that the
  630 model makes inhibitory but the 783 file makes excitatory; 2 OA-VUMa5 that 783 labels
  as antennal-lobe local neurons. Two versions were run: "rule" (166 cells) and "same
  cells" (the 630 set). Brain-wide, the 783 model file makes more GABA- or glutamate-guessed
  neurons excitatory than the 630 one: 1,348 vs 239 (GABA) and 2,941 vs 580 (glutamate).
  The cause was not traced.
- Inputs in 783: DM1 = 68 smell neurons (35 left, 33 right, `cell_type` ORN_DM1; exactly
  the 630 set). Ir94e = the paper's 18 IDs, unchanged. Sugar = 20 paper IDs plus
  720575940639259967 for 720575940620900446 (supervoxel lookup and the Phase 3
  fingerprint agree). MN9 720575940660219265 is unchanged.
- Published 783 (3 seeds x 30 one-second trials, same seeds as 630): DM1 150 Hz runs away
  in 90/90 (630: 90/90). Ir94e 200 Hz 4/90 (630: 10/90, p = 0.16); 17/300 with seeds 0-9
  (p = 0.095). The volleys (10 DM1 neurons, 44 eLNs, all 685 projection neurons fire once)
  all ignite (464,459 / 718,558 / 773,167 spikes). Same state: of the neurons that fire
  in seed-0 DM1 trials, 98% of 630's also fire on 783 (96% of 783's); 97% of the Phase 6
  core is in the 783 core (8,484 neurons). Healthy trials peak at 557 neurons per 10 ms,
  runaways never below 4,320.
- Fix on 783, both versions: DM1 0/90, Ir94e 0/90 (rule: 0/300 vs 17/300, p = 1.2e-5).
  Volleys die out (30 to 4,419 spikes). Kenyon cells under DM1: 3.61% / 3.68% per trial
  (630: 3.62%). Sugar 100 Hz -> MN9: 68.52 Hz in all three 783 versions, the same in every
  one of the 90 trials. Every spike of every neuron is identical in the 10 trials saved in
  full (630: 67.28).
- Silencing (published 783, seed 0): silencing the 44 eLNs stops the 10-DM1 volley (26
  spikes); 3 random 44-cell sets from the runaway outside the antennal lobe do not. DM1
  150 Hz still runs away 30/30 with the eLNs silenced. It stops (0/30) only with all 166
  excitatory AL local neurons silenced; 166 random cells: 30/30.
- Synapse strength (1 seed x 30): the fix holds on 783 at -10/+10/+20% (0 runaways for
  every input). Kenyon cells 2.65/4.60/5.38% (630: 2.72/4.56/5.38). Published 783 at -10%
  still runs away 30/30 on DM1. Ir94e on the published models at +5/+10%: 783 33%/63%,
  630 57%/93%.
- DM1 on one side only (3 seeds x 30): published 783 left 90/90, right 90/90 (630 the
  same). Both fixes give 0/90 on each side. Kenyon cells 2.1-2.2% per trial (630: 2.1-2.2%).
- Numbers: `results/summary_stats.txt`; figure `plots/fig_runaway_783.png` (runaway
  counts like Phase 7's fig1, 630 next to 783, plus sugar -> MN9).

**Validated?** VALIDATED for the questions asked: the runaway holds on 783, the fix holds
(both versions), and the taste result is unchanged. Each used 3 seeds, a port proven exact
on 630, and a comparison with 630. PRELIMINARY: the silencing and synapse-strength checks
(one seed), and the lower taste-trigger rate on 783 (p = 0.095). Not done: Brian2 on 783
(fast engine only; the Brian2 cross-check was only ever done on 630); smell channels other
than DM1; why the 783 model file has more excitatory cells. Nothing was shared or sent.

**Plain English.** Everything we had found about the runaway came from the older version of
the fly wiring map, the one the paper used. Before anyone could tell the model's authors,
we had to check the newer, public version that everyone downloads today. We wrote down
beforehand what would count as "it holds", then ran it. The newer map runs away exactly
like the old one: smell input locks the whole brain into non-stop firing every time, and
it is the same set of neurons. Our fix carries over unchanged: no runaways in hundreds of
trials, and the paper's sugar-feeding result is identical to the last spike. The same
handful of smell-centre cells is the way in. One small difference: taste input tips the
newer map about half as often, because it sits a little further from the edge.

## 2026-09-23 - Does the model's smell system respond like real fly recordings? Real receptor data for 110 odours, 8 pre-registered facts (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/` or `tests/`. New folder
`experiments/olfaction_realfly/` and write-up `docs/olfaction-vs-real-fly.md`. Real
receptor responses came from DoOR 2.0 (Muench & Galizia 2016; public GitHub
`ropensci/DoOR.data`, downloaded to `data/olfaction/door/`, not committed). The inputs are
Hallem & Carlson 2006's 24 receptors x 110 odours (spikes/s, 1:100) plus DoOR's merged
estimates for 23 more glomeruli. Receptors were mapped to FlyWire ORN types through DoOR's
mapping table and the snapshot-630 `hemibrain_type` labels. Coverage: 23 of 51 glomeruli
measured (1,117 of 2,271 ORNs, 49%). With the DoOR estimates, 46 glomeruli (88%). No
data: DA1, VC1, VC3m, VC5, VA7m. Every ORN fired Poisson spikes at its spontaneous rate +
odour response (untested types: 12 Hz, the median measured spontaneous rate). The
whole-brain model (630, fast engine) ran for 0.5 s trials. Eight real-fly facts and their
MATCH/PARTIAL/MISMATCH lines were written to `results/preregistration.md` before the main
runs; only a 3-odour speed test had been seen, and that is disclosed. Runs: recommended fix
`al_ln_literature`, 110 odours + no odour, 3 seeds x 4 trials; the same with both APL cells
silenced (3 x 2, trial-paired); DoOR-extended input (3 x 2); published model (`none`) with
and without spontaneous firing (2 x 0.3 s per odour); Olsen-2010-style single-glomerulus
curves with and without a "public" odour (4 glomeruli x 7 levels x 3 backgrounds, 3 x 4).
About 45 minutes of simulation in total.

**What happened.**
- Stability: recommended fix, 0 runaways in 1,332 trials (busiest 10 ms: 736 non-sensory
  neurons; threshold 1,500). Published model: all 110 odours run away in 220 of 220
  trials within 10-20 ms. So does spontaneous input alone, with no odour. About 67% of KCs
  fire. Stronger odours tip faster (rank correlation -0.77).
- F1 KC sparseness: 3.0% per odour (median 2.7%, max 6.7%) with the measured inputs;
  3.9% (max 12.9%) with the DoOR estimates. Real: ~5% (Honegger 2011), 6% (Turner 2008).
  PARTIAL (2.98% vs the 3% line) / MATCH.
- F2 PNs broader than ORNs: in 8 of 23 glomeruli (real 7 of 7); median lifetime sparseness
  0.57 PN vs 0.53 ORN. MISMATCH. The too-picky PNs are the weakly wired ones (rank
  correlation -0.52 with mV per ORN spike). The DA3 PNs never respond (0.56 mV per ORN spike).
- F3 transfer curve: saturating (gain 3-8x higher for weak input), but half-point 36-49 Hz
  vs 12-16 Hz in real DL5/DM4/VM7 (DM1 32 vs 45). PARTIAL.
- F4 lateral inhibition (pentyl acetate on the other glomeruli): 75-85% less PN response vs
  50-78% from Olsen 2010's equation. MATCH on size. The shape is subtractive, not
  divisive: weak input is pushed below rest (the public odour alone lowers DL5 PNs by 44 Hz).
- F5 PN responses vs the Olsen 2010 normalization equation fed the same data: r = 0.85
  (2,530 pairs; 0.68 without the normalization term). MATCH.
- F6 inter-odour correlation: ORN 0.21, uPN 0.54 (0.31 per measured glomerulus), KC 0.31.
  KCs are less alike than PNs but not less alike than the ORN input. PARTIAL.
- F7 APL silenced: KCs responding 3.0% -> 11.3% (110 of 110 odours denser), correlation
  0.30 -> 0.41. MATCH in direction (the real size is in figures only, UNVERIFIED).
- F8 spikes per responding KC: median 6.2 per 0.5 s (real "a few"). PARTIAL.
- Seeds: each seed alone gives KC 3.09/3.09/3.09%, F2 8/9/9 glomeruli, F5 r 0.85 each.

**Validated?** No: PRELIMINARY. Done: pre-registration; 3 seeds (they agree to within
0.01 percentage points on F1); a paired APL comparison on identical input spikes; the
runaway count excludes the driven ORNs, and the margin was checked; a bug in the F7 verdict
code (numpy booleans OR-ed instead of added) was caught and fixed before scoring. Sources:
full text via PMC for Honegger 2011, Bhandawat 2007, Olsen 2010 and Lin 2014 (Lin via a
summarising fetch). Abstract only: Turner 2008, Olsen & Wilson 2008. Not done: other
concentrations or odour datasets, an independent review, and a sugar -> MN9 re-run
(nothing in `sim/` changed). Weak points: one receptor dataset recorded in the "empty
neuron" system; constant-rate input; half the ORN types unmeasured; the F3/F4 real values
are an equation fitted to recordings.

**Plain English.** We gave the simulated fly the real responses of its smell sensors to
110 real odours, and checked its smell circuit against 8 things measured in real flies.
We decided beforehand what would count as a match. With the recommended fix, the big
picture is right. The brain stays calm, only about 3-4% of the memory-centre cells respond
to each smell (real flies about 5%), and the brake neuron APL keeps it that way, as in real
flies. The first relay station is off, though. Real flies boost weak smell signals there,
so their output cells respond to more smells than their sensors do. The model boosts them
too little (about 3 times less sensitive), so its output cells are pickier, and different
smells look more alike instead of less. The published model without the fix locks up
for every smell and even with no smell at all. Score: 3 match, 4 partly, 1 does not.

## 2026-09-23 - Does the simulation match a real fly? The first 10 scorecard tests, pre-registered, on the published model and the recommended fix (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or
`experiments/scorecard/`. New folder `experiments/scorecard_batch1/` and write-up
`docs/real-fly-scorecard-batch1.md`.
- The tests: the first batch of 10 recommended in `docs/real-fly-scorecard.md` (FC2, FC5,
  FC1, SD4, TH3, TH2 with TH1, OS4, LL1, SD1 with SD2, TF4), with the catalogue's cell IDs
  (`ids_630.csv`).
- Pre-registered before any simulation (doc section 1, 19:45): for each test, the
  stimulated, silenced and read cells; the input rate (the catalogue's, else 150 Hz); the
  expected result; and the MATCH/PARTIAL/MISMATCH lines.
- Model: whole-brain (snapshot 630, fast engine), 1 s trials, 3 seeds x 30 trials.
  - Versions: the published model (`none`) and the recommended fix (`al_ln_literature`).
    Test 7 also ran with the Phase 7 gap junctions.
  - Test 5 gave DN1a a steady 8 mV current as its background (10 mV check), because a
    Poisson-driven cell fires on every input spike in this engine and cannot be inhibited.
    A 1-seed Poisson run confirmed it: DN1a 23.1 Hz with and without cool input.
- Changes from the plan:
  - Seven published-model conditions that ran away in 30 of 30 trials of seed 0 got 1 seed.
    This was a time rule added at 20:28; it looks at runaway only.
  - Two restarts, with the same seeds.
  - Test 7 was re-run at 30 Hz post hoc and not scored.
- Run time: about 35 minutes of simulation after the last restart (730 + 1,061 + 336 s),
  plus the runs saved before it.

**What happened.**
- Score, published model: 2 MATCH, 3 PARTIAL, 5 MISMATCH.
- Score, recommended fix: 4 MATCH, 2 PARTIAL, 3 MISMATCH, 1 CAN'T TELL.
- Runaway:
  - Published model: every smell or temperature condition, in 30 of 30 trials (26 of its
    70 runs; one more run in 1 of 30 trials).
  - Fix: 0 of 100 runs.
- Results per test (published / fix):
  - 1 FC2, PARTIAL / PARTIAL: pC1a 80.6 Hz, pC1b 77.7, pC1c 73.6, pC1d 19.1, pC1e 4.8 (fly:
    pC1a strong, pC1b weak, c-e little or none). SAG sends pC1b 296 synapses vs 387 to
    pC1a.
  - 2 FC5, MISMATCH / MISMATCH: aSP-g 0/23, aSP-f 1/45 (published, in runaway) or 0/45,
    aSP-h 0/22 respond (fly: 11/15, 1/34, 2/8). The DA1 projection neurons send 63
    synapses to aSP-g and none to aSP-f or aSP-h.
  - 3 FC1, MATCH / MATCH: vpoDN 55.5 Hz (vpoEN), 104.6 (pC1), 123.9 (both). HIGH
    circularity.
  - 4 SD4, MATCH / MATCH: 100% of 90 trials per side turn toward the stimulated side (fly:
    about 92%).
  - 5 TH3, MISMATCH / MATCH:
    - Published: DN1a 22.0 -> 24.4 Hz with cool input (runaway).
    - Fix: DN1a 22.0 -> 0.0 Hz, and 21.1 with VP3+_vPN silenced.
    - The 10 mV check agrees.
  - 6 TH2, PARTIAL (1 seed) / MATCH: warm projection neurons -2.5% (runaway) / -34%
    (92.2 -> 61.0 Hz, through l2LN21 local neurons). Cool projection neurons respond in
    both.
  - 7 OS4, MISMATCH (1 seed) / CAN'T TELL:
    - Published: sister r 0.039 vs cross 0.024.
    - Fix: the DA1 projection neurons are silent at 10 Hz (and 30 Hz) background input,
      with or without gap junctions.
    - Odour side result (not scored): sister r 0.087 vs 0.004 (0.133 with gap junctions).
  - 8 LL1, MISMATCH (1 seed) / MISMATCH:
    - Fix: M4/6 8.9 -> 9.1 Hz; V2 silent.
    - Switching MVP2 on slows APL (141 -> 91 Hz), which releases MBON02 (30.4 -> 34.3 Hz).
  - 9 SD1, PARTIAL / PARTIAL: MDN 16.7 Hz with LC16 at 100 Hz, 0 at 50 Hz. One-sided:
    left 0 vs 0 Hz, right 2.9 vs 5.0 Hz. There is no direct path, and the main relay
    (LT51) is inhibitory.
  - 10 TF4, MISMATCH / MISMATCH: water/sugar rates are Usnea 90.7/77.5, Phantom 78.5/39.1
    (ratio 0.498) and Clavicle 43.2/39.9 Hz. The wiring gives Usnea 305 water vs 285 sugar
    synapses.
- Seeds agree to within about 1 Hz. Tests outside the antennal lobe give the same numbers
  in both versions (within 0.2 Hz).

**Validated?** No: PRELIMINARY.
- Done:
  - Pre-registration before any run.
  - 3 seeds (1 for seven published-model runaway conditions).
  - A no-input control per version (0 spikes).
  - Runaway recorded in every trial.
  - A verdict-code bug was caught and fixed before the write-up: a test 7 run with no
    scorable pairs had been marked MISMATCH; the pre-registered verdict is CAN'T TELL.
- Not done:
  - An independent review.
  - Full-text reading of the abstract-only sources (Wang 2021, Kazama & Wilson 2009,
    Sen 2017, Wu 2016).
  - Checking the aSP-f/g/h and TPN-II (= VP3+_vPN) cell matches.
  - Checking whether Shiu et al. 2024 already compared Usnea/Phantom/Clavicle.
  - Any causal test of the proposed reasons, except test 5's silencing.
- Weak points:
  - Circularity: HIGH for tests 1 and 3.
  - Cell matching from the catalogue.
  - Near-saturated firing under strong input in this engine, which flattens graded
    differences.

**Plain English.** We checked the simulated fly brain against ten things measured in real
flies. We decided beforehand what would count as a match. The published model gets 2 right,
3 partly right and 5 wrong. Most of the wrong ones happen because smell or temperature input
makes the whole brain lock up, a fault found earlier. With the recommended fix the lock-up
is gone. The model then gets 4 right, 2 partly right and 3 wrong, and 1 can't be scored. Two
temperature circuits now behave like the real ones. The three misses that remain are a
pheromone pathway, a memory-circuit output neuron, and taste cells that should tell water
from sugar. They look like wiring or missing-mechanism problems, not the lock-up. One of the
matches (test 3) is partly built in, because the paper found that connection in the same
kind of wiring map the model is made from.

## 2026-09-23 - Phase 9: the same-side release boost (Gaudry 2013) as a switch, and can the brain then steer the body toward cVA? (PARTIAL, PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or any existing doc. New, in
`experiments/phase9_sameside/`: `sameside.py`, an optional "release switch" that multiplies
every same-side smell-receptor-neuron (ORN) -> projection-neuron (PN) connection by 1.39.
Source: Gaudry, Hong, Kain, de Bivort & Wilson 2013, *Nature* 493:424 (PMC3590906),
Fig. 3e: same-side synaptic currents 39% larger than other-side ones (n = 15 pairs of DM6
PNs); abstract: "~40% more neurotransmitter" per spike from the same-side branch. Weights
are kept exact (counts x1024, weight per synapse /1024); switch off = the old model
(`build_brain("al_ln_literature")`), unchanged. Also a DIAGNOSTIC (not a realism claim)
"arm 2": the switch plus same-side x1.30 more (FlyWire's median same-side ratio 1.25 vs
about 1.63 in BANC, maleCNS and the hemibrain) and every glomerulus's left/right size
imbalance removed. Scripts: `check_switch.py` (identity, anatomy, Phase 3),
`open_loop_sameside.py` (brain-only screen), `pn_drive_check.py` (per-PN rates; PNs driven
directly), `run_sameside.py` (closed loop; conditions, seeds and measures imported
unchanged from `experiments/phase9_da1/run_da1.py`), `analyze_sameside.py`. Expectations
and the pass rule (reused from docs/phase9-da1-demo.md section 1) were written into
`docs/phase9-sameside.md` section 1 at 19:05, before any run.

**What happened.**
- Switch checks: at x1.0 the brain is the old one spike for spike (511,602 spikes, sugar
  200 Hz, 30 trials; DA1 windows identical). Arm 1 changes 11,570 ORN -> PN connections
  and nothing else (same-side synapse-equivalents 99,296 -> 138,020). Glomeruli in which
  each PN gets more from its own side's ORNs: 32 of 51 -> 42 (arm 2: 50). Phase 3 sugar
  -> MN9 with the switch on is unchanged to the last spike (67.28 Hz at 100 Hz sugar,
  93.53 at 200 Hz; water 30.79, bitter 0.00, sugar + bitter 1.36).
- Brain-only screen (3 seeds x 2 s): for a DA1 (cVA) source 5 mm to the RIGHT, DNa02 still
  says "turn left" in every variant (+15.2 to +19.3 Hz); one antenna is answered
  correctly in every variant. With the diagnostic map the left and right DA1 PNs fire
  126.9 vs 129.9 Hz per neuron at equal smell, yet DNa02 still leans left. Driving the
  DA1 PNs directly also gives a left lean (+2.5 Hz at equal drive, +11.7 Hz with the
  RIGHT PNs driven 50% harder), and the relay DNae007 stays silent. So the lean is not
  in the ORN -> PN map; it arises after or beside the DA1 PNs (not traced).
- Closed loop, arm 1, normal fly (15 trials): left turn in 15 of 15 (sign test
  p = 0.00006); toward the source in 6 of 12, +12.4° vs 0° for each silenced control
  (Mann-Whitney p = 1.0; paired Wilcoxon p = 0.38); closest approach 4.14 vs 4.22 mm
  (p = 1.0). Switch off gave +12.7° and 4.12 mm (p = 0.93, 0.97).
- Arm 1, one antenna (12): toward the smelling side 11 of 12 raw, 12 of 12 against the
  same-seed control; +34.0° vs 0° (p = 0.0006 vs DA1 silenced and vs DNa02 silenced;
  paired p = 0.0005); left antenna +47.6°, right +20.4° (switch off +43.1° / +19.0°);
  closest approach 5.82 vs 5.92 mm (p = 0.93).
- Arm 2 (DIAGNOSTIC), normal fly (15): left in 15 of 15 (p = 0.00006); toward 6 of 12,
  +8.8° (p = 1.0); closest 4.14 vs 4.22 mm (p = 0.97).
- Arm 2 (DIAGNOSTIC), one antenna, cVA (12): toward the smelling side 12 of 12 raw and
  paired, +43.3° vs 0° (p = 0.00006; paired p = 0.0005); left +58.4°, right +28.2°
  (not different from switch off: p = 0.39, 0.52); closest approach 5.68 vs 5.92 mm
  (p = 0.87).
- DM1 (vinegar): arm 1 failed the pre-registered brain-only rule (right antenna alone
  said "left" in 2 of 3 seeds, +2.8 Hz), so no pre-registered closed loop. Arm 2
  mirrored (+26.7 / -10.3 Hz), so a one-antenna DM1 run was added after the screen as a
  DIAGNOSTIC (12 trials): toward the smelling side 10 of 12 raw, 11 of 12 paired,
  +42.0° vs 0° (p = 0.002; paired p = 0.001); left +59.8°, right +24.2°; closest
  approach 5.34 vs 5.92 mm (p = 0.33).
- Arm 1 with the DNpe002 read-out (direction assumed), normal fly (15): left in 12 of 15
  (p = 0.035); toward the source 7 of 12, +0.3° vs 0° (p = 0.66; paired p = 0.97);
  closest approach 4.25 vs 4.22 mm (p = 0.98). Switch off: +2.1° (p = 0.67).
- Controls: all 69 control trials (DA1 smell neurons silenced, DNa02 silenced, no odor;
  both arenas) were re-run with the switch on. Each walked exactly its phase9_da1 twin's
  path (0.0 mm apart), with the straight drive in every window.
- Verdicts against the pre-registered rule: arm 1 PARTIAL (PRELIMINARY), the same as
  with the switch off; arm 2 (DIAGNOSTIC) also PARTIAL by the rule, and NOT PASSED for
  a normal fly. All five pre-registered predictions came true.

**Validated?** No: PRELIMINARY. Done: pre-registration before any run; the identity
check (x1.0 = old model spike for spike); the Phase 3 re-check (identical); 3 seeds per
condition; re-run controls compared with their phase9_da1 twins (identical paths); our
glomerulus table matches the banc_asymmetry lane's in 50 of 51 glomeruli. A screen error
was caught by a per-neuron check and corrected before writing: one weakly wired right
PN (M_lvPNm44) had lowered the right-side group mean. Source: Gaudry et al. 2013 read
through an automated extract of the PMC full text (Fig. 3e legend and results). Not
done: other factors or a factor per glomerulus, tracing the connections that carry the
left lean, parameter variations in the closed loop. Weak points: 3 seeds; a factor measured in DM6 applied to every
glomerulus; possible double counting (part of the 39% may already be in FlyWire's
synapse counts); a smell-to-firing curve not fitted to cVA or vinegar neurons.

**Plain English.** We added a real effect that a wiring diagram cannot show. In a real
fly, each smell-sensor spike releases about 40% more transmitter on its own side of the
brain. It is an on/off switch: off gives exactly the old model, and it leaves the earlier
sugar test exactly as it was. It did not help the fly steer. With both antennae smelling,
the simulated fly still circles left whichever side the smell is on, just as before.
Even a hand-made version with a perfectly balanced first smell station still circles
left; that version is a diagnostic, not a claim. The left lean comes from further along
the smell pathway, so fixing the first relay does not fix it. What still works, with or
without the switch, is the lab test: a fly with one antenna covered turns toward the
side that can smell. With the balanced map that also works for a vinegar smell. In
neither case does the fly get closer to the smell.

## 2026-09-23 - Hybrid computer roadmap: what exists, what an individual can use, and a virtual hybrid computer to build first (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or any existing
doc. New: a staged plan (a design note kept outside this repo) for the end goal of a hybrid computer
(neuromorphic silicon plus living neurons), and this entry. Research only: no runs, no
purchases, no sign-ups and no contact with anyone. Every source was checked on
2026-09-23, and every price carries that date.

**What happened.**
- **The fly brain already runs on neuromorphic silicon.** Sandia put the whole FlyWire
  brain (139,255 neurons) on 12 Loihi 2 chips. It ran at 12.40 ms per simulated second
  with 1 ms steps, against 4,419 ms on a CPU (about 356 times faster). With dense
  activity the gain fell to about 2.4 times. This is an arXiv preprint (2508.16792,
  2025-08-22), and it reports no power. Weights were cut to 9 bits (0.007% capped).
- **Energy gap.** A whole fly brain uses about 256 nW (Panda et al. 2026). That is
  about 2 pW per neuron, against about 1 µW per neuron slot on Loihi 2 and about 30 µW
  per neuron for a CL1 box (about 25 W for about 800,000 neurons, including life
  support).
- **Electrode bottleneck.** A CL1 reads about 800,000 neurons through 59 electrodes,
  about 13,600 neurons per electrode. DishBrain's loop took about 5 ms. Between US West
  datacentres and Melbourne or Zurich, a round trip takes 138 to 173 ms, about 14 to 17
  times DishBrain's 10 ms tick.
- **What an individual can buy.** A SparkFun Pro Micro RP2350 ($16.95) with a Nordic
  PPK2 power meter ($99.95). A published test ran 186 spiking neurons in real time on
  that chip, under 20 mW. FPGA boards cost $36 to $80. The BrainChip Akida M.2 card is
  $249 on DigiKey, but it runs CNN-style models only. SynSense Xylo and Speck and
  Innatera Pulsar kits have no public price. Loihi 2, SpiNNaker2 and EBRAINS need an
  institution. Lava was archived on 2026-05-13.
- **Living neurons.** No cell culture outside a lab: biosafety rules put even BSL-1
  human or animal cells in a supervised lab. Cortical Labs' CL API simulator is free. News
  reports put Cortical Cloud at $300 a week. Whether individuals can use it, or
  FinalSpark, is unconfirmed.
- **Virtual hybrid computer (new Stage 1b, section 6).** It has four parts: a digital
  core for exact work, neuromorphic cores for sensing, recognition, learning and fly
  circuits, an optional simulated living module, and the links between them. Time and
  energy are modeled by counting operations and pricing each one at published per-part
  costs, the way gem5, Accel-Sim and SANA-FE work. SANA-FE's first version matched
  Loihi within mean errors of 9.7% (energy) and 13.4% (latency). SST has no spiking
  component (it added "golem", for in-memory computing). A 10-task benchmark suite
  names a predicted winner for each task. Every result is labelled measured, modeled or
  knob-dependent. Cloud GPU prices seen: $0.526 to $6.99 an hour.
- **Next step.** Find the smallest piece of the fly circuit that keeps MN9 at about
  67 Hz. If it is about 1,000 neurons or fewer, buy the RP2350 and the PPK2 (about
  $117). That piece also becomes the virtual computer's first neuromorphic core.

**Validated?** No: PRELIMINARY literature review. Several prices come from secondary
sources: CNX Software for the AKD1500, news reports for Cortical Cloud, and Vantage for
AWS. The Sandia result is not peer reviewed. The energy-per-neuron figures are
order-of-magnitude arithmetic. Every number in the virtual computer is modeled until
Stages 2 and 3 measure hardware. Its living module rests on guessed settings. Section 8
of the plan lists what could not be confirmed.

**Plain English.** We wrote a realistic plan for the hybrid computer. Chips that work
like brains are real, and one already runs our whole fly brain much faster than a
normal computer. What an individual can actually use is cheap microcontroller and
FPGA boards, not the big research chips. Living neurons can only be reached through a lab or a paid remote
service, and today they are read through a few dozen to a few thousand wires. First,
we will build the whole hybrid computer in software, with every part's speed and
energy taken from real chips, and test it against normal CPUs and GPUs. After that
comes a $17 chip and a $100 power meter.

## 2026-09-23 - Energy budget: one decision costs a fly nanojoules, a Loihi-class chip millijoules, this laptop joules (PRELIMINARY)

**What was changed.** New lane `experiments/energy_budget/` and write-up
`docs/energy-budget.md`. Nothing under `sim/`, `app/`, `tests/` or `data/` was edited.

- **Decisions run.** Eight one-second decisions on both the published model ("none") and
  the recommended fix ("al_ln_literature"): sugar, bitter, water, smell DA1, smell DM1,
  grooming (JO-C/E), cool and warm. Each got 2 seeds x 20 trials, one thread. Stimulus
  lists and rates were reused from `phase7_signs`, `scorecard_batch1` and `heldout`.
- **Counted per trial:**
  - spikes;
  - neurons that fired, and neurons touched (got any input);
  - synaptic events, two ways: spikes x output synapses, and spikes x output connections;
  - MN9 and aBN1 onset;
  - wall time and CPU time.
- **Laptop power.** The CPU package power (Windows' RAPL "Energy Meter" counter) was
  logged every second during every run.
- **Energy estimated three ways, each as low / middle / high:**
  - fly: ATP per spike and per synaptic event, from Sengupta 2010 and Attwell & Laughlin
    2001, with hemibrain partners per release site;
  - Loihi (Davies 2018) and Loihi 2 upper bounds derived from Hala Point, plus TrueNorth,
    SpiNNaker and GPU figures for comparison;
  - this laptop: measured time x power.
- **Sandia (arXiv:2508.16792) checked** against its own text.
- **Scripts:** `run_decisions.py`, `validate.py`, `timing.py`, `analyze.py`, and
  `constants.py`, where every constant carries its source.

**What happened.**

*Decisions on the fixed model:*

- 87-1,127 neurons fire, 0.07-0.9% of the brain.
- 6,400-36,400 spikes per decision.
- Energy per decision, middle estimates:

  | Platform | Energy per decision | Ratio |
  |---|---|---|
  | Fly | 4-47 nJ | widest range 1.2-690 nJ |
  | Loihi-class chip | about 6.6-6.9 mJ | 150,000-1.6 million x the fly |
  | This laptop | 1.4-19 J | a further 200-2,800 x the chip |

*The published model's runaway (DA1, DM1, cool, warm):*

- About 8,200 neurons fire, 440,000-470,000 spikes.
- Compared with the fix, that is 13-64x the spikes and 10-60x the fly's energy.
- It needs about 1.9x the measured power of a whole living fly brain (256 nW, Panda et
  al. 2026), so a real fly could not sustain it.
- On a Loihi-class chip it costs only 1.4x more. On the laptop it takes 2-8x longer.

*Why the chip costs what it does:*

- In the Loihi-style estimate, 99.6-99.97% of the chip's energy is spent updating every
  neuron at every step.
- A fully event-driven design would need 3,300-38,000x less work than a dense
  every-step design. That is 60-720x less than Loihi-style.

*Other read-outs:*

- MN9 first spike after sugar onset: median 41 ms. aBN1 during grooming: 73 Hz, onset
  14 ms.
- Sandia put FlyWire on 12 Loihi 2 chips. Speed per simulated second of sugar: 54 ms at
  0.1 ms steps, 12 ms at 1 ms steps. They measured no power.
- No single chip of any kind holds the whole brain.

**Validated?** No: PRELIMINARY.

*Done:*

- Two seeds agree within 2%.
- No input gives 0 spikes on both models.
- Same seed gives the same spikes: 48/48 re-run trials match.
- Output synapse counts recomputed independently from the connection file are
  identical (52,793,639 synapses).
- The fix changes exactly 137 ALLN outputs.
- Weight per synapse at 80% and 120%: fly energy moves x0.51-x1.33, and the fix never
  runs away.
- Every literature constant was swept low to high: the synaptic-event cost dominates,
  at x0.5-x11.
- Sandia's sugar run had 0.3% of neurons active, against our 0.28%.

*Not done:*

- No independent review.
- No Loihi 2 per-operation energy is published, so upper bounds derived from Hala Point
  stand in.
- A second "8 nJ" SpiNNaker figure and a whole-brain oxygen-use figure could not be
  confirmed, and were left out.

*Weak points:*

- The membrane area a spike charges is our assumption.
- The fly's synaptic-event cost is uncertain by about 30x and uses mammalian vesicle
  numbers.
- Chip figures leave out idle power.
- Laptop timings were slowed by other lanes (package power about 12 W throughout;
  identical work up to 2.5x slower).
- The model has no background activity, no glia, no nerve cord and no graded
  (non-spiking) neurons.

**Plain English.** A fly's brain makes a taste or smell decision for a few billionths of
a joule. Intel's neuromorphic chip would spend about a million times more, almost all of
it keeping every silent neuron ticking. This laptop spends another few hundred to few
thousand times more than that. The published model's smell runaway would need nearly
twice the power a real fly brain has, which is more evidence that it is a model fault.
The lesson for the hybrid computer: fly activity is extremely sparse, so hardware that
spends nothing on idle neurons is where the big savings are.

## 2026-09-23 - The smallest circuit that still makes the feeding decision: 36 neurons, fits a $17 RP2350 board (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or `data/`. New:
`experiments/minimal_circuit/` (scripts and results) and `docs/minimal-circuit.md`.
Model: snapshot 630 with the `al_ln_literature` fix, fast engine, MN9 =
720575940660219265. The pass rule was written into the doc at 22:19, before any pruned
circuit was run, and was not changed. A circuit passes if, run on its own
(`FastBrain.from_arrays`), MN9 at sugar 100 Hz and 200 Hz is within 10% of the whole
brain; water (100 and 200 Hz) is weaker than sugar at the same rate; bitter alone
(100 and 200 Hz) gives MN9 below 0.5 Hz; and bitter 100 Hz added to sugar 100 Hz lowers
MN9 by at least half the whole brain's drop. The final verdict used 3 held-out seeds
(0, 1, 2) x 30 trials. The search used seed 7 (10 trials) and a stricter version
(7.5%, zero bitter spikes, brake 0.6). About 47 minutes of compute, one process,
1 thread.

**What happened.**
- **Whole brain (30 trials, seeds 0/1/2):** sugar 100 Hz 67.6/67.3/66.2 Hz, sugar
  200 Hz 92.9/93.3/93.8, water 200 Hz 31.0/30.8/30.3, water 100 Hz and bitter alone 0,
  sugar + bitter 4.4/3.6/4.9.
- **Lossless starting cuts.** The 21,461 neurons that received any input, and then the
  642 that fired and sit on a taste-to-MN9 route, reproduce the whole brain exactly
  (0.00% error).
- **Strongest-path pruning** (widest path; strength = presynaptic rate x synapses):
  600, 500 and 400 neurons pass. 300 misses the stricter search test (9.8%), 200 is off
  by 14.7%, 80 loses the bitter brake (0.17), 40 leaves MN9 silent.
- **Greedy pruning** (neuron blocks 100 down to 2, connection blocks, then one at a time
  until a full round removed nothing): 400 -> 249 -> 120 -> 69 -> 53 -> 51 -> 41 -> **36
  neurons, 110 connections, 6,463 synapses**. 2,167 candidates were tested.
- **Held-out check of the 36-neuron circuit: passes on all 3 seeds.** Sugar 100 Hz
  63.7/62.1/61.0 vs 67.6/67.3/66.2 (-5.8% to -7.9%). Sugar 200 Hz 100.1/100.0/98.8 vs
  92.9/93.3/93.8 (+5.3% to +7.7%). Brake 0.61/0.58/0.61. Bitter alone 0. Water 0 (whole
  brain 31 Hz at 200 Hz; the rule did not require water).
- **Contents:** 9 sugar and 3 bitter taste neurons, MN9, and 23 relay neurons: G2N-1,
  Zorro, FMIn, Roundup (both), Rattle, Clavicle, Rounddown (both), Roundtree, Sternum,
  DNge062, Scapula (CB0219, glutamate, the bitter brake), DNge031 (GABA), CB0277, CB0824,
  CB0872, CB0393, CB0855, CB0177, DNge059 (both) and one unlabelled ascending neuron.
  6 of the paper's 10 named sugar-pathway types are kept (not Phantom, Usnea, Bract or
  Fdg). The strongest route (sugar -> G2N-1 -> Roundup -> MN9) is intact, as are 6 of
  Phase 5's 20 strongest excitatory routes.
- **Weights +/-20% (seed 0): the 36-neuron circuit fails.** At -20% sugar 100 Hz gives
  0.3 vs 36.6 Hz. At +20% it gives 120.2 vs 79.7. Every checkpoint from 249 neurons down
  fails this test. The 400-neuron strongest-path circuit passes it (errors under 3.5%,
  brake 0.93 to 1.00), passes all 3 held-out seeds and keeps water (30 to 32 Hz).
- **RP2350 arithmetic** (2 x Cortex-M33 at 150 MHz, 520 KB SRAM; Raspberry Pi product
  page, checked 2026-09-23). 36 neurons: 3.5 KB with 16-bit weights. Worst case (sugar
  200 Hz): 360,000 neuron updates, 120,000 random draws and 11,943 synaptic events per
  simulated second at 0.1 ms steps, about 10.6 M cycles = 7% of one core (clock-driven),
  or about 0.5 M cycles = 0.3% (event-driven). Cycle costs are assumed (25 per update,
  12 per draw, 10 per event). 400 neurons: 108 KB, about 77% of one core (clock-driven),
  20% event-driven. 642 neurons: 181 KB, about 119% (needs both cores). Whole brain:
  about 88 MB, 170 times the SRAM.
- **Weight precision (36 neurons, seed 0):** 16-bit exact passes. 8-bit clipped at 127
  fails (sugar 100 Hz 19.9 Hz). 8-bit rescaled (max 561 -> 127) just fails (-10.3%).

**Validated?** No: PRELIMINARY. Done: 3 held-out seeds, +/-20% weights, lossless-cut
exactness as a bug check, comparison with the named pathway, chip specs from the maker.
Not done: other removal orders (36 is a local minimum, not proven smallest), a search
that includes +/-20% or water in the rule, 32-bit arithmetic, anything on real hardware,
and a literature search for other minimal feeding circuits. The held-out margins are
thin (up to 7.9% against 10%), and the circuit's brake is about 60% of the whole
brain's (sugar + bitter gives about 24 Hz instead of about 4 Hz). This is a reduction of
the model, which already disagrees with real flies on Roundup and Fdg.

**Plain English.** Out of 127,400 neurons, 36 are enough to reproduce the model's feeding
decision: sugar drives the feeding motor neuron at the right rate, bitter alone does
nothing, and bitter still holds sugar back. That circuit needs about 3.5 KB of memory
and a few percent of one core on the $17 RP2350 board, so it fits with lots of room.
The catch is that it is fragile: make every connection 20% stronger or weaker and it
drifts far from the full brain, and it ignores water. A 400-neuron version has none of
those problems and still fits the chip's memory, but may need both cores to keep up in
real time.

## 2026-09-23 - Mushroom body as a continual learner: it barely forgets, but the real PN->KC wiring loses to random wiring (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or `data/`. New:
`experiments/mb_continual/` (scripts and results) and `docs/mb-continual-learning.md`.
This is a fast rate model, not the spiking engine. Glomerulus -> KC synapse counts come
from snapshot 630 via Phase 8's `circuit_630.npz` (uniglomerular ALPNs, 95.5% of PN -> KC
synapses): 2,397 KCs on the left and 2,423 on the right, 55 glomeruli, about 5.2 inputs
per KC. Each half was modelled separately. Odours: the 110 Hallem & Carlson odours (smell
lane set A + DoOR set B, Olsen 2010 transform), with Poisson noise in a 0.05 s window,
fixed by a pilot on seed 999. APL = keep the top 5% of KCs. There is one output per
class, and the learning rule is Shen et al.'s local "always add" rule. Controls, drawn
fresh per seed, keep each KC's in-degree and synapse counts: (a) shuffled (real
glomerulus frequencies), (b) uniform. The MLP has the same hidden size and uses Adam,
taught step by step and all at once. The pass rule (WIN only if "higher" by 2 SE,
paired and unpaired, in all 4 half x control comparisons; LOSE if "lower" in both halves
for either control) was frozen in `results/preregistration.md` at 21:58, before any
learning run on the real or shuffled wiring. It was not changed afterwards. There were
20 fly seeds and 10 MLP seeds. Runs took from about 22:00 to 23:35.

**What happened.**
- **Primary (110 odours, 10 tasks of 11): REAL WIRING LOSES.** Final accuracy, left /
  right: real 57.5 / 58.9%, shuffled 64.4 / 64.0%, uniform 66.8 / 66.8%. The real wiring
  is lower by 5.0 to 9.2 points (9.6 to 22.9 paired SE).
- **Question 1:** the MLP taught step by step ends at 14.5 / 15.3%, with memory loss
  0.94 / 0.93. The fly (real wiring) has memory loss 0.12, so it ends more accurate and
  forgets less (clear in both halves). The MLP taught all at once reaches 93.2%. The fly
  rule only adds, so its step-by-step and all-at-once results are identical.
- **Cost per example:** the fly changes 120 synapses (5% of KCs active). The MLP changes
  about 114,600 (step by step, 27% active) or 275,800 (all at once, 73% active) of its
  400,170 weights.
- **11 pre-registered variants:** sparseness 2 / 3 / 7.5 / 10%, windows 0.02 / 0.1 / 0.2 /
  0.5 s, 5+ synapses only, per-KC-normalised input, and set A only. All are LOSES. The
  real wiring is lower in all 4 comparisons in 11 of 12 settings. The exception is
  per-KC-normalised input, where the left real wiring beats shuffled (+3.8 points).
- **Capacity (good/bad):** fly 6.5 to 7.9 odours before error passes 10%, 34-36% error at
  110 odours. MLP all at once about 95 (10.5% error at 110); MLP 10 odours at a time
  about 17. Real vs random: no clear difference. Post hoc: a 0.5 s window gives 8-10
  odours, and an error-driven local rule gives 14.5-19.5 odours with about 44 synapse
  changes per example. Neither shows a clear real-vs-random difference.
- **Odour groups:** the real wiring is lower in 34 of 40 chemical-class comparisons. Fruit
  odours lose less than the rest in the left half only (2.4 to 2.9 points). Exposure to
  the core community, pre-registered and post hoc, does not correlate with the loss
  (Spearman -0.14 to +0.02). The pre-registered core community turned out to be DA4m,
  VL1 and three thermo/hygro channels.
- **MNIST (5 tasks of 2 digits, fixed 784 -> 55 projection; 5 fly and 3 MLP seeds):** fly
  real 72.1 / 71.3%, shuffled 72.6 / 73.0%, uniform 74.3 / 73.8% (LOSES by 0.5 to 2.5
  points). MLP step by step 19.2%, all at once 92%. Shen et al. report FlyModel 0.86 and
  a plain network 0.19 on MNIST-20, with better features.
- **Post-hoc diagnostics:** the structure is real. There are 89 (left) and 56 (right)
  over-shared glomerulus pairs above z = 3, against about 6 expected, and the halves agree
  (rho 0.70). The loss is not caused by the non-odour channels or by KC subtypes. The
  edge-swap control recovers about half of the left-half gap. With self-balancing KCs,
  the gap shrinks to 1-2 points.

**Validated?** No: PRELIMINARY. Done: PLAN.md Phase 6 steps 1-5 (step 6, sharing,
skipped); 20 seeds; 11 variants; a recount of the wiring matrix for 100 of 100 KCs;
control invariants asserted; the diagnostics reproduce the main run exactly (120 of 120
runs); a literature check (Shen, Zheng, Caron, Dasgupta). Not done: the spiking engine,
more than one fly, real odour mixtures or concentrations, and continual-learning tricks
for the MLP (replay, EWC). Weak points: the size of the gap depends on the KC input
model, which the connectome does not fix (1 to 9 points). 47-95% of DoOR values are
missing for 23 glomeruli. Capacity mostly measures a noise floor, because the error is
already 10-13% at 5 odours. The brief's "Shen et al. 2021 PNAS" does not exist: the paper
is an arXiv preprint (2021) and a Neural Computation paper (2023). Zheng et al.'s exact
community list sits in a figure, so it was not checked. The main run's MLP part ran
alongside the variant queue, so at times two processes ran at once. Each started only
with at least 1.5 GB of RAM free.

**Plain English.** The mushroom body is a good pattern for a machine that has to keep
learning. It stores each new smell by strengthening a few synapses from the few cells
that smell switches on, so it almost never overwrites old memories. It does this with
about a thousandth of the changes a normal neural network makes. The price is accuracy:
it gets about 58% of 110 noisy odours right, where a normal network taught everything at
once gets 93%. The fly's actual wiring did worse than random wiring with the same
statistics, by 5 to 9 points, in every setting we tried. So copy the design, not the
exact wiring diagram. The real wiring does have structure, but that structure is not
for this test.

## 2026-09-23 - Reservoir computing: does the fly's whole wiring diagram compute better than random wiring? (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or `data/`. New folder
`experiments/reservoir/` and write-up `docs/connectome-reservoir.md`.
- The test: the whole-brain signed matrix (snapshot 630) used as a fixed
  "reservoir".
  - Built exactly as the fast engine builds its connection list; 300 neurons
    were checked against `build_brain`.
  - Recommended fix (`al_ln_literature`): 127,400 neurons, 14,635,639
    connections.
  - Rate model: x(t) = (1-a) x(t-1) + a tanh(rho W x(t-1) + W_in u(t)).
  - Every network divided by its own spectral radius.
  - Input: one random number per step (between 0 and 0.5) into all 9,145
    sensory neurons, with weights of ±1.
  - Only a ridge readout is trained. The settings are chosen on validation
    data and the scores are taken on test data.
- Controls, 3 seeds each: a degree-preserving shuffle (target column
  permuted), and Erdős-Rényi with the same edge count and weight values.
- Grid: rho 0.5-1.5 (8 values) x leak 0.3 or 1.
- Tasks: memory capacity (delays 0-100), NARMA-10, and delayed XOR.
- Readouts:
  - all 1,299 descending neurons;
  - 10 / 30 / 100 / 300 / 1,000 / 3,000 random non-sensory neurons;
  - each clean and with read noise (SD 0.01).
- Pre-registered pass rule, written before any comparison run (doc, 21:45):
  real wins a task only if, at each network's own best setting, it beats both
  controls by more than the larger seed-to-seed range.
- Changes from the plan:
  - The timeline was cut from 3,000 to 2,200 steps before the main run, for
    compute.
  - The published matrix got seed 0 only.
  - The spiking check was not done.
- Added after the main run:
  - The two seed-1 controls were re-run without self-connections.
  - An exploratory "same divisor" run of the real network (seed 0).
  - An exploratory high-gain run (rho 2-10) of the real and shuffled
    networks, main readouts only.
- Run time: about 1 h 40 min of sweep (other lanes made it 2-4x slower than
  timed), plus about 30 min of follow-up runs and checks.

**What happened.**
- Pass rule: FAIL, with 0 wins, 4 losses and 2 ties.

  | | Real | Shuffled | Erdős-Rényi |
  |---|---|---|---|
  | Memory, descending neurons | 17.9 | 22.4 | 48.0 |
  | Memory, 1,000 random | 16.3 | 22.3 | 46.0 |
  | NARMA-10 error, descending | 0.45 | 0.27 | 0.26 |
  | NARMA-10 error, 1,000 random | 0.47 | 0.29 | 0.26 |
  | XOR, descending | 91.5% | 91.7% | 91.6% |
  | XOR, 1,000 random | 90.6% | 91.5% | 91.9% |

  - Memory and NARMA-10 are LOSE; XOR is a TIE.
  - A plain delay line of the last 30-100 inputs gets NARMA 0.37-0.38, so the
    real wiring is worse than no network on NARMA.
- Electrode bottleneck:
  - At 10 read neurons the networks are close (memory 7.8 / 9.6 / 8.7).
  - The real wiring saturates by about 100 neurons (14.5 of 17.2).
  - With read noise 0.01 it collapses: memory 1.5 and XOR 52%. The shuffle
    keeps memory 9.0; Erdős-Rényi keeps 40.9 and 69% on XOR.
- Why:
  - The real matrix's spectral radius (1,954, against 306-373 shuffled and
    96-100 Erdős-Rényi) is set by a mode on about 8 mutually inhibitory
    lobula-plate cells (LPi21, DCH, VCH, HSE, H2; 500-760 synapses each way).
  - After scaling, a typical real neuron swings by only 0.0002, and just 3%
    of neurons swing more than the noise.
- The published matrix's top mode (+2,139) is the lLN1_bc antennal-lobe loop
  behind the Phase 6 runaway. The spectral analysis finds it without any
  simulation.
- Published matrix, seed 0: memory 15.5 / 15.2, NARMA 0.38, XOR 89-91%. No
  wins.
- Control flaw found:
  - Random rewiring made a few self-connections. In seed 1 of both controls,
    one of them set the radius (ER -177, shuffle +335), making those controls
    too quiet.
  - Re-run without them: still 0 wins, 4 losses and 2 ties. Erdős-Rényi
    memory rises to about 60 and NARMA falls to 0.22.
- Exploratory, not pre-registered:
  - Same divisor (real matrix divided by the Erdős-Rényi radius, 96, seed 0):
    loud but input-blind. Memory 1.7-2.9, NARMA 1.0-1.3, XOR 51-54% (chance).
  - Higher gain, rho 2-10 (real and shuffled, 3 seeds each): the real wiring
    peaks at rho 1.5-2 and then declines. With best settings re-picked over
    rho 0.5-10, it still has 0 wins, 4 losses and 2 ties
    (`verdicts_extended.csv`).

**Validated?** No: PRELIMINARY.
- Done:
  - Pre-registration before any comparison run.
  - 3 seeds per network.
  - Settings chosen on validation data and scores taken on test data.
  - Matrix checked against the engine.
  - Fast kernel checked against a plain one (3e-7).
  - Task code checked with no-network baselines (a K-step memory gives memory
    capacity K; linear XOR sits at chance).
  - Literature check.
  - Self-connection flaw re-run.
  - Gain range extended to rho 10 for the real and shuffled networks.
- Not done:
  - Spiking-engine check.
  - Published matrix seeds 1-2.
  - Other input scalings and noise levels.
  - Other ways of scaling the matrix (for example, taming only the hot loop).
  - Independent review.
- Weak points:
  - The verdict depends on the standard spectral-radius scaling, which is
    dominated by a few super-connected cells.
  - Rate units, not spikes.
  - An artificial input.
  - Only 1,000 training steps.

**New or reproduction?** Partly both.
- Already done:
  - The whole FlyWire connectome has been used as a reservoir against an
    Erdős-Rényi control (Costi et al. 2025, *Biomimetics*), with mixed
    results.
  - conn2res (Suárez et al. 2024) found no significant advantage for a
    FlyCircuit fly network over degree-preserving nulls (p = 0.11).
- Not seen in the sources we reached: the neuron-level degree-preserving
  control, the descending-neuron readout, the electrode and noise sweep, and
  the localized-mode explanation.

**Plain English.**
- We used the fly's whole wiring diagram as a fixed circuit and trained only
  a simple readout on it, the way a living-neuron computer would be used.
- The real wiring did not beat random wiring of the same size. It remembered
  less, did worse on a standard prediction task, and matched it on a logic
  task.
- The reason is that a handful of optic-lobe cells are wired to each other
  so strongly that, once the network is scaled to be stable, everything else
  is almost silent.
- That silence makes the real wiring very hard to read with noisy
  electrodes.
- So copying the fly's wiring as-is is not a shortcut to a better reservoir.
  Whatever the fly's wiring is good for, it is not this generic job.

## 2026-09-23 - The recommended fix (`al_ln_literature`) is now the project default; the published model stays one click away (VALIDATED for the code change)

**What was changed.** The author approved this on 2026-09-23. `FastBrain` is unchanged: it still
loads the published weights as they are.
- `sim/sign_fixes.py`: `build_brain(fix=RECOMMENDED_FIX, ...)`. It used to default to `"none"`.
- `sim/realism.py`: `build_realistic_brain(fix=RECOMMENDED_FIX, ...)`, imported from
  `sim.sign_fixes`.
- `app/engine_adapter.py`:
  - new `DEFAULT_FIX = "al_ln_literature"`.
  - new `EngineAdapter.default_variant(snapshot)`, which returns the model and, when it is
    not the fix, the reason.
  - `models_status()` now also returns `default_fix` and `defaults` (one entry per map).
  - the fix's label is now "Recommended neurotransmitter fix (default)". The published
    model keeps its label, "Published model (Shiu et al. 2024)".
  - `warm_up()` builds each map's default model.
- `app/main.py`: when `/api/models/state` gets no `fix`, it uses the map's default and
  returns `fallback` (the reason, or null).
- `app/__main__.py`: the start-up printout names the model built for each map and prints
  the 783 note.
- `app/static/app.js`, `index.html`, `app.css`:
  - the page opens on the server's default.
  - new yellow note `#modelNote`.
  - drafts are now version 3. An older draft that only held the old default (published
    model, no upgrades) opens on the new default. Any other saved choice is kept.
- Tests:
  - `tests/test_app.py`: 3 calls that relied on the old default now pass `fix=none`.
    Assertions unchanged. New test for the default and the 783 fallback.
  - `tests/test_sign_fixes.py`: new test that both builders default to `RECOMMENDED_FIX`.
- Docs: `docs/phase4-app-explained.md` (3 lines), `docs/phase7-neurotransmitter-audit.md`
  (1 line).

**Snapshot 783.**
- `sim/` builds the fix for 630 only. The 783 port lives in `experiments/runaway_783/`
  (`common783.py`) and is not part of `sim/`.
- So on 783 the app falls back to the published model and says so in the yellow note:
  "the recommended fix is built into the simulator (sim/) for brain map 630 only ... so on
  map 783 the app runs the published model."
- Switching back to 630 restores the fix and hides the note.
- If a request to the API asks for the fix on 783 by name, the app still refuses and gives
  the reason. It never swaps models without saying so.
- If the fix cannot be built at all (for example, `sim/sign_fixes.py` fails to import), the
  page opens on the published model and gives the reason, in the same way.

**What stays on the paper's model.**
- The Phase 3 scripts and the paper-comparison tests (`test_fast_engine.py`,
  `test_shiu_model.py`) build `FastBrain` or `shiu_model` directly, never `build_brain`, so
  they are unaffected.
- Every existing `build_brain` / `build_realistic_brain` call in `experiments/` and `tests/`
  already passed a fix explicitly (checked with grep).
- A run request or saved setup with no `variant` is still the published model. That is how
  setups saved before model choices existed are read. The page always sends a model.

**What happened.**
- Fast suite before: `211 passed, 2 skipped, 23 deselected, 54 warnings in 37.75s`.
- After: `213 passed, 2 skipped, 23 deselected, 54 warnings in 46.58s`. The 2 extra are the
  new tests.
- App smoke check (real fast engine, port 8799, `--no-warm`, no browser):
  - `/api/models/state` with no fix gives `al_ln_literature`.
  - `fix=none` gives the published model.
  - `snapshot=783` gives the published model plus the `fallback` reason.
  - `snapshot=783&fix=al_ln_literature` is refused with the reason.
  - `/api/status` reports `defaults` `{630: al_ln_literature, 783: none}`.
  - The page HTML contains `#modelNote`.

**Validated?**
- Yes, for the code change: the tests and the endpoint checks above.
- Not verified:
  - the page's JavaScript in a browser: the note appearing on 783 and the fix coming back
    on 630. Only a syntax check (`node --check`) was run.
  - `warm_up()` building the fix at start-up (the smoke run used `--no-warm`).
  - the slow suite (not run).

**Plain English.**
- The corrected brain model is now the one you get unless you ask otherwise, both in code
  and in the app.
- The original published model is still there: pass `fix="none"` in code, or click
  "Published model (Shiu et al. 2024)" in the app. Anything that checks our work against
  the paper still uses it.
- On the newer brain map (783) the correction is not built in yet, so the app uses the
  published model there and shows a yellow note saying so and why.

## 2026-09-24 - Virtual hybrid computer v0: the fly circuit costs ~1,000x less energy on a Loihi-style chip than on this laptop, but standby power decides the all-day task (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or `data/`. New folder `vhc/`
and write-up `docs/virtual-computer.md` (Stage 1b of the hybrid-computer plan, a design note not in this repo, section 6).
- Parts, each with a price list (`vhc/prices.py`, every constant labelled PUBLISHED,
  MEASURED, ASSUMED or GUESSED, with its source):
  - conventional core: Cortex-M33 @ 150 MHz (assumed cycles per operation, 30 mW active)
    and this laptop's x86 core (ns per operation measured by `vhc/calibrate.py`);
  - neuromorphic core: a numba LIF engine that counts synaptic events, inputs, spikes and
    neuron updates, priced with Loihi's Table 2 numbers (Davies et al. 2018, checked
    against the PDF) in "clocked" (Loihi-style) and "ideal event-driven" modes;
  - GPU: NVIDIA T4 datasheet plus an assumed 5 us launch overhead;
  - living-neuron module: 1,000-cell small-world culture with noise, fatigue, drift, cell
    death and Hebbian plasticity (mostly GUESSED), behind an electrode model (N channels,
    2.2 uV read noise, stimulation spread, CL1 latencies);
  - scheduler: rules (exact work -> conventional core, spiking -> neuromorphic, ...), then
    the cheapest allowed core that meets the accuracy requirement.
- Workloads: (a) feeding decision on the 36- and 400-neuron circuits; (b) continual
  odour learning, mushroom-body design, random ("uniform") wiring, imported from
  `experiments/mb_continual/common.py`; (c) exact sum and sort of 50,000 integers; (d) an
  all-day odour watch with an exact log (hybrid task); (e) electrode bottleneck, accuracy
  vs 1-256 channels.
- Decision rule for (a), set before the benchmark: feed if MN9 > 35.7 Hz (midpoint of the
  whole brain's sugar and sugar+bitter rates). It was chosen knowing the 36-neuron circuit's
  sugar+bitter rate (24 Hz).
- Honesty rule: no design's speed comes from the emulator's own run time.

**What happened.**
- Engine check: the vhc LIF engine gives identical spikes to `sim/fast_engine.py` on the
  same input (unit test). MN9 rates reproduce `docs/minimal-circuit.md` exactly (36:
  62.3 / 0 / 24.5 Hz; 400: 67.7 / 0 / 4.9 Hz for sugar / bitter / both).
- Feeding decision, 36 neurons: Loihi-style chip 3.1 ms and 19.5 uJ; laptop 1.24 ms
  measured and 18.7 mJ (x 15 W); M33 64 ms and 1.9 mJ; T4 GPU 100 ms and 7 J (launch-bound).
  Ideal event-driven: 72 us and 0.64 uJ. 400 neurons: 23.6 ms / 217 uJ (chip) vs 12.9 ms /
  194 mJ (laptop). Accuracy 98.5-100% everywhere; 9-bit weights 100%, 8-bit 98.9% (36) and
  100% (400, brake weakened from 3.4 to 9.2 Hz).
- Odour learning: 66.85% (float, 5 seeds x 2 halves; lane: 66.8%), 66.2% with an 8-bit
  read-out. Per sniff: chip 7.9 uJ, M33 26 uJ, laptop 2.2 mJ (145 us measured), GPU 3.5 mJ.
- Exact sum / sort: laptop 14.5 us / 284 us (measured); hybrid = its M33, 1.33 ms / 62 ms;
  neuromorphic only: not possible.
- Odour watch, per day: hybrid 87 J, M33 alone 89 J, neuromorphic alone 0.65 J (no log),
  laptop 259 kJ, GPU 1.1 MJ. The hybrid's day is 99% the M33's GUESSED 1 mW sleep power;
  at 0.1 / 0.01 mW sleep the hybrid wins by 1.17x / 2.0x. Chip leakage is excluded.
  Log exact; end-to-end accuracy 95.9% (66% on the odour sniffs alone).
- Electrodes (1,000-cell culture, 8 patterns, chance 12.5%): 1-16 channels 10-42% (depends
  on placement), 32: 82%, 59: 90%, 128: 97%, 256: 99.6%; every cell read singly 86%, pooled
  into 256 areas 92%. 30 simulated days of drift + death (87% alive): the day-0 read-out
  still 87.5%.
- Calibration: priced the same way, the whole-brain sugar test on 1,440 cores comes out at
  9.3 ms per simulated second vs Sandia's measured 53.8 ms (model 5.8x too fast).
- Laptop cost model vs measured: 11-15% off on the circuits, 2-3x off on sum/sort.
- Unit tests: `vhc/tests`, 16 passed in about 5 s.

**Validated?** No: PRELIMINARY. Done: spike-for-spike check against the project engine;
the circuit and odour results reproduced; Loihi constants checked against the paper; one
calibration against Sandia (failed by 5.8x on time, reported). Not done: any measurement
on real neuromorphic, microcontroller or GPU hardware; chip static power; on-chip message
traffic; GPU batching; laptop power measurement for this lane (energy = time x 15 W).
Weak points: M33 cycle counts and GPU overheads are assumptions; the living module's
biology is mostly guessed and the model culture does little computing of its own; the
mushroom body's spike counts per sniff (KC, APL, output spikes) are guesses; most runs use
one seed; the feeding threshold was set after seeing the 36-neuron circuit's rates.

**New or reproduction?** New as a whole (a priced, testable model of this project's hybrid
design). The method (count operations, price them per operation) is standard: SANA-FE
does it for spiking chips, gem5 and Accel-Sim for CPUs and GPUs.

**Plain English.** We built a pretend computer out of software that has the parts of the
future hybrid machine: an ordinary processor, a brain-like chip and a dish of living
neurons. We gave every part a price list (how long and how much energy each small step
costs on the real thing), ran five jobs, and added up the bills. The brain-like chip ran
the fly's feeding circuit for about a thousandth of the laptop's energy, and learned smells
cheaply. It cannot do exact maths at all, so the hybrid hands that to its small ordinary
core, which is much slower than a laptop. For a gadget that listens all day, the winner
depends mostly on how little power each part draws while waiting, and we do not know those
numbers yet. The living neurons worked through 59 electrodes but cost a lot of energy per
answer, and their settings are guesses.

## 2026-09-24 - Reservoir computing, spiking version: does the fly's wiring compute better than random wiring when run as real spikes? (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or `data/`. New folder
`experiments/reservoir_spiking/` and write-up `docs/connectome-reservoir-spiking.md`.
- The test: the rate lane's reservoir question (`docs/connectome-reservoir.md`),
  redone with the project's spiking model.
  - Reservoir: `FastBrain` from `build_brain(fix="al_ln_literature")` (fix
    passed explicitly), 127,400 neurons, 14,635,639 connections, w_syn
    0.275 mV. No rescaling of any kind.
  - Input: u(t) (0 to 0.5, one value per 20 ms bin) as Poisson spikes on all
    9,145 sensory neurons (the rate lane's set). Push-pull code: half the
    neurons (random) fire at peak x 2u, the other half at peak x (1 - 2u).
  - Input level (the tuned setting): peak 150 or 400 Hz.
  - Readout: spike counts per 20 ms bin of the 1,299 descending neurons, and
    of 10 / 30 / 100 / 300 / 1,000 random non-sensory neurons. Each clean and
    with count noise (80% of spikes detected, plus 5 Hz false detections).
  - Tasks, ridge readout, train / validation / test split (1,000 / 400 / 600
    bins) and controls: reused from `experiments/reservoir/lib.py`.
  - Runs cut into 4 segments, each with 500 ms of true-input washout, plus
    500 ms with the input off at the end (runaway test).
- Controls, 3 seeds each, built without self-connections: a degree-preserving
  shuffle (target column permuted), and Erdős-Rényi with the same edge count
  and weight values.
- Pre-registered pass rule, written before any comparison run (doc, 00:10),
  the rate lane's rule unchanged: real wins a task only if it beats both
  controls by more than the larger seed-to-seed range.
- Changes from the plan:
  - Amendment 1 (00:20, compute): the 50 Hz level was dropped after the real
    network's seed-0 runs, because runs were 1.4x slower than timed. Only
    that network had been scored; 50 Hz was its worst level.
  - Amendment 2 (01:25, exploratory): the same grid with 5 ms bins at 400 Hz.
- Run time: about 115 min of compute (main 70, ±20% check 27, 5 ms run 11,
  probes and checks 7). That is over the 90-minute budget.

**What happened.**
- Pass rule: FAIL, with 0 wins, 4 losses and 2 ties (the rate lane's count).

  | | Real | Shuffled | Erdős-Rényi |
  |---|---|---|---|
  | Memory, descending neurons | 1.90 | 2.13 | 2.03 |
  | Memory, 1,000 random | 1.51 | 1.85 | 1.98 |
  | NARMA-10 error, descending | 0.95 | 0.94 | 0.98 |
  | NARMA-10 error, 1,000 random | 0.95 | 0.92 | 0.93 |
  | XOR, descending | 57.6% | 67.8% | 70.7% |
  | XOR, 1,000 random | 53.4% | 63.6% | 70.4% |

  - Memory and XOR are LOSE; NARMA-10 is a TIE, because every network fails
    it (1.0 = guessing the average).
  - Across all 36 comparisons (every readout, clean and noisy): 0 wins, 19
    losses, 17 ties.
- Every network forgets within about 2 bins (40-60 ms): memory capacity is
  about 2, against 18-48 in the rate version.
- Activity (non-sensory neurons, 400 Hz): no network runs away (0 of 18
  runs).
  - Real: 10% of neurons fire, 3.9 Hz on average, 39 Hz among those that
    fire. 0.9% fire above 100 Hz and make 36% of all spikes. The hot cells
    are mostly in the smell system (antennal-lobe local and projection
    neurons, including 30 lLN1_bc at 150-210 Hz).
  - Shuffle: 22% fire, 2.9 Hz on average, 13 Hz among those that fire.
  - Erdős-Rényi: 46% fire, 5.5 Hz on average, 12 Hz among those that fire.
  - The optic lobe is almost silent in the real network (3% active), including
    the lobula-plate cells behind the rate lane's spectral-radius artefact.
- Electrode bottleneck:
  - The real wiring is the worst to read at every electrode count (memory at
    10 neurons: 0.21 / 0.40 / 0.52).
  - With count noise its XOR falls to chance (50%) with 1,000 neurons, while
    Erdős-Rényi keeps 63%.
  - Its descending neurons are its best, most noise-proof readout.
- ±20% synapse weight (seed 0, 400 Hz): the real wiring is still lowest on
  XOR everywhere, and lowest on memory everywhere except the descending
  neurons at -20% (a three-way level).
- Exploratory 5 ms bins: 0 wins, 3 losses, 3 ties. Memory reaches back only
  15-20 ms in any network, and XOR is at chance.
- Biology check: in the real brain alone, activity outlasts the input. A
  pair of cholinergic CB0216 neurons (one per side, 451 and 455 synapses onto
  each other) keeps firing at about 156 Hz for at least 1 s after the input
  stops, dragging along 422 neurons at low rates. This is likely a model
  artefact (wrong transmitter, or no synaptic fatigue in the model): a
  candidate for the transmitter audit.

**Validated?** No: PRELIMINARY.
- Done:
  - Pre-registration before any comparison run.
  - 3 seeds per network.
  - Settings chosen on validation data and scores taken on test data.
  - Controls checked: edge counts, no self-connections, weight lists,
    degrees, signs.
  - Real network checked against `build_brain`.
  - Input rates checked (1.5-4% below intended, from the model's own
    refractory rule).
  - No readout neuron is sensory.
  - ±20% synapse weight.
  - The 5 ms-bin run.
  - Persistence check.
  - Literature search.
- Not done:
  - The published matrix as a spiking reservoir.
  - The ±20% check on seeds 1-2.
  - Other input codes (for example, one sense only).
  - Independent review.
- Weak points:
  - An artificial input that barely reaches the optic lobe.
  - Tasks built for longer memory than the model has.
  - Only two input levels.
  - 1,000 training bins.
- Bug found in the reused rate-lane code: `degree_shuffle(no_self=True)` can
  copy a target instead of swapping it when one connection is picked twice.
  It changed 2 neurons' input counts by one in shuffle seed 1. Negligible;
  not fixed, because the file belongs to that lane.

**New or reproduction?** Partly both.
- Already done:
  - The rate-model versions (Costi et al. 2025; conn2res, Suárez et al.
    2024).
  - Informal GitHub projects: a larval-fly spiking reservoir against a
    degree-matched random graph, too short to conclude; a pre-registered
    fly-reservoir framework with no results yet; and a simulator showing that
    rewiring changes activity.
- Not seen in the sources we reached: the whole adult FlyWire brain as a
  spiking reservoir on memory / NARMA / XOR with both controls and
  pre-registration, the descending-neuron readout, the electrode and
  count-noise sweep, and the activity-concentration measure.

**Plain English.**
- We ran the fly's whole wiring diagram as real spiking neurons, fed it a
  signal, and trained only a simple readout, as a living-neuron computer
  would be used.
- It again did not beat random wiring of the same size. It remembered less,
  did worse on a logic task, and matched it on a prediction task that every
  network failed.
- The old explanation (a scaling artefact) is gone. The new one is similar
  in spirit: the real brain drives a few pathways, mostly smell, very hard
  and leaves 90% of its neurons silent. So random electrodes mostly read
  silence, and read noise hurts it most.
- None of the networks remembers anything for longer than about 50 ms. That
  is a limit of the model (no slow parts), not of the fly.

## 2026-09-24 - Virtual hybrid computer v1: calibrated on real Loihi 2, the chip's energy lead over a $5 microcontroller shrinks from ~96x to ~4x; the model culture plays Pong only through 1,024 electrodes and does not learn (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or `data/`. Changes in `vhc/`
and a rewrite of `docs/virtual-computer.md`.
- Chip timing calibrated (`vhc/neurocal.py`): v1 = v0 + A per time step + B per spike,
  fitted to Sandia's Loihi 2 measurements (Wang et al. 2025, arXiv:2508.16792). B = slope of
  wall time vs spikes in the paper's 1 ms background sweep (7 points; relative least
  squares, intercept discarded); A = the sugar run at 0.1 ms steps (one point). Held out:
  the sugar run at 1 ms steps and the 0.1 ms sweep (7 points).
- Chip static power, per Loihi 2 chip: 18 / 73 / 296 mW (low / mid / high), DERIVED from
  Shrestha et al. 2024 (arXiv:2310.03251) Table 1 as (total - dynamic energy) / time. The
  table's time base is ambiguous, hence the 16x range; Hala Point ceiling 2.26 W per chip.
  Charged for the whole busy time, and all day for the odour watch.
- `neuromorphic.price(version="v1")` is the default; `"v0"` keeps the old pricing;
  `price_range` gives best case (v0 timing + low static) and worst case (calibrated + high).
- Living module: DishBrain (Kagan et al. 2022, Neuron, PMC9747182) and FinalSpark (Jordan
  et al. 2024, Front. AI, PMC11097343) settings added to `prices.py`, both read in full;
  figure values read off by eye and labelled so. Cell death FITTED to 50% at 100 days;
  false electrode events 1 -> 0.05 Hz (bounded by DishBrain's 0.05-0.1 Hz mean electrode
  rate); resting drive and noise lowered (still GUESSED; ~0.13 spikes/cell/s).
- New workload (f), `vhc/workloads/pong.py`: DishBrain's game (8 place-coded sites, 4-40 Hz
  rate code, 10 ms ticks, 100 ms / 100 Hz hit feedback, 4 s / 5 Hz random miss feedback +
  4 s rest, 20-min sessions) as one compiled closed loop. Players: living culture through N
  electrodes, its silicon copy on the neuromorphic core (every cell read, pooled), a
  noise-driven paddle, the culture with no stimulation, and an M33 controller. Paddle size
  FITTED so the noise paddle scores DishBrain's 0.80 hits per rally; ball crossing time
  3.5 s DERIVED from 69 rallies per session. GUESSED: layout, paddle speed, read-out rule,
  and a reward-modulated Hebbian learning rule (eligibility trace, +/- on hit/miss).
- Feeding default is now the robust 400-neuron circuit; 36 remains an option.
- `bench.py` writes `results/compare.md` (v0 vs v1 side by side); v0 results kept in
  `results_v0.json` / `table_v0.md`. New tests: `vhc/tests/test_v1.py`.

**What happened.**
- Calibration: v0 was 5.8x too fast at 0.1 ms steps and 13.2x at 1 ms, so no single factor
  fits. Fit: A = 3.30 us per step, B = 0.967 us per spike. Held-out sugar at 1 ms: 15.7 ms
  predicted vs 12.4 ms measured (+26%). Held-out 0.1 ms sweep: -42% to -7%. Fit residuals
  on the 1 ms sweep: -26% to +11%. One-term fits miss the held-out point by -57% (A only)
  and +266% (B only).
- Feeding, 400 neurons (default): chip 23.6 ms / 217 uJ (v0) -> 65.8 ms / 5.0 mJ (v1; range
  0.64-19.7 mJ). Laptop 10 ms measured / 150 mJ; M33 694 ms / 20.8 mJ. Energy lead over the
  laptop ~900x -> ~30x (8-230x); over the M33 ~96x -> ~4x (1.06-32x). 100% correct at 8 and
  9 bits.
- Feeding, 36 neurons: 3.1 ms / 19.5 uJ -> 38 ms / 2.8 mJ; the M33 (1.9 mJ) now beats the
  chip at the mid estimate. Odour sniff: 8.5 -> 66 uJ (M33 26 uJ). Whole-brain sugar on 12
  chips: 66 mJ -> 113 mJ per simulated second.
- All-day odour watch: hybrid 87 J/day -> 6,390 J/day (1,640-25,700); M33 alone 88.5 J/day.
- Electrode test (e): 59 electrodes 89.6% -> 95.4%; silicon copy 91.7% -> 97.5%; after 30
  days (79% alive) the day-0 read-out 91%.
- Pong (20-min sessions; hits per rally, balls hit): living 1,024 electrodes 1.89, 62%
  (learning off: 1.27, 54%); living 59 electrodes 0.62, 46%; DishBrain's own layout 0.77,
  43%; no stimulation 0.79, 44%; noise paddle 0.86, 47%; silicon copy 98.9% (rallies 42,
  very spread; learning off 4.1, 98.0%); M33 controller never missed (100%). By electrodes
  (2-5 sessions): 8: 0.44, 16: 1.07, 32: 0.38, 59: 0.62, 128: 0.39, 256: 1.25, 1,024: 1.89.
  No within-session improvement (minutes 6-20 vs 0-5) in any living setting; DishBrain's
  human cultures went 0.68 -> 1.10. Learning rates 0.03-1.0 tried before the benchmark
  (0.1-1.0 on seeds 10-12, kept apart); none reproduced DishBrain, so eta stays GUESSED.
- Cost per game-second: living 1 s real time / 25 J (CL1 box); silicon copy 18.7 ms /
  74 mJ (v0: 11 ms / 1.1 mJ); M33 controller 47 us / 1.0 mJ.
- Unit tests: `vhc/tests`, 24 passed (8 new). Emulator time of the benchmark ~10 min (never
  used as a design's speed).

**Validated?** No: PRELIMINARY. Done: a timing fit with a held-out check on real hardware
data; static power from a published measurement; DishBrain/FinalSpark settings read from
the papers; the Pong noise baseline matched by construction. Not done: energy measured on
any chip; a one-chip Loihi 2 timing; the per-step/per-spike split for small jobs; any
living-culture learning reproduced. Weak points: static power range is 16x; the
calibrated overheads come from a 12-chip system and are applied to one-chip jobs (range
given); the Pong skill comes from a GUESSED layout; the culture's wiring, noise, reach,
fatigue and learning rule are guesses; 2-5 sessions per Pong setting; figure values read
by eye.

**New or reproduction?** Partly both. The Pong task reproduces DishBrain's published
protocol; the fitted chip timing and the living-vs-silicon-vs-controller comparison on
the same game, priced per game-second, are new as far as the sources we read show.

**Plain English.** We checked our pretend brain-like chip against a real one. Sandia ran
the whole fly brain on 12 real Loihi 2 chips, and our chip was about 6 times too fast. We
added two costs real chips pay: waiting for each other every step, and sending spikes
around. Then we tested the fix on a run we had kept aside, and it was off by about a
quarter. We also added the power a chip leaks while it is switched on. After that, the
brain-like chip is still better than the laptop on the fly's feeding circuit, but only
about 4 times better than a $5 microcontroller. For tiny jobs, and for gadgets that
listen all day, the microcontroller now wins. We also taught the model dish of neurons to
play Pong the way DishBrain did. Read through 1,024 electrodes it played a bit better than
chance; through 59 it did not. A silicon copy of the same network played almost perfectly,
and a few lines of ordinary code never missed, for far less energy. Unlike DishBrain's real
cells, our model cells did not get better with practice, so how fast living cells learn is
still the biggest unknown.

## 2026-09-24 - The smallest hardware-ready feeding circuit: 95 neurons pass +/-20% weights and 8-bit, about 10 KB and 18% of one RP2350 core (PRELIMINARY)

**What was changed.** Nothing in the model, `sim/`, `app/`, `tests/` or `data/`. New:
`experiments/robust_circuit/` (scripts and results; reuses `experiments/minimal_circuit/`
code by import) and `docs/robust-circuit.md`. Model: snapshot 630 with the
`al_ln_literature` fix passed explicitly, fast engine, 1 thread, MN9 =
720575940660219265. The pass rule was written into the doc at 02:05, before any
candidate was run. A circuit, run on its own (`FastBrain.from_arrays`), must pass in
four versions, each against the whole brain in the matching state: normal weights,
weight per synapse -20%, +20%, and 8-bit weights (largest synapse count -> 127, round
to nearest). In each: MN9 at sugar 100 and 200 Hz within 10% of the whole brain; bitter
alone below 0.5 Hz; bitter 100 Hz added to sugar 100 Hz lowers MN9 by at least half the
whole brain's drop. Water is reported, not required. Final verdict as first written:
seeds 0, 1, 2 x 30 trials. **Amendment at 03:15** (after review): seeds 0-2 were used
by the step-back to choose among ~215 circuits, so they are not held out; the real
held-out test is fresh seeds 3, 4, 5 (never used by this or the minimal-circuit lane),
with four circuits declared in advance. Search: seed 7, stricter version (7.5%, zero bitter spikes,
brake 0.6), rejecting at the first failed check. **Amendment at 02:08** (search
settings only): scoring on 30 trials of seed 7 instead of 10, and starting from the
400-neuron circuit even though it missed the stricter 8-bit check on 10 trials (8.3%
vs 7.5%). About 68 minutes of compute of the 90 budgeted.

**What happened.**
- **Whole brain at +/-20% (new; seeds 7/1/2, 30 trials):** -20%: sugar 100 Hz
  34.0/35.1/34.5, sugar 200 Hz 83.0/82.1/82.3, sugar + bitter 0.4/0.1/0.2. +20%: sugar
  100 Hz 77.1/77.2/77.4, sugar 200 Hz 98.5/99.8/97.7, sugar + bitter 12.9/14.3/12.9.
  Bitter alone 0 throughout.
- **Strongest-path circuits under the new rule:** 600, 500 and 400 neurons pass. 300,
  250 and 200 fail at -20% (sugar 100 Hz 19%, 28%, 58% low).
- **Search from the 400:** neuron blocks (100 down to 2, weakest path score first)
  400 -> 127; single neurons, 3 rounds to a local minimum, 127 -> 95; connection blocks
  down to single connections (one pass) 2,156 -> 1,007 connections and 91 neurons.
  3,688 candidates. Of 3,060 rejections, 1,853 failed first at -20%, 1,184 at +20%,
  21 at normal weights and 2 at 8-bit.
- **Check on seeds 0-2 (used for selection, not held out):** the 91-neuron end point
  failed (seed 0, -20%: sugar 100 Hz 13% low). Stepping back, 214 accepted circuits
  failed and checkpoint 411 passed: **95 neurons, 1,236 connections, 27,295 synapses.**
  Its neighbours with one connection fewer fail seed 2. On seeds 0/1/2, sugar errors
  +1.1% to +9.8% and -4.2% to -8.4% across the four versions (worst +9.8%, seed 1,
  +20%); brake 0.79 to 0.81 (normal), 0.86 to 0.89 (-20%), 0.56 to 0.60 (+20%), 0.85
  (8-bit); bitter alone 0. Sugar + bitter at normal weights 21.5 to 22.5 Hz against 3.6
  to 4.9 Hz in the whole brain.
- **Real held-out test, fresh seeds 3/4/5 (30 trials, whole brain re-measured at each:
  sugar 100 Hz 67.1/67.8/68.5 normal, 34.6/34.2/34.3 at -20%, 77.1/77.4/77.5 at +20%):**
  checkpoint 411 **passes all 12 seed x version tests.** Worst sugar error 9.0% (seed 4,
  normal); weakest brake 0.59 (seed 3, +20%); bitter alone 0. The other circuits
  declared in advance: checkpoint 79 (95 neurons, 2,156 connections) **fails** seed 5
  at -20% (13.4% low); checkpoint 47 (127 neurons) passes (worst 7.3%, brake 0.61);
  the 400-neuron start passes (worst 3.0%, brake 0.91, water 32 vs 30-32 Hz).
- **Water:** 0 Hz at 100 and 200 Hz on every seed (whole brain 0 and 30 to 31 Hz). The
  circuit has no water taste neurons; water survived in the search down to 181 neurons.
- **Contents:** 18 sugar and 6 bitter taste neurons, MN9, 70 relays (41 acetylcholine,
  21 GABA, 7 glutamate, 1 dopamine). 9 of the paper's 10 named sugar-pathway types
  (all but Fdg), plus Scapula. It contains 34 of the previous lane's 36-neuron circuit.
  292 of 1,236 connections inhibit; the largest has 561 synapses.
- **The 400-neuron start circuit** also passes all four versions on all 3 held-out
  seeds (worst error 5.4%, weakest brake 0.90).
- **Second removal order** (random, neurons only, 15 minutes): 400 -> 165 neurons,
  still shrinking when time ran out. Inconclusive about whether 95 is order-dependent.
- **RP2350 arithmetic** (2 x Cortex-M33 at 150 MHz, 520 KB SRAM; previous lane's
  assumed costs: 25 cycles per neuron update, 10 per synaptic event, 12 per random
  draw; 0.1 ms steps). 8-bit version (954 connections kept; 282 round to zero): memory
  10,287 B (10 KB, 2% of SRAM; 16-bit 12 KB). Worst case sugar 200 Hz: 950,000 neuron
  updates, 240,000 random draws, 90,860 synaptic events per simulated second = 27.5 M
  cycles = 18% of one core, about 5.4x faster than real time (clock-driven); about
  3.3 M cycles = 2.2%, about 45x (event-driven). For comparison: 36 neurons 7%, 400
  neurons 77% (previous lane).
- **Firmware file:** `results/robust_circuit_firmware.json` (20 KB): neurons with types,
  8-bit and exact weights, parameters, per-step constants, update rule, expected MN9.
  Rebuilding the circuit from that file alone gives MN9 identical to the simulator
  (difference 0.000 Hz on all 7 stimuli, seed 0).

**Validated?** No: PRELIMINARY. Done: rule fixed before the search; 3 fresh held-out
seeds (3-5) in all four versions, after seeds 0-2 turned out to be used for selection;
whole-brain +/-20% references on every seed used; the firmware file checked by
rebuilding from it; a second removal order (inconclusive). Not done: more fresh seeds,
other start points, a completed second order, other 8-bit methods, 32-bit or
fixed-point arithmetic, anything on a real chip. Margins are thin (9.0% against 10% on
fresh seeds; brake 0.59 against 0.5), and a 95-neuron sibling fails a fresh seed, so
some other seeds will probably fail the chosen circuit too. The search overfitted its
own seed: 214 accepted circuits between 91 and 95 neurons failed seed 0. It is a reduction of the model, which disagrees with real
flies on Roundup and Fdg.

**New or reproduction?** New as far as this project goes: it extends the previous
lane's minimal-circuit search with weight-tolerance and 8-bit tests inside the rule.
No literature search was done for other robust minimal feeding circuits.

**Plain English.**
- The previous 36-neuron feeding circuit broke if every connection got 20% stronger or
  weaker, and just failed with 8-bit weights. This time those tests were part of the
  rule from the start.
- The smallest circuit that passes all of them has 95 neurons. On random inputs it had
  never seen, it matches the whole brain's sugar response within 10% (only just: 9%), ignores bitter alone and
  still lets bitter hold sugar back, whether the synapses are normal, 20% weaker, 20%
  stronger or stored as 8-bit numbers. It no longer responds to water.
- On the $17 RP2350 board it would need about 10 KB of memory and about a fifth of one
  core, so it should run in real time with about 5 times to spare. That is arithmetic,
  not a test on the chip. The file a firmware lane needs is ready.

## 2026-09-24 - The CB0216 loop that keeps the brain firing after input stops: real excitatory wiring in three connectomes, not a sign error; the endless lock-in is unverified (PRELIMINARY)

**What was changed.** Nothing in `sim/`, `app/`, `tests/` or `data/`, and the default model
(`"al_ln_literature"`) is unchanged. New folder `experiments/cb0216_loop/` (identify,
cross-dataset, reproduction, loop-search and diagnosis scripts, `results/`) and
`docs/cb0216-loop.md`. Pass rules R1-R5 were written into the doc before any
simulation was run. Fast engine, `n_threads=1`, one simulation at a time; about 35 minutes
of compute in total.

**What happened.**
- **Identity.** Two cells, one per side: 720575940633316307 (right) and
  720575940636552805 (left). Both are central intrinsic cells of the gnathal ganglion
  (GNG) with a putative primary hemilineage. They are the only two CB0216 cells in both
  annotation releases. All of their synapses are in the GNG. FlyWire predicts
  acetylcholine at 0.639 / 0.650 (v783: 0.642 / 0.652); `known_nt` is empty. The average
  synapse scores are ACh 0.64-0.65, Glu 0.18-0.21, DA 0.10-0.12 and GABA 0.03. They have
  451 and 455 synapses onto each other (identical in the model and the v783 table). Each
  is the other's largest output (18%) and largest input (24-26%). They send 553 synapses
  onto the two MN9 motor neurons.
- **Other connectomes.** In maleCNS 0.9 (type GNG117) the pair has 914 / 973 mutual
  synapses and ACh at 0.852 / 0.836. In BANC 888 it has 237 / 205 and ACh at
  0.708 / 0.644. In both, each cell is the other's top output. The hemibrain has no match,
  since it does not cover the GNG.
- **R1 PASS.** After the input stops, both cells fire at 156-157 Hz in the last second of
  5 s, in 3/3 seeds, for the reservoir lane's input (400 Hz peak) and for all touch
  sensors at 100 Hz. MN9 fires at 104-105 / 125-126 Hz, and 31-32 other cells stay on.
- **R2 PASS.** Silencing either cell gives 0 Hz for both and 0 other active cells, in
  12/12 runs.
- **Switch-on.** One spike in either cell is enough. Touch input switches it on: all
  mechanosensory cells at 50 Hz for 1 s or 100 Hz for 100 ms, but not at 20 Hz or for
  20 ms. Only the 50 mechanosensory cells of "unknown" sub-class do it (35 via the
  maxillary-labial nerve, 15 via the antennal nerve). Sugar, bitter, water, Ir94e, smell,
  vision, humidity and temperature input do not. CB0216 is at 0 Hz during sugar, so the
  Phase 3 sugar -> MN9 result does not involve it.
- **Robustness.** Adaptation on: 126-127 Hz. Conductance-based synapses on: 151 Hz (3/3
  seeds each). Mutual synapses set by hand: it holds at 205 or more (205: 2/3 seeds;
  237: 99 Hz; 300: 122 Hz) and never at 150 or fewer. The one-spike arithmetic threshold
  is about 162.
- **Off-switch.** Driving the pair's two GABA inputs for 0.1 s stops it in 3/3 seeds; the
  DNge160 pair stops it in 2/3. Nothing drives these inputs at rest in the model.
- **R3.** The search found 357 reciprocal excitatory pairs (at least 30 synapses each
  way), 158 excitatory 3-cycles and 0 autapses. Of the top 60 pairs and 30 cycles tested,
  only CB0216 self-sustains (it also holds on seeds 1 and 2). Three other pairs are above
  the one-spike threshold: LT1a/LT1b on the left (252/268) and on the right (188/180),
  and CB0756 (229/221). Isolated, they hold at 70-110 Hz. In the whole brain they die
  after 1-2 spikes, because the cells they fire send 333-479 inhibitory synapses back.
  For CB0216 that number is 37.
- **Literature.** No publication names CB0216 or GNG117. There is no staining and no
  recording. Eckstein et al. 2024 (Cell) report 94% neuron-level accuracy and 91% for
  known cholinergic types; consistent left/right pairs average 0.79 confidence.
  MN9 activation extends the proboscis (McKellar et al. 2020, eLife); MN9 is driven by
  sugar and inhibited by bitter (Gordon & Scott 2009, Neuron; abstract). Loop-held
  persistent activity is real in flies elsewhere (Zhao et al. 2018, eLife:
  MBgamma > M6 > aSP13, minutes).
- **R4 verdict (rule fixed in advance): biology (plausible).** ACh comes from maleCNS
  (0.84-0.85) and BANC on top of FlyWire. The wiring is in both other connectomes,
  nothing contradicts it, and the loop survives both realism upgrades. **R5 not run**:
  there is no supported sign correction, so no variant was built.

**Validated?** No: PRELIMINARY. Done: 3 seeds for R1/R2 and the realism upgrades; two
switch-on inputs; a weight sweep; the IDs, synapse counts and sign checked against the
v783 table; the isolated pair reproduces the rate; a cross-check in two other
connectomes; a literature search. One protocol mistake was found and fixed before
scoring (directly driven cells were given no refractory period, which produced a
471 Hz state). Not done: any real recording. The rule tests the sign and the wiring, not
whether a real pair holds on for seconds. The model lacks synaptic depression or
saturation and background activity. Its adaptation is only the Phase 7 calibration.
The endless 156 Hz lock-in is probably exaggerated.

**New or reproduction?** New. It explains the reservoir lane's persistence finding. We
found no prior report on this cell type.

**Plain English.**
- The brain model has one pair of neurons that, once started, never stop. We checked
  whether that was a labelling mistake like the earlier smell runaway. It is not. The
  two cells really are wired strongly to each other in three different fly brains, and
  every source says they are the excitatory kind.
- A single spike, or a short touch to the proboscis sensors, turns them on. After that
  they keep the proboscis motor neurons firing for as long as we simulate. Silencing
  either cell stops it.
- Many other pairs in the brain are wired just as strongly. They switch themselves off
  because the cells they excite send a brake straight back. CB0216 has almost no such
  brake, which is why it is the only loop that holds.
- It does not touch the sugar -> feeding result. Whether a real fly's CB0216 cells
  really stay on after a touch is unknown. Nobody has recorded them, and the model
  leaves out synapse fatigue, which would probably shorten it.

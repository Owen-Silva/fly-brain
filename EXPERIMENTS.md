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

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

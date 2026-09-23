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

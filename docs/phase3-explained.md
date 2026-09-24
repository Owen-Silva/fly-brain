# Phase 3 explained: did we reproduce the paper?

*Written 2026-09-22. Everything here was produced by code in `sim/shiu_model.py` and
`experiments/phase3/`. The numbers come from `experiments/phase3/comparison_table.md`.*

## The short answer

**Yes. Our copy of the model reproduces the paper.** Every one of the 12 checks went the same
way as the paper, and most numbers land within a few spikes per second of the published ones.
Switching on the sugar-tasting neurons makes MN9, the "stick out the tongue" motor neuron, fire at
67 spikes per second (paper: 65.7). Bitter taste alone does nothing to MN9, and bitter added to
sugar shuts MN9 down, just as in the paper. A neuron-by-neuron comparison against the original
code's own saved output matches almost perfectly (correlation 0.9996 across 448 neurons).

One thing we saw that the paper does not mention: in 2 of 5 trials of the "strong sugar plus
Ir94e" experiment, the whole simulated brain suddenly tipped into a runaway state where about
8,000 neurons fire non-stop. This does not change the verdict, but it needs checking in Phase 6
before anyone relies on that experiment (details under "Honest caveats").

## What the paper did

Shiu and colleagues (Nature, 2024) built a computer model of the entire fruit fly brain.
Each of the 127,400 neurons in their copy of the wiring diagram (FlyWire "snapshot 630")
is a very simple model neuron: it collects electrical input, slowly leaks it away, and fires
a spike when its voltage passes a threshold. Every connection is copied from the real
wiring diagram. Its strength is the number of synapses between the two neurons, and its sign
comes from the chemical the sending neuron uses: acetylcholine excites, GABA and glutamate
inhibit.

To "taste" something, they switched on a group of taste neurons on the fly's mouthparts
(for example, the 21 sugar-sensing neurons on one side) by making them fire randomly at a
chosen rate, such as 100 times per second. Then they watched what the rest of the brain did.
The key neuron to watch is **MN9**, a motor neuron that makes the fly stick out its
proboscis (its feeding tube) to drink. Real flies do that when they taste sugar, so a good
model should make MN9 fire when sugar neurons fire.

Each experiment was repeated 30 times ("trials"), 1 second of brain time each, because the
random input makes every trial a little different. Firing rates are averages over trials.

## What we did

1. **Copied their model exactly.** `sim/shiu_model.py` is a line-by-line port of their
   `model.py`. The equations, every parameter, the weights and the sign rule are
   identical. A test (`tests/test_shiu_model.py`) loads their file and checks every
   parameter is equal to ours. Only five things changed, all to make it run on this
   Windows laptop without changing the maths (listed at the top of `sim/shiu_model.py`).
   The most important: the random seed of every trial is now recorded, so any run can be
   repeated exactly.
2. **Used their data.** The paper used snapshot 630 of the wiring diagram, so that is what
   the main comparison uses. A second check on the newer public snapshot 783 was
   planned but dropped for time (see below).
3. **Ran fewer trials.** This laptop needs between 1 and 6.5 minutes (typically about 2) of
   computer time per second of brain time (depending on how busy it is), so the paper's 30
   trials per experiment would take 30 minutes to over 2 hours each. We ran 10 trials for the main experiments and 5 for the checks. This is marked
   "REDUCED" everywhere. It is enough to see the direction and size of every effect.
4. **Compared three ways.** (a) With the numbers in the paper. (b) With the reference
   code's own saved output (their GitHub repository includes two complete 30-trial sugar
   runs), neuron by neuron. (c) Direction checks: does each effect go the way the paper says?

## The experiments

| Name | What was switched on | What the paper says should happen |
|---|---|---|
| sugar 100 Hz | 21 sugar neurons, 100 spikes per second each | MN9 fires about 66 times per second |
| sugar 200 Hz | same, twice as fast | MN9 fires faster, about 93 per second |
| water 200 Hz | 18 water-sensing neurons | MN9 fires, but more weakly than with sugar |
| bitter 200 Hz | 21 bitter-sensing neurons | MN9 stays completely silent |
| sugar 100 + bitter 40 / 120 | sugar at 100 plus bitter at 40 or 120 | bitter pushes MN9 down; strong bitter almost silences it |
| sugar 200 + Ir94e 200 | strong sugar plus 18 Ir94e taste neurons | MN9 drops but does not stop |

## What we found

All numbers are firing rates of MN9 in spikes per second, averaged over trials, from snapshot
630. "±" is how much the rate varied from one trial to the next. The full table, with sources for
every paper number, is `experiments/phase3/comparison_table.md`.

| Experiment | Our MN9 | Paper's MN9 | Same direction? |
|---|---|---|---|
| sugar 100 Hz (10 trials) | 67.0 ± 3.6 | 65.7 ± 3.3 | yes, MN9 turns on |
| sugar 200 Hz (10 trials) | 92.7 ± 3.7 | 93.2 ± 5.2 | yes, faster input gives faster MN9 |
| MN9 on the same side as the sugar neurons, sugar 100 / 200 Hz | 51.4 / 62.9 | 49.7 / 62.9 | yes, weaker than the opposite-side MN9 |
| water 200 Hz (10 trials) | 33.5 ± 6.1 | 30.7 ± 5.4 | yes, on, but weaker than sugar |
| bitter 200 Hz alone (5 trials) | 0.0 | 0.0 | yes, MN9 stays silent |
| sugar 100 + bitter 40 Hz (5 trials) | 48.0 ± 6.1 | 45.3 | yes, bitter pushes MN9 down |
| sugar 100 + bitter 120 Hz (10 trials) | 0.9 ± 0.7 | 1.5 | yes, strong bitter almost silences MN9 |
| sugar 200 + Ir94e 200 Hz (5 trials) | 58.4 ± 17.3 | 64.3 | yes, MN9 drops but keeps firing |

**The strongest check** is not the table above but the comparison with the original code's own
saved runs (two 30-trial sugar runs that ship with the reference repository):

- Every neuron that fired at 5 spikes per second or more in their run also fired in ours
  (335 of 335 at 200 Hz, 273 of 273 at 100 Hz).
- Neuron by neuron, the firing rates agree with a correlation of 0.9996 (200 Hz) and 0.9992
  (100 Hz). A correlation of 1 would be a perfect match.
- Not one neuron differs by more than random trial-to-trial noise would explain (0 neurons
  more than 4 standard errors apart).
- Their runs have 16 (200 Hz) and 17 (100 Hz) "active" neurons that never fired in ours
  (448 vs 432 active at 200 Hz). Every one of those fired less than once every 4 seconds in
  their runs, so with our 10 trials instead of their 30 we simply never caught them. The
  same reason explains why our neuron counts (392 and 432) sit a little under the paper's
  (410 and 455).

**Where the paper's numbers come from.** The paper's text itself only gives a few numbers (for
example "455 neurons respond at 200 Hz" and "30 simulations of 1,000 ms"). We checked those
against the paper's full text. The MN9 numbers for sugar at 100 and 200 Hz we checked ourselves
against the reference code's saved runs (67.0 and 93.3 there). The MN9 numbers for water, bitter,
sugar + bitter and Ir94e come from the authors' published result files as summarised in
`docs/reference-notes.md`; we did not re-open those files, so those exact numbers are
**UNVERIFIED** by this phase. Their *direction* (water turns MN9 on, bitter turns it down, strong
Ir94e does not abolish it) is stated in the paper's text, and we checked that.

**Verdict for the Phase 3 checkpoint: PASS.** The same neurons respond, in the same direction,
with closely matching strength.

## The plots

- `experiments/phase3/plots/mn9_ours_vs_paper.png`: for each experiment, a blue bar (our
  MN9 firing rate) next to an orange bar (the paper's). The thin black lines show how much
  the rate varied from trial to trial. Bars of similar length mean we match.
- `experiments/phase3/plots/per_neuron_vs_reference.png`: every dot is one neuron. Across
  the bottom is how fast it fired in the reference code's own saved run, up the side is how
  fast it fired in ours. If the port is right, the dots sit on the dashed diagonal line.
  The two MN9s are the orange dots.
- `experiments/phase3/plots/raster_sugar_100Hz.png`: one second of one trial. Each row is
  one of the 60 most active neurons, each tick is one spike. The grey rows at the top are
  the sugar neurons being driven. The blue rows are neurons further along the circuit. MN9 is
  labelled.

## Snapshot 783 (the newer public data)

Not run (dropped for time). Running the Brian2 model on snapshot 783 is about three times slower on
this laptop, and the machine's memory was needed by other work. The faster engine
(`sim/fast_engine.py`) covers snapshot 783 instead.

What *was* done for 783: three of the paper's neurons have new ID numbers in snapshot 783 (one
sugar neuron, one bitter neuron and the second MN9). We found each one's new ID by comparing
who it connects to in the two snapshots. The sugar neuron's new ID connects to exactly the same
partners with the same 557 synapses; the bitter neuron's has the same 302 synapses. The
translations are built into `sim/shiu_model.py` (`SUGAR_R_783`, `BITTER_R_783`,
`MN9_RIGHT_783`). A single 100 ms test run on 783 did make MN9 fire, but that is far too short
to count as a result.

## Honest caveats

- **Fewer trials.** 10 (or 5) trials instead of 30. Averages are therefore a little noisier than
  the paper's, and very rarely firing neurons are missed. None of the conclusions depend on this.
- **Runaway activity with strong Ir94e input.** In the "sugar 200 + Ir94e 200" experiment, trials
  2 and 4 (of 5) suddenly switched, part-way through, into a state where about 8,300 neurons fire
  continuously (up to 364,000 spikes in one second, against about 21,000 in a normal trial). In one
  of those trials MN9 dropped to 25 spikes per second. This is why that row's "±" is so large (17.3)
  and why the run lists 8,613 "active" neurons. None of our 50 trials in the other six experiments,
  and none of the reference code's 60 saved sugar trials, did this. It is most likely a real property of the model
  (the equations are identical and everything else matches the original code), not a bug in our
  copy, but we cannot prove that without the authors' raw Ir94e spikes. **Treat it as unexplained
  until Phase 6 re-runs it with more seeds.** Without the runaway trial where MN9 dropped, our MN9
  average for this experiment would be about 67, close to the paper's 64.3.
- **Model left/right labels are mirrored.** The code calls MN9 `...660219265` "left", the paper
  would call it the other side. We avoid the words left and right and say "contra" (opposite side
  to the stimulated sugar neurons, the stronger one) and "ipsi" (same side). Go by the ID numbers.
- **Sugar stimulus rate of the reference's saved run.** Their saved `sugarR.parquet` has no rate
  written in it. The stimulated neurons fire about 197 times per second in it and their notebook
  says the default was 200 Hz, so we compare it with our 200 Hz run.
- **The paper's model is simple.** Matching the paper means our copy is faithful, not that the
  fly's brain works this way. That question belongs to later phases.

## Files

- `sim/shiu_model.py`: the model. `run_trials(...)` runs one experiment and returns spike
  times and firing rates.
- `experiments/phase3/run_experiments.py`: the experiment list and runner.
- `experiments/phase3/results/v630/`: for each experiment, every spike
  (`*_spikes.parquet`), per-neuron rates (`*_rates.csv`) and exact settings, including seeds
  (`*_settings.json`). `results/phase3_rates.parquet` has all rates in one table. This is the
  ground truth the faster engine (`sim/fast_engine.py`) is checked against.
- `experiments/phase3/compare.py`: builds the comparison table and plots.
- `experiments/phase3/map_ids_630_to_783.py`: finds the new IDs of neurons that were renamed
  between snapshots. (The IDs in use came from an interactive run of the same method; the
  script itself has not been run yet.)

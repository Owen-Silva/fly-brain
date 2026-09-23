# Phase 7, upgrades 1-3: making the neurons and synapses more realistic

Status: **PRELIMINARY.** The checks below were re-run with 3 random seeds (and
parameter variants for every upgrade), but the other PLAN.md Phase 6 steps
(independent review, sharing) have not been done.

Code: `sim/realism.py` (the upgraded engine, `RealisticBrain`).
Tests: `tests/test_realism.py`.
Experiments: `experiments/phase7/` (`run_phase7.py` runs, `analyze.py` summarises,
`results/summary.md` has every number, `log-entry.md` is the EXPERIMENTS.md text).

## The short version

The baseline model (Shiu et al. 2024, `sim/fast_engine.py`) makes three big
simplifications. Each one now has an on/off switch:

| switch | baseline | upgrade | main published source |
|---|---|---|---|
| `delays` | every signal takes exactly 1.8 ms | 1.8 ms + travel time (distance / 0.2 m/s) | Paul et al. 2015 (1.8 ms synaptic part); Kottmeier et al. 2020 (0.196 m/s) |
| `conductance` | each synapse pushes the voltage by a fixed amount | the push depends on how far the voltage is from the channel's reversal potential (0 mV excitatory, -60 mV inhibitory) | Lee & O'Dowd 1999, Su & O'Dowd 2003 (0 mV); Rohrbough & Broadie 2002 (-50 to -60 mV) |
| `adaptation` | a steadily driven neuron fires at a steady rate forever | every spike adds a slow brake current (fades over 100 ms) | Onodera et al. 2017 (SK channel pauses ~100 ms); Zhao & Wu 1997 (strength) |

With all three switches OFF the new engine gives exactly the same spikes as
the baseline engine, spike for spike, for the same seed (proved by tests on
small networks and on the whole brain). `sim/fast_engine.py` was not changed.

## How each upgrade was checked

For every upgrade the Phase 3 baseline checks were re-run on the whole brain
(snapshot 630) with the upgrade ON:

* sugar 100 Hz and 200 Hz -> MN9 fires (and 200 Hz more than 100 Hz, and the
  MN9 on the opposite side more than the one on the same side);
* water 200 Hz -> MN9 fires, less than sugar;
* bitter 200 Hz alone -> MN9 silent;
* sugar 100 Hz + bitter 120 Hz -> MN9 near zero (at most 10% of sugar alone);
* sugar 200 Hz + Ir94e 200 Hz -> MN9 lower than sugar alone but not abolished,
  and how often this condition "runs away" (a trial with more than 5x the
  baseline's median spike count: the whole network ignites).

Each condition was run with 3 random seeds x 30 trials x 1 s (the runaway
condition with 5 seeds = 150 trials for the main versions, because runaway
happens in only ~3% of trials). A check "holds" only if it passes for every
seed. Every neuron was also compared with the baseline: Pearson correlation of
firing rates (stimulated neurons left out) and how many of the 50 most active
neurons are the same. The "noise floor" is the same comparison between the
baseline and itself run with 3 new seeds. Parameter variants (a slower and a
faster conduction speed, another reversal potential, another adaptation time
constant and strength) were run with 1 seed x 30 trials of the five main
conditions (the machine was shared with other simulations); the two
adaptation variants were also run on the runaway condition (150 trials each).

## Upgrade 1: synaptic delays that depend on distance

**What the baseline does.** Every spike reaches every target exactly 1.8 ms
later, whether the two neurons touch or sit on opposite sides of the brain.

**What the published data say.**

* The 1.8 ms itself comes from Paul et al. 2015 (Front Cell Neurosci 9:29).
  It was measured at the fly larval neuromuscular junction *from the peak of
  the spike at the nerve terminal* to the start of the response in the
  muscle (1.8 +/- 0.3 ms, 18 C). So it is the synaptic part only: it
  contains no travel time along the axon. We keep it, and add travel time.
* Travel speed: Kottmeier et al. 2020 (Nat Commun 11:4491) measured
  Drosophila larval axons at 0.196 m/s (motor) and 0.129 m/s (sensory);
  these axons are about 0.4 um thick, similar to typical fly brain neurites.
  Kadas et al. 2019 (eNeuro) measured the adult giant fiber, one of the
  thickest axons in the fly (7 um), at 2.07 m/s. Main value: 0.2 m/s;
  0.129 and 2.07 m/s run as slow and fast bounds.

**What positions exist for snapshot 630.** Our data have no synapse
positions, so the distance used is the straight line between the two neurons'
"anchor" points (a point on each neuron's main branch, from the FlyWire
annotation table, Schlegel et al. 2024): 127,322 of 127,400 neurons have one.
Cell-body positions exist for 115,562 (sensory neurons have none: their cell
bodies are outside the brain). Two anchor points lie far outside the brain
(apparently stored in the wrong units) and are ignored; 80 neurons have no
position at all, and their 6,454 connections get the median distance. A
straight line is shorter than the real wire, so travel times are if anything
under-estimated; the 0.129 m/s run is equivalent to a wire 1.5x longer than
the straight line at 0.2 m/s.

**Resulting delays** (`results/delay_stats.json`): median distance between
connected neurons 92 um (95% under 236 um). Delays at 0.2 m/s: median
2.3 ms, 95% under 3.0 ms, longest 4.9 ms (baseline: all 1.8 ms). At
0.129 m/s: median 2.5 ms, longest 6.6 ms. At 2.07 m/s: nearly all 1.8-1.9 ms.

**Result: the baseline still holds; very little changes.**

| MN9 (opposite side), Hz, mean of 90 trials | baseline | delays ON | paper |
|---|---|---|---|
| sugar 100 Hz | 67.3 | 71.1 | 65.7 +/- 3.3 |
| sugar 200 Hz | 93.5 | 93.3 | 93.2 +/- 5.2 |
| water 200 Hz | 30.8 | 31.0 | 30.7 |
| bitter 200 Hz alone | 0.0 | 0.0 | 0.0 |
| sugar 100 + bitter 120 Hz | 1.4 | 1.4 | 1.5 |
| sugar 200 + Ir94e 200 Hz (150 trials) | 63.6 | 64.2 | 64.3 |

* Every Phase 3 check holds on every seed.
* Sugar 100 Hz drives MN9 about 6% harder (+3.9 Hz; the three seeds agree
  within about 1 Hz, so this small rise is real). Everything else moves by
  less than the seed-to-seed noise.
* Neuron by neuron: correlation with the baseline 0.9988-1.0000 (noise
  floor 0.9999-1.0000); 49-50 of the 50 most active neurons are the same.
  With sugar 100 Hz, 44 extra neurons fire at all (465 vs 425), all weakly.
* Runaway (sugar 200 + Ir94e 200 Hz): 6 of 150 trials vs 5 of 150 in the
  baseline (Fisher test p = 1.0): no detectable change.

In plain English: signals now take a realistic, distance-dependent time to
arrive (half a millisecond longer on average). The brain's responses are
almost identical, which is reassuring: the paper's results do not depend on
the unrealistic "everything takes exactly 1.8 ms" simplification.

**Variants (1 seed x 30 trials each, five main conditions).** The result
does not depend on the chosen speed or on which point of the neuron is used:

| MN9 (opposite side), Hz, seed 0 | baseline | 0.2 m/s (main) | 0.129 m/s (slow) | 2.07 m/s (fast) | 0.2 m/s, cell-body distances |
|---|---|---|---|---|---|
| median delay | 1.8 ms | 2.3 ms | 2.5 ms | 1.8 ms | 2.4 ms |
| sugar 100 Hz | 68.2 | 70.6 | 71.5 | 68.5 | 70.7 |
| sugar 200 Hz | 94.7 | 95.4 | 94.1 | 93.6 | 94.3 |
| water 200 Hz | 29.7 | 30.7 | 30.3 | 30.9 | 29.6 |
| bitter 200 Hz | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| sugar 100 + bitter 120 Hz | 1.3 | 1.3 | 1.4 | 2.0 | 1.8 |

All six checks that these runs cover hold for every variant (the runaway
condition was not run for the variants). Neuron by neuron against the
baseline: correlation 0.997-1.000 and 48-50 of the top 50 for all three. The
longer the delays, the slightly larger the rise at sugar 100 Hz (fast
+0.3 Hz, main +2.4 Hz, slow +3.3 Hz on this seed), which fits a real but
small effect of timing. The cell-body variant uses distances between cell
bodies (median 114 um instead of 92 um); sensory neurons have no cell-body
position and fall back to their anchor point.

## Upgrade 2: conductance-based synapses

**What the baseline does.** One synapse always pushes the voltage by the same
amount (0.275 mV of input per synapse), whatever the voltage already is. So a
strongly inhibited neuron can be pushed to absurd voltages (hundreds of mV
below rest), and excitation never "fills up".

**What real synapses do.** A synapse opens ion channels. The current through
them is proportional to the distance between the voltage and the channel's
*reversal potential*, the voltage where that channel stops pushing:

* Acetylcholine (excitatory) opens nicotinic receptors, which pass positive
  ions and reverse near 0 mV (Lee & O'Dowd 1999 J Neurosci 19:5311;
  +8.9 +/- 1.7 mV in cultured Drosophila Kenyon cells, Su & O'Dowd 2003
  J Neurosci 23:9246). We use 0 mV.
* GABA (Rdl receptors) and glutamate (GluCl, Liu & Wilson 2013 PNAS
  110:10294) open chloride channels. Measured reversal potentials in fly
  neurons: -50 to -60 mV in larval central neurons (Rohrbough & Broadie 2002
  J Neurophysiol 88:847), -45 to -50 mV in adult l-LNv clock neurons
  (McCarthy et al. 2011 J Neurosci 31:8181), -37 mV in cultured Kenyon cells
  (Su & O'Dowd 2003). All are whole-cell recordings, where the pipette sets
  the chloride level, so the true value inside a living fly is uncertain. We
  use -60 mV (the most negative published fly value we found); -70 mV (a
  common modelling choice, not a fly measurement) is run as a variant.

**The weight rescaling, written out.** The model keeps the baseline's
connections and synapse counts; only how each synapse acts changes. The rule:
*one synapse must move a neuron that sits at rest (-52 mV) exactly as much as
in the baseline*. In the conductance model the push of a synapse at rest is
(conductance) x (reversal potential - rest), so

* excitatory conductance per synapse = 0.275 mV / (0 - (-52) mV) = 0.00529
* inhibitory conductance per synapse = 0.275 mV / (-52 - (-60) mV) = 0.0344

(in units of the neuron's own resting "leak" conductance). This is the fair
starting point because it changes nothing for a single small input at rest
(tests/test_realism.py checks this); everything that differs comes from the
voltage moving. Note what it implies: because chloride channels reverse only
8 mV below rest, matching their push at rest needs a large conductance
(6.5x the excitatory one per synapse). Large inhibitory conductances *shunt*:
they short-circuit excitation arriving at the same time, and near threshold
(-45 mV) their push is almost twice the baseline's (15 mV vs 8 mV of driving
force). Excitation, in turn, weakens as the voltage rises toward 0 mV.

**Result: switched on as a drop-in, the upgrade breaks three of the seven
checks.**

| MN9 (opposite side), Hz | baseline (90 trials) | conductance, -60 mV (90) | conductance, -70 mV (30, 1 seed) |
|---|---|---|---|
| sugar 100 Hz | 67.3 | **6.8** (fails: needs >= 20) | 26.1 |
| sugar 200 Hz | 93.5 | 25.6 | 67.5 |
| water 200 Hz | 30.8 | **0.0** (fails) | **0.1** (fails) |
| bitter 200 Hz alone | 0.0 | 0.0 | 0.0 |
| sugar 100 + bitter 120 Hz | 1.4 | 0.1 | 0.1 |
| sugar 200 + Ir94e 200 Hz (150 trials) | 63.6 | **0.0** (fails: abolished) | not run |
| runaway trials (of 150) | 5 | 0 | not run |

The yes/no pattern is still there for sugar (sugar drives MN9, more sugar more,
bitter blocks it), but the feeding neuron barely fires at 100 Hz sugar, water
no longer reaches it at all, and Ir94e now abolishes the sugar response
instead of lowering it. Neuron by neuron: correlation with the baseline
0.81-0.99, 33-46 of the top 50 (lowest for the sugar conditions): many
neurons of the sugar pathway fall silent.

**Why (diagnosis, 1 seed x 30 trials of sugar 100 Hz).** Each half of the
upgrade was switched on alone by giving the other reversal potential an
absurdly far value (so it behaves like the baseline):

| sugar 100 Hz, MN9 Hz | |
|---|---|
| baseline | 68.2 |
| only excitation conductance-based ("fills up" toward 0 mV) | 53.3 |
| only inhibition conductance-based (reverses at -60 mV) | 25.0 |
| both (the upgrade) | 6.9 |

So both halves weaken the pathway and together they compound; the inhibitory
half does more damage. That fits the rescaling note above: with chloride
reversing only 8 mV below rest, a rest-matched inhibitory synapse needs a large
conductance, which shunts excitation and pushes almost twice as hard near
threshold. With -70 mV (smaller conductance) sugar 100 Hz recovers to 26 Hz,
but water still fails.

**Is the upgrade wrong, or does it need tuning? What was tried.**

1. *Rest-matched rescaling* (above): fails 3 checks.
2. *Re-fitting the one global synapse strength*, the same knob Shiu et al.
   fitted for the baseline (one multiplier on every synapse, target: sugar
   100 Hz -> 65.7 Hz as in the paper; seed 900, 15-30 trials per step):

   | multiplier | MN9 at sugar 100 Hz | what the network does |
   |---|---|---|
   | 1.0 | 6.5 Hz | quiet |
   | 2.0 | 54.2 Hz | best value |
   | 2.38 | 52.4 Hz | twice the baseline's total activity (median 20,261 spikes per trial) |
   | 4.0 | 16.3 Hz | MN9 falls; the run took 18x longer than at 1.0, a sign of far more activity (spike counts were not saved for this step) |

   The target is never reached: past about 2x, stronger synapses make the
   whole network busier instead of driving MN9 harder (probably because the
   extra activity includes more inhibition onto the feeding pathway; this was
   not tested). The fit stopped at 2.0.
3. *All checks at the best multiplier (2.0), 3 seeds x 30 trials:*

   | | baseline | conductance, 2x | runaway trials (baseline -> 2x) |
   |---|---|---|---|
   | sugar 100 Hz, MN9 Hz | 67.3 | 52.6 | 0 -> **2** of 90 |
   | sugar 200 Hz | 93.5 | 71.7 | 0 -> **2** |
   | water 200 Hz | 30.8 | 20.6 | 0 -> **19** |
   | bitter 200 Hz alone | 0.0 | 0.0 | 0 -> **4** |
   | sugar 100 + bitter 120 Hz | 1.4 | 4.4 | 0 -> 0 |
   | sugar 200 + Ir94e 200 Hz | 63.6 | 13.7 | 3 -> 5 |
   | total spikes per trial (median), water | 7,512 | 22,024 | |

   All seven MN9 checks now pass on every seed (Ir94e only just: 12.4 Hz on
   the worst seed against a 10 Hz bar; it now removes 81% of the sugar
   response instead of 32%). But the price is a different, unstable brain:
   it runs away with water, bitter or sugar alone, which the baseline never
   does in these trials (0 of 450); even the median trial has more total
   activity than the baseline (1.1x for sugar 200 Hz, 1.8x for bitter, 2.9x
   for water); and neuron by neuron it resembles
   the baseline less (correlation 0.64-0.95, 34-45 of the top 50; water
   lowest).

   Are these new runaways the Phase 6 antennal-lobe loop? The same trials
   (same seed, same input spikes) were re-run with the 38 eLNs silenced
   (`eln_silence_test.py`, `results/eln_silence_test.csv`, 1 seed each):
   water 7 -> 2 runaways of 30, bitter 2 -> 0 of 30. So most of them go
   through the eLN loop, but not all: 2 water runaways remain, so the 2x brain has at least
   one other way to ignite. Silencing the eLNs does not lower the raised
   everyday activity (water: median 20,352 spikes per trial, still 2.7x the
   baseline).

**Verdict: not usable yet; it needs more than a single retune.** The physics
of the upgrade is right (real synapses do have reversal potentials, and the
measured values were used), but the baseline's single synapse strength was
fitted for the simpler model, and one global multiplier cannot restore both
the feeding result and a stable network. Getting there would need separate
strengths for excitation and inhibition, or per-cell-type values, and a
better estimate of the chloride reversal potential inside a living fly
brain; that is beyond a drop-in switch and was not attempted. Because it did
not pass, upgrade 2 was not stacked with upgrades 1 and 3.

## Upgrade 3: spike-frequency adaptation

**What the baseline does.** A neuron given a steady push fires at a steady
rate for ever.

**What real fly neurons do.** Many slow down during a long push. In cultured
Drosophila central neurons given 600 ms current steps at 2-3x their threshold,
32% of wild-type neurons were "adaptive", defined as the last firing rate
being below 0.7x the first (Zhao & Wu 1997, J Neurosci 17:2187). One
mechanism is the calcium-activated potassium channel SK, which Drosophila
neurons have (dSK; Abou Tayoun et al. 2011, J Neurosci 31:13897); in
Drosophila sensory neurons SK channels produce firing pauses of about 100 ms
(median 104 ms, 47 ms with SK knocked down; Onodera et al. 2017, eLife
6:e29754).

**What the model does.** Every spike adds a small "brake" current that fades
with a 100 ms time constant. Its size per spike was calibrated, not guessed:
0.974 mV per spike is the value at which one model neuron, given the Zhao & Wu
protocol (600 ms step at 2.5x threshold), slows from 76 Hz to 53 Hz, i.e. to
exactly 0.7x (the boundary of "adaptive"). Variants: half that strength
(ratio 0.82), and a 300 ms time constant re-calibrated to the same 0.7 ratio
(0.312 mV per spike). Caveats: no fly measurement of the adaptation time
constant of central brain neurons was found (100 ms comes from SK-driven
pauses in fly sensory neurons); the strength comes from cultured neurons; and
the same adaptation is given to every neuron, although only about a third of
fly neurons adapt this strongly (cell-type-specific values are upgrade 4).
The stimulated taste neurons are driven by the stimulus protocol (each input
kick makes them fire), so adaptation does not change their input rates.

**Result: the baseline still holds, but every response is weaker.**

| MN9 (opposite side), Hz, mean of 90 trials | baseline | adaptation ON | delays + adaptation |
|---|---|---|---|
| sugar 100 Hz | 67.3 | 43.9 | 45.3 |
| sugar 200 Hz | 93.5 | 67.0 | 69.6 |
| water 200 Hz | 30.8 | 11.0 | 10.0 |
| bitter 200 Hz alone | 0.0 | 0.0 | 0.0 |
| sugar 100 + bitter 120 Hz | 1.4 | 3.2 | 3.6 |
| sugar 200 + Ir94e 200 Hz (150 trials) | 63.6 | 32.0 | 31.9 |
| runaway trials (of 150) | 5 | 0 | 0 |

* Every Phase 3 check holds on every seed, for adaptation alone and for
  delays + adaptation together.
* MN9 fires about a third less (sugar 100 Hz: 67 -> 44 Hz; the three seeds
  agree within 0.4 Hz). Water is hit hardest (31 -> 11 Hz, still well above
  the 5 Hz check). This is expected: adaptation brakes every neuron that
  fires for a long time, and the path from the taste neurons to MN9 is a
  chain of such neurons.
* Bitter still blocks sugar, but a little less completely: MN9 keeps 7% of
  its sugar-alone rate (3.2 of 43.9 Hz) against 2% in the baseline (1.4 of
  67.3 Hz); the check allows 10%.
* Ir94e still lowers the sugar response, and relatively more than in the
  baseline (MN9 keeps 48% of the sugar 200 Hz rate against 68%).
* Neuron by neuron: correlation with the baseline 0.947-0.991 (noise floor
  0.9999-1.0000); 38-47 of the 50 most active neurons are the same. So the
  same neurons respond, but their relative strengths shift more than with
  delays. Delays + adaptation against delays alone: 0.934-0.991, 38-47.
* Runaway: 0 of 150 trials against 5 of 150 in the baseline (95% range for
  the true rate 0-2.5%; Fisher test p = 0.06, so on its own this falls just
  short of the usual 0.05 bar). See "Runaway" below for what this means.

**Variants (1 seed x 30 trials, five main conditions).**

| MN9 (opposite side), Hz, seed 0 | baseline | main (100 ms, 0.97 mV) | half strength (100 ms, 0.49 mV) | slower (300 ms, 0.31 mV) |
|---|---|---|---|---|
| sugar 100 Hz | 68.2 | 43.8 | 54.0 | 47.8 |
| sugar 200 Hz | 94.7 | 67.9 | 79.7 | 72.3 |
| water 200 Hz | 29.7 | 11.9 | 19.5 | 13.8 |
| bitter 200 Hz | 0.0 | 0.0 | 0.0 | 0.0 |
| sugar 100 + bitter 120 Hz | 1.3 | 2.9 | 2.5 | 2.9 |

All checks these runs cover hold for both variants. The size of the drop
scales with the strength of adaptation, as it should: half the strength gives
a little more than half the drop (about 57% of it, in all three sugar and
water conditions). Neuron by neuron against the baseline: half strength
0.983-0.997 (42-48 of the top 50), 300 ms 0.955-0.993 (39-47).

Both variants were also run on the runaway condition (sugar 200 + Ir94e
200 Hz, 5 seeds = 150 trials each): MN9 43.8 Hz (half strength) and 34.8 Hz
(300 ms) against 63.6 Hz in the baseline and 32.0 Hz with the main setting,
and 0 runaway trials for both (see "Runaway" below).

In plain English: once neurons are allowed to "tire" during a long input, as
many real fly neurons do, the sugar -> feeding result survives: sugar still
drives the feeding motor neuron, more sugar drives it harder, water drives it
weakly, bitter blocks it. The numbers get smaller, so the exact firing rates
the paper reports depend on the model having no adaptation; the yes/no
behaviours do not. How much smaller is uncertain, because the strength and
speed of adaptation in fly central brain neurons have not been measured
directly (see caveats above).

## Runaway activity: what each upgrade does to it, and why

"Runaway" = a trial of sugar 200 + Ir94e 200 Hz in which the whole brain
ignites (more than 5x the baseline's median spike count). Phase 6
(`docs/phase6-runaway-activity.md`) traced every baseline runaway to about 40
antennal-lobe local neurons (types lLN1_b/c and lLN2T) that the model treats
as excitatory. Whether that is a wrong transmitter label (the olfaction lane:
they are GABAergic) or missing electrical synapses (FlyWire lists them as
cholinergic) is not settled, but either way it is a problem with how the
model treats those neurons. **None of upgrades 1-3 changes any neuron's sign
or wiring, so none of them can fix that problem.** Any change in the runaway
rate is therefore either a side effect that hides it (masking), or noise.

| | runaway trials | 95% range | vs baseline (Fisher) |
|---|---|---|---|
| baseline | 5 / 150 | 1.4-7.6% | |
| baseline, 3 new seeds (noise check) | 2 / 90 | 0.6-7.7% | p = 0.71 |
| upgrade 1: delays | 6 / 150 | 1.8-8.5% | p = 1.0 |
| upgrade 2: conductance, as drop-in | 0 / 150 | 0-2.5% | p = 0.06 |
| upgrade 2: conductance, synapses 2x | 5 / 90 | 2.4-12.4% | p = 0.51 |
| upgrade 3: adaptation (main) | 0 / 150 | 0-2.5% | p = 0.06 |
| upgrade 3, half strength | 0 / 150 | 0-2.5% | p = 0.06 |
| upgrade 3, 300 ms time constant | 0 / 150 | 0-2.5% | p = 0.06 |
| upgrades 1 + 3 | 0 / 150 | 0-2.5% | p = 0.06 |

Each adaptation setting alone falls just short of the usual p < 0.05 bar, but
all three settings give 0 runaways; pooled, 0 of 450 against 5 of 150 has
p = 0.001. So adaptation really does make runaway rarer.

To tell "harder to set off" apart from "the loop is gone", the two forced
triggers that ignite the baseline brain every time in Phase 6 (10 DM1 smell
neurons firing once; the eLNs firing once; no other input, so each is a single
exact run) were repeated with every upgrade (`trigger_test.py`,
`results/trigger_test.csv`):

| total spikes in the second after the trigger | 10 DM1 smell neurons fire once | 38 eLNs fire once |
|---|---|---|
| baseline | 444,790 (ignites) | 664,857 (ignites) |
| upgrade 1: delays | 447,185 (ignites) | 719,431 (ignites) |
| upgrade 2: conductance, drop-in | 164,127 (ignites) | 300,019 (ignites) |
| upgrade 2: conductance, synapses 2x | 358,629 (ignites) | 735,213 (ignites) |
| upgrade 3: adaptation (main) | 297,401 (ignites) | 464,698 (ignites) |
| upgrade 3, half strength | 359,593 (ignites) | 548,292 (ignites) |
| upgrade 3, 300 ms | 319,554 (ignites) | 496,845 (ignites) |
| upgrades 1 + 3 | 302,088 (ignites) | 465,187 (ignites) |

(The baseline numbers are exactly Phase 6's, which confirms the test is the
same. When the loop is cut, Phase 6 got 26-30 spikes from the DM1 trigger.)

**Verdict for each upgrade, as the coordinator asked (the upgrade itself, or
masking the sign problem?):**

* **Upgrade 1 (delays):** no change in runaway (6 vs 5 of 150), and the loop
  ignites as before. Nothing to explain.
* **Upgrade 2 as a drop-in (0 of 150): masking.** It weakens the whole network
  so much that the feeding result itself fails; a single forced kick still
  ignites the brain.
* **Upgrade 2 with 2x synapses: the upgrade itself adds instability.** Runaway
  in the Ir94e condition is about the same (5 of 90 against 3 of 90 on the same
  seeds), but the brain now also runs away with water, bitter or sugar alone,
  which the baseline never does. Silencing the eLNs removes most of those
  (water 7 -> 2, bitter 2 -> 0 of 30): stronger synapses make the existing
  eLN loop much easier to set off, and at least one other route to ignition
  appears as well. Either way it is a side effect of the upgrade plus retune,
  not a correction of the sign problem.
* **Upgrade 3 (adaptation): masking.** Runaway from natural input disappears
  (0 of 450 over three settings), but a single forced kick to the smell
  neurons or to the eLNs still ignites the whole brain with every setting,
  only about 30% less violently. So the loop Phase 6 found is still there
  (the eLNs are still treated as excitatory); adaptation makes it harder to
  set off, because every neuron that starts firing hard is braked. That is a
  real biological mechanism (Phase 6 noted the model lacked it), but it hides
  the eLN problem rather than fixing it; the fix (correct signs, or electrical
  synapses) is upgrade 4/5 territory and was not attempted here.

## Limitations and what was not verified

* **PRELIMINARY** in the PLAN.md Phase 6 sense: 3 seeds and parameter
  variants, but no independent review.
* Distances are straight lines between anchor points, not wire lengths along
  the real branches (no synapse positions for snapshot 630). Conduction speeds
  come from larval axons and one giant fiber; no adult central-brain value
  was found.
* Chloride reversal potentials come from whole-cell recordings, where the
  pipette sets the chloride level; the value inside a living fly brain is not
  known.
* No fly measurement of the adaptation time constant of central brain neurons
  was found; the same adaptation is given to every neuron, although only about
  a third of cultured fly neurons adapt this strongly.
* Parameter variants were run with 1 seed x 30 trials (the main versions with
  3 seeds). The combinations with upgrade 2 (1+2, 1+2+3) were not run because
  upgrade 2 failed its checks.
* A settings bug was found and fixed during the work: changing one switch left
  the previous configuration's other settings in place. It affected only two
  runs (a diagnostic and the first weight fit), which were deleted and re-run;
  every configuration now starts from the full default settings. Its log is
  kept as `results/log_stage3_ABORTED_settings_leak.txt`.

## Tests

`tests/test_realism.py` (run with `.venv\Scripts\python.exe -m pytest
tests/test_realism.py -m "not slow"`; the whole-brain test with `-m slow`).
Last runs (2026-09-22, after all code changes): `18 passed, 1 deselected`
(fast tests) and `1 passed, 18 deselected` (whole-brain test).
The key ones: with every switch off the new engine gives exactly the
baseline's spikes for the same seed (small random networks, 4 seeds, and the
whole brain); delays match a slow, simple reference implementation exactly;
the conductance integration matches a standard ODE solver; the adaptation
calibration reaches its 0.7 target.

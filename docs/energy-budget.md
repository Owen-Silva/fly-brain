# Energy budget: what one decision costs a fly, a neuromorphic chip and this laptop (PRELIMINARY)

| Decision (1 second of input) | Neurons that fired (of 127,400) | Spikes | Fly brain | Loihi-class chip | This laptop |
|---|---|---|---|---|---|
| Sugar -> feeding (MN9) | 356 (0.28%) | 9,749 | 9.3 nJ (2.9-126) | 6.7 mJ (1.4-66) | 1.9 J (1.5-4.8) |
| Bitter taste | 87 (0.07%) | 6,446 | 4.2 nJ (1.2-50) | 6.6 mJ (1.4-66) | 1.4 J (1.1-2.5) |
| Water taste | 247 (0.19%) | 7,557 | 5.1 nJ (1.5-63) | 6.6 mJ (1.4-66) | 1.9 J (1.5-4.2) |
| Smell: DA1 (the cVA pheromone) | 608 (0.48%) | 27,588 | 20 nJ (6-251) | 6.7 mJ (1.4-66) | 9.8 J (7.8-13) |
| Smell: DM1 | 1,127 (0.88%) | 36,411 | 47 nJ (15-689) | 6.9 mJ (1.5-66) | 18 J (14-18) |
| Grooming (Johnston's organ) | 395 (0.31%) | 22,965 | 14 nJ (4.1-168) | 6.7 mJ (1.4-66) | 4.5 J (3.6-9.7) |
| Temperature: cool | 253 (0.20%) | 6,917 | 7.9 nJ (2.5-111) | 6.7 mJ (1.4-66) | 8.8 J (7-9.3) |
| Temperature: warm | 568 (0.45%) | 10,984 | 18 nJ (5.9-278) | 6.7 mJ (1.4-66) | 19 J (15-20) |
| *Published model, smell DA1* | *8,342 (6.55%)* | *471,405* | *485 nJ (151-6,725)* | *9.5 mJ (2.2-69)* | *41 J (33-70)* |
| *Published model, smell DM1* | *8,283 (6.50%)* | *465,406* | *486 nJ (151-6,763)* | *9.5 mJ (2.2-69)* | *41 J (33-82)* |
| *Published model, cool* | *8,204 (6.44%)* | *444,303* | *471 nJ (147-6,582)* | *9.5 mJ (2.2-69)* | *39 J (32-72)* |
| *Published model, warm* | *8,195 (6.43%)* | *446,747* | *475 nJ (148-6,635)* | *9.5 mJ (2.2-69)* | *41 J (33-68)* |

*Written 2026-09-23. Every number is PRELIMINARY. The top eight rows are the recommended
fixed model ("al_ln_literature"). Taste and grooming give exactly the same spikes on the
published model, so they are not repeated; the four italic rows are where the published
model runs away. Each row is the mean of 40 one-second trials (2 random seeds x 20
trials). Energy: the middle estimate, then the low-high range in brackets. The fly and
chip columns are estimates built from published constants; the laptop column is
measured. Scripts and results: `experiments/energy_budget/`. Figures:
`experiments/energy_budget/results/fig_energy_per_decision.png` and
`fig_runaway_cost.png`.*

**Units.** A joule (J) is a small amount of energy: about what it takes to lift an apple
by one metre. 1 mJ (millijoule) is a thousandth of a joule, 1 µJ (microjoule) a
millionth, 1 nJ (nanojoule) a billionth.

## The short version

- **The fly is absurdly efficient.** One of these one-second decisions costs a real fly
  brain about **4-47 nJ** (middle estimates). Even the widest range is 1-700 nJ.
- **A neuromorphic chip costs about 150,000 to 1.6 million times more.** A
  **neuromorphic chip** is a processor built to work like neurons: it passes spikes
  instead of running a program step by step. On an Intel Loihi-class chip each decision
  costs about **7 mJ**. But **99.6% or more of that is the chip updating all 127,400 model
  neurons at every time step**, whether they do anything or not. The spikes themselves
  cost only 21-244 µJ.
- **This laptop costs another 200 to 2,800 times more than the chip:** **1.4-19 J** per
  decision, measured. That is 200 million to 1.1 billion times the fly.
- **Activity is very sparse.** Only **0.07-0.9%** of the brain's neurons fire at all
  during a decision. Out of every million (neuron, 0.1 ms time step) pairs, only 5-30
  contain a spike.
- **The computing lesson.** A design that updates every neuron and every connection
  every 0.1 ms would do about 150 billion operations per decision. Handling only the
  spikes needs 2-21 million: **3,000-38,000 times less work and energy**. Today's
  Loihi-style chip gets only part of that saving (53 times), because it still updates
  every neuron at every step. Skipping idle neurons as well would save another **60-720
  times**.
- **The runaway's cost.** For smells and temperature, the published model fires **13-64
  times more spikes** than the fixed model. That costs a fly **10-60 times more
  energy**: about **1.9 times the power of the whole living brain**, which a real fly
  could not supply. On the laptop the runaway takes 2-8 times longer. On a Loihi-class
  chip it adds only 40%, because the chip's per-step cost swamps everything else.
- **Feeding is fast.** MN9, the motor neuron that starts feeding, fires its first spike a
  median **41 ms** after sugar input starts (middle half of trials: 34-46 ms).
- **The Sandia paper exists, but has no energy numbers.** Wang et al. (Sandia, 2025) ran
  the whole FlyWire brain on **12 Intel Loihi 2 chips**. The paper's sugar experiment took
  **54 ms per simulated second** (0.1 ms steps), about 19 times faster than real time.
  The paper reports **no power or energy measurement**. Summaries online that say it ran
  at "milliwatt-level power" are not backed by the paper's text. It does give one useful
  cross-check: in its sugar run about 0.3% of neurons fired. We see 0.28%.

## 1. What was simulated

A **decision** here is one second of sensory input and the whole-brain response to it.
Each one drives a set of sensory neurons with random ("Poisson") spikes at a fixed rate.
Every neuron list and rate is reused from an earlier lane; none was chosen for this one.

| Decision | Sensory neurons driven | Rate | Where the list and rate come from |
|---|---|---|---|
| Sugar -> feeding | 21 sugar taste neurons | 100 Hz | the paper's list; rate from `experiments/phase7_signs` |
| Bitter | 21 bitter taste neurons | 200 Hz | the paper's list; `phase7_signs` |
| Water | 18 water taste neurons | 200 Hz | the paper's list; `phase7_signs` |
| Smell DA1 | all 126 DA1 smell neurons, both antennae | 150 Hz | scorecard test FC5 (`scorecard_batch1`) |
| Smell DM1 | all 68 DM1 smell neurons, both sides | 150 Hz | the runaway test in `phase7_signs` |
| Grooming | the 70 JO-C/E neurons (Johnston's organ, the antenna's motion sensor) | 220 Hz | `experiments/heldout` |
| Cool | 9 cool-sensing neurons (TRN_VP3a/b) | 150 Hz | scorecard tests TH1 / TH3 |
| Warm | 7 warm-sensing neurons (TRN_VP2) | 150 Hz | scorecard test TH2 |

Both model versions were run: the **published model** ("none") and the **recommended
fix** ("al_ln_literature", which stops the smell-circuit runaway). Each decision got 20
one-second trials with each of 2 random seeds, on the fast engine, one thread.

## 2. What each decision spends, in activity

Terms used below:

- A **spike** is one electrical pulse from one neuron.
- A **synapse** is one contact where a neuron passes a signal to another. FlyWire counts
  about 52.8 million in this model.
- A **connection** is one sending-to-receiving neuron pair, however many synapses it
  has. There are 14.7 million.
- A **synaptic event** is one spike arriving at one synapse. We count them two ways: each
  spike times the neuron's output synapses (what the fly pays for), and each spike times
  its output connections (what a chip pays for, because a chip stores one weight per
  connection).
- A neuron is **touched** if it got any input at all during the trial, even too little to
  make it fire.

| Decision | Neurons fired, per trial / in any of the 40 | Neurons touched | Spikes (mean ± SD) | Share from the driven sensory neurons | Synaptic events (synapses) | Synaptic events (connections) |
|---|---|---|---|---|---|---|
| Sugar | 356 / 421 | 10,719 (8%) | 9,749 ± 309 | 21% | 12.2 M | 1.48 M |
| Bitter | 87 / 93 | 5,799 (5%) | 6,446 ± 131 | 64% | 4.6 M | 0.87 M |
| Water | 247 / 394 | 10,943 (9%) | 7,557 ± 251 | 47% | 5.8 M | 1.01 M |
| Smell DA1 | 608 / 901 | 32,166 (25%) | 27,588 ± 1,152 | 68% | 23.5 M | 3.89 M |
| Smell DM1 | 1,127 / 1,415 | 38,591 (30%) | 36,411 ± 1,826 | 28% | 68.6 M | 10.3 M |
| Grooming | 395 / 517 | 22,866 (18%) | 22,965 ± 217 | 66% | 15.3 M | 3.02 M |
| Cool | 253 / 336 | 20,268 (16%) | 6,917 ± 214 | 19% | 11.0 M | 1.52 M |
| Warm | 568 / 941 | 47,322 (37%) | 10,984 ± 377 | 10% | 28.0 M | 4.09 M |
| DA1, published | 8,342 / 8,810 | 97,573 (77%) | 471,405 ± 603 | 4% | 657 M | 123 M |
| DM1, published | 8,283 / 8,756 | 98,027 (77%) | 465,406 ± 637 | 2% | 662 M | 123 M |
| Cool, published | 8,204 / 8,707 | 98,022 (77%) | 444,303 ± 1,396 | <1% | 645 M | 120 M |
| Warm, published | 8,195 / 8,713 | 97,860 (77%) | 446,747 ± 1,110 | <1% | 650 M | 121 M |

"M" means million. "Touched" is the mean of 3 trials per decision (`neurons_touched.csv`).

- The two seeds agree closely. The largest gap between the two seed means is 2.0%
  (spikes, water).
- An average spike reaches 670 synapses (grooming) to 2,550 (warm), and 1,250 for
  sugar. The brain-wide average is 414 output synapses per neuron, so the neurons that
  fire tend to be the well-connected ones.
- **Feeding (MN9).** With sugar, MN9 fires at 68 spikes per second. Its first spike comes
  a median **41.4 ms** after input starts (middle half of trials 34.1-46.1 ms). The MN9 on
  the other side starts at 44.2 ms. With water, MN9 fires at 31 per second, first spike
  at a median 70.5 ms. Both model versions are identical here.
- **Grooming read-out.** aBN1, the grooming brain neuron, fires at 73 per second and
  starts after a median 14 ms.

## 3. Energy, three ways

### a) The fly

Energy = spikes x (cost of one spike) + synaptic events x (cost of one synaptic event).
Costs are counted in **ATP**, the molecule cells spend as fuel, then turned into joules.

| Constant | Low | Middle | High | Basis |
|---|---|---|---|---|
| Na+ charge per spike, per cm² of membrane | 65 nC | 130 nC | 200 nC | Sengupta et al. 2010: efficient spikes run 65 nC/cm² (mouse relay neuron) to "below 200" (bee Kenyon cell, rat interneurons). 1,098 nC/cm² costs 2.3x10^12 ATP/cm², so 1 nC = 2.1x10^9 ATP. |
| Membrane one spike charges | 500 µm² | 1,000 µm² | 2,000 µm² | **Our assumption.** FlyWire has 149.2 m of neurite in 139,255 neurons: 1.07 mm each. Times pi x an assumed mean branch width of 0.15-0.6 µm. |
| = ATP per spike | 0.68 million | 2.7 million | 8.4 million | the two rows above multiplied |
| ATP per synaptic event | 2,400 | 6,100 | 82,000 | Attwell & Laughlin 2001: 164,000 ATP per released vesicle (mammal, mostly the receiving side's currents), release probability 0.25. A fly release site feeds 6.7 partners on average (hemibrain count), and FlyWire counts each partner as a synapse. Low/middle: one vesicle shared by 6.7 partners, release probability 0.1/0.25. High: a full mammalian vesicle per partner, release probability 0.5. |
| Joules per ATP | 7.8x10^-20 | 9.1x10^-20 | 1.2x10^-19 | 47-70 kJ per mole of ATP in living cells (Milo & Phillips); middle 55 kJ/mol |

- **Synapses dominate.** At the middle values, spikes are 15-40% of the fly's cost and
  synaptic events the rest.
- **Per event, in joules:** one spike's own cost is 0.05-1 picojoule (pJ, a millionth of a
  µJ). One synaptic event is 0.2-10 femtojoules (fJ, a thousandth of a pJ).
- **Low and high rows in the table** use all-low and all-high constants together, so the
  bracket is the widest possible.

**Sanity check against the real fly.** An explanted adult fly brain gives off about
**256 nW** (billionths of a watt) of heat (Panda et al. 2026, direct calorimetry, room
temperature). So it uses about 256 nJ in each second. A whole fly uses about 34-51 µW
(Piper et al. 2014: 43-65 mW per gram, 0.78 mg flies).

- Each fixed-model decision needs 1.6-18% of the brain's total power (middle
  estimates). That is plausible: the brain also pays to stay alive and ready.
- The published model's runaway needs **184-190%** of the whole brain's measured
  power, before any resting cost. A real fly could not do this. This is independent
  evidence that the runaway is a model fault, not biology.
- The same constants say the brain's 256 nW could pay for, at most, about **4 spikes
  per neuron per second** on average (0.4-15 across the constants' range), with nothing
  left over for keeping cells alive. At the high constants the brain could afford less
  than one spike per neuron every two seconds, which seems too little for a working
  brain. So the middle and low constants look more plausible than the high end. This is
  a judgement: we found no measured average firing rate for the whole fly brain.

### b) Neuromorphic chips

A chip works in **time steps**. Loihi updates every neuron once per step. It spends
energy on a synaptic operation only when a spike arrives at a connection: it is
**event-driven** for synapses and **clock-driven** for neurons. So:

Chip energy = neurons x time steps x (energy per neuron update) + connection events x
(energy per synaptic operation).

| Chip | Published per-operation energy | Source |
|---|---|---|
| Intel Loihi (2018) | 23.6 pJ per synaptic operation; 52 pJ per idle neuron update, 81 pJ per active one | Davies et al. 2018, Table 2 (pre-silicon figures at 0.75 V) |
| Intel Loihi 2 | **Not published per operation.** Our derived upper bounds: 6.8 pJ per synaptic op, 10.8 pJ per neuron op | Hala Point system (1,152 Loihi 2 chips): at most 2,600 W, 380 trillion synaptic ops/s, 240 trillion neuron ops/s |
| IBM TrueNorth | 26 pJ per synaptic event; 63-70 mW per chip in real time | Merolla et al. 2014; 26 pJ from Akopyan et al. 2015, as quoted by Kim et al. 2018 |
| SpiNNaker | 20 nJ (early chip-level figure) to 0.6 µJ (whole machine, real time) per synaptic event | Rhodes et al. 2020 |
| SpiNNaker2 | No per-event energy published | Scholze et al. 2026 |
| GPU, for reference | 0.3-0.47 µJ per synaptic event | Knight & Nowotny 2018, via Rhodes et al. 2020 |

**How the "Loihi-class chip" column is built:**

- Middle: Loihi (2018) constants at 1 ms steps (the faster of the two steps Sandia used).
- High: Loihi (2018) constants at the model's own 0.1 ms step.
- Low: the Loihi 2 upper bounds at 1 ms steps.

**Energy per decision on each chip (fixed model, synaptic events only unless stated):**

| Decision | Loihi, spikes part only | TrueNorth, spikes part only | SpiNNaker | GPU |
|---|---|---|---|---|
| Sugar | 35 µJ | 39 µJ | 30 mJ - 0.9 J | 0.45-0.70 J |
| Smell DM1 | 244 µJ | 268 µJ | 0.21-6.2 J | 3.1-4.9 J |
| Smell DM1, published | 2.9 mJ | 3.2 mJ | 2.5-74 J | 37-58 J |

The per-step neuron updates add 6.6 mJ (1 ms steps) or 66 mJ (0.1 ms steps) on Loihi.

- **These are operation energies only.** A real chip also draws idle ("static") power.
  Intel has not published that per chip.
- **A ceiling from the Sandia run.** 12 chips x Hala Point's maximum 2.26 W per chip,
  times their measured 54 ms (0.1 ms steps) or 12.4 ms (1 ms steps) per simulated
  second, gives 1.46 J or 0.34 J for the sugar decision. That is an upper bound at full
  power. The true figure lies somewhere between this ceiling and our operations-only
  6.7 mJ. Nobody has measured it yet.
- **SpiNNaker and GPU figures** are whole-system energy divided by synaptic events, from
  a busy cortex model. They overstate the cost of a sparse decision's events and leave
  out the machine's idle draw. Treat them as rough.

**Does the whole fly brain fit on one chip?** The model has 127,400 neurons (the full
FlyWire brain: 139,255), 14.7 million connections and 52.8 million synapses. The most
inputs any neuron takes is 10,356 connections (Sandia's count).

| Chip | One chip holds | Fits? |
|---|---|---|
| Loihi (2018) | 131,072 neurons in 128 cores; per core at most 128 KB of synapse memory and 4,096 input routes | **No.** The neuron count just squeezes in, but each core's input memory cannot hold the fly's wiring. Sandia fitted about 97 fly neurons per Loihi 2 core. At that density Loihi (2018) would need about 12 chips. This is our extrapolation, not a test. |
| Loihi 2 | up to 1 million neurons (8,192 per core) | **No, in practice.** Sandia needed 12 chips (1,440 cores), because of memory limits on each neuron's inputs and outputs. |
| TrueNorth | 1 million neurons, 256 million on/off synapses, at most 256 inputs per neuron | **No.** Fly neurons need up to 10,356 inputs. Each one would have to be split into trees of helper neurons, and no such mapping is published. |
| SpiNNaker | 18 small processor cores, under 1 W | **No.** A 48-chip board ran up to 250,000 neurons and 81 million synapses (Stromatias et al. 2013), so one board is about the right size. |
| SpiNNaker2 | more than 150,000 neurons and 1.8 billion synaptic events per second; 158.6 Mbit (about 20 MB) of on-chip memory | **Neurons yes, wiring no.** 14.7 million connections at 2-4 bytes each is 30-60 MB, so it would need the chip's external memory. This has not been demonstrated. |

**The Sandia paper, checked.** Wang, Theilman, Rothganger, Severa, Vineyard and Aimone
(Sandia National Laboratories), *Neuromorphic Simulation of Drosophila Melanogaster
Brain Connectome on Loihi 2*, arXiv:2508.16792, August 2025.

- **Confirmed.** It runs the FlyWire whole brain on Loihi 2: about 140,000 neurons, with
  the 50 million synapses condensed into about 15 million weighted connections. It copies
  the model of the paper we reproduce: 20 ms membrane time constant, 5 ms synapse time
  constant, 2.2 ms refractory period, 1.8 ms delay.
- **Chips.** The full, unmodified connectome fits on 12 chips (1,440 cores). A second
  method needed 20 chips and a slightly modified connectome. The system used is a Kapoho
  Point board (32 chips).
- **Their sugar input was 150 Hz, ours is 100 Hz**, so their sugar run is somewhat busier
  than ours.
- **Speed.** Wall time per simulated second of the sugar experiment:

  | System | Wall time per simulated second |
  |---|---|
  | Brian2 (the usual research simulator) | 4,419 ms |
  | STACS (another simulator) | 2,656 ms |
  | Loihi 2, 0.1 ms steps | 53.76 ms |
  | Loihi 2, 1 ms steps | 12.40 ms |

- **Speed falls as activity rises.** At an average background of 40 Hz, Loihi 2 needs
  5.8 s per simulated second. The paper says the speed-up is largest when activity is
  sparse, and reaches "over 100x" versus Brian2.
- **Energy.** None measured or reported; the words "power" and "energy" never refer to
  a measurement in the text. So "Sandia put it on Loihi 2" is right. Any energy number
  for that run, including this lane's, is an estimate.

### c) This laptop

Energy = measured wall time per simulated second x CPU power.

- **The machine.** Intel Core i3-1215U: 2 performance cores and 4 efficient cores. Intel
  states a processor base power of 15 W (maximum turbo power 55 W).
- **Power measured.** Windows' built-in CPU energy meter (Intel's "RAPL" package
  counter) was logged every second during every run. It read **about 12.0 W** on
  average, because other lanes kept the CPU near its power limit throughout.
- **Middle:** the fastest time seen x 15 W. **Low:** fastest time x the measured 12.0 W.
  **High:** the typical time in a back-to-back timing pass of both models x 15 W.
- **Timings.** Simulating one second takes the engine 0.09-1.25 s on the fixed model:
  faster than real time. It takes 2.6-2.7 s on the published runaway. For sugar the
  engine is about 35 times faster than Sandia's Brian2 figure, and Loihi 2 is about 2.3
  times faster again.
- **What the engine's time follows.** It tracks the number of **touched** neurons, not
  spikes. The fast engine keeps updating any neuron that has received input. The fixed
  model's "warm" decision fires only 11,000 spikes but touches 47,000 neurons, so it is
  one of the slowest.
- **Not included:** the rest of the laptop (screen, memory, power supply).
- **Contention.** Other lanes made the same work up to about 2.5 times slower at busy
  moments, which is why the high end exists. If only this job's share of the busy CPU
  time is charged, the fixed-model decisions cost 0.5-3.4 J instead.

## 4. The runaway's cost (published model / fixed model)

| Smell or temperature | Spikes | Neurons that fired | Synaptic events | Fly energy | Loihi, spikes part | Loihi, total (1 ms steps) | Laptop time |
|---|---|---|---|---|---|---|---|
| DA1 | 17x | 14x | 28x | 24x | 32x | 1.4x | 4.2-5.5x |
| DM1 | 13x | 7.3x | 9.7x | 10x | 12x | 1.4x | 2.3-4.4x |
| Cool | 64x | 32x | 59x | 60x | 79x | 1.4x | 4.5-7.8x |
| Warm | 41x | 14x | 23x | 26x | 29x | 1.4x | 2.2-3.4x |

- In the runaway about 8,200-8,300 neurons (6.5% of the brain) fire about 55 times a
  second each, and 77% of the brain is touched.
- What that means for each platform:
  - **The fly** pays for every extra spike and synapse: 10-60 times more energy.
  - **The laptop engine** pays mainly for touched neurons: 2-8 times more time.
  - **The Loihi-class chip** barely notices (1.4 times), because updating every neuron
    at every step already costs far more than the spikes do.

## 5. The computing lesson in numbers

For each decision on the fixed model, three designs are compared, all using the same
Loihi (2018) per-operation energies:

- **Dense.** Update all 127,400 neurons and all 14.7 million connections at every 0.1
  ms step.
- **Loihi-style.** Update every neuron every step, but touch a connection only when a
  spike crosses it.
- **Fully event-driven.** Update a neuron only when a spike reaches it or it fires.

| Measure (fixed model, 8 decisions) | Value |
|---|---|
| Neurons that fire at all | 0.07-0.9% of the brain |
| Spikes per (neuron x 0.1 ms step) | 5-29 in a million |
| Connection events vs a dense design's per-step connection work | 6-70 in a million |
| Dense: operations / energy per decision | 148 billion / 3.5 J |
| Loihi-style: operations / energy | 1.28 billion / 66 mJ (**53x** less than dense) |
| Fully event-driven: operations / energy | 1.7-21 million / 0.09-1.1 mJ (**3,300-38,000x** less than dense; **61-720x** less than Loihi-style) |
| Share of the Loihi-style energy spent updating idle neurons | 99.6-99.97% |
| The fly: brain's measured total power vs the decision's signalling cost | 5-60x |
| Published runaway, fully event-driven vs dense | only 275x less (vs Loihi-style: 5.4x) |

- **Sparseness is the whole game.** A fly decision involves under 1% of neurons. In a
  typical 0.1 ms step only 0.6-3.6 neurons in the whole brain fire.
- **Where today's chips fall short.** Loihi removes the waste in synapses but keeps
  paying every neuron at every step. For sparse brain activity that step cost is
  99.6% or more of the chip's energy. A design where an idle neuron costs nothing
  would be 60-720 times cheaper again.
- **Biology pays an idle cost too, but a much smaller one.** The fly's always-on cost
  is 5-60 times its decision cost. The chip's is 270-3,200 times (at 0.1 ms steps).
- **Per event, the gap is still huge.** One connection event costs the fly about 0.7-34
  fJ, against Loihi's 23.6 pJ: 700-34,000 times more.
- **What this means for a hybrid computer.**
  - Silicon should skip idle neurons entirely, not just idle synapses.
  - Runaway-like dense activity destroys the event-driven advantage, so the circuit
    must stay sparse.
  - Living neurons already pay only for what they do.

## 6. How far the totals move

Fly energy for sugar and the DM1 smell (fixed model): each constant is moved to its low
and high value while the others stay at the middle (`fly_energy_sensitivity.csv`).

| Changed | Sugar | Smell DM1 |
|---|---|---|
| ATP per spike (low / high) | x0.80 / x1.54 | x0.86 / x1.40 |
| ATP per synaptic event (low / high) | x0.56 / x10 | x0.51 / x11 |
| Joules per ATP (low / high) | x0.85 / x1.27 | x0.85 / x1.27 |
| Model weight per synapse at 80% / 120% (re-simulated, new seed) | x0.51 / x1.33 | x0.73 / x1.33 |

- **The biggest unknown** is the cost of one synaptic event in a fly: how many vesicles
  a spike releases, and how much current each partner gets. It spans more than 30 times.
- **The chip's range** comes mostly from the time step (x10) and Loihi versus Loihi 2
  (up to x5).
- **The laptop's range** comes mostly from other lanes sharing the CPU (up to x2.5).
- **The ratios between platforms and between models** move much less than the absolute
  numbers.

## 7. Checks (PLAN.md Phase 6, steps 1-5)

1. **Seeds and parameters.**
   - Two seeds agree within 1.7% on spike totals.
   - With the weight per synapse at 80% and 120%, sugar spikes change by x0.57 and
     x1.28, and DM1 spikes by x0.71 and x1.35 (fixed model, 10 trials, new seed 21).
   - The fixed model does not run away even at 120%.
2. **Bugs.**
   - With no input, both models give 0 spikes.
   - The same seed gives the same spikes as the main run (48 of 48 re-run trials match).
   - Output synapse and connection counts were recomputed straight from the paper's
     connection file with pandas, grouped by neuron ID. They are identical, and match
     FlyWire's own per-neuron total (52,793,639 synapses).
   - The fix changes the outputs of exactly 137 neurons, all antennal-lobe local
     neurons, and removes 351,448 synapses (0.7%).
   - Sugar drives MN9 at 68 Hz and grooming drives aBN1 at 73 Hz on both models: the
     fix leaves taste and grooming untouched, as intended.
3. **Literature.**
   - The Loihi 2 claim is confirmed (above), with no energy data. Its sugar run had about
     0.3% of neurons active, close to our 0.28%.
   - We found no published energy-per-decision estimate for this whole-brain model.
     The search was not exhaustive.
4. **Biology.**
   - The fixed model's decisions fit inside the brain's measured power budget.
   - The published model's runaway does not fit. It needs about twice the brain's power.
5. **Write-up:** this file and `experiments/energy_budget/log-entry.md`.

## 8. Limits of the model for energy

- **No spontaneous background activity.** With no input the model is silent. A living
  fly brain fires all the time, and much of its measured 256 nW goes on staying alive
  and ready. (In mammal cortex, keeping resting voltages up and cell housekeeping take
  about 34% and 38% of the energy; Howarth et al. 2012.) Our numbers are only the extra
  cost of one decision.
- **No glia.** Glia are the support cells that recycle transmitter and feed neurons.
  They use energy, and none of it is counted.
- **No nerve cord.** The fly's "spinal cord", which actually moves the legs and
  mouthparts, is not in the model, so the motor side of each decision is missing.
- **Every neuron is treated as spiking.** Many fly neurons never spike. They signal with
  graded voltages and leak current all the time, and that cost is not captured here.
- **No vision.** The optic lobes hold more than half of the fly's brain neurons, and
  vision is expensive: in the blowfly the retina alone uses about 8% of the resting
  energy of the whole animal (Niven & Laughlin 2008). With no light input they stay
  silent in these runs.
- **The model's own simplifications.** Synapse counts are used as weights, all synapses
  are equal, and sensory input is a fixed-rate random drive. Energy scales with the spike
  and synapse counts these produce.
- **Constants are estimates.** The fly constants come mostly from mammals, plus a
  membrane-area assumption. The chip constants are for operations only; idle power and
  the host computer are not included.
- **The laptop was shared** with other lanes the whole time.

## 9. Sources

- Sengupta B, Stemmler M, Laughlin SB, Niven JE (2010). Action potential energy efficiency varies among neuron types in vertebrates and invertebrates. *PLoS Comput Biol* 6:e1000840. <https://journals.plos.org/ploscompbiol/article?id=10.1371/journal.pcbi.1000840>
- Attwell D, Laughlin SB (2001). An energy budget for signaling in the grey matter of the brain. *J Cereb Blood Flow Metab* 21:1133-1145. <https://pubmed.ncbi.nlm.nih.gov/11598490/>
  - Its 1.64x10^5 ATP per vesicle is confirmed via Yuan et al. 2018, *Front Comput Neurosci*: <https://www.frontiersin.org/journals/computational-neuroscience/articles/10.3389/fncom.2018.00079/full>
  - Its release probability of 0.25 is confirmed via Engl & Attwell 2015, *J Physiol*: <http://discovery.ucl.ac.uk/1466835/1/tjp6567.pdf>
- Niven JE, Laughlin SB (2008). Energy limitation as a selective pressure on the evolution of sensory systems. *J Exp Biol* 211:1792-1804. Used for the blowfly-retina figure; it gives no per-spike cost we could use. <https://journals.biologists.com/jeb/article/211/11/1792/9506/Energy-limitation-as-a-selective-pressure-on-the>
- Howarth C, Gleeson P, Attwell D (2012). Updated energy budgets for neural computation in the neocortex and cerebellum. *J Cereb Blood Flow Metab* 32:1222-1232. <https://pmc.ncbi.nlm.nih.gov/articles/PMC3390818/>
- Milo R, Phillips R. *Cell Biology by the Numbers*: how much energy is released in ATP hydrolysis. <https://book.bionumbers.org/how-much-energy-is-released-in-atp-hydrolysis/>
- Scheffer LK et al. (2020). A connectome and analysis of the adult Drosophila central brain. *eLife* 9:e57443. 6.7 partners per release site. <https://elifesciences.org/articles/57443>
- FlyWire totals (139,255 neurons, 149.2 m of wiring), reporting Dorkenwald et al. 2024 *Nature*: <https://www.sciencenews.org/article/fruit-fly-brain-connections-traced>
- Panda K et al. (2026). Direct quantification of the metabolic heat output of individual Drosophila brains. *Cell Reports Methods*. <https://pmc.ncbi.nlm.nih.gov/articles/PMC13494548/>
- Piper MDW, Selman C, Speakman JR, Partridge L (2014). Using doubly-labeled water to measure energy expenditure in an important small ectotherm Drosophila melanogaster. *J Genet Genomics*. <https://pmc.ncbi.nlm.nih.gov/articles/PMC4507022/>
- Davies M et al. (2018). Loihi: a neuromorphic manycore processor with on-chip learning. *IEEE Micro* 38(1):82-99. <https://redwood.berkeley.edu/wp-content/uploads/2021/08/Davies2018.pdf>
- Intel (2021). Loihi 2 announcement. <https://www.intc.com/news-events/press-releases/detail/1502/intel-advances-neuromorphic-with-loihi-2-new-lava-software>
- Intel (2024). Hala Point. <https://www.intel.com/content/www/us/en/newsroom/news/intel-builds-worlds-largest-neuromorphic-system.html>
- Wang F, Theilman BH, Rothganger F, Severa W, Vineyard CM, Aimone JB (2025). Neuromorphic simulation of Drosophila melanogaster brain connectome on Loihi 2. arXiv:2508.16792. <https://arxiv.org/abs/2508.16792>
- Merolla PA et al. (2014). A million spiking-neuron integrated circuit with a scalable communication network and interface. *Science* 345:668-673. <https://pubmed.ncbi.nlm.nih.gov/25104385/>
  - 70 mW and 46 billion synaptic operations per second per watt: <https://modha.org/2014/08/breaking-news-one-giant-leap-for-the-synapse-team-one-small-step-for-mankind/>
  - 26 pJ per operation (Akopyan et al. 2015), as quoted by Kim et al. 2018, *Front Neurosci*: <https://www.frontiersin.org/journals/neuroscience/articles/10.3389/fnins.2018.00829/full>
- Stromatias E, Galluppi F, Patterson C, Furber S (2013). Power analysis of large-scale, real-time neural networks on SpiNNaker. IJCNN. <https://research.manchester.ac.uk/en/publications/power-analysis-of-large-scale-real-time-neural-networks-on-spinna/>
  - The 48-chip board detail: <https://explore.openaire.eu/search/publication?articleId=ec_fp7_ict__::419540e14a45b866e283ae78c0674db4>
- Rhodes O et al. (2020). Real-time cortical simulation on neuromorphic hardware. *Phil Trans R Soc A* 378:20190160. <https://pmc.ncbi.nlm.nih.gov/articles/PMC6939236/>
- Scholze S et al. (2026). The SpiNNaker2 chip: a many-core platform for flexible and scalable brain-inspired computing. arXiv:2607.24396. <https://arxiv.org/abs/2607.24396>
- Intel Core i3-1215U specifications. <https://www.intel.com/content/www/us/en/products/sku/226263/intel-core-i31215u-processor-10m-cache-up-to-4-40-ghz/specifications.html>

## 10. Files

All under `experiments/energy_budget/`:

- **Scripts**
  - `common.py`: stimulus lists and helpers.
  - `constants.py`: every literature constant, with its source.
  - `run_decisions.py`: the main runs, with the power log.
  - `validate.py`: the checks in section 7.
  - `timing.py`: the back-to-back laptop timing pass.
  - `analyze.py`: the energy maths and the figures.
- **Results** (in `results/`)
  - `decision_summary.csv`, `energy_per_decision.csv`, `summary.json`.
  - `trials_<model>.csv`: one row per trial.
  - `validation.json`, `sensitivity_wsyn.csv`, `neurons_touched.csv`,
    `laptop_timing.csv`, `fly_energy_sensitivity.csv`, `model_size_<model>.json`.
  - The two figures.
- **`results/raw/`** (about 3 MB, not for git)
  - Per-neuron spike counts.
  - The per-second power logs.
  - Run logs.

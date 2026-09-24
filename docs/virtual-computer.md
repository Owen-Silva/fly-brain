# The virtual hybrid computer, version 1

*Built 2026-09-24. Every number here is **PRELIMINARY**. Times and energies are modeled
from published chip numbers, fits to published measurements and some guesses. Only the
times marked (M) were measured, on this laptop. Nothing ran on real neuromorphic chips,
microcontrollers, GPUs or living cells.*

## The v1 results

Each cell gives **time per task / energy per task / accuracy**. "Hybrid" means the
neuromorphic (brain-like) chip plus a small conventional core (a Cortex-M33, the processor
in the $5 Raspberry Pi Pico 2). The chip is now priced the way real Loihi 2 hardware
behaved (see "What changed"). Chip energies are the middle estimate, with the full range
in brackets.

| Task | Hybrid | CPU only: this laptop | CPU only: M33 | GPU (T4) | Neuromorphic only |
|---|---|---|---|---|---|
| (a) Feeding decision, **400-neuron circuit (now the default)**, 1 s of tasting | 66 ms / 5.0 mJ (0.6-20 mJ) / 100% | 10 ms (M) / 150 mJ / 100% | 694 ms / 21 mJ / 100% | 100 ms / 7 J / 100% | 66 ms / 5.0 mJ / 100% |
| (a) Feeding decision, 36-neuron circuit (option) | 38 ms / 2.8 mJ (0.07-11 mJ) / 100% | 1.1 ms (M) / 16.5 mJ / 98.5% | 64 ms / 1.9 mJ / 98.5% | 100 ms / 7 J / 98.5% | 38 ms / 2.8 mJ / 100% |
| (b) Odour learning: one sniff recognised and learned | 806 µs / 66 µJ (14-241 µJ) / 66.2% | 121 µs (M) / 1.8 mJ / 66.8% | 866 µs / 26 µJ / 66.8% | 50 µs / 3.5 mJ / 66.8% | 786 µs / 65 µJ / 66.2% |
| (c) Exact sum of 50,000 big whole numbers | 1.3 ms / 40 µJ / 100% | 13 µs (M) / 195 µJ / 100% | 1.3 ms / 40 µJ / 100% | 65 µs / 4.5 mJ / 100% | cannot do it |
| (c) Sort 50,000 numbers | 62 ms / 1.9 mJ / 100% | 261 µs (M) / 3.9 mJ / 100% | 62 ms / 1.9 mJ / 100% | 118 µs / 8.3 mJ / 100% | cannot do it |
| (d) All-day odour watch with an exact log (**energy per day**) | **6,400 J** (1,600-26,000) / 95.9% | **259,000 J** / 95.9% | **89 J** / 95.9% | **1.1 million J** / 95.9% | **6,300 J** / 95.9%, no log |
| (e) Name 1 of 8 stimulation patterns | living cells, 59 electrodes: 60 ms / 1.5 J / 95.4% (K); silicon copy of the culture: 5.6 ms / 0.43 mJ / 97.5% | 1.1 ms (M) / 17 mJ / 97.5% | 101 ms / 3.0 mJ / 97.5% | 6.1 ms / 425 mJ / 97.5% | needs the conventional core for its read-out |
| (f) **New: Pong, DishBrain-style** (per second of game; accuracy = share of balls hit) | living cells, 1,024 electrodes: real time / 25 J / 62% (K); silicon copy of the culture: 19 ms / 74 mJ / 99% | not run | a simple controller: 47 µs / 1.0 mJ / 100% | not run | needs the conventional core to run the game |

**Labels.** (M) = time measured on this laptop. Everything else is modeled: counted
operations times the price of each operation. The chip's timing is **fitted** to Sandia's
real Loihi 2 measurements; its idle ("static") power is **derived** from Intel's published
Loihi 2 measurements. (K) = rests on biology settings that are partly guessed. Laptop
energy = measured time x 15 W (an assumed share of its rated power). Accuracies come from
simulating each task. Full table, with every label and v0's numbers next to v1's:
`vhc/results/compare.md`.

**The headline.**
- **The chip's advantage shrank a lot once it was priced like real hardware.** On the
  400-neuron feeding circuit it now uses about **30 times less energy than this laptop**
  (range 8-230 times), down from about 900 times in v0. Against the $5 microcontroller the
  advantage fell from about 96 times to about **4 times** (range 1-32 times).
- **For the smallest jobs, the microcontroller can now win.** At the middle estimate the
  M33 uses less energy than the chip on the 36-neuron circuit (1.9 mJ against 2.8 mJ) and on
  one odour sniff (26 µJ against 66 µJ). The reason: a whole chip leaks power while it
  steps through a tiny circuit.
- **The all-day watch now clearly favours the plain microcontroller**: 89 J a day against
  about 6,400 J (1,600-26,000 J) for the hybrid, because a Loihi-2-sized chip that listens
  all day leaks power all day.
- **The chip is also slower than v0 said**: 66 ms for the 400-neuron decision, against 10 ms
  measured on this laptop.
- **Pong:** read through 1,024 electrodes, the model culture hit 62% of balls (1.9 hits per
  rally). A random paddle hits about 47%. Read through a CL1's 59 electrodes, it did no
  better than random. A silicon copy of the same culture, reading every cell, hit 99%. A
  few lines of code on the M33 never missed. The M33 did that for 1 mJ per game-second.
  The silicon copy needed 74 mJ and the living box about 25 J.
  **The model culture did not learn within a game.** DishBrain's real cultures did.

## What changed from v0, and why

### 1. The chip is now calibrated against real hardware

**The problem.** v0 priced each chip operation with Intel's 2018 Loihi numbers. Priced
that way, the whole fly brain ran **5.8 times faster** than Sandia measured on 12 real
Loihi 2 chips (9.3 ms against 53.8 ms per simulated second at 0.1 ms steps). With 1 ms
steps v0 was **13 times** too fast (0.94 ms against 12.4 ms). The two errors differ, so one
fudge factor cannot fix both.

**What v1 adds.** Two costs that real multi-chip hardware pays and v0 ignored:
- **3.3 µs per time step**: the chips wait for each other at the end of every step;
- **0.97 µs per spike**: each spike has to be sent to the cores and chips that hold its
  targets.

**How it was fitted, keeping a fair test.** Sandia's paper has 16 timings: the sugar test
at two step sizes, and 14 runs where every neuron fires on its own at 0.5-40 Hz.
- The per-spike cost comes from how the run time grows with activity in the seven 1 ms
  runs.
- The per-step cost then comes from **one** point: the sugar test at 0.1 ms steps.
- Held back as the test: **the sugar test at 1 ms steps.** v1 predicts 15.7 ms; Sandia
  measured 12.4 ms. v1 is **26% too slow** there.
- Also held back: the seven 0.1 ms background runs. v1 is **7-42% too fast** on those.
  Those runs also pay for the chip's own random-spike generator, which v1 leaves out.
- Either cost alone misses the held-back point badly: per-step only is 57% too fast, and
  per-spike only is 266% too slow. So both are needed.

**Caveat.** Both costs were measured on a 12-chip system. A job that fits on one chip
(every task here) may pay less. So each chip number comes with a range: the best case is
v0's timing (Loihi 2's shortest possible step is 200 ns, so v0's per-step time is not
impossible), and the worst case is the full 12-chip overhead.

### 2. The chip now leaks power

Intel publishes no idle ("static") power for Loihi 2. Intel's own 2024 measurements of
one Loihi 2 chip (Shrestha et al., arXiv:2310.03251, Table 1) give total and "dynamic"
energy per task. The difference is the leakage: **18 to 296 mW per chip**, depending on
how the table's time base is read. v1 uses **73 mW** (the middle) and shows the range.
Ceiling: Intel's Hala Point system draws at most 2.26 W per chip.

This one change drives most of v1's energy numbers. Here is how the chip rows moved:

| Chip job | v0 | v1 (middle; range) |
|---|---|---|
| Feeding, 400 neurons | 23.6 ms / 217 µJ | 66 ms / 5.0 mJ (0.6-20 mJ) |
| Feeding, 36 neurons | 3.1 ms / 19.5 µJ | 38 ms / 2.8 mJ (0.07-11 mJ) |
| Odour sniff | 316 µs / 8.5 µJ | 806 µs / 66 µJ (14-241 µJ) |
| All-day watch, per day | 87 J (hybrid) | 6,400 J (1,600-26,000 J) |
| Silicon copy of the culture, one pattern | 3.6 ms / 41 µJ | 5.6 ms / 427 µJ (0.1-1.6 mJ) |
| Whole fly brain, sugar, 12 chips, per simulated second | 9.3 ms / 66 mJ | 53.8 ms (fitted) / 113 mJ |

The "ideal event-driven" chip (one that only works when a spike arrives) is now a bound
on timing only; it also leaks. For the 36-neuron circuit it would take 72 µs and 5.9 µJ.

### 3. The living-neuron module uses real settings where they exist

Sources: DishBrain (Kagan et al. 2022, *Neuron*, doi:10.1016/j.neuron.2022.09.001) and
FinalSpark's Neuroplatform (Jordan et al. 2024, *Frontiers in AI*,
doi:10.3389/frai.2024.1376042), both read in full. Values marked "read off" were read
from the published figures by eye.

| Setting | v0 | v1 | Status | Source |
|---|---|---|---|---|
| How long a culture lasts | half the cells gone at about 6 months | half gone at **100 days** | FITTED; "end of life = half the cells gone" is assumed | FinalSpark: organoids last "up to 100 days in best cases"; DishBrain kept human cultures over 3 months; CL1 up to 6 months |
| Stimulation during the game | none | DishBrain's exact scheme: 8 sites, place + rate code 4-40 Hz, 75 mV | PUBLISHED | DishBrain |
| Feedback | none | hit: 100 Hz for 100 ms on all sites; miss: 150 mV at 5 Hz on random sites for 4 s, then 4 s rest | PUBLISHED | DishBrain |
| Game timing | none | spikes counted and game updated every 10 ms; 20-minute sessions | PUBLISHED | DishBrain |
| Electrodes | CL1: 59 | also a MaxOne-like array: 1,024 recording channels | PUBLISHED | DishBrain: 26,400 electrodes, 1,024 read at once, 20 kHz |
| False electrode events | 1 per channel per second | 0.05 | FITTED (upper limit) | DishBrain's mean electrode rate is only 0.05-0.1 Hz (read off Fig 3), false events included |
| Resting firing | about 4 spikes per cell per second | about 0.13 | GUESSED (checked, not fitted) | see the check below |
| Learning speed | none | the model shows none (see Pong) | the learning rule is GUESSED; its rate could not be fitted | DishBrain: improvement "within five minutes", +0.2 to +0.4 hits per rally by minutes 6-20 |
| Variability | one seed | 2-5 sessions per setting; spread reported | reported | DishBrain sessions spread widely (boxes about 0.5-1.4 hits per rally, read off Fig 5B) |
| Response to one pulse (how far it reaches) | 60 µm | same | GUESSED | no per-cell figure found; FinalSpark gives only pulse sizes (e.g. 4 µA) |
| Fatigue with repeated pulses | 3% per pulse, 20 s recovery | same | GUESSED | FinalSpark says only that stronger pulses are needed as organoids age |
| Drift, wiring, synapse strengths, noise | guessed | same | GUESSED | none |
| Number of cells | 1,000 | 1,000 | ASSUMED (for speed) | DishBrain plated about 1,000,000; CL1 about 800,000 |

**Firing-rate check.** DishBrain's electrodes averaged 0.05-0.1 spikes per second (the
busiest 6-22). The model's electrodes average 1.2-1.7 (busiest 2-7). The model is quieter
at its busiest spots and 15-30 times busier on average. The comparison is not like for
like: DishBrain plated about 250 times more cells per square millimetre, and its cells
are not all alike. So the model reports this as a check, not a fit.

**Effect on the old electrode test (e).** Fewer false events and a quieter culture make
patterns easier to read: 95.4% through 59 electrodes (v0: 89.6%), 97.5% for the silicon
copy (v0: 91.7%). After 30 simulated days (79% of cells alive) the old read-out still
scores 91%.

### 4. A DishBrain-style Pong game

The model culture plays Pong the way DishBrain's cultures did. The game tells the culture
where the ball is by stimulating one of 8 sites (which site = where the ball is compared
with the paddle; how often = how close it is). The culture moves the paddle through
activity in "up" and "down" areas, read every 10 ms. A hit is followed by calm, regular
pulses; a miss by 4 seconds of random pulses.

- **The paddle's size was set so a paddle driven by noise scores 0.80 hits per rally,
  like DishBrain's own random-paddle control.** The ball crossing time (3.5 s) comes from
  DishBrain's 69 rallies per 20-minute session.
- **Guessed:** where the stimulation sites and "up/down" areas sit on the dish, how fast
  the paddle moves, how activity turns into movement, and how the cells learn.

**Results** (20-minute sessions; "hits per rally" = how many times the ball is returned
before a miss):

| Player | Hits per rally: whole game (minutes 0-5 → 6-20) | Balls hit | Compute time per game-second | Energy per game-second |
|---|---|---|---|---|
| Living module, 1,024 electrodes | 1.9 (2.2 → 1.8) | 62% | real time (1 s) | 25 J (the CL1 box) |
| Same, learning switched off | 1.3 (0.9 → 1.5) | 54% | real time | 25 J |
| Living module, 59 electrodes (CL1) | 0.6 (0.6 → 0.6) | 46% | real time | 25 J |
| Living module, DishBrain's own layout (sites along the edge), 1,024 electrodes | 0.8 (0.9 → 0.7) | 43% | real time | 25 J |
| Living module, no stimulation at all | 0.8 | 44% | real time | 25 J |
| Silicon copy of the culture on the neuromorphic core, every cell read | 42, very spread (a few endless rallies) | 98.9% | 19 ms (v0: 11 ms) | 74 mJ (v0: 1.1 mJ) |
| Same, learning switched off | 4.1 | 98.0% | 19 ms | 74 mJ |
| M33 running a simple controller | never missed (171 hits per game) | 100% | 47 µs | 1.0 mJ |
| Paddle driven by noise | 0.9 | 47% | none | none |
| *DishBrain's real cultures (read off Fig 5B)* | *human 0.68 → 1.10; mouse 0.78 → 1.00; noise paddle 0.80* | | *real time* | |

Sessions: 5 each for the living rows with 1,024 electrodes (learning on and off) and 59
electrodes, the silicon copy and the noise paddle; 3 for the other rows.

- **Electrodes are the bottleneck.** The same network, read cell by cell on silicon, hit
  99% of balls. Read through 1,024 electrodes it hit 62%, and through 59 it was no better
  than chance. Part of the gap is fatigue: the living sites tire (about 50% strength by the
  end), and the silicon copy has no fatigue.
- **How the score depends on the number of electrodes** (hits per rally; noise paddle 0.86):

  | Electrodes | 8 | 16 | 32 | 59 | 128 | 256 | 1,024 |
  |---|---|---|---|---|---|---|---|
  | Hits per rally | 0.44 | 1.07 | 0.38 | 0.62 | 0.39 | 1.25 | 1.89 |
  | Sessions | 2 | 2 | 2 | 5 | 2 | 2 | 5 |

  Only 1,024 electrodes beat the noise paddle clearly. From 8 to 256 the scores bounce
  around chance, and 2 sessions each are too few to rank them.
- **The skill comes from the layout, not from learning.** In the default layout, the cells
  next to each site sit in the "up" or "down" areas, so the dish starts out with a crude
  built-in reflex. With DishBrain's own layout (sites along one edge, far from the motor
  areas), activity in this model does not travel that far, and the culture plays at chance.
- **No learning.** DishBrain's cultures improved within 5 minutes. In the model, minutes
  6-20 were not better than minutes 0-5, and switching learning off changed the living
  score by less than the session-to-session spread. (On the silicon copy, learning
  lengthened rallies from 4 to 42 hits, but the spread is huge.) Learning rates from 0.03
  to 1.0 were tried before the benchmark, partly on sessions kept apart for this; none
  reproduced DishBrain. So the learning rule is only a placeholder, and learning speed is
  the biggest open gap.
- **Cost.** The living module costs about 25 J per game-second, because its box runs at
  25 W and the game runs in real time. The silicon copy is about 340 times cheaper. The
  simple controller is about 25,000 times cheaper, and it plays perfectly.

### 5. The robust 400-neuron circuit is the feeding default

It makes the same decisions as the whole brain, and its brake on bitter matches the whole
brain's (MN9 at 4.9 Hz against 4.3 Hz; the 36-neuron circuit gives 24.5 Hz). It still
decides correctly with 8- or 9-bit weights. The 36-neuron circuit is still an option
(`feeding.run("36")`).

## Did the machine get the known answers right?

- **Fly circuits: yes, exactly** (unchanged from v0). The engine matches the project
  simulator spike for spike. The 400-neuron circuit gives MN9 67.7 / 0 / 4.9 Hz for sugar /
  bitter / both; the whole brain gives 67.0 / 0 / 4.3 Hz.
- **Odour learning: yes**: 66.85% on 110 odours (lane: 66.8%); 66.2% with 8-bit weights.
- **Chip timing: fitted, then tested on held-back data**: 26% off on the held-back sugar
  run and 7-42% off on the held-back background runs (above).
- **Pong baselines: yes by design**: the noise paddle scored 0.86 against DishBrain's
  0.80; the paddle size was fitted for this.
- **DishBrain's learning: no.** The model does not reproduce it.

## Limits, stated plainly

- The chip's timing costs were fitted on one 12-chip system and one kind of workload (the
  fly brain). They are applied to one-chip jobs, with a range because this is uncertain.
- The chip's static power comes from one paper's table, read two ways (a 16-fold range).
  How much a smaller, purpose-built chip would leak is unknown.
- The chip's energy per operation is still Loihi 1's 2018 pre-silicon figure.
- The M33 cycle counts and its 1 mW sleep power are still assumptions. Sleep power decides
  the all-day task.
- **Living module, still guessed:** wiring, synapse strengths, noise, resting drive, how
  far a pulse reaches, fatigue, drift, the learning rule, the dish layout in Pong, the
  paddle speed and the read-out rule. The model culture has 1,000 identical cells, about
  1,000 times fewer than a real dish.
- The model culture ran with 0.5 ms steps in Pong (the fly circuits use 0.1 ms), to keep
  the emulator fast enough.
- Pong: only 2-5 sessions per setting. Rally lengths vary a lot between sessions.
- Laptop energy = measured time x 15 W, an assumed share of its power. Laptop times vary
  by 10-20% from run to run because other work shares the machine.

## Where things are

- Code: `vhc/` (see `vhc/README.md`). New in v1: `vhc/neurocal.py` (the chip fit),
  `vhc/workloads/pong.py` (the game) and `vhc/tests/test_v1.py`.
- Results: `vhc/results/results.json`, `table.md`, `compare.md` (v0 against v1),
  `neuro_calibration.json`. v0's own results are kept in `results_v0.json` and
  `table_v0.md`.
- Price list with every source: `vhc/prices.py`.
- Run: `.venv\Scripts\python.exe -m vhc.bench` (about 10 minutes; the emulator's own time
  is never used as a design's speed). Tests: `-m pytest vhc/tests -q -p no:cacheprovider`
  (24 tests, about 6-8 s).

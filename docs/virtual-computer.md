# The virtual hybrid computer, version 0

*Built 2026-09-24. Every number here is **PRELIMINARY**: modeled from published chip numbers
and guesses, not measured on the real hardware (except where marked M).*

## The results

Each cell gives **time per task / energy per task / accuracy**. "Hybrid" means the
neuromorphic (brain-like) chip plus a small conventional core (a Cortex-M33, the processor
in the $17 RP2350 board). The neuromorphic numbers use Intel Loihi's published cost of each
operation, run the way Loihi runs (every neuron updated every 0.1 ms).

| Task | Hybrid | CPU only: this laptop | CPU only: M33 | GPU (T4) | Neuromorphic only |
|---|---|---|---|---|---|
| (a) Feeding decision, 36-neuron fly circuit (1 s of tasting) | 3.1 ms / 19.5 µJ / 100% | 1.2 ms (M) / 18.7 mJ / 98.5% | 64 ms / 1.9 mJ / 98.5% | 100 ms / 7 J / 98.5% | 3.1 ms / 18.9 µJ / 100% |
| (a) Feeding decision, 400-neuron circuit | 24 ms / 217 µJ / 100% | 12.9 ms (M) / 194 mJ / 100% | 694 ms / 20.8 mJ / 100% | 100 ms / 7 J / 100% | 24 ms / 217 µJ / 100% |
| (b) Odour learning: 110 odours, one sniff recognised and learned | 316 µs / 8.5 µJ / 66.2% | 145 µs (M) / 2.2 mJ / 66.8% | 866 µs / 26 µJ / 66.8% | 50 µs / 3.5 mJ / 66.8% | 296 µs / 7.9 µJ / 66.2% |
| (c) Exact sum of 50,000 big whole numbers | 1.3 ms / 40 µJ / 100% | 15 µs (M) / 218 µJ / 100% | 1.3 ms / 40 µJ / 100% | 65 µs / 4.5 mJ / 100% | cannot do it |
| (c) Sort 50,000 numbers | 62 ms / 1.9 mJ / 100% | 284 µs (M) / 4.3 mJ / 100% | 62 ms / 1.9 mJ / 100% | 118 µs / 8.3 mJ / 100% | cannot do it |
| (d) All-day odour watch with an exact log (per sniff; **energy per day**) | 280 µs / **87 J** / 95.9%, exact log | 140 µs (M) / **259,000 J** / 95.9% | 854 µs / **89 J** / 95.9% | 45 µs / **1.1 million J** / 95.9% | 277 µs / **0.65 J** / 95.9%, **no log** |
| (e) Name 1 of 8 stimulation patterns | with living cells, 59 electrodes: 60 ms / 1.5 J / 89.6% (K); with a silicon copy of the culture: 3.6 ms / 41 µJ / 91.7% | 1.3 ms (M) / 19.5 mJ / 91.7% | 101 ms / 3.0 mJ / 91.7% | 6.1 ms / 425 mJ / 91.7% | needs the conventional core for its read-out |

**Labels.** (M) = time measured on this laptop. Every other time and energy is modeled:
counted operations times the published (or assumed) cost of each operation. (K) = rests on
guessed biology settings. Laptop energy = measured time x 15 W (Intel's rated base power; an
assumed share). Accuracies come from simulating each task. The full table, with the "ideal
event-driven" chip mode and every label, is in `vhc/results/table.md`.

The accuracy gap between 100% and 98.5% on the 36-neuron circuit is not a real difference:
the chip-style run used one seed (90 trials), the others three seeds (270 trials).

**The headline.** On the fly's feeding circuit the hybrid's neuromorphic chip uses about
**1,000 times less energy than this laptop** and **100 times less than the
microcontroller**, at the same accuracy. On odour learning the saving is smaller: **250
times** against the laptop and **3 times** against the microcontroller. On exact jobs (sums,
sorting) the hybrid is only as good as its small conventional core: the laptop is **90 to
220 times faster**. The all-day odour watch shows the design rule works in principle, but in
v0 its daily energy is decided by **standby power**, which is guessed (see below).

## How the numbers were made (and why the emulator's speed does not count)

The virtual computer runs on this laptop, much slower than real chips would. So its own run
time is never used as a design's speed. Instead:

1. Each task is simulated, and the simulator **counts** what the hardware would have to do:
   neuron updates, synaptic events (one spike reaching one target), sensor inputs, learning
   writes, integer additions, comparisons.
2. Each count is multiplied by the **price** of that operation on the real part:
   - neuromorphic chip: Intel Loihi, 23.6 pJ and 3.5 ns per synaptic event, 52 to 81 pJ and
     5.3 to 8.4 ns per neuron update, 120 pJ per learning write, 113 to 465 ns per time-step
     barrier (Davies et al. 2018, *IEEE Micro*, Table 2, checked against the paper);
   - M33 microcontroller: 150 MHz, about 30 mW while working (Niedermeier and Krichmar,
     arXiv:2604.16474); cycles per operation are **assumed** (for example 25 per neuron update,
     10 per synaptic event, 4 per 64-bit addition);
   - this laptop: time per operation **measured** here (`vhc/calibrate.py`);
   - GPU: NVIDIA T4 datasheet (70 W, 8.1 TFLOPS, 320 GB/s) plus an **assumed** 5 µs to start
     each GPU job;
   - living cells: they only run in real time; a CL1 box draws about 25 W (The Next Web);
     59 electrodes, 25 kHz, 40 µs frames (Cortical Labs' CL API paper, arXiv:2602.11632);
     electrode noise 2.2 µV (MaxWell MaxOne).
3. Time per task is the time the hardware is busy with one task, running as fast as it can.
   (The fly model itself covers 1 s of tasting; a chip can finish that second of simulation
   in 3 ms.)

Every constant, with its label (published, measured, assumed or guessed) and source, is in
`vhc/prices.py`.

## Did the machine get the known answers right?

- **The fly circuits: yes, exactly.** The virtual neuromorphic core gives the same spikes,
  spike for spike, as the project's own simulator on the same input (checked by a test). So
  it reproduces the circuit results in `docs/minimal-circuit.md` exactly: MN9 fires 62.3 Hz
  on sugar, 0 on bitter and 24.5 Hz on sugar plus bitter (36 neurons), and 67.7 / 0 / 4.9 Hz
  (400 neurons). The whole brain gives 67.0 / 0 / 4.3 Hz.
- **Decision rule.** "Feed" when MN9 fires above 35.7 Hz, halfway between the whole brain's
  sugar and sugar-plus-bitter rates. Caveat: I chose this after seeing that the 36-neuron
  circuit fires 24 Hz on sugar plus bitter; a threshold below 24 Hz would make that circuit
  wrong every time on that stimulus.
- **Chip-style weights.** Stored in 9 bits (Loihi 2's fly-brain setting), both circuits still
  decide correctly on every trial tested (one seed, 30 trials per stimulus). In 8 bits the
  36-neuron circuit gets 98.9% right, and the 400-neuron circuit's bitter brake gets weaker
  (9.2 Hz instead of 3.4 Hz) but still decides correctly.
- **Odour learning: yes.** Random wiring, 5 seeds x 2 brain halves: **66.85%** correct on
  110 odours, matching the memory-centre lane's 66.8%. With the learned weights stored in
  8 bits: 66.2%.
- **Chip timing check: 5.8 times too optimistic.** Priced the same way, the whole fly brain's
  sugar test on 1,440 cores comes out at 9.3 ms per simulated second. Sandia measured
  53.8 ms on real Loihi 2 chips. So the chip **times** in the table may be several times too
  fast, as the roadmap warned (message traffic between chips is not modeled).
- **Laptop cost model:** within 11-15% of the measured time on the fly circuits; 2-3 times
  off on sum and sort (so the laptop rows use measured times).

## What the hybrid is good at

- **Brain-like jobs at tiny energy.** The feeding decision costs 19.5 µJ on the chip,
  against 18.7 mJ on the laptop, 1.9 mJ on the microcontroller and about 7 J on a GPU. The
  fly circuit is tiny and sparse, which is exactly what spiking hardware is built for.
- **Learning on the spot, cheaply.** Each odour sniff is recognised and learned from for
  about 8 µJ, changing only about 120 connections. The laptop spends 2.2 mJ on the same
  sniff.
- **Exact records when needed.** The hybrid's log in the odour watch is exact (checked); the
  neuromorphic chip alone cannot keep one.
- **Better when "event-driven" hardware arrives.** If the chip only did work when a spike
  arrived (the "ideal event-driven" mode), the 36-neuron decision would drop from 3.1 ms and
  19.5 µJ to 72 µs and 0.6 µJ. The fixed clock is most of today's cost for small circuits.

## What it is bad at

- **Exact maths is slow.** The hybrid sends sums and sorts to its small M33 core, which is
  about 90 times slower than the laptop on the sum and 220 times slower on the sort. It uses
  less energy than the laptop, but a bigger conventional core would be needed for heavy
  exact work.
- **The chip is not faster than the laptop on small circuits.** The laptop finished the
  36-neuron decision in 1.2 ms (measured); the Loihi-style chip is modeled at 3.1 ms, because
  it must step through 10,000 clock ticks.
- **GPUs are wasted on single small tasks.** A GPU spends almost all its time starting jobs.
  Processing thousands of tasks at once would help it a lot; v0 only models one task at a
  time, as a sensor delivers them.
- **Standby power decides the all-day watch.** With the M33 asleep at a guessed 1 mW, the
  hybrid uses 87 J a day and the M33 alone 89 J: only 2% better. With a 0.1 mW sleep the
  hybrid wins by 17% (9.3 vs 10.9 J a day), with 0.01 mW by 2 times (1.5 vs 3.1 J). And the
  chip's own leakage is not in v0 at all: a Xylo-class chip's 100 µW would add 8.6 J a day.
  So this row is not settled.
- **The accuracy ceiling of the memory-centre design stays low**: 66% on 110 odours (a
  normal neural network trained on everything at once gets 93%, `docs/mb-continual-learning.md`).
- **Living cells cost a lot per answer.** The simulated culture read through a CL1's 59
  electrodes got 89.6% right, but each answer takes 60 ms of real time and about 1.5 J of the
  box's life support. A silicon copy of the same network got 91.7% for 41 µJ.

## The electrode bottleneck

The simulated culture has 1,000 cells on a 1.4 mm dish. The same trials were read through
different numbers of electrodes (chance = 12.5%):

| Electrodes | 1 | 2 | 4 | 8 | 16 | 32 | 59 (CL1) | 128 | 256 | every cell, one by one | every cell, pooled into 256 areas |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Correct | 14% | 15% | 10% | 42% | 11% | 82% | 90% | 97% | 99.6% | 86% | 92% |

- **Below about 32 electrodes it is luck.** With few electrodes, accuracy depends on whether
  one happens to sit near a stimulated spot (16 electrodes on a wide grid missed all of
  them). From 32 electrodes up, more is better.
- **Reading every cell was not the best.** With only 320 training trials, 6,000 separate
  cell readings are hard to learn from; grouped electrode counts did better. How the reading
  is pooled matters as much as how many cells are seen.
- **Drift and cell death barely hurt, in this model.** After 30 simulated days (87% of cells
  alive), the day-0 read-out still scored 87.5% (90% at day 0). This is probably optimistic:
  the model culture mostly passes the stimulation on, doing little computing of its own, and
  the drift rate is a guess.
- **Fatigue.** Stimulated spots ended at about 83% of their fresh strength (guessed rates).

## What v1 should add

1. **Standby power for every part**, from datasheets (RP2350 sleep and dormant modes, a
   neuromorphic chip's leakage). This decides the all-day tasks.
2. **Message traffic on the chip**, calibrated so the whole-brain test matches Sandia's
   53.8 ms, or SANA-FE (the published Loihi energy/latency simulator) run in the cloud.
3. **Measured energy on real parts**: the RP2350 board from Stage 2 (a USB power meter), and
   this laptop's package power (its power counter is readable, `docs/energy-budget.md`).
4. **A GPU running many tasks at once**, and a real cloud GPU measurement.
5. **A living module that computes**, not just relays: bursting, a culture model with
   published parameters (for example Maheswaranathan et al. 2012), and learning through the
   electrodes (a DishBrain-style task), behind Cortical Labs' CL API simulator.
6. **A bigger conventional core option** (for example a Cortex-A class core) so exact work
   is not stuck on a microcontroller.
7. **The whole brain as a workload** (it would need the fix setting passed explicitly), and
   the fly-body steering task.

## Limits, stated plainly

- Loihi's numbers are pre-silicon estimates from 2018; newer chips may differ.
- Static (leakage) power of the neuromorphic chip is left out.
- The M33 cycle counts are assumptions, not measured on the chip; M33 accuracy was taken
  from the full-precision simulation.
- The GPU is modeled, not measured, and charged its full 70 W while busy (an upper bound).
- Laptop energy charges the whole 15 W to one busy core (an upper-end assumption); laptop
  times were measured while other work shared the machine.
- The living module's settings (noise, fatigue, drift, death, plasticity, electrode reach,
  spike size) are mostly **guessed**; its results are hypotheses for Stage 4.
- The odour-watch accuracy (95.9%) is flattered by easy "no odour" sniffs (90% of the
  stream); on odours alone, the name was right 66% of the time.
- One seed for most runs; no independent review.

## Where things are

- Code: `vhc/` (see `vhc/README.md`); results: `vhc/results/results.json` and
  `vhc/results/table.md`; price list: `vhc/prices.py`.
- Run: `.venv\Scripts\python.exe -m vhc.calibrate`, then `-m vhc.bench` (about 75 s of
  emulator time); tests: `-m pytest vhc/tests -q -p no:cacheprovider` (16 tests, about 5 s).

# The fast engine, explained

**In one sentence:** `sim/fast_engine.py` runs the same whole-brain model as the
paper's Brian2 code, gives the same answers, and is about 45 to 300 times
faster on this laptop, depending on how the Brian2 run is timed (about 45x
against Brian2's best case, about 250-300x against our Phase 3 runs). That makes
silencing sweeps, sensitivity runs and the interactive app practical.

## Why it exists

The paper's model is written for Brian2, a neuroscience simulator. Brian2 is fast
only when it can turn the model into C++ and compile it, and this laptop has no
C++ compiler. Without one, Brian2 falls back to a slow pure-Python mode.

| | Time for one 1-second trial of the whole brain (v630) |
|---|---|
| Brian2 without a compiler (Phase 3 port, running alone) | about 55 s |
| Brian2 without a compiler (Phase 3 port, two runs side by side, as logged) | about 100 s |
| Brian2 without a compiler (main session's measurement) | 21-40 s |
| **Fast engine, one CPU core** | **0.38 s** (sugar at 100 Hz), 0.48 s (200 Hz) |
| **Fast engine, two cores, the paper's 30 trials** | **about 7-10 s for all 30** |

So the speedup on one core is roughly 45x against the most favourable Brian2
figure, and about 145x against the Phase 3 port running alone. A full 30-trial
experiment used to take 30-60 minutes. It now takes about 10 seconds.

## How it gets that speed

1. **Compiled with numba.** numba is a Python add-on that includes its own
   compiler, so it needs no C compiler. It turns the inner loop into fast
   machine code the first time it runs (15-20 s, once) and caches it.
2. **It only works on neurons that have received input.** In the sugar
   experiment about 11,000 of the 127,400 neurons ever get any input. The
   others sit exactly at rest. In Brian2 every resting neuron follows the same
   path, so the engine stores that path once, as a single number, instead of
   127,400 times.
3. **Spikes are delivered from a list.** When a neuron fires, the engine walks
   only through that neuron's outgoing connections, 1.8 ms later.
4. **The busy loop never resizes memory.** A first version was 15 times slower
   because it could grow its spike list from inside the busiest loop. Moving
   that check out of the loop fixed it.

## Is it really the same model?

Every rule was copied from `data/reference/model.py`, and also from what Brian2
actually does with that code. Brian2's own generated code was printed and read
line by line. Three of the rules are easy to miss:

- **Inputs are ignored during the refractory period.** After a spike, a
  neuron is frozen for 2.2 ms. Brian2 also throws away any input that arrives in
  that window, because the equations are marked "unless refractory". The engine
  does the same.
- **Order within a time step.** Brian2 updates voltages first, then checks for
  spikes, then delivers inputs, then resets the neurons that spiked. Input that
  reaches a neuron in the same step it fires is therefore lost.
- **Stimulated neurons have no refractory period.** The reference sets it to 0
  for them, so the engine does too.

The engine also works in the same units as Brian2 (volts and seconds) and does
each calculation in the same order. That makes the arithmetic identical down to
the last digit.

## How it was checked

**1. Small networks, identical input: identical results.** The test file
`tests/test_fast_engine.py` builds four random networks of 40-100 neurons,
with excitatory and inhibitory connections and some silenced neurons. It feeds
the same input spikes to both the reference's own Brian2 code
(`data/reference/model.py`, unmodified) and the fast engine. Each network fires
900-1,060 spikes in 200 ms. **Every spike happens at the same 0.1 ms time
step in both, and the recorded voltage traces are identical to the last
digit.**

To make sure this test can actually catch mistakes, two deliberate bugs were
planted in a scratch copy of the engine:

- letting input through during the refractory period gave about 700 wrong spikes;
- delivering spikes one step late gave about 600 wrong spikes.

The test flagged both.

**2. Whole brain against the paper authors' own Brian2 output.** The reference
repository includes the output of its tutorial runs (v630, 30 trials each). The
engine ran the same experiments with 30 new trials. The two can only agree up
to random trial-to-trial noise, because the random input differs. "Within 3
standard errors" is the check for that noise.

| Experiment | Correlation of all neurons' rates | Neurons within 3 standard errors | MN9, engine | MN9, authors' Brian2 |
|---|---|---|---|---|
| Sugar GRNs at 100 Hz | 0.9996 | 99.4% (100% within 4) | 67.6 Hz | 67.0 Hz |
| Sugar GRNs at 200 Hz | 0.9998 | 100% | 92.9 Hz | 93.3 Hz |
| 100 Hz, with neuron ...617937543 silenced | 0.9997 | 99.7% | 64.0 Hz | 63.3 Hz |
| 100 Hz, with neuron ...621754367 silenced | 0.9996 | 99.7% | 67.1 Hz | 66.9 Hz |
| 100 Hz, with neuron ...622695448 silenced | 0.9997 | 100% | 70.7 Hz | 71.2 Hz |

**The paper's numbers:** MN9 at 65.7 ± 3.3 Hz with sugar at 100 Hz (engine:
67.6 ± 4.6) and 93.2 Hz at 200 Hz (engine: 92.9 ± 3.3).

**A finding along the way.** The tutorial file called `sugarR.parquet` was made
with **200 Hz** input, even though today's `model.py` default is 150 Hz. The
file itself shows this: its stimulated neurons fire at 196.75 Hz. With 200 Hz
input they should fire at 196.1 Hz; with 150 Hz, at 147.8 Hz. Comparing a
150 Hz run against that file would look like a 10 Hz error in MN9 that is not
really there.

**3. Whole brain against the Phase 3 Brian2 port.** This project's own port
(`sim/shiu_model.py`) ran 10 trials per condition; the engine ran 30.

| Condition | Correlation | Within 3 standard errors | MN9, engine | MN9, Brian2 port |
|---|---|---|---|---|
| Sugar 100 Hz | 0.9992 | 98.9% (99.7% within 4) | 69.7 Hz | 67.0 Hz |
| Water 200 Hz | 0.9996 | 99.6% (100% within 4) | 29.7 Hz | 33.5 Hz |

Both MN9 differences are under 2 standard errors, which is normal random
variation. `experiments/fast_engine/compare_phase3.py` re-runs this comparison
whenever Phase 3 finishes more conditions.

## What is different from Brian2 (and why it does not matter)

- **The random numbers are different.** The engine uses numpy's random
  generator, not Brian2's. A single trial will not match a single Brian2 trial,
  but averages over trials do (see the tables above). The Poisson rule itself is
  the same: each 0.1 ms step, a stimulated neuron gets a kick with probability
  rate x 0.1 ms. A test confirms that the resulting firing rate matches the
  mathematical prediction.
- **Very tiny inputs are rounded to zero.** Once a neuron's fading synaptic
  input drops below 10^-200 volts, the engine sets it to exactly zero.
  That is so small that it cannot change the voltage at all, not even in the
  last digit. It stops the processor from slowing down on extremely tiny numbers
  in runs longer than about 3 seconds.
- **The same seed always gives the same result.** Trial 5 is also the same
  whether you run 10 trials or 30.

## How to use it

```python
from sim.fast_engine import FastBrain

brain = FastBrain(snapshot="630")          # or "783"; loads in about 2 s
res = brain.run(excite=sugar_ids, rate_hz=100, duration_ms=1000,
                n_trials=30, seed=0)       # silence=[...] to silence neurons
res.rate(720575940660219265)               # MN9 firing rate, Hz
res.rates()                                # every active neuron, highest first
res.spike_times(trial=0)                   # {neuron id: spike times in ms}
res.to_dataframe("sugar")                  # same table layout as the reference
```

Model settings, such as the threshold or the weight per synapse, can be changed
for a single run: `brain.run(..., params={"w_syn": 0.33})`. That is what the
+/-20% sensitivity tests will use. `n_threads=2` runs two trials at a time.

## Files

- `sim/fast_engine.py`: the engine.
- `tests/test_fast_engine.py`: the comparison with Brian2 and other checks
  (about 15-40 s), plus one slow whole-brain test (about 13 s).
- `experiments/fast_engine/benchmark.py`: the whole-brain timings and the
  comparison with the authors' output. Results are in
  `experiments/fast_engine/results/summary.json`.
- `experiments/fast_engine/compare_phase3.py`: the comparison with the Phase 3
  Brian2 port.

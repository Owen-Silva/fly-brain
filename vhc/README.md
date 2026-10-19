# vhc: the virtual hybrid computer, v1 (PRELIMINARY)

A software model of the machine in the hybrid-computer plan (a design note not included in this repo) section 6: a conventional core,
a neuromorphic core, an optional living-neuron module behind electrodes, and a scheduler.
Each part carries a price list, so a task gives three numbers per design: time, energy and
accuracy. Plain-English results: `docs/virtual-computer.md`.

**Honesty rule.** A design's speed and energy come only from counted operations times the
price list (`prices.py`), or, for "CPU only: laptop", from timing the laptop itself. The
emulator's own run time is never used as a design's speed.

## Run

```
.venv\Scripts\python.exe -m vhc.calibrate        # measure this laptop's ns per operation (~15 s)
.venv\Scripts\python.exe -m vhc.neurocal         # v1: fit the chip timing to Sandia's Loihi 2 runs (<1 s)
.venv\Scripts\python.exe -m vhc.bench            # every benchmark (~8 min, 3 worker processes) -> vhc/results/
.venv\Scripts\python.exe -m pytest vhc/tests -q -p no:cacheprovider   # unit tests (~6 s)
```

## Layout

| File | What it is |
|---|---|
| `prices.py` | every time/energy constant, labelled PUBLISHED / DERIVED / FITTED / MEASURED / ASSUMED / GUESSED, with its source; v1 adds Sandia's Loihi 2 timings, Loihi 2 static power, DishBrain and FinalSpark settings |
| `neurocal.py` | v1: fits the neuromorphic timing (+A per step, +B per spike) to Sandia's measurements, with held-out checks -> `results/neuro_calibration.json` |
| `ledger.py` | `Cost` (time, energy, label) and operation counts |
| `cores/lif.py` | event-counting LIF engine; spike-for-spike identical to `sim/fast_engine.py` on the same input |
| `cores/neuromorphic.py` | prices spike counts with Loihi's published per-op numbers, "clocked" or "event" mode; `version="v1"` (default) adds the calibrated timing and static power, `"v0"` keeps the old pricing; `price_range` gives v1's best/worst case |
| `cores/conventional.py` | operations -> cycles -> time/energy for a Cortex-M33 @ 150 MHz; measured ns/op for the laptop |
| `cores/gpu.py` | NVIDIA T4 model from its datasheet (launch-bound for small work) |
| `cores/living.py` | simulated culture: noise, fatigue, drift, cell death, slow plasticity; v1: lifetime FITTED to FinalSpark, resting activity lowered; most wiring/biology still GUESSED |
| `cores/electrodes.py` | N recording channels, read noise, stimulation spread, latency |
| `scheduler.py` | rule-based routing, then cheapest core that meets the accuracy requirement |
| `workloads/` | (a) feeding decision (400-neuron circuit by default, 36 optional), (b) odour learning, (c) exact sum/sort, (d) hybrid odour watch, (e) electrode bottleneck, (f) v1: DishBrain-style closed-loop Pong (`pong.py`, compiled game loop) |
| `bench.py` | runs everything; writes `results/results.json`, `results/table.md` and `results/compare.md` (v0 vs v1); v0's results are kept as `results_v0.json` / `table_v0.md` |
| `calibrate.py` | measures the laptop's ns per operation -> `results/x86_calibration.json` |

## Reuse of other lanes (read-only)

- `experiments/minimal_circuit/results/{minimal,robust}_circuit.json` (the 36/400-neuron circuits) and its `paper_ids()`.
- `experiments/mb_continual/common.py` (odour tables, KC code, fly read-out), imported by path.
- `experiments/energy_budget/results/decision_summary.csv` (whole-brain counts, for the Sandia calibration).
- The whole-brain model is not run, so no sign-fix choice is involved.

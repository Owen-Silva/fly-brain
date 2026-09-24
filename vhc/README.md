# vhc: the virtual hybrid computer, v0 (PRELIMINARY)

A software model of the machine in `docs/hybrid-roadmap.md` section 6: a conventional core,
a neuromorphic core, an optional living-neuron module behind electrodes, and a scheduler.
Each part carries a price list, so a task gives three numbers per design: time, energy and
accuracy. Plain-English results: `docs/virtual-computer.md`.

**Honesty rule.** A design's speed and energy come only from counted operations times the
price list (`prices.py`), or, for "CPU only: laptop", from timing the laptop itself. The
emulator's own run time is never used as a design's speed.

## Run

```
.venv\Scripts\python.exe -m vhc.calibrate        # measure this laptop's ns per operation (~15 s)
.venv\Scripts\python.exe -m vhc.bench            # every benchmark (~2 min) -> vhc/results/
.venv\Scripts\python.exe -m pytest vhc/tests -q -p no:cacheprovider   # unit tests (~5 s)
```

## Layout

| File | What it is |
|---|---|
| `prices.py` | every time/energy constant, labelled PUBLISHED / MEASURED / ASSUMED / GUESSED, with its source |
| `ledger.py` | `Cost` (time, energy, label) and operation counts |
| `cores/lif.py` | event-counting LIF engine; spike-for-spike identical to `sim/fast_engine.py` on the same input |
| `cores/neuromorphic.py` | prices spike counts with Loihi's published per-op numbers, "clocked" or "event" mode |
| `cores/conventional.py` | operations -> cycles -> time/energy for a Cortex-M33 @ 150 MHz; measured ns/op for the laptop |
| `cores/gpu.py` | NVIDIA T4 model from its datasheet (launch-bound for small work) |
| `cores/living.py` | simulated culture: noise, fatigue, drift, cell death, slow plasticity (mostly GUESSED) |
| `cores/electrodes.py` | N recording channels, read noise, stimulation spread, latency |
| `scheduler.py` | rule-based routing, then cheapest core that meets the accuracy requirement |
| `workloads/` | (a) feeding decision, (b) odour learning, (c) exact sum/sort, (d) hybrid odour watch, (e) electrode bottleneck |
| `bench.py` | runs everything; writes `results/results.json` and `results/table.md` |
| `calibrate.py` | measures the laptop's ns per operation -> `results/x86_calibration.json` |

## Reuse of other lanes (read-only)

- `experiments/minimal_circuit/results/{minimal,robust}_circuit.json` (the 36/400-neuron circuits) and its `paper_ids()`.
- `experiments/mb_continual/common.py` (odour tables, KC code, fly read-out), imported by path.
- `experiments/energy_budget/results/decision_summary.csv` (whole-brain counts, for the Sandia calibration).
- The whole-brain model is not run, so no sign-fix choice is involved.

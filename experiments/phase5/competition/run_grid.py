"""Phase 5 "Competition": stimulate sugar GRNs together with bitter, water or
Ir94e GRNs at many input rates and record the feeding motor neuron MN9.

Plain English
-------------
Each "condition" is one pair of input rates, for example "sugar neurons at
100 Hz plus bitter neurons at 80 Hz". For each condition we run 30 one-second
trials (different random input each trial) and record how fast MN9 fires.
Every condition is repeated with 3 different random seeds so we can tell a
real effect from luck.

Stages (pick one on the command line; each can be re-run and resumes where
it stopped, because every finished condition is saved immediately):
  anchor  the paper's own test points (Fig. 3b, 3c, 4e), seed 0 only
  bitter  sugar {50,100,150,200} x bitter {0,25,50,100,150,200} Hz, + anchor, 3 seeds
  fine    sugar {100,200} x bitter 0..200 Hz in 10 Hz steps (for the tipping point)
  water   sugar {0,20,40,100} x water {0,100,200} Hz, 3 seeds
  ir94e   sugar {0,100,200} x Ir94e {0,50,100,200} Hz, 3 seeds

Output: results/grid.csv (one row per condition and seed) and, for a few
key conditions, the full firing-rate vector of every neuron (results/rates_*.npy).
"""

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phase5_common import get_brain, paper_ids, per_trial_rates  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
GRID_CSV = OUT / "grid.csv"
N_TRIALS = 30
SEEDS = (0, 1, 2)

ids = paper_ids()
brain = get_brain(globals())
MN9_IDX = brain.index_of([ids["MN9"], ids["MN9_IPSI"]])

# Conditions whose whole-brain rate vector we keep (seed 0), for the
# "which neurons carry the suppression" analysis.
KEEP_RATES = {("bitter", 100, 0), ("bitter", 100, 40), ("bitter", 100, 80),
              ("bitter", 100, 120), ("bitter", 100, 200), ("bitter", 200, 0),
              ("bitter", 200, 200), ("bitter", 0, 200), ("bitter", 50, 50),
              ("ir94e", 100, 200), ("ir94e", 0, 200), ("water", 40, 200)}


def conditions(stage):
    if stage == "anchor":
        c = [("bitter", 100, b) for b in (0, 40, 80, 120, 200)]
        c += [("bitter", 200, 0), ("bitter", 200, 200), ("bitter", 0, 200)]
        c += [("ir94e", 100, 200), ("ir94e", 200, 200)]
        c += [("water", 40, 0), ("water", 40, 200), ("water", 0, 200)]
        return [(k, s, o, 0) for k, s, o in c]
    if stage == "bitter":
        c = [("bitter", s, b) for s in (50, 100, 150, 200) for b in (0, 25, 50, 100, 150, 200)]
        c += [("bitter", 100, b) for b in (40, 80, 120)] + [("bitter", 0, 200)]
        return [(k, s, o, seed) for seed in SEEDS for k, s, o in c]
    if stage.startswith("fine"):
        seeds = SEEDS if stage == "fine3" else (0,)
        c = [("bitter", s, b) for s in (100, 200) for b in range(0, 201, 10)]
        return [(k, s, o, seed) for seed in seeds for k, s, o in c]
    if stage == "water":
        c = [("water", s, w) for s in (0, 20, 40, 100) for w in (0, 100, 200)]
        return [(k, s, o, seed) for seed in SEEDS for k, s, o in c]
    if stage == "ir94e":
        c = [("ir94e", s, r) for s in (0, 100, 200) for r in (0, 50, 100, 200)]
        return [(k, s, o, seed) for seed in SEEDS for k, s, o in c]
    raise ValueError(stage)


def done_keys():
    if not GRID_CSV.exists():
        return set()
    d = pd.read_csv(GRID_CSV)
    return set(zip(d.kind, d.sugar_hz, d.other_hz, d.seed))


def run_one(kind, sugar_hz, other_hz, seed):
    other = {"bitter": ids["BITTER"], "water": ids["WATER"], "ir94e": ids["IR94E"]}[kind]
    excite = {}
    if sugar_hz > 0:
        excite.update({int(i): float(sugar_hz) for i in ids["SUGAR"]})
    if other_hz > 0:           # rate 0 = those neurons are simply not stimulated
        excite.update({int(i): float(other_hz) for i in other})
    t0 = time.perf_counter()
    if excite:
        res = brain.run(excite=excite, duration_ms=1000.0, n_trials=N_TRIALS, seed=seed)
        pt = per_trial_rates(res, MN9_IDX)
        n_active = int((res.rates_hz > 0).sum())
        rates = res.rates_hz
    else:
        pt = np.zeros((N_TRIALS, 2))
        n_active, rates = 0, None
    row = dict(kind=kind, sugar_hz=sugar_hz, other_hz=other_hz, seed=seed, n_trials=N_TRIALS,
               mn9_mean=pt[:, 0].mean(), mn9_sd=pt[:, 0].std(),
               mn9_active_frac=float((pt[:, 0] > 0).mean()),
               mn9_ipsi_mean=pt[:, 1].mean(), mn9_ipsi_sd=pt[:, 1].std(),
               n_active_neurons=n_active, wall_s=round(time.perf_counter() - t0, 1),
               mn9_per_trial=json.dumps([round(x, 1) for x in pt[:, 0]]))
    if rates is not None and seed == 0 and (kind, sugar_hz, other_hz) in KEEP_RATES:
        np.save(OUT / f"rates_{kind}_s{sugar_hz}_o{other_hz}.npy", rates.astype(np.float32))
    return row


def main(stage):
    todo = [c for c in conditions(stage) if c not in done_keys()]
    print(f"stage {stage}: {len(todo)} conditions to run", flush=True)
    for n, (kind, s, o, seed) in enumerate(todo, 1):
        row = run_one(kind, s, o, seed)
        pd.DataFrame([row]).to_csv(GRID_CSV, mode="a", header=not GRID_CSV.exists(), index=False)
        print(f"[{n}/{len(todo)}] {kind} sugar {s} Hz + {o} Hz seed {seed}: "
              f"MN9 {row['mn9_mean']:.1f} +/- {row['mn9_sd']:.1f} Hz "
              f"({row['wall_s']} s)", flush=True)


if __name__ == "__main__":
    for st in (sys.argv[1:] or ["anchor"]):
        main(st)

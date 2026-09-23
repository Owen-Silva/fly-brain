"""Step 1a: does the runaway hold up? 30 trials x 5 seeds, fast engine.

Plain English
-------------
Three conditions, each 150 one-second trials (30 trials with each of 5
different random seeds):
  * sugar 200 Hz + Ir94e 200 Hz  (the condition that ran away in Phase 3)
  * sugar 200 Hz alone
  * Ir94e 200 Hz alone
For every trial we record the total number of spikes, how many neurons fired,
whether it ran away (definition in common.py) and when, and MN9's rate.
For the main condition we also keep, for every neuron that fired, how often
and when it first fired (used in step 3 to see which neurons ignite first).

Outputs: results/reproduce_trials.csv, results/reproduce_series.npz,
         results/main_neuron_stats.npz
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import (RESULTS, ROOT, paper_ids, run_one, sparse_neuron_stats,  # noqa: E402
                    trial_summary, free_ram_gb)

brain = globals().get("brain")
if brain is None:
    sys.path.insert(0, str(ROOT))
    from sim.fast_engine import FastBrain
    brain = FastBrain("630", n_threads=1)

ids = paper_ids()
SEEDS = [0, 1, 2, 3, 4]
N_TRIALS = 30
conds = {
    "sugar200_ir94e200": {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}},
    "sugar200_alone": {i: 200.0 for i in ids["SUGAR"]},
    "ir94e200_alone": {i: 200.0 for i in ids["IR94E"]},
}
out_csv = RESULTS / "reproduce_trials.csv"
rows, s1_all, d10_all, keys = [], [], [], []
nstats = {}
for name, excite in conds.items():
    for seed in SEEDS:
        for k in range(N_TRIALS):
            res = run_one(brain, excite, seed, k, 1000.0)
            row, s1, d10 = trial_summary(res, brain, ids)
            rows.append(dict(condition=name, seed=seed, trial=k, **row))
            s1_all.append(s1)
            d10_all.append(d10)
            keys.append(f"{name}|{seed}|{k}")
            if name == "sugar200_ir94e200":
                u, c, f = sparse_neuron_stats(res)
                nstats[f"{seed}_{k}_idx"], nstats[f"{seed}_{k}_cnt"], nstats[f"{seed}_{k}_first"] = u, c, f
            del res
        df = pd.DataFrame(rows)
        df.to_csv(out_csv, index=False)
        d = df[(df.condition == name) & (df.seed == seed)]
        print(f"{name} seed {seed}: runaway {int(d.runaway.sum())}/{len(d)}, "
              f"median spikes {d.total_spikes.median():.0f}, onsets {d.onset_ms.dropna().tolist()}, "
              f"free RAM {free_ram_gb():.1f} GB", flush=True)
    np.savez_compressed(RESULTS / "reproduce_series.npz", keys=np.array(keys),
                        spikes_1ms=np.array(s1_all, np.int32), distinct_10ms=np.array(d10_all, np.int32))
    if nstats:
        np.savez_compressed(RESULTS / "main_neuron_stats.npz", **nstats)
print("finished", flush=True)

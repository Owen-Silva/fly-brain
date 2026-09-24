"""No-network baselines and a check of the task code (seconds, no brain).

- "delay line K": the readout sees the last K inputs directly (a perfect
  linear memory). Its memory capacity should come out close to K.
- "delay line 10 + products": the last 10 inputs plus all their pairwise
  products (a hand-built nonlinear memory). It should do well on XOR and
  NARMA-10, which a purely linear delay line cannot.
Same timeline, seeds and scoring as run_grid.py. Writes results/baselines.csv.
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_v] = "1"
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from run_grid import T_WASH, T_TR, T_VA, T_TE  # noqa: E402

T = T_WASH + T_TR + T_VA + T_TE
idx = {"tr": np.arange(T_WASH, T_WASH + T_TR),
       "va": np.arange(T_WASH + T_TR, T_WASH + T_TR + T_VA),
       "te": np.arange(T_WASH + T_TR + T_VA, T)}
rows = []
for seed in (0, 1, 2):
    u, y = lib.make_input(T, seed)
    Y = {k: lib.targets(u, y, v) for k, v in idx.items()}
    lag = np.stack([np.concatenate([np.zeros(k), u[:T - k]]) for k in range(100)], 1)
    feats = {f"delay line {K}": lag[:, :K] for K in (10, 30, 100)}
    prods = np.stack([lag[:, i] * lag[:, j] for i, j in combinations(range(10), 2)], 1)
    feats["delay line 10 + products"] = np.hstack([lag[:, :10], lag[:, :10] ** 2, prods])
    for name, F in feats.items():
        r = lib.ridge_scores(F[idx["tr"]], Y["tr"], F[idx["va"]], Y["va"], F[idx["te"]], Y["te"])
        rows.append({"baseline": name, "seed": seed, "features": F.shape[1], "mc": r["mc"],
                     "narma_nrmse": r["narma_nrmse"], "xor_acc": r["xor_acc"]})
df = pd.DataFrame(rows)
df.to_csv(lib.RESULTS / "baselines.csv", index=False, float_format="%.4f")
print(df.groupby("baseline")[["features", "mc", "narma_nrmse", "xor_acc"]].mean().round(3).to_string())

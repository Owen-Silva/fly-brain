"""Phase 6 checks on the two Hampel et al. 2015 mismatches (published model).

Plain English
-------------
Test F found two places where the published model disagrees with real flies:
  F1: driving JO-F (Hampel's "aJO") leaves aBN2_1-3 and aDN1 silent, but in real
      flies both respond;
  F7: driving aBN2_1-3 EXCITES aDN2 in the model, but INHIBITS it in real flies.
PLAN.md Phase 6 says to re-check a surprise with parameter variations before
believing it. This script re-runs the relevant conditions with the model's one
free parameter (w_syn, the strength of every synapse) at 0.8x and 1.2x the
paper's value (the paper's own robustness range, Supp. Table 11), and runs F7
with weaker aBN2 drive (50 and 100 Hz) and with each aBN2 cell driven alone.

Output: results/robustness.csv (one row per condition, variation and seed)
Usage:  python experiments/heldout/robustness.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import ids  # noqa: E402
from run_heldout import ABN2_2026, DNGE220, IN_RUN_MIN_GB, wait_for_ram  # noqa: E402

OUT = HERE / "results" / "robustness.csv"
W0 = 0.275
SEEDS = (0, 1, 2)
N_TRIALS = 30

# name: (stimulated IDs, rate, base seed, record aDN2 voltage?)
CONDS = {
    "F_220": (ids.JON_F, 220, 24_000, False),
    "ALL_220": (ids.JON_ALL, 220, 44_000, False),
    "aBN2x3_200": (ABN2_2026, 200, 52_000, True),
    "aBN2x3_100": (ABN2_2026, 100, 54_000, True),
    "aBN2x3_50": (ABN2_2026, 50, 55_000, True),
    "aBN2_1_200": ([ABN2_2026[0]], 200, 56_000, True),
    "aBN2_2_200": ([ABN2_2026[1]], 200, 57_000, True),
    "aBN2_3_200": ([ABN2_2026[2]], 200, 58_000, True),
}
# (variation name, w_syn, which conditions)
PLAN = [("w_syn x0.8", 0.8 * W0, ["F_220", "ALL_220", "aBN2x3_200"]),
        ("w_syn x1.2", 1.2 * W0, ["F_220", "ALL_220", "aBN2x3_200"]),
        ("baseline", W0, ["aBN2x3_100", "aBN2x3_50", "aBN2_1_200", "aBN2_2_200", "aBN2_3_200"])]


def main():
    from sim.sign_fixes import build_brain
    wait_for_ram()
    brain = build_brain(fix="none", n_threads=2)
    done = set()
    if OUT.exists():
        d = pd.read_csv(OUT)
        done = set(zip(d.variation, d.condition, d.seed))
    key = {"aBN1": ids.ABN1, "aDN1": ids.ADN1, "aDN2": ids.ADN2, "DNge220": DNGE220,
           "aBN2_1": ABN2_2026[0], "aBN2_2": ABN2_2026[1], "aBN2_3": ABN2_2026[2]}
    kidx = brain.index_of(list(key.values()))
    for var, w, conds in PLAN:
        for c in conds:
            stim, rate, base, rec = CONDS[c]
            for sd in SEEDS:
                if (var, c, base + sd) in done:
                    continue
                wait_for_ram(IN_RUN_MIN_GB)
                t0 = time.perf_counter()
                res = brain.run(excite=list(stim), duration_ms=1000.0, n_trials=N_TRIALS,
                                seed=base + sd, rate_hz=float(rate), params={"w_syn": w},
                                record_v=[ids.ADN2] if rec else [])
                cnt = np.bincount(res.neuron, minlength=brain.n_neurons)
                row = {"variation": var, "condition": c, "seed": base + sd, "w_syn": w}
                for (n, _), i in zip(key.items(), kidx):
                    row[f"{n}_hz"] = cnt[i] / N_TRIALS
                row["aDN2_mean_v_mV"] = (float(res.voltages_mV[ids.ADN2].mean()) if rec else np.nan)
                row["wall_s"] = round(time.perf_counter() - t0, 1)
                pd.DataFrame([row]).to_csv(OUT, mode="a", header=not OUT.exists(), index=False)
                print(f"  {var} {c} seed {base + sd}: aBN1 {row['aBN1_hz']:.1f} aDN1 {row['aDN1_hz']:.1f} "
                      f"aDN2 {row['aDN2_hz']:.1f} aBN2 mean "
                      f"{np.mean([row['aBN2_1_hz'], row['aBN2_2_hz'], row['aBN2_3_hz']]):.2f} "
                      f"v(aDN2) {row['aDN2_mean_v_mV']:.2f} mV; {row['wall_s']} s", flush=True)


if __name__ == "__main__":
    main()

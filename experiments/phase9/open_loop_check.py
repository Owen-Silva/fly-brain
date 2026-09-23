"""Phase 9 open-loop check (no body): does left vs right smell change the
steering neurons in the direction a steering rule needs?

Recommended in docs/phase9-body-research.md section 6.2 before closing the
loop. Uses the same window-by-window brain (sim/body/brain_stepper.py) and
the same DM1 smell neurons as the loop, with the rates the loop's sensor
mapping would give (sim/body/mapping.py: 75 Hz = odor at 10 mm).

Conditions (per brain variant, seeds 0-2, 1 s each in 50 ms windows):
  left_only  : left DM1 ORNs 150 Hz, right 0
  right_only : right 150 Hz, left 0
  both_equal : both 75 Hz
  left_more  : left 80 Hz, right 70 Hz (odor a bit to the LEFT, as in the loop)
  right_more : left 70 Hz, right 80 Hz (odor a bit to the RIGHT)

Output: experiments/phase9/results/open_loop_check.csv (+ printed table).
Run: .venv-body\\Scripts\\python.exe experiments/phase9/open_loop_check.py [fix ...]
"""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim.body.brain_stepper import BrainStepper  # noqa: E402
from sim.body.mapping import DN_IDS, DriveMapping, dm1_orn_ids  # noqa: E402
from sim import sign_fixes  # noqa: E402

OUT = ROOT / "experiments" / "phase9" / "results"
CONDITIONS = {
    "left_only": (150.0, 0.0), "right_only": (0.0, 150.0), "both_equal": (75.0, 75.0),
    "left_more": (80.0, 70.0), "right_more": (70.0, 80.0),
}
WINDOW_MS, DURATION_MS, SEEDS = 50.0, 1000.0, (0, 1, 2)


def run_fix(fix):
    left, right = dm1_orn_ids()
    orns = np.concatenate([left, right])
    brain = sign_fixes.build_brain(fix)
    dn_idx = brain.index_of(list(DN_IDS.values()))
    names = list(DN_IDS)
    mapping = DriveMapping()
    rows = []
    for cond, (rl, rr) in CONDITIONS.items():
        rates = np.concatenate([np.full(left.size, rl), np.full(right.size, rr)])
        for seed in SEEDS:
            st = BrainStepper(brain, orns, seed=seed)
            t0 = time.perf_counter()
            counts = []
            for _ in range(int(DURATION_MS / WINDOW_MS)):
                w = st.step(rates, WINDOW_MS)
                counts.append(w.count(dn_idx))
            wall = time.perf_counter() - t0
            counts = np.array(counts)                      # (windows, DNs)
            late = counts[len(counts) // 2:].sum(0) / (DURATION_MS / 2 * 1e-3)
            early = counts[:4].sum(0) / (4 * WINDOW_MS * 1e-3)
            r_late = dict(zip(names, late))
            turn = mapping.turn(r_late)
            row = {"fix": fix, "condition": cond, "seed": seed, "rate_left_hz": rl,
                   "rate_right_hz": rr, "neurons_reached": st.n_active,
                   "wall_s": round(wall, 1), "turn_late": round(turn, 3)}
            row.update({f"{n}_late_hz": v for n, v in r_late.items()})
            row.update({f"{n}_first200ms_hz": v for n, v in zip(names, early)})
            rows.append(row)
            print(f"{fix:>16} {cond:>10} s{seed}: DNa02 L/R {r_late['DNa02_L']:5.1f}/"
                  f"{r_late['DNa02_R']:5.1f}  DNa01 L/R {r_late['DNa01_L']:5.1f}/"
                  f"{r_late['DNa01_R']:5.1f}  DNg100 {r_late['DNg100_L']:5.1f}/"
                  f"{r_late['DNg100_R']:5.1f}  turn {turn:+.2f}  reached {st.n_active}"
                  f"  ({wall:.0f} s)", flush=True)
    del brain
    gc.collect()
    return rows


def main(fixes):
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for fix in fixes:
        rows += run_fix(fix)
    df = pd.DataFrame(rows)
    path = OUT / "open_loop_check.csv"
    if path.exists():
        old = pd.read_csv(path)
        df = pd.concat([old[~old.fix.isin(fixes)], df], ignore_index=True)
    df.to_csv(path, index=False)
    print(f"wrote {path}")


if __name__ == "__main__":
    main(sys.argv[1:] or ["none", sign_fixes.RECOMMENDED_FIX])

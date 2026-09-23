"""Phase 9 step 1: does FlyGym's walking run here, and which way does the
drive turn the fly? (No brain involved.)

Three 0.5 s walks from the same start (facing +x; +y is the fly's LEFT):
  straight     drive [1.0, 1.0]
  lower_left   drive [0.2, 1.0]   -> should veer LEFT  (+y, heading up)
  lower_right  drive [1.0, 0.2]   -> should veer RIGHT (-y, heading down)
Also checks that the left antenna sensor is on the fly's left (+y).

Output: experiments/phase9/results/walk_and_sign_check.csv (+ printed lines).
Run: .venv-body\\Scripts\\python.exe experiments/phase9/walk_and_sign_check.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

t_imp = time.perf_counter()
from sim.body.loop import Body  # noqa: E402
from sim.body.odor import SENSOR_ORDER  # noqa: E402
print(f"import FlyGym + loop: {time.perf_counter() - t_imp:.1f} s", flush=True)

OUT = ROOT / "experiments" / "phase9" / "results"
DRIVES = {"straight": (1.0, 1.0), "lower_left": (0.2, 1.0), "lower_right": (1.0, 0.2)}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for name, drive in DRIVES.items():
        t0 = time.perf_counter()
        body = Body((0.0, 0.0), 0.0, seed=0)
        t_build = time.perf_counter() - t0
        x0, y0, h0 = body.pose()
        sens = body.odor_sensor_positions()
        t1 = time.perf_counter()
        body.step(drive, 0.5)
        wall = time.perf_counter() - t1
        x1, y1, h1 = body.pose()
        z = body.thorax_z()
        body.close()
        la, ra = SENSOR_ORDER.index("LAntenna"), SENSOR_ORDER.index("RAntenna")
        row = {"drive": name, "drive_L": drive[0], "drive_R": drive[1],
               "dx_mm": x1 - x0, "dy_mm": y1 - y0,
               "heading_change_deg": float(np.degrees(np.angle(np.exp(1j * (h1 - h0))))),
               "thorax_z_end_mm": z, "wall_s_for_0.5s": wall, "build_s": t_build,
               "L_antenna_y_mm": sens[la, 1], "R_antenna_y_mm": sens[ra, 1],
               "antenna_separation_mm": float(np.linalg.norm(sens[la] - sens[ra])),
               "antenna_z_mm": float(sens[la, 2])}
        rows.append(row)
        print(f"{name:>12}: dx {row['dx_mm']:+.2f} mm  dy {row['dy_mm']:+.2f} mm  "
              f"heading {row['heading_change_deg']:+.1f} deg  thorax z {z:.2f} mm  "
              f"wall {wall:.1f} s (build {t_build:.1f} s)  antennae y L/R "
              f"{row['L_antenna_y_mm']:+.3f}/{row['R_antenna_y_mm']:+.3f} "
              f"sep {row['antenna_separation_mm']:.3f} mm", flush=True)
    pd.DataFrame(rows).to_csv(OUT / "walk_and_sign_check.csv", index=False)
    ok_left = rows[1]["heading_change_deg"] > 0 and rows[1]["dy_mm"] > rows[0]["dy_mm"]
    ok_right = rows[2]["heading_change_deg"] < 0 and rows[2]["dy_mm"] < rows[0]["dy_mm"]
    ok_ant = rows[0]["L_antenna_y_mm"] > rows[0]["R_antenna_y_mm"]
    print(f"lower LEFT drive turns LEFT: {ok_left}; lower RIGHT drive turns RIGHT: {ok_right}; "
          f"left antenna on the left: {ok_ant}")


if __name__ == "__main__":
    main()

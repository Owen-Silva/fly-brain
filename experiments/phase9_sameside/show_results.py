"""Print the closed-loop result tables written by analyze_sameside.py (for the write-up)."""
from pathlib import Path

import pandas as pd

R = Path(__file__).resolve().parent / "results"
pd.set_option("display.width", 250)
c = pd.read_csv(R / "ss_condition_table.csv")
cols = [x for x in ["condition", "n_trials", "reached", "mean_min_dist_mm", "mean_turn_left_1s_deg",
                    "frac_trials_turn_left_1s", "mean_turn_toward_source_1s_deg",
                    "frac_lateral_trials_toward", "mean_turn_toward_intact_1s_deg",
                    "frac_trials_toward_intact", "mean_min_dist_source_on_smelling_side_mm",
                    "reached_source_on_smelling_side", "mean_DNa02_L_hz", "mean_DNa02_R_hz",
                    "mean_orn_rate_L", "mean_orn_rate_R"] if x in c]
print(c[cols].round(2).to_string(index=False))
for f in ("ss_stats.csv", "ss_sign_tests.csv", "ss_paired_tests.csv", "ss_brain_vs_brain.csv"):
    d = pd.read_csv(R / f)
    if "condition" in d:
        d = d[~d.condition.str.startswith("old")] if f != "ss_brain_vs_brain.csv" else d
    print(f"== {f} ==")
    print(d.round(5).to_string(index=False))
t = pd.read_csv(R / "ss_trials.csv")
for (v, cond), d in t[~t.condition.str.contains("off|no_odor")].groupby(["variant", "condition"]):
    print(f"== {v}/{cond}: heading change in 1st s (deg) by layout x rep ==")
    print(d.pivot(index="layout", columns="rep", values="heading_change_1s_deg").round(0).to_string())

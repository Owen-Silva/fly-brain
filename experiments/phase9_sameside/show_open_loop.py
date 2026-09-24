"""Print compact tables of results/open_loop_summary.csv (for the write-up)."""
from pathlib import Path

import pandas as pd

s = pd.read_csv(Path(__file__).resolve().parent / "results" / "open_loop_summary.csv")
pd.set_option("display.width", 250)
cols = ["variant", "stimulus", "orn_L_hz", "orn_R_hz", "DNa02_L", "DNa02_R", "dna02_turn_hz",
        "dna02_turn_by_seed", "dna02_frac_right_sign", "dna02_frac_wrong_sign", "dna02_frac_silent",
        "dnpe002_turn_hz", "dnpe002_turn_by_seed", "PN_L", "PN_R", "DNae007_L", "DNae007_R"]
for g in ("DA1", "DM1"):
    d = s[s.glom == g][[c for c in cols if c in s]]
    print(f"== {g} ==")
    print(d.to_string(index=False, float_format=lambda x: f"{x:.1f}"))

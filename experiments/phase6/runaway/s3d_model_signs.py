"""Correction for results/strong_loops.txt: its "model sign" column came from
the Phase 2 label file, which agrees with the model's own signs for 98.5% of
neurons, not 100%. This script reads the signs the model actually uses (the
reference connectivity file) for the loop neurons, plus every connection
among them, without building the brain.

Output: results/strong_loop_members.csv, results/strong_loop_edges.csv
"""
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.compute as pc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import LABELS_630, RESULTS, ROOT  # noqa: E402

txt = (RESULTS / "strong_loops.txt").read_text(encoding="utf-8").splitlines()
ids, group, g = [], [], 0
for line in txt:
    if line.startswith("Loop group"):
        g += 1
    m = re.match(r"^  (\d{18})\s", line)
    if m:
        ids.append(int(m.group(1)))
        group.append(g)
ids = np.array(ids, np.int64)
t = pq.read_table(ROOT / "data/reference/2023_03_23_connectivity_630_final.parquet",
                  columns=["Presynaptic_ID", "Postsynaptic_ID", "Excitatory x Connectivity"],
                  filters=[("Presynaptic_ID", "in", ids.tolist())]).to_pandas()
sign = t.groupby("Presynaptic_ID")["Excitatory x Connectivity"].apply(lambda s: int(np.sign(s.iloc[0])))
lab = pd.read_parquet(LABELS_630, columns=["root_id", "cell_class", "hemibrain_type", "side", "top_nt",
                                           "top_nt_conf", "sign"]).set_index("root_id")
mem = lab.reindex(ids).reset_index().rename(columns={"sign": "label_file_sign"})
mem.insert(0, "loop_group", group)
mem["model_sign"] = sign.reindex(ids).to_numpy()
mem.to_csv(RESULTS / "strong_loop_members.csv", index=False)
e = t[t.Postsynaptic_ID.isin(ids)].copy()
e["pre_type"] = lab.hemibrain_type.reindex(e.Presynaptic_ID).to_numpy()
e["post_type"] = lab.hemibrain_type.reindex(e.Postsynaptic_ID).to_numpy()
e = e.sort_values("Excitatory x Connectivity", ascending=False)
e.to_csv(RESULTS / "strong_loop_edges.csv", index=False)
print(mem.to_string(index=False))
print(e[e["Excitatory x Connectivity"] >= 162].to_string(index=False))

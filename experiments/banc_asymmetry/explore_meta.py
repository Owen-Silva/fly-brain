"""Quick look at a harmonised meta table (BANC framework columns).

Usage: python explore_meta.py <path-to-meta.feather>
Prints the column list and the label values for smell receptor neurons (ORNs)
and antennal-lobe projection neurons (PNs). Read-only, small memory.
"""
import sys
from pathlib import Path

import pyarrow.feather as pf
import pyarrow.ipc as ipc
import pandas as pd

path = Path(sys.argv[1])
schema = ipc.open_file(path).schema
print("columns:", len(schema.names))
print(", ".join(schema.names))

want = [c for c in ["root_id", "banc_888_id", "super_class", "cell_class", "cell_sub_class",
                    "cell_type", "side", "nerve", "proofread", "roughly_proofread",
                    "fafb_cell_type", "hemibrain_cell_type", "status", "root_region",
                    "region", "flow", "soma_side", "root_side"] if c in schema.names]
m = pf.read_table(path, columns=want).to_pandas()
print("rows:", len(m))
for c in ("super_class", "cell_class"):
    if c in m:
        vc = m[c].value_counts(dropna=False)
        print(f"\n{c}: {len(vc)} values; top 40:")
        print(vc.head(40).to_string())

cc = m["cell_class"].astype("string").fillna("")
ct = m["cell_type"].astype("string").fillna("")
olf = cc.str.contains("olfactory", case=False) | ct.str.startswith("ORN")
print("\nolfactory-ish rows:", int(olf.sum()))
print(m[olf].groupby(["cell_class", "side"], dropna=False).size().to_string())
if "nerve" in m:
    print(m[olf].groupby(["side", "nerve"], dropna=False).size().to_string())
print("ORN cell_type examples:", sorted(ct[olf].unique())[:15])

pn = cc.str.contains("projection", case=False) & cc.str.contains("antennal|lobe|AL", case=False)
print("\nAL PN-ish rows:", int(pn.sum()))
print(m[pn].groupby(["cell_class", "side"], dropna=False).size().to_string())
if "cell_sub_class" in m:
    print(m[pn].cell_sub_class.value_counts(dropna=False).head(20).to_string())
print("PN cell_type examples:", sorted(ct[pn].unique())[:25])
for c in ("proofread", "roughly_proofread"):
    if c in m:
        print(c, "ORN:", m[olf][c].value_counts(dropna=False).to_dict(),
              "PN:", m[pn][c].value_counts(dropna=False).to_dict())

"""Step 0b: why does the 783 rule pick 17 cells the 630 fix does not?

Plain English: each of the 17 extra cells is looked up in 630 through its
supervoxel, and its 630 label and 630 model sign are printed next to the 783
ones. Output: results/extra_cells_783.csv (and printed).
"""

import numpy as np
import pandas as pd

import common783 as C
from sim import sign_fixes as S

fix783 = pd.read_csv(C.RESULTS / "fix_cells_783.csv")
extra = fix783[~fix783.from_630_fix].copy()
a630 = pd.read_csv(C.ANN_630, sep="\t", usecols=["supervoxel_id", "root_id"],
                   dtype={"root_id": "int64", "supervoxel_id": "int64"})
a783 = pd.read_csv(C.ANN_783, sep="\t", usecols=["supervoxel_id", "root_id"],
                   dtype={"root_id": "int64", "supervoxel_id": "int64"})
sv783 = a783.drop_duplicates("root_id").set_index("root_id").supervoxel_id
sv2r630 = a630.drop_duplicates("supervoxel_id").set_index("supervoxel_id").root_id
rid630, pre, post, signed = S.load_reference_arrays("630")
sign630 = C.neuron_signs(rid630.size, pre, signed)
del pre, post, signed
lab630 = S.neuron_table(rid630).set_index("root_id")
row630 = {int(r): i for i, r in enumerate(rid630)}
out = []
for _, r in extra.iterrows():
    sv = int(sv783.get(int(r.root_id_783), -1))
    r630 = int(sv2r630.get(sv, -1)) if sv > 0 else -1
    if r630 < 0 and int(r.root_id_783) in row630:
        r630 = int(r.root_id_783)
    d = dict(root_id_783=int(r.root_id_783), role_783=r.role_783, cell_type_783=r.cell_type,
             known_nt_783=r.known_nt, top_nt_783=r.top_nt, root_id_630=r630,
             in_630_model=r630 in row630)
    if r630 in row630:
        L = lab630.loc[r630]
        d.update(cell_class_630=L.cell_class, type_630=L.hemibrain_type or L.cell_type,
                 top_nt_630=L.top_nt, known_nt_630=L.known_nt, model_sign_630=int(sign630[row630[r630]]))
    out.append(d)
df = pd.DataFrame(out)
df.to_csv(C.RESULTS / "extra_cells_783.csv", index=False)
with pd.option_context("display.width", 250, "display.max_columns", 20):
    print(df.drop(columns=["root_id_783", "root_id_630"]).to_string())

"""Quick look at the hemibrain v1.2.1 and maleCNS v0.9 harmonised tables (labels + edge schema)."""
from pathlib import Path

import pandas as pd
import pyarrow.feather as pf
import pyarrow.ipc as ipc

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data/banc"

for name, meta, edges in (("hemibrain", D / "hemibrain_121/hemibrain_121_meta.feather",
                           D / "hemibrain_121/hemibrain_121_simple_edgelist.feather"),
                          ("malecns", D / "malecns_09/malecns_09_meta.feather",
                           D / "malecns_09/malecns_09_simple_edgelist.feather")):
    print("=====", name)
    r = ipc.open_file(edges)
    print("edge schema:", r.schema.names, [str(t) for t in r.schema.types])
    print("batches", r.num_record_batches, "rows in batch0", r.get_batch(0).num_rows)
    print(r.get_batch(0).slice(0, 2).to_pandas().to_string())
    m = pf.read_table(meta).to_pandas()
    cc = m.cell_class.astype("string").fillna("")
    ct = m.cell_type.astype("string").fillna("")
    orn = cc.eq("olfactory_receptor_neuron") & ct.str.startswith("ORN_")
    pn = cc.eq("antennal_lobe_projection_neuron")
    print("ORNs typed:", int(orn.sum()), " PNs:", int(pn.sum()))
    cols = [c for c in ("side", "nerve", "instance", "cropped", "status", "region") if c in m.columns]
    for c in cols:
        print(f"-- ORN {c}:", m[orn][c].astype("string").fillna("NA").value_counts().head(8).to_dict())
        print(f"-- PN  {c}:", m[pn][c].astype("string").fillna("NA").value_counts().head(8).to_dict())
    if "side" in m.columns and "nerve" in m.columns:
        print(pd.crosstab(m[orn].side.fillna("NA"), m[orn].nerve.fillna("NA")).to_string())
    if "instance" in m.columns:
        print("ORN instance examples:", m[orn].instance.astype("string").sample(8, random_state=0).tolist())
        print("PN instance examples:", m[pn].instance.astype("string").sample(8, random_state=0).tolist())
    idcol = [c for c in m.columns if c.endswith("_id")][0]
    print("id column:", idcol, m[idcol].dtype)

"""Step 1: pull the small pieces of BANC this lane needs, with low memory.

BANC = brain and nerve cord of a second adult female fly (Bates, Phelps, Kim, Yang
et al.; data release v888, CAVE materialization of 2026-04-16), public files from
gs://lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/banc_888/ (no login).

Writes to data/banc/derived/ (never committed):
  banc_neurons.parquet   one row per neuron in the meta table (id + the labels used here)
  banc_v2_edges.parquet  connections whose sender is a smell receptor neuron (ORN)
                         or whose receiver is an antennal-lobe projection neuron (PN),
                         from banc_888_edgelist_simple_v2.feather (synapses of size >= 5
                         voxels, no per-connection minimum: the paper's table)
  banc_v3_edges.parquet  the same from the v3 table (newer detector, size >= 10)
The edge lists are streamed batch by batch (180 batches of 65,536 rows) and filtered
before anything is kept, so peak memory stays around 300 MB.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as pf
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SRC = ROOT / "data/banc"
OUT = SRC / "derived"
OUT.mkdir(exist_ok=True)

META_COLS = ["banc_888_id", "proofread", "roughly_proofread", "status", "side", "position",
             "root_position_nm", "root_region", "region", "nerve", "super_class", "cell_class",
             "cell_sub_class", "cell_type", "fafb_cell_type", "hemibrain_cell_type",
             "output_side_index", "input_side_index"]


def neurons():
    path = SRC / "banc_888_meta.feather"
    have = ipc.open_file(path).schema.names
    cols = [c for c in META_COLS if c in have]
    m = pf.read_table(path, columns=cols).to_pandas()
    m["banc_888_id"] = m.banc_888_id.astype("int64")
    for c in ("proofread", "roughly_proofread"):
        m[c] = m[c].astype("string").eq("TRUE").fillna(False)
    xyz = m.root_position_nm.astype("string").str.strip("[]() ").str.split(r"[,\s]+", expand=True)
    for i, a in enumerate("xyz"):
        m[f"root_{a}_um"] = pd.to_numeric(xyz[i], errors="coerce") / 1000
    xyz = m.position.astype("string").str.strip("[]() ").str.split(r"[,\s]+", expand=True)
    for i, (a, s) in enumerate(zip("xyz", (4, 4, 45))):
        m[f"soma_{a}_um"] = pd.to_numeric(xyz[i], errors="coerce") * s / 1000
    m = m.drop(columns=["root_position_nm", "position"])
    dup = m.banc_888_id.duplicated().sum()
    if dup:
        print("duplicate ids dropped:", dup)
        m = m.drop_duplicates("banc_888_id")
    m.to_parquet(OUT / "banc_neurons.parquet", index=False)
    return m


def extract(version, orn_ids, pn_ids):
    path = SRC / f"banc_888_edgelist_simple_{version}.feather"
    out = OUT / f"banc_{version}_edges.parquet"
    r = ipc.open_file(path)
    orn_set = pa.array(np.sort(orn_ids), type=pa.int64())
    pn_set = pa.array(np.sort(pn_ids), type=pa.int64())
    keep, total_rows, total_syn = [], 0, 0
    for i in range(r.num_record_batches):
        b = r.get_batch(i)
        pre = pc.cast(b.column("pre"), pa.int64())
        post = pc.cast(b.column("post"), pa.int64())
        cnt = b.column("count")
        total_rows += b.num_rows
        total_syn += pc.sum(cnt).as_py() or 0
        mask = pc.or_(pc.is_in(pre, value_set=orn_set), pc.is_in(post, value_set=pn_set))
        if pc.sum(pc.cast(mask, pa.int64())).as_py():
            keep.append(pa.table({"pre": pc.filter(pre, mask), "post": pc.filter(post, mask),
                                  "count": pc.filter(cnt, mask)}))
    t = pa.concat_tables(keep)
    pq.write_table(t, out)
    print(f"{version}: scanned {total_rows:,} connections ({total_syn:,} synapses); kept {t.num_rows:,}; "
          f"min count kept {pc.min(t.column('count')).as_py()}")


def main():
    m = neurons()
    cc = m.cell_class.astype("string").fillna("")
    ct = m.cell_type.astype("string").fillna("")
    orn = cc.eq("olfactory_receptor_neuron") | ct.str.startswith("ORN")
    pn = cc.eq("antennal_lobe_projection_neuron")
    print(f"meta rows {len(m):,}; ORN-like {int(orn.sum())}; AL PNs {int(pn.sum())}")
    print("root_x_um range", float(m.root_x_um.min()), float(m.root_x_um.max()),
          "soma_x_um non-null", int(m.soma_x_um.notna().sum()))
    for v in ("v2", "v3"):
        if (OUT / f"banc_{v}_edges.parquet").exists():
            print(v, "already extracted; delete the file to redo")
            continue
        extract(v, m.banc_888_id[orn].to_numpy(), m.banc_888_id[pn].to_numpy())


if __name__ == "__main__":
    main()

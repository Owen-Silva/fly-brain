"""Step 0: prove common.orn_pn_tables reproduces FlyWire's saved Phase 6 tables exactly.

Runs the ported code on the local FlyWire caches (snapshots 630 and 783) with the
same labels s1_anatomy.py used, and compares against
experiments/phase6/steering/results/glomerulus_map_{630,783}.csv and
pn_ipsi_contra_{630,783}.csv. Also prints the section-3 summary numbers
(41/51 same-side stronger, median 1.25, 32/51 mirror, 35/51 left bigger, boosts 35/42/45/46).
Edges are filtered while reading (only rows whose pre is an ORN), so memory stays small.

Output: results/flywire_{630,783}_glomerulus_map.csv, results/flywire_summary.csv,
results/port_check.txt
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
RES.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
from common import orn_pn_tables, summary  # noqa: E402

OLD = ROOT / "experiments/phase6/steering/results"


def flywire_inputs(snap):
    n = pd.read_parquet(ROOT / f"data/cache/connectome_{snap}_neurons.parquet",
                        columns=["root_id", "cell_class", "hemibrain_type", "cell_type", "side", "soma_x_nm"])
    col = "hemibrain_type" if snap == "630" else "cell_type"
    t = n[col].astype("string")
    is_orn = ((n.cell_class == "olfactory").fillna(False) & t.str.startswith("ORN_").fillna(False)).astype(bool)
    glom = t.where(is_orn).str.replace("ORN_", "", regex=False).to_numpy(dtype=object)
    glom = np.array([None if (g is pd.NA or g is None or (isinstance(g, float) and np.isnan(g))) else g
                     for g in glom], dtype=object)
    pn_mask = (n.cell_class == "ALPN").fillna(False).to_numpy(bool)
    side = n.side.astype("string").fillna("na").to_numpy(dtype=object)
    orn_idx = np.flatnonzero(is_orn.to_numpy())
    e = pq.read_table(ROOT / f"data/cache/connectome_{snap}_edges.parquet",
                      columns=["pre", "post", "syn_count"],
                      filters=[("pre", "in", orn_idx.astype(np.int32).tolist())]).to_pandas()
    # soma offset from midline, as s1 did (midline = mean of left/right median soma x)
    s = n[n.side.isin(["left", "right"])].groupby("side").soma_x_nm.median()
    mid = float((s["left"] + s["right"]) / 2)
    off = (n.soma_x_nm.to_numpy() - mid) / 1000
    return side, glom, pn_mask, e, n.root_id.to_numpy(), n.hemibrain_type.astype("string").to_numpy(), off


def main():
    lines, summ = [], []
    for snap in ("630", "783"):
        side, glom, pn_mask, e, rid, ptype, off = flywire_inputs(snap)
        pn, gm, _ = orn_pn_tables(side, glom, pn_mask, e, rid, ptype, label=snap, soma_offset_um=off)
        gm.to_csv(RES / f"flywire_{snap}_glomerulus_map.csv", index=False)
        old = pd.read_csv(OLD / f"glomerulus_map_{snap}.csv")
        new = gm.copy()
        new["snapshot"] = new.snapshot.astype(int)
        cols = [c for c in old.columns]
        a = old.sort_values("glomerulus").reset_index(drop=True)[cols]
        b = new.sort_values("glomerulus").reset_index(drop=True)[cols]
        same_shape = a.shape == b.shape
        eq = same_shape and all(
            (np.allclose(a[c].to_numpy(float), b[c].to_numpy(float), equal_nan=True)
             if a[c].dtype.kind in "fiub" else (a[c].astype(str) == b[c].astype(str)).all())
            for c in cols)
        lines.append(f"FlyWire {snap}: glomerulus map rows old={len(old)} new={len(gm)}; identical={eq}")
        oldpn = pd.read_csv(OLD / f"pn_ipsi_contra_{snap}.csv")
        k = ["pn_root_id", "glomerulus", "pn_side", "from_ipsi_orns", "from_contra_orns"]
        m = oldpn[k].merge(pn[k], on="pn_root_id", how="outer", suffixes=("_old", "_new"), indicator=True)
        same_pn = (m._merge == "both").all() and all(
            (m[f"{c}_old"].astype(str) == m[f"{c}_new"].astype(str)).all() for c in k[1:])
        lines.append(f"FlyWire {snap}: per-PN table rows old={len(oldpn)} new={len(pn)}; identical={same_pn}")
        s = summary(gm, f"FlyWire {snap}")
        summ.append(s)
        lines.append(f"  summary: {s}")
    pd.DataFrame(summ).to_csv(RES / "flywire_summary.csv", index=False)
    (RES / "port_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

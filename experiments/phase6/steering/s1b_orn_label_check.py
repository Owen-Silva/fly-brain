"""Phase 6 steering check, step 1b: is each ORN's side label believable?

Plain English
-------------
An ORN's side label is the antenna (nerve) it enters the brain from. We cannot
see the nerve here, but the literature gives a fingerprint: an ORN makes MORE
synapses onto projection neurons (PNs) on its own side than onto PNs on the
other side (Tobin et al. 2017; Schlegel et al. 2021; Taisz et al. 2023). So for
every ORN we compute its "same-side share": synapses onto same-labelled-side
PNs divided by all its synapses onto PNs. A correctly labelled ORN should be
above 0.5 more often than not; a group of wrongly labelled ORNs would show up
as a pile-up below 0.5. We also look at the ORNs whose "anchor" point (a
reference point FlyWire places on the neuron) lies on the other side of the
midline from their label.

Output: results/orn_label_check_630.csv (one row per ORN) and a printed summary.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = HERE / "results"


def main():
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet")
    e = pd.read_parquet(ROOT / "data/cache/connectome_630_edges.parquet", columns=["pre", "post", "syn_count"])
    side = n.side.astype("string").fillna("na").to_numpy()
    t = n.hemibrain_type.astype("string")
    is_orn = ((n.cell_class == "olfactory").fillna(False) & t.str.startswith("ORN_").fillna(False)).to_numpy(bool)
    is_pn = (n.cell_class == "ALPN").fillna(False).to_numpy(bool)
    s = n[n.side.isin(["left", "right"])].groupby("side").soma_x_nm.median()
    mid = (s["left"] + s["right"]) / 2
    x = e[is_orn[e.pre.to_numpy()] & is_pn[e.post.to_numpy()]]
    same = side[x.pre.to_numpy()] == side[x.post.to_numpy()]
    df = pd.DataFrame({"pre": x.pre.to_numpy(), "same": x.syn_count.to_numpy() * same,
                       "all": x.syn_count.to_numpy()}).groupby("pre").sum()
    df["same_side_share"] = df["same"] / df["all"]
    df["root_id"] = n.root_id.to_numpy()[df.index]
    df["glomerulus"] = t.to_numpy()[df.index]
    df["label"] = side[df.index]
    ax = n.anchor_x_nm.to_numpy()[df.index]
    df["anchor_on_label_side"] = np.where(df.label == "left", ax < mid, ax > mid)
    df = df[df.label.isin(["left", "right"])]
    df.to_csv(RES / "orn_label_check_630.csv", index=False)
    print("ORNs:", len(df))
    print("same-side share, all ORNs: median %.3f; fraction > 0.5: %.3f"
          % (df.same_side_share.median(), (df.same_side_share > 0.5).mean()))
    print("histogram (0-0.1, ..., 0.9-1):", np.histogram(df.same_side_share, bins=np.linspace(0, 1, 11))[0].tolist())
    for k, g in df.groupby("anchor_on_label_side"):
        print(f"anchor on label side = {k}: n={len(g)}, median same-side share {g.same_side_share.median():.3f}")
    d = df[df.glomerulus == "ORN_DM1"]
    print("DM1 ORNs by label: median same-side share",
          d.groupby("label").same_side_share.median().round(3).to_dict(),
          "; fraction > 0.5:", d.groupby("label").same_side_share.apply(lambda v: (v > 0.5).mean()).round(2).to_dict())
    # by glomerulus: how many glomeruli have median same-side share > 0.5 for each label
    gm = df.groupby(["glomerulus", "label"]).same_side_share.median().unstack()
    print("glomeruli with median same-side share > 0.5: left ORNs %d, right ORNs %d, of %d"
          % ((gm.left > 0.5).sum(), (gm.right > 0.5).sum(), len(gm)))


if __name__ == "__main__":
    main()

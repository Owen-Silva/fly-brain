"""Step 1 (PRELIMINARY): who are the two CB0216 neurons and how are they wired?

Reads only (nothing in data/ is changed):
  * snapshot-630 labels + FlyWire annotation (cell type, hemilineage, predicted
    transmitter and its confidence), and the v783 annotation (known_nt =
    FlyWire's literature column) matched by supervoxel, as sim/sign_fixes does;
  * the model's connection list after the default fix (al_ln_literature);
  * the v783 proofread connection table (per-neuropil synapse counts and the
    per-connection transmitter scores ach/gaba/glut/...);
  (the other connectomes are checked in cross_datasets.py).
Writes results/identify.json and prints a summary.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.feather as feather

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from sim.sign_fixes import (ANN_630, ANN_783, apply_fix, load_reference_arrays,  # noqa: E402
                            neuron_table)

PAIR = [720575940633316307, 720575940636552805]   # right, left (snapshot 630)
TYPE = "CB0216"
out = {"pair_630": PAIR}

root_ids, pre, post, signed = load_reference_arrays("630")
lab = neuron_table(root_ids)
pre2, post2, s2, _ = apply_fix("al_ln_literature", root_ids, pre, post, signed, lab)
del pre, post, signed
idx = {int(r): i for i, r in enumerate(root_ids)}
ia, ib = idx[PAIR[0]], idx[PAIR[1]]
cols = ["root_id", "cell_type", "hemibrain_type", "side", "top_nt", "top_nt_conf",
        "known_nt", "known_nt_source", "matched_783"]
out["labels"] = lab.loc[[ia, ib], cols].astype(str).to_dict("records")
a630 = pd.read_csv(ANN_630, sep="\t", dtype=str)
out["ann_630"] = a630[a630.root_id.isin([str(p) for p in PAIR])].dropna(axis=1).to_dict("records")

# v783 row via supervoxel
a783 = pd.read_csv(ANN_783, sep="\t", dtype=str)
svs = a630.set_index("root_id").loc[[str(p) for p in PAIR], "supervoxel_id"].tolist()
r783 = a783[a783.supervoxel_id.isin(svs)]
out["ann_783"] = r783.dropna(axis=1).to_dict("records")
same_type_783 = a783[a783.cell_type == TYPE]
out["n_type_783"] = int(len(same_type_783))
ids783 = [int(x) for x in r783.root_id]
print("783 rows:", r783[["root_id", "cell_type", "top_nt", "top_nt_conf", "known_nt",
                          "ito_lee_hemilineage", "side"]].to_string(index=False))


def model_edges(a, b):
    m = (pre2 == a) & (post2 == b)
    return int(s2[m].sum()) if m.any() else 0


out["model_syn"] = {"right_to_left": model_edges(ia, ib), "left_to_right": model_edges(ib, ia),
                    "self_right": model_edges(ia, ia), "self_left": model_edges(ib, ib)}
print("model signed synapses:", out["model_syn"])

# top partners in the model
tops = {}
for name, i in (("right", ia), ("left", ib)):
    for direc, mine, other in (("in", post2, pre2), ("out", pre2, post2)):
        m = mine == i
        d = pd.DataFrame({"j": other[m], "w": s2[m]}).sort_values("w", key=np.abs,
                                                                   ascending=False)
        tot_exc = int(d.w[d.w > 0].sum()); tot_inh = int(-d.w[d.w < 0].sum())
        d = d.head(12)
        rows = [{"root_id": int(root_ids[j]), "cell_type": lab.cell_type[j],
                 "top_nt": lab.top_nt[j], "w": int(w)} for j, w in zip(d.j, d.w)]
        tops[f"{name}_{direc}"] = {"exc_total": tot_exc, "inh_total": tot_inh, "top": rows}
out["partners"] = tops
for k, v in tops.items():
    print(k, "exc", v["exc_total"], "inh", v["inh_total"], "|",
          ", ".join(f"{r['cell_type'] or '?'}({r['top_nt'][:4]}){r['w']}" for r in v["top"][:8]))

# v783 proofread connections: neuropils + per-synapse transmitter scores
con = feather.read_table(ROOT / "data/flywire/proofread_connections_783.feather").to_pandas()
if len(ids783) == 2:
    side = dict(zip(r783.root_id.astype(int), r783.side))
    pair = con[(con.pre_pt_root_id.isin(ids783)) & (con.post_pt_root_id.isin(ids783))]
    out["v783_pair_edges"] = pair.assign(
        pre_side=pair.pre_pt_root_id.map(side), post_side=pair.post_pt_root_id.map(side)
    ).drop(columns=["pre_pt_root_id", "post_pt_root_id"]).round(3).to_dict("records")
    print(pair.assign(pre=pair.pre_pt_root_id.map(side), post=pair.post_pt_root_id.map(side))
          .drop(columns=["pre_pt_root_id", "post_pt_root_id"]).round(2).to_string(index=False))
    # neuron-level transmitter scores (synapse-weighted over all outgoing connections)
    nts = ["ach_avg", "gaba_avg", "glut_avg", "oct_avg", "ser_avg", "da_avg"]
    nt_rows = {}
    for rid in ids783:
        o = con[con.pre_pt_root_id == rid]
        w = o.syn_count.to_numpy(float)
        nt_rows[side[rid]] = {c: float(np.average(o[c], weights=w)) for c in nts}
        nt_rows[side[rid]]["n_out_syn_783"] = int(w.sum())
        np_out = o.groupby("neuropil").syn_count.sum().sort_values(ascending=False)
        nt_rows[side[rid]]["out_neuropils"] = {k: int(v) for k, v in np_out.head(6).items()}
        i_ = con[con.post_pt_root_id == rid].groupby("neuropil").syn_count.sum()
        nt_rows[side[rid]]["in_neuropils"] = {k: int(v) for k, v in
                                              i_.sort_values(ascending=False).head(6).items()}
    out["v783_nt_scores"] = nt_rows
    print(json.dumps(nt_rows, indent=1))
del con

# other connectomes: see cross_datasets.py

(HERE / "results").mkdir(exist_ok=True)
(HERE / "results" / "identify.json").write_text(json.dumps(out, indent=1, default=str))
print("wrote results/identify.json")

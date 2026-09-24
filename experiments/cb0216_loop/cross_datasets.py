"""Step 1b (PRELIMINARY): is the CB0216 pair, and its strong mutual wiring, also in
the other connectomes shipped with the project (maleCNS 0.9, BANC 888,
hemibrain 1.2.1), and what transmitter do THEY predict for it?

A neuron is matched by any type column equal to "CB0216" (fafb_cell_type,
cell_type, ...). Reads data/banc only; writes results/cross_datasets.json.
"""
import json
from pathlib import Path

import pyarrow.feather as feather
import pyarrow.compute as pc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TYPE = "CB0216"
SETS = (
    ("malecns_09", "data/banc/malecns_09/malecns_09_meta.feather",
     "data/banc/malecns_09/malecns_09_simple_edgelist.feather", "malecns_09_id"),
    ("banc_888", "data/banc/banc_888_meta.feather",
     "data/banc/banc_888_edgelist_simple_v3.feather", "banc_888_id"),
    ("hemibrain_121", "data/banc/hemibrain_121/hemibrain_121_meta.feather",
     "data/banc/hemibrain_121/hemibrain_121_simple_edgelist.feather", "hemibrain_121_id"),
)
KEEP = ["cell_type", "fafb_cell_type", "fafb_alignment_cell_type", "hemibrain_cell_type",
        "malecns_cell_type", "side", "hemilineage", "region", "super_class",
        "neurotransmitter_predicted", "neurotransmitter_score", "neurotransmitter_verified"]

out = {}
for name, meta_f, edge_f, idcol in SETS:
    meta = feather.read_table(ROOT / meta_f).to_pandas()
    tcols = [c for c in meta.columns if "type" in c]
    hit = None
    for c in tcols:
        h = meta[c].astype("string").str.fullmatch(TYPE).fillna(False).to_numpy(bool)
        hit = h if hit is None else (hit | h)
    m = meta[hit]
    info = {"n_match": int(len(m))}
    if len(m):
        info["rows"] = m[[idcol] + [c for c in KEEP if c in m.columns]].astype(str).to_dict("records")
        ids = m[idcol].astype(str).tolist()
        t = feather.read_table(ROOT / edge_f, columns=["pre", "post", "count"])
        pre_s = pc.cast(t["pre"], "string")
        post_s = pc.cast(t["post"], "string")
        import pyarrow as pa
        vals = pa.array(ids, pa.string())
        mask_any = pc.or_(pc.is_in(pre_s, value_set=vals), pc.is_in(post_s, value_set=vals))
        sub = t.filter(mask_any).to_pandas()
        del t
        sub["pre"] = sub["pre"].astype(str)
        sub["post"] = sub["post"].astype(str)
        pair = sub[sub.pre.isin(ids) & sub.post.isin(ids)]
        info["pair_edges"] = pair.to_dict("records")
        info["out_syn"] = {i: int(sub[sub.pre == i]["count"].sum()) for i in ids}
        info["in_syn"] = {i: int(sub[sub.post == i]["count"].sum()) for i in ids}
        for i in ids:  # share of each neuron's output that goes to its partner(s)
            o = sub[sub.pre == i].sort_values("count", ascending=False).head(3)
            info.setdefault("top_out", {})[i] = o[["post", "count"]].to_dict("records")
    out[name] = info
    print(name, json.dumps(info, default=str)[:2000], flush=True)
    del meta

(HERE / "results" / "cross_datasets.json").write_text(json.dumps(out, indent=1, default=str))
print("wrote results/cross_datasets.json")

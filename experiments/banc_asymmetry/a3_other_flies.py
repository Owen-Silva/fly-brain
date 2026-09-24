"""Step 3: two more flies, from the same public bucket, through the same code.

  hemibrain v1.2.1 (Janelia; a third female fly; only the RIGHT antennal lobe is
    complete, so only same-side vs other-side input to right PNs can be measured)
  maleCNS v0.9 (Janelia; a male fly, both antennal lobes; ORNs are mostly only
    "roughly traced", so its ORN numbers are the least reliable of the four)

Both are read from the BANC team's harmonised copies
(gs://lee-lab_brain-and-nerve-cord-fly-connectome/compiled_data/{hemibrain_121,malecns_09}/),
which use BANC column names. Edge lists are streamed and filtered (ORN senders or PN
receivers only); the maleCNS list is 3.4 GB / 143 M rows, read 65,536 rows at a time.

Labels: ORN = cell_class olfactory_receptor_neuron + cell_type ORN_<glomerulus>; ORN side =
entry `nerve` side; PN = cell_class antennal_lobe_projection_neuron; PN side = `side`
(maleCNS) or the _L/_R suffix of `instance` (hemibrain). Which ORN label (nerve or side
column) behaves like a real side label is checked with the same-side fingerprint.

Outputs: data/banc/derived/{hemibrain,malecns}_edges.parquet (cache),
results/{malecns}_glomerulus_map.csv, results/other_flies_summary.csv,
results/hemibrain_right_al.csv, results/other_flies_label_checks.csv
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.feather as pf
import pyarrow.ipc as ipc
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
D = ROOT / "data/banc"
DER = D / "derived"
RES = HERE / "results"
sys.path.insert(0, str(HERE))
from common import orn_pn_tables, summary  # noqa: E402

SETS = {"hemibrain": ("hemibrain_121/hemibrain_121_meta.feather",
                      "hemibrain_121/hemibrain_121_simple_edgelist.feather", "hemibrain_121_id"),
        "malecns": ("malecns_09/malecns_09_meta.feather",
                    "malecns_09/malecns_09_simple_edgelist.feather", "malecns_09_id")}


def meta(name):
    mf, _, idc = SETS[name]
    m = pf.read_table(D / mf).to_pandas()
    m["nid"] = pd.to_numeric(m[idc], errors="coerce").astype("int64")
    m = m.drop_duplicates("nid").reset_index(drop=True)
    cc = m.cell_class.astype("string").fillna("")
    ct = m.cell_type.astype("string").fillna("")
    m["is_orn"] = (cc.eq("olfactory_receptor_neuron") & ct.str.startswith("ORN_")).to_numpy(bool)
    m["is_pn"] = cc.eq("antennal_lobe_projection_neuron").to_numpy(bool)
    nerve = m.nerve.astype("string").fillna("")
    m["nerve_side"] = np.where(nerve.str.startswith("left_"), "left",
                               np.where(nerve.str.startswith("right_"), "right", "na"))
    if "side" in m.columns:
        m["side_col"] = m.side.astype("string").fillna("na")
    else:
        inst = m.instance.astype("string").fillna("")
        m["side_col"] = np.where(inst.str.endswith("_L"), "left",
                                 np.where(inst.str.endswith("_R"), "right", "na"))
    return m


def extract(name, m):
    out = DER / f"{name}_edges.parquet"
    if out.exists():
        return pd.read_parquet(out)
    _, ef, _ = SETS[name]
    r = ipc.open_file(D / ef)
    orn_set = pa.array(np.sort(m.nid[m.is_orn].to_numpy()), type=pa.int64())
    pn_set = pa.array(np.sort(m.nid[m.is_pn].to_numpy()), type=pa.int64())
    keep, rows = [], 0
    for i in range(r.num_record_batches):
        b = r.get_batch(i)
        pre = pc.cast(b.column("pre"), pa.int64())
        post = pc.cast(b.column("post"), pa.int64())
        rows += b.num_rows
        mask = pc.or_(pc.is_in(pre, value_set=orn_set), pc.is_in(post, value_set=pn_set))
        if pc.any(mask).as_py():
            keep.append(pa.table({"pre": pc.filter(pre, mask), "post": pc.filter(post, mask),
                                  "count": pc.filter(b.column("count"), mask)}))
        if i % 300 == 0:
            print(f"  {name}: batch {i}/{r.num_record_batches}", flush=True)
    t = pa.concat_tables(keep)
    pq.write_table(t, out)
    print(f"{name}: scanned {rows:,} connections, kept {t.num_rows:,}, min count {pc.min(t.column('count')).as_py()}")
    return t.to_pandas()


def to_index(m, e):
    idx = pd.Series(np.arange(len(m)), index=m.nid.to_numpy())
    pre = idx.reindex(e.pre.to_numpy()).to_numpy()
    post = idx.reindex(e.post.to_numpy()).to_numpy()
    ok = ~(np.isnan(pre) | np.isnan(post))
    return pd.DataFrame({"pre": pre[ok].astype(np.int64), "post": post[ok].astype(np.int64),
                         "syn_count": e["count"].to_numpy()[ok].astype(np.int64)})


def arrays(m, orn_side_src):
    side = m.side_col.to_numpy(dtype=object).copy()
    if orn_side_src == "nerve":
        s = np.where(m.nerve_side != "na", m.nerve_side, m.side_col)
        side = np.where(m.is_orn, s, side).astype(object)
    glom = np.full(len(m), None, dtype=object)
    ct = m.cell_type.astype("string")
    glom[m.is_orn.to_numpy()] = ct[m.is_orn].str.replace("ORN_", "", regex=False).to_numpy(dtype=object)
    return side, glom, m.is_pn.to_numpy(bool)


def fingerprint(side, glom, pn_mask, e, label):
    """Per ORN: share of its PN synapses onto PNs on its own labelled side."""
    orn = pd.notna(glom)
    x = e[orn[e.pre.to_numpy()] & pn_mask[e.post.to_numpy()]]
    ps, os_ = side[x.post.to_numpy()], side[x.pre.to_numpy()]
    known = np.isin(ps, ["left", "right"]) & np.isin(os_, ["left", "right"])
    same = (ps == os_) & known
    tot = int(x.syn_count.to_numpy()[known].sum())
    s_same = int(x.syn_count.to_numpy()[same].sum())
    d = pd.DataFrame({"orn": x.pre.to_numpy()[known], "same": (x.syn_count.to_numpy() * same)[known],
                      "tot": x.syn_count.to_numpy()[known]}).groupby("orn").sum()
    share = d.same / d.tot
    return dict(dataset=label, orns_with_pn_synapses=len(d), median_same_side_share=round(float(share.median()), 3),
                orns_share_above_half=int((share > 0.5).sum()), pooled_same_over_other=round(s_same / (tot - s_same), 3))


def main():
    summ, checks = [], []
    # ---------------- maleCNS: both lobes -----------------
    m = meta("malecns")
    e = to_index(m, extract("malecns", m))
    for src in ("nerve", "side"):
        side, glom, pn_mask = arrays(m, src)
        checks.append(fingerprint(side, glom, pn_mask, e, f"maleCNS ORN side from {src}"))
        pn, gm, _ = orn_pn_tables(side, glom, pn_mask, e, m.nid.to_numpy(),
                                  m.cell_type.astype("string").to_numpy(), label=f"maleCNS ({src})")
        gm.to_csv(RES / f"malecns_{src}_glomerulus_map.csv", index=False)
        s = summary(gm, f"maleCNS, ORN side from {src}")
        s["uniglomerular_pns"] = len(pn)
        summ.append(s)
    # ---------------- hemibrain: right lobe only ----------
    h = meta("hemibrain")
    eh = to_index(h, extract("hemibrain", h))
    side_n, glom, pn_mask = arrays(h, "nerve")
    checks.append(fingerprint(side_n, glom, pn_mask, eh, "hemibrain ORN side from nerve column (right PNs only)"))
    # The harmonised hemibrain `nerve` is uniform within each ORN type (filled per type), so
    # use the antenna suffix of the neuPrint instance name (ORN_DA1_L / ORN_DA1_R; Schlegel et
    # al. 2021) where it exists; ORNs without a suffix get side "na" (not counted as either).
    inst = h.instance.astype("string").fillna("")
    suf = np.where(inst.str.endswith("_L"), "left", np.where(inst.str.endswith("_R"), "right", "na"))
    side = np.where(h.is_orn, suf, h.side_col).astype(object)
    checks.append(fingerprint(side, glom, pn_mask, eh, "hemibrain ORN side from instance suffix (right PNs only)"))
    # PN glomerulus assignment uses ALL ORNs (suffix or not), as elsewhere
    pn, gm, ee = orn_pn_tables(side, glom, pn_mask, eh, h.nid.to_numpy(),
                               h.cell_type.astype("string").to_numpy(), label="hemibrain")
    rpn = pn[pn.pn_side == "right"]
    upn_glom = rpn.set_index("pn_root_id").glomerulus
    x = ee.assign(pn_glom=pd.Series(h.nid.to_numpy()[ee.post.to_numpy()], index=ee.index).map(upn_glom))
    x = x[x.glom == x.pn_glom]
    rows = []
    for g, sub in x.groupby("glom"):
        orns = h[(glom == g)]
        n_r = int((suf[orns.index] == "right").sum())
        n_l = int((suf[orns.index] == "left").sum())
        n_u = int((suf[orns.index] == "na").sum())
        ipsi = int(sub[sub.oside == "right"].syn_count.sum())
        contra = int(sub[sub.oside == "left"].syn_count.sum())
        unk = int(sub[sub.oside == "na"].syn_count.sum())
        rows.append(dict(glomerulus=g, n_right_pns=int((rpn.glomerulus == g).sum()), orn_R=n_r, orn_L=n_l,
                         orn_unsuffixed=n_u, from_ipsi_R_orns=ipsi, from_contra_L_orns=contra,
                         from_unsuffixed_orns=unk,
                         ipsi_over_contra=ipsi / contra if contra else np.nan,
                         per_orn_ipsi_over_contra=(ipsi / n_r) / (contra / n_l) if (n_r and n_l and contra) else np.nan,
                         total_input_right_pns=ipsi + contra + unk))
    hb = pd.DataFrame(rows)
    hb.to_csv(RES / "hemibrain_right_al.csv", index=False)
    both = hb[(hb.orn_R > 0) & (hb.orn_L > 0) & (hb.from_contra_L_orns > 0)]
    full = both[both.orn_unsuffixed == 0]
    summ.append(dict(dataset="hemibrain (right lobe only; ORN side from instance suffix)",
                     glomeruli_with_PNs_both_sides=0,
                     glomeruli_right=len(hb), glomeruli_with_L_and_R_ORNs=len(both),
                     same_side_stronger=int((both.ipsi_over_contra > 1).sum()),
                     median_same_over_other=round(float(both.ipsi_over_contra.median()), 3),
                     pooled_same_over_other=round(both.from_ipsi_R_orns.sum() / both.from_contra_L_orns.sum(), 3),
                     median_per_orn_same_over_other=round(float(both.per_orn_ipsi_over_contra.median()), 3),
                     glomeruli_fully_suffixed=len(full),
                     pooled_same_over_other_fully_suffixed=round(full.from_ipsi_R_orns.sum() / max(full.from_contra_L_orns.sum(), 1), 3),
                     uniglomerular_pns=len(rpn)))
    pd.DataFrame(summ).to_csv(RES / "other_flies_summary.csv", index=False)
    pd.DataFrame(checks).to_csv(RES / "other_flies_label_checks.csv", index=False)
    print(pd.DataFrame(checks).to_string(index=False))
    print(pd.DataFrame(summ).T.to_string())
    for g in ("DM1", "DA1"):
        r = hb[hb.glomerulus == g]
        print(g, "hemibrain right PNs:", r.iloc[0].to_dict() if len(r) else "absent")


if __name__ == "__main__":
    main()

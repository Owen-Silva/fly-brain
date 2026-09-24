"""Step 5: why is BANC's same-side advantage (about 2.4x) so much bigger than FlyWire's (1.25x)?

Each smell receptor neuron (ORN) enters the brain on its own side, makes synapses in that
side's antennal lobe, then crosses the midline and makes synapses in the other lobe. If
BANC's ORNs were cut (antennal-nerve damage, or unfinished proofreading of the crossing
branch), many ORNs would have NO synapses at all onto the other side's PNs of their
glomerulus. If the far branch is present but simply smaller, almost every ORN has some.

Per ORN (FlyWire 783 vs BANC v888): synapses onto the uniglomerular PNs of its own
glomerulus on its own side vs the other side (the same PNs used in the main tables).
Output: results/orn_branch_check.csv
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
sys.path.insert(0, str(HERE))
from common import orn_pn_tables, summary  # noqa: E402
import a0_check_port_flywire as a0  # noqa: E402
import a2_banc_tables as a2  # noqa: E402


def complete_only(side, glom, pn_mask, e, rid, ptype, label):
    """Mirror test using only ORNs that have synapses on BOTH sides' PNs of their glomerulus
    (i.e. whose crossing branch is present in the reconstruction)."""
    pn, gm, ee = orn_pn_tables(side, glom, pn_mask, e, rid, ptype, label=label)
    pos = pd.Series(np.arange(len(rid)), index=rid)
    upn = pn.assign(pos=pos.reindex(pn.pn_root_id.to_numpy()).to_numpy()).set_index("pos").glomerulus
    x = ee[ee.post.isin(upn.index)]
    x = x[(x.post.map(upn) == x.glom) & x.oside.isin(["left", "right"])]
    d = x.assign(same=np.where(x.oside == x.pside, x.syn_count, 0),
                 other=np.where(x.oside != x.pside, x.syn_count, 0)).groupby("pre")[["same", "other"]].sum()
    both = d.index[(d.same > 0) & (d.other > 0)].to_numpy()
    g2 = np.full(len(glom), None, dtype=object)
    g2[both] = np.asarray(glom, dtype=object)[both]
    _, gm2, _ = orn_pn_tables(side, g2, pn_mask, e, rid, ptype, label=label + " (ORNs with both branches)")
    s = summary(gm2, label + ", ORNs with both branches only")
    gm2.to_csv(RES / f"complete_orns_{label.replace(' ', '_')}_glomerulus_map.csv", index=False)
    return s


def per_orn(side, glom, pn_mask, e, rid, ptype, label, extra=None):
    pn, gm, ee = orn_pn_tables(side, glom, pn_mask, e, rid, ptype, label=label)
    keep = set(gm.glomerulus)  # glomeruli with PNs on both sides
    pos = pd.Series(np.arange(len(rid)), index=rid)
    upn = pn.assign(pos=pos.reindex(pn.pn_root_id.to_numpy()).to_numpy()).set_index("pos").glomerulus
    x = ee[ee.post.isin(upn.index)].copy()
    x = x[(x.post.map(upn) == x.glom) & x.glom.isin(keep) & x.oside.isin(["left", "right"])]
    x["same"] = np.where(x.oside == x.pside, x.syn_count, 0)
    x["other"] = np.where(x.oside != x.pside, x.syn_count, 0)
    d = x.groupby("pre")[["same", "other"]].sum()
    d["tot"] = d.same + d.other
    out = dict(dataset=label, orns=len(d), median_uPN_synapses_per_orn=float(d.tot.median()),
               pct_orns_no_other_side=round(100 * float((d.other == 0).mean()), 1),
               pct_orns_no_same_side=round(100 * float((d.same == 0).mean()), 1),
               median_other_side_share=round(float((d.other / d.tot).median()), 3),
               pooled_same_over_other=round(d.same.sum() / d.other.sum(), 3))
    b = d[(d.same > 0) & (d.other > 0)]
    out.update(orns_with_both=len(b), pooled_same_over_other_orns_with_both=round(b.same.sum() / b.other.sum(), 3),
               median_other_side_share_orns_with_both=round(float((b.other / b.tot).median()), 3))
    big = d[d.tot >= d.tot.median()]
    out.update(pooled_same_over_other_top_half_orns=round(big.same.sum() / big.other.sum(), 3),
               pct_no_other_side_top_half_orns=round(100 * float((big.other == 0).mean()), 1))
    if extra is not None:  # BANC: by proofreading tier
        for nm, msk in extra.items():
            s = d[d.index.isin(np.flatnonzero(msk))]
            out[f"pooled_same_over_other_{nm}"] = round(s.same.sum() / max(s.other.sum(), 1), 3)
            out[f"pct_no_other_side_{nm}"] = round(100 * float((s.other == 0).mean()), 1) if len(s) else np.nan
            out[f"orns_{nm}"] = len(s)
    return out


def main():
    rows, comp = [], []
    side, glom, pn_mask, e, rid, ptype, _ = a0.flywire_inputs("783")
    rows.append(per_orn(side, glom, pn_mask, e, rid, ptype, "FlyWire 783"))
    comp.append(complete_only(side, glom, pn_mask, e, rid, ptype, "FlyWire 783"))
    m = a2.load()
    side, glom, pn_mask, _ = a2.labels(m, "lenient", "nerve")
    e, _ = a2.edges(m, "v2")
    tiers = {"strict": m.proofread.to_numpy(bool), "rough_only": m.roughly_proofread.to_numpy(bool)}
    rid, ptype = m.banc_888_id.to_numpy(), m.cell_type.astype("string").to_numpy()
    rows.append(per_orn(side, glom, pn_mask, e, rid, ptype, "BANC v2", extra=tiers))
    comp.append(complete_only(side, glom, pn_mask, e, rid, ptype, "BANC v2"))
    e3, _ = a2.edges(m, "v3")
    rows.append(per_orn(side, glom, pn_mask, e3, rid, ptype, "BANC v3"))
    import a3_other_flies as a3
    mm = a3.meta("malecns")
    em = a3.to_index(mm, pd.read_parquet(a3.DER / "malecns_edges.parquet"))
    side, glom, pn_mask = a3.arrays(mm, "side")
    rid, ptype = mm.nid.to_numpy(), mm.cell_type.astype("string").to_numpy()
    rows.append(per_orn(side, glom, pn_mask, em, rid, ptype, "maleCNS"))
    comp.append(complete_only(side, glom, pn_mask, em, rid, ptype, "maleCNS"))
    df = pd.DataFrame(rows)
    df.to_csv(RES / "orn_branch_check.csv", index=False)
    print(df.T.to_string())
    dc = pd.DataFrame(comp)
    dc.to_csv(RES / "complete_orns_summary.csv", index=False)
    print(dc.set_index("dataset").T.to_string())


if __name__ == "__main__":
    main()

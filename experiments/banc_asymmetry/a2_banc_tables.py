"""Step 2: FlyWire's Phase 6 left/right measures, recomputed for BANC (a second fly).

Same code as FlyWire (common.orn_pn_tables, proven identical by a0). Label mapping:
  FlyWire                         BANC (v888 meta)
  cell_class "olfactory" + type   cell_class "olfactory_receptor_neuron" + cell_type
    "ORN_<glomerulus>"              "ORN_<glomerulus>"
  cell_class "ALPN"               cell_class "antennal_lobe_projection_neuron"
  ORN side = side of entry nerve  ORN side = side of `nerve` (left/right antennal or
                                    maxillary-labial nerve); `side` column if no nerve
  PN side = soma side             PN side = `side` (from the soma anchor)
  proofread neurons only          proofread OR roughly_proofread (the BANC team's
                                    "lenient" rule); strict-only as a variant
  all connections (min 1 syn)     all connections (min 1 syn), v2 synapses (paper's)

Also runs section-2-style label checks and the variants listed in VARIANTS.
Outputs in results/: banc_<variant>_glomerulus_map.csv, banc_main_pn_table.csv,
banc_summary.csv, banc_label_checks.csv, banc_dm1_da1.csv
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DER = ROOT / "data/banc/derived"
RES = HERE / "results"
RES.mkdir(exist_ok=True)
sys.path.insert(0, str(HERE))
from common import orn_pn_tables, summary  # noqa: E402

VARIANTS = {
    # name: (edge version, inclusion rule, ORN side source)
    "main": ("v2", "lenient", "nerve"),
    "strict_proofread": ("v2", "strict", "nerve"),
    "all_segments": ("v2", "all", "nerve"),
    "orn_side_from_side_column": ("v2", "lenient", "side"),
    "v3_synapses": ("v3", "lenient", "nerve"),
}


def load():
    m = pd.read_parquet(DER / "banc_neurons.parquet")
    m = m.reset_index(drop=True)
    return m


def labels(m, inclusion, orn_side_src):
    cc = m.cell_class.astype("string").fillna("")
    ct = m.cell_type.astype("string").fillna("")
    if inclusion == "strict":
        ok = m.proofread.to_numpy(bool)
    elif inclusion == "lenient":
        ok = (m.proofread | m.roughly_proofread).to_numpy(bool)
    else:
        ok = np.ones(len(m), bool)
    is_orn = (cc.eq("olfactory_receptor_neuron") & ct.str.startswith("ORN_")).to_numpy(bool) & ok
    glom = np.full(len(m), None, dtype=object)
    glom[is_orn] = ct[is_orn].str.replace("ORN_", "", regex=False).to_numpy(dtype=object)
    pn_mask = cc.eq("antennal_lobe_projection_neuron").to_numpy(bool) & ok
    side = m.side.astype("string").fillna("na").to_numpy(dtype=object)
    nerve = m.nerve.astype("string").fillna("")
    nerve_side = np.where(nerve.str.startswith("left_"), "left",
                          np.where(nerve.str.startswith("right_"), "right", "na")).astype(object)
    if orn_side_src == "nerve":
        s = np.where(nerve_side != "na", nerve_side, side).astype(object)
        side = np.where(is_orn, s, side).astype(object)
    return side, glom, pn_mask, nerve_side


def edges(m, version):
    e = pd.read_parquet(DER / f"banc_{version}_edges.parquet")
    idx = pd.Series(np.arange(len(m)), index=m.banc_888_id.to_numpy())
    pre = idx.reindex(e.pre.to_numpy()).to_numpy()
    post = idx.reindex(e.post.to_numpy()).to_numpy()
    ok = ~(np.isnan(pre) | np.isnan(post))
    return pd.DataFrame({"pre": pre[ok].astype(np.int64), "post": post[ok].astype(np.int64),
                         "syn_count": e["count"].to_numpy()[ok].astype(np.int64)}), int((~ok).sum())


def midline(m):
    s = m[m.side.isin(["left", "right"])].groupby("side").soma_x_um.median()
    return float((s["left"] + s["right"]) / 2), bool(s["left"] < s["right"])


def label_checks(m, side, glom, pn_mask, nerve_side, e, mid, left_low):
    rows = []
    orn = pd.notna(glom)
    x_root = m.root_x_um.to_numpy()
    x_soma = m.soma_x_um.to_numpy()

    def on_left(x):
        return x < mid if left_low else x > mid

    for grp, mask, xs, what in (("ORN", orn, x_root, "root point"), ("ALPN", pn_mask, x_soma, "soma")):
        for sd in ("left", "right"):
            ii = np.flatnonzero(mask & (side == sd))
            x = xs[ii]
            okp = ~np.isnan(x)
            agree = on_left(x[okp]) if sd == "left" else ~on_left(x[okp])
            rows.append(dict(check=f"{grp} {what} on the labelled side", label=sd, n=len(ii),
                             agree=int(agree.sum()), of=int(okp.sum())))
    # ORN: nerve side vs side column; root region (AL_L / AL_R) vs label
    sc = m.side.astype("string").fillna("na").to_numpy(dtype=object)
    for sd in ("left", "right"):
        ii = orn & (side == sd)
        rows.append(dict(check="ORN: side column agrees with nerve side", label=sd, n=int(ii.sum()),
                         agree=int((sc[ii] == sd).sum()), of=int((sc[ii] != "na").sum())))
        rr = m.root_region.astype("string").fillna("").to_numpy(dtype=object)[ii]
        al = np.array([r.endswith("AL_L") or r.endswith("AL_R") for r in rr])
        suffix = "AL_L" if sd == "left" else "AL_R"
        rows.append(dict(check="ORN: root point in the antennal lobe of the labelled side (AL_L/AL_R)",
                         label=sd, n=int(ii.sum()), agree=int(sum(r.endswith(suffix) for r in rr)),
                         of=int(al.sum())))
        osi = m.output_side_index.to_numpy(float)[ii]
        okk = ~np.isnan(osi)
        agree = (osi[okk] < 0) if sd == "left" else (osi[okk] > 0)
        rows.append(dict(check="ORN: most output synapses on the labelled side (output_side_index)",
                         label=sd, n=int(ii.sum()), agree=int(agree.sum()), of=int(okk.sum())))
    rows.append(dict(check="ORN side came from nerve (not side column)", label="all",
                     n=int(orn.sum()), agree=int((orn & (nerve_side != "na")).sum()), of=int(orn.sum())))
    # ORN fingerprint: share of each ORN's PN synapses going to same-side PNs
    x = e[orn[e.pre.to_numpy()] & pn_mask[e.post.to_numpy()]]
    same = side[x.pre.to_numpy()] == side[x.post.to_numpy()]
    known = np.isin(side[x.post.to_numpy()], ["left", "right"]) & np.isin(side[x.pre.to_numpy()], ["left", "right"])
    d = pd.DataFrame({"orn": x.pre.to_numpy()[known], "same": x.syn_count.to_numpy()[known] * same[known],
                      "tot": x.syn_count.to_numpy()[known]}).groupby("orn").sum()
    share = d.same / d.tot
    rows.append(dict(check="ORN fingerprint: median same-side share of PN synapses", label="all",
                     n=len(d), agree=round(float(share.median()), 3), of=np.nan))
    rows.append(dict(check="ORN fingerprint: ORNs with same-side share above 0.5", label="all",
                     n=len(d), agree=int((share > 0.5).sum()), of=len(d)))
    rows.append(dict(check="ORNs sending >90% of their PN synapses to the side opposite their label",
                     label="all", n=len(d), agree=int((share < 0.1).sum()), of=len(d)))
    return pd.DataFrame(rows), share


def whole_lobe(m, side, glom, pn_mask, e):
    orn = pd.notna(glom)
    cc = m.cell_class.astype("string").fillna("")
    ln_mask = cc.eq("antennal_lobe_local_neuron").to_numpy(bool)
    rows = []
    for tgt, msk in (("ALPN", pn_mask), ("ALLN", ln_mask)):
        x = e[orn[e.pre.to_numpy()] & msk[e.post.to_numpy()]]
        for a in ("left", "right"):
            for b in ("left", "right"):
                s = int(x[(side[x.pre.to_numpy()] == a) & (side[x.post.to_numpy()] == b)].syn_count.sum())
                rows.append(dict(target=tgt, orn_side=a, target_side=b, synapses=s))
    for nm, msk in (("ORN", orn), ("ALPN", pn_mask), ("ALLN", ln_mask)):
        for sd in ("left", "right"):
            rows.append(dict(target=f"count_{nm}", orn_side="", target_side=sd,
                             synapses=int((msk & (side == sd)).sum())))
    # all input synapses onto left vs right PNs (any sender in the table)
    x = e[pn_mask[e.post.to_numpy()]]
    for sd in ("left", "right"):
        rows.append(dict(target="ALPN_all_inputs", orn_side="any", target_side=sd,
                         synapses=int(x[side[x.post.to_numpy()] == sd].syn_count.sum())))
    return pd.DataFrame(rows)


def dm1_da1(gm, label):
    out = []
    for g in ("DM1", "DA1"):
        r = gm[gm.glomerulus == g]
        if len(r) == 0:
            out.append(dict(dataset=label, glomerulus=g, note="no PNs on both sides"))
            continue
        r = r.iloc[0]
        out.append(dict(dataset=label, glomerulus=g, orn_left=r.orn_left, orn_right=r.orn_right,
                        pn_left=r.pn_left, pn_right=r.pn_right,
                        Lorn_to_Lpn=r.Lorn_to_Lpn, Lorn_to_Rpn=r.Lorn_to_Rpn,
                        Rorn_to_Lpn=r.Rorn_to_Lpn, Rorn_to_Rpn=r.Rorn_to_Rpn,
                        left_pn_total=r.left_pn_total, right_pn_total=r.right_pn_total,
                        left_over_right=round(r.left_pn_total / r.right_pn_total, 3),
                        same_over_other=round(r.ipsi_over_contra, 3), mirror=bool(r.mirror_ok_total)))
    return out


def main():
    m = load()
    mid, left_low = midline(m)
    print(f"BANC midline x = {mid:.1f} um (from median soma x of left vs right neurons); "
          f"left at smaller x: {left_low}")
    summ, dd = [], []
    for name, (ver, inc, oss) in VARIANTS.items():
        side, glom, pn_mask, nerve_side = labels(m, inc, oss)
        e, dropped = edges(m, ver)
        pn, gm, _ = orn_pn_tables(side, glom, pn_mask, e, m.banc_888_id.to_numpy(),
                                  m.cell_type.astype("string").to_numpy(), label=f"BANC {name}",
                                  soma_offset_um=(m.soma_x_um.to_numpy() - mid) * (1 if left_low else -1))
        gm.to_csv(RES / f"banc_{name}_glomerulus_map.csv", index=False)
        s = summary(gm, f"BANC {name}")
        s.update(edges_version=ver, inclusion=inc, orn_side_source=oss,
                 orns_typed=int(pd.notna(glom).sum()), pns=int(pn_mask.sum()),
                 uniglomerular_pns=len(pn))
        summ.append(s)
        dd += dm1_da1(gm, f"BANC {name}")
        if name == "main":
            pn.to_csv(RES / "banc_main_pn_table.csv", index=False)
            ck, share = label_checks(m, side, glom, pn_mask, nerve_side, e, mid, left_low)
            ck.to_csv(RES / "banc_label_checks.csv", index=False)
            wl = whole_lobe(m, side, glom, pn_mask, e)
            wl.to_csv(RES / "banc_whole_lobe.csv", index=False)
            print(ck.to_string(index=False))
            print(wl.to_string(index=False))
        print(f"{name}: {s}")
    pd.DataFrame(summ).to_csv(RES / "banc_summary.csv", index=False)
    pd.DataFrame(dd).to_csv(RES / "banc_dm1_da1.csv", index=False)
    print(pd.DataFrame(dd).to_string(index=False))


if __name__ == "__main__":
    main()

"""Shared ORN -> PN left/right measures, usable on any connectome.

This is a line-by-line port of the ORN -> PN part of
experiments/phase6/steering/s1_anatomy.py::glomerulus_tables (the code behind
docs/phase6-steering.md section 3), made dataset-neutral so FlyWire and BANC
(and other flies) go through exactly the same counting.
a0_check_port_flywire.py proves the port reproduces the saved FlyWire tables
(glomerulus_map_630.csv, glomerulus_map_783.csv, pn_ipsi_contra_*.csv) exactly.

Inputs (all indexed by a neuron position 0..N-1):
  side    : numpy array of str, "left" / "right" / "na"
  glom    : numpy object array, glomerulus name for smell receptor neurons (ORNs)
            ("DM1" for type "ORN_DM1"), None/NaN for every other neuron
  pn_mask : numpy bool array, True for antennal-lobe projection neurons (PNs)
  edges   : DataFrame with integer columns pre, post (neuron positions), syn_count
  root_id, pn_type : per-neuron arrays, only used to label the per-PN table

Definitions (same as FlyWire's run):
  - a PN's glomerulus is the ORN type giving it the most ORN synapses; it counts as
    uniglomerular if that type gives >= 50% of its ORN synapses and >= 20 synapses.
  - per glomerulus, ORN -> PN synapses are summed over its uniglomerular PNs for the
    four side combinations (left/right ORN x left/right PN); glomeruli need a PN on
    each side.
  - "mirrors at the first synapse" (mirror_ok_total): a left-only smell gives the left
    PNs more synapses than the right PNs AND a right-only smell gives the right PNs
    more than the left PNs.
"""
import numpy as np
import pandas as pd


def orn_pn_tables(side, glom, pn_mask, edges, root_id, pn_type, label="", soma_offset_um=None):
    side = np.asarray(side, dtype=object)
    glom = np.asarray(glom, dtype=object)
    pn_mask = np.asarray(pn_mask, dtype=bool)
    orn_idx = np.flatnonzero(pd.notna(glom))
    e = edges
    ee = e[np.isin(e.pre.to_numpy(), orn_idx) & pn_mask[e.post.to_numpy()]]
    ee = ee.assign(glom=glom[ee.pre.to_numpy()], oside=side[ee.pre.to_numpy()],
                   pside=side[ee.post.to_numpy()])
    # each PN's main glomerulus by ORN input
    per_pn_g = ee.groupby(["post", "glom"]).syn_count.sum().reset_index()
    tot = per_pn_g.groupby("post").syn_count.sum()
    best = per_pn_g.sort_values("syn_count", ascending=False).drop_duplicates("post").set_index("post")
    best["purity"] = best.syn_count / tot.reindex(best.index)
    best["orn_total"] = tot.reindex(best.index)
    upn = best[(best.purity >= 0.5) & (best.syn_count >= 20)]

    pn_rows = []
    for p, r in upn.iterrows():
        g = r.glom
        sub = ee[(ee.post == p) & (ee.glom == g)]
        ps = side[p]
        ipsi = int(sub[sub.oside == ps].syn_count.sum())
        contra = int(sub[(sub.oside != ps) & (sub.oside != "na")].syn_count.sum())
        pn_rows.append(dict(snapshot=label, glomerulus=g, pn_root_id=int(root_id[p]),
                            pn_type=str(pn_type[p]), pn_side=ps,
                            soma_offset_um=(float(soma_offset_um[p]) if soma_offset_um is not None else np.nan),
                            from_ipsi_orns=ipsi, from_contra_orns=contra,
                            ipsi_over_contra=ipsi / contra if contra else np.nan,
                            purity=round(float(r.purity), 3)))
    pn = pd.DataFrame(pn_rows)

    g_rows = []
    for g, sub in ee[ee.post.isin(upn.index)].groupby("glom"):
        sub = sub[sub.post.map(upn.glom) == g]
        S = {(a, b): int(sub[(sub.oside == a) & (sub.pside == b)].syn_count.sum())
             for a in ("left", "right") for b in ("left", "right")}
        n_orn = pd.Series(side[orn_idx][glom[orn_idx] == g]).value_counts()
        pns = pn[pn.glomerulus == g]
        npl, npr = int((pns.pn_side == "left").sum()), int((pns.pn_side == "right").sum())
        if npl == 0 or npr == 0:
            continue
        in_l = S["left", "left"] + S["right", "left"]
        in_r = S["left", "right"] + S["right", "right"]
        ipsi = S["left", "left"] + S["right", "right"]
        contra = S["left", "right"] + S["right", "left"]
        g_rows.append(dict(
            snapshot=label, glomerulus=g, orn_left=int(n_orn.get("left", 0)),
            orn_right=int(n_orn.get("right", 0)), pn_left=npl, pn_right=npr,
            Lorn_to_Lpn=S["left", "left"], Lorn_to_Rpn=S["left", "right"],
            Rorn_to_Lpn=S["right", "left"], Rorn_to_Rpn=S["right", "right"],
            ipsi_over_contra=ipsi / contra if contra else np.nan,
            left_pn_total=in_l, right_pn_total=in_r,
            left_right_asym=(in_l - in_r) / (in_l + in_r),
            leftstim_Lpn_minus_Rpn=S["left", "left"] - S["left", "right"],
            rightstim_Rpn_minus_Lpn=S["right", "right"] - S["right", "left"],
            leftstim_perPN_diff=S["left", "left"] / npl - S["left", "right"] / npr,
            rightstim_perPN_diff=S["right", "right"] / npr - S["right", "left"] / npl,
        ))
    gm = pd.DataFrame(g_rows)
    if gm.empty:  # e.g. the hemibrain: no glomerulus has PNs on both sides
        return pn, gm, ee
    gm["mirror_ok_total"] = (gm.leftstim_Lpn_minus_Rpn > 0) & (gm.rightstim_Rpn_minus_Lpn > 0)
    gm["mirror_ok_perPN"] = (gm.leftstim_perPN_diff > 0) & (gm.rightstim_perPN_diff > 0)
    return pn, gm, ee


def mirror_with_boost(gm, k):
    """Mirror test if every same-side ORN -> PN synapse counted k times (Gaudry et al. 2013)."""
    left_ok = k * gm.Lorn_to_Lpn - gm.Lorn_to_Rpn > 0
    right_ok = k * gm.Rorn_to_Rpn - gm.Rorn_to_Lpn > 0
    return left_ok & right_ok


def summary(gm, label):
    """The numbers in docs/phase6-steering.md section 3's table, plus a few extras."""
    n = len(gm)
    fail = gm[~gm.mirror_ok_total]
    ok = gm[gm.mirror_ok_total]
    lr_total_ipsi = int((gm.Lorn_to_Lpn + gm.Rorn_to_Rpn).sum())
    lr_total_contra = int((gm.Lorn_to_Rpn + gm.Rorn_to_Lpn).sum())
    out = dict(
        dataset=label,
        glomeruli_with_PNs_both_sides=n,
        same_side_stronger=int((gm.ipsi_over_contra > 1).sum()),
        median_same_over_other=round(float(gm.ipsi_over_contra.median()), 3),
        pooled_same_over_other=round(lr_total_ipsi / lr_total_contra, 3),
        mirror_at_first_synapse=int(gm.mirror_ok_total.sum()),
        fail_mirror=int((~gm.mirror_ok_total).sum()),
        fail_left_bigger=int((fail.left_right_asym > 0).sum()),
        fail_right_bigger=int((fail.left_right_asym < 0).sum()),
        left_pns_get_more_total=int((gm.left_pn_total > gm.right_pn_total).sum()),
        median_abs_asym_fail_pct=round(float(fail.left_right_asym.abs().median() * 100), 1) if len(fail) else np.nan,
        median_abs_asym_ok_pct=round(float(ok.left_right_asym.abs().median() * 100), 1) if len(ok) else np.nan,
        median_abs_asym_all_pct=round(float(gm.left_right_asym.abs().median() * 100), 1),
        median_asym_signed_pct=round(float(gm.left_right_asym.median() * 100), 1),
        mirror_perPN=int(gm.mirror_ok_perPN.sum()),
    )
    for k in (1.2, 1.4, 1.6, 2.0):
        out[f"mirror_if_same_side_x{k}"] = int(mirror_with_boost(gm, k).sum())
    return out

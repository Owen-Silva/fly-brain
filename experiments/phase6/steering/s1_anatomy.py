"""Phase 6 steering check, steps 1 and 2: side labels and the ORN -> PN wiring map.

Plain English
-------------
The model says "a smell on the LEFT antenna and a smell on the RIGHT antenna
both make the LEFT steering neuron fire". Before believing that, this script
checks the wiring it comes from, with no simulation at all:

1. Are the left/right labels right? For each smell receptor neuron (ORN), each
   projection neuron (PN) and the steering neurons DNa02 / DNa01, we compare the
   label with where the neuron actually is (cell body or "anchor" position; the
   brain's midline is where the two sides meet). In snapshot 783 we also have,
   for every connection, the brain region ("neuropil") its synapses sit in, so
   we can check that a "left" PN really collects its smell input in the LEFT
   antennal lobe, and see how each ORN splits its output between the two lobes.
2. For every glomerulus (smell channel), how many synapses each PN gets from
   same-side ("ipsilateral") and other-side ("contralateral") ORNs, and whether
   a left-only smell gives the left PNs more input than the right PNs (and the
   mirror image for a right-only smell). Real flies: ipsilateral input is
   stronger (Tobin et al. 2017; Taisz et al. 2023 measured 5,184 vs 3,580
   synapses for DA1 in FlyWire).

Outputs (results/): side_checks.csv, orn_side_detail_783.csv,
pn_ipsi_contra_{630,783}.csv, glomerulus_map_{630,783}.csv, al_totals.csv.
"""
from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pyarrow as pa

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = HERE / "results"
RES.mkdir(exist_ok=True)
sys.path.insert(0, str(ROOT))

# Steering neurons (docs/phase9-body-research.md; experiments/phase5/unexplored/steering_ids.py)
DN_630 = {"DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
          "DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551}
DN_783 = {"DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
          "DNa01_L": 720575940627787609, "DNa01_R": 720575940644438551}


def load(snap):
    n = pd.read_parquet(ROOT / f"data/cache/connectome_{snap}_neurons.parquet")
    e = pd.read_parquet(ROOT / f"data/cache/connectome_{snap}_edges.parquet",
                        columns=["pre", "post", "syn_count"])
    return n, e


def orn_type(n, snap):
    col = "hemibrain_type" if snap == "630" else "cell_type"
    t = n[col].astype("string")
    is_orn = ((n.cell_class == "olfactory").fillna(False) & t.str.startswith("ORN_").fillna(False)).astype(bool)
    return t.where(is_orn)


def midline(n):
    s = n[n.side.isin(["left", "right"])].groupby("side").soma_x_nm.median()
    return float((s["left"] + s["right"]) / 2), s["left"] < s["right"]


def glomerulus_tables(snap):
    n, e = load(snap)
    mid, left_is_low = midline(n)
    assert left_is_low, "expected 'left' somata at smaller x"
    ot = orn_type(n, snap)
    orn_idx = np.flatnonzero(ot.notna().to_numpy())
    pn_mask = (n.cell_class == "ALPN").fillna(False).to_numpy(bool)
    side = n.side.astype("string").fillna("na").to_numpy()
    glom = ot.str.replace("ORN_", "", regex=False).to_numpy()

    # -- position checks ---------------------------------------------------
    rows = []
    x_anchor = n.anchor_x_nm.to_numpy()
    x_soma = n.soma_x_nm.to_numpy()
    for grp, idx, xs, what in [("ORN", orn_idx, x_anchor, "anchor"),
                               ("ALPN", np.flatnonzero(pn_mask), x_soma, "soma")]:
        for sd in ("left", "right"):
            ii = idx[side[idx] == sd]
            x = xs[ii]
            ok = ~np.isnan(x)
            pos_left = x[ok] < mid
            agree = pos_left if sd == "left" else ~pos_left
            rows.append(dict(snapshot=snap, group=grp, label=sd, n=len(ii), n_with_pos=int(ok.sum()),
                             position_used=what, agree_with_label=int(agree.sum()),
                             median_offset_from_midline_um=float(np.median(x[ok] - mid) / 1000)))
    dn = DN_630 if snap == "630" else DN_783
    rid = pd.Index(n.root_id.to_numpy())
    for k, r in dn.items():
        i = rid.get_indexer([r])[0]
        if i < 0:
            rows.append(dict(snapshot=snap, group=k, label="MISSING", n=0))
            continue
        x = x_soma[i]
        rows.append(dict(snapshot=snap, group=k, label=side[i], n=1, n_with_pos=int(~np.isnan(x)),
                         position_used="soma", agree_with_label=int((x < mid) == (side[i] == "left")),
                         median_offset_from_midline_um=float((x - mid) / 1000),
                         type_630=str(n.hemibrain_type.iloc[i]), cell_type=str(n.cell_type.iloc[i])))

    # -- ORN -> PN synapses ------------------------------------------------
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
        pn_rows.append(dict(snapshot=snap, glomerulus=g, pn_root_id=int(n.root_id.iloc[p]),
                            pn_type=str(n.hemibrain_type.iloc[p]), pn_side=ps,
                            soma_offset_um=float((x_soma[p] - mid) / 1000),
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
            snapshot=snap, glomerulus=g, orn_left=int(n_orn.get("left", 0)),
            orn_right=int(n_orn.get("right", 0)), pn_left=npl, pn_right=npr,
            Lorn_to_Lpn=S["left", "left"], Lorn_to_Rpn=S["left", "right"],
            Rorn_to_Lpn=S["right", "left"], Rorn_to_Rpn=S["right", "right"],
            ipsi_over_contra=ipsi / contra if contra else np.nan,
            left_pn_total=in_l, right_pn_total=in_r,
            left_right_asym=(in_l - in_r) / (in_l + in_r),
            # does a one-sided smell give the same-side PNs more input? (totals and per PN)
            leftstim_Lpn_minus_Rpn=S["left", "left"] - S["left", "right"],
            rightstim_Rpn_minus_Lpn=S["right", "right"] - S["right", "left"],
            leftstim_perPN_diff=S["left", "left"] / npl - S["left", "right"] / npr,
            rightstim_perPN_diff=S["right", "right"] / npr - S["right", "left"] / npl,
        ))
    gm = pd.DataFrame(g_rows)
    gm["mirror_ok_total"] = (gm.leftstim_Lpn_minus_Rpn > 0) & (gm.rightstim_Rpn_minus_Lpn > 0)
    gm["mirror_ok_perPN"] = (gm.leftstim_perPN_diff > 0) & (gm.rightstim_perPN_diff > 0)

    # whole-lobe totals (all ORN types, all ALPNs; also ORN -> AL local neurons)
    ln_mask = (n.cell_class == "ALLN").fillna(False).to_numpy(bool)
    tot_rows = []
    for tgt, m in (("ALPN", pn_mask), ("ALLN", ln_mask)):
        x = e[np.isin(e.pre.to_numpy(), orn_idx) & m[e.post.to_numpy()]]
        for a in ("left", "right"):
            for b in ("left", "right"):
                s = int(x[(side[x.pre.to_numpy()] == a) & (side[x.post.to_numpy()] == b)].syn_count.sum())
                tot_rows.append(dict(snapshot=snap, target=tgt, orn_side=a, target_side=b, synapses=s))
    for cls in ("ALPN", "ALLN", "olfactory"):
        m = (n.cell_class == cls).fillna(False)
        for sd in ("left", "right"):
            tot_rows.append(dict(snapshot=snap, target=f"count_{cls}", orn_side="", target_side=sd,
                                 synapses=int((m & (n.side == sd).fillna(False)).sum())))
    # all input synapses to left vs right ALPNs from anything (reconstruction-size check)
    for sd in ("left", "right"):
        m = pn_mask & (side == sd)
        tot_rows.append(dict(snapshot=snap, target="ALPN_all_inputs", orn_side="any", target_side=sd,
                             synapses=int(n.in_synapses.to_numpy()[m].sum())))
    return pd.DataFrame(rows), pn, gm, pd.DataFrame(tot_rows), n, orn_idx, glom, side, mid


def neuropil_check_783(n, orn_idx, glom, side):
    """Snapshot 783 per-connection neuropil: where ORN output and PN/DN input sit."""
    rid = n.root_id.to_numpy()
    orn_ids = set(rid[orn_idx].tolist())
    pn_ids = set(rid[(n.cell_class == "ALPN").fillna(False).to_numpy(bool)].tolist())
    dn_ids = set(DN_783.values())
    reader = pa.ipc.open_file(ROOT / "data/flywire/proofread_connections_783.feather")
    keep = []
    orn_arr = np.array(sorted(orn_ids), dtype=np.int64)
    pn_arr = np.array(sorted(pn_ids | dn_ids), dtype=np.int64)
    for b in range(reader.num_record_batches):
        t = reader.get_batch(b).select(["pre_pt_root_id", "post_pt_root_id", "neuropil", "syn_count"])
        pre = t.column(0).to_numpy()
        post = t.column(1).to_numpy()
        m = np.isin(pre, orn_arr) | np.isin(post, pn_arr)
        if m.any():
            keep.append(t.filter(pa.array(m)).to_pandas())
    c = pd.concat(keep, ignore_index=True)
    c.columns = ["pre", "post", "neuropil", "syn_count"]
    idx = pd.Series(np.arange(len(rid)), index=rid)
    # ORNs: output split between AL_L and AL_R, by label
    o = c[c.pre.isin(orn_ids) & c.neuropil.isin(["AL_L", "AL_R"])]
    per = o.pivot_table(index="pre", columns="neuropil", values="syn_count", aggfunc="sum",
                        fill_value=0)
    per["frac_AL_L"] = per["AL_L"] / (per["AL_L"] + per["AL_R"])
    ii = idx.reindex(per.index).to_numpy()
    per["label"] = side[ii]
    per["glomerulus"] = glom[ii]
    per["anchor_x_um"] = n.anchor_x_nm.to_numpy()[ii] / 1000
    per = per.reset_index().rename(columns={"pre": "root_id"})
    # PNs and DNs: where their inputs sit
    rows = []
    q = c[c.post.isin(pn_ids)]
    pnin = q.assign(al=q.neuropil.where(q.neuropil.isin(["AL_L", "AL_R"]), "other")) \
        .pivot_table(index="post", columns="al", values="syn_count", aggfunc="sum", fill_value=0)
    pnin["label"] = side[idx.reindex(pnin.index).to_numpy()]
    for sd in ("left", "right"):
        s = pnin[pnin.label == sd]
        in_al = s[["AL_L", "AL_R"]].sum(axis=1) > 0
        maj_l = (s.AL_L > s.AL_R)[in_al]
        agree = maj_l if sd == "left" else ~maj_l
        rows.append(dict(snapshot="783", group="ALPN (input neuropil)", label=sd, n=int(in_al.sum()),
                         position_used="majority of AL input synapses in AL_L vs AL_R",
                         agree_with_label=int(agree.sum())))
    for k, r in DN_783.items():
        d = c[c.post == r].groupby("neuropil").syn_count.sum().sort_values(ascending=False)
        top = ", ".join(f"{a}:{int(b)}" for a, b in d.head(4).items())
        lal_l, lal_r = int(d.get("LAL_L", 0)), int(d.get("LAL_R", 0))
        lab = side[idx.get(r)] if r in idx.index else "MISSING"
        rows.append(dict(snapshot="783", group=k + " (input neuropil)", label=lab, n=1,
                         position_used=f"top input neuropils {top}",
                         agree_with_label=int((lal_l > lal_r) == (lab == "left"))))
    return per, pd.DataFrame(rows)


def main():
    all_checks, all_tot = [], []
    for snap in ("630", "783"):
        checks, pn, gm, tot, n, orn_idx, glom, side, mid = glomerulus_tables(snap)
        pn.to_csv(RES / f"pn_ipsi_contra_{snap}.csv", index=False)
        gm.to_csv(RES / f"glomerulus_map_{snap}.csv", index=False)
        all_checks.append(checks)
        all_tot.append(tot)
        print(f"[{snap}] midline x = {mid/1000:.1f} um; glomeruli with PNs on both sides: {len(gm)}")
        print(gm[gm.glomerulus.isin(["DM1", "DM2", "DM4", "VA2", "DA2", "DA1", "DM6", "VM7d"])]
              [["glomerulus", "orn_left", "orn_right", "pn_left", "pn_right", "Lorn_to_Lpn", "Lorn_to_Rpn",
                "Rorn_to_Lpn", "Rorn_to_Rpn", "ipsi_over_contra", "left_right_asym"]].to_string(index=False))
        if snap == "783":
            per, ck = neuropil_check_783(n, orn_idx, glom, side)
            per.to_csv(RES / "orn_side_detail_783.csv", index=False)
            all_checks.append(ck)
    pd.concat(all_checks, ignore_index=True).to_csv(RES / "side_checks.csv", index=False)
    pd.concat(all_tot, ignore_index=True).to_csv(RES / "al_totals.csv", index=False)
    print(pd.concat(all_checks, ignore_index=True).to_string(index=False))


if __name__ == "__main__":
    main()

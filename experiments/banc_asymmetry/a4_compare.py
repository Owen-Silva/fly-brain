"""Step 4: FlyWire vs BANC (plus maleCNS and hemibrain), side by side.

Exact split of each glomerulus's 2x2 ORN -> PN table (LL = left ORNs -> left PNs, etc.):
  same-side factor  w   = sqrt(LL*RR / (LR*RL))   (how much more a PN gets from same-side ORNs)
  PN size factor    rho = sqrt(LL*RL / (LR*RR))   (how much more the LEFT PNs get, from either side)
Then LL/LR = rho*w and RR/RL = w/rho exactly, so a glomerulus mirrors at the first synapse
exactly when w > max(rho, 1/rho): "the size imbalance beats the same-side advantage" means
|log rho| > log w. rho does not depend on how many ORNs each antenna has, so BANC's damaged
antennal nerves (fewer right ORNs) cannot create or hide a PN size imbalance.

Outputs (results/): compare_glomeruli.csv (one row per glomerulus, all flies),
compare_summary.csv, compare_stats.txt, dm1_relative_size.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
RES = HERE / "results"

FLIES = {  # label: file (all made by the same common.orn_pn_tables)
    "FlyWire 783": "flywire_783_glomerulus_map.csv",
    "FlyWire 630": "flywire_630_glomerulus_map.csv",
    "BANC": "banc_main_glomerulus_map.csv",
    "BANC v3 synapses": "banc_v3_synapses_glomerulus_map.csv",
    "maleCNS": "malecns_side_glomerulus_map.csv",
}


def factors(g):
    LL, LR, RL, RR = (g[c].astype(float).clip(lower=0.5) for c in
                      ("Lorn_to_Lpn", "Lorn_to_Rpn", "Rorn_to_Lpn", "Rorn_to_Rpn"))
    g = g.copy()
    g["w_same_side"] = np.sqrt(LL * RR / (LR * RL))
    g["rho_left_size"] = np.sqrt(LL * RL / (LR * RR))
    g["mirror_by_factors"] = g.w_same_side > np.maximum(g.rho_left_size, 1 / g.rho_left_size)
    return g


def spearman(a, b):
    ra, rb = pd.Series(a).rank(), pd.Series(b).rank()
    return float(np.corrcoef(ra, rb)[0, 1])


def perm_p(a, b, n=20000, seed=0):
    rng = np.random.default_rng(seed)
    obs = spearman(a, b)
    rb = pd.Series(b).rank().to_numpy()
    ra = pd.Series(a).rank().to_numpy()
    null = np.array([np.corrcoef(ra, rng.permutation(rb))[0, 1] for _ in range(n)])
    return obs, float((np.abs(null) >= abs(obs)).mean())


def fisher_overlap(set_a, set_b, universe):
    """One-sided hypergeometric p for an overlap at least this big."""
    from math import comb
    N, K, n = len(universe), len(set_a & universe), len(set_b & universe)
    k = len(set_a & set_b & universe)
    p = sum(comb(K, i) * comb(N - K, n - i) for i in range(k, min(K, n) + 1)) / comb(N, n)
    return k, K, n, N, p


def main():
    t = {k: factors(pd.read_csv(RES / f)) for k, f in FLIES.items()}
    for k, g in t.items():
        assert (g.mirror_by_factors == g.mirror_ok_total).all(), f"decomposition check failed for {k}"
    lines = ["decomposition check: mirror_by_factors == mirror_ok_total in every glomerulus of every fly: OK"]

    fw, bc, mc = t["FlyWire 783"], t["BANC"], t["maleCNS"]
    cols = ["glomerulus", "w_same_side", "rho_left_size", "left_right_asym", "ipsi_over_contra",
            "mirror_ok_total", "left_pn_total", "right_pn_total", "pn_left", "pn_right", "orn_left", "orn_right"]
    wide = (fw[cols].add_suffix("_FW").rename(columns={"glomerulus_FW": "glomerulus"})
            .merge(bc[cols].add_suffix("_BANC").rename(columns={"glomerulus_BANC": "glomerulus"}), on="glomerulus", how="outer")
            .merge(mc[cols].add_suffix("_maleCNS").rename(columns={"glomerulus_maleCNS": "glomerulus"}), on="glomerulus", how="outer"))
    hb = pd.read_csv(RES / "hemibrain_right_al.csv")
    wide = wide.merge(hb[["glomerulus", "ipsi_over_contra", "per_orn_ipsi_over_contra", "total_input_right_pns"]]
                      .add_suffix("_hemibrainR").rename(columns={"glomerulus_hemibrainR": "glomerulus"}),
                      on="glomerulus", how="left")
    wide.sort_values("glomerulus").to_csv(RES / "compare_glomeruli.csv", index=False)

    # --- same-side advantage, all flies ---------------------------------------------
    rows = []
    for k, g in t.items():
        fail = g[~g.mirror_ok_total]
        rows.append(dict(fly=k, glomeruli=len(g), mirror=int(g.mirror_ok_total.sum()), fail=len(fail),
                         median_w=round(float(g.w_same_side.median()), 2),
                         median_same_over_other=round(float(g.ipsi_over_contra.median()), 2),
                         median_abs_size_imbalance_pct=round(float((np.abs(np.log(g.rho_left_size))).median() * 100), 1),
                         median_signed_size_left_pct=round(float(np.log(g.rho_left_size).median() * 100), 1),
                         glomeruli_left_bigger=int((g.rho_left_size > 1).sum()),
                         failing=",".join(sorted(fail.glomerulus))))
    hbok = hb[(hb.orn_R > 0) & (hb.orn_L > 0) & (hb.from_contra_L_orns > 0)]
    rows.append(dict(fly="hemibrain (right lobe only)", glomeruli=len(hbok), mirror=np.nan, fail=np.nan,
                     median_w=np.nan, median_same_over_other=round(float(hbok.ipsi_over_contra.median()), 2),
                     median_abs_size_imbalance_pct=np.nan, failing=""))
    summ = pd.DataFrame(rows)
    summ.to_csv(RES / "compare_summary.csv", index=False)
    lines.append(summ.drop(columns=["failing"]).to_string(index=False))
    for r in rows:
        lines.append(f"failing in {r['fly']}: {r['failing']}")

    # --- are the imbalanced glomeruli the same ones? -----------------------------------
    for a, b in (("FlyWire 783", "BANC"), ("FlyWire 783", "maleCNS"), ("BANC", "maleCNS"),
                 ("FlyWire 783", "FlyWire 630"), ("BANC", "BANC v3 synapses")):
        m = t[a][["glomerulus", "rho_left_size", "w_same_side"]].merge(
            t[b][["glomerulus", "rho_left_size", "w_same_side"]], on="glomerulus", suffixes=("_a", "_b"))
        r_rho, p_rho = perm_p(np.log(m.rho_left_size_a), np.log(m.rho_left_size_b))
        r_abs, p_abs = perm_p(np.abs(np.log(m.rho_left_size_a)), np.abs(np.log(m.rho_left_size_b)))
        r_w, p_w = perm_p(np.log(m.w_same_side_a), np.log(m.w_same_side_b))
        lines.append(f"{a} vs {b}: {len(m)} shared glomeruli; Spearman of signed left/right size factor "
                     f"r={r_rho:+.2f} (p={p_rho:.3f}); of unsigned size imbalance r={r_abs:+.2f} (p={p_abs:.3f}); "
                     f"of same-side factor r={r_w:+.2f} (p={p_w:.3f})")
    uni = set(fw.glomerulus) & set(bc.glomerulus) & set(mc.glomerulus)
    ffail = set(fw.glomerulus[~fw.mirror_ok_total])
    mfail = set(mc.glomerulus[~mc.mirror_ok_total])
    k, K, n, N, p = fisher_overlap(ffail, mfail, uni)
    lines.append(f"FlyWire-783 failing vs maleCNS failing (glomeruli in all three flies, N={N}): "
                 f"overlap {k} of {K} and {n}; hypergeometric p(overlap >= {k}) = {p:.3f}")
    # FlyWire's failing glomeruli: how big is their size imbalance in BANC / maleCNS?
    big = wide[wide.glomerulus.isin(ffail)]
    lines.append("FlyWire-783 failing glomeruli, PN size factor rho (left/right) in each fly:")
    for _, r in big.sort_values("glomerulus").iterrows():
        lines.append(f"  {r.glomerulus:6s} FW {r.rho_left_size_FW:5.2f}  BANC {r.rho_left_size_BANC:5.2f}  "
                     f"maleCNS {r.rho_left_size_maleCNS:5.2f}   (w: FW {r.w_same_side_FW:4.2f} BANC {r.w_same_side_BANC:4.2f})")
    # --- counterfactual swaps --------------------------------------------------------
    m = fw.merge(bc, on="glomerulus", suffixes=("_fw", "_bc"))
    fw_with_bc_w = (m.w_same_side_bc > np.maximum(m.rho_left_size_fw, 1 / m.rho_left_size_fw)).sum()
    bc_with_fw_w = (m.w_same_side_fw > np.maximum(m.rho_left_size_bc, 1 / m.rho_left_size_bc)).sum()
    lines.append(f"Swap test on the {len(m)} glomeruli in both: FlyWire's size factors with BANC's same-side "
                 f"factors -> {fw_with_bc_w} mirror; BANC's size factors with FlyWire's same-side factors -> "
                 f"{bc_with_fw_w} mirror (actual: FlyWire {int(m.mirror_ok_total_fw.sum())}, BANC {int(m.mirror_ok_total_bc.sum())})")

    # --- which of FlyWire's DM1s is the unusual one? -----------------------------------
    common = sorted(set(fw.glomerulus) & set(bc.glomerulus) & set(mc.glomerulus) & set(hb.glomerulus))
    als = {"FlyWire L": fw.set_index("glomerulus").left_pn_total, "FlyWire R": fw.set_index("glomerulus").right_pn_total,
           "BANC L": bc.set_index("glomerulus").left_pn_total, "BANC R": bc.set_index("glomerulus").right_pn_total,
           "maleCNS L": mc.set_index("glomerulus").left_pn_total, "maleCNS R": mc.set_index("glomerulus").right_pn_total,
           "hemibrain R": hb.set_index("glomerulus").total_input_right_pns}
    share = pd.DataFrame({k: v.reindex(common) / v.reindex(common).sum() for k, v in als.items()})
    share.to_csv(RES / "glomerulus_share_by_lobe.csv")
    rel = []
    for g in ("DM1", "DA1", "DM2", "DM4", "VA2", "DA2"):
        if g not in share.index:
            continue
        s = share.loc[g] * 100
        others = s.drop(["FlyWire L", "FlyWire R"])
        rel.append(dict(glomerulus=g, **{k: round(v, 2) for k, v in s.items()},
                        others_min=round(others.min(), 2), others_max=round(others.max(), 2),
                        others_median=round(others.median(), 2)))
    rel = pd.DataFrame(rel)
    rel.to_csv(RES / "dm1_relative_size.csv", index=False)
    lines.append(f"Share of each lobe's ORN -> uniglomerular-PN input (percent; {len(common)} glomeruli present in all four flies):")
    lines.append(rel.to_string(index=False))
    # for every FlyWire-failing glomerulus: is the big side unusually big, or the small side unusually small?
    out = []
    for g in sorted(ffail & set(common)):
        s = share.loc[g]
        others = s.drop(["FlyWire L", "FlyWire R"])
        big_side = "FlyWire L" if s["FlyWire L"] > s["FlyWire R"] else "FlyWire R"
        small_side = "FlyWire R" if big_side == "FlyWire L" else "FlyWire L"
        out.append(dict(glomerulus=g, big=big_side[-1], big_vs_others=round(s[big_side] / others.median(), 2),
                        small_vs_others=round(s[small_side] / others.median(), 2),
                        big_above_all_others=bool(s[big_side] > others.max()),
                        small_below_all_others=bool(s[small_side] < others.min())))
    out = pd.DataFrame(out)
    out.to_csv(RES / "flywire_failing_vs_other_flies.csv", index=False)
    lines.append("FlyWire-783 failing glomeruli: FlyWire's bigger and smaller side vs the median of the 5 other lobes")
    lines.append(out.to_string(index=False))
    lines.append(f"  bigger side above every other lobe: {int(out.big_above_all_others.sum())} of {len(out)}; "
                 f"smaller side below every other lobe: {int(out.small_below_all_others.sum())} of {len(out)}")
    # --- fair versions: only ORNs whose crossing branch is present (tables from a5) ----------
    fair = {k: RES / f"complete_orns_{k}_glomerulus_map.csv" for k in ("FlyWire_783", "BANC_v2", "maleCNS")}
    if all(p.exists() for p in fair.values()):
        ff = {k: factors(pd.read_csv(p)) for k, p in fair.items()}
        lines.append("FAIR VERSION (only ORNs with synapses on both sides' PNs of their glomerulus):")
        for a, b in (("FlyWire_783", "BANC_v2"), ("FlyWire_783", "maleCNS"), ("BANC_v2", "maleCNS")):
            m = ff[a][["glomerulus", "rho_left_size", "w_same_side", "mirror_ok_total"]].merge(
                ff[b][["glomerulus", "rho_left_size", "w_same_side", "mirror_ok_total"]], on="glomerulus",
                suffixes=("_a", "_b"))
            r1, p1 = perm_p(np.log(m.rho_left_size_a), np.log(m.rho_left_size_b))
            r2, p2 = perm_p(np.abs(np.log(m.rho_left_size_a)), np.abs(np.log(m.rho_left_size_b)))
            r3, p3 = perm_p(np.log(m.w_same_side_a), np.log(m.w_same_side_b))
            a_with_b = int((m.w_same_side_b > np.maximum(m.rho_left_size_a, 1 / m.rho_left_size_a)).sum())
            b_with_a = int((m.w_same_side_a > np.maximum(m.rho_left_size_b, 1 / m.rho_left_size_b)).sum())
            lines.append(f"  {a} vs {b}: {len(m)} shared; signed size r={r1:+.2f} (p={p1:.3f}); unsigned size "
                         f"r={r2:+.2f} (p={p2:.3f}); same-side r={r3:+.2f} (p={p3:.3f}); swap: {a} sizes with {b} "
                         f"same-side -> {a_with_b} mirror; {b} sizes with {a} same-side -> {b_with_a} mirror "
                         f"(actual {int(m.mirror_ok_total_a.sum())} and {int(m.mirror_ok_total_b.sum())})")
        allb = pd.read_csv(RES / "banc_main_glomerulus_map.csv")
        cb = pd.read_csv(fair["BANC_v2"])
        lines.append(f"  BANC ORNs kept as 'both branches' (summed over glomeruli in each table): left "
                     f"{int(cb.orn_left.sum())} of {int(allb.orn_left.sum())}, right {int(cb.orn_right.sum())} of "
                     f"{int(allb.orn_right.sum())}")
        for g in ("DM1", "DA1", "DA2"):
            a_, c_ = allb[allb.glomerulus == g], cb[cb.glomerulus == g]
            if len(a_) and len(c_):
                lines.append(f"    {g}: left {int(c_.orn_left.iloc[0])} of {int(a_.orn_left.iloc[0])}, right "
                             f"{int(c_.orn_right.iloc[0])} of {int(a_.orn_right.iloc[0])}")
    (RES / "compare_stats.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

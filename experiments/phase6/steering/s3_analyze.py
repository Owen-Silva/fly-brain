"""Phase 6 steering check: tables from the simulations of s2_simulate.py.

Plain English
-------------
For every brain version, smell channel and side we ask four questions:

1. Steering neurons DNa02 / DNa01: does a left smell make the LEFT one fire
   more than the right one, and a right smell the RIGHT one (a "mirror")?
   "turn" = left DN rate minus right DN rate (positive = turn left).
2. Is there ANY left/right pair of descending neurons (same cell type, one or
   more per side) whose turn signal flips sign when the smell switches side,
   in all 3 seeds? That would be a usable steering read-out.
3. A bias-corrected read-out: even if a DN pair always says "turn left", the
   AMOUNT might change with the smell's side. d' says how well one 1-second
   trial tells a left smell from a right one (d' = difference of means divided
   by the pooled trial-to-trial spread; d' of 1 = often wrong, 3 = rarely wrong).
4. Projection neurons (the first relay): does the same-side PN fire more?

Outputs (results/): steering_table.csv, dn_pair_scan.csv, dn_pair_candidates.csv,
pn_lateralization.csv, flip_summary.csv
"""
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = HERE / "results"
SIM = RES / "sim"
VARIANTS = ["al_ln", "al_ln_ipsi", "none"]
GLOMERULI = ["DM1", "DA1", "DM4", "DM2", "VA2", "DA2"]
SEEDS = [0, 1, 2]
STEER = {"DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
         "DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551}


def load_runs(variant, glom):
    out = {}
    for s in ("left", "right"):
        for sd in SEEDS:
            f = SIM / f"{variant}_{glom}_{s}_s{sd}.npz"
            if not f.exists():
                return None
            out[s, sd] = np.load(f)
    return out


def dn_labels():
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                        columns=["root_id", "cell_type", "hemibrain_type", "side"]).set_index("root_id")
    ids = np.load(SIM / "dn_root_ids.npy")
    lab = n.reindex(ids)
    t = lab.cell_type.astype(object).where(lab.cell_type.notna(), lab.hemibrain_type.astype(object))
    return ids, t.fillna("untyped").to_numpy(), lab.side.astype(object).fillna("na").to_numpy()


def dprime(a, b):
    sd = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    return (a.mean() - b.mean()) / sd if sd > 0 else (np.inf if a.mean() != b.mean() else 0.0)


def main():
    ids, dtype_, dside = dn_labels()
    col = {k: int(np.flatnonzero(ids == v)[0]) for k, v in STEER.items()}
    pn_lab = pd.read_csv(RES / "pn_ipsi_contra_630.csv")
    pn_ids = np.load(SIM / "pn_root_ids.npy")
    # DN pair types: same type, at least one neuron on each side
    types = pd.DataFrame({"type": dtype_, "side": dside})
    both = types[types.side.isin(["left", "right"]) & (types.type != "untyped")]
    pair_types = sorted(set(both[both.side == "left"].type) & set(both[both.side == "right"].type))
    Lcols = {t: np.flatnonzero((dtype_ == t) & (dside == "left")) for t in pair_types}
    Rcols = {t: np.flatnonzero((dtype_ == t) & (dside == "right")) for t in pair_types}

    steer_rows, scan_rows, pn_rows, flip_rows = [], [], [], []
    for v in VARIANTS:
        for g in GLOMERULI:
            R = load_runs(v, g)
            if R is None:
                continue
            # 1. steering neurons
            for pair in ("DNa02", "DNa01"):
                L, Rr = col[pair + "_L"], col[pair + "_R"]
                row = dict(variant=v, glomerulus=g, pair=pair)
                turn = {}
                for s in ("left", "right"):
                    l = np.concatenate([R[s, sd]["dn"][:, L] for sd in SEEDS])
                    r = np.concatenate([R[s, sd]["dn"][:, Rr] for sd in SEEDS])
                    row[f"{s}_odor_L_hz"] = round(float(l.mean()), 2)
                    row[f"{s}_odor_R_hz"] = round(float(r.mean()), 2)
                    turn[s] = {sd: R[s, sd]["dn"][:, L] - R[s, sd]["dn"][:, Rr] for sd in SEEDS}
                    row[f"turn_{s}_odor"] = round(float(l.mean() - r.mean()), 2)
                ps = [stats.ttest_ind(turn["left"][sd], turn["right"][sd], equal_var=False).pvalue
                      for sd in SEEDS]
                row["turn_change_left_minus_right_odor"] = round(row["turn_left_odor"] - row["turn_right_odor"], 2)
                row["welch_p_per_seed"] = "/".join(f"{p:.2g}" for p in ps)
                row["dprime_1s"] = round(float(dprime(np.concatenate(list(turn["left"].values())),
                                                      np.concatenate(list(turn["right"].values())))), 2)
                row["mirror"] = bool(row["turn_left_odor"] > 0 > row["turn_right_odor"])
                steer_rows.append(row)
            # 2. every DN pair type
            n_flip_ipsi = n_flip_contra = 0
            for t in pair_types:
                per_seed = {}
                for s in ("left", "right"):
                    per_seed[s] = {sd: R[s, sd]["dn"][:, Lcols[t]].mean(1) - R[s, sd]["dn"][:, Rcols[t]].mean(1)
                                   for sd in SEEDS}
                mL = np.array([per_seed["left"][sd].mean() for sd in SEEDS])
                mR = np.array([per_seed["right"][sd].mean() for sd in SEEDS])
                act = max(np.abs(mL).max(), np.abs(mR).max())
                if act < 0.5:
                    continue
                ps = np.array([stats.ttest_ind(per_seed["left"][sd], per_seed["right"][sd],
                                               equal_var=False).pvalue for sd in SEEDS])
                ipsi = bool((mL > 0).all() and (mR < 0).all())
                contra = bool((mL < 0).all() and (mR > 0).all())
                sig = bool((np.nan_to_num(ps, nan=1) < 0.01).all())
                a = np.concatenate(list(per_seed["left"].values()))
                b = np.concatenate(list(per_seed["right"].values()))
                scan_rows.append(dict(
                    variant=v, glomerulus=g, dn_type=t, n_left=len(Lcols[t]), n_right=len(Rcols[t]),
                    turn_left_odor=round(float(mL.mean()), 2), turn_right_odor=round(float(mR.mean()), 2),
                    flip=("ipsi" if ipsi else "contra" if contra else "none"), sig_all_seeds=sig,
                    min_abs_turn=round(float(min(abs(mL.mean()), abs(mR.mean()))), 2),
                    dprime_1s=round(float(dprime(a, b)), 2),
                    max_p=float(np.nan_to_num(ps, nan=1).max())))
                n_flip_ipsi += ipsi and sig
                n_flip_contra += contra and sig
            # single DNs whose rate depends on the odor side
            a = np.stack([np.concatenate([R["left", sd]["dn"] for sd in SEEDS])])[0]
            b = np.stack([np.concatenate([R["right", sd]["dn"] for sd in SEEDS])])[0]
            active = (a.mean(0) > 1) | (b.mean(0) > 1)
            sig_single = 0
            ipsi_pref = 0
            for j in np.flatnonzero(active):
                ok = True
                sgn = []
                for sd in SEEDS:
                    x, y = R["left", sd]["dn"][:, j], R["right", sd]["dn"][:, j]
                    p = stats.ttest_ind(x, y, equal_var=False).pvalue
                    if not (p < 0.01):
                        ok = False
                        break
                    sgn.append(np.sign(x.mean() - y.mean()))
                if ok and len(set(sgn)) == 1:
                    sig_single += 1
                    pref_left = sgn[0] > 0
                    ipsi_pref += (pref_left and dside[j] == "left") or ((not pref_left) and dside[j] == "right")
            n_act = [int(np.median(R[s, sd]["n_active"])) for s in ("left", "right") for sd in SEEDS]
            flip_rows.append(dict(variant=v, glomerulus=g, median_active_neurons=int(np.median(n_act)),
                                  active_dns=int(active.sum()), side_sensitive_dns=sig_single,
                                  of_which_prefer_own_side=int(ipsi_pref),
                                  dn_pair_types_tested=len(pair_types),
                                  pairs_flip_ipsi=int(n_flip_ipsi), pairs_flip_contra=int(n_flip_contra)))
            # 4. PNs of this glomerulus (uniglomerular ones, purity >= 0.9)
            sel = pn_lab[(pn_lab.glomerulus == g) & (pn_lab.purity >= 0.9)]
            for side_pn in ("left", "right"):
                cols = np.flatnonzero(np.isin(pn_ids, sel[sel.pn_side == side_pn].pn_root_id.to_numpy()))
                for s in ("left", "right"):
                    full = np.concatenate([R[s, sd]["pn"][:, cols].mean(1) for sd in SEEDS])
                    early = np.concatenate([R[s, sd]["pn_early"][:, cols].mean(1) for sd in SEEDS])
                    pn_rows.append(dict(variant=v, glomerulus=g, pn_side=side_pn, n_pns=len(cols), odor_side=s,
                                        ipsi=(side_pn == s), rate_hz=round(float(full.mean()), 1),
                                        early_0_50ms_hz=round(float(early.mean()), 1)))
    st = pd.DataFrame(steer_rows)
    st.to_csv(RES / "steering_table.csv", index=False)
    sc = pd.DataFrame(scan_rows)
    sc.to_csv(RES / "dn_pair_scan.csv", index=False)
    pn = pd.DataFrame(pn_rows)
    pn.to_csv(RES / "pn_lateralization.csv", index=False)
    fl = pd.DataFrame(flip_rows)
    fl.to_csv(RES / "flip_summary.csv", index=False)
    if len(sc):
        cand = sc[(sc.flip != "none") & sc.sig_all_seeds].copy()
        cand = cand.sort_values(["variant", "min_abs_turn"], ascending=[True, False])
        cand.to_csv(RES / "dn_pair_candidates.csv", index=False)
        # which pair types flip for several odors?
        agg = cand.groupby(["variant", "dn_type", "flip"]).agg(
            n_glomeruli=("glomerulus", "nunique"), glomeruli=("glomerulus", lambda x: ",".join(sorted(x))),
            mean_min_abs_turn=("min_abs_turn", "mean")).reset_index()
        agg = agg.sort_values(["variant", "n_glomeruli", "mean_min_abs_turn"], ascending=[True, False, False])
        agg.to_csv(RES / "dn_pair_candidates_by_type.csv", index=False)
    # PN ipsi/contra summary
    if len(pn):
        pv = pn.pivot_table(index=["variant", "glomerulus", "odor_side"], columns="ipsi",
                            values=["rate_hz", "early_0_50ms_hz"]).reset_index()
        pv.columns = ["variant", "glomerulus", "odor_side", "early_contra", "early_ipsi", "rate_contra", "rate_ipsi"]
        pv["ipsi_over_contra_rate"] = (pv.rate_ipsi / pv.rate_contra.replace(0, np.nan)).round(2)
        pv["ipsi_over_contra_early"] = (pv.early_ipsi / pv.early_contra.replace(0, np.nan)).round(2)
        pv.to_csv(RES / "pn_ipsi_contra_rates.csv", index=False)
    pd.set_option("display.width", 200)
    print(st.to_string(index=False))
    print(fl.to_string(index=False))


if __name__ == "__main__":
    main()

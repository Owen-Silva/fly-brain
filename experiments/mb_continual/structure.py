"""Is the real glomerulus -> KC wiring different from random, and where? (No learning.)

Zheng et al. 2022 (Curr Biol) found that some, mostly food-responsive, PN types converge
onto the same KCs more often than chance. Our version of their test, per brain half:
* C[g, h] = number of KCs that get input from both glomerulus g and glomerulus h.
* The same count in 500 "shuffled" controls (control (a): each KC keeps its number of
  inputs, glomeruli drawn with their real frequencies) gives a mean and SD per pair;
  z[g, h] = (real - mean) / SD.
* A glomerulus's over-convergence score = its mean z with all other glomeruli.
* Replicate check: do the left and right halves agree (Spearman over glomeruli / pairs)?
* Communities (as Zheng et al.): glomeruli clustered by pair z (mean of both halves); the
  cluster with the highest within-cluster z is the "core community".
* Per odour, "exposure" = the share of the odour's PN drive that flows through the core
  community, used later to ask whether real wiring helps those odours.
Writes results/overconvergence.csv, results/communities.csv, results/odour_exposure.csv,
results/structure.json (and results/raw/pair_z.npz).
"""
import numpy as np
import pandas as pd
from scipy import stats

from common import (RES, all_glomeruli, control_wiring, glomerulus_kc_table, load_odours,
                    log, pn_mean, real_wiring, save_json)

N_NULL = 500
table, _ = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
P = pn_mean(od.delta, od.set_a)
out, per_side = {}, {}
iu = np.triu_indices(len(gloms), 1)
for si, side in enumerate(("left", "right")):
    r = real_wiring(side, table=table, gloms=gloms)
    B = (r.W > 0).astype(np.float32)
    C = B.T @ B
    rng = np.random.default_rng([7, si])
    null = np.empty((N_NULL, len(gloms), len(gloms)), np.float32)
    for i in range(N_NULL):
        c = control_wiring(r, "shuffled", rng)
        b = (c.W > 0).astype(np.float32)
        null[i] = b.T @ b
    mu, sd = null.mean(0), null.std(0)
    z = np.where(sd > 0, (C - mu) / np.where(sd > 0, sd, 1), 0.0)
    np.fill_diagonal(z, np.nan)
    per_side[side] = {"z": z, "score": np.nanmean(z, 1), "freq": B.sum(0) / B.sum()}
    zp = z[iu]
    # expected number of |z| > 3 pairs under the null, from the null samples themselves
    null_z = (null[:50][:, iu[0], iu[1]] - mu[iu]) / np.where(sd[iu] > 0, sd[iu], 1)
    out[side] = {"pairs": int(zp.size), "pairs_z_above_3": int((zp > 3).sum()),
                 "pairs_z_below_-3": int((zp < -3).sum()),
                 "null_pairs_abs_z_above_3_mean": float((np.abs(null_z) > 3).sum(1).mean()),
                 "top10_overconvergent": [gloms[i] for i in np.argsort(-per_side[side]["score"])[:10]]}
    log(f"{side}: pairs z>3 {out[side]['pairs_z_above_3']}, z<-3 {out[side]['pairs_z_below_-3']}, "
        f"null |z|>3 {out[side]['null_pairs_abs_z_above_3_mean']:.1f}; top {out[side]['top10_overconvergent']}")
zl, zr = per_side["left"]["score"], per_side["right"]["score"]
out["left_right_spearman_glomerulus_score"] = float(stats.spearmanr(zl, zr).statistic)
out["left_right_spearman_pair_z"] = float(stats.spearmanr(per_side["left"]["z"][iu],
                                                          per_side["right"]["z"][iu]).statistic)
score = (zl + zr) / 2
np.savez_compressed(RES / "raw" / "pair_z.npz", z_left=per_side["left"]["z"],
                    z_right=per_side["right"]["z"], gloms=np.array(gloms))

# Communities, as in Zheng et al. 2022: cluster glomeruli by their pair z-scores (mean of
# both halves; average linkage on distance = max z - z), cut into 6 clusters, and call the
# cluster (>= 3 glomeruli) with the highest mean within-cluster z the "core community".
from scipy.cluster.hierarchy import fcluster, linkage
from scipy.spatial.distance import squareform

zm = (per_side["left"]["z"] + per_side["right"]["z"]) / 2
dist = np.nanmax(zm) - zm
np.fill_diagonal(dist, 0.0)
lab = fcluster(linkage(squareform(dist, checks=False), "average"), 6, "maxclust")
comm = []
for c in np.unique(lab):
    idx = np.flatnonzero(lab == c)
    sub = zm[np.ix_(idx, idx)]
    within = float(np.nanmean(sub)) if idx.size > 1 else np.nan
    comm.append({"cluster": int(c), "n": int(idx.size), "within_mean_z": within,
                 "within_mean_z_left": float(np.nanmean(per_side["left"]["z"][np.ix_(idx, idx)]))
                 if idx.size > 1 else np.nan,
                 "within_mean_z_right": float(np.nanmean(per_side["right"]["z"][np.ix_(idx, idx)]))
                 if idx.size > 1 else np.nan,
                 "glomeruli": " ".join(gloms[i] for i in idx)})
comm = pd.DataFrame(comm).sort_values("within_mean_z", ascending=False)
comm.to_csv(RES / "communities.csv", index=False)
core_id = comm[comm.n >= 3].iloc[0].cluster
core = lab == core_id
out["core_community"] = [g for g, c in zip(gloms, core) if c]
out["communities"] = comm.round(3).to_dict("records")
log(f"core community: {out['core_community']}")
pd.DataFrame({"glomerulus": gloms, "score_left": zl, "score_right": zr, "score_mean": score,
              "cluster": lab, "core_community": core,
              "freq_left": per_side["left"]["freq"], "freq_right": per_side["right"]["freq"],
              "odour_data": np.where(od.set_a, "A", np.where(od.has_data, "B", "none"))}
             ).sort_values("score_mean", ascending=False).to_csv(RES / "overconvergence.csv",
                                                                 index=False)
# odour exposure: the share of the odour's PN drive that flows through core-community
# glomeruli (Zheng et al.: real wiring should help when signal flows through them)
expo = P[:, core].sum(1) / np.maximum(P.sum(1), 1e-9)
fruit = np.isin(od.chem, ("esters", "alcohols", "acids"))
pd.DataFrame({"odour": od.names, "chem_class": od.chem, "exposure": expo,
              "total_pn_drive_hz": P.sum(1)}).to_csv(RES / "odour_exposure.csv", index=False)
out["exposure_fruit_vs_other_mannwhitney_p"] = float(stats.mannwhitneyu(expo[fruit], expo[~fruit]).pvalue)
out["exposure_mean_fruit"] = float(expo[fruit].mean())
out["exposure_mean_other"] = float(expo[~fruit].mean())
out["exposure_by_chem_class"] = pd.Series(expo).groupby(od.chem).mean().round(3).to_dict()
save_json(out, RES / "structure.json")
log(f"L-R agreement: glomerulus score rho {out['left_right_spearman_glomerulus_score']:.2f}, "
    f"pair z rho {out['left_right_spearman_pair_z']:.2f}")
log(f"exposure fruit {out['exposure_mean_fruit']:.3f} vs other {out['exposure_mean_other']:.3f} "
    f"(p {out['exposure_fruit_vs_other_mannwhitney_p']:.2g}); by class {out['exposure_by_chem_class']}")

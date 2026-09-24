"""POST HOC diagnostic: the hardest odour pairs. Accuracy depends on how close each odour's
KC code is to its NEAREST other odour, not on the average similarity. Noise-free odour
inputs, main settings. Per wiring: mean over odours of the highest correlation with any
other odour ("nearest-neighbour similarity"), share of odour pairs with correlation > 0.8,
and the same for the PN input. Controls: 10 draws each (same streams as the main run).
Writes results/diag_nearest_neighbour.csv and results/diag_nearest_neighbour_per_odour.csv.
"""
import numpy as np
import pandas as pd

from common import (RES, all_glomeruli, control_wiring, glomerulus_kc_table, kc_code,
                    load_odours, pn_mean, real_wiring)

table, _ = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
P = pn_mean(od.delta, od.set_a).astype(np.float32)


def nn_stats(H):
    C = np.corrcoef(H)
    np.fill_diagonal(C, np.nan)
    iu = np.triu_indices(C.shape[0], 1)
    return np.nanmax(C, 1), float(np.nanmean(C[iu] > 0.8))


rows, per = [], []
pn_nn, pn_hi = nn_stats(P)
rows.append({"side": "-", "wiring": "PN input", "nn_corr_mean": float(np.nanmean(pn_nn)),
             "pairs_corr_above_0.8": pn_hi})
for si, side in enumerate(("left", "right")):
    real = real_wiring(side, table=table, gloms=gloms)
    nn, hi = nn_stats(kc_code(real.W, P))
    rows.append({"side": side, "wiring": "real", "nn_corr_mean": float(np.nanmean(nn)),
                 "pairs_corr_above_0.8": hi})
    per.append(pd.DataFrame({"side": side, "wiring": "real", "odour": od.names, "nn_corr": nn}))
    for kind in ("shuffled", "uniform"):
        acc_nn, acc_hi = [], []
        for seed in range(10):
            wr = np.random.default_rng([seed, 303, si])
            c1 = control_wiring(real, "shuffled", wr)
            c = c1 if kind == "shuffled" else control_wiring(real, "uniform", wr)
            nn_c, hi_c = nn_stats(kc_code(c.W, P))
            acc_nn.append(nn_c)
            acc_hi.append(hi_c)
        m = np.nanmean(acc_nn, 0)
        rows.append({"side": side, "wiring": kind, "nn_corr_mean": float(np.nanmean(m)),
                     "pairs_corr_above_0.8": float(np.mean(acc_hi))})
        per.append(pd.DataFrame({"side": side, "wiring": kind, "odour": od.names, "nn_corr": m}))
pd.DataFrame(rows).to_csv(RES / "diag_nearest_neighbour.csv", index=False)
pd.concat(per).to_csv(RES / "diag_nearest_neighbour_per_odour.csv", index=False)
print(pd.DataFrame(rows).round(3).to_string(index=False))

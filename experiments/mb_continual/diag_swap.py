"""POST HOC diagnostic: is the real wiring's deficit caused by WHICH glomeruli share a KC
(co-convergence), or by how strong each glomerulus's connections are?

"edge_swap" control: every real connection keeps its glomerulus AND its synapse count; the
connections are dealt out again at random to the KC input slots (each KC keeps its number
of inputs; a KC never gets the same glomerulus twice). So each glomerulus keeps exactly its
real set of connection strengths, but which glomeruli meet on the same KC is random.
If edge_swap ~ real: the deficit comes from per-glomerulus connection strengths.
If edge_swap ~ shuffled: the deficit comes from co-convergence (Zheng et al.'s structure).
Also: per glomerulus, mean synapses per connection vs its mean odour-evoked PN response.
Main settings, same trials as the main run, 20 seeds, both halves. With --kcnorm, each
KC's input is divided by its total synapses (removes the KC-total confound of edge_swap).
Writes results/diag_swap.csv, results/diag_swap_compare.csv, results/glomerulus_weight_vs_response.csv.
"""
import sys

import numpy as np
import pandas as pd
from scipy import stats

from analyze import compare
from common import (RES, FlyReadout, all_glomeruli, control_wiring, edge_swap,
                    glomerulus_kc_table, kc_code, load_odours, log, make_trials, pn_mean,
                    real_wiring)

K, T, N_TR, N_TE = 0.05, 0.05, 20, 20
KCNORM = "--kcnorm" in sys.argv        # divide each KC's input by its total synapses
TAG = "_kcnorm" if KCNORM else ""


table, _ = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
P = pn_mean(od.delta, od.set_a)
n_od = P.shape[0]
rows, gw = [], []
for seed in range(20):
    rng_tr = np.random.default_rng([seed, 101])
    Xtr, ytr = make_trials(P, N_TR, T, rng_tr)
    Xte, yte = make_trials(P, N_TE, T, rng_tr)
    for si, side in enumerate(("left", "right")):
        real = real_wiring(side, table=table, gloms=gloms)
        if seed == 0:
            B = real.W > 0
            mw = np.where(B.sum(0) > 0, real.W.sum(0) / np.maximum(B.sum(0), 1), np.nan)
            resp = P.mean(0)
            ok = od.has_data & np.isfinite(mw)
            r = stats.spearmanr(mw[ok], resp[ok])
            gw.append(pd.DataFrame({"side": side, "glomerulus": gloms, "mean_syn_per_connection": mw,
                                    "connections": B.sum(0), "mean_evoked_pn_hz": resp,
                                    "has_odour_data": od.has_data}))
            log(f"{side}: Spearman(mean synapses per connection, mean odour response) over "
                f"{ok.sum()} glomeruli with data = {r.statistic:.2f} (p {r.pvalue:.2g})")
        ws = [real, edge_swap(real, np.random.default_rng([seed, 1111, si])),
              control_wiring(real, "shuffled", np.random.default_rng([seed, 303, si]))]
        for w in ws:
            fly = FlyReadout(w.W.shape[0], n_od)
            fly.train(kc_code(w.W, Xtr, K, per_kc_norm=KCNORM), ytr)
            acc = float((fly.predict(kc_code(w.W, Xte, K, per_kc_norm=KCNORM), np.arange(n_od)) == yte).mean())
            rows.append({"seed": seed, "side": side, "wiring": w.name, "final_acc": acc})
    log(f"seed {seed} done")
d = pd.DataFrame(rows)
d.to_csv(RES / f"diag_swap{TAG}.csv", index=False)
pd.concat(gw).to_csv(RES / "glomerulus_weight_vs_response.csv", index=False)
comp = []
for side in ("left", "right"):
    x = d[d.side == side].pivot(index="seed", columns="wiring", values="final_acc")
    for ctl in ("edge_swap", "shuffled"):
        comp.append({"side": side, "control": ctl, **compare(x["real"], x[ctl])})
    comp.append({"side": side, "control": "edge_swap minus shuffled",
                 **compare(x["edge_swap"], x["shuffled"])})
c = pd.DataFrame(comp)
c.to_csv(RES / f"diag_swap_compare{TAG}.csv", index=False)
print(c[["side", "control", "mean_a", "mean_b", "diff", "se_paired", "call"]].round(4).to_string(index=False))

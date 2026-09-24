"""POST HOC robustness check (not pre-registered): KCs that balance their own excitability.

In the main model over half of the KCs never respond to any of the 110 odours (every wiring),
because KCs with many synapses always win. Real neurons adjust their own excitability. Here
each KC's input is z-scored with its own mean and SD over the training trials (all odours)
before the top-5% selection, so every KC is roughly equally likely to win. Main settings,
same trials and control draws as the main run, 20 seeds, both halves; final accuracy (train
on all 110 odours, test on all 110 = task-10 accuracy, since the fly rule is order-free).
Writes results/diag_kcz.csv and results/diag_kcz_compare.csv.
"""
import numpy as np
import pandas as pd

from analyze import compare
from common import (RES, FlyReadout, all_glomeruli, control_wiring, edge_swap,
                    glomerulus_kc_table, load_odours, log, make_trials, pn_mean, real_wiring)

K, T, N_TR, N_TE = 0.05, 0.05, 20, 20


def kc_code_z(W, Xtr, Xte, k_frac=K):
    Wt = W.T.astype(np.float32)
    itr, ite = Xtr @ Wt, Xte @ Wt
    mu, sd = itr.mean(0), itr.std(0) + 1e-6
    out = []
    for inp in (itr, ite):
        z = (inp - mu) / sd
        k = int(round(k_frac * W.shape[0]))
        thr = -np.partition(-z, k, axis=1)[:, k]
        h = np.maximum(z - thr[:, None], 0.0)
        mx = h.max(1, keepdims=True)
        out.append(np.where(mx > 0, h / np.where(mx > 0, mx, 1.0), 0.0).astype(np.float32))
    return out


table, _ = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
P = pn_mean(od.delta, od.set_a)
n_od = P.shape[0]
rows = []
for seed in range(20):
    rng_tr = np.random.default_rng([seed, 101])
    Xtr, ytr = make_trials(P, N_TR, T, rng_tr)
    Xte, yte = make_trials(P, N_TE, T, rng_tr)
    for si, side in enumerate(("left", "right")):
        real = real_wiring(side, table=table, gloms=gloms)
        wr = np.random.default_rng([seed, 303, si])
        ws = [real, control_wiring(real, "shuffled", wr), control_wiring(real, "uniform", wr),
              edge_swap(real, np.random.default_rng([seed, 1111, si]))]
        for w in ws:
            Htr, Hte = kc_code_z(w.W, Xtr, Xte)
            fly = FlyReadout(w.W.shape[0], n_od)
            fly.train(Htr, ytr)
            acc = float((fly.predict(Hte, np.arange(n_od)) == yte).mean())
            rows.append({"seed": seed, "side": side, "wiring": w.name, "final_acc": acc,
                         "silent_kc_share_test": float((~(Hte > 0).any(0)).mean())})
    log(f"seed {seed} done")
d = pd.DataFrame(rows)
d.to_csv(RES / "diag_kcz.csv", index=False)
comp = []
for side in ("left", "right"):
    x = d[d.side == side].pivot(index="seed", columns="wiring", values="final_acc")
    for ctl in ("shuffled", "uniform", "edge_swap"):
        comp.append({"side": side, "control": ctl, **compare(x["real"], x[ctl])})
c = pd.DataFrame(comp)
c.to_csv(RES / "diag_kcz_compare.csv", index=False)
print(c[["side", "control", "mean_a", "mean_b", "diff", "se_paired", "se_unpaired", "call"]].round(4).to_string(index=False))
print(d.groupby(["side", "wiring"]).silent_kc_share_test.mean().round(3).to_string())

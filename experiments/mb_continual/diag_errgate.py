"""POST HOC (not pre-registered): is the small good/bad capacity a limit of the KC code or
of the always-add learning rule?

Same capacity task as run_capacity.py (main settings, T = 0.05 s, same trials, same odour
order and labels, same control draws), fly models only. Rule compared with the pre-registered
one ("always add", Shen et al.):
"error-gated": still local (only synapses from active KCs change) and still gated by a
teaching signal, but the signal is an ERROR: after a trial the synapses change only if the
answer was wrong, and then the correct output's synapses from active KCs strengthen and the
wrong output's weaken (weights kept in [0, 1]; 5 passes over the training trials in random
order). Dopamine neurons in flies receive feedback from the output neurons, so an
error-like teaching signal is biologically possible; we did not model its mechanism.
Writes results/diag_errgate.csv and results/diag_errgate_summary.csv.
"""
import numpy as np
import pandas as pd

from common import (RES, all_glomeruli, control_wiring, glomerulus_kc_table, kc_code,
                    load_odours, log, make_trials, pn_mean, real_wiring)
from run_capacity import N_GRID

T, K, N_TR, N_TE, BETA, PASSES = 0.05, 0.05, 20, 20, 0.01, 5


def train_errgate(H, v, rng, n_kc):
    W = np.zeros((2, n_kc), np.float32)
    changed = []
    for _ in range(PASSES):
        for i in rng.permutation(H.shape[0]):
            h = H[i]
            s = W @ h
            if np.argmax(s) != v[i] or s[0] == s[1]:
                W[v[i]] = np.minimum(1.0, W[v[i]] + BETA * h)
                W[1 - v[i]] = np.maximum(0.0, W[1 - v[i]] - BETA * h)
                changed.append(2 * int((h > 0).sum()))
            else:
                changed.append(0)
    return W, float(np.mean(changed))


table, _ = glomerulus_kc_table()
gloms = all_glomeruli()
od = load_odours(gloms)
P = pn_mean(od.delta, od.set_a)
n_od = P.shape[0]
rows = []
for seed in range(20):
    rng = np.random.default_rng([seed, 7001])          # same stream as run_capacity.py
    Xtr, ytr = make_trials(P, N_TR, T, rng)
    Xte, yte = make_trials(P, N_TE, T, rng)
    order = rng.permutation(n_od)
    val = np.zeros(n_od, int)
    val[order] = np.arange(n_od) % 2
    rank = np.empty(n_od, int)
    rank[order] = np.arange(n_od)
    for si, side in enumerate(("left", "right")):
        real = real_wiring(side, table=table, gloms=gloms)
        wr = np.random.default_rng([seed, 7002, si])
        for w in (real, control_wiring(real, "shuffled", wr), control_wiring(real, "uniform", wr)):
            Htr, Hte = kc_code(w.W, Xtr, K), kc_code(w.W, Xte, K)
            for N in N_GRID:
                mtr, mte = rank[ytr] < N, rank[yte] < N
                W, ch = train_errgate(Htr[mtr], val[ytr[mtr]], np.random.default_rng([seed, 7006, si, N]),
                                      w.W.shape[0])
                pred = np.argmax(Hte[mte] @ W.T, axis=1)
                rows.append({"seed": seed, "side": side, "model": f"fly_{w.name}_errgate", "N": N,
                             "error": float((pred != val[yte[mte]]).mean()),
                             "changed_per_example": ch})
    log(f"seed {seed} done")
    pd.DataFrame(rows).to_csv(RES / "diag_errgate.csv", index=False)
d = pd.DataFrame(rows)


def n_at_10(x):
    x = x.sort_values("N")
    e, n = x.error.to_numpy(), x.N.to_numpy()
    above = np.flatnonzero(e > 0.10)
    if above.size == 0:
        return np.nan
    i = above[0]
    if i == 0:
        return float(n[0])
    return float(n[i - 1] + (0.10 - e[i - 1]) * (n[i] - n[i - 1]) / (e[i] - e[i - 1]))


cap = d.groupby(["seed", "side", "model"]).apply(n_at_10, include_groups=False).rename("capacity")
s = cap.reset_index().groupby(["side", "model"]).capacity.agg(["mean", "sem", lambda x: int(x.isna().sum())])
s.columns = ["capacity_mean", "capacity_se", "n_never_above_10pct"]
s = s.join(d[d.N == 110].groupby(["side", "model"]).error.mean().rename("error_at_110"))
s = s.join(d.groupby(["side", "model"]).changed_per_example.mean())
s.to_csv(RES / "diag_errgate_summary.csv")
print(s.round(3).to_string())

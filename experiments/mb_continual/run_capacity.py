"""Capacity: how many odour -> good/bad associations fit before errors pass 10%?

For each seed: a random order of the 110 real odours; good/bad labels alternate along that
order (so the labels are random but balanced for every N). For N = 5 ... 110, the first N odours are learned (20 noisy training trials each)
and tested on 20 fresh trials each. Error = fraction of test trials given the wrong label.
Two output neurons ("approach" and "avoid").
* fly models (real / shuffled / uniform wiring): the Shen et al. rule, weights capped at 1
  ("capped"), and the same without the cap ("uncapped", ideal unbounded synapses). For two
  outputs this rule is the same as the fly's own (weakening the other output's synapses).
* mlp_joint: backprop on all N at once. mlp_seq: backprop in blocks of 10 odours, one block
  after another (a block of fewer than 10 at the end if N is not a multiple of 10).
Usage: python run_capacity.py [--seeds 20] [--mlp-seeds 5] [--T 0.05] [--k 0.05]
Writes results/raw/capacity[_tag].csv.
"""
import argparse
import time

import numpy as np
import pandas as pd

from common import (MLP, RAW, FlyReadout, all_glomeruli, control_wiring, glomerulus_kc_table,
                    kc_code, load_odours, log, make_trials, pn_mean, real_wiring, wait_for_ram)
from run_incremental import MLP_EPOCHS, MLP_LR, N_TE, N_TR

N_GRID = (5, 10, 15, 20, 30, 40, 50, 60, 80, 110)
N_GRID_MLP = (10, 20, 40, 60, 80, 110)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--mlp-seeds", type=int, default=5)
    ap.add_argument("--T", type=float, default=0.05)
    ap.add_argument("--k", type=float, default=0.05)
    ap.add_argument("--tag", default="")
    a = ap.parse_args()
    wait_for_ram()
    table, _ = glomerulus_kc_table()
    gloms = all_glomeruli()
    od = load_odours(gloms)
    P = pn_mean(od.delta, od.set_a)
    n_od = P.shape[0]
    reals = {s: real_wiring(s, table=table, gloms=gloms) for s in ("left", "right")}
    rows = []
    t0 = time.time()
    for seed in range(a.seeds):
        rng = np.random.default_rng([seed, 7001])
        Xtr, ytr = make_trials(P, N_TR, a.T, rng)
        Xte, yte = make_trials(P, N_TE, a.T, rng)
        order = rng.permutation(n_od)
        val = np.zeros(n_od, int)
        val[order] = np.arange(n_od) % 2        # good/bad alternate along the random order,
        #                                         so every N has a balanced (or +1) split
        rank = np.empty(n_od, int)
        rank[order] = np.arange(n_od)
        for si, side in enumerate(("left", "right")):
            real = reals[side]
            wr = np.random.default_rng([seed, 7002, si])
            wirings = [real, control_wiring(real, "shuffled", wr), control_wiring(real, "uniform", wr)]
            for w in wirings:
                Htr = kc_code(w.W, Xtr, a.k)
                Hte = kc_code(w.W, Xte, a.k)
                for N in N_GRID:
                    mtr, mte = rank[ytr] < N, rank[yte] < N
                    for capname, cap in (("capped", 1.0), ("uncapped", np.inf)):
                        fly = FlyReadout(w.W.shape[0], 2, cap=cap)
                        fly.train(Htr[mtr], val[ytr[mtr]])
                        pred = fly.predict(Hte[mte], [0, 1])
                        rows.append({"seed": seed, "side": side, "model": f"fly_{w.name}_{capname}",
                                     "N": N, "error": float((pred != val[yte[mte]]).mean())})
            if seed < a.mlp_seeds:
                n_hid = real.W.shape[0]
                for N in N_GRID_MLP:
                    mtr, mte = rank[ytr] < N, rank[yte] < N
                    Xa, ya = Xtr[mtr] / 100.0, val[ytr[mtr]]
                    mlp = MLP(Xtr.shape[1], n_hid, 2, np.random.default_rng([seed, 7003, si, N]), lr=MLP_LR)
                    mlp.fit(Xa, ya, [0, 1], MLP_EPOCHS, np.random.default_rng([seed, 7004, si, N]))
                    pred = mlp.predict(Xte[mte] / 100.0, [0, 1])
                    rows.append({"seed": seed, "side": side, "model": "mlp_joint", "N": N,
                                 "error": float((pred != val[yte[mte]]).mean())})
                    mlp = MLP(Xtr.shape[1], n_hid, 2, np.random.default_rng([seed, 7003, si, N]), lr=MLP_LR)
                    fit_rng = np.random.default_rng([seed, 7005, si, N])
                    for b in range(0, N, 10):
                        blk = (rank[ytr] >= b) & (rank[ytr] < min(N, b + 10))
                        mlp.fit(Xtr[blk] / 100.0, val[ytr[blk]], [0, 1], MLP_EPOCHS, fit_rng)
                    pred = mlp.predict(Xte[mte] / 100.0, [0, 1])
                    rows.append({"seed": seed, "side": side, "model": "mlp_seq", "N": N,
                                 "error": float((pred != val[yte[mte]]).mean())})
        pd.DataFrame(rows).to_csv(RAW / f"capacity{a.tag}.csv", index=False)
        log(f"seed {seed} done ({time.time() - t0:.0f} s)")
    log("done")


if __name__ == "__main__":
    main()

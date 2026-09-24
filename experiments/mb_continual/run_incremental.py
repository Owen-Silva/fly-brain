"""Class-incremental odour learning: 110 real odours taught in 10 tasks of 11 odours.

After each task every model is tested on fresh noisy trials of ALL odours taught so far
(answer = the most active output among the odours taught so far). Models, per brain half:
* fly_real      fly model on the real glomerulus -> KC wiring
* fly_shuffled  control (a): same KCs / input counts / synapse counts, glomeruli drawn
                with their real frequencies (new draw each seed)
* fly_uniform   control (b): same, glomeruli equally likely (new draw each seed)
* mlp_seq       MLP, same hidden size, backprop, tasks one after another (no replay)
* mlp_joint     MLP trained on all 110 odours at once (the upper bound)
Seed s fixes the noisy trials and the task order, shared by every model of that seed.

Usage: python run_incremental.py VARIANT [--seeds N] [--mlp-seeds M]
VARIANT: main | k2 | k3 | k7.5 | k10 | T0.02 | T0.1 | T0.2 | T0.5 | syn5 | kcnorm | setA
Writes results/raw/incr_<VARIANT>.csv.gz (per seed, side, model, checkpoint, odour: correct
test trials) and results/raw/incr_<VARIANT>_cost.csv.
"""
import argparse
import time

import numpy as np
import pandas as pd

from common import (MLP, RAW, FlyReadout, all_glomeruli, control_wiring, glomerulus_kc_table,
                    kc_code, load_odours, log, make_trials, mlp_changed_per_example, pn_mean,
                    real_wiring, wait_for_ram)

MAIN = dict(k=0.05, T=0.05, min_syn=1, kcnorm=False, sets=("A", "B"))
N_TR, N_TE, N_TASKS = 20, 20, 10
MLP_EPOCHS, MLP_LR = 20, 1e-3          # chosen in pilot.py (seed 999)


def variant_params(v):
    p = dict(MAIN)
    if v == "main":
        pass
    elif v == "syn5":
        p["min_syn"] = 5
    elif v == "kcnorm":
        p["kcnorm"] = True
    elif v == "setA":
        p["sets"] = ("A",)
    elif v.startswith("k"):
        p["k"] = float(v[1:]) / 100
    elif v.startswith("T"):
        p["T"] = float(v[1:])
    else:
        raise ValueError(v)
    return p


def eval_rows(pred, yte, classes, base):
    """One row per odour in ``classes``: number of its test trials answered correctly."""
    ok = pred == yte
    out = []
    for c in classes:
        m = yte == c
        out.append({**base, "odour": int(c), "correct": int(ok[m].sum()), "n": int(m.sum())})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("--seeds", type=int, default=20)
    ap.add_argument("--mlp-seeds", type=int, default=0)
    a = ap.parse_args()
    p = variant_params(a.variant)
    log(f"variant {a.variant}: {p}, seeds {a.seeds}, mlp seeds {a.mlp_seeds}")
    wait_for_ram()
    table, _ = glomerulus_kc_table()
    gloms = all_glomeruli()
    od = load_odours(gloms, sets=p["sets"])
    P = pn_mean(od.delta, od.set_a)
    n_od = P.shape[0]
    reals = {s: real_wiring(s, min_syn=p["min_syn"], table=table, gloms=gloms)
             for s in ("left", "right")}
    rows, cost = [], []
    t0 = time.time()
    for seed in range(a.seeds):
        rng_tr = np.random.default_rng([seed, 101])
        Xtr, ytr = make_trials(P, N_TR, p["T"], rng_tr)
        Xte, yte = make_trials(P, N_TE, p["T"], rng_tr)
        order = np.random.default_rng([seed, 202]).permutation(n_od)
        tasks = np.array_split(order, N_TASKS)
        for si, side in enumerate(("left", "right")):
            real = reals[side]
            wr = np.random.default_rng([seed, 303, si])
            wirings = [real, control_wiring(real, "shuffled", wr), control_wiring(real, "uniform", wr)]
            for w in wirings:
                Htr = kc_code(w.W, Xtr, p["k"], per_kc_norm=p["kcnorm"])
                Hte = kc_code(w.W, Xte, p["k"], per_kc_norm=p["kcnorm"])
                fly = FlyReadout(w.W.shape[0], n_od)
                seen = []
                for ti, task in enumerate(tasks):
                    m = np.isin(ytr, task)
                    fly.train(Htr[m], ytr[m])
                    seen.extend(task.tolist())
                    mt = np.isin(yte, seen)
                    pred = fly.predict(Hte[mt], seen)
                    rows += eval_rows(pred, yte[mt], seen, {"seed": seed, "side": side,
                                                           "model": f"fly_{w.name}", "after_task": ti})
                cost.append({"seed": seed, "side": side, "model": f"fly_{w.name}",
                             "changed_per_example": float(np.mean(fly.n_changed)),
                             "frac_active_test": float((Hte > 0).mean()),
                             "n_hidden": w.W.shape[0]})
            if seed < a.mlp_seeds:
                n_hid = real.W.shape[0]
                Xtr_s, Xte_s = Xtr / 100.0, Xte / 100.0
                # sequential: tasks one after another, softmax over the odours seen so far
                mlp = MLP(Xtr.shape[1], n_hid, n_od, np.random.default_rng([seed, 404, si]), lr=MLP_LR)
                seen = []
                fit_rng = np.random.default_rng([seed, 505, si])
                for ti, task in enumerate(tasks):
                    seen.extend(task.tolist())
                    m = np.isin(ytr, task)
                    mlp.fit(Xtr_s[m], ytr[m], np.array(seen), MLP_EPOCHS, fit_rng)
                    mt = np.isin(yte, seen)
                    pred = mlp.predict(Xte_s[mt], seen)
                    rows += eval_rows(pred, yte[mt], seen, {"seed": seed, "side": side,
                                                           "model": "mlp_seq", "after_task": ti})
                act_te = float((mlp.hidden(Xte_s) > 0).mean())
                cost.append({"seed": seed, "side": side, "model": "mlp_seq",
                             "changed_per_example": float(mlp_changed_per_example(
                                 np.mean(mlp.active_frac), Xtr.shape[1], n_hid, n_od)),
                             "frac_active_test": act_te, "n_hidden": n_hid,
                             "n_weights": int(sum(q.size for q in mlp.params))})
                # joint: everything at once (upper bound); tested once, at the end
                mlp = MLP(Xtr.shape[1], n_hid, n_od, np.random.default_rng([seed, 404, si]), lr=MLP_LR)
                mlp.fit(Xtr_s, ytr, np.arange(n_od), MLP_EPOCHS, np.random.default_rng([seed, 606, si]))
                pred = mlp.predict(Xte_s, np.arange(n_od))
                rows += eval_rows(pred, yte, np.arange(n_od), {"seed": seed, "side": side,
                                                               "model": "mlp_joint",
                                                               "after_task": N_TASKS - 1})
                cost.append({"seed": seed, "side": side, "model": "mlp_joint",
                             "changed_per_example": float(mlp_changed_per_example(
                                 np.mean(mlp.active_frac), Xtr.shape[1], n_hid, n_od)),
                             "frac_active_test": float((mlp.hidden(Xte_s) > 0).mean()),
                             "n_hidden": n_hid, "n_weights": int(sum(q.size for q in mlp.params))})
            # task membership, for the memory-loss measure
        log(f"seed {seed} done ({time.time() - t0:.0f} s)")
        df = pd.DataFrame(rows)
        df["variant"] = a.variant
        df.to_csv(RAW / f"incr_{a.variant}.csv.gz", index=False)
        pd.DataFrame(cost).assign(variant=a.variant).to_csv(RAW / f"incr_{a.variant}_cost.csv",
                                                             index=False)
    # the task order of every seed (needed to know which task each odour belonged to)
    orders = [{"seed": s, "odour": int(o), "task": ti}
              for s in range(a.seeds)
              for ti, task in enumerate(np.array_split(
                  np.random.default_rng([s, 202]).permutation(n_od), N_TASKS))
              for o in task]
    pd.DataFrame(orders).to_csv(RAW / f"incr_{a.variant}_tasks.csv", index=False)
    log("done")


if __name__ == "__main__":
    main()

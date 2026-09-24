"""Pilot (seed 999, never used again): pick the trial-noise level and the MLP settings
WITHOUT looking at real-vs-random wiring.

Rule fixed before running: the noise window T is the grid value whose MLP-joint
(backprop, all odours at once, the upper bound) test accuracy is closest to 85%, so the
task is neither trivial nor hopeless. The MLP's epochs/learning rate are the pair with the
best MLP-joint accuracy at that T. The only fly model looked at uses a UNIFORM control
wiring (left half), just to check it is not at floor or ceiling. Output: results/pilot.json
"""
import time

import numpy as np

from common import (MLP, RES, control_wiring, kc_code, load_odours, log, make_trials,
                    pn_mean, real_wiring, save_json, FlyReadout, wait_for_ram)

wait_for_ram()
SEED = 999
N_TR, N_TE = 20, 20
od = load_odours()
P = pn_mean(od.delta, od.set_a)
n_od = P.shape[0]
real_left = real_wiring("left")
n_hid = real_left.W.shape[0]
out = {"seed": SEED, "n_train": N_TR, "n_test": N_TE, "grid": []}
for T in (0.05, 0.1, 0.2, 0.5):
    rng = np.random.default_rng([SEED, int(T * 1000)])
    Xtr, ytr = make_trials(P, N_TR, T, rng)
    Xte, yte = make_trials(P, N_TE, T, rng)
    row = {"T": T}
    for epochs, lr in ((20, 1e-3), (50, 1e-3), (50, 3e-4)):
        t0 = time.time()
        m = MLP(Xtr.shape[1], n_hid, n_od, np.random.default_rng([SEED, 1]), lr=lr)
        m.fit(Xtr / 100.0, ytr, np.arange(n_od), epochs, np.random.default_rng([SEED, 2]))
        acc = float((m.predict(Xte / 100.0, np.arange(n_od)) == yte).mean())
        row[f"mlp_joint_e{epochs}_lr{lr:g}"] = acc
        row[f"mlp_joint_e{epochs}_lr{lr:g}_sec"] = time.time() - t0
        log(f"T={T} MLP joint epochs={epochs} lr={lr:g}: acc {acc:.3f} ({time.time() - t0:.0f} s)")
    uni = control_wiring(real_left, "uniform", np.random.default_rng([SEED, 3]))
    Htr, Hte = kc_code(uni.W, Xtr), kc_code(uni.W, Xte)
    fr = FlyReadout(n_hid, n_od)
    fr.train(Htr, ytr)
    row["fly_uniform_left"] = float((fr.predict(Hte, np.arange(n_od)) == yte).mean())
    log(f"T={T} fly (uniform control, left): acc {row['fly_uniform_left']:.3f}")
    out["grid"].append(row)
    save_json(out, RES / "pilot.json")

# choose T and MLP settings by the rule above
keys = [k for k in out["grid"][0] if k.startswith("mlp_joint") and not k.endswith("_sec")]
best_T = min(out["grid"], key=lambda r: abs(max(r[k] for k in keys) - 0.85))
best_key = max(keys, key=lambda k: best_T[k])
out["chosen"] = {"T": best_T["T"], "mlp": best_key,
                 "mlp_joint_acc": best_T[best_key]}
save_json(out, RES / "pilot.json")
log(f"chosen: {out['chosen']}")

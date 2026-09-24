"""Optional check (S8): split-MNIST, class-incremental, 5 tasks of 2 digits (0/1, 2/3, ...).

Images (pixels / 255, minus the mean training image) go through a FIXED random projection
(Gaussian, seeded) to 55 numbers, one per glomerulus, each scaled to unit variance on the
training images. Then the same models as the odour task: fly model on real / shuffled /
uniform wiring (top 5% KCs, Shen et al. rule; capped and uncapped weights) and the MLP with
the same hidden size (sequential and joint). To keep run time sane: 1,000 training images
per digit (10,000 in all), the full 10,000-image test set; MLP 5 epochs per task (sequential)
or 5 epochs on everything (joint).

Not the same set-up as Shen et al. (they used MNIST + Fashion-MNIST, "MNIST-20", with 84
features from a LeNet5 trained on Japanese characters, and 3,200 KCs sampling 10 inputs
each); the closest published number is their accuracy after the first 5 tasks (= digits
0-9): FlyModel 0.86, plain network 0.19.
Usage: python run_mnist.py [--seeds 5] [--mlp-seeds 3]. Writes results/raw/mnist.csv.
"""
import argparse
import gzip
import time

import numpy as np
import pandas as pd

from common import (MLP, RAW, FlyReadout, all_glomeruli, control_wiring, glomerulus_kc_table,
                    kc_code, log, real_wiring, wait_for_ram)

MN = RAW / "mnist"
PER_DIGIT = 1000
MLP_EPOCHS = 5
TASKS = [(0, 1), (2, 3), (4, 5), (6, 7), (8, 9)]


def read_idx(name):
    with gzip.open(MN / name, "rb") as f:
        data = f.read()
    ndim = data[3]
    dims = [int.from_bytes(data[4 + 4 * i:8 + 4 * i], "big") for i in range(ndim)]
    return np.frombuffer(data, np.uint8, offset=4 + 4 * ndim).reshape(dims)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=5)
    ap.add_argument("--mlp-seeds", type=int, default=3)
    a = ap.parse_args()
    wait_for_ram()
    Xall = read_idx("train-images-idx3-ubyte.gz").reshape(60000, -1).astype(np.float32) / 255
    yall = read_idx("train-labels-idx1-ubyte.gz").astype(int)
    Xte0 = read_idx("t10k-images-idx3-ubyte.gz").reshape(10000, -1).astype(np.float32) / 255
    yte = read_idx("t10k-labels-idx1-ubyte.gz").astype(int)
    table, _ = glomerulus_kc_table()
    gloms = all_glomeruli()
    reals = {s: real_wiring(s, table=table, gloms=gloms) for s in ("left", "right")}
    rows = []
    t0 = time.time()
    for seed in range(a.seeds):
        rng = np.random.default_rng([seed, 9001])
        idx = np.concatenate([rng.choice(np.flatnonzero(yall == d), PER_DIGIT, replace=False)
                              for d in range(10)])
        Xtr0, ytr = Xall[idx], yall[idx]
        mu = Xtr0.mean(0)
        R = rng.standard_normal((784, len(gloms))).astype(np.float32) / np.sqrt(784)
        Ftr, Fte = (Xtr0 - mu) @ R, (Xte0 - mu) @ R
        sd = Ftr.std(0)
        Ftr, Fte = Ftr / sd, Fte / sd
        for si, side in enumerate(("left", "right")):
            real = reals[side]
            wr = np.random.default_rng([seed, 9002, si])
            wirings = [real, control_wiring(real, "shuffled", wr), control_wiring(real, "uniform", wr)]
            for w in wirings:
                Htr, Hte = kc_code(w.W, Ftr), kc_code(w.W, Fte)
                for capname, cap in (("capped", 1.0), ("uncapped", np.inf)):
                    fly = FlyReadout(w.W.shape[0], 10, cap=cap)
                    seen = []
                    for ti, task in enumerate(TASKS):
                        m = np.isin(ytr, task)
                        fly.train(Htr[m], ytr[m])
                        seen += list(task)
                        for d in seen:
                            mt = yte == d
                            acc = float((fly.predict(Hte[mt], seen) == d).mean())
                            rows.append({"seed": seed, "side": side, "model": f"fly_{w.name}_{capname}",
                                         "after_task": ti, "digit": d, "acc": acc, "n": int(mt.sum())})
                    if capname == "capped":
                        rows.append({"seed": seed, "side": side, "model": f"fly_{w.name}_capped",
                                     "after_task": -1, "digit": -1,
                                     "acc": float((fly.W >= 1.0).mean()), "n": 0})  # saturated share
            if seed < a.mlp_seeds:
                n_hid = real.W.shape[0]
                mlp = MLP(Ftr.shape[1], n_hid, 10, np.random.default_rng([seed, 9003, si]))
                fit_rng = np.random.default_rng([seed, 9004, si])
                seen = []
                for ti, task in enumerate(TASKS):
                    seen += list(task)
                    m = np.isin(ytr, task)
                    mlp.fit(Ftr[m], ytr[m], np.array(seen), MLP_EPOCHS, fit_rng)
                    for d in seen:
                        mt = yte == d
                        rows.append({"seed": seed, "side": side, "model": "mlp_seq", "after_task": ti,
                                     "digit": d, "acc": float((mlp.predict(Fte[mt], seen) == d).mean()),
                                     "n": int(mt.sum())})
                mlp = MLP(Ftr.shape[1], n_hid, 10, np.random.default_rng([seed, 9003, si]))
                mlp.fit(Ftr, ytr, np.arange(10), MLP_EPOCHS, np.random.default_rng([seed, 9005, si]))
                for d in range(10):
                    mt = yte == d
                    rows.append({"seed": seed, "side": side, "model": "mlp_joint", "after_task": 4,
                                 "digit": d, "acc": float((mlp.predict(Fte[mt], np.arange(10)) == d).mean()),
                                 "n": int(mt.sum())})
        pd.DataFrame(rows).to_csv(RAW / "mnist.csv", index=False)
        log(f"seed {seed} done ({time.time() - t0:.0f} s)")
    log("done")


if __name__ == "__main__":
    main()

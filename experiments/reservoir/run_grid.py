"""Main sweep: every network x seed x (rho, a); all readouts; all tasks.

One batch = one network and one seed, with all 16 (rho, a) settings run
side by side (they share the matrix). Results are appended to
results/grid.csv after every batch, so a restart skips finished batches.

Run: .venv\\Scripts\\python.exe experiments\\reservoir\\run_grid.py [--quick]
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "2"
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

RHOS = [0.5, 0.65, 0.8, 0.95, 1.05, 1.2, 1.35, 1.5]
LEAKS = [0.3, 1.0]
T_WASH, T_TR, T_VA, T_TE = 200, 1000, 400, 600   # amended 21:55 for compute (was 200/1500/500/800)
NS = [10, 30, 100, 300, 1000, 3000]
NOISE_SD = 0.01
POOL = 3000
ORDER = [("real_fix", 0), ("shuffle", 0), ("er", 0),
         ("real_fix", 1), ("shuffle", 1), ("er", 1),
         ("real_fix", 2), ("shuffle", 2), ("er", 2),
         ("real_none", 0), ("real_none", 1), ("real_none", 2)]

ap = argparse.ArgumentParser()
ap.add_argument("--quick", action="store_true", help="short debug run, writes to raw/quick_*")
ap.add_argument("--only", default="", help="comma list of network:seed to run")
ap.add_argument("--samegain", action="store_true",
                help="EXPLORATORY (not pre-registered): divide every network by the same "
                     "number (the Erdos-Renyi seed-0 radius) instead of its own radius")
ap.add_argument("--lite", action="store_true", help="only the primary readouts (all DN, 1,000 random)")
ap.add_argument("--highgain", action="store_true",
                help="EXPLORATORY (added after the main run): rho 2-10 instead of 0.5-1.5")
args = ap.parse_args()
if args.quick:
    T_WASH, T_TR, T_VA, T_TE = 100, 300, 100, 200
T = T_WASH + T_TR + T_VA + T_TE
tag = "quick_" if args.quick else ("samegain_" if args.samegain else ("noself_" if "noself" in args.only else ""))
if args.highgain:
    RHOS = [2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0]
    tag = "highgain_"
OUT = (lib.RAW if args.quick else lib.RESULTS) / f"{tag}grid.csv"
CURVES = lib.RAW / f"{tag}mc_curves.csv"
RADII = lib.RESULTS / "radii.json"
LOG = lib.RAW / f"{tag}run_grid.log"


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def main():
    t_start = time.perf_counter()
    root_ids, pre, post, w, rep = lib.load_edges("al_ln_literature")
    n = root_ids.size
    base = {"real_fix": (pre, post, w)}
    lab = lib.labels(root_ids)
    sc = lab.super_class.to_numpy()
    sens = np.flatnonzero(sc == "sensory")
    dn = np.flatnonzero(sc == "descending")
    nonsens = np.flatnonzero(sc != "sensory")
    log(f"n={n} edges={pre.size:,} sensory={sens.size} descending={dn.size}; {rep.notes}")
    radii = json.load(open(RADII)) if RADII.exists() else {}
    done = set()
    if OUT.exists():
        d = pd.read_csv(OUT, usecols=["network", "seed"])
        done = set(zip(d.network, d.seed))
    order = ORDER
    if args.only:
        want = [tuple(x.split(":")) for x in args.only.split(",")]
        order = [(k, int(s)) for k, s in want]
    if args.quick:
        order = order[:3]

    idx_tr = np.arange(T_WASH, T_WASH + T_TR)
    idx_va = np.arange(T_WASH + T_TR, T_WASH + T_TR + T_VA)
    idx_te = np.arange(T_WASH + T_TR + T_VA, T)
    rho_col = np.tile(RHOS, len(LEAKS)).astype(np.float32)
    a_col = np.repeat(LEAKS, len(RHOS)).astype(np.float32)
    B = rho_col.size

    for kind, seed in order:
        if (kind, seed) in done:
            log(f"skip {kind} seed {seed} (done)")
            continue
        free = lib.wait_for_ram(1.5, log=log)
        t0 = time.perf_counter()
        # --- the network
        if kind == "real_fix":
            p, q, ww = base["real_fix"]
        elif kind == "real_none":
            if "real_none" not in base:
                _, p0, q0, w0, _ = lib.load_edges("none")
                base["real_none"] = (p0, q0, w0)
            p, q, ww = base["real_none"]
        elif kind == "shuffle":
            p, q, ww = lib.degree_shuffle(pre, post, w, seed)
        elif kind == "er":
            p, q, ww = lib.erdos_renyi(pre, post, w, n, seed)
        elif kind == "shuffle_noself":     # sensitivity check, added after the main run
            p, q, ww = lib.degree_shuffle(pre, post, w, seed, no_self=True)
        elif kind == "er_noself":
            p, q, ww = lib.erdos_renyi(pre, post, w, n, seed, no_self=True)
        else:
            raise ValueError(kind)
        est = lib.edge_stats(p, q, n)
        m = lib.to_csr(p, q, ww, n)
        key = kind if kind.startswith("real") else f"{kind}_{seed}"
        if key not in radii:
            r, vals, secs = lib.spectral_radius(m, tol=1e-6)
            top = sorted(vals, key=lambda z: -abs(z))
            radii[key] = {"radius": r, "top6": [[float(z.real), float(z.imag)] for z in top],
                          "seconds": secs, **est, "nnz_after_merging_duplicates": int(m.nnz)}
            json.dump(radii, open(RADII, "w"), indent=1)
        r = radii[key]["radius"]
        if args.samegain:
            r = radii["er_0"]["radius"]
        m.data /= np.float32(r)
        bm = lib.BlockedMatrix(m, block_cols=32768)
        del m
        if kind in ("shuffle", "er", "shuffle_noself", "er_noself"):
            del p, q, ww
        # --- this seed's input, input weights and readout pool (same for every network)
        u, y = lib.make_input(T, seed)
        rs = np.random.default_rng(np.random.SeedSequence([seed, 11]))
        signs = np.where(rs.random(sens.size) < 0.5, -1.0, 1.0).astype(np.float32)
        rp = np.random.default_rng(np.random.SeedSequence([seed, 13]))
        pool = rp.choice(nonsens, POOL, replace=False)
        rec_idx = np.concatenate([dn, pool]).astype(np.int64)
        U = np.repeat(u[:, None], B, 1).astype(np.float32)
        win = np.repeat(signs[:, None], B, 1)
        t1 = time.perf_counter()
        rec = bm.run(U, sens, win, rho_col, a_col, rec_idx)      # (T, n_rec, B)
        t_dyn = time.perf_counter() - t1
        del bm
        Ytr, Yva, Yte = (lib.targets(u, y, ix) for ix in (idx_tr, idx_va, idx_te))
        rows, curves = [], []
        t2 = time.perf_counter()
        for col in range(B):
            F = np.ascontiguousarray(rec[:, :, col])
            post_w = F[T_WASH:]
            sd = post_w.std(0)
            stat = {"dn_median_sd": float(np.median(sd[:dn.size])),
                    "dn_frac_sd_gt_noise": float((sd[:dn.size] > NOISE_SD).mean()),
                    "pool_median_sd": float(np.median(sd[dn.size:])),
                    "pool_frac_sd_gt_noise": float((sd[dn.size:] > NOISE_SD).mean()),
                    "pool_frac_saturated": float((np.abs(post_w[:, dn.size:]) > 0.9).mean()),
                    "pool_mean_abs": float(np.abs(post_w[:, dn.size:]).mean())}
            rn = np.random.default_rng(np.random.SeedSequence([seed, 17, col]))
            noise = rn.normal(0.0, NOISE_SD, F.shape).astype(np.float32)
            for noisy in (False, True):
                G = F + noise if noisy else F
                sets = [("DN", dn.size, slice(0, dn.size))]
                sets += [("rand", N, slice(dn.size, dn.size + N)) for N in (NS if not args.lite else [1000])]
                for name, N, sl in sets:
                    res = lib.ridge_scores(G[idx_tr, sl], Ytr, G[idx_va, sl], Yva,
                                           G[idx_te, sl], Yte)
                    row = {"network": kind, "seed": seed, "rho": float(rho_col[col]),
                           "leak": float(a_col[col]), "readout": name, "N": N,
                           "noise": NOISE_SD if noisy else 0.0,
                           **{k: v for k, v in res.items() if k != "mc_curve"}, **stat}
                    rows.append(row)
                    if not noisy and (name == "DN" or N in (1000, 3000)):
                        curves.append([kind, seed, float(rho_col[col]), float(a_col[col]), name, N]
                                      + list(np.round(res["mc_curve"], 5)))
            del F, noise
        t_read = time.perf_counter() - t2
        del rec
        df = pd.DataFrame(rows)
        df["radius"] = r
        df.to_csv(OUT, mode="a", header=not OUT.exists(), index=False)
        cdf = pd.DataFrame(curves, columns=["network", "seed", "rho", "leak", "readout", "N"]
                           + [f"k{k}" for k in range(lib.N_MC)])
        cdf.to_csv(CURVES, mode="a", header=not CURVES.exists(), index=False)
        best = df[(df.readout == "rand") & (df.N == 1000) & (df.noise == 0)]
        log(f"{kind} seed {seed}: radius {r:.1f}; dynamics {t_dyn:.0f}s, readouts {t_read:.0f}s, "
            f"total {time.perf_counter()-t0:.0f}s (free RAM at start {free:.1f} GB). "
            f"rand1000 clean: best MC {best.mc.max():.2f}, best NARMA {best.narma_nrmse.min():.3f}, "
            f"best XOR {best.xor_acc.max():.3f}")
    log(f"all done in {time.perf_counter()-t_start:.0f}s")


if __name__ == "__main__":
    main()

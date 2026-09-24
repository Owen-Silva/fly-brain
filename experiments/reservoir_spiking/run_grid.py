"""Main sweep: spiking whole-brain reservoir, real wiring vs two random controls.

Usage (from this folder):
  python run_grid.py --tag main                        # the pre-registered grid
  python run_grid.py --tag wsyn --wsyn 0.8 1.2 --peaks 150   # +/-20% check
  python run_grid.py --tag quick --quick --nets real --seeds 0 --peaks 50   # debug

One row per (network, seed, peak, w_syn factor, readout, N, noise) goes to
results/<tag>_grid.csv; raw spike-count features go to results/raw/.
"""
import argparse
import gc
import json
import time

import numpy as np
import pandas as pd

import lib_spk as L

R = L.rlib
ap = argparse.ArgumentParser()
ap.add_argument("--tag", default="main")
ap.add_argument("--nets", nargs="+", default=["real", "shuffle", "er"])
ap.add_argument("--seeds", nargs="+", type=int, default=[0, 1, 2])
ap.add_argument("--peaks", nargs="+", type=float, default=[50.0, 150.0, 400.0])
ap.add_argument("--wsyn", nargs="+", type=float, default=[1.0])
ap.add_argument("--quick", action="store_true")
ap.add_argument("--bin", type=float, default=20.0,
                help="bin width in ms (20 = pre-registered; others exploratory)")
args = ap.parse_args()
L.set_bin(args.bin)

# Timeline in bins (the same split as the rate lane after its amendment)
T_TR, T_VA, T_TE = (1000, 400, 600) if not args.quick else (200, 80, 120)
T_KEEP = T_TR + T_VA + T_TE
T_PRE = 110          # history needed by the targets (memory delays up to 100)
W = int(round(500 / args.bin))      # washout bins per segment (500 ms; 25 at 20 ms)
SEG = 500 if not args.quick else 200   # kept bins per segment
T_OFF = int(round(500 / args.bin))  # bins with input off at the very end (runaway test)
LATE0 = int(round(200 / args.bin))  # runaway window starts 200 ms after input off
NS = [10, 30, 100, 300, 1000]
POOL = 1000
W_SYN0 = 0.275
NAME = {"real": "real_fix", "shuffle": "shuffle", "er": "er"}

OUT = L.RESULTS / f"{args.tag}_grid.csv"
ACT = L.RESULTS / f"{args.tag}_activity.csv"
LOG = L.RAW / f"{args.tag}_run_grid.log"
CURVES = L.RAW / f"{args.tag}_mc_curves.csv"
L.RAW.mkdir(parents=True, exist_ok=True)


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def done_keys():
    if not ACT.exists():
        return set()
    a = pd.read_csv(ACT)
    return {(r.network, int(r.seed), float(r.peak_hz), float(r.wsyn)) for r in a.itertuples()}


def run_one(brain, kind, seed, peak, wsyn, u, sens, readout_idx, col_of):
    signs = L.input_signs(sens.size, seed)
    params = {"w_syn": W_SYN0 * wsyn}
    n_cols = readout_idx.size
    counts, pops, totals = [], [], np.zeros(brain.n_neurons, np.int64)
    tail_pop = None
    wall = 0.0
    n_sp = 0
    starts = list(range(T_PRE, T_PRE + T_KEEP, SEG))
    for si, a in enumerate(starts):
        b = min(a + SEG, T_PRE + T_KEEP)
        u_seg = u[a - W:b].astype(float)
        last = si == len(starts) - 1
        if last:
            u_seg = np.concatenate([u_seg, np.full(T_OFF, np.nan)])
        rng = np.random.default_rng(np.random.SeedSequence(
            [seed, 31, int(peak), int(round(wsyn * 100)), si]))
        out = L.simulate(brain, u_seg, signs, sens, peak, rng, col_of, n_cols,
                         keep_from=W, keep_to=W + (b - a), params=params)
        keep = slice(W, W + (b - a))
        counts.append(out["counts"][keep])
        pops.append(out["pop"])
        if last:
            tail_pop = out["pop"][W + (b - a):]
        totals += out["totals"]
        wall += out["wall_s"]
        n_sp += out["n_spikes"]
    return np.concatenate(counts), pops, totals, tail_pop, wall, n_sp


def activity(totals, pops, tail_pop, sens_mask, dn, kept_bins):
    ns = ~sens_mask
    dur_s = kept_bins * L.BIN_MS * 1e-3
    rate = totals[ns] / dur_s
    pop_on = np.concatenate([p[W:] for p in pops[:-1]] + [pops[-1][W:-T_OFF]])
    pop_on_hz = pop_on.mean() / ns.sum() / (L.BIN_MS * 1e-3)
    late = tail_pop[LATE0:]                      # 200-500 ms after input off
    late_hz = late.mean() / ns.sum() / (L.BIN_MS * 1e-3)
    return {"frac_active": float((rate > 0).mean()),
            "mean_rate_hz": float(rate.mean()),
            "frac_gt_50hz": float((rate > 50).mean()),
            "frac_gt_100hz": float((rate > 100).mean()),
            "max_rate_hz": float(rate.max()),
            "dn_frac_active": float((totals[dn] > 0).mean()),
            "dn_mean_rate_hz": float((totals[dn] / dur_s).mean()),
            "pop_on_hz": float(pop_on_hz), "pop_off_late_hz": float(late_hz),
            "tail_first_bins_hz": ";".join(f"{x / ns.sum() / (L.BIN_MS * 1e-3):.3f}"
                                           for x in tail_pop[:10]),
            "runaway": bool(late_hz >= 0.1 * pop_on_hz and late_hz > 0)}


def main():
    free = R.wait_for_ram(1.5, log=log)
    log(f"start tag={args.tag} nets={args.nets} seeds={args.seeds} peaks={args.peaks} "
        f"wsyn={args.wsyn} quick={args.quick} free={free:.2f}GB fix={L.FIX}")
    root_ids, pre, post, signed, rep = L.real_arrays()
    arrays = (root_ids, pre, post, signed)
    n = len(root_ids)
    lab = R.labels(root_ids)
    sc = lab.super_class.to_numpy()
    sens = np.flatnonzero(sc == "sensory")
    dn = np.flatnonzero(sc == "descending")
    nonsens = np.flatnonzero(sc != "sensory")
    sens_mask = np.zeros(n, bool)
    sens_mask[sens] = True
    log(f"n={n} edges={pre.size:,} sensory={sens.size} descending={dn.size}")
    done = done_keys()
    for seed in args.seeds:
        u, y = R.make_input(T_PRE + T_KEEP, seed)
        pool = np.random.default_rng(np.random.SeedSequence([seed, 3])).choice(
            nonsens, POOL, replace=False)
        readout_idx = np.unique(np.concatenate([dn, pool]))
        col_of = np.full(n, -1, np.int64)
        col_of[readout_idx] = np.arange(readout_idx.size)
        dn_cols = col_of[dn]
        pool_cols = col_of[pool]
        idx = np.arange(T_PRE, T_PRE + T_KEEP)
        Y = R.targets(u, y, idx)
        tr, va, te = slice(0, T_TR), slice(T_TR, T_TR + T_VA), slice(T_TR + T_VA, T_KEEP)
        for kind in args.nets:
            todo = [(pk, ws) for ws in args.wsyn for pk in args.peaks
                    if (NAME[kind], seed, float(pk), float(ws)) not in done]
            if not todo:
                continue
            R.wait_for_ram(1.5, log=log)
            t0 = time.perf_counter()
            brain = L.make_brain(kind, seed, arrays)
            log(f"{kind} s{seed}: built in {time.perf_counter() - t0:.1f}s "
                f"({brain.n_connections:,} connections)")
            for pk, ws in todo:
                R.wait_for_ram(1.5, log=log)
                t1 = time.perf_counter()
                X, pops, totals, tail_pop, wall, n_sp = run_one(
                    brain, kind, seed, pk, ws, u, sens, readout_idx, col_of)
                act = activity(totals, pops, tail_pop, sens_mask, dn, T_KEEP)
                np.savez_compressed(
                    L.RAW / f"{args.tag}_{NAME[kind]}_s{seed}_p{int(pk)}_w{int(round(ws * 100))}.npz",
                    X=X, pool=pool, dn=dn, readout_idx=readout_idx, u=u,
                    pop=np.concatenate(pops), totals=totals.astype(np.int32))
                rows, curves = [], []
                feats = [("DN", dn.size, X[:, dn_cols])] + \
                        [("rand", N, X[:, pool_cols[:N]]) for N in NS]
                for ro, N, F in feats:
                    for noise in (0, 1):
                        Fx = L.noisy_counts(F, seed * 1000 + N) if noise else F
                        Fx = Fx.astype(np.float64)
                        s = R.ridge_scores(Fx[tr], Y[tr], Fx[va], Y[va], Fx[te], Y[te])
                        rows.append({"network": NAME[kind], "seed": seed, "peak_hz": pk,
                                     "wsyn": ws, "readout": ro, "N": N, "noise": noise,
                                     **{k: s[k] for k in ("mc", "narma_nrmse", "narma_lag",
                                                          "xor_acc", "xor_delay", "mc_val",
                                                          "narma_val", "xor_val")},
                                     "feat_frac_nonzero_cols": float((F.sum(0) > 0).mean()),
                                     "feat_mean_count": float(F.mean())})
                        curves.append([NAME[kind], seed, pk, ws, ro, N, noise] + list(s["mc_curve"]))
                df = pd.DataFrame(rows)
                df.to_csv(OUT, mode="a", header=not OUT.exists(), index=False)
                pd.DataFrame(curves).to_csv(CURVES, mode="a", header=False, index=False)
                arow = {"network": NAME[kind], "seed": seed, "peak_hz": pk, "wsyn": ws,
                        **act, "sim_wall_s": wall, "total_wall_s": time.perf_counter() - t1,
                        "n_spikes_incl_input": n_sp}
                pd.DataFrame([arow]).to_csv(ACT, mode="a", header=not ACT.exists(), index=False)
                d0 = df[(df.readout == "DN") & (df.noise == 0)].iloc[0]
                r1 = df[(df.readout == "rand") & (df.N == 1000) & (df.noise == 0)].iloc[0]
                log(f"{kind} s{seed} peak={pk:g} wsyn={ws:g}: sim {wall:.0f}s total "
                    f"{time.perf_counter() - t1:.0f}s | active {act['frac_active']:.3f} "
                    f"rate {act['mean_rate_hz']:.2f}Hz DNact {act['dn_frac_active']:.2f} "
                    f"runaway={act['runaway']} | DN mc {d0.mc:.2f} narma {d0.narma_nrmse:.3f} "
                    f"xor {d0.xor_acc:.3f} | R1000 mc {r1.mc:.2f} narma {r1.narma_nrmse:.3f} "
                    f"xor {r1.xor_acc:.3f}")
            del brain
            gc.collect()
    log("done")


if __name__ == "__main__":
    main()

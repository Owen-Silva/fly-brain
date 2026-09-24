"""Time one short segment per network and look at activity (debug / budget).

Usage: python experiments/reservoir_spiking/timing.py [peak_hz ...]
Runs 40 bins (800 ms): 25 bins with input, then 15 bins with input off.
"""
import gc
import sys
import time

import numpy as np

import lib_spk as L

peaks = [float(a) for a in sys.argv[1:] if not a.startswith("--")] or [100.0]
nets = [("real", 0), ("shuffle", 0), ("er", 0)]
if "--real-only" in sys.argv:
    nets = nets[:1]

free = L.rlib.wait_for_ram(1.5)
print(f"free RAM {free:.2f} GB", flush=True)
t0 = time.perf_counter()
root_ids, pre, post, signed, rep = L.real_arrays()
arrays = (root_ids, pre, post, signed)
lab = L.rlib.labels(root_ids)
sc = lab.super_class.to_numpy()
sens = np.flatnonzero(sc == "sensory")
dn = np.flatnonzero(sc == "descending")
print(f"load {time.perf_counter()-t0:.1f}s  n={len(root_ids)} edges={pre.size:,} "
      f"sensory={sens.size} dn={dn.size}", flush=True)
col_of = np.full(len(root_ids), -1, np.int64)
col_of[dn] = np.arange(dn.size)
u = np.random.default_rng(0).uniform(0, 0.5, 40)
u[25:] = np.nan
for kind, seed in nets:
    L.rlib.wait_for_ram(1.5)
    t1 = time.perf_counter()
    brain = L.make_brain(kind, seed, arrays)
    tb = time.perf_counter() - t1
    for pk in peaks:
        rng = np.random.default_rng(1)
        out = L.simulate(brain, u, L.input_signs(sens.size, 0), sens, pk, rng,
                         col_of, dn.size, keep_from=0)
        nonsens = np.setdiff1d(np.arange(len(root_ids)), sens)
        tot = out["totals"][nonsens]
        pop_hz = out["pop"] / nonsens.size / (L.BIN_MS * 1e-3)
        print(f"{kind} s{seed} peak={pk:g}Hz build {tb:.1f}s  sim {out['wall_s']:.1f}s "
              f"for 0.8 s  spikes={out['n_spikes']:,}  active={np.mean(tot > 0):.3f} "
              f"DN active={np.mean(out['counts'].sum(0) > 0):.3f}", flush=True)
        print("  pop rate Hz per bin:", " ".join(f"{x:.1f}" for x in pop_hz), flush=True)
    del brain
    gc.collect()

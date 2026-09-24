"""Time one reservoir run before sweeping (and check the matrix build).

Run: .venv\\Scripts\\python.exe experiments\\reservoir\\timing.py
"""
import os
for _v in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "NUMBA_NUM_THREADS"):
    os.environ[_v] = "2"
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

t0 = time.perf_counter()
print(f"free RAM {lib.wait_for_ram(1.5):.2f} GB", flush=True)
root_ids, pre, post, w, rep = lib.load_edges("al_ln_literature")
n = root_ids.size
print(f"edges loaded: {pre.size:,} ({time.perf_counter()-t0:.1f}s); fix: {rep.notes}", flush=True)

# --- check against the engine's own arrays (build_brain -> FastBrain.from_arrays)
from sim.sign_fixes import build_brain  # noqa: E402
brain = build_brain("al_ln_literature")
m = lib.to_csr(pre, post, w, n)
assert m.nnz == brain.n_connections == pre.size, (m.nnz, brain.n_connections)
rng = np.random.default_rng(0)
for j in rng.choice(n, 300, replace=False):          # j = presynaptic neuron
    tg = brain._post[brain._indptr[j]:brain._indptr[j + 1]]
    ct = brain._count[brain._indptr[j]:brain._indptr[j + 1]]
    col = m[:, j].toarray().ravel()
    assert np.array_equal(np.flatnonzero(col), np.sort(tg)), j
    assert np.array_equal(col[tg], ct.astype(np.float32)), j
print("matrix matches the engine's connection list for 300 random neurons", flush=True)
del brain

lab = lib.labels(root_ids)
sens = np.flatnonzero(lab.super_class.to_numpy() == "sensory")
dn = np.flatnonzero(lab.super_class.to_numpy() == "descending")
print(f"sensory {sens.size}, descending {dn.size}", flush=True)

r, vals, secs = lib.spectral_radius(m)
print(f"spectral radius {r:.4f} in {secs:.1f}s; top |eig| {np.sort(np.abs(vals))[::-1][:6].round(3)}",
      flush=True)
m.data /= np.float32(r)

T = 60
u = np.random.default_rng(1).uniform(0, 0.5, T)
out = {}
for B in (1, 5, 15):
    U = np.repeat(u[:, None], B, 1)
    win = np.where(rng.random((sens.size, B)) < 0.5, -1.0, 1.0)
    rho = np.linspace(0.5, 1.5, B)
    a = np.full(B, 0.5)
    rec_idx = np.concatenate([dn, rng.choice(n, 3000, replace=False)])
    lib.esn_run(m, U[:3], sens, win, rho, a, rec_idx)     # compile / warm up
    t1 = time.perf_counter()
    rec = lib.esn_run(m, U, sens, win, rho, a, rec_idx)
    dt = (time.perf_counter() - t1) / T
    out[B] = dt
    print(f"B={B:2d}: {dt*1e3:.1f} ms per step ({dt/B*1e3:.2f} ms per run-step); "
          f"final mean|x| rec {np.abs(rec[-1]).mean(0).round(4)[:5]}", flush=True)
json.dump({"radius": r, "ms_per_step": {str(k): v * 1e3 for k, v in out.items()}},
          open(lib.RAW / "timing.json", "w"), indent=1)
print(f"total {time.perf_counter()-t0:.0f}s, free RAM now {lib.mem_free_gb():.2f} GB")

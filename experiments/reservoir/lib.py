"""Helpers for the connectome-as-reservoir lane (experiments/reservoir).

Plain English
-------------
We treat the fly's whole wiring diagram as a fixed "reservoir": a big
recurrent network whose connections are never changed. A signal u(t) is fed
into the sensory neurons, the network's activity echoes it around, and only a
simple linear readout (ridge regression) is trained to turn the activity of a
few read-out neurons into an answer.

The matrix W is built exactly as the fast engine builds its connection list
(sim/sign_fixes.build_brain -> FastBrain.from_arrays): one entry per
connection, weight = signed synapse count (the engine multiplies by w_syn,
which does not matter here because W is rescaled to spectral radius 1).
W[post, pre] = signed count, so (W @ x)[i] is the input to neuron i.

Rate model (echo-state network):
    x(t) = (1 - a) x(t-1) + a tanh(rho * W x(t-1) + W_in u(t))
with W scaled to spectral radius 1, so rho is the spectral radius used.

Nothing in sim/, app/, tests/ or data/ is modified; the connection list is
read with sim.sign_fixes and changed only in memory.
"""
from __future__ import annotations

import math
import sys
import time
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

RESULTS = HERE / "results"
RAW = RESULTS / "raw"
LABELS_630 = ROOT / "data" / "cache" / "connectome_630_neurons.parquet"


# ---------------------------------------------------------------------------
# Connection lists
# ---------------------------------------------------------------------------
def load_edges(fix="al_ln_literature"):
    """(root_ids, pre, post, w, report) for snapshot 630 with ``fix`` applied,
    exactly as sim.sign_fixes.build_brain feeds FastBrain.from_arrays."""
    from sim.sign_fixes import apply_fix, load_reference_arrays
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre2, post2, signed2, rep = apply_fix(fix, root_ids, pre, post, signed)
    del pre, post, signed
    return (np.asarray(root_ids, np.int64), pre2.astype(np.int32),
            post2.astype(np.int32), signed2.astype(np.float32), rep)


def labels(root_ids):
    """super_class per model neuron, in the model's row order."""
    lab = pd.read_parquet(LABELS_630, columns=["root_id", "super_class", "cell_class"])
    lab = lab.set_index("root_id").reindex(np.asarray(root_ids, np.int64)).reset_index()
    for c in ("super_class", "cell_class"):
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "").astype(str)
    return lab


def degree_shuffle(pre, post, w, seed, no_self=False):
    """Control (a): permute the target column of the edge list. Every neuron
    keeps its out-degree, its outgoing weights and signs (so Dale's law), and
    its in-degree; who connects to whom is randomised.
    no_self=True (added after the main run, as a sensitivity check): any
    connection that landed on its own sender swaps targets with a random
    other connection, until none is left (degrees are still kept)."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 101]))
    q = rng.permutation(post).astype(np.int32)
    if no_self:
        for _ in range(1000):
            bad = np.flatnonzero(pre == q)
            if bad.size == 0:
                break
            other = rng.integers(0, q.size, bad.size)
            tmp = q[bad].copy()
            q[bad] = q[other]
            q[other] = tmp
        assert not (pre == q).any()
    return pre, q, w


def erdos_renyi(pre, post, w, n, seed, no_self=False):
    """Control (b): same number of edges, same weight values, sources and
    targets drawn uniformly at random (Erdos-Renyi).
    no_self=True (sensitivity check): self-connections get a new random target."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 202]))
    e = pre.size
    pre_r = rng.integers(0, n, e, dtype=np.int64).astype(np.int32)
    post_r = rng.integers(0, n, e, dtype=np.int64).astype(np.int32)
    w_r = rng.permutation(w)
    if no_self:
        rng2 = np.random.default_rng(np.random.SeedSequence([seed, 203]))
        while True:
            bad = np.flatnonzero(pre_r == post_r)
            if bad.size == 0:
                break
            post_r[bad] = rng2.integers(0, n, bad.size)
    return pre_r, post_r, w_r


def edge_stats(pre, post, n):
    key = pre.astype(np.int64) * n + post
    return {"edges": int(pre.size), "self_loops": int((pre == post).sum()),
            "duplicate_edges": int(pre.size - np.unique(key).size)}


def to_csr(pre, post, w, n):
    """CSR (rows = targets) with duplicates summed. float32 data, int32 indices."""
    import scipy.sparse as sp
    m = sp.csr_matrix((w.astype(np.float32), (post.astype(np.int32), pre.astype(np.int32))),
                      shape=(n, n))
    m.sum_duplicates()
    m.indices = m.indices.astype(np.int32)
    m.indptr = m.indptr.astype(np.int64)
    return m


def spectral_radius(m, tol=1e-6, k=6):
    """Largest |eigenvalue| of a sparse matrix (ARPACK, largest magnitude).
    Returns (radius, the k eigenvalues found, seconds)."""
    from scipy.sparse.linalg import eigs
    t0 = time.perf_counter()
    m64 = m.astype(np.float64)
    vals = eigs(m64, k=k, which="LM", tol=tol, ncv=max(3 * k, 40), maxiter=20000,
                return_eigenvectors=False)
    del m64
    return float(np.abs(vals).max()), vals, time.perf_counter() - t0


# ---------------------------------------------------------------------------
# The echo-state network run (numba, parallel over rows)
# ---------------------------------------------------------------------------
def balanced_chunks(indptr, n_chunks):
    """Row boundaries so each chunk holds about the same number of connections."""
    nnz = indptr[-1]
    targets = np.linspace(0, nnz, n_chunks + 1)
    bounds = np.searchsorted(indptr, targets).astype(np.int64)
    bounds[0], bounds[-1] = 0, indptr.size - 1
    return np.unique(bounds)


@nb.njit(parallel=True, fastmath=True, cache=True)
def _esn_run(indptr, indices, data, bounds, U, win_idx, win_val, rho, a, rec_idx):
    """Run B echo-state networks that share one matrix (one per column).

    indptr/indices/data: CSR of W (spectral radius 1), rows = targets.
    U: (T, B) input per step and column. win_idx: input neurons;
    win_val: (n_in, B) input weights. rho, a: (B,) per column.
    Returns rec (T, n_rec, B): the states of rec_idx after each step.
    """
    n = indptr.size - 1
    T, B = U.shape
    X = np.zeros((n, B), np.float32)
    Xn = np.zeros((n, B), np.float32)
    drive = np.zeros((n, B), np.float32)
    rec = np.empty((T, rec_idx.size, B), np.float32)
    n_chunks = bounds.size - 1
    for t in range(T):
        for q in range(win_idx.size):
            i = win_idx[q]
            for b in range(B):
                drive[i, b] = win_val[q, b] * U[t, b]
        for c in nb.prange(n_chunks):
            acc = np.empty(B, np.float32)
            for i in range(bounds[c], bounds[c + 1]):
                for b in range(B):
                    acc[b] = 0.0
                for k in range(indptr[i], indptr[i + 1]):
                    j = indices[k]
                    wk = data[k]
                    for b in range(B):
                        acc[b] += wk * X[j, b]
                for b in range(B):
                    Xn[i, b] = (1.0 - a[b]) * X[i, b] + a[b] * math.tanh(rho[b] * acc[b] + drive[i, b])
        X, Xn = Xn, X
        for r in range(rec_idx.size):
            for b in range(B):
                rec[t, r, b] = X[rec_idx[r], b]
    return rec


def esn_run(m, U, win_idx, win_val, rho, a, rec_idx, n_chunks=256):
    """Python wrapper; m is a CSR matrix already scaled to spectral radius 1.
    (Reference version; esn_run_blocked is the fast one used for the sweep.)"""
    bounds = balanced_chunks(m.indptr, n_chunks)
    return _esn_run(m.indptr, m.indices, m.data.astype(np.float32, copy=False), bounds,
                    np.ascontiguousarray(U, np.float32), np.asarray(win_idx, np.int64),
                    np.ascontiguousarray(win_val, np.float32), np.asarray(rho, np.float32),
                    np.asarray(a, np.float32), np.asarray(rec_idx, np.int64))


@nb.njit(inline="always", fastmath=True)
def fast_tanh(x):
    """tanh for float32 as a clamped rational function (the coefficients of
    Eigen's generic_fast_tanh_float); max error about 1e-7, checked in
    check_fast_tanh()."""
    if x > 7.90531110763549805:
        x = 7.90531110763549805
    elif x < -7.90531110763549805:
        x = -7.90531110763549805
    x2 = x * x
    p = x2 * -2.76076847742355e-16 + 2.00018790482477e-13
    p = x2 * p + -8.60467152213735e-11
    p = x2 * p + 5.12229709037114e-08
    p = x2 * p + 1.48572235717979e-05
    p = x2 * p + 6.37261928875436e-04
    p = x2 * p + 4.89352455891786e-03
    p = x * p
    q = x2 * 1.19825839466702e-06 + 1.18534705686654e-04
    q = x2 * q + 2.26843463243900e-03
    q = x2 * q + 4.89352518554385e-03
    return p / q


@nb.njit(fastmath=True)
def _tanh_vec(x):
    out = np.empty_like(x)
    for i in range(x.size):
        out[i] = fast_tanh(x[i])
    return out


def check_fast_tanh():
    x = np.linspace(-12, 12, 2_000_001)
    return float(np.abs(_tanh_vec(x) - np.tanh(x)).max())


def column_blocks(m, block_cols):
    """Split CSR m into column blocks (cache blocking): returns
    (indptrs (n_blocks, n+1), indices, data, bounds (n_blocks, n_chunks+1))."""
    n = m.shape[0]
    starts = list(range(0, m.shape[1], block_cols))
    indptrs, inds, dats = [], [], []
    off = 0
    for c0 in starts:
        sub = m[:, c0:c0 + block_cols].tocsr()
        sub.sort_indices()
        indptrs.append(sub.indptr.astype(np.int64) + off)
        inds.append((sub.indices + c0).astype(np.int32))
        dats.append(sub.data.astype(np.float32))
        off += sub.nnz
    return (np.stack(indptrs), np.concatenate(inds), np.concatenate(dats))


def block_bounds(indptrs, n_chunks):
    out = np.zeros((indptrs.shape[0], n_chunks + 1), np.int64)
    for b in range(indptrs.shape[0]):
        ip = indptrs[b] - indptrs[b, 0]
        tg = np.linspace(0, ip[-1], n_chunks + 1)
        bd = np.searchsorted(ip, tg).astype(np.int64)
        bd[0], bd[-1] = 0, ip.size - 1
        out[b] = np.maximum.accumulate(bd)
    return out


@nb.njit(parallel=True, fastmath=True, cache=True)
def _esn_run_blocked(indptrs, indices, data, bounds, rbounds, U, win_idx, win_val,
                     rho, a, rec_idx):
    """Same maths as _esn_run, but the matrix product is done one column
    block at a time so the source states it reads stay in the CPU cache."""
    n = indptrs.shape[1] - 1
    nblk = indptrs.shape[0]
    nch = bounds.shape[1] - 1
    nrch = rbounds.size - 1
    T, B = U.shape
    X = np.zeros((n, B), np.float32)
    Xn = np.zeros((n, B), np.float32)
    acc = np.zeros((n, B), np.float32)
    drive = np.zeros((n, B), np.float32)
    rec = np.empty((T, rec_idx.size, B), np.float32)
    for t in range(T):
        for q in range(win_idx.size):
            i = win_idx[q]
            for b in range(B):
                drive[i, b] = win_val[q, b] * U[t, b]
        for c in nb.prange(nrch):
            for i in range(rbounds[c], rbounds[c + 1]):
                for b in range(B):
                    acc[i, b] = 0.0
        for blk in range(nblk):
            for c in nb.prange(nch):
                for i in range(bounds[blk, c], bounds[blk, c + 1]):
                    k0 = indptrs[blk, i]
                    k1 = indptrs[blk, i + 1]
                    if k1 > k0:
                        for k in range(k0, k1):
                            j = indices[k]
                            wk = data[k]
                            for b in range(B):
                                acc[i, b] += wk * X[j, b]
        for c in nb.prange(nrch):
            for i in range(rbounds[c], rbounds[c + 1]):
                for b in range(B):
                    Xn[i, b] = (1.0 - a[b]) * X[i, b] + a[b] * fast_tanh(rho[b] * acc[i, b] + drive[i, b])
        X, Xn = Xn, X
        for r in range(rec_idx.size):
            for b in range(B):
                rec[t, r, b] = X[rec_idx[r], b]
    return rec


class BlockedMatrix:
    """W prepared for _esn_run_blocked (built once per network)."""

    def __init__(self, m, block_cols=16384, n_chunks=64):
        self.indptrs, self.indices, self.data = column_blocks(m, block_cols)
        self.bounds = block_bounds(self.indptrs, n_chunks)
        n = m.shape[0]
        self.rbounds = np.linspace(0, n, 65).astype(np.int64)

    def run(self, U, win_idx, win_val, rho, a, rec_idx):
        return _esn_run_blocked(self.indptrs, self.indices, self.data, self.bounds,
                                self.rbounds, np.ascontiguousarray(U, np.float32),
                                np.asarray(win_idx, np.int64),
                                np.ascontiguousarray(win_val, np.float32),
                                np.asarray(rho, np.float32), np.asarray(a, np.float32),
                                np.asarray(rec_idx, np.int64))


# ---------------------------------------------------------------------------
# Tasks (one input sequence feeds all of them)
# ---------------------------------------------------------------------------
MC_MAX_DELAY = 100
NARMA_MAX_LAG = 10
XOR_MAX_DELAY = 15


def make_input(T, seed):
    """i.i.d. uniform input in [0, 0.5] (the standard NARMA-10 input)."""
    rng = np.random.default_rng(np.random.SeedSequence([seed, 7]))
    while True:
        u = rng.uniform(0.0, 0.5, T)
        y = narma10(u)
        if np.isfinite(y).all() and np.abs(y).max() < 1.0:
            return u, y


def narma10(u):
    """NARMA-10: y(t) = 0.3 y(t-1) + 0.05 y(t-1) sum_{i=1..10} y(t-i)
    + 1.5 u(t-1) u(t-10) + 0.1 (Atiya & Parlos 2000; Jaeger 2003 form)."""
    T = u.size
    y = np.zeros(T)
    for t in range(10, T):
        y[t] = (0.3 * y[t - 1] + 0.05 * y[t - 1] * y[t - 10:t].sum()
                + 1.5 * u[t - 1] * u[t - 10] + 0.1)
    return y


def targets(u, y_narma, idx):
    """Target matrix for the time steps ``idx`` (states x(t) seen after u(t)).
    Columns: MC delays 0..MC_MAX_DELAY (u(t-k)), NARMA y(t-l) for latency
    l = 0..NARMA_MAX_LAG, XOR(b(t-d), b(t-d-1)) for d = 0..XOR_MAX_DELAY with
    b = [u > 0.25]."""
    b = (u > 0.25).astype(np.float64)
    cols = [u[idx - k] for k in range(MC_MAX_DELAY + 1)]
    cols += [y_narma[idx - l] for l in range(NARMA_MAX_LAG + 1)]
    cols += [np.logical_xor(b[idx - d], b[idx - d - 1]).astype(np.float64)
             for d in range(XOR_MAX_DELAY + 1)]
    return np.stack(cols, axis=1)


N_MC = MC_MAX_DELAY + 1
N_NA = NARMA_MAX_LAG + 1
N_XO = XOR_MAX_DELAY + 1
SL_MC = slice(0, N_MC)
SL_NA = slice(N_MC, N_MC + N_NA)
SL_XO = slice(N_MC + N_NA, N_MC + N_NA + N_XO)
ALPHAS = 10.0 ** np.array([-8.0, -6.0, -4.0, -2.0, 0.0])


# ---------------------------------------------------------------------------
# Ridge readout with separate train / validation / test data
# ---------------------------------------------------------------------------
def ridge_scores(Xtr, Ytr, Xva, Yva, Xte, Yte, alphas=ALPHAS):
    """Fit ridge readouts for every target column and every alpha, choose
    per task on VALIDATION data, report TEST scores.

    Alphas are relative: alpha * (mean squared feature size). Features are
    not standardised (a weak signal stays weak), only centred.
    Returns dict with mc, mc_curve, narma_nrmse, narma_lag, xor_acc, xor_delay.
    """
    Xtr = np.asarray(Xtr, np.float64)
    mu_x = Xtr.mean(0)
    mu_y = Ytr.mean(0)
    Xc = Xtr - mu_x
    Yc = Ytr - mu_y
    Xv = np.asarray(Xva, np.float64) - mu_x
    Xt = np.asarray(Xte, np.float64) - mu_x
    n, p = Xc.shape
    if p <= n:                       # primal: eigen-decomposition of X'X
        G = Xc.T @ Xc
        s, V = np.linalg.eigh(G)
        Q = V.T @ (Xc.T @ Yc)
        Av, At = Xv @ V, Xt @ V
        scale = np.trace(G) / p
    else:                            # dual: eigen-decomposition of XX'
        K = Xc @ Xc.T
        s, Uk = np.linalg.eigh(K)
        Q = Uk.T @ Yc
        Av, At = (Xv @ Xc.T) @ Uk, (Xt @ Xc.T) @ Uk
        scale = np.trace(K) / p
    s = np.clip(s, 0.0, None)
    if scale <= 0 or not np.isfinite(scale):
        scale = 1.0
    na = len(alphas)
    pv = np.empty((na,) + Yva.shape)
    pt = np.empty((na,) + Yte.shape)
    for ia, al in enumerate(alphas):
        coef = Q / (s + al * scale)[:, None]
        pv[ia] = Av @ coef + mu_y
        pt[ia] = At @ coef + mu_y
    # --- memory capacity: per delay, alpha by validation MSE, test r^2
    mse_v = ((pv[:, :, SL_MC] - Yva[None, :, SL_MC]) ** 2).mean(1)
    best = mse_v.argmin(0)
    ptm = pt[best, :, np.arange(N_MC)].T          # (T_test, N_MC)
    pvm = pv[best, :, np.arange(N_MC)].T
    ytm = Yte[:, SL_MC]
    r2 = np.array([_r2corr(ptm[:, k], ytm[:, k]) for k in range(N_MC)])
    r2v = np.array([_r2corr(pvm[:, k], Yva[:, k]) for k in range(N_MC)])
    # --- NARMA-10: (latency, alpha) by validation NRMSE, test NRMSE
    yv, yt = Yva[:, SL_NA], Yte[:, SL_NA]
    nr_v = np.sqrt(((pv[:, :, SL_NA] - yv[None]) ** 2).mean(1) / yv.var(0)[None])
    ia, il = np.unravel_index(np.nanargmin(nr_v), nr_v.shape)
    nr_t = float(np.sqrt(((pt[ia, :, N_MC + il] - yt[:, il]) ** 2).mean() / yt[:, il].var()))
    # --- delayed XOR: (delay, alpha) by validation accuracy, test accuracy
    xv, xt = Yva[:, SL_XO], Yte[:, SL_XO]
    acc_v = ((pv[:, :, SL_XO] > 0.5) == (xv[None] > 0.5)).mean(1)
    ja, jd = np.unravel_index(np.argmax(acc_v), acc_v.shape)
    acc_t = float(((pt[ja, :, SL_XO.start + jd] > 0.5) == (xt[:, jd] > 0.5)).mean())
    return {"mc": float(r2.sum()), "mc_curve": r2, "narma_nrmse": nr_t,
            "narma_lag": int(il), "xor_acc": acc_t, "xor_delay": int(jd),
            "mc_val": float(r2v.sum()), "narma_val": float(nr_v[ia, il]),
            "xor_val": float(acc_v[ja, jd])}


def _r2corr(p, y):
    """Squared correlation (Jaeger 2001 memory-capacity definition)."""
    ps, ys = p.std(), y.std()
    if ps == 0 or ys == 0 or not np.isfinite(ps):
        return 0.0
    c = np.corrcoef(p, y)[0, 1]
    return float(c * c) if np.isfinite(c) else 0.0


def mem_free_gb():
    """Free physical RAM in GB (Windows)."""
    import ctypes

    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    st = MS()
    st.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
    return st.ullAvailPhys / 1e9


def wait_for_ram(min_gb=1.5, poll_s=20, log=print):
    while True:
        f = mem_free_gb()
        if f >= min_gb:
            return f
        log(f"waiting for RAM: {f:.2f} GB free < {min_gb} GB")
        time.sleep(poll_s)

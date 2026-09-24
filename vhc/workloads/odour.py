"""Workload (b): continual odour learning with the mushroom-body design, RANDOM wiring.

The learner is the mb_continual lane's model, imported from experiments/mb_continual/common.py
(odour tables, PN response, noisy sniffs, k-winners KC code, the local "fly read-out" rule).
Wiring: the lane's "uniform" control (each Kenyon cell keeps its real number of inputs and
synapse counts; which glomerulus each input comes from is drawn at random). That control
scored 66.8% (docs/mb-continual-learning.md), better than the real wiring.

Protocol (as run_incremental.py "main"): 110 odours taught in 10 steps of 11, 20 noisy
training sniffs per odour (50 ms windows), tested after the last step on 20 fresh sniffs of
every odour. One TASK = one labelled sniff processed online: recognise it, then learn from it.

For the neuromorphic core the rate model is translated into spike events (counts below).
Constants marked GUESSED are placeholders.
"""
from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np

from ..cores import conventional, gpu
from ..paths import MB, load_module, wait_for_ram

T_S, K_FRAC, N_TR, N_TE, N_TASKS = 0.05, 0.05, 20, 20, 10
KC_SPIKES_PER_ACTIVE = 2      # GUESSED: an active KC fires ~1-3 spikes per sniff
APL_SPIKES = 5                # GUESSED: spikes of the one inhibitory APL neuron per sniff
OUT_SPIKES = 5                # GUESSED: output-neuron spikes per sniff
CHIP_DT_MS = 1.0              # ASSUMED: 1 ms steps on the chip (Loihi-typical), 50 per sniff


def mb():
    return load_module("mb_common", MB / "common.py")


@dataclass
class Setup:
    W: np.ndarray        # (n_kc, n_glom) synapse counts, random ("uniform") wiring
    P: np.ndarray        # (n_odour, n_glom) mean evoked PN rates
    spont: float
    source: str


def real_setup(side="left", seed=0):
    m = mb()
    wait_for_ram(1.5)
    table, _ = m.glomerulus_kc_table()
    gloms = m.all_glomeruli()
    od = m.load_odours(gloms)
    real = m.real_wiring(side, table=table, gloms=gloms)
    # same random draw as run_incremental.py: the "shuffled" control is drawn first
    wr = np.random.default_rng([seed, 303, ("left", "right").index(side)])
    m.control_wiring(real, "shuffled", wr)
    W = m.control_wiring(real, "uniform", wr).W
    return Setup(W, m.pn_mean(od.delta, od.set_a), m.PN_SPONT_HZ, f"FlyWire 630 {side}, uniform random")


def synthetic_setup(n_kc=300, n_glom=20, n_odour=22, inputs=6, seed=0):
    """Small made-up problem for unit tests (no data files needed)."""
    rng = np.random.default_rng(seed)
    W = np.zeros((n_kc, n_glom), np.float32)
    for k in range(n_kc):
        W[k, rng.choice(n_glom, inputs, replace=False)] = rng.integers(1, 10, inputs)
    P = rng.gamma(1.0, 30.0, (n_odour, n_glom)) * (rng.random((n_odour, n_glom)) < 0.4)
    return Setup(W, P, 5.0, "synthetic")


class QuantReadout:
    """The fly read-out with weights stored in ``bits``-bit integers (0..2^bits-1 = 0..cap),
    updated with stochastic rounding (ASSUMED available in the chip's learning engine)."""

    def __init__(self, n_kc, n_class, bits, rng, beta=0.01):
        self.q = 2 ** bits - 1
        self.W = np.zeros((n_class, n_kc), np.int32)
        self.beta, self.rng = beta, rng
        self.n_changed = []

    def train(self, H, y):
        for c in np.unique(y):
            inc = self.beta * H[y == c] * self.q
            fl = np.floor(inc)
            inc = fl + (self.rng.random(inc.shape) < (inc - fl))
            self.W[c] = np.minimum(self.q, self.W[c] + inc.sum(0).astype(np.int32))
        self.n_changed.extend((H > 0).sum(1).tolist())

    def predict(self, H, classes):
        classes = np.asarray(classes)
        return classes[np.argmax(H @ self.W[classes].T.astype(np.float32), axis=1)]


def run_protocol(s: Setup, seed=0, bits=None):
    """Class-incremental run; returns final accuracy on all odours and mean activity."""
    m = mb()
    n_od = s.P.shape[0]
    rng = np.random.default_rng([seed, 101])
    Xtr, ytr = m.make_trials(s.P, N_TR, T_S, rng, s.spont)
    Xte, yte = m.make_trials(s.P, N_TE, T_S, rng, s.spont)
    order = np.random.default_rng([seed, 202]).permutation(n_od)
    tasks = np.array_split(order, N_TASKS)
    Htr = m.kc_code(s.W, Xtr, K_FRAC)
    Hte = m.kc_code(s.W, Xte, K_FRAC)
    ro = (m.FlyReadout(s.W.shape[0], n_od) if bits is None
          else QuantReadout(s.W.shape[0], n_od, bits, np.random.default_rng([seed, 9])))
    seen = []
    for task in tasks:
        sel = np.isin(ytr, task)
        ro.train(Htr[sel], ytr[sel])
        seen.extend(task.tolist())
    acc = float(np.mean(ro.predict(Hte, seen) == yte))
    return {"accuracy": acc, "active_per_sniff": float((Htr > 0).sum(1).mean()),
            "Xtr": Xtr, "Htr": Htr, "n_classes": n_od, "readout": ro}


def neuro_counts(s: Setup, X, H, n_seen, train=True):
    """Mean spike-event counts per sniff for the neuromorphic core."""
    n_kc = s.W.shape[0]
    fan = (s.W > 0).sum(0)                                   # KCs reached per glomerulus
    pn_spikes = np.clip(np.round((X + s.spont) * T_S), 0, None)
    active = (H > 0).sum(1)
    kc_spikes = active * KC_SPIKES_PER_ACTIVE
    syn = pn_spikes @ fan + kc_spikes * (1 + n_seen) + APL_SPIKES * n_kc
    return {"steps": int(T_S * 1e3 / CHIP_DT_MS), "neurons": n_kc + n_seen + 1,
            "spikes": float(np.mean(kc_spikes + APL_SPIKES + OUT_SPIKES)),
            "syn_event": float(np.mean(syn)), "input_event": float(np.mean(pn_spikes.sum(1))),
            "syn_update": float(np.mean(active)) if train else 0.0}


def m33_ops(s: Setup, active, n_seen, train=True):
    """The same rate algorithm on a microcontroller, written sparsely."""
    n_kc = s.W.shape[0]
    return {"mac": float((s.W > 0).sum() + active * n_seen), "select": float(n_kc + n_seen),
            "syn_update": float(active if train else 0.0)}


def gpu_cost(s: Setup, n_seen, train=True):
    n_kc, n_glom = s.W.shape
    return gpu.price(launches=4 + int(train), flops=2 * n_kc * (n_glom + n_seen),
                     mem_bytes=4 * n_kc * (n_glom + n_seen), copies=2, copy_bytes=4 * n_glom + 8)


def measure_x86(s: Setup, n=300, seed=0):
    """Measured laptop time per task (one sniff at a time: code it, recognise, learn)."""
    m = mb()
    rng = np.random.default_rng([seed, 7])
    n_od = s.P.shape[0]
    X, y = m.make_trials(s.P, 3, T_S, rng, s.spont)
    idx = rng.permutation(X.shape[0])[:n]
    Wout = np.zeros((n_od, s.W.shape[0]), np.float32)
    classes = np.arange(n_od)
    ts = []
    for rep, i in enumerate(idx):
        t0 = time.perf_counter()
        h = m.kc_code(s.W, X[i:i + 1], K_FRAC)[0]
        _ = classes[np.argmax(Wout @ h)]
        Wout[y[i]] = np.minimum(1.0, Wout[y[i]] + 0.01 * h)
        ts.append(time.perf_counter() - t0)
    return float(np.median(ts[10:]))


def m33_cost(s: Setup, active, n_seen, train=True):
    return conventional.price(m33_ops(s, active, n_seen, train), "m33")

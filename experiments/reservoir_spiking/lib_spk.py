"""Helpers for the SPIKING connectome-reservoir lane (experiments/reservoir_spiking).

Plain English
-------------
Same question as experiments/reservoir (does the fly's real wiring work better
as a fixed "reservoir" than random wiring?), but the reservoir is now the
project's own spiking model (sim/fast_engine.FastBrain), with its real
synapse weights. There is no spectral-radius scaling here: every network
uses w_syn = 0.275 mV per synapse, exactly as the model does.

* Input: a number u(t) in [0, 0.5] per time bin, turned into Poisson spike
  rates on all 9,145 sensory neurons ("push-pull": half the neurons, chosen at
  random per seed, fire faster when u is high, the other half when u is low).
* Readout: spike counts per time bin of the descending neurons and of a pool
  of random non-sensory neurons. A ridge readout is trained on them.
* The tasks, the ridge readout and the two random controls are reused
  unchanged from experiments/reservoir/lib.py.

The long run is cut into segments (each re-started from rest by the engine).
Every segment first gets W bins of the TRUE preceding input, which are thrown
away ("washout"), so every kept bin has seen at least W bins of real history.
This keeps memory use bounded (a runaway network can make billions of spikes)
and lets a runaway network be stopped early.

Nothing in sim/, app/, tests/ or data/ is modified.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p_ in (str(ROOT), str(ROOT / "experiments" / "reservoir")):
    if p_ not in sys.path:
        sys.path.insert(0, p_)

import lib as rlib  # noqa: E402  (previous lane: tasks, ridge, controls, RAM)
from sim.fast_engine import FastBrain  # noqa: E402

RESULTS = HERE / "results"
RAW = RESULTS / "raw"
FIX = "al_ln_literature"   # always passed explicitly (project default may change)

BIN_MS = 20.0              # one input step = one readout bin
DT_MS = 0.1                # engine time step
SUB = int(round(BIN_MS / DT_MS))  # engine steps per bin (200)


def set_bin(ms):
    """Change the bin width (exploratory runs only; the pre-registered one is 20 ms)."""
    global BIN_MS, SUB
    BIN_MS = float(ms)
    SUB = int(round(BIN_MS / DT_MS))


# ---------------------------------------------------------------------------
# Networks
# ---------------------------------------------------------------------------
def real_arrays():
    """(root_ids, pre, post, signed) with the recommended fix, exactly what
    sim.sign_fixes.build_brain(fix=FIX) feeds FastBrain.from_arrays."""
    from sim.sign_fixes import apply_fix, load_reference_arrays
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre2, post2, signed2, rep = apply_fix(FIX, root_ids, pre, post, signed)
    return root_ids, pre2, post2, signed2, rep


def make_brain(kind, seed, arrays):
    """kind: 'real' | 'shuffle' | 'er'. Controls keep the same neurons, the same
    edge count and the same weight values (signed synapse counts)."""
    root_ids, pre, post, signed = arrays
    n = len(root_ids)
    if kind == "real":
        from sim.sign_fixes import build_brain
        return build_brain(fix=FIX, n_threads=1)
    if kind == "shuffle":
        p, q, w = rlib.degree_shuffle(pre, post, signed, seed, no_self=True)
    elif kind == "er":
        p, q, w = rlib.erdos_renyi(pre, post, signed, n, seed, no_self=True)
    else:
        raise ValueError(kind)
    return FastBrain.from_arrays(root_ids, np.asarray(p, np.int64),
                                 np.asarray(q, np.int64), np.asarray(w, np.int64),
                                 n_threads=1)


# ---------------------------------------------------------------------------
# Input: u(t) -> Poisson events on the sensory neurons
# ---------------------------------------------------------------------------
def input_signs(n_sens, seed):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 11]))
    return rng.choice(np.array([-1, 1], np.int8), n_sens)


def rates_for(u, signs, peak_hz):
    """Rate (Hz) of every sensory neuron in every bin: (n_bins, n_sens).
    v = 2u in [0, 1]; '+' neurons fire at peak*v, '-' neurons at peak*(1-v).
    u = NaN means input switched off (rate 0)."""
    v = np.clip(2.0 * np.asarray(u, np.float64), 0.0, 1.0)
    r = np.where(signs[None, :] > 0, v[:, None], 1.0 - v[:, None]) * peak_hz
    r[np.isnan(np.asarray(u, float))] = 0.0
    return r


def poisson_events(rates, sens_idx, rng):
    """Poisson kicks: in each bin, neuron i gets Binomial(SUB, rate*dt) kicks at
    uniformly random engine steps (same distribution as the engine's own
    Poisson input; the rare duplicate step of one neuron is merged, <1%).
    Returns (ev_ptr, ev_neuron) for the engine."""
    n_bins, n_sens = rates.shape
    prob = rates * DT_MS * 1e-3
    k = rng.binomial(SUB, prob)                       # (n_bins, n_sens)
    tot = int(k.sum())
    b_idx, s_idx = np.nonzero(k)
    reps = k[b_idx, s_idx]
    b_rep = np.repeat(b_idx, reps).astype(np.int64)
    s_rep = np.repeat(s_idx, reps)
    steps = b_rep * SUB + rng.integers(0, SUB, tot)
    neurons = sens_idx[s_rep].astype(np.int64)
    key = np.unique(steps * 200_000 + neurons)
    steps, neurons = key // 200_000, key % 200_000
    return FastBrain._pack_events(steps, neurons, n_bins * SUB)


# ---------------------------------------------------------------------------
# One segment
# ---------------------------------------------------------------------------
def simulate(brain, u_seg, signs, sens_idx, peak_hz, rng, col_of, n_cols,
             keep_from, keep_to=None, params=None):
    """Simulate one segment from rest.

    u_seg: input per bin (NaN = input off). Bins before ``keep_from`` are
    washout. Returns dict with
      counts   (n_bins, n_cols) int16 spike counts of the readout columns,
      pop      (n_bins,) spikes of all non-input neurons per bin,
      totals   (n_neurons,) spikes per neuron in bins [keep_from, keep_to),
      n_spikes, wall_s.
    """
    p = brain._params_for(params)
    rates = rates_for(u_seg, signs, peak_hz)
    ev = poisson_events(rates, sens_idx, rng)
    n_bins = len(u_seg)
    t0 = time.perf_counter()
    res = brain._run_events([ev], sens_idx, (), n_bins * SUB, p, ())
    wall = time.perf_counter() - t0
    b = (res.step // SUB).astype(np.int64)
    nrn = res.neuron.astype(np.int64)
    del res
    col = col_of[nrn]
    m = col >= 0
    counts = np.bincount(b[m] * n_cols + col[m], minlength=n_bins * n_cols)
    counts = counts.reshape(n_bins, n_cols).astype(np.int16)
    is_input = np.zeros(brain.n_neurons, bool)
    is_input[sens_idx] = True
    ni = ~is_input[nrn]
    pop = np.bincount(b[ni], minlength=n_bins)
    kk = (b >= keep_from) & (b < (n_bins if keep_to is None else keep_to))
    totals = np.bincount(nrn[kk], minlength=brain.n_neurons)
    return {"counts": counts, "pop": pop, "totals": totals,
            "n_spikes": int(nrn.size), "wall_s": wall}


# ---------------------------------------------------------------------------
# Count noise (electrode model), pre-registered
# ---------------------------------------------------------------------------
DETECT_P = 0.8        # each real spike is detected with probability 0.8
FALSE_HZ = 5.0        # plus false detections, Poisson at 5 Hz per electrode


def noisy_counts(counts, seed):
    rng = np.random.default_rng(np.random.SeedSequence([seed, 55]))
    c = rng.binomial(counts.astype(np.int64), DETECT_P)
    c += rng.poisson(FALSE_HZ * BIN_MS * 1e-3, counts.shape)
    return c

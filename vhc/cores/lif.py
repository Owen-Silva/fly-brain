"""Event-counting LIF simulator: the behaviour engine of the neuromorphic core (and of the
simulated culture).

The neuron model is the Shiu et al. 2024 model exactly as sim/fast_engine.py runs it (same
update formula, same order of operations, same Poisson input draw), so for the same seed it
gives the same spikes as the project's engine (vhc/tests/test_lif.py checks this). Differences:
  * every neuron is updated every step (fine for circuits of <= a few thousand neurons);
  * it COUNTS what hardware would have to do: synaptic events delivered, input events,
    spikes, spike messages;
  * optional extras used by the living-neuron module: membrane noise, per-event input
    weights, dead neurons.

Units inside: seconds and volts (like the engine). Public API: ms, mV, Hz.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numba as nb
import numpy as np

DEFAULT = {"v_0": -52.0, "v_rst": -52.0, "v_th": -45.0, "t_mbr": 20.0, "tau": 5.0,
           "t_rfc": 2.2, "t_dly": 1.8, "w_syn": 0.275, "f_poi": 250.0, "dt": 0.1}
_NEVER = -(1 << 40)


def update_constants(p):
    """Brian2's exact per-step multipliers (copied from sim/fast_engine.py)."""
    dt = np.float64(p["dt"] * 1e-3)
    tau = np.float64(p["tau"] * 1e-3)
    t_mbr = np.float64(p["t_mbr"] * 1e-3)
    v_0 = np.float64(p["v_0"] * 1e-3)
    l1 = (-dt) / tau
    l3 = tau / (t_mbr - tau)
    l4 = dt / t_mbr
    l5 = dt / tau
    l6 = (-dt) / t_mbr
    c_g = np.exp(l1)
    c_v0 = v_0 - (v_0 * np.exp(l6))
    c_vg = ((l3 * ((-np.exp(l4)) + np.exp(l5))) * np.exp(l6)) * np.exp(l1)
    c_vv = np.exp(l6)
    return float(c_g), float(c_v0), float(c_vg), float(c_vv)


@nb.njit(cache=True, nogil=True)
def _trial(n_steps, indptr, post, w, delay_steps, rfc, alive, ev_ptr, ev_neuron, ev_w,
           c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, noise_v, noise_seed):
    """One trial. Returns (spike_steps, spike_neurons, n_syn_events, n_input_events)."""
    n = rfc.shape[0]
    v = np.full(n, v_0)
    g = np.zeros(n)
    ls = np.full(n, _NEVER, np.int64)
    if noise_v > 0.0:
        np.random.seed(noise_seed)
    cap = 4096
    sp_s = np.empty(cap, np.int32)
    sp_n = np.empty(cap, np.int32)
    n_sp = 0
    deliver = 0
    n_syn = 0
    n_inp = 0
    for t in range(n_steps):
        if n_sp + n > cap:
            cap = 2 * (n_sp + n)
            a = np.empty(cap, np.int32)
            b = np.empty(cap, np.int32)
            a[:n_sp] = sp_s[:n_sp]
            b[:n_sp] = sp_n[:n_sp]
            sp_s = a
            sp_n = b
        # neuron updates (index order, so spikes come out in index order like Brian2)
        for i in range(n):
            if t - ls[i] >= rfc[i]:
                gi = g[i]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v[i]))
                if noise_v > 0.0:
                    vi += noise_v * np.random.standard_normal()
                g[i] = c_g * gi
                if vi > v_th and alive[i]:
                    sp_s[n_sp] = t
                    sp_n[n_sp] = i
                    n_sp += 1
                    ls[i] = t
                    v[i] = v_rst
                    g[i] = 0.0
                else:
                    v[i] = vi
        # input events (Poisson kicks / stimulation) add straight to v
        for e in range(ev_ptr[t], ev_ptr[t + 1]):
            i = ev_neuron[e]
            n_inp += 1
            if ls[i] != t and t - ls[i] >= rfc[i]:
                v[i] += ev_w[e]
        # spikes fired delay_steps ago arrive
        target = t - delay_steps
        while deliver < n_sp and sp_s[deliver] == target:
            j = sp_n[deliver]
            deliver += 1
            for s in range(indptr[j], indptr[j + 1]):
                i = post[s]
                n_syn += 1
                if ls[i] != t and t - ls[i] >= rfc[i]:
                    g[i] += w[s]
    return sp_s[:n_sp].copy(), sp_n[:n_sp].copy(), n_syn, n_inp


@dataclass
class Network:
    """A spiking network in CSR form (connections grouped by presynaptic neuron, stable)."""
    n: int
    indptr: np.ndarray
    post: np.ndarray
    count: np.ndarray            # signed synapse count (or any real weight in units of w_syn)
    params: dict = field(default_factory=lambda: dict(DEFAULT))
    names: list | None = None    # optional labels, e.g. root IDs

    @classmethod
    def from_edges(cls, n, pre, post, count, params=None, names=None):
        pre = np.asarray(pre, np.int64)
        order = np.argsort(pre, kind="stable")
        indptr = np.zeros(n + 1, np.int64)
        np.cumsum(np.bincount(pre, minlength=n), out=indptr[1:])
        p = dict(DEFAULT)
        p.update(params or {})
        return cls(n, indptr, np.ascontiguousarray(np.asarray(post)[order], np.int32),
                   np.ascontiguousarray(np.asarray(count, np.float64)[order]), p, names)

    @property
    def n_connections(self):
        return int(self.post.size)

    def out_degree(self):
        return np.diff(self.indptr)

    def quantized(self, bits):
        """Weights stored as signed integers of ``bits`` bits, scaled so the largest weight
        uses the full range (one shared scale, like a per-core weight exponent)."""
        q = 2 ** (bits - 1) - 1
        scale = np.abs(self.count).max() / q
        c = np.round(self.count / scale) * scale
        return Network(self.n, self.indptr, self.post, c, dict(self.params), self.names)


def poisson_events(rng, exc_idx, prob, n_steps):
    """The engine's Poisson draw (sim/fast_engine.py _poisson_events): per excited neuron a
    binomial number of kicks, placed on distinct random steps."""
    steps, neurons = [], []
    for i, pr in zip(exc_idx, prob):
        k = rng.binomial(n_steps, pr)
        if k:
            steps.append(rng.choice(n_steps, size=k, replace=False))
            neurons.append(np.full(k, i, np.int64))
    if steps:
        return np.concatenate(steps), np.concatenate(neurons)
    return np.zeros(0, np.int64), np.zeros(0, np.int64)


def pack_events(steps, neurons, n_steps, weights=None):
    keep = (steps >= 0) & (steps < n_steps)
    steps, neurons = steps[keep], neurons[keep]
    order = np.lexsort((neurons, steps))
    ev_n = np.ascontiguousarray(neurons[order], np.int32)
    ev_w = None if weights is None else np.ascontiguousarray(np.asarray(weights)[keep][order], np.float64)
    ptr = np.zeros(n_steps + 1, np.int64)
    np.cumsum(np.bincount(steps, minlength=n_steps), out=ptr[1:])
    return ptr, ev_n, ev_w


@dataclass
class TrialResult:
    spike_steps: np.ndarray
    spike_neurons: np.ndarray
    counts: dict             # hardware operation counts for this trial
    n_steps: int
    dt_ms: float

    def spike_count(self, n):
        return np.bincount(self.spike_neurons, minlength=n)


def prepare(net: Network, events, n_steps, excited_idx=(), alive=None, noise_mV=0.0,
            noise_seed=0):
    """Pack everything the compiled kernel needs (so its time can be measured alone)."""
    p = net.params
    dt_s = p["dt"] * 1e-3
    c_g, c_v0, c_vg, c_vv = update_constants(p)
    rfc = np.full(net.n, int((p["t_rfc"] * 1e-3 + 1e-3 * dt_s) / dt_s), np.int64)
    rfc[np.asarray(excited_idx, np.int64)] = 0
    delay = int(p["t_dly"] * 1e-3 / dt_s + 0.5)
    w_syn = p["w_syn"] * 1e-3
    w = net.count * w_syn
    steps, neurons = events[0], events[1]
    w_ev = (np.full(steps.size, w_syn * p["f_poi"]) if len(events) < 3 or events[2] is None
            else np.asarray(events[2], np.float64) * 1e-3)
    ptr, ev_n, ev_w = pack_events(np.asarray(steps, np.int64), np.asarray(neurons, np.int64),
                                  n_steps, w_ev)
    alive = np.ones(net.n, np.bool_) if alive is None else np.asarray(alive, np.bool_)
    return (n_steps, net.indptr, net.post, w, delay, rfc, alive, ptr, ev_n, ev_w, c_g, c_v0,
            c_vg, c_vv, p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3, noise_mV * 1e-3,
            int(noise_seed))


def kernel(args):
    """Run the compiled kernel on prepared arguments (this is what calibrate.py times)."""
    return _trial(*args)


def run_trial(net: Network, events, n_steps, excited_idx=(), alive=None, noise_mV=0.0,
              noise_seed=0):
    """Run one trial with explicit input events (steps, neurons[, weights in mV]).
    ``excited_idx``: neurons with no refractory period (the engine's Poisson-driven cells)."""
    args = prepare(net, events, n_steps, excited_idx, alive, noise_mV, noise_seed)
    alive = args[6]
    s_s, s_n, n_syn, n_inp = _trial(*args)
    outdeg = net.out_degree()
    counts = {"steps": n_steps, "neurons": int(alive.sum()), "spikes": int(s_n.size),
              "syn_event": int(n_syn), "input_event": int(n_inp),
              "spike_msgs": int((outdeg[s_n] > 0).sum())}
    return TrialResult(s_s, s_n, counts, n_steps, net.params["dt"])


def run_poisson(net: Network, excite: dict, duration_ms=1000.0, n_trials=1, seed=0):
    """Engine-compatible run: ``excite`` = {neuron index: rate Hz}, in the engine's order.
    Trial k gets the same input as the engine's trial k for the same seed."""
    p = net.params
    n_steps = int(round(duration_ms / p["dt"]))
    exc_idx = np.array(list(excite.keys()), np.int64)
    prob = np.array(list(excite.values()), float) * p["dt"] * 1e-3
    out = []
    for s in np.random.SeedSequence(seed).spawn(n_trials):
        st, ne = poisson_events(np.random.default_rng(s), exc_idx, prob, n_steps)
        out.append(run_trial(net, (st, ne), n_steps, excited_idx=exc_idx))
    return out

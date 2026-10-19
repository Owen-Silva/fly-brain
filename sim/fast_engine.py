# Portions of this file are copied or adapted from Drosophila_brain_model by Philip Shiu
# and Nico Spiller (https://github.com/philshiu/Drosophila_brain_model, commit 91bdd1e),
# used under the MIT License. Their copyright and permission notice:
#
# MIT License
#
# Copyright (c) 2023 Philip Shiu and Nico Spiller
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#
# This project's own code is also MIT-licensed: see LICENSE and THIRD_PARTY_NOTICES.md.

"""Fast whole-brain simulation engine (no C compiler needed).

What this is, in plain English
------------------------------
The reference fly-brain model (Shiu et al. 2024, ``data/reference/model.py``)
is written for Brian2. Brian2 is fast only when it can compile C++ code, and
this laptop has no C++ compiler, so Brian2 falls back to a slow pure-Python
mode (roughly 20-40 seconds of computer time per simulated second of brain
activity). This file re-implements *exactly the same model* in a way that is
fast without a C compiler: the inner loop is compiled on the fly by numba
(which ships its own compiler), and it only does work for neurons that have
actually received input.

"Exactly the same model" means every rule below is copied from the reference
code and from what Brian2 does with it (checked against Brian2's own
generated code, see docs/fast-engine-explained.md):

* Every neuron is a leaky integrate-and-fire neuron with two variables:
  ``v`` (membrane voltage) and ``g`` (synaptic input that fades away).
  ``dv/dt = (v_0 - v + g) / t_mbr`` and ``dg/dt = -g / tau``, solved exactly
  over each 0.1 ms time step with the same arithmetic Brian2 generates.
* A neuron spikes when ``v > v_th``; then ``v = v_rst`` and ``g = 0``.
* After a spike the neuron is refractory for 2.2 ms (22 steps): ``v`` and ``g``
  are frozen AND any input arriving in that window is thrown away (Brian2's
  "unless refractory" rule blocks writes to frozen variables).
* A spike reaches its targets 1.8 ms (18 steps) later and adds
  ``signed synapse count x w_syn`` to the target's ``g``.
* Stimulated ("excited") neurons get Poisson input: every time step, with
  probability ``rate x dt``, their ``v`` jumps by ``w_syn x f_poi`` (68.75 mV),
  and their refractory period is set to 0, just like ``model.poi``.
* Silencing sets the output of the silenced neurons to zero, like
  ``model.silence``. A silenced neuron can still fire; it just has no effect.
* Within one time step the order of operations is Brian2's default schedule:
  update voltages, check thresholds, deliver inputs, then reset.

Units: the public API uses milliseconds, millivolts and Hz. Inside, the
numbers are converted to seconds and volts, the same units Brian2 uses, so
that the arithmetic matches Brian2 bit for bit.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

import numba as nb
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DIR = PROJECT_ROOT / "data" / "reference"

#: Connectome snapshots shipped with the reference repository.
#: "630" is the one the paper used; "783" is the newer public release.
SNAPSHOTS = {
    "630": ("2023_03_23_completeness_630_final.csv",
            "2023_03_23_connectivity_630_final.parquet"),
    "783": ("Completeness_783.csv", "Connectivity_783.parquet"),
}

#: Model constants, copied from ``default_params`` in data/reference/model.py.
#: Units: voltages in mV, times in ms, rates in Hz.
DEFAULT_PARAMS = {
    "v_0": -52.0,     # resting potential (mV)
    "v_rst": -52.0,   # reset potential after a spike (mV)
    "v_th": -45.0,    # spike threshold (mV)
    "t_mbr": 20.0,    # membrane time constant (ms)
    "tau": 5.0,       # synaptic time constant (ms)
    "t_rfc": 2.2,     # refractory period (ms)
    "t_dly": 1.8,     # synaptic delay (ms)
    "w_syn": 0.275,   # weight per synapse (mV)
    "r_poi": 150.0,   # default Poisson input rate for excited neurons (Hz)
    "f_poi": 250.0,   # Poisson input weight = w_syn * f_poi
    "dt": 0.1,        # simulation time step (ms); Brian2's default clock
}

_NEVER = -(1 << 40)  # "last spike" step for neurons that have never spiked


# ---------------------------------------------------------------------------
# The compiled inner loop (one trial)
# ---------------------------------------------------------------------------
@nb.njit(cache=True, nogil=True)
def _simulate_trial(n_steps, indptr, post, count, w_syn, silenced, rfc_steps,
                    ev_ptr, ev_neuron, w_poi, delay_steps,
                    c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx):
    """Run one trial. All voltages in volts.

    Neurons nobody has touched yet sit exactly on the shared "resting
    trajectory" ``rest`` (every untouched neuron in Brian2 starts at v_0 with
    g = 0 and evolves identically), so they are stored once, as one number.
    The first time a neuron receives input it gets a "slot" in compact
    arrays (v_a, g_a, ...) that are updated every step. Keeping the active
    neurons side by side in memory is what makes the loop fast.

    Returns (spike_steps, spike_neurons, voltage_record, n_touched).
    """
    n_neurons = rfc_steps.shape[0]
    slot = np.full(n_neurons, -1, np.int32)      # neuron -> slot (-1: untouched)
    act_id = np.empty(n_neurons, np.int32)        # slot -> neuron
    v_a = np.empty(n_neurons)
    g_a = np.empty(n_neurons)
    ls_a = np.empty(n_neurons, np.int64)          # step of last spike
    rf_a = np.empty(n_neurons, np.int64)          # refractory period in steps
    n_active = 0
    rest = v_0

    cap = 4096
    sp_step = np.empty(cap, np.int32)
    sp_neu = np.empty(cap, np.int32)
    n_sp = 0
    deliver = 0

    n_rec = rec_idx.shape[0]
    vrec = np.empty((n_steps, n_rec))

    for n in range(n_steps):
        # Brian2 'start' slot: StateMonitor records v before the update.
        for r in range(n_rec):
            k = slot[rec_idx[r]]
            vrec[n, r] = v_a[k] if k >= 0 else rest

        # Make room for up to n_active new spikes. (Growing the arrays here,
        # outside the inner loop, keeps the inner loop ~15x faster.)
        if n_sp + n_active > cap:
            cap = 2 * (n_sp + n_active)
            tmp_s = np.empty(cap, np.int32)
            tmp_n = np.empty(cap, np.int32)
            tmp_s[:n_sp] = sp_step[:n_sp]
            tmp_n[:n_sp] = sp_neu[:n_sp]
            sp_step = tmp_s
            sp_neu = tmp_n

        # 'groups' slot: exact linear update (Brian2's generated formula).
        rest = c_v0 + ((c_vg * 0.0) + (c_vv * rest))
        first_new = n_sp
        for k in range(n_active):
            if n - ls_a[k] >= rf_a[k]:                    # not refractory
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    # Far below one rounding step of v (~1e-18 V): has no
                    # effect on v at all, but would slow the CPU down once it
                    # decays into "denormal" numbers after ~3.5 s.
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v_a[k]))
                g_a[k] = c_g * gi
                # 'thresholds' slot (+ the reset, applied right away; inputs
                # to a neuron in its spike step are blocked below anyway).
                if vi > v_th:
                    sp_step[n_sp] = n
                    sp_neu[n_sp] = act_id[k]
                    n_sp += 1
                    ls_a[k] = n
                    v_a[k] = v_rst
                    g_a[k] = 0.0
                else:
                    v_a[k] = vi

        # Keep this step's spikes in neuron-index order, as Brian2 does, so
        # inputs are summed in the same order (identical rounding).
        for a in range(first_new + 1, n_sp):
            x = sp_neu[a]
            b = a - 1
            while b >= first_new and sp_neu[b] > x:
                sp_neu[b + 1] = sp_neu[b]
                b -= 1
            sp_neu[b + 1] = x

        # 'synapses' slot, part 1: Poisson kicks to v. Inputs are ignored
        # while the target is refractory or spiked this very step (Brian2's
        # "unless refractory" rule).
        for e in range(ev_ptr[n], ev_ptr[n + 1]):
            i = ev_neuron[e]
            k = slot[i]
            if k < 0:
                k = n_active
                n_active += 1
                slot[i] = k
                act_id[k] = i
                v_a[k] = rest
                g_a[k] = 0.0
                ls_a[k] = _NEVER
                rf_a[k] = rfc_steps[i]
            if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                v_a[k] += w_poi

        # 'synapses' slot, part 2: spikes fired delay_steps ago arrive.
        target_step = n - delay_steps
        while deliver < n_sp and sp_step[deliver] == target_step:
            j = sp_neu[deliver]
            deliver += 1
            if silenced[j]:
                continue
            for s in range(indptr[j], indptr[j + 1]):
                i = post[s]
                k = slot[i]
                if k < 0:
                    k = n_active
                    n_active += 1
                    slot[i] = k
                    act_id[k] = i
                    v_a[k] = rest
                    g_a[k] = 0.0
                    ls_a[k] = _NEVER
                    rf_a[k] = rfc_steps[i]
                if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                    g_a[k] += count[s] * w_syn

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), vrec, n_active


def _update_constants(p):
    """The per-step multipliers, computed exactly as Brian2's generated code
    computes them (same operations in the same order, float64)."""
    dt = np.float64(p["dt"] * 1e-3)
    tau = np.float64(p["tau"] * 1e-3)
    t_mbr = np.float64(p["t_mbr"] * 1e-3)
    v_0 = np.float64(p["v_0"] * 1e-3)
    if abs(t_mbr - tau) < 1e-12:
        raise ValueError("t_mbr and tau must differ (the exact solution divides by t_mbr - tau)")
    lio_1 = (-dt) / tau
    lio_2 = np.exp(lio_1)
    lio_3 = tau / (t_mbr - tau)
    lio_4 = dt / t_mbr
    lio_5 = dt / tau
    lio_6 = (-dt) / t_mbr
    lio_8 = v_0 - (v_0 * np.exp(lio_6))
    lio_9 = ((lio_3 * ((-np.exp(lio_4)) + np.exp(lio_5))) * np.exp(lio_6)) * np.exp(lio_1)
    lio_10 = np.exp(lio_6)
    return float(lio_2), float(lio_8), float(lio_9), float(lio_10)


def _timestep(t, dt):
    """Brian2's ``timestep()``: time -> whole number of steps."""
    return int((t + 1e-3 * dt) / dt)


def _as_root_ids(ids):
    """Root IDs must stay int64. Floats lose digits of 18-digit IDs."""
    arr = np.asarray(list(ids) if not isinstance(ids, np.ndarray) else ids)
    if arr.size == 0:
        return np.zeros(0, np.int64)
    if not np.issubdtype(arr.dtype, np.integer):
        raise TypeError(f"neuron IDs must be integers (int64), got dtype {arr.dtype}; "
                        "floats silently corrupt 18-digit FlyWire IDs")
    return arr.astype(np.int64)


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
@dataclass
class SimResult:
    """Everything one call to ``FastBrain.run`` produced.

    Spikes are stored as three equal-length arrays (one entry per spike):
    ``trial``, ``neuron`` (row number in ``root_ids``) and ``step``.
    """
    root_ids: np.ndarray
    n_trials: int
    duration_ms: float
    dt_ms: float
    seed: int | None
    excite: dict
    silence: list
    params: dict
    trial: np.ndarray
    neuron: np.ndarray
    step: np.ndarray
    neurons_reached: list = field(default_factory=list)
    voltages_V: dict = field(default_factory=dict)
    wall_time_s: float = 0.0

    @property
    def voltages_mV(self):
        """Recorded voltage traces: {root_id: array (n_trials, n_steps) in mV},
        value at the start of each time step (like Brian2's StateMonitor)."""
        return {k: v * 1e3 for k, v in self.voltages_V.items()}

    @property
    def time_ms(self):
        """Spike times in ms (same order as ``trial`` / ``neuron``)."""
        return self.step * self.dt_ms

    @property
    def spike_counts(self):
        """Total spikes per neuron over all trials (length = number of neurons)."""
        return np.bincount(self.neuron, minlength=len(self.root_ids))

    @property
    def rates_hz(self):
        """Mean firing rate per neuron in Hz, averaged over trials
        (same definition as the reference ``utils.get_rate``)."""
        return self.spike_counts / (self.n_trials * self.duration_ms * 1e-3)

    def rate(self, root_id):
        """Mean firing rate (Hz) of one neuron."""
        idx = np.flatnonzero(self.root_ids == np.int64(root_id))
        if idx.size == 0:
            raise KeyError(f"neuron {root_id} is not in this connectome snapshot")
        return float(self.rates_hz[idx[0]])

    def rates(self, nonzero_only=True):
        """Firing rates as a pandas Series indexed by root ID, highest first."""
        s = pd.Series(self.rates_hz, index=pd.Index(self.root_ids, name="root_id"),
                      name="rate_hz")
        if nonzero_only:
            s = s[s > 0]
        return s.sort_values(ascending=False)

    def rate_stats(self):
        """Mean and standard deviation over trials (Hz) for neurons that spiked,
        matching the reference ``utils.get_rate`` (std with ddof=0)."""
        dur_s = self.duration_ms * 1e-3
        spiking = np.unique(self.neuron)
        per_trial = np.zeros((self.n_trials, spiking.size))
        col = np.searchsorted(spiking, self.neuron)
        np.add.at(per_trial, (self.trial, col), 1.0)
        per_trial /= dur_s
        return pd.DataFrame(
            {"mean_hz": per_trial.mean(axis=0), "std_hz": per_trial.std(axis=0)},
            index=pd.Index(self.root_ids[spiking], name="root_id"),
        ).sort_values("mean_hz", ascending=False)

    def spike_times(self, trial=0):
        """Spike times (ms) of one trial as {root_id: array of times}."""
        m = self.trial == trial
        neu, st = self.neuron[m], self.step[m]
        order = np.lexsort((st, neu))
        neu, st = neu[order], st[order]
        cuts = np.flatnonzero(np.diff(neu)) + 1
        out = {}
        for block_n, block_s in zip(np.split(neu, cuts), np.split(st, cuts)):
            if block_n.size:
                out[int(self.root_ids[block_n[0]])] = block_s * self.dt_ms
        return out

    def spike_trains(self):
        """List (one per trial) of {root_id: spike times in ms}."""
        return [self.spike_times(k) for k in range(self.n_trials)]

    def to_dataframe(self, exp_name=""):
        """One row per spike, in the reference repository's format
        (t in seconds, trial, flywire_id, exp_name)."""
        return pd.DataFrame({
            "t": self.step * (self.dt_ms * 1e-3),
            "trial": self.trial.astype(np.int64),
            "flywire_id": self.root_ids[self.neuron],
            "exp_name": exp_name,
        })


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
class FastBrain:
    """The whole-brain model, built once and run many times.

    Example
    -------
    >>> brain = FastBrain(snapshot="630")
    >>> res = brain.run(excite=sugar_ids, duration_ms=1000, n_trials=30, seed=0)
    >>> res.rate(720575940660219265)          # MN9 firing rate in Hz

    Parameters
    ----------
    snapshot : "630" (the paper's FlyWire snapshot) or "783" (newer public one).
    params : optional dict overriding ``DEFAULT_PARAMS`` (mV / ms / Hz).
    n_threads : how many trials to run at the same time (each uses one core).
    """

    def __init__(self, snapshot="630", params=None, n_threads=1, *,
                 comp_path=None, con_path=None):
        if comp_path is None or con_path is None:
            if str(snapshot) not in SNAPSHOTS:
                raise ValueError(f"snapshot must be one of {sorted(SNAPSHOTS)}")
            comp_name, con_name = SNAPSHOTS[str(snapshot)]
            comp_path = REFERENCE_DIR / comp_name
            con_path = REFERENCE_DIR / con_name
        self.snapshot = str(snapshot)
        t0 = time.perf_counter()
        root_ids = pd.read_csv(comp_path, index_col=0).index.to_numpy()
        table = pq.read_table(con_path, columns=[
            "Presynaptic_ID", "Presynaptic_Index", "Postsynaptic_Index",
            "Excitatory x Connectivity"])
        pre = table.column("Presynaptic_Index").to_numpy()
        pre_id = table.column("Presynaptic_ID").to_numpy()
        # Sanity check: the file's row numbers must point at the right neurons.
        if not np.array_equal(root_ids[pre], pre_id):
            raise ValueError("Presynaptic_Index does not match the completeness file")
        del pre_id
        self._setup(root_ids, pre,
                    table.column("Postsynaptic_Index").to_numpy(),
                    table.column("Excitatory x Connectivity").to_numpy(),
                    params, n_threads)
        self.load_time_s = time.perf_counter() - t0

    @classmethod
    def from_arrays(cls, root_ids, pre_index, post_index, signed_count,
                    params=None, n_threads=1):
        """Build from raw arrays (used by the tests for tiny networks)."""
        self = cls.__new__(cls)
        self.snapshot = "custom"
        self._setup(np.asarray(root_ids), np.asarray(pre_index, dtype=np.int64),
                    np.asarray(post_index, dtype=np.int64),
                    np.asarray(signed_count, dtype=np.int64), params, n_threads)
        self.load_time_s = 0.0
        return self

    def _setup(self, root_ids, pre, post, signed, params, n_threads):
        self.root_ids = _as_root_ids(root_ids)
        n = self.root_ids.size
        self._index = pd.Index(self.root_ids)
        if not self._index.is_unique:
            raise ValueError("duplicate root IDs")
        # Group connections by presynaptic neuron. A stable sort keeps the
        # file's order within each neuron (the order Brian2 adds them up in).
        order = np.argsort(pre, kind="stable")
        self._post = np.ascontiguousarray(post[order], dtype=np.int32)
        self._count = np.ascontiguousarray(signed[order], dtype=np.int32)
        self._indptr = np.zeros(n + 1, np.int64)
        np.cumsum(np.bincount(pre, minlength=n), out=self._indptr[1:])
        self.n_neurons = n
        self.n_connections = int(self._post.size)
        self.params = dict(DEFAULT_PARAMS)
        if params:
            self._check_params(params)
            self.params.update(params)
        self.n_threads = max(1, int(n_threads))

    @staticmethod
    def _check_params(params):
        unknown = set(params) - set(DEFAULT_PARAMS)
        if unknown:
            raise KeyError(f"unknown parameter(s) {sorted(unknown)}; "
                           f"known: {sorted(DEFAULT_PARAMS)}")

    def index_of(self, root_ids):
        """Row numbers for a list of root IDs (KeyError names any missing ID)."""
        ids = _as_root_ids(root_ids)
        idx = self._index.get_indexer(ids)
        if (idx < 0).any():
            missing = ids[idx < 0].tolist()
            raise KeyError(f"{len(missing)} ID(s) not in snapshot {self.snapshot}: {missing[:10]}")
        return idx.astype(np.int64)

    # -- running -----------------------------------------------------------
    def run(self, excite=(), silence=(), duration_ms=1000.0, n_trials=1,
            seed=0, rate_hz=None, params=None, record_v=()):
        """Simulate the brain.

        Parameters
        ----------
        excite : list of root IDs to drive with Poisson input at ``rate_hz``,
            or a dict {root_id: rate in Hz} to give neurons different rates
            (the reference's second input class, ``r_poi2``).
        silence : list of root IDs whose outgoing connections are set to 0.
        duration_ms : length of each trial in ms.
        n_trials : number of independent trials (different random input).
        seed : integer; the same seed always gives the same result. Trial k
            gets the same input whatever ``n_trials`` is.
        rate_hz : Poisson rate for a plain list in ``excite`` (default 150 Hz).
        params : optional per-run overrides of the model constants.
        record_v : root IDs whose voltage trace (mV, every step) to keep.
        """
        p = self._params_for(params)
        if isinstance(excite, dict):
            exc_ids = _as_root_ids(list(excite.keys()))
            rates = np.array([float(r) for r in excite.values()])
        else:
            exc_ids = _as_root_ids(excite)
            r = p["r_poi"] if rate_hz is None else float(rate_hz)
            rates = np.full(exc_ids.size, r)
        exc_idx = self.index_of(exc_ids)
        n_steps = int(round(duration_ms / p["dt"]))
        prob = rates * p["dt"] * 1e-3
        if (prob < 0).any() or (prob > 1).any():
            raise ValueError("rate x dt must be between 0 and 1")

        seqs = np.random.SeedSequence(seed).spawn(n_trials)
        events = [self._poisson_events(np.random.default_rng(s), exc_idx, prob, n_steps)
                  for s in seqs]
        res = self._run_events(events, exc_idx, silence, n_steps, p, record_v)
        res.seed = seed
        res.excite = {int(i): float(r) for i, r in zip(exc_ids, rates)}
        return res

    def run_with_input_events(self, events, excite=(), silence=(), duration_ms=100.0,
                              params=None, record_v=()):
        """Run with input spike trains given explicitly (used to compare with
        Brian2 on identical input). ``events`` is one (steps, root_ids) pair
        per trial: at step ``steps[k]`` neuron ``root_ids[k]`` gets one Poisson
        kick. ``excite`` lists the neurons treated as stimulated (refractory
        period 0), exactly like ``model.poi``."""
        p = self._params_for(params)
        n_steps = int(round(duration_ms / p["dt"]))
        exc_idx = self.index_of(excite)
        ev = []
        for steps, ids in events:
            steps = np.asarray(steps, np.int64)
            idx = self.index_of(ids) if len(ids) else np.zeros(0, np.int64)
            ev.append(self._pack_events(steps, idx, n_steps))
        res = self._run_events(ev, exc_idx, silence, n_steps, p, record_v)
        res.excite = {int(i): float("nan") for i in self.root_ids[exc_idx]}
        return res

    # -- internals ---------------------------------------------------------
    def _params_for(self, overrides):
        p = dict(self.params)
        if overrides:
            self._check_params(overrides)
            p.update(overrides)
        return p

    @staticmethod
    def _poisson_events(rng, exc_idx, prob, n_steps):
        """Each step, each excited neuron gets a kick with probability
        rate x dt, independently (what Brian2's PoissonInput with N=1 does).
        Drawn as: how many kicks (binomial), then which steps (uniform,
        without repeats), which is the same distribution."""
        steps, neurons = [], []
        for i, pr in zip(exc_idx, prob):
            k = rng.binomial(n_steps, pr)
            if k:
                steps.append(rng.choice(n_steps, size=k, replace=False))
                neurons.append(np.full(k, i, np.int64))
        if steps:
            steps = np.concatenate(steps)
            neurons = np.concatenate(neurons)
        else:
            steps = neurons = np.zeros(0, np.int64)
        return FastBrain._pack_events(steps, neurons, n_steps)

    @staticmethod
    def _pack_events(steps, neurons, n_steps):
        keep = (steps >= 0) & (steps < n_steps)
        steps, neurons = steps[keep], neurons[keep]
        order = np.lexsort((neurons, steps))
        ev_neuron = np.ascontiguousarray(neurons[order], dtype=np.int32)
        ev_ptr = np.zeros(n_steps + 1, np.int64)
        np.cumsum(np.bincount(steps, minlength=n_steps), out=ev_ptr[1:])
        return ev_ptr, ev_neuron

    def _run_events(self, events, exc_idx, silence, n_steps, p, record_v):
        t0 = time.perf_counter()
        dt_s = p["dt"] * 1e-3
        c_g, c_v0, c_vg, c_vv = _update_constants(p)
        rfc = np.full(self.n_neurons, _timestep(p["t_rfc"] * 1e-3, dt_s), np.int64)
        rfc[exc_idx] = 0                        # model.poi: no refractory period
        silenced = np.zeros(self.n_neurons, np.bool_)
        sil_ids = _as_root_ids(silence)
        silenced[self.index_of(sil_ids)] = True
        rec_ids = _as_root_ids(record_v)
        rec_idx = self.index_of(rec_ids).astype(np.int64)
        delay_steps = int(p["t_dly"] * 1e-3 / dt_s + 0.5)  # Brian2 SpikeQueue rounding
        w_syn = p["w_syn"] * 1e-3
        w_poi = w_syn * p["f_poi"]
        v_0, v_th, v_rst = p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3

        def one(ev):
            return _simulate_trial(n_steps, self._indptr, self._post, self._count, w_syn,
                                   silenced, rfc, ev[0], ev[1], w_poi, delay_steps,
                                   c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx)

        if self.n_threads > 1 and len(events) > 1:
            with ThreadPoolExecutor(self.n_threads) as pool:
                outs = list(pool.map(one, events))
        else:
            outs = [one(ev) for ev in events]

        trial = np.concatenate([np.full(o[0].size, k, np.int32) for k, o in enumerate(outs)]) \
            if outs else np.zeros(0, np.int32)
        step = np.concatenate([o[0] for o in outs]) if outs else np.zeros(0, np.int32)
        neuron = np.concatenate([o[1] for o in outs]) if outs else np.zeros(0, np.int32)
        voltages = {int(rid): np.stack([o[2][:, r] for o in outs])
                    for r, rid in enumerate(rec_ids)}
        return SimResult(
            root_ids=self.root_ids, n_trials=len(events), duration_ms=n_steps * p["dt"],
            dt_ms=p["dt"], seed=None, excite={}, silence=[int(s) for s in sil_ids],
            params=p, trial=trial, neuron=neuron, step=step,
            neurons_reached=[int(o[3]) for o in outs], voltages_V=voltages,
            wall_time_s=time.perf_counter() - t0,
        )

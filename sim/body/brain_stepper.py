"""Run the whole-brain model in short windows, keeping its state in between.

Why this file exists (plain English)
------------------------------------
A closed loop needs the brain to run for a short window (say 50 ms), hand its
output to the body, get new senses back, and then CONTINUE from exactly where
it stopped: same voltages, same half-faded synaptic inputs, and the spikes
that were still "in flight" (a spike takes 1.8 ms to reach its targets).

``FastBrain`` (sim/fast_engine.py) cannot do that: every call to ``run`` or
``run_with_input_events`` starts all 127,400 neurons from rest. We may not
edit that file. Two workarounds were possible:

1. **Replay.** For window k, re-run the brain from time 0 with ALL the input
   so far, and keep only the last window. Exact, but the cost grows with the
   square of the trial length: a 3-second trial in 50 ms windows would
   simulate 91.5 s of brain time instead of 3 s (30x more).
2. **A stateful copy of the engine's inner loop (used here).** The loop below
   is a line-by-line copy of ``_simulate_trial`` in sim/fast_engine.py, with
   one change: the state lives outside the loop and is handed back and forth.
   It uses the SAME connection arrays, constants and helpers as the
   ``FastBrain`` it wraps, so the model itself is not re-implemented.
   Cost: about 100 duplicated lines that must stay in step with
   fast_engine.py. That risk is covered by a test
   (tests/test_body_loop.py): a run cut into windows of several sizes must
   give spike-for-spike the SAME result as one uninterrupted
   ``FastBrain.run_with_input_events`` run. If fast_engine.py ever changes
   its rules, that test fails.

Input to the smell neurons is Poisson (random) like everywhere else in the
project, drawn window by window with that window's rates, using
``FastBrain``'s own drawing routine.
"""

from __future__ import annotations

from dataclasses import dataclass

import numba as nb
import numpy as np

from sim.fast_engine import _NEVER, FastBrain, _as_root_ids, _timestep, _update_constants


@nb.njit(cache=True, nogil=True)
def _run_window(n0, n_steps, indptr, post, count, w_syn, silenced, rfc_steps,
                ev_ptr, ev_neuron, w_poi, delay_steps,
                c_g, c_v0, c_vg, c_vv, v_th, v_rst,
                slot, act_id, v_a, g_a, ls_a, rf_a, n_active, rest,
                pend_step, pend_neu):
    """Advance the brain from global step ``n0`` by ``n_steps`` steps.

    Identical rules to ``sim.fast_engine._simulate_trial`` (see there for the
    comments on each slot); only the bookkeeping differs:

    * ``slot, act_id, v_a, g_a, ls_a, rf_a`` are the neuron state arrays and
      are updated IN PLACE; ``n_active`` and ``rest`` are returned.
    * steps are counted globally (``n0 + local step``) so refractory periods
      and spike delays carry across windows.
    * ``pend_step/pend_neu``: spikes fired earlier but not yet delivered
      (in flight); they are delivered first, in order.

    Returns (spike_steps, spike_neurons, n_pending_in, n_delivered, n_active, rest).
    Spikes ``[n_pending_in:]`` are the ones fired in this window; spikes
    ``[n_delivered:]`` are still in flight at the end of the window.
    """
    n_pend = pend_step.shape[0]
    cap = 4096
    while cap < 2 * n_pend + 16:
        cap *= 2
    sp_step = np.empty(cap, np.int64)
    sp_neu = np.empty(cap, np.int32)
    for a in range(n_pend):
        sp_step[a] = pend_step[a]
        sp_neu[a] = pend_neu[a]
    n_sp = n_pend
    deliver = 0

    for m in range(n_steps):
        n = n0 + m
        if n_sp + n_active > cap:
            cap = 2 * (n_sp + n_active)
            tmp_s = np.empty(cap, np.int64)
            tmp_n = np.empty(cap, np.int32)
            tmp_s[:n_sp] = sp_step[:n_sp]
            tmp_n[:n_sp] = sp_neu[:n_sp]
            sp_step = tmp_s
            sp_neu = tmp_n

        rest = c_v0 + ((c_vg * 0.0) + (c_vv * rest))
        first_new = n_sp
        for k in range(n_active):
            if n - ls_a[k] >= rf_a[k]:
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v_a[k]))
                g_a[k] = c_g * gi
                if vi > v_th:
                    sp_step[n_sp] = n
                    sp_neu[n_sp] = act_id[k]
                    n_sp += 1
                    ls_a[k] = n
                    v_a[k] = v_rst
                    g_a[k] = 0.0
                else:
                    v_a[k] = vi

        for a in range(first_new + 1, n_sp):
            x = sp_neu[a]
            b = a - 1
            while b >= first_new and sp_neu[b] > x:
                sp_neu[b + 1] = sp_neu[b]
                b -= 1
            sp_neu[b + 1] = x

        for e in range(ev_ptr[m], ev_ptr[m + 1]):
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

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), n_pend, deliver, n_active, rest


@dataclass
class WindowResult:
    """What one brain window produced."""
    start_ms: float
    duration_ms: float
    spike_steps: np.ndarray      # global step of each spike fired in the window
    spike_index: np.ndarray      # neuron row number of each spike
    n_input_kicks: int           # Poisson kicks given to the stimulated neurons

    def count(self, idx):
        """Spikes fired by the neurons at row numbers ``idx`` (array-like)."""
        idx = np.asarray(idx, np.int64)
        if self.spike_index.size == 0:
            return np.zeros(idx.size, np.int64)
        counts = np.bincount(self.spike_index, minlength=int(idx.max()) + 1)
        return counts[idx]

    def rates_hz(self, idx):
        """Firing rate (Hz) of the neurons at row numbers ``idx`` in this window."""
        return self.count(idx) / (self.duration_ms * 1e-3)


class BrainStepper:
    """One trial of the brain, advanced window by window with its state kept.

    Parameters
    ----------
    brain : a ``FastBrain`` (any snapshot or sign fix).
    input_ids : root IDs of the neurons that receive Poisson input during the
        trial (e.g. all DM1 smell neurons). Fixed for the whole trial, as in a
        single ``FastBrain.run``; their rates can change every window (a rate
        of 0 means no input in that window).
    silence : root IDs whose outgoing connections are cut (``model.silence``).
    seed : random seed for the Poisson input.
    params : optional per-trial overrides of the model constants.
    """

    def __init__(self, brain: FastBrain, input_ids, silence=(), seed=0, params=None):
        self.brain = brain
        self.p = brain._params_for(params)
        self.input_ids = _as_root_ids(input_ids)
        self.input_idx = brain.index_of(self.input_ids)
        n = brain.n_neurons
        p = self.p
        self.dt_ms = p["dt"]
        dt_s = p["dt"] * 1e-3
        self._c = _update_constants(p)
        self._rfc = np.full(n, _timestep(p["t_rfc"] * 1e-3, dt_s), np.int64)
        self._rfc[self.input_idx] = 0          # model.poi: no refractory period
        self._silenced = np.zeros(n, np.bool_)
        sil = _as_root_ids(silence)
        self._silenced[brain.index_of(sil)] = True
        self.silence_ids = sil
        self._delay = int(p["t_dly"] * 1e-3 / dt_s + 0.5)   # Brian2 rounding
        self._w_syn = p["w_syn"] * 1e-3
        self._w_poi = self._w_syn * p["f_poi"]
        self._v_th, self._v_rst = p["v_th"] * 1e-3, p["v_rst"] * 1e-3
        self._rng = np.random.default_rng(np.random.SeedSequence(seed))
        # Neuron state (what FastBrain keeps inside one call).
        self._slot = np.full(n, -1, np.int32)
        self._act_id = np.empty(n, np.int32)
        self._v = np.empty(n)
        self._g = np.empty(n)
        self._ls = np.empty(n, np.int64)
        self._rf = np.empty(n, np.int64)
        self._n_active = 0
        self._rest = p["v_0"] * 1e-3
        self._pend_step = np.zeros(0, np.int64)
        self._pend_neu = np.zeros(0, np.int32)
        self.step_count = 0                    # global time step reached so far

    @property
    def time_ms(self):
        return self.step_count * self.dt_ms

    @property
    def n_active(self):
        """How many neurons have received any input so far this trial."""
        return int(self._n_active)

    def _steps_for(self, duration_ms):
        n = int(round(duration_ms / self.dt_ms))
        if n < 1:
            raise ValueError("window must be at least one time step")
        return n

    def step(self, rates_hz, duration_ms):
        """Run one window with Poisson input at ``rates_hz`` (one rate per
        ``input_ids`` entry, in Hz; or one number for all)."""
        n_steps = self._steps_for(duration_ms)
        rates = np.broadcast_to(np.asarray(rates_hz, float), self.input_idx.shape)
        prob = rates * self.dt_ms * 1e-3
        if (prob < 0).any() or (prob > 1).any():
            raise ValueError("rate x dt must be between 0 and 1")
        ev_ptr, ev_neuron = FastBrain._poisson_events(self._rng, self.input_idx, prob, n_steps)
        return self._advance(n_steps, ev_ptr, ev_neuron)

    def step_events(self, steps, root_ids, duration_ms):
        """Run one window with explicitly given input kicks: at local step
        ``steps[k]`` (0 = first step of this window) neuron ``root_ids[k]``
        gets one Poisson kick. Used by the tests to compare with FastBrain."""
        n_steps = self._steps_for(duration_ms)
        steps = np.asarray(steps, np.int64)
        idx = self.brain.index_of(root_ids) if len(root_ids) else np.zeros(0, np.int64)
        ev_ptr, ev_neuron = FastBrain._pack_events(steps, idx, n_steps)
        return self._advance(n_steps, ev_ptr, ev_neuron)

    def _advance(self, n_steps, ev_ptr, ev_neuron):
        b = self.brain
        c_g, c_v0, c_vg, c_vv = self._c
        start_ms = self.time_ms
        sp_step, sp_neu, n_in, n_del, n_act, rest = _run_window(
            self.step_count, n_steps, b._indptr, b._post, b._count, self._w_syn,
            self._silenced, self._rfc, ev_ptr, ev_neuron, self._w_poi, self._delay,
            c_g, c_v0, c_vg, c_vv, self._v_th, self._v_rst,
            self._slot, self._act_id, self._v, self._g, self._ls, self._rf,
            self._n_active, self._rest, self._pend_step, self._pend_neu)
        self._n_active = n_act
        self._rest = rest
        self._pend_step = sp_step[n_del:].copy()
        self._pend_neu = sp_neu[n_del:].copy()
        self.step_count += n_steps
        return WindowResult(start_ms=start_ms, duration_ms=n_steps * self.dt_ms,
                            spike_steps=sp_step[n_in:], spike_index=sp_neu[n_in:].astype(np.int64),
                            n_input_kicks=int(ev_neuron.size))

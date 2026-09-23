"""Phase 7 realism upgrades 1-3, each behind its own on/off switch.

What this is, in plain English
------------------------------
The baseline model (``sim/fast_engine.py``, a copy of Shiu et al. 2024) makes
three big simplifications. This file adds, one at a time, the three upgrades
PLAN.md Phase 7 asks for first:

1. **Synaptic delays that depend on distance** (switch ``delays``).
   Baseline: every spike reaches every target exactly 1.8 ms later.
   Upgrade: 1.8 ms (the synaptic part, kept) PLUS the time the spike needs to
   travel from the sending neuron to the receiving neuron. Travel time =
   distance / conduction speed.

2. **Conductance-based synapses** (switch ``conductance``).
   Baseline: each input synapse pushes the voltage by a fixed amount whatever
   the voltage already is ("current injection").
   Upgrade: each synapse opens ion channels. The push is proportional to how
   far the voltage is from the channel's "reversal potential" (the voltage at
   which that channel stops pushing). Excitatory (acetylcholine) channels push
   toward 0 mV; inhibitory (GABA, glutamate) chloride channels pull toward
   about -60 mV and cannot pull the neuron below that.

3. **Spike-frequency adaptation** (switch ``adaptation``).
   Baseline: a neuron driven steadily fires at a steady rate forever.
   Upgrade: every spike adds a little slow "brake" current that fades over
   ~100 ms, so a neuron driven for a long time slows down, like many real fly
   neurons do.

Everything else (the input protocol, thresholds, reset, refractory period,
how "silencing" works, the random input for a given seed) is exactly the
baseline's. With all three switches OFF this engine reproduces the baseline
engine spike for spike (tests/test_realism.py proves it on small networks and
on the whole brain). ``sim/fast_engine.py`` itself is not changed.

Published sources (full notes: docs/phase7-realism.md)
------------------------------------------------------
Upgrade 1 (delays)
  * Synaptic part, kept at 1.8 ms: Paul MM et al. (2015) "Bruchpilot and
    Synaptotagmin collaborate to drive rapid glutamate release and active zone
    differentiation", Front Cell Neurosci 9:29. Wild-type Drosophila synaptic
    delay 1.8 +/- 0.3 ms, measured from the PEAK of the presynaptic action
    potential at the terminal to EPSC onset (18 C). This is the source of the
    baseline's 1.8 ms, and it contains no travel time, so travel time is added
    on top.
  * Conduction speed, main value 0.20 m/s: Kottmeier R et al. (2020)
    "Wrapping glia regulates neuronal signaling speed and precision in the
    peripheral nervous system of Drosophila", Nat Commun 11:4491. Larval motor
    axons 0.196 m/s, sensory axons 0.129 m/s (mean axon radius 0.19 um).
  * Fast bound 2.07 m/s: Kadas D, Duch C, Consoulas C (2019) "Postnatal
    increases in axonal conduction velocity of an identified Drosophila
    interneuron...", eNeuro 6:ENEURO.0181-19.2019. Adult giant fiber (7 um
    thick, one of the thickest axons in the fly) 2.07 m/s at 24 h.
  * Distance: straight-line distance between the two neurons' FlyWire
    "anchor" points (a point on each neuron's main branch), from the Schlegel
    et al. 2024 annotation table for snapshot 630. Synapse-level positions are
    NOT in our data, and the real wire is longer than a straight line, so this
    under-estimates travel distance; the slow-speed run (0.129 m/s) covers a
    path ~1.5x longer than the straight line.

Upgrade 2 (conductances)
  * Excitatory reversal 0 mV: nicotinic acetylcholine receptors are
    non-selective cation channels (Lee D, O'Dowd DK 1999 J Neurosci 19:5311).
    Cholinergic EPSCs in cultured Drosophila Kenyon cells reverse at
    +8.9 +/- 1.7 mV (Su H, O'Dowd DK 2003 J Neurosci 23:9246); we use the
    standard 0 mV (driving force at rest 52 mV instead of 61 mV; the rescaling
    below makes the effect at rest identical either way).
  * Inhibitory reversal -60 mV (chloride): GABA (Rdl) and glutamate (GluCl,
    Liu WW & Wilson RI 2013 PNAS 110:10294) open chloride channels in fly
    central neurons. GABA-evoked currents in Drosophila larval central neurons
    reverse at -50 to -60 mV (Rohrbough J, Broadie K 2002 J Neurophysiol
    88:847); in adult l-LNv neurons at -45 to -50 mV (McCarthy EV et al. 2011
    J Neurosci 31:8181); in cultured Kenyon cells at -37 mV with a pipette
    solution whose chloride potential was -45 mV (Su & O'Dowd 2003). All of
    these are whole-cell recordings, where the pipette sets the chloride
    level, so the true in-vivo value is uncertain. -60 mV is the most
    hyperpolarised published value we found; -70 mV is run as a sensitivity
    check only (a common modelling choice, not a fly measurement).
  * Weight rescaling (explicit): one synapse must move a neuron sitting at
    rest (v_0 = -52 mV) by the same amount as in the baseline. In the
    baseline one synapse adds w_syn = 0.275 mV to g. In the conductance model
    its effect at rest is g_exc * (E_exc - v_0), so
        g_exc per synapse = w_syn / (E_exc - v_0) = 0.275 / 52 = 0.00529
        g_inh per synapse = w_syn / (v_0 - E_inh) = 0.275 / 8  = 0.0344
    (conductances in units of the neuron's own leak conductance). So at rest
    the two models agree exactly for a single small input; they differ only
    when the voltage moves (excitation weakens slightly near threshold,
    inhibition gets stronger near threshold and vanishes at -60 mV).

Upgrade 3 (adaptation)
  * Mechanism: a slow potassium "brake" current. Drosophila neurons have the
    calcium-activated SK channel (dSK; Abou Tayoun AN et al. 2011 J Neurosci
    31:13897), and SK channels cause ~100 ms firing pauses in Drosophila
    neurons (median pause 104 ms wild type vs 47 ms with SK knocked down;
    Onodera K et al. 2017 eLife 6:e29754). Main time constant: 100 ms.
  * Strength: calibrated so that a model neuron given a 600 ms current step
    at 2.5x its threshold current slows to f_last / f_first = 0.7, the
    boundary Zhao ML & Wu CF (1997) J Neurosci 17:2187 used to call a
    cultured Drosophila central neuron "adaptive" (32% of wild-type neurons;
    steps of 600 ms at 2-3x threshold). No fly measurement of the adaptation
    time constant itself was found; see docs/phase7-realism.md.

Model equations (voltages in mV, times in ms)
---------------------------------------------
Baseline:    dv/dt = (v_0 - v + g) / t_mbr,  dg/dt = -g / tau
Conductance: dv/dt = (v_0 - v + ge (E_exc - v) + gi (E_inh - v)) / t_mbr,
             dge/dt = -ge / tau,  dgi/dt = -gi / tau
Adaptation:  "- a" is added inside the brackets of dv/dt,
             da/dt = -a / tau_adapt, and a += adapt_mV at every spike.

Numerics: the baseline and the adaptation-only model use exact solutions over
each 0.1 ms step (the same formula style as Brian2). The conductance model has
no simple exact solution, so each step uses the exact solution for
conductances held at their average value over that step (an "exponential
integrator"); tests compare it with a high-accuracy ODE solver.
"""

from __future__ import annotations

import math
import time
from concurrent.futures import ThreadPoolExecutor

import numba as nb
import numpy as np
import pandas as pd

from sim.fast_engine import (
    DEFAULT_PARAMS, PROJECT_ROOT, SimResult, FastBrain, _NEVER, _as_root_ids,
    _timestep, _update_constants,
)

CACHE_DIR = PROJECT_ROOT / "data" / "cache"

#: Realism switches and their published values. All three switches default to
#: OFF, which is exactly the baseline model.
REALISM_DEFAULTS = {
    # --- upgrade 1: distance-dependent delays ---
    "delays": False,
    "velocity_m_per_s": 0.20,   # Kottmeier et al. 2020 (0.196 m/s motor axons)
    "distance": "anchor",       # "anchor" (main-branch point) or "soma"
    # synaptic part of the delay = params["t_dly"] (1.8 ms, Paul et al. 2015)
    # --- upgrade 2: conductance-based synapses ---
    "conductance": False,
    "E_exc_mV": 0.0,            # nAChR, cation channel
    "E_inh_mV": -60.0,          # GABA-A (Rdl) / GluCl chloride channels
    # One global factor on every synaptic conductance (NOT on the stimulus
    # kicks). 1.0 = matched to the baseline at rest. Shiu et al. fitted their
    # one free parameter (w_syn) so sugar 100 Hz drives MN9 strongly; a
    # conductance model needs that one number re-fitted the same way
    # (experiments/phase7/run_phase7.py, fit_cond_scale).
    "cond_weight_scale": 1.0,
    # --- upgrade 3: spike-frequency adaptation ---
    "adaptation": False,
    "tau_adapt_ms": 100.0,      # SK-channel pauses ~100 ms (Onodera et al. 2017)
    "adapt_mV": None,           # None = calibrate to f_last/f_first = ADAPT_TARGET_RATIO
}

#: Zhao & Wu 1997: "adaptive" = f_last / f_first < 0.7 over a 600 ms step at
#: 2-3x threshold. We calibrate to the boundary value, at 2.5x threshold.
ADAPT_TARGET_RATIO = 0.7
ADAPT_STEP_MS = 600.0
ADAPT_STEP_X_THRESHOLD = 2.5


# ---------------------------------------------------------------------------
# The compiled inner loop (one trial), with the three switches
# ---------------------------------------------------------------------------
@nb.njit(cache=True, nogil=True)
def _simulate_trial_realism(n_steps, grp_ptr, grp_lo, grp_d, n_slots, post, count,
                            w_exc, w_inh, silenced, rfc_steps, ev_ptr, ev_neuron, w_poi,
                            c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
                            cond, E_e, E_i, dt_over_tm, g_avg,
                            adapt, c_a, c_va, a_avg, a_inc):
    """One trial. Voltages in volts, like the baseline kernel.

    Identical to ``fast_engine._simulate_trial`` when ``cond`` and ``adapt``
    are False and every connection has the same delay; the only structural
    difference is how spikes wait for their delay:

    * Each neuron's outgoing connections are grouped by delay (in the
      baseline there is one group per neuron, in the original order).
    * When a neuron spikes, each of its groups is put in the "mailbox" for
      the step it must arrive in (a ring of ``n_slots`` mailboxes).
    * Each step, the mailbox for that step is opened and its groups are
      delivered in the order they were posted. With one shared delay this is
      exactly the baseline's order (neuron-index order within a step), so the
      additions happen in the same order and give the same rounding.
    """
    n_neurons = rfc_steps.shape[0]
    slot = np.full(n_neurons, -1, np.int32)
    act_id = np.empty(n_neurons, np.int32)
    v_a = np.empty(n_neurons)
    g_a = np.empty(n_neurons)       # baseline g, or ge (excitatory conductance)
    gi_a = np.empty(n_neurons)      # gi (inhibitory conductance), conductance mode only
    ad_a = np.empty(n_neurons)      # adaptation current a (volts), adaptation mode only
    ls_a = np.empty(n_neurons, np.int64)
    rf_a = np.empty(n_neurons, np.int64)
    n_active = 0
    rest = v_0

    cap = 4096
    sp_step = np.empty(cap, np.int32)
    sp_neu = np.empty(cap, np.int32)
    n_sp = 0

    qcap = 1024
    q = np.empty((n_slots, qcap), np.int32)
    qn = np.zeros(n_slots, np.int64)

    n_rec = rec_idx.shape[0]
    vrec = np.empty((n_steps, n_rec))

    for n in range(n_steps):
        for r in range(n_rec):
            k = slot[rec_idx[r]]
            vrec[n, r] = v_a[k] if k >= 0 else rest

        if n_sp + n_active > cap:
            cap = 2 * (n_sp + n_active)
            tmp_s = np.empty(cap, np.int32)
            tmp_n = np.empty(cap, np.int32)
            tmp_s[:n_sp] = sp_step[:n_sp]
            tmp_n[:n_sp] = sp_neu[:n_sp]
            sp_step = tmp_s
            sp_neu = tmp_n

        # 'groups' slot: voltage update.
        rest = c_v0 + ((c_vg * 0.0) + (c_vv * rest))
        first_new = n_sp
        for k in range(n_active):
            spiked = False
            if n - ls_a[k] >= rf_a[k]:                    # not refractory
                gi = g_a[k]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                if cond:
                    gh = gi_a[k]
                    if -1e-200 < gh < 1e-200:
                        gh = 0.0
                    ge_m = gi * g_avg                     # average over the step
                    gi_m = gh * g_avg
                    gt = 1.0 + ge_m + gi_m
                    num = v_0 + ge_m * E_e + gi_m * E_i
                    if adapt:
                        num -= ad_a[k] * a_avg
                    vinf = num / gt
                    vi = vinf + (v_a[k] - vinf) * math.exp(-dt_over_tm * gt)
                    gi_a[k] = c_g * gh
                else:
                    vi = c_v0 + ((c_vg * gi) + (c_vv * v_a[k]))
                    if adapt:
                        vi -= c_va * ad_a[k]
                g_a[k] = c_g * gi
                if vi > v_th:
                    sp_step[n_sp] = n
                    sp_neu[n_sp] = act_id[k]
                    n_sp += 1
                    ls_a[k] = n
                    v_a[k] = v_rst
                    g_a[k] = 0.0
                    if cond:
                        gi_a[k] = 0.0
                    spiked = True
                else:
                    v_a[k] = vi
            # The adaptation current keeps fading every step, refractory or
            # not, and jumps up by a_inc at each spike.
            if adapt:
                ad_a[k] *= c_a
                if spiked:
                    ad_a[k] += a_inc

        for a in range(first_new + 1, n_sp):
            x = sp_neu[a]
            b = a - 1
            while b >= first_new and sp_neu[b] > x:
                sp_neu[b + 1] = sp_neu[b]
                b -= 1
            sp_neu[b + 1] = x

        # Post this step's spikes into the mailboxes of their arrival steps.
        for a in range(first_new, n_sp):
            j = sp_neu[a]
            if silenced[j]:
                continue
            for gidx in range(grp_ptr[j], grp_ptr[j + 1]):
                sl = (n + grp_d[gidx]) % n_slots
                if qn[sl] >= qcap:
                    qcap2 = 2 * qcap
                    q2 = np.empty((n_slots, qcap2), np.int32)
                    for r2 in range(n_slots):
                        for c2 in range(qn[r2]):
                            q2[r2, c2] = q[r2, c2]
                    q = q2
                    qcap = qcap2
                q[sl, qn[sl]] = gidx
                qn[sl] += 1

        # 'synapses' slot, part 1: Poisson kicks (unchanged from baseline).
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
                gi_a[k] = 0.0
                ad_a[k] = 0.0
                ls_a[k] = _NEVER
                rf_a[k] = rfc_steps[i]
            if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                v_a[k] += w_poi

        # 'synapses' slot, part 2: open this step's mailbox.
        sl = n % n_slots
        for qi in range(qn[sl]):
            gidx = q[sl, qi]
            for s in range(grp_lo[gidx], grp_lo[gidx + 1]):
                i = post[s]
                k = slot[i]
                if k < 0:
                    k = n_active
                    n_active += 1
                    slot[i] = k
                    act_id[k] = i
                    v_a[k] = rest
                    g_a[k] = 0.0
                    gi_a[k] = 0.0
                    ad_a[k] = 0.0
                    ls_a[k] = _NEVER
                    rf_a[k] = rfc_steps[i]
                if ls_a[k] != n and n - ls_a[k] >= rf_a[k]:
                    if cond:
                        c = count[s]
                        if c > 0:
                            g_a[k] += c * w_exc
                        else:
                            gi_a[k] += (-c) * w_inh
                    else:
                        g_a[k] += count[s] * w_exc
        qn[sl] = 0

    return sp_step[:n_sp].copy(), sp_neu[:n_sp].copy(), vrec, n_active


# ---------------------------------------------------------------------------
# Single-neuron helper (calibration and tests)
# ---------------------------------------------------------------------------
@nb.njit(cache=True)
def _step_current_trace(I, n_steps, c_v0, c_vv, v_0, v_th, v_rst, rfc_steps,
                        adapt, c_a, c_va, a_inc):
    """One neuron, constant input I (volts, "current x leak resistance"),
    baseline current-based model with optional adaptation. Uses the same
    update formulas as the kernel (constant input: exact update)."""
    v = v_0
    a = 0.0
    last = -(1 << 40)
    spikes = np.empty(n_steps, np.int64)
    ns = 0
    c_vI = 1.0 - c_vv
    for n in range(n_steps):
        spiked = False
        if n - last >= rfc_steps:
            vi = c_v0 + (c_vv * v) + c_vI * I
            if adapt:
                vi -= c_va * a
            if vi > v_th:
                spikes[ns] = n
                ns += 1
                last = n
                v = v_rst
                spiked = True
            else:
                v = vi
        if adapt:
            a *= c_a
            if spiked:
                a += a_inc
    return spikes[:ns]


def _adapt_constants(p, tau_adapt_ms):
    """Per-step multipliers for the adaptation current a:
    c_a  : how much of a is left after one step (exp(-dt/tau_a));
    c_va : exact effect of a (decaying over the step) on v, same formula
           style as the baseline's effect of g on v;
    a_avg: average of a over the step / a at the start (conductance mode)."""
    dt = p["dt"] * 1e-3
    ta = tau_adapt_ms * 1e-3
    tm = p["t_mbr"] * 1e-3
    if abs(ta - tm) < 1e-12:
        raise ValueError("tau_adapt must differ from t_mbr")
    c_a = math.exp(-dt / ta)
    c_va = ta / (ta - tm) * (math.exp(-dt / ta) - math.exp(-dt / tm))
    a_avg = ta / dt * (1.0 - c_a)
    return c_a, c_va, a_avg


def adaptation_ratio(adapt_mV, tau_adapt_ms, params=None,
                     x_threshold=ADAPT_STEP_X_THRESHOLD, step_ms=ADAPT_STEP_MS):
    """f_last / f_first for one model neuron given a ``step_ms`` current step
    at ``x_threshold`` times its threshold current (Zhao & Wu 1997 protocol).
    Also returns (f_first, f_last, n_spikes)."""
    p = dict(DEFAULT_PARAMS)
    if params:
        p.update(params)
    _, c_v0, _, c_vv = _update_constants(p)
    dt_s = p["dt"] * 1e-3
    I = x_threshold * (p["v_th"] - p["v_0"]) * 1e-3
    c_a, c_va, _ = _adapt_constants(p, tau_adapt_ms)
    rfc = _timestep(p["t_rfc"] * 1e-3, dt_s)
    sp = _step_current_trace(I, int(round(step_ms / p["dt"])), c_v0, c_vv, p["v_0"] * 1e-3,
                             p["v_th"] * 1e-3, p["v_rst"] * 1e-3, rfc,
                             adapt_mV > 0, c_a, c_va, adapt_mV * 1e-3)
    if sp.size < 3:
        return float("nan"), float("nan"), float("nan"), int(sp.size)
    isi = np.diff(sp) * p["dt"]
    f_first, f_last = 1000.0 / isi[0], 1000.0 / isi[-1]
    return f_last / f_first, f_first, f_last, int(sp.size)


def calibrate_adaptation(tau_adapt_ms, target=ADAPT_TARGET_RATIO, params=None):
    """The adaptation increment (mV per spike) that gives f_last/f_first =
    ``target`` in the Zhao & Wu protocol (bisection; ratio falls as the
    increment grows)."""
    lo, hi = 0.0, 5.0
    while adaptation_ratio(hi, tau_adapt_ms, params)[0] > target:
        hi *= 2
        if hi > 1e3:
            raise RuntimeError("could not reach the target adaptation ratio")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if adaptation_ratio(mid, tau_adapt_ms, params)[0] > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# ---------------------------------------------------------------------------
# The engine
# ---------------------------------------------------------------------------
class RealisticBrain(FastBrain):
    """The baseline whole-brain model plus the Phase 7 upgrades 1-3.

    Same interface as ``FastBrain`` (``run``, ``run_with_input_events``, same
    results object, same random input for the same seed). The upgrades are
    switched on with ``realism={...}`` at construction or ``set_realism``.

    >>> brain = RealisticBrain("630", n_threads=2)
    >>> brain.set_realism(delays=True)          # upgrade 1 on
    >>> res = brain.run(excite=sugar_ids, rate_hz=100, n_trials=30, seed=0)
    """

    def __init__(self, snapshot="630", params=None, n_threads=1, realism=None, **kw):
        super().__init__(snapshot, params, n_threads, **kw)
        # Reading the connectome leaves ~1 GB of freed memory parked in
        # pyarrow's allocator; hand it back to the computer (the machine is
        # shared with other simulations).
        try:
            import pyarrow as pa
            pa.default_memory_pool().release_unused()
        except Exception:  # noqa: BLE001 - only a memory courtesy
            pass
        self._init_realism(realism)

    @classmethod
    def from_arrays(cls, root_ids, pre_index, post_index, signed_count, params=None,
                    n_threads=1, positions_um=None, realism=None):
        """Tiny test networks. ``positions_um``: (n, 3) array of positions in
        micrometres used for the distance-dependent delays."""
        self = super().from_arrays(root_ids, pre_index, post_index, signed_count,
                                   params=params, n_threads=n_threads)
        self._init_realism(realism)
        if positions_um is not None:
            pos = np.asarray(positions_um, float)
            self._positions = {"anchor": pos, "soma": pos}
        return self

    def _init_realism(self, realism):
        self.realism = dict(REALISM_DEFAULTS)
        self._positions = None
        self._length_cache = {}
        self._group_cache = {}
        self._adapt_cache = {}
        self.distance_notes = {}
        if realism:
            self.set_realism(**realism)

    def set_realism(self, **kw):
        unknown = set(kw) - set(REALISM_DEFAULTS)
        if unknown:
            raise KeyError(f"unknown realism option(s) {sorted(unknown)}; "
                           f"known: {sorted(REALISM_DEFAULTS)}")
        self.realism.update(kw)
        if self.realism["distance"] not in ("anchor", "soma"):
            raise ValueError("distance must be 'anchor' or 'soma'")
        return self

    # -- upgrade 1 helpers ----------------------------------------------------
    def _load_positions(self):
        """Neuron positions (micrometres) for this snapshot, from the cached
        connectome table (built by sim/connectome.py from the Schlegel et al.
        annotation file). Two points per neuron: the 'anchor' (on the main
        branch) and the soma (cell body; none for sensory neurons, whose cell
        bodies sit outside the brain)."""
        if self._positions is not None:
            return self._positions
        f = CACHE_DIR / f"connectome_{self.snapshot}_neurons.parquet"
        if not f.exists():
            raise FileNotFoundError(f"{f} missing: build it with sim.connectome.load_connectome('{self.snapshot}')")
        df = pd.read_parquet(f, columns=["root_id", "anchor_x_nm", "anchor_y_nm", "anchor_z_nm",
                                         "soma_x_nm", "soma_y_nm", "soma_z_nm"])
        if not np.array_equal(df["root_id"].to_numpy(np.int64), self.root_ids):
            raise ValueError("position table is not in the engine's neuron order")
        anc = df[["anchor_x_nm", "anchor_y_nm", "anchor_z_nm"]].to_numpy(float) / 1000.0
        som = df[["soma_x_nm", "soma_y_nm", "soma_z_nm"]].to_numpy(float) / 1000.0
        # A handful of anchor points sit far outside the brain (2 in snapshot
        # 630, apparently stored in the wrong units). Anything outside the box
        # spanned by all cell bodies (plus a 50 um margin) is treated as unknown.
        lo = np.nanmin(som, axis=0) - 50.0
        hi = np.nanmax(som, axis=0) + 50.0
        bad = ~np.all((anc >= lo) & (anc <= hi), axis=1) & ~np.isnan(anc).any(axis=1)
        anc[bad] = np.nan
        # anchor missing -> use the soma
        anc_f = anc.copy()
        miss = np.isnan(anc_f).any(axis=1)
        anc_f[miss] = som[miss]
        som_f = som.copy()
        miss_s = np.isnan(som_f).any(axis=1)
        som_f[miss_s] = anc[miss_s]          # soma missing (sensory) -> anchor
        self.distance_notes = {
            "n_neurons": int(self.n_neurons),
            "anchor_present": int((~np.isnan(anc).any(axis=1)).sum() + bad.sum()),
            "anchor_out_of_brain_dropped": int(bad.sum()),
            "soma_present": int((~miss_s).sum()),
            "no_position_at_all": int(np.isnan(anc_f).any(axis=1).sum()),
        }
        self._positions = {"anchor": anc_f, "soma": som_f}
        return self._positions

    def connection_lengths_um(self, distance=None):
        """Straight-line distance (um) for every connection, in the engine's
        connection order. Connections touching a neuron with no position get
        the median distance (flagged in ``distance_notes``)."""
        distance = distance or self.realism["distance"]
        if distance in self._length_cache:
            return self._length_cache[distance]
        pos = self._load_positions()[distance]
        d = np.empty(self.n_connections, np.float32)
        # In chunks of neurons, so a (connections x 3) array never has to fit
        # in memory at once.
        step = 5000
        for j0 in range(0, self.n_neurons, step):
            j1 = min(self.n_neurons, j0 + step)
            s0, s1 = int(self._indptr[j0]), int(self._indptr[j1])
            if s1 == s0:
                continue
            pre = np.repeat(np.arange(j0, j1), np.diff(self._indptr[j0:j1 + 1]))
            diff = pos[pre] - pos[self._post[s0:s1]]
            d[s0:s1] = np.sqrt((diff * diff).sum(axis=1))
        nan = np.isnan(d)
        med = float(np.nanmedian(d)) if (~nan).any() else 0.0
        d[nan] = med
        self.distance_notes[f"{distance}_connections_without_position"] = int(nan.sum())
        self._length_cache[distance] = d
        return d

    def delay_steps_per_connection(self, p=None):
        """Delay of every connection in time steps, rounded the way Brian2
        rounds delays. Upgrade 1 off: one shared delay (the baseline's)."""
        p = self._params_for(p)
        dt_s = p["dt"] * 1e-3
        base = int(p["t_dly"] * 1e-3 / dt_s + 0.5)
        if not self.realism["delays"]:
            return np.full(self.n_connections, base, np.int16)
        v = float(self.realism["velocity_m_per_s"])        # 1 m/s = 1 um/us = 1000 um/ms
        if v <= 0:
            raise ValueError("velocity must be > 0")
        key = (v, self.realism["distance"], p["t_dly"], p["dt"])
        cached = getattr(self, "_dsteps_cache", None)
        if cached is not None and cached[0] == key:
            return cached[1]
        L = self.connection_lengths_um()
        delay_ms = p["t_dly"] + L.astype(np.float64) / (1000.0 * v)   # float64, as before
        steps = np.maximum(np.floor(delay_ms / p["dt"] + 0.5), 1)
        if steps.max() > 30000:
            raise ValueError("delays longer than 3 s are not supported")
        steps = steps.astype(np.int16)
        del delay_ms
        self._dsteps_cache = (key, steps)
        return steps

    def _groups_for(self, dsteps):
        """Group each neuron's outgoing connections by delay (stable, so with
        one shared delay the original order is kept exactly)."""
        c = self._group_cache
        if c and c["dsteps"].shape == dsteps.shape and (
                c["dsteps"] is dsteps or np.array_equal(c["dsteps"], dsteps)):
            return c["groups"]
        self._group_cache = {}                # keep one layout in memory at a time
        n = self.n_neurons
        has = np.diff(self._indptr) > 0
        if dsteps.size == 0 or dsteps.min() == dsteps.max():
            # One shared delay: one group per neuron, original order, no copy.
            idx = np.flatnonzero(has)
            grp_ptr = np.zeros(n + 1, np.int64)
            np.cumsum(has.astype(np.int64), out=grp_ptr[1:])
            # group g covers connections lo[g] .. lo[g + 1] - 1
            lo = np.append(self._indptr[idx], self.n_connections).astype(np.int64)
            d = int(dsteps[0]) if dsteps.size else 1
            out = (grp_ptr, lo, np.full(idx.size, d, np.int16), self._post, self._count)
        else:
            # Connections are already grouped by sender; a stable sort on
            # (sender, delay) orders each sender's connections by delay while
            # keeping the file order inside each delay.
            pre = np.repeat(np.arange(n, dtype=np.int64), np.diff(self._indptr))
            key2 = pre * (int(dsteps.max()) + 1) + dsteps.astype(np.int64)
            del pre
            order = np.argsort(key2, kind="stable")
            key2 = key2[order]
            post = np.ascontiguousarray(self._post[order])
            count = np.ascontiguousarray(self._count[order])
            del order
            new = np.ones(key2.size, bool)
            new[1:] = key2[1:] != key2[:-1]
            starts = np.flatnonzero(new)
            del new
            dmax1 = int(dsteps.max()) + 1
            gkey = key2[starts]
            del key2
            gpre, gd = gkey // dmax1, gkey % dmax1
            del gkey
            grp_ptr = np.zeros(n + 1, np.int64)
            np.cumsum(np.bincount(gpre, minlength=n), out=grp_ptr[1:])
            # group g covers connections lo[g] .. lo[g + 1] - 1
            lo = np.append(starts, self.n_connections).astype(np.int64)
            out = (grp_ptr, lo, gd.astype(np.int16), post, count)
        self._group_cache = {"dsteps": dsteps, "groups": out}
        return out

    def adaptation_increment_mV(self, p=None):
        """Per-spike adaptation increment (mV): the explicit value, or the
        Zhao & Wu 1997 calibration for the chosen time constant."""
        r = self.realism
        if r["adapt_mV"] is not None:
            return float(r["adapt_mV"])
        p = self._params_for(p)
        key = (float(r["tau_adapt_ms"]), tuple(sorted(p.items())))
        if key not in self._adapt_cache:
            self._adapt_cache[key] = calibrate_adaptation(r["tau_adapt_ms"], params=p)
        return self._adapt_cache[key]

    def describe(self, p=None, dsteps=None):
        """Plain summary of the switches and the numbers actually used."""
        p = self._params_for(p)
        r = dict(self.realism)
        out = {"delays": r["delays"], "conductance": r["conductance"],
               "adaptation": r["adaptation"]}
        if r["delays"]:
            if dsteps is None:
                dsteps = self.delay_steps_per_connection(p)
            d = dsteps * p["dt"]
            out.update(velocity_m_per_s=r["velocity_m_per_s"], distance=r["distance"],
                       delay_ms_mean=float(d.mean()), delay_ms_median=float(np.median(d)),
                       delay_ms_p95=float(np.percentile(d, 95)), delay_ms_max=float(d.max()))
        if r["conductance"]:
            v0 = p["v_0"]
            out.update(E_exc_mV=r["E_exc_mV"], E_inh_mV=r["E_inh_mV"],
                       cond_weight_scale=r["cond_weight_scale"],
                       g_exc_per_synapse=r["cond_weight_scale"] * p["w_syn"] / (r["E_exc_mV"] - v0),
                       g_inh_per_synapse=r["cond_weight_scale"] * p["w_syn"] / (v0 - r["E_inh_mV"]))
        if r["adaptation"]:
            out.update(tau_adapt_ms=r["tau_adapt_ms"],
                       adapt_mV=self.adaptation_increment_mV(p))
        return out

    # -- running ---------------------------------------------------------------
    def run_baseline(self, *args, **kw):
        """Run the UNMODIFIED baseline engine (sim/fast_engine.py's own compiled
        loop) on this same brain object, ignoring every realism switch. Same
        arguments as ``run``. Lets experiments compare with and without an
        upgrade without loading a second whole brain into memory."""
        self._use_baseline_engine = True
        try:
            return self.run(*args, **kw)
        finally:
            self._use_baseline_engine = False

    def _run_events(self, events, exc_idx, silence, n_steps, p, record_v):
        if getattr(self, "_use_baseline_engine", False):
            return FastBrain._run_events(self, events, exc_idx, silence, n_steps, p, record_v)
        t0 = time.perf_counter()
        r = self.realism
        dt_s = p["dt"] * 1e-3
        c_g, c_v0, c_vg, c_vv = _update_constants(p)
        rfc = np.full(self.n_neurons, _timestep(p["t_rfc"] * 1e-3, dt_s), np.int64)
        rfc[exc_idx] = 0
        silenced = np.zeros(self.n_neurons, np.bool_)
        sil_ids = _as_root_ids(silence)
        silenced[self.index_of(sil_ids)] = True
        rec_ids = _as_root_ids(record_v)
        rec_idx = self.index_of(rec_ids).astype(np.int64)
        w_syn = p["w_syn"] * 1e-3
        w_poi = w_syn * p["f_poi"]
        v_0, v_th, v_rst = p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3

        dsteps = self.delay_steps_per_connection(p)
        grp_ptr, grp_lo, grp_d, post, count = self._groups_for(dsteps)
        n_slots = int(grp_d.max()) + 1 if grp_d.size else 2

        cond = bool(r["conductance"])
        if cond:
            E_e, E_i = r["E_exc_mV"] * 1e-3, r["E_inh_mV"] * 1e-3
            if not (E_e > v_0 > E_i):
                raise ValueError("need E_inh < v_0 < E_exc for the rescaling at rest")
            k = float(r["cond_weight_scale"])
            w_exc = k * w_syn / (E_e - v_0)       # conductance per synapse (x leak)
            w_inh = k * w_syn / (v_0 - E_i)
        else:
            E_e = E_i = 0.0
            w_exc, w_inh = w_syn, 0.0
        tau_s = p["tau"] * 1e-3
        dt_over_tm = dt_s / (p["t_mbr"] * 1e-3)
        g_avg = tau_s / dt_s * (1.0 - math.exp(-dt_s / tau_s))

        adapt = bool(r["adaptation"])
        if adapt:
            c_a, c_va, a_avg = _adapt_constants(p, r["tau_adapt_ms"])
            a_inc = self.adaptation_increment_mV(p) * 1e-3
        else:
            c_a = c_va = a_avg = a_inc = 0.0

        def one(ev):
            return _simulate_trial_realism(
                n_steps, grp_ptr, grp_lo, grp_d, n_slots, post, count,
                w_exc, w_inh, silenced, rfc, ev[0], ev[1], w_poi,
                c_g, c_v0, c_vg, c_vv, v_0, v_th, v_rst, rec_idx,
                cond, E_e, E_i, dt_over_tm, g_avg,
                adapt, c_a, c_va, a_avg, a_inc)

        if self.n_threads > 1 and len(events) > 1:
            with ThreadPoolExecutor(self.n_threads) as pool:
                outs = list(pool.map(one, events))
        else:
            outs = [one(ev) for ev in events]

        trial = np.concatenate([np.full(o[0].size, k, np.int32) for k, o in enumerate(outs)]) \
            if outs else np.zeros(0, np.int32)
        step = np.concatenate([o[0] for o in outs]) if outs else np.zeros(0, np.int32)
        neuron = np.concatenate([o[1] for o in outs]) if outs else np.zeros(0, np.int32)
        voltages = {int(rid): np.stack([o[2][:, k] for o in outs])
                    for k, rid in enumerate(rec_ids)}
        pr = dict(p)
        key = (tuple(sorted((k, str(v)) for k, v in r.items())),
               tuple(sorted(p.items())))
        if getattr(self, "_describe_key", None) != key:
            self._describe_cache = self.describe(p, dsteps)
            self._describe_key = key
        pr["realism"] = dict(self._describe_cache)
        return SimResult(
            root_ids=self.root_ids, n_trials=len(events), duration_ms=n_steps * p["dt"],
            dt_ms=p["dt"], seed=None, excite={}, silence=[int(s) for s in sil_ids],
            params=pr, trial=trial, neuron=neuron, step=step,
            neurons_reached=[int(o[3]) for o in outs], voltages_V=voltages,
            wall_time_s=time.perf_counter() - t0,
        )

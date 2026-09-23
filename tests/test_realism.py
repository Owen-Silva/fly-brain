"""Tests for sim/realism.py (PLAN.md Phase 7, upgrades 1-3).

The most important test: with every upgrade switched OFF, the new engine
gives exactly the same spikes (same neurons, same time steps, same voltages)
as the untouched baseline engine sim/fast_engine.py, for the same seed.
Then one group of tests per upgrade checks that it does what the published
biology says and nothing else.
"""

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from sim.fast_engine import DEFAULT_PARAMS, FastBrain, _update_constants
from sim.realism import (ADAPT_TARGET_RATIO, RealisticBrain, adaptation_ratio,
                         calibrate_adaptation)

MN9 = 720575940660219265
SUGAR_630 = [  # data/reference/example.ipynb, `neu_sugar`
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _random_arrays(rng, n, p_conn, max_count, frac_exc):
    mask = rng.random((n, n)) < p_conn
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    perm = rng.permutation(pre.size)                # file order is not sorted
    pre, post = pre[perm], post[perm]
    count = rng.integers(1, max_count + 1, pre.size)
    sign = np.where(rng.random(n) < frac_exc, 1, -1)[pre]
    ids = (720575940600000000 + rng.choice(10**8, n, replace=False)).astype(np.int64)
    return ids, pre, post, sign * count


def _both(ids, pre, post, signed, **kw):
    base = FastBrain.from_arrays(ids, pre, post, signed)
    new = RealisticBrain.from_arrays(ids, pre, post, signed, **kw)
    return base, new


def _same(a, b):
    return (np.array_equal(a.trial, b.trial) and np.array_equal(a.step, b.step)
            and np.array_equal(a.neuron, b.neuron))


def _chain(counts, positions_um=None, realism=None):
    n = len(counts) + 1
    return RealisticBrain.from_arrays(np.arange(n, dtype=np.int64) + 10**17, np.arange(n - 1),
                                      np.arange(1, n), np.asarray(counts),
                                      positions_um=positions_um, realism=realism)


def _two_inputs(c_exc, c_inh, realism=None):
    """Neuron 0 (excitatory, c_exc synapses) and neuron 1 (inhibitory,
    c_inh synapses) both onto neuron 2."""
    ids = np.arange(3, dtype=np.int64) + 10**17
    return RealisticBrain.from_arrays(ids, [0, 1], [2, 2], [c_exc, -c_inh], realism=realism)


# ---------------------------------------------------------------------------
# 0. all switches off == baseline, exactly
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_all_off_is_the_baseline_exactly(seed):
    rng = np.random.default_rng(seed)
    ids, pre, post, signed = _random_arrays(rng, 80, 0.12, 60, 0.7)
    base, new = _both(ids, pre, post, signed)
    kw = dict(excite=ids[:6], duration_ms=300, n_trials=3, seed=seed, rate_hz=180,
              silence=ids[10:12], record_v=ids[20:23])
    a, b = base.run(**kw), new.run(**kw)
    assert a.step.size > 100                         # the network actually did something
    assert _same(a, b)
    for k in a.voltages_V:
        assert np.array_equal(a.voltages_V[k], b.voltages_V[k])
    # the helper that runs the untouched baseline loop on the same object agrees too
    c = new.run_baseline(**kw)
    assert _same(a, c)


def test_switches_on_but_neutral_are_the_baseline_exactly():
    """Delays on with infinite speed, adaptation on with zero strength:
    same spikes as the baseline (proves those code paths add nothing extra)."""
    rng = np.random.default_rng(5)
    ids, pre, post, signed = _random_arrays(rng, 60, 0.15, 60, 0.7)
    pos = rng.random((60, 3)) * 300.0
    base, new = _both(ids, pre, post, signed, positions_um=pos)
    kw = dict(excite=ids[:5], duration_ms=300, n_trials=2, seed=1, rate_hz=200)
    a = base.run(**kw)
    new.set_realism(delays=True, velocity_m_per_s=1e12, adaptation=True, adapt_mV=0.0)
    assert _same(a, new.run(**kw))


# ---------------------------------------------------------------------------
# 1. distance-dependent delays
# ---------------------------------------------------------------------------
def test_delay_adds_travel_time():
    # 200 um apart at 0.2 m/s = 1.0 ms travel = 10 extra steps on top of 1.8 ms
    pos = np.array([[0.0, 0.0, 0.0], [200.0, 0.0, 0.0]])
    brain = _chain([300], positions_um=pos)
    ids = brain.root_ids
    ev = [(np.array([10]), ids[:1])]
    off = brain.run_with_input_events(ev, excite=ids[:1], duration_ms=10.0, record_v=ids[1:])
    brain.set_realism(delays=True, velocity_m_per_s=0.2)
    on = brain.run_with_input_events(ev, excite=ids[:1], duration_ms=10.0, record_v=ids[1:])
    assert brain.delay_steps_per_connection().tolist() == [28]
    s_off = dict(zip(off.neuron.tolist(), off.step.tolist()))
    s_on = dict(zip(on.neuron.tolist(), on.step.tolist()))
    assert s_on[0] == s_off[0] == 11
    assert s_on[1] - s_off[1] == 10                  # target fires exactly 1 ms later
    v_off, v_on = off.voltages_V[int(ids[1])][0], on.voltages_V[int(ids[1])][0]
    assert np.array_equal(v_on[10:], v_off[:-10])    # same response, shifted by 10 steps


def _reference_hetero_delays(n, pre, post, signed, dsteps, exc_idx, events, n_steps, p):
    """Slow, obvious pure-Python version of the model with one delay per
    connection. Updates every neuron every step and delivers, for each
    arrival step, spikes in (spike step, neuron) order and each spike's
    connections in file order: the order the engine promises."""
    c_g, c_v0, c_vg, c_vv = _update_constants(p)
    v0, vth, vrst = p["v_0"] * 1e-3, p["v_th"] * 1e-3, p["v_rst"] * 1e-3
    w = p["w_syn"] * 1e-3
    w_poi = w * p["f_poi"]
    rf = np.full(n, int(round(p["t_rfc"] / p["dt"])))
    rf[exc_idx] = 0
    v = np.full(n, v0)
    g = np.zeros(n)
    last = np.full(n, -(1 << 40))
    out = [[] for _ in range(n)]
    for s in range(pre.size):
        out[pre[s]].append(s)
    spikes = []                                      # (step, neuron) in firing order
    ev_steps, ev_neu = events
    for t in range(n_steps):
        for i in range(n):
            if t - last[i] >= rf[i]:
                gi = g[i]
                if -1e-200 < gi < 1e-200:
                    gi = 0.0
                vi = c_v0 + ((c_vg * gi) + (c_vv * v[i]))
                g[i] = c_g * gi
                if vi > vth:
                    spikes.append((t, i))
                    last[i] = t
                    v[i] = vrst
                    g[i] = 0.0
                else:
                    v[i] = vi
        for k in np.flatnonzero(ev_steps == t):
            i = ev_neu[k]
            if last[i] != t and t - last[i] >= rf[i]:
                v[i] += w_poi
        for (m, j) in spikes:
            d = t - m
            if d <= 0:
                continue
            for s in out[j]:
                if dsteps[s] == d:
                    i = post[s]
                    if last[i] != t and t - last[i] >= rf[i]:
                        g[i] += signed[s] * w
    return spikes


@pytest.mark.parametrize("seed", [0, 1])
def test_mixed_delays_match_slow_reference(seed):
    rng = np.random.default_rng(100 + seed)
    n = 30
    ids, pre, post, signed = _random_arrays(rng, n, 0.2, 80, 0.75)
    pos = rng.random((n, 3)) * 400.0                 # up to ~0.7 mm apart
    brain = RealisticBrain.from_arrays(ids, pre, post, signed, positions_um=pos,
                                       realism=dict(delays=True, velocity_m_per_s=0.15))
    # the engine's connection order is file order grouped by sender (stable)
    order = np.argsort(pre, kind="stable")
    d_file = np.empty(pre.size, np.int64)
    d_file[order] = brain.delay_steps_per_connection()
    assert np.unique(d_file).size > 5                # really mixed delays
    n_steps = 1500
    ev_rng = np.random.default_rng(seed)
    exc = np.arange(4)
    ev_steps, ev_neu = [], []
    for i in exc:
        st = np.flatnonzero(ev_rng.random(n_steps) < 0.02)
        ev_steps.append(st)
        ev_neu.append(np.full(st.size, i))
    ev_steps, ev_neu = np.concatenate(ev_steps), np.concatenate(ev_neu)
    o = np.lexsort((ev_neu, ev_steps))
    ev_steps, ev_neu = ev_steps[o], ev_neu[o]
    res = brain.run_with_input_events([(ev_steps, ids[ev_neu])], excite=ids[exc],
                                      duration_ms=n_steps * 0.1)
    ref = _reference_hetero_delays(n, pre, post, signed, d_file, exc, (ev_steps, ev_neu),
                                   n_steps, dict(DEFAULT_PARAMS))
    got = sorted(zip(res.step.tolist(), res.neuron.tolist()))
    assert len(ref) > 50
    assert got == sorted(ref)


def test_whole_network_positions_note_missing_values():
    pos = np.array([[0.0, 0, 0], [np.nan, np.nan, np.nan], [100.0, 0, 0]])
    brain = RealisticBrain.from_arrays(np.arange(3, dtype=np.int64) + 10**17, [0, 0], [1, 2],
                                       [5, 5], positions_um=pos)
    L = brain.connection_lengths_um("anchor")
    assert L.tolist() == [100.0, 100.0]              # unknown distance -> median of known ones


# ---------------------------------------------------------------------------
# 2. conductance-based synapses
# ---------------------------------------------------------------------------
def _psp(brain, which, n_steps=400):
    ids = brain.root_ids
    res = brain.run_with_input_events([(np.array([10]), ids[which:which + 1])],
                                      excite=ids[:2], duration_ms=n_steps * 0.1,
                                      record_v=ids[2:3])
    return res.voltages_V[int(ids[2])][0] * 1e3      # mV


def test_single_synapse_same_effect_at_rest():
    """The explicit rescaling: one synapse moves a resting neuron by the same
    amount in both models (tiny differences only from the voltage moving)."""
    for which, count in [(0, 1), (1, 1), (0, 10), (1, 10)]:
        c_exc, c_inh = (count, 1) if which == 0 else (1, count)
        base = _psp(_two_inputs(c_exc, c_inh), which)
        cond = _psp(_two_inputs(c_exc, c_inh, dict(conductance=True)), which)
        d_base = base - DEFAULT_PARAMS["v_0"]
        d_cond = cond - DEFAULT_PARAMS["v_0"]
        peak_b, peak_c = d_base[np.argmax(abs(d_base))], d_cond[np.argmax(abs(d_cond))]
        assert np.sign(peak_b) == np.sign(peak_c) == (1 if which == 0 else -1)
        # driving force changes by |peak| / (distance to reversal)
        tol = abs(peak_b) / (52.0 if which == 0 else 8.0) + 0.002
        assert abs(peak_c / peak_b - 1) < tol, (which, count, peak_b, peak_c)


def _ode_trace(brain, events_step, c_exc, c_inh, n_steps, cond, E_e=0.0, E_i=-60.0):
    """High-accuracy ODE solution for neuron 2 of ``_two_inputs``, with the
    conductance jumps at the times the engine applies them (the input
    delivered in step n acts from time (n + 1) dt on)."""
    p = DEFAULT_PARAMS
    v0, tm, tau, dt = p["v_0"], p["t_mbr"], p["tau"], p["dt"]
    w = p["w_syn"]
    jumps = {}
    for step, src in events_step:
        arrive = step + 1 + 18                       # spike next step, then 1.8 ms
        jumps.setdefault(arrive + 1, []).append(src)
    t_edges = sorted(jumps)
    ge = gi = g = 0.0
    y = v0
    t0 = 0
    out = np.full(n_steps, np.nan)

    def rhs(t, yy, ge0, gi0, g0, tstart):
        f = math.exp(-(t - tstart) / tau)
        if cond:
            return [(v0 - yy[0] + ge0 * f * (E_e - yy[0]) + gi0 * f * (E_i - yy[0])) / tm]
        return [(v0 - yy[0] + g0 * f) / tm]

    for te in t_edges + [n_steps]:
        ts = np.arange(t0, min(te, n_steps) + 1)
        if ts.size > 1:
            sol = solve_ivp(rhs, (t0 * dt, ts[-1] * dt), [y], t_eval=ts * dt,
                            args=(ge, gi, g, t0 * dt), rtol=1e-11, atol=1e-12, method="DOP853")
            out[ts[:-1]] = sol.y[0][:-1]
            y = sol.y[0][-1]
            decay = math.exp(-(ts[-1] - t0) * dt / tau)
            ge, gi, g = ge * decay, gi * decay, g * decay
        t0 = min(te, n_steps)
        if te >= n_steps:
            break
        for src in jumps[te]:
            if src == 0:
                g += c_exc * w
                ge += c_exc * w / (E_e - v0)
            else:
                g -= c_inh * w
                gi += c_inh * w / (v0 - E_i)
    return out


@pytest.mark.parametrize("cond", [False, True])
def test_integration_matches_ode_solver(cond):
    c_exc, c_inh = 40, 30
    brain = _two_inputs(c_exc, c_inh, dict(conductance=cond))
    ids = brain.root_ids
    ev = [(10, 0), (60, 1), (90, 0), (95, 0), (140, 1)]
    n_steps = 600
    res = brain.run_with_input_events(
        [(np.array([e[0] for e in ev]), ids[[e[1] for e in ev]])], excite=ids[:2],
        duration_ms=n_steps * 0.1, record_v=ids[2:3])
    v = res.voltages_V[int(ids[2])][0] * 1e3
    assert not (res.neuron == 2).any()               # stays below threshold
    ref = _ode_trace(brain, ev, c_exc, c_inh, n_steps, cond)
    err = np.nanmax(abs(v - ref))
    # baseline: exact formula (rounding only); conductances: exponential integrator
    assert err < (1e-9 if not cond else 0.01), err
    assert np.nanmax(v) - DEFAULT_PARAMS["v_0"] > 1.0   # the trace really moved


def test_huge_reversal_potentials_recover_the_current_model():
    """With reversal potentials far away the driving force never changes, so
    the conductance model must turn back into the baseline current model."""
    c_exc, c_inh = 40, 30
    ev = [(10, 0), (60, 1), (90, 0), (95, 0), (140, 1)]
    traces = []
    for realism in [None, dict(conductance=True, E_exc_mV=1e6, E_inh_mV=-1e6)]:
        brain = _two_inputs(c_exc, c_inh, realism)
        ids = brain.root_ids
        res = brain.run_with_input_events(
            [(np.array([e[0] for e in ev]), ids[[e[1] for e in ev]])], excite=ids[:2],
            duration_ms=60.0, record_v=ids[2:3])
        traces.append(res.voltages_V[int(ids[2])][0] * 1e3)
    assert np.max(abs(traces[0] - traces[1])) < 0.005


def test_inhibition_cannot_push_below_its_reversal_potential():
    brain_b = _two_inputs(1, 3000)
    brain_c = _two_inputs(1, 3000, dict(conductance=True))
    vb, vc = _psp(brain_b, 1), _psp(brain_c, 1)
    assert vb.min() < -150                          # current model: absurdly negative
    assert vc.min() >= -60.0 - 1e-9 and vc.min() < -59.0


def test_excitation_is_sublinear():
    """A big excitatory input pushes less in the conductance model, because the
    push shrinks as the voltage rises toward 0 mV; the baseline is linear."""
    ids = np.arange(3, dtype=np.int64) + 10**17
    out = {}
    for mode in [False, True]:
        b = RealisticBrain.from_arrays(ids, [0, 1], [2, 2], [22, 5],
                                       realism=dict(conductance=mode))
        r1 = b.run_with_input_events([(np.array([10]), ids[[0]])], excite=ids[:2],
                                     duration_ms=40, record_v=ids[2:3])
        out[mode] = r1.voltages_V[int(ids[2])][0] * 1e3
    rise_b = out[False].max() - DEFAULT_PARAMS["v_0"]
    rise_c = out[True].max() - DEFAULT_PARAMS["v_0"]
    assert rise_c < rise_b                          # sublinear: driving force shrinks as v rises


# ---------------------------------------------------------------------------
# 3. spike-frequency adaptation
# ---------------------------------------------------------------------------
def test_adaptation_calibration_hits_the_published_criterion():
    inc = calibrate_adaptation(100.0)
    ratio, f_first, f_last, n = adaptation_ratio(inc, 100.0)
    assert abs(ratio - ADAPT_TARGET_RATIO) < 0.01
    assert f_last < f_first and n > 10
    # no adaptation: a steadily driven LIF neuron does not slow down at all
    assert adaptation_ratio(0.0, 100.0)[0] == pytest.approx(1.0, abs=1e-9)


def test_adaptation_slows_a_driven_neuron_in_the_network():
    """Neuron 1 is driven by a steady 400 Hz input train. Without adaptation its
    late rate is at least its early rate; with adaptation it fires less late
    in the trial, and less overall."""
    brain = _chain([30])                             # 30 synapses: neuron 1 needs several inputs
    ids = brain.root_ids
    kw = dict(excite=ids[:1], duration_ms=1000, n_trials=40, seed=4, rate_hz=400)
    rates = {}
    for on in [False, True]:
        brain.set_realism(adaptation=on)
        r = brain.run(**kw)
        t = r.step[r.neuron == 1] * 0.1
        rates[on] = ((t < 50).sum() / 40 / 0.05, (t >= 600).sum() / 40 / 0.4)
    (early_off, late_off), (early_on, late_on) = rates[False], rates[True]
    assert early_off > 20                            # neuron 1 really fires (~40 Hz)
    assert late_on < 0.85 * late_off                 # adapted: lower steady rate
    assert late_on / early_on < late_off / early_off - 0.15   # and it declines over time


# ---------------------------------------------------------------------------
# 4. whole brain (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_whole_brain_all_off_is_the_baseline_exactly():
    brain = RealisticBrain(snapshot="630", n_threads=2)
    kw = dict(excite=SUGAR_630, rate_hz=100, duration_ms=400, n_trials=2, seed=0,
              record_v=[MN9])
    a = brain.run_baseline(**kw)
    b = brain.run(**kw)
    assert a.step.size > 1000
    assert _same(a, b)
    assert np.array_equal(a.voltages_V[MN9], b.voltages_V[MN9])
    brain.set_realism(delays=True, velocity_m_per_s=1e12)   # travel time ~0: still 1.8 ms
    c = brain.run(**kw)
    assert _same(a, c)
    brain.set_realism(delays=True, velocity_m_per_s=0.2)
    d = brain.run(**kw)
    assert not _same(a, d)                                  # the switch really does something
    notes = brain.distance_notes
    assert notes["anchor_out_of_brain_dropped"] == 2


def test_conductance_weight_scale_multiplies_synapses_not_stimulus():
    """cond_weight_scale (the one re-fitted number of upgrade 2) scales every
    synaptic conductance, so a small input at rest pushes ~k times as hard;
    the stimulus kick is untouched (the stimulated neuron still fires once
    per kick)."""
    base = _psp(_two_inputs(1, 1, dict(conductance=True)), 0) - DEFAULT_PARAMS["v_0"]
    dbl = _psp(_two_inputs(1, 1, dict(conductance=True, cond_weight_scale=2.0)), 0) \
        - DEFAULT_PARAMS["v_0"]
    assert abs(dbl.max() / base.max() - 2.0) < 0.01
    b = _two_inputs(1, 1, dict(conductance=True, cond_weight_scale=3.0))
    ids = b.root_ids
    r = b.run_with_input_events([(np.array([10, 50]), ids[[0, 0]])], excite=ids[:2],
                                duration_ms=10.0)
    assert (r.neuron == 0).sum() == 2

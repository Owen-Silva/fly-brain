"""Tests for sim/celltype_params.py (PLAN.md Phase 7, upgrade 4).

The most important tests: with no measured values (or the upgrade switched
off) the new engine gives exactly the same spikes and voltages as the
untouched baseline engine sim/fast_engine.py, for the same seed. Then: the
measured values really reach the neurons they belong to (time constant,
threshold gap), and nothing else changes.
"""

import math

import numpy as np
import pytest

from sim.celltype_params import (MODEL_PARAMS, SELECTORS, CellTypeBrain, applied_values,
                                 read_table)
from sim.fast_engine import DEFAULT_PARAMS, FastBrain

MN9 = 720575940660219265
SUGAR_630 = [  # data/reference/example.ipynb, `neu_sugar`
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
SHARED = {"v_0_mV": DEFAULT_PARAMS["v_0"],
          "v_th_gap_mV": DEFAULT_PARAMS["v_th"] - DEFAULT_PARAMS["v_0"],
          "t_mbr_ms": DEFAULT_PARAMS["t_mbr"], "t_rfc_ms": DEFAULT_PARAMS["t_rfc"]}


def _random_arrays(rng, n, p_conn, max_count, frac_exc):
    mask = rng.random((n, n)) < p_conn
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    perm = rng.permutation(pre.size)
    pre, post = pre[perm], post[perm]
    count = rng.integers(1, max_count + 1, pre.size)
    sign = np.where(rng.random(n) < frac_exc, 1, -1)[pre]
    ids = (720575940600000000 + rng.choice(10**8, n, replace=False)).astype(np.int64)
    return ids, pre, post, sign * count


def _same(a, b):
    return (np.array_equal(a.trial, b.trial) and np.array_equal(a.step, b.step)
            and np.array_equal(a.neuron, b.neuron))


def _net(seed, n=80, values=None):
    rng = np.random.default_rng(seed)
    ids, pre, post, signed = _random_arrays(rng, n, 0.12, 60, 0.7)
    members = {"A": ids[20:40], "B": ids[40:55]}
    base = FastBrain.from_arrays(ids, pre, post, signed)
    new = CellTypeBrain.from_arrays(ids, pre, post, signed, members=members,
                                    values=values if values is not None else {})
    kw = dict(excite=ids[:6], duration_ms=300, n_trials=3, seed=seed, rate_hz=180,
              silence=ids[10:12], record_v=[ids[25], ids[45], ids[70]])
    return ids, base, new, kw


# ---------------------------------------------------------------------------
# 0. no measured values == baseline, exactly
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_no_measured_values_is_the_baseline_exactly(seed):
    ids, base, new, kw = _net(seed)
    a, b = base.run(**kw), new.run(**kw)
    assert a.step.size > 100                          # the network actually did something
    assert _same(a, b)
    for k in a.voltages_V:
        assert np.array_equal(a.voltages_V[k], b.voltages_V[k])
    assert new.describe()["n_neurons_changed"] == 0
    assert _same(a, new.run_baseline(**kw))           # the helper runs the untouched loop


@pytest.mark.parametrize("seed", [0, 1])
def test_switched_off_is_the_baseline_exactly(seed):
    ids, base, new, kw = _net(seed, values={"A": {"t_mbr_ms": 11.2, "v_th_gap_mV": 21.5},
                                            "B": {"v_th_gap_mV": 12.0}})
    new.set_celltype(enabled=False)
    a, b = base.run(**kw), new.run(**kw)
    assert _same(a, b)
    for k in a.voltages_V:
        assert np.array_equal(a.voltages_V[k], b.voltages_V[k])


def test_groups_given_the_shared_values_are_the_baseline_exactly():
    """Two groups that exist but carry exactly the shared numbers: the
    per-group code path adds nothing."""
    ids, base, new, kw = _net(7, values={"A": dict(SHARED), "B": dict(SHARED)})
    assert new.describe()["n_neurons_changed"] == 35
    a, b = base.run(**kw), new.run(**kw)
    assert _same(a, b)
    for k in a.voltages_V:
        assert np.array_equal(a.voltages_V[k], b.voltages_V[k])


def test_only_the_gap_matters_not_the_resting_level():
    """Moving rest and threshold together (same 7 mV gap) leaves the spikes
    unchanged: in this model a synapse adds a fixed number of millivolts."""
    ids, base, new, kw = _net(3, values={"A": {"v_0_mV": -60.0}, "B": {"v_0_mV": -45.0}})
    a, b = base.run(**kw), new.run(**kw)
    assert _same(a, b)
    va, vb = a.voltages_V[int(ids[25])], b.voltages_V[int(ids[25])]
    assert np.allclose(vb - va, -8e-3, atol=1e-9)     # shifted 8 mV down, same shape


# ---------------------------------------------------------------------------
# 1. the measured values reach the right neurons
# ---------------------------------------------------------------------------
def _chain(values):
    """Neuron 0 (stimulated) -> neuron 1 with 5 synapses. Neuron 1 is in group G."""
    ids = np.arange(3, dtype=np.int64) + 10**17
    return ids, CellTypeBrain.from_arrays(ids, [0], [1], [5], members={"G": ids[1:2]},
                                          values={"G": values})


@pytest.mark.parametrize("t_mbr", [3.66, 11.2, 22.9, 200.0])
def test_membrane_time_constant_is_used(t_mbr):
    """One input spike: neuron 1's voltage must follow the exact solution of
    dv/dt = (v_0 - v + g)/t_mbr, dg/dt = -g/tau with ITS OWN t_mbr."""
    ids, brain = _chain({"t_mbr_ms": t_mbr, "v_th_gap_mV": 50.0})
    ev = [(np.array([0]), np.array([ids[0]]))]
    res = brain.run_with_input_events(ev, excite=[ids[0]], duration_ms=60.0,
                                      record_v=[ids[1]])
    p = DEFAULT_PARAMS
    t_spk = res.spike_times(0)[int(ids[0])][0]         # neuron 0 fires once
    t_arr = t_spk + p["t_dly"]
    v = res.voltages_mV[int(ids[1])][0]
    t = np.arange(v.size) * p["dt"]
    g0 = 5 * p["w_syn"]
    # input added in the arrival step is first used in the next step's update,
    # and a recorded value is the voltage at the START of a step
    s = t - t_arr - p["dt"]
    tau = p["tau"]
    exact = np.where(s >= 0, g0 * tau / (tau - t_mbr) * (np.exp(-s / tau) - np.exp(-s / t_mbr)), 0.0)
    assert np.allclose(v - p["v_0"], exact, atol=1e-6)


def test_threshold_gap_is_used():
    """A bigger measured gap needs a bigger input: one spike through 250
    synapses (peak depolarization about 10.8 mV with tau_m 20 ms) fires a
    neuron with the shared 7 mV gap but not one with a 21.5 mV gap."""
    for gap, fires in [(7.0, True), (21.5, False)]:
        ids = np.arange(2, dtype=np.int64) + 10**17
        brain = CellTypeBrain.from_arrays(ids, [0], [1], [250], members={"G": ids[1:2]},
                                          values={"G": {"v_th_gap_mV": gap, "t_mbr_ms": 20.0}})
        ev = [(np.array([0]), np.array([ids[0]]))]
        res = brain.run_with_input_events(ev, excite=[ids[0]], duration_ms=50.0)
        assert (int(ids[1]) in res.spike_times(0)) == fires


def test_other_neurons_are_untouched():
    """Changing group A's settings leaves neurons outside A (and outside
    anything A drives) exactly as in the baseline, until A's changed spikes
    reach them. Checked on a network where A has no outgoing connections."""
    rng = np.random.default_rng(11)
    ids, pre, post, signed = _random_arrays(rng, 60, 0.15, 60, 0.7)
    a_ids = ids[30:40]
    keep = ~np.isin(pre, np.arange(30, 40))           # A sends nothing
    pre, post, signed = pre[keep], post[keep], signed[keep]
    base = FastBrain.from_arrays(ids, pre, post, signed)
    new = CellTypeBrain.from_arrays(ids, pre, post, signed, members={"A": a_ids},
                                    values={"A": {"t_mbr_ms": 11.2, "v_th_gap_mV": 21.5}})
    kw = dict(excite=ids[:5], duration_ms=300, n_trials=2, seed=4, rate_hz=200)
    a, b = base.run(**kw), new.run(**kw)
    outside = ~np.isin(np.arange(60), np.arange(30, 40))
    ca = np.bincount(a.neuron, minlength=60)
    cb = np.bincount(b.neuron, minlength=60)
    assert np.array_equal(ca[outside], cb[outside])
    assert not np.array_equal(ca[30:40], cb[30:40])   # A itself did change


def test_bad_options_are_rejected():
    ids, brain = _chain({"t_mbr_ms": 11.2})
    with pytest.raises(KeyError):
        brain.set_celltype(groups=["nope"])
    with pytest.raises(KeyError):
        brain.set_celltype(overrides={"G": {"tau_ms": 3.0}})


# ---------------------------------------------------------------------------
# 2. the parameter table
# ---------------------------------------------------------------------------
def test_table_values_used_in_the_model():
    vals = applied_values()
    assert set(vals) == {"uPN_ACh", "KC", "PEN", "lLNv"}
    assert vals["KC"] == {"t_mbr_ms": 11.2, "v_th_gap_mV": 21.5, "v_0_mV": -57.8}
    assert vals["uPN_ACh"] == {"t_mbr_ms": 22.9, "v_th_gap_mV": 10.0, "v_0_mV": -57.8}
    assert vals["PEN"] == {"v_th_gap_mV": 12.0, "v_0_mV": -46.1}
    assert vals["lLNv"] == {"t_mbr_ms": 3.66, "v_0_mV": -49.0}
    assert set(vals) <= set(SELECTORS)
    for r in read_table():
        if r["model_param"] not in ("", "-"):
            assert r["model_param"] in MODEL_PARAMS
            assert r["status"] in ("READ", "READ+DERIVED")   # never an unread number
            assert r["source"].strip() and r["where_in_paper"].strip()


def test_derived_numbers_in_the_table_are_right():
    """The numbers computed from the papers' values (not quoted directly)."""
    assert math.isclose(np.mean([8.3 * 2.6, 20.4 * 1.5, 20.8 * 0.8]), 22.9, abs_tol=0.05)
    assert math.isclose(1.0 / 0.089, 11.2, abs_tol=0.05)            # Cm / gL (ms)
    assert math.isclose(305e6 * 12e-12 * 1e3, 3.66, abs_tol=0.005)  # R x C (ms)
    rest = [-43, -47, -48, -42, -57, -44, -45, -43]                 # Turner-Evans 2017
    thr = [-25, -34, -38, -34, -41, -30, -35, -36]
    assert math.isclose(np.mean(rest), -46.1, abs_tol=0.05)
    assert math.isclose(np.mean(np.subtract(thr, rest)), 12.0, abs_tol=0.05)


# ---------------------------------------------------------------------------
# 3. whole brain (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_whole_brain_no_values_is_the_baseline_exactly():
    brain = CellTypeBrain(snapshot="630", n_threads=2)
    # group sizes match the table
    counts = {g: int(m.size) for g, m in brain.members.items()}
    for r in read_table():
        if r["cell_group"] in counts:
            assert int(r["n_neurons_630"]) == counts[r["cell_group"]]
    kw = dict(excite=SUGAR_630, rate_hz=100, duration_ms=400, n_trials=2, seed=0,
              record_v=[MN9])
    a = brain.run_baseline(**kw)
    brain.set_celltype(enabled=False)
    b = brain.run(**kw)
    assert a.step.size > 1000
    assert _same(a, b)
    assert np.array_equal(a.voltages_V[MN9], b.voltages_V[MN9])
    brain.set_celltype(groups=[])                     # on, but no measured values
    assert _same(a, brain.run(**kw))
    brain.set_celltype()                              # the full table
    assert brain.describe()["n_neurons_changed"] == sum(counts.values())
    c = brain.run(**kw)
    assert c.params["celltype"]["enabled"] and c.step.size > 1000

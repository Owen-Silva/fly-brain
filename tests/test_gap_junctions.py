"""Tests for sim/gap_junctions.py (electrical synapses, Phase 7 item 5).

Plain English: (1) with no electrical synapses, or with electrical synapses of
strength zero, the new engine gives exactly the same spikes as the old one;
(2) two cells joined by one junction show the textbook coupling coefficient
kappa / (1 + kappa); (3) a spike adds the expected "spikelet" to its partner;
(4) a silenced cell does not move its partner; (5) the calibration hits the
measured coupling coefficient; (6) slow: on the whole brain, zero junctions
reproduce the al_ln_literature brain spike for spike, and the coupling table
has the expected size.
"""

import gc

import numpy as np
import pandas as pd
import pytest

from sim.fast_engine import DEFAULT_PARAMS, FastBrain
from sim import gap_junctions as G


def _random_arrays(seed, n=60, p_conn=0.15, max_count=12, frac_exc=0.6):
    rng = np.random.default_rng(seed)
    mask = rng.random((n, n)) < p_conn
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    count = rng.integers(1, max_count + 1, pre.size)
    sign = np.where(rng.random(n) < frac_exc, 1, -1)[pre]
    ids = (720575940600000000 + rng.choice(10**8, n, replace=False)).astype(np.int64)
    return ids, pre, post, sign * count


def _same(a, b):
    return (np.array_equal(a.trial, b.trial) and np.array_equal(a.neuron, b.neuron)
            and np.array_equal(a.step, b.step))


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_no_couplings_identical_to_fast_engine(seed):
    ids, pre, post, signed = _random_arrays(seed)
    fb = FastBrain.from_arrays(ids, pre, post, signed)
    gb = G.GapBrain.from_arrays(ids, pre, post, signed)
    kw = dict(excite=ids[:6], duration_ms=300, n_trials=3, seed=seed, rate_hz=120,
              silence=ids[10:12], record_v=ids[20:23])
    r1, r2 = fb.run(**kw), gb.run(**kw)
    assert r1.step.size > 50
    assert _same(r1, r2)
    for k in r1.voltages_V:
        assert np.array_equal(r1.voltages_V[k], r2.voltages_V[k])


@pytest.mark.parametrize("seed", [3, 4])
def test_zero_strength_couplings_identical(seed):
    ids, pre, post, signed = _random_arrays(seed)
    fb = FastBrain.from_arrays(ids, pre, post, signed)
    gb = G.GapBrain.from_arrays(ids, pre, post, signed)
    rng = np.random.default_rng(seed)
    a = rng.choice(60, 40)
    b = (a + rng.integers(1, 59, 40)) % 60
    gb.set_couplings(a, b, 0.0)
    kw = dict(excite=ids[:6], duration_ms=300, n_trials=3, seed=seed, rate_hz=120,
              record_v=ids[[int(a[0]), int(b[0])]])
    r1, r2 = fb.run(**kw), gb.run(**kw)
    assert _same(r1, r2)
    for k in r1.voltages_V:
        assert np.array_equal(r1.voltages_V[k], r2.voltages_V[k])
    # run_baseline on the same object is the old engine
    assert _same(r1, gb.run_baseline(**kw))


def _two_cells():
    ids = np.array([720575940600000001, 720575940600000002], np.int64)
    return ids, G.GapBrain.from_arrays(ids, np.zeros(0, np.int64), np.zeros(0, np.int64),
                                       np.zeros(0, np.int64))


@pytest.mark.parametrize("kappa", [0.013, 0.1, 0.5])
def test_two_cell_coupling_coefficient(kappa):
    ids, gb = _two_cells()
    gb.set_couplings([0], [1], kappa)
    gb.set_test_current({int(ids[0]): 5.0})          # 5 mV alone: below threshold
    res = gb.run(duration_ms=500, record_v=ids)
    v1 = res.voltages_mV[int(ids[0])][0, -1] - DEFAULT_PARAMS["v_0"]
    v2 = res.voltages_mV[int(ids[1])][0, -1] - DEFAULT_PARAMS["v_0"]
    assert res.step.size == 0
    assert v2 / v1 == pytest.approx(G.two_cell_cc(kappa), rel=1e-6)
    assert v1 == pytest.approx(5.0 * (1 + kappa) / (1 + 2 * kappa), rel=1e-6)


def test_uncoupled_cell_does_not_move():
    ids, gb = _two_cells()
    gb.set_test_current({int(ids[0]): 5.0})
    res = gb.run(duration_ms=200, record_v=ids)
    assert np.allclose(res.voltages_mV[int(ids[1])], DEFAULT_PARAMS["v_0"], rtol=0, atol=1e-9)


def test_spikelet_size():
    ids, gb = _two_cells()
    kappa = 0.05
    gb.set_test_current({int(ids[0]): 10.0})         # cell 1 fires regularly
    out = {}
    for area in (0.0, G.SPIKE_AREA_MV_MS):
        gb.set_couplings([0], [1], kappa, spike_area_mV_ms=area)
        res = gb.run(duration_ms=200, record_v=ids)
        out[area] = res
    r0, r1 = out[0.0], out[G.SPIKE_AREA_MV_MS]
    first = int(r0.step[r0.neuron == 0].min())
    assert int(r1.step[r1.neuron == 0].min()) == first
    v0 = r0.voltages_mV[int(ids[1])][0]
    v1 = r1.voltages_mV[int(ids[1])][0]
    assert np.array_equal(v0[:first + 1], v1[:first + 1])
    expected = kappa * G.SPIKE_AREA_MV_MS / DEFAULT_PARAMS["t_mbr"]   # mV
    assert v1[first + 1] - v0[first + 1] == pytest.approx(expected, rel=1e-9)
    assert expected == pytest.approx(0.1)            # 0.05 * 40 / 20


def test_silenced_cell_does_not_drive_partner():
    ids, gb = _two_cells()
    gb.set_couplings([0], [1], 0.2)
    gb.set_test_current({int(ids[0]): 10.0})
    res = gb.run(duration_ms=200, record_v=ids, silence=[int(ids[0])])
    assert res.spike_counts[0] > 0
    assert np.allclose(res.voltages_mV[int(ids[1])], DEFAULT_PARAMS["v_0"], rtol=0, atol=1e-9)


def test_refractory_cell_ignores_junction_current():
    ids, gb = _two_cells()
    gb.set_couplings([0], [1], 0.5)
    gb.set_test_current({int(ids[0]): 20.0, int(ids[1]): 20.0})
    res = gb.run(duration_ms=50, record_v=ids)
    v = res.voltages_mV[int(ids[1])][0]
    s = res.step[res.neuron == 1]
    rfc = int(round(DEFAULT_PARAMS["t_rfc"] / DEFAULT_PARAMS["dt"]))
    # v is frozen at reset for the whole refractory period after each spike
    for st in s[:-1]:
        seg = v[st + 1: st + rfc]
        assert np.allclose(seg, DEFAULT_PARAMS["v_rst"], rtol=0, atol=1e-9)


def test_calibration_hits_target():
    # a small eLN/PN network: 3 "eLNs" each coupled to 6 "PNs"; 2 sister groups
    rows = [dict(cls="eln_pn", a=e, b=p) for e in range(3) for p in range(3, 9)]
    rows += [dict(cls="sister_pn", a=a, b=b) for a, b in [(3, 4), (3, 5), (4, 5), (6, 7)]]
    t = pd.DataFrame(rows)
    kap = G.calibrate_kappa(t, {"eln_pn": 0.013, "sister_pn": 0.016})
    pcc = G.pair_cc(t, kap)
    assert np.median(pcc.cc_ab[pcc.cls == "eln_pn"]) == pytest.approx(0.013, rel=1e-5)
    s = pcc[pcc.cls == "sister_pn"]
    assert np.median(np.r_[s.cc_ab, s.cc_ba]) == pytest.approx(0.016, rel=1e-5)
    assert kap["eln_pn"] > G.CC_TARGET["eln_pn"]      # loading needs a stronger junction
    assert G.two_cell_cc(1.0) == 0.5


# ---------------------------------------------------------------------------
# Whole brain (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_whole_brain_table_and_zero_coupling_identity():
    from sim import sign_fixes as S
    brain, table = G.build_gap_brain("al_ln_literature", n_threads=2, return_table=True)
    counts = table.cls.value_counts().to_dict()
    assert counts == {"eln_pn": 7371, "sister_pn": 703}
    assert table.source.notna().all() and (table.source != "").all()
    assert table[table.cls == "eln_pn"].a.nunique() == 44
    kap = brain.kappa_by_class
    pcc = G.pair_cc(table, kap)
    assert np.median(pcc.cc_ab[pcc.cls == "eln_pn"]) == pytest.approx(G.CC_TARGET["eln_pn"], rel=1e-4)
    rid, _, _, _ = S.load_reference_arrays()
    lab = S.neuron_table(rid)
    dm1 = rid[(lab.hemibrain_type.to_numpy() == "ORN_DM1")]
    kw = dict(excite=dm1, duration_ms=300, n_trials=2, seed=0, rate_hz=150)
    ref = brain.run_baseline(**kw)          # = sign_fixes.build_brain("al_ln_literature")
    brain.gap_scale = 0.0                   # junctions present, strength 0
    zero = brain.run(**kw)
    assert ref.step.size > 1000
    assert _same(ref, zero)
    brain.gap_scale = 1.0
    on = brain.run(**kw)
    assert not _same(ref, on)
    del brain, table
    gc.collect()

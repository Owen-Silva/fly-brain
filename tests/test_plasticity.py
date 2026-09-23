"""Tests for sim/plasticity.py (PLAN.md Phase 8, learning in the mushroom body).

In plain English, these check that:
0. with learning switched off, the new engine gives exactly the same spikes
   as the untouched baseline engine (sim/fast_engine.py);
1. the learning rule does what the papers say and nothing else: a Kenyon
   cell -> output neuron synapse weakens only when the Kenyon cell was active
   AND dopamine arrived in that synapse's compartment, never below zero, only
   in the dopamine neuron's own compartment and hemisphere;
2. the numbers match the rule's formula;
3. (slow) on the real brain, switching learning on without training leaves
   the Phase 3 sugar -> MN9 result spike-for-spike unchanged.
"""

import numpy as np
import pandas as pd
import pytest

from sim.fast_engine import FastBrain
from sim.plasticity import (DAN_COMPARTMENTS, HIGE_PULSES_MS, MBON_COMPARTMENTS,
                            LearningRule, PlasticBrain, extract_circuit, kc_lobe,
                            load_labels, mb_circuit_rows, pulse_blocks)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
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


def _labels(ids, cell_class=None, hb=None, side=None):
    n = len(ids)
    return pd.DataFrame({
        "root_id": np.asarray(ids, np.int64),
        "cell_class": cell_class if cell_class is not None else [""] * n,
        "hemibrain_type": hb if hb is not None else [""] * n,
        "side": side if side is not None else ["left"] * n,
    })


def _same(a_steps, a_neu, b_steps, b_neu):
    return np.array_equal(a_steps, b_steps) and np.array_equal(a_neu, b_neu)


def _unpack(events, ids):
    """(ev_ptr, ev_neuron) -> (steps, root_ids) for FastBrain.run_with_input_events."""
    ptr, neu = events
    steps = np.repeat(np.arange(ptr.size - 1), np.diff(ptr))
    return steps, ids[neu]


def _mini_mb(n_kc=6, kc_counts=40, side="left", dan_side=None):
    """A hand-made mushroom body: KCs 0..n_kc-1 (gamma), then MBON11 (row A),
    MBON01 (row B), a non-MBON target (row C), PPL101 (row D) and PAM01 (row E).
    Every KC connects to A, B and C with ``kc_counts`` synapses; the DANs
    connect to the KCs (so their hemisphere can be measured) and weakly to A."""
    A, B, C, D, E = n_kc, n_kc + 1, n_kc + 2, n_kc + 3, n_kc + 4
    n = n_kc + 5
    pre, post, cnt = [], [], []
    for k in range(n_kc):
        for t in (A, B, C):
            pre.append(k); post.append(t); cnt.append(kc_counts)
        pre.append(D); post.append(k); cnt.append(3)
        pre.append(E); post.append(k); cnt.append(3)
    pre.append(D); post.append(A); cnt.append(5)
    ids = np.arange(n, dtype=np.int64) + 10**17
    cls = ["Kenyon_Cell"] * n_kc + ["MBON", "MBON", "", "DAN", "DAN"]
    hb = ["KCg-m"] * n_kc + ["MBON11", "MBON01", "", "PPL101", "PAM01"]
    sides = [side] * n + []
    if dan_side is not None:
        sides[D] = sides[E] = dan_side
    brain = FastBrain.from_arrays(ids, pre, post, cnt)
    return brain, _labels(ids, cls, hb, sides), dict(A=A, B=B, C=C, D=D, E=E)


def _paired_blocks(kc_rows, dan_rows, odor_on=0.0, odor_off=1000.0,
                   pulses=HIGE_PULSES_MS, kc_rate=40.0):
    return [(np.asarray(kc_rows), kc_rate, odor_on, odor_off)] + pulse_blocks(
        np.asarray(dan_rows), pulses)


def _rel(pb, state, kc_rows, target):
    t = pb.plastic_table
    m = t.kc_row.isin(kc_rows) & (t.mbon_row == target)
    idx = t.loc[m, "wk_index"].to_numpy()
    return state.wk[idx] / pb.wk0[idx]


# ---------------------------------------------------------------------------
# 0. learning off == baseline, exactly
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("seed", [0, 1, 2])
def test_learning_off_is_the_baseline_exactly(seed):
    rng = np.random.default_rng(seed)
    ids, pre, post, signed = _random_arrays(rng, 80, 0.12, 60, 0.7)
    base = FastBrain.from_arrays(ids, pre, post, signed)
    # label a third of the neurons as KCs and some as MBONs/DANs, so the KC
    # weight path and the dopamine path are both exercised
    cls = np.array([""] * 80, dtype=object)
    hb = np.array([""] * 80, dtype=object)
    cls[:25], hb[:25] = "Kenyon_Cell", "KCg-m"
    cls[25:30], hb[25:30] = "MBON", "MBON11"
    cls[30:32], hb[30:32] = "DAN", "PPL101"
    pb = PlasticBrain(base, _labels(ids, list(cls), list(hb)), dan_mode="fast")
    n_steps = 3000
    ev = pb.make_events([(np.arange(6), 180.0, 0.0, 300.0)], n_steps,
                        np.random.default_rng(seed))
    ref = base.run_with_input_events([_unpack(ev, ids)], excite=ids[:6], duration_ms=300.0,
                                     record_v=ids[40:42])
    assert ref.step.size > 100                     # the network actually did something
    for plastic in (False, True):
        state = pb.new_state()
        out = pb.run(None, 300.0, None, state=state, plastic=plastic, events=ev,
                     excite_rows=np.arange(6), record_v=[40, 41])
        if not plastic:
            assert _same(ref.step, ref.neuron, out.step, out.neuron)
            for q, i in enumerate((40, 41)):
                assert np.array_equal(ref.voltages_V[int(ids[i])][0], out.voltages_V[i])
            assert np.array_equal(state.wk, pb.wk0)  # nothing learned
    # with learning ON, spikes can only differ after a weight has changed
    state = pb.new_state()
    pb.rule = LearningRule(eta=0.0)
    out = pb.run(None, 300.0, None, state=state, plastic=True, events=ev,
                 excite_rows=np.arange(6))
    assert _same(ref.step, ref.neuron, out.step, out.neuron)
    assert np.array_equal(state.wk, pb.wk0)


def test_modulatory_mode_removes_only_dan_fast_synapses():
    brain, lab, r = _mini_mb()
    fast = PlasticBrain(brain, lab, dan_mode="fast")
    mod = PlasticBrain(brain, lab, dan_mode="modulatory")
    blocks = pulse_blocks(np.array([r["D"]]), [10.0], width_ms=30.0, rate_hz=900.0)
    a = fast.run(blocks, 100.0, 0, plastic=False, record_v=[0])
    b = mod.run(blocks, 100.0, 0, plastic=False, record_v=[0])
    # the DAN fires the same spikes in both...
    assert np.array_equal(a.counts([r["D"]]), b.counts([r["D"]]))
    assert a.counts([r["D"]])[0] > 3
    # ...but only in "fast" mode does it push the KCs' voltage
    assert a.voltages_V[0].max() > b.voltages_V[0].max()
    assert np.allclose(b.voltages_V[0], b.voltages_V[0][0])     # KC stays at rest


# ---------------------------------------------------------------------------
# 1. the rule: what changes and what does not
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def mini():
    brain, lab, r = _mini_mb()
    pb = PlasticBrain(brain, lab, LearningRule(eta=2.0), dan_mode="modulatory")
    return pb, r


def test_plastic_pairs_are_exactly_kc_to_mbon(mini):
    pb, r = mini
    t = pb.plastic_table
    assert set(t.mbon_row) == {r["A"], r["B"]}                 # not the non-MBON C
    assert set(t.kc_row) == set(range(6))
    comp = dict(zip(t.mbon_type, t.compartments))
    assert comp["MBON11"] == "g1"                              # gamma KC -> gamma1 part
    assert comp["MBON01"] == "g5"                              # gamma KC -> gamma5 part


def test_paired_depresses_only_the_dan_compartment(mini):
    pb, r = mini
    s = pb.new_state()
    blocks = _paired_blocks([0, 1, 2], [r["D"]])               # KCs 3-5 stay silent
    res = pb.run(blocks, 2000.0, 1, state=s)
    assert res.counts([r["D"]])[0] >= 4
    a = _rel(pb, s, [0, 1, 2], r["A"])
    assert (a < 0.9).all() and (a > 0).all()                   # weaker, never negative
    assert np.array_equal(_rel(pb, s, [3, 4, 5], r["A"]), np.ones(3))   # silent KCs: no change
    assert np.array_equal(_rel(pb, s, range(6), r["B"]), np.ones(6))    # gamma5: no change
    # the non-plastic KC -> C weights never move
    t = pb.plastic_table
    plastic_idx = set(t.wk_index)
    other = np.array([i for i in range(pb.wk0.size) if i not in plastic_idx])
    assert np.array_equal(s.wk[other], pb.wk0[other])


def test_pam_teaches_gamma5_not_gamma1(mini):
    pb, r = mini
    s = pb.new_state()
    pb.run(_paired_blocks([0, 1, 2], [r["E"]]), 2000.0, 2, state=s)
    assert (_rel(pb, s, [0, 1, 2], r["B"]) < 0.9).all()
    assert np.array_equal(_rel(pb, s, range(6), r["A"]), np.ones(6))


@pytest.mark.parametrize("what", ["kc_alone", "dan_alone", "separate_trials", "learning_off"])
def test_no_pairing_no_change(mini, what):
    pb, r = mini
    s = pb.new_state()
    kc = [(np.array([0, 1, 2]), 40.0, 0.0, 1000.0)]
    dan = pulse_blocks(np.array([r["D"]]), HIGE_PULSES_MS)
    if what == "kc_alone":
        pb.run(kc, 2000.0, 3, state=s)
    elif what == "dan_alone":
        pb.run(dan, 2000.0, 3, state=s)
    elif what == "separate_trials":                            # explicitly unpaired
        pb.run(dan, 2000.0, 3, state=s)
        pb.run(kc, 2000.0, 4, state=s)
    else:
        pb.run(kc + dan, 2000.0, 3, state=s, plastic=False)
    assert np.array_equal(s.wk, pb.wk0)


def test_backward_pairing_is_much_weaker_than_forward(mini):
    pb, r = mini
    fwd, bwd = pb.new_state(), pb.new_state()
    pb.run(_paired_blocks([0, 1, 2], [r["D"]]), 3500.0, 5, state=fwd)
    # DAN first; odor starts 0.5 s after the last pulse (Hige 2015 backward)
    pb.run(_paired_blocks([0, 1, 2], [r["D"]], odor_on=2200.0, odor_off=3200.0),
           3500.0, 5, state=bwd)
    # compare the size of the change on a log scale (the forward change
    # saturates near zero weight with this deliberately large eta)
    log_f = -np.log(_rel(pb, fwd, [0, 1, 2], r["A"])).mean()
    log_b = -np.log(_rel(pb, bwd, [0, 1, 2], r["A"])).mean()
    assert log_f > 1.0
    assert 0 <= log_b < 0.05 * log_f


def test_other_hemisphere_untouched():
    brain, lab, r = _mini_mb()
    lab.loc[3:5, "side"] = "right"                             # KCs 3-5 in the right MB
    # the DAN's KC outputs go to all six KCs equally -> half its dopamine each side
    pb = PlasticBrain(brain, lab, LearningRule(eta=2.0))
    assert abs(pb.dan_frac_left[r["D"]] - 0.5) < 1e-12
    # now make the DAN innervate only the left KCs
    pre = np.r_[np.repeat(np.arange(6), 3), [r["D"]] * 3, r["D"]]
    post = np.r_[np.tile([r["A"], r["B"], r["C"]], 6), [0, 1, 2], r["A"]]
    cnt = np.r_[np.full(18, 40), [3, 3, 3], 5]
    b2 = FastBrain.from_arrays(brain.root_ids, pre, post, cnt)
    pb2 = PlasticBrain(b2, lab, LearningRule(eta=2.0))
    assert pb2.dan_frac_left[r["D"]] == 1.0
    s = pb2.new_state()
    pb2.run(_paired_blocks(range(6), [r["D"]]), 2000.0, 6, state=s)
    assert (_rel(pb2, s, [0, 1, 2], r["A"]) < 0.9).all()
    assert np.array_equal(_rel(pb2, s, [3, 4, 5], r["A"]), np.ones(3))


# ---------------------------------------------------------------------------
# 2. the numbers match the formula
# ---------------------------------------------------------------------------
def test_single_spike_pair_matches_formula():
    """One KC spike, then one DAN spike 100 ms later. Expected log weight
    change = -eta * inc * exp(-0.1/tau_kc) * tau_kc*tau_da/(tau_kc+tau_da)."""
    brain, lab, r = _mini_mb()
    rule = LearningRule(eta=3.0, tau_kc_ms=1000.0, tau_da_ms=200.0)
    pb = PlasticBrain(brain, lab, rule)
    n_steps = 20000
    # one kick = one spike (68.75 mV >> threshold)
    steps = np.array([100, 1100])
    neu = np.array([0, r["D"]])
    ev = FastBrain._pack_events(steps, neu, n_steps)
    s = pb.new_state()
    res = pb.run(None, 2000.0, None, state=s, events=ev, excite_rows=[0, r["D"]])
    sp = dict(zip(res.neuron.tolist(), res.step.tolist()))
    gap_s = (sp[r["D"]] - sp[0]) * 1e-4
    inc = pb.dan_increments()[pb.dan_ptr[r["D"]]:pb.dan_ptr[r["D"] + 1]]
    assert inc.size == 1 and abs(inc[0] - 1.0) < 1e-12        # one DAN of its type, one compartment
    tkc, tda = 1.0, 0.2
    expect = np.exp(-3.0 * np.exp(-gap_s / tkc) * tkc * tda / (tkc + tda))
    got = _rel(pb, s, [0], r["A"])[0]
    assert abs(got - expect) < 0.01 * (1 - expect)             # within 1% of the change
    assert np.array_equal(_rel(pb, s, [1, 2, 3, 4, 5], r["A"]), np.ones(5))


def test_end_of_trial_tail_equals_running_on():
    """Stopping a trial early and letting the traces fade analytically gives
    the same weights as simulating the fading."""
    brain, lab, r = _mini_mb()
    pb = PlasticBrain(brain, lab, LearningRule(eta=2.0))
    blocks = _paired_blocks([0, 1, 2], [r["D"]], pulses=(200.0, 700.0))
    short, long_ = pb.new_state(), pb.new_state()
    pb.run(blocks, 1100.0, 7, state=short)        # odor ends at 1000 ms: no spike in flight
    pb.run(blocks, 8000.0, 7, state=long_)
    a = _rel(pb, short, [0, 1, 2], r["A"])
    b = _rel(pb, long_, [0, 1, 2], r["A"])
    assert np.allclose(np.log(a), np.log(b), rtol=0.01)


def test_slow_compartments_learn_slower():
    brain, lab, r = _mini_mb()
    lab.loc[r["A"], "hemibrain_type"] = "MBON18"               # alpha2 output neuron
    lab.loc[r["D"], "hemibrain_type"] = "PPL105"               # alpha'2alpha2 DAN
    lab.loc[0:5, "hemibrain_type"] = "KCab-s"
    pb = PlasticBrain(brain, lab, LearningRule(eta=2.0, slow_ratio=0.1))
    s = pb.new_state()
    pb.run(_paired_blocks([0, 1, 2], [r["D"]]), 2000.0, 8, state=s)
    log_slow = np.log(_rel(pb, s, [0, 1, 2], r["A"]))
    pb.rule = LearningRule(eta=2.0, slow_ratio=1.0)
    s2 = pb.new_state()
    pb.run(_paired_blocks([0, 1, 2], [r["D"]]), 2000.0, 8, state=s2)
    log_fast = np.log(_rel(pb, s2, [0, 1, 2], r["A"]))
    assert np.allclose(log_slow, 0.1 * log_fast, rtol=1e-6)


def test_kc_lobe_names():
    assert kc_lobe("KCg-m") == "g" and kc_lobe("KCab-p") == "ab"
    assert kc_lobe("KCa'b'-ap1") == "apbp" and kc_lobe("MBON11") == ""


# ---------------------------------------------------------------------------
# 3. real data (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_every_mb_type_in_630_has_a_compartment():
    lab = load_labels()
    mb = set(lab.loc[lab.cell_class == "MBON", "hemibrain_type"]) - {""}  # 1 untyped MBON
    assert mb <= set(MBON_COMPARTMENTS)
    dans = set(lab.loc[lab.cell_class == "DAN", "hemibrain_type"]) - {""}
    assert dans - set(DAN_COMPARTMENTS) == {"PPL107", "PPL201", "PPL202", "PPL203"}


@pytest.fixture(scope="module")
def whole():
    brain = FastBrain(snapshot="630", n_threads=1)
    yield brain, load_labels()


@pytest.mark.slow
def test_whole_brain_sugar_unchanged_with_learning_on(whole):
    """Phase 3 regression: learning on (published DAN treatment), no
    training -> sugar 100 Hz gives exactly the baseline spikes."""
    from tests.test_realism import MN9, SUGAR_630
    brain, lab = whole
    ids = {"SUGAR": SUGAR_630, "MN9": MN9}
    pb = PlasticBrain(brain, lab, LearningRule(eta=5.0), dan_mode="fast")
    sugar = brain.index_of(ids["SUGAR"])
    n_steps = 5000
    ev = pb.make_events([(sugar, 100.0, 0.0, 500.0)], n_steps, np.random.default_rng(0))
    ref = brain.run_with_input_events([_unpack(ev, brain.root_ids)], excite=ids["SUGAR"],
                                      duration_ms=500.0)
    s = pb.new_state()
    out = pb.run(None, 500.0, None, state=s, events=ev, excite_rows=sugar)
    mn9 = brain.index_of([ids["MN9"]])[0]
    assert (ref.neuron == mn9).sum() > 10
    changed = not np.array_equal(s.wk, pb.wk0)
    if not changed:
        assert _same(ref.step, ref.neuron, out.step, out.neuron)
    else:                                   # sugar itself triggered some learning
        assert abs(int((out.neuron == mn9).sum()) - int((ref.neuron == mn9).sum())) <= 3


@pytest.mark.slow
def test_circuit_extraction_keeps_connections(whole):
    brain, lab = whole
    rows = mb_circuit_rows(lab)
    circ, rows2 = extract_circuit(brain, rows, n_threads=1)
    assert np.array_equal(rows, rows2)
    # connection count inside the circuit, recomputed independently
    inside = np.zeros(brain.n_neurons, bool)
    inside[rows] = True
    n = 0
    for j in rows[:200]:
        a, z = brain._indptr[j], brain._indptr[j + 1]
        n += int(inside[brain._post[a:z]].sum())
    m = circ._indptr[200]
    assert n == m

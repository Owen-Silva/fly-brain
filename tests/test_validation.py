"""Tests for sim/validation.py (the Phase 6 step-1 validation kit).

All tests use tiny networks built with FastBrain.from_arrays, or no brain at
all, so the whole file runs in seconds (no whole-brain load).
"""

import numpy as np
import pandas as pd
import pytest

from sim import validation as V
from sim.fast_engine import DEFAULT_PARAMS, FastBrain


def _chain(count):
    """Neuron A -> neuron B with ``count`` synapses."""
    return FastBrain.from_arrays(np.array([1, 2], dtype=np.int64) + 10**17, [0], [1], [count])


def _random_brain(seed=3, n=40, p=0.12, max_count=60, frac_exc=0.8):
    rng = np.random.default_rng(seed)
    mask = rng.random((n, n)) < p
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    count = rng.integers(1, max_count + 1, pre.size)
    sign = np.where(rng.random(n) < frac_exc, 1, -1)[pre]
    return FastBrain.from_arrays(np.arange(n, dtype=np.int64) + 10**17, pre, post, count * sign)


# ---------------------------------------------------------------------------
# variations
# ---------------------------------------------------------------------------
def test_one_at_a_time_rules():
    vs = V.one_at_a_time()
    assert len(vs) == len(V.PARAMETER_RULES) * 4
    assert len({v.name for v in vs}) == len(vs)
    by = {v.name: v for v in vs}
    base = DEFAULT_PARAMS
    # weight: brain connections change, the Poisson input kick does not
    for name, f in [("w_syn-20%", -0.2), ("w_syn+10%", 0.1)]:
        p = by[name].params
        assert p["w_syn"] == pytest.approx(base["w_syn"] * (1 + f))
        assert p["w_syn"] * p["f_poi"] == pytest.approx(base["w_syn"] * base["f_poi"])
    # threshold: the GAP to rest changes (7 mV -> 8.4 mV), rest/reset do not
    assert by["threshold_gap+20%"].params == {"v_th": pytest.approx(-52.0 + 7.0 * 1.2)}
    assert by["threshold_gap-20%"].params == {"v_th": pytest.approx(-52.0 + 7.0 * 0.8)}
    for key in ("t_mbr", "tau", "t_rfc", "t_dly", "r_poi"):
        assert by[f"{key}-10%"].params == {key: pytest.approx(base[key] * 0.9)}
    assert by["tau+20%"].change == pytest.approx(0.2) and by["tau+20%"].parameter == "tau"
    with pytest.raises(KeyError):
        V.one_at_a_time(["no_such_parameter"])
    # the engine rounds refractory period and delay to whole 0.1 ms steps
    assert V.effective_steps({}) == {"t_rfc_steps": 22, "t_dly_steps": 18}
    assert V.effective_steps(by["t_dly-20%"].params)["t_dly_steps"] == 14


def test_standard_variations_contents():
    vs = V.standard_variations(jitter_draws=2)
    kinds = [v.parameter for v in vs]
    assert kinds[:2] == ["baseline", "seed_noise"]
    assert kinds.count("weight_jitter") == 2 and kinds.count("jitter_control") == 1
    assert vs[1].seed_offset == V.NEW_SEEDS_OFFSET


def test_rate_factor():
    assert V.rate_factor({}) == 1.0
    assert V.rate_factor({"r_poi": 120.0}) == pytest.approx(0.8)


# ---------------------------------------------------------------------------
# verdicts, summary, warnings (pure function: no brain)
# ---------------------------------------------------------------------------
def _toy_experiment(brain, params, seed):
    # 10 at baseline; "k" scales it; seed 2 is 10% lower than the others
    return {"x": 10.0 * (1 + params.get("k", 0.0)) * (0.9 if seed == 2 else 1.0),
            "vec": pd.Series([3.0, 2.0, 1.0], index=[7, 8, 9])}


def test_verdicts_holds_and_flips():
    variations = [V.Variation("baseline"),
                  V.Variation("up", {"k": 0.2}, "k", 0.2),
                  V.Variation("edge", {"k": -0.45}, "k", -0.45),   # 5.5, 5.5, 4.95
                  V.Variation("down", {"k": -0.9}, "k", -0.9),
                  V.Variation("ignored", {"unused": 1.0}, "unused", 0.1)]
    res = V.run_validation(_toy_experiment, variations, seeds=(0, 1, 2),
                           claims={"big": V.at_least("x", 5.0)}, log=None)
    assert set(res.table.columns) == {"variation", "parameter", "change", "seed", "readout", "value"}
    assert len(res.table) == 5 * 3          # one scalar readout x 5 variations x 3 seeds
    v = res.verdicts.set_index("variation")
    assert v.loc["baseline", "verdict"] == "holds" and v.loc["up", "verdict"] == "holds"
    # one failing seed out of three is enough to flip (the strict rule)
    assert v.loc["edge", "verdict"] == "flips" and v.loc["edge", "seeds_holding"] == 2
    assert v.loc["down", "verdict"] == "flips" and v.loc["down", "seeds_holding"] == 0
    # an experiment that ignores a setting is flagged, not silently passed
    assert bool(v.loc["ignored", "identical_to_baseline"])
    assert not bool(v.loc["up", "identical_to_baseline"])
    assert v["rule"].iloc[0] == "x >= 5"
    assert not res.robust("big")
    s = res.summary("x")
    assert s.loc["up", "change_pct"] == pytest.approx(20.0)
    assert s.loc["baseline", "change_pct"] == pytest.approx(0.0)
    # vector readouts are kept aside, not in the tidy table
    assert ("up", 1, "vec") in res.vectors
    assert res.pooled_vector("up", "vec").tolist() == [3.0, 2.0, 1.0]


def test_baseline_added_and_names_unique():
    res = V.run_validation(_toy_experiment, [V.Variation("up", {"k": 0.1})], seeds=(0,), log=None)
    assert [v.name for v in res.variations] == ["baseline", "up"]
    with pytest.raises(ValueError):
        V.run_validation(_toy_experiment, [V.Variation("a"), V.Variation("a")], log=None)


def test_suppressed_claim():
    c = V.suppressed("t", "c", 0.5, 5.0)
    assert c.test({"t": 1.0, "c": 60.0})
    assert not c.test({"t": 40.0, "c": 60.0})       # not suppressed enough
    assert not c.test({"t": 0.0, "c": 1.0})         # nothing there to suppress


def test_cache_resume(tmp_path):
    variations = [V.Variation("baseline"), V.Variation("up", {"k": 0.2}, "k", 0.2)]
    first = V.run_validation(_toy_experiment, variations, seeds=(0, 1), cache_dir=tmp_path, log=None)

    def must_not_run(brain, params, seed):
        raise AssertionError("should have been read from the cache")

    again = V.run_validation(must_not_run, variations, seeds=(0, 1), cache_dir=tmp_path, log=None)
    pd.testing.assert_frame_equal(first.table, again.table)
    # changed params for the same name -> recomputed, not a stale cache hit
    changed = [V.Variation("baseline"), V.Variation("up", {"k": 0.5}, "k", 0.5)]
    new = V.run_validation(_toy_experiment, changed, seeds=(0, 1), cache_dir=tmp_path, log=None)
    assert new.summary("x").loc["up", "mean"] == pytest.approx(15.0)


# ---------------------------------------------------------------------------
# ranking change
# ---------------------------------------------------------------------------
def test_spearman_and_top_k():
    base = pd.Series([50.0, 40, 30, 20, 10, 5], index=[1, 2, 3, 4, 5, 6])
    assert V.top_k_change(base, base, k=4) == (pytest.approx(1.0), 1.0)
    rev = pd.Series([10.0, 20, 30, 40, 50, 5], index=[1, 2, 3, 4, 5, 6])
    rho, ov = V.top_k_change(base, rev, k=5)
    assert rho == pytest.approx(-1.0) and ov == 1.0
    # neuron 1 excluded (e.g. a stimulated neuron): top-2 of the rest is {2, 3}
    rho, ov = V.top_k_change(base, pd.Series([1.0, 9.0], index=[2, 7]), k=2, exclude=[1])
    assert ov == 0.5
    assert np.isnan(V.spearman([1, 1, 1], [1, 2, 3]))


# ---------------------------------------------------------------------------
# on the real engine (tiny networks)
# ---------------------------------------------------------------------------
def test_params_reach_the_engine():
    """A drives B with 60 synapses at 150 Hz: B fires. A 4x larger threshold
    gap or a 90% weaker synapse silences B, and the kit must report 'flips'."""
    brain = _chain(60)
    a, b = brain.root_ids

    def experiment(brain, params, seed):
        res = brain.run(excite=[a], duration_ms=300, n_trials=2, seed=seed, params=params)
        return {"b_hz": res.rate(b)}

    variations = ([V.baseline()] + V.one_at_a_time(["threshold_gap"], levels=(0.2, 3.0))
                  + V.one_at_a_time(["w_syn"], levels=(-0.9,)) + V.one_at_a_time(["r_poi"], levels=(-0.2,)))
    res = V.run_validation(experiment, variations, seeds=(0, 1),
                           claims={"b_fires": V.at_least("b_hz", 1.0)}, brain=brain, log=None)
    v = res.verdicts.set_index("variation")["verdict"]
    assert v["baseline"] == "holds" and v["threshold_gap+20%"] == "holds"
    assert v["threshold_gap+300%"] == "flips" and v["w_syn-90%"] == "flips"
    # a plain excite list uses params["r_poi"], so the input-rate variation acts
    assert not res.verdicts.set_index("variation").loc["r_poi-20%", "identical_to_baseline"]
    assert res.summary("b_hz").loc["r_poi-20%", "change_pct"] < 0


def test_jittered_weights_restores_and_matches_control():
    brain = _random_brain()
    original = brain._count
    exc = brain.root_ids[:5]
    base = brain.run(excite=exc, duration_ms=300, n_trials=2, seed=4)
    # no jitter: the x1000 rescaling alone must not change the result
    with V.jittered_weights(brain, frac=0.0) as extra:
        assert brain._count is not original
        ctrl = brain.run(excite=exc, duration_ms=300, n_trials=2, seed=4, params=extra)
    assert brain._count is original
    assert np.array_equal(base.step, ctrl.step) and np.array_equal(base.neuron, ctrl.neuron)
    # 20% jitter: every weight within +/-20% (plus rounding), pattern set by `draw`
    with V.jittered_weights(brain, frac=0.2, draw=1):
        j1 = brain._count.copy()
    with V.jittered_weights(brain, frac=0.2, draw=1):
        assert np.array_equal(brain._count, j1)
    with V.jittered_weights(brain, frac=0.2, draw=2):
        assert not np.array_equal(brain._count, j1)
    ratio = j1 / (original * 1000.0)
    assert ratio.min() >= 0.8 - 1e-3 and ratio.max() <= 1.2 + 1e-3 and ratio.std() > 0.05
    assert np.array_equal(np.sign(j1), np.sign(original))
    # restored even when the block fails
    with pytest.raises(RuntimeError):
        with V.jittered_weights(brain, frac=0.2):
            raise RuntimeError("boom")
    assert brain._count is original


def test_validate_standard_set_on_tiny_brain():
    brain = _random_brain()
    exc = brain.root_ids[:5]
    probe = int(brain.root_ids[np.argmax(brain.run(excite=exc, duration_ms=300, seed=0)
                                         .rates_hz * (np.arange(brain.n_neurons) >= 5))])

    def experiment(brain, params, seed):
        res = brain.run(excite=exc, duration_ms=300, n_trials=2, seed=seed, params=params)
        return {"probe_hz": res.rate(probe), "rates": res.rates()}

    res = V.validate(experiment, brain, claims={"probe": V.at_least("probe_hz", 1.0)},
                     seeds=(0, 1), jitter_draws=1, log=None)
    assert len(res.variations) == 2 + 4 * len(V.PARAMETER_RULES) + 2
    v = res.verdicts
    assert len(v) == len(res.variations) and set(v["verdict"]) <= {"holds", "flips"}
    rc = res.ranking_change("rates", k=10, exclude=exc)
    assert rc.set_index("variation").loc["baseline", "spearman_top10"] == pytest.approx(1.0)
    assert rc.set_index("variation").loc["baseline", "overlap_top10"] == 1.0
    assert brain._count.dtype == np.int32 and brain._count.max() <= 60

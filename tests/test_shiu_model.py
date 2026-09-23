"""Tests for sim/shiu_model.py, the port of the Shiu et al. 2024 fly-brain model.

Fast tests check the port against the reference code and run the exact same
simulation code on a tiny hand-built 4-neuron network. Tests marked ``slow``
load the real connectome (about 1 GB of RAM) and simulate the whole brain.
Run only the fast ones with:  pytest -m "not slow"
"""
import importlib.util
import sys
import types

import numpy as np
import pandas as pd
import pytest

from sim import shiu_model as sm

REF = sm.REF_DIR


def _load_reference_module(name, filename):
    """Import a file from data/reference/ without modifying it.

    model.py imports joblib (only used for its parallel runner, which the
    port does not use and which is not installed), so a stand-in module is
    provided for the import to succeed.
    """
    if "joblib" not in sys.modules:
        stub = types.ModuleType("joblib")
        stub.Parallel = stub.delayed = stub.parallel_backend = None
        sys.modules["joblib"] = stub
    spec = importlib.util.spec_from_file_location(name, REF / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# The port is identical to the reference
# ---------------------------------------------------------------------------
def test_parameters_identical_to_reference():
    ref = _load_reference_module("ref_model", "model.py").default_params
    assert set(ref) == set(sm.DEFAULT_PARAMS)
    for key, value in ref.items():
        assert sm.DEFAULT_PARAMS[key] == value, key


def test_brian2_uses_numpy_target():
    assert sm.prefs.codegen.target == "numpy"


def test_rates_match_reference_get_rate():
    utils = _load_reference_module("ref_utils", "utils.py")
    rng = np.random.default_rng(0)
    n = 500
    spikes = pd.DataFrame({
        "t": rng.uniform(0, 0.5, n),
        "trial": rng.integers(0, 4, n),
        "flywire_id": rng.choice([720575940600000001, 720575940600000002, 720575940600000003], n),
        "exp_name": "x",
    })
    spikes = spikes[~((spikes.flywire_id == 720575940600000003) & (spikes.trial == 2))]  # a silent trial
    ref_rate, ref_std = utils.get_rate(spikes, t_run=0.5, n_run=4)
    rates, std = sm.rates_from_spikes(spikes, duration_s=0.5, n_trials=4)
    for f in ref_rate.index:
        assert rates[f] == pytest.approx(ref_rate.loc[f, "x"])
        assert std[f] == pytest.approx(ref_std.loc[f, "x"])


# ---------------------------------------------------------------------------
# Neuron IDs
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def completeness():
    return {ds: pd.read_csv(paths[0], index_col=0).index for ds, paths in sm.DATASETS.items()}


def test_paper_ids_present_in_630(completeness):
    ids = set(completeness["630"])
    for group in (sm.SUGAR_R_630, sm.BITTER_R_630, sm.WATER_R_630, sm.IR94E_630):
        assert all(i in ids for i in group)
    assert sm.MN9_LEFT in ids and sm.MN9_RIGHT_630 in ids
    assert (len(sm.SUGAR_R_630), len(sm.BITTER_R_630), len(sm.WATER_R_630), len(sm.IR94E_630)) == (21, 21, 18, 18)


def test_783_translation_complete(completeness):
    ids = set(completeness["783"])
    for group in (sm.SUGAR_R_783, sm.BITTER_R_783, sm.WATER_R_783, sm.IR94E_783):
        assert all(i in ids for i in group)
        assert len(set(group)) == len(group)
    assert sm.MN9_LEFT in ids and sm.MN9_RIGHT_783 in ids
    # exactly the three renamed neurons differ
    assert sum(a != b for a, b in zip(sm.SUGAR_R_630, sm.SUGAR_R_783)) == 1
    assert sum(a != b for a, b in zip(sm.BITTER_R_630, sm.BITTER_R_783)) == 1
    assert sm.WATER_R_783 == sm.WATER_R_630


def test_ids_map_to_row_positions():
    # the reference maps FlyWire ID -> Brian2 index by row position in the
    # completeness file; unknown IDs must fail loudly, like the reference
    conn = _tiny_connectome()
    assert sm.to_indices(conn, [11, 13]) == [1, 3]
    with pytest.raises(KeyError):
        sm.to_indices(conn, [999])


# ---------------------------------------------------------------------------
# The real simulation code on a tiny hand-built network
# ---------------------------------------------------------------------------
def _tiny_connectome():
    """4 neurons: 10 -> 11 excitatory (100 synapses), 13 -> 11 inhibitory
    (300 synapses, GABA-like), 12 unconnected."""
    flyids = np.array([10, 11, 12, 13], dtype=np.int64)
    return sm.Connectome(
        dataset="tiny",
        flyids=flyids,
        flyid2i={int(f): i for i, f in enumerate(flyids)},
        i_pre=np.array([0, 3], dtype=np.int64),
        i_post=np.array([1, 1], dtype=np.int64),
        exc_x_conn=np.array([100.0, -300.0]),
    )


def test_tiny_run_produces_spikes():
    res = sm.run_trials([10], duration_ms=300, n_trials=2, rate_hz=150, seed=1, dataset=_tiny_connectome())
    assert 60 < res.rate_of(10) < 250          # driven neuron follows its ~150 Hz input
    assert res.rate_of(11) > 10                 # excited partner fires
    assert res.rate_of(12) == 0                 # unconnected neuron stays silent
    assert set(res.spikes.columns) == {"t", "trial", "flywire_id", "exp_name"}
    assert res.settings["seeds"] == [1, 2]


def test_no_input_no_spikes():
    res = sm.run_trials([], duration_ms=100, n_trials=1, seed=1, dataset=_tiny_connectome())
    assert res.spikes.empty


def test_inhibition_and_silencing():
    conn = _tiny_connectome()
    base = sm.run_trials([10], duration_ms=300, n_trials=2, rate_hz=150, seed=3, dataset=conn)
    inhib = sm.run_trials([10], excite2_ids=[13], rate2_hz=150, duration_ms=300, n_trials=2,
                          rate_hz=150, seed=3, dataset=conn)
    silenced = sm.run_trials([10], silence_ids=[10], duration_ms=300, n_trials=2, rate_hz=150,
                             seed=3, dataset=conn)
    assert inhib.rate_of(11) < base.rate_of(11)       # inhibitory input lowers firing
    assert silenced.rate_of(10) > 60                   # silencing cuts the OUTPUT only...
    assert silenced.rate_of(11) == 0                   # ...so the partner goes quiet


def test_same_seed_same_spikes():
    conn = _tiny_connectome()
    a = sm.run_trials([10], duration_ms=200, n_trials=2, rate_hz=150, seed=7, dataset=conn)
    b = sm.run_trials([10], duration_ms=200, n_trials=2, rate_hz=150, seed=7, dataset=conn)
    c = sm.run_trials([10], duration_ms=200, n_trials=1, rate_hz=150, seed=8, dataset=conn)
    pd.testing.assert_frame_equal(a.spikes, b.spikes)
    # trial 1 of a (seed 8, restored from the stored start state) equals a fresh run with seed 8
    t1 = a.spikes[a.spikes.trial == 1][["t", "flywire_id"]].to_numpy()
    np.testing.assert_array_equal(t1, c.spikes[["t", "flywire_id"]].to_numpy())


# ---------------------------------------------------------------------------
# Whole brain (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.parametrize("dataset,n_neurons,n_connections", [
    ("630", 127_400, 14_687_178),
    ("783", 138_639, 15_091_983),
])
def test_connectome_loads(dataset, n_neurons, n_connections):
    conn = sm.load_connectome(dataset)  # also checks index/ID consistency
    assert conn.n == n_neurons and len(conn.i_pre) == n_connections
    assert conn.flyids.dtype == np.int64
    assert (conn.exc_x_conn < 0).any() and (conn.exc_x_conn > 0).any()
    sm._CACHE.pop(dataset, None)


@pytest.mark.slow
def test_sugar_drives_mn9():
    """Paper: sugar GRNs at 100 Hz drive MN9 to 65.7 +/- 3.3 Hz (snapshot 630)."""
    res = sm.run_trials(sm.SUGAR_R_630, duration_ms=500, n_trials=2, rate_hz=100, seed=42, dataset="630")
    assert res.rate_of(sm.MN9_LEFT) > 30
    assert res.rate_of(sm.MN9_LEFT) > res.rate_of(sm.MN9_RIGHT_630) > 0


@pytest.mark.slow
def test_bitter_alone_leaves_mn9_silent():
    """Paper: bitter GRNs alone never activate MN9."""
    res = sm.run_trials(sm.BITTER_R_630, duration_ms=500, n_trials=1, rate_hz=200, seed=42, dataset="630")
    assert res.rate_of(sm.MN9_LEFT) == 0
    assert res.rate_of(sm.BITTER_R_630[0]) > 100   # the bitter neurons themselves are firing

"""Tests for sim/fast_engine.py.

The main check: on small random networks, the fast engine and the
reference's own Brian2 code (data/reference/model.py, run with Brian2's numpy
engine) are fed the SAME input spikes, and must produce the SAME spikes at the
SAME time steps, and the same voltage traces.
"""

import importlib.util
import sys
import types

import numpy as np
import pandas as pd
import pytest

from sim.fast_engine import FastBrain, REFERENCE_DIR

SUGAR_GRNS_630 = [  # data/reference/example.ipynb, `neu_sugar`
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]
MN9 = 720575940660219265


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _load_reference_model():
    """Import data/reference/model.py unchanged. It imports joblib (only used
    for its parallel runner, which we do not call), so stub it if missing."""
    if "joblib" not in sys.modules:
        try:
            import joblib  # noqa: F401
        except ImportError:
            stub = types.ModuleType("joblib")
            stub.Parallel = stub.delayed = stub.parallel_backend = None
            sys.modules["joblib"] = stub
    spec = importlib.util.spec_from_file_location("shiu_reference_model",
                                                  REFERENCE_DIR / "model.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _random_network(rng, n, p_conn, max_count, frac_exc):
    """A tiny random connectome in the reference file format."""
    root_ids = (720575940600000000 + rng.choice(10**8, n, replace=False)).astype(np.int64)
    mask = rng.random((n, n)) < p_conn
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    perm = rng.permutation(pre.size)            # file order is not sorted
    pre, post = pre[perm], post[perm]
    count = rng.integers(1, max_count + 1, pre.size)
    sign = np.where(rng.random(n) < frac_exc, 1, -1)[pre]   # sign per presynaptic neuron
    df_comp = pd.DataFrame({"Completed": True}, index=pd.Index(root_ids))
    df_con = pd.DataFrame({
        "Presynaptic_ID": root_ids[pre], "Postsynaptic_ID": root_ids[post],
        "Presynaptic_Index": pre, "Postsynaptic_Index": post,
        "Connectivity": count, "Excitatory": sign,
        "Excitatory x Connectivity": sign * count,
    })
    return df_comp, df_con


def _input_events(rng, exc_idx, n_steps, prob):
    steps, idx = [], []
    for i in exc_idx:
        s = np.flatnonzero(rng.random(n_steps) < prob)
        steps.append(s)
        idx.append(np.full(s.size, i))
    return np.concatenate(steps), np.concatenate(idx)


def _run_brian2(ref, comp_path, con_path, exc_idx, slnc_idx, ev_steps, ev_idx,
                n_steps, rec_idx):
    """The reference model (create_model + silence), with the Poisson inputs
    replaced by the given input spikes delivered exactly like PoissonInput:
    'v += w_syn * f_poi' in the synapses slot, and refractory period 0 for
    stimulated neurons (as in model.poi)."""
    import brian2 as b2
    b2.prefs.codegen.target = "numpy"
    b2.defaultclock.dt = 0.1 * b2.ms
    params = ref.default_params
    neu, syn, spk_mon = ref.create_model(comp_path, con_path, params)
    for i in exc_idx:
        neu[i].rfc = 0 * b2.ms
    syn = ref.silence(list(slnc_idx), syn)
    slot = {int(i): k for k, i in enumerate(exc_idx)}
    gen = b2.SpikeGeneratorGroup(len(exc_idx), [slot[int(i)] for i in ev_idx],
                                 np.asarray(ev_steps) * b2.defaultclock.dt)
    kick = b2.Synapses(gen, neu, on_pre="v_post += kick",
                       namespace={"kick": params["w_syn"] * params["f_poi"]})
    kick.connect(i=np.arange(len(exc_idx)), j=np.asarray(exc_idx))
    mon = b2.StateMonitor(neu, "v", record=list(rec_idx))
    net = b2.Network(neu, syn, spk_mon, gen, kick, mon)
    net.run(n_steps * b2.defaultclock.dt)
    steps = np.round(np.asarray(spk_mon.t / b2.defaultclock.dt)).astype(np.int64)
    return (np.asarray(spk_mon.i, np.int64), steps,
            np.asarray(mon.v / b2.volt))


@pytest.fixture(scope="module")
def reference_model():
    return _load_reference_model()


# ---------------------------------------------------------------------------
# 1. identical to Brian2 on small networks with identical input
# ---------------------------------------------------------------------------
CASES = [
    # seed, neurons, connection prob, max synapse count, frac excitatory, n silenced
    (1, 60, 0.10, 60, 0.75, 0),
    (2, 60, 0.10, 60, 0.75, 3),
    (3, 100, 0.06, 90, 0.60, 5),
    (4, 40, 0.25, 40, 0.85, 2),
]


@pytest.mark.parametrize("seed,n,p_conn,max_count,frac_exc,n_sil", CASES)
def test_identical_to_reference_brian2(tmp_path, reference_model, seed, n, p_conn,
                                       max_count, frac_exc, n_sil):
    rng = np.random.default_rng(seed)
    df_comp, df_con = _random_network(rng, n, p_conn, max_count, frac_exc)
    comp_path, con_path = tmp_path / "comp.csv", tmp_path / "con.parquet"
    df_comp.to_csv(comp_path)
    df_con.to_parquet(con_path)

    n_steps = 2000                                   # 200 ms
    exc_idx = np.sort(rng.choice(n, 8, replace=False))
    rest = np.setdiff1d(np.arange(n), exc_idx)
    slnc_idx = np.sort(rng.choice(rest, n_sil, replace=False)) if n_sil else np.zeros(0, int)
    # 150 Hz, plus two neurons at 1500 Hz so kicks often land on spike steps
    ev_s, ev_i = _input_events(rng, exc_idx[:6], n_steps, 0.015)
    ev_s2, ev_i2 = _input_events(rng, exc_idx[6:], n_steps, 0.15)
    ev_steps, ev_idx = np.concatenate([ev_s, ev_s2]), np.concatenate([ev_i, ev_i2])
    rec_idx = np.sort(rng.choice(n, 6, replace=False))

    b_i, b_t, b_v = _run_brian2(reference_model, comp_path, con_path, exc_idx, slnc_idx,
                                ev_steps, ev_idx, n_steps, rec_idx)

    brain = FastBrain(comp_path=comp_path, con_path=con_path)
    ids = brain.root_ids
    res = brain.run_with_input_events(
        [(ev_steps, ids[ev_idx])], excite=ids[exc_idx], silence=ids[slnc_idx],
        duration_ms=n_steps * 0.1, record_v=ids[rec_idx])

    brian = sorted(zip(b_t.tolist(), b_i.tolist()))
    fast = sorted(zip(res.step.tolist(), res.neuron.tolist()))
    assert len(brian) > 300, "network too quiet to be a meaningful test"
    assert len({i for _, i in brian} - set(exc_idx.tolist())) > 5, "activity did not spread"
    assert fast == brian                              # identical spikes, identical steps
    for r, rid in enumerate(ids[rec_idx]):
        np.testing.assert_array_equal(res.voltages_V[int(rid)][0], b_v[r])  # bit for bit


# ---------------------------------------------------------------------------
# 2. small targeted checks
# ---------------------------------------------------------------------------
def _chain(counts):
    """Neuron 0 -> 1 -> 2 ... with the given signed synapse counts."""
    n = len(counts) + 1
    return FastBrain.from_arrays(np.arange(n, dtype=np.int64) + 10**17,
                                 np.arange(n - 1), np.arange(1, n), np.asarray(counts))


def test_delay_refractory_and_reset():
    brain = _chain([300])        # 300 synapses x 0.275 mV: one spike makes the target fire
    ids = brain.root_ids
    res = brain.run_with_input_events([(np.array([10]), ids[:1])], excite=ids[:1],
                                      duration_ms=10.0)
    steps = dict(zip(res.neuron.tolist(), res.step.tolist()))
    assert steps[0] == 11                  # kick at step 10 -> spike on the next step
    assert steps[1] > 11 + 18              # input arrives 18 steps (1.8 ms) later, then rises
    assert (res.neuron == 1).sum() == 1


def test_silenced_neuron_fires_but_has_no_effect():
    brain = _chain([300])
    ids = brain.root_ids
    ev = [(np.array([10]), ids[:1])]
    res = brain.run_with_input_events(ev, excite=ids[:1], silence=ids[:1], duration_ms=10.0)
    assert res.neuron.tolist() == [0]      # neuron 0 still spikes, neuron 1 never does


def test_inhibition_blocks_firing():
    brain = FastBrain.from_arrays(np.array([1, 2, 3]) + 10**17, [0, 1], [2, 2], [300, -600])
    ids = brain.root_ids
    both = [(np.array([10, 10]), ids[:2])]
    only_exc = [(np.array([10]), ids[:1])]
    r_both = brain.run_with_input_events(both, excite=ids[:2], duration_ms=10.0)
    r_exc = brain.run_with_input_events(only_exc, excite=ids[:2], duration_ms=10.0)
    assert 2 in r_exc.neuron.tolist() and 2 not in r_both.neuron.tolist()


def test_poisson_input_rate():
    # 300 unconnected stimulated neurons, 10 s at 150 Hz. Each kick makes the
    # neuron fire on the next step unless the kick lands on a spike step, so
    # the expected rate is 150 / (1 + 150 * dt) = 147.78 Hz.
    brain = FastBrain.from_arrays(np.arange(300) + 10**17, [], [], [])
    res = brain.run(excite=brain.root_ids, duration_ms=10_000, n_trials=1, seed=7)
    expected = 150 / (1 + 150 * 1e-4)
    assert abs(res.rates_hz.mean() - expected) < 0.01 * expected


def test_deterministic_and_trial_independent():
    rng = np.random.default_rng(0)
    _, df = _random_network(rng, 50, 0.1, 60, 0.8)
    brain = FastBrain.from_arrays(np.arange(50) + 10**17, df["Presynaptic_Index"],
                                  df["Postsynaptic_Index"], df["Excitatory x Connectivity"])
    exc = brain.root_ids[:5]
    a = brain.run(excite=exc, duration_ms=200, n_trials=3, seed=11)
    b = brain.run(excite=exc, duration_ms=200, n_trials=3, seed=11)
    c = brain.run(excite=exc, duration_ms=200, n_trials=1, seed=11)
    d = brain.run(excite=exc, duration_ms=200, n_trials=1, seed=12)
    assert np.array_equal(a.step, b.step) and np.array_equal(a.neuron, b.neuron)
    m = a.trial == 0
    assert np.array_equal(a.step[m], c.step) and np.array_equal(a.neuron[m], c.neuron)
    assert not (np.array_equal(c.step, d.step) and np.array_equal(c.neuron, d.neuron))
    brain.n_threads = 2
    e = brain.run(excite=exc, duration_ms=200, n_trials=3, seed=11)
    assert np.array_equal(a.step, e.step) and np.array_equal(a.trial, e.trial)


def test_ids_must_be_int64():
    brain = _chain([10])
    with pytest.raises(TypeError):
        brain.run(excite=[float(brain.root_ids[0])], duration_ms=1)
    with pytest.raises(KeyError):
        brain.run(excite=[123], duration_ms=1)
    assert brain.root_ids.dtype == np.int64


def test_result_helpers():
    brain = _chain([100])
    ids = brain.root_ids
    res = brain.run(excite=ids[:1], duration_ms=500, n_trials=2, seed=3)
    df = res.to_dataframe("x")
    assert list(df.columns) == ["t", "trial", "flywire_id", "exp_name"]
    assert df["flywire_id"].dtype == np.int64
    st = res.rate_stats()
    assert np.isclose(st.loc[ids[0], "mean_hz"], res.rate(ids[0]))
    trains = res.spike_trains()
    assert len(trains) == 2 and int(ids[0]) in trains[0]
    assert sum(len(v) for t in trains for v in t.values()) == res.step.size


# ---------------------------------------------------------------------------
# 3. whole brain (slow)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_sugar_drives_mn9_whole_brain_v630():
    """Paper: sugar GRNs at 100 Hz -> MN9 at 65.7 +/- 3.3 Hz (30 trials).
    Also compare with the authors' own Brian2 output for the same run
    (data/reference/results/example/sugarR_100Hz.parquet)."""
    brain = FastBrain(snapshot="630", n_threads=2)
    res = brain.run(excite=SUGAR_GRNS_630, rate_hz=100, duration_ms=1000,
                    n_trials=30, seed=0)
    mn9 = res.rate(MN9)
    assert 60 < mn9 < 72, mn9

    ref = pd.read_parquet(REFERENCE_DIR / "results" / "example" / "sugarR_100Hz.parquet")
    ref_rate = ref.groupby("flywire_id").size() / 30.0
    ours = res.rates()
    both = pd.concat([ref_rate.rename("ref"), ours.rename("fast")], axis=1).fillna(0.0)
    assert abs(mn9 - both.loc[MN9, "ref"]) < 4.0
    assert np.corrcoef(both["ref"], both["fast"])[0, 1] > 0.99

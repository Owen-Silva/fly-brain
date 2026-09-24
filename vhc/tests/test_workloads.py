"""Workload checks. The engine-equivalence test reads the 36-neuron circuit file and imports
sim/fast_engine.py read-only (skipped if either is missing)."""
import numpy as np
import pytest

from vhc.paths import MINIMAL, ROOT
from vhc.workloads import electrode_test, exact, feeding, odour

HAVE_CIRCUIT = (MINIMAL / "results" / "minimal_circuit.json").exists()
HAVE_ENGINE = (ROOT / "sim" / "fast_engine.py").exists()


@pytest.mark.skipif(not (HAVE_CIRCUIT and HAVE_ENGINE), reason="circuit file or engine missing")
def test_lif_matches_project_engine_spike_for_spike():
    from sim.fast_engine import FastBrain
    net, mn9, pos = feeding.load_circuit("36")
    pre = np.repeat(np.arange(net.n), np.diff(net.indptr))
    fb = FastBrain.from_arrays(np.array(net.names), pre, net.post, net.count.astype(np.int64),
                               n_threads=1)
    exc = feeding.excite_for("sugar+bitter", feeding.paper_ids(), pos)
    from vhc.cores.lif import run_poisson
    mine = run_poisson(net, exc, 300.0, 2, 5)
    ref = fb.run(excite={int(net.names[i]): r for i, r in exc.items()}, duration_ms=300.0,
                 n_trials=2, seed=5)
    for k in range(2):
        a = np.lexsort((mine[k].spike_neurons, mine[k].spike_steps))
        sel = ref.trial == k
        b = np.lexsort((ref.neuron[sel], ref.step[sel]))
        assert np.array_equal(mine[k].spike_steps[a], ref.step[sel][b])
        assert np.array_equal(mine[k].spike_neurons[a], ref.neuron[sel][b])


@pytest.mark.skipif(not HAVE_CIRCUIT, reason="circuit file missing")
def test_feeding_decisions_36():
    r = feeding.run("36", n_trials=4, seed=0)
    assert r["bitter"]["mn9_hz"].max() == 0.0                # bitter alone: MN9 silent
    assert r["sugar"]["mn9_hz"].mean() > feeding.THRESHOLD_HZ
    assert r["sugar+bitter"]["mn9_hz"].mean() < r["sugar"]["mn9_hz"].mean()   # the brake
    assert feeding.accuracy(r) >= 0.9


def test_exact_workloads_are_exact():
    for kind in ("sum", "sort"):
        t, ok = exact.measure_x86(kind, reps=3)
        assert ok and t > 0
    assert exact.m33_cost("sum").time_s == pytest.approx(exact.N * 4 / 150e6)


def test_odour_learner_synthetic():
    s = odour.synthetic_setup()
    r = odour.run_protocol(s, seed=0)
    assert r["accuracy"] > 3 / s.P.shape[0]                   # well above chance
    r8 = odour.run_protocol(s, seed=0, bits=8)
    assert abs(r8["accuracy"] - r["accuracy"]) < 0.15        # 8-bit read-out: close
    c = odour.neuro_counts(s, r["Xtr"], r["Htr"], s.P.shape[0])
    assert c["syn_event"] > c["input_event"] > 0 and c["syn_update"] > 0


def test_electrode_curve_small():
    from vhc.cores.living import CultureParams
    r = electrode_test.run(n_train=6, n_test=3, channels=(4, 64), drift_days=(),
                           params=CultureParams(n=300, dish_um=800.0))
    assert set(r["curve"]) >= {4, 64, "all cells"}
    assert all(0.0 <= v <= 1.0 for v in r["curve"].values())

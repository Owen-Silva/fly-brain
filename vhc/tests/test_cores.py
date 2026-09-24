"""Fast checks of the virtual computer's parts (run: .venv\\Scripts\\python.exe -m pytest vhc/tests -q)."""
import numpy as np
import pytest

from vhc.cores import conventional, electrodes, gpu, neuromorphic
from vhc.cores.lif import Network, run_poisson, run_trial
from vhc.cores.living import Culture, CultureParams
from vhc.ledger import Cost
from vhc.prices import LOIHI, M33_CLOCK_HZ, table
from vhc.scheduler import HYBRID, HYBRID_LIVING, Job, route


def chain(n=5, w=40.0):
    """0 -> 1 -> ... -> n-1, strong enough that each spike passes on."""
    return Network.from_edges(n, np.arange(n - 1), np.arange(1, n), np.full(n - 1, w))


def test_lif_counts_events_and_spikes():
    net = chain()
    res = run_poisson(net, {0: 200.0}, duration_ms=200.0, n_trials=1, seed=1)[0]
    c = res.counts
    assert c["steps"] == 2000 and c["neurons"] == 5
    assert c["input_event"] > 0 and c["spikes"] > 0
    # every spike of neurons 0..3 is delivered to exactly one target (unless too late)
    sent = int(np.sum(res.spike_neurons < 4))
    assert sent - 20 <= c["syn_event"] <= sent


def test_lif_same_seed_same_spikes_and_quantize():
    net = chain()
    a = run_poisson(net, {0: 150.0}, 100.0, 1, 3)[0]
    b = run_poisson(net, {0: 150.0}, 100.0, 1, 3)[0]
    assert np.array_equal(a.spike_neurons, b.spike_neurons)
    q = Network.from_edges(3, [0, 1], [1, 2], [100.0, 3.0]).quantized(4)   # levels of 100/7
    assert abs(q.count.max() - 100.0) < 1e-9 and q.count.min() == 0.0      # 3 rounds to 0


def test_dead_neurons_never_spike():
    net = chain()
    alive = np.array([True, False, True, True, True])
    steps = np.arange(0, 1000, 50)
    res = run_trial(net, (steps, np.zeros(steps.size, np.int64)), 1000, excited_idx=[0], alive=alive)
    assert 1 not in set(res.spike_neurons.tolist())
    assert 2 not in set(res.spike_neurons.tolist())      # nothing gets past the dead cell


def test_neuromorphic_modes():
    c = {"steps": 10000, "neurons": 36, "spikes": 1000, "syn_event": 5000, "input_event": 900}
    clk, evt = neuromorphic.price(c, "clocked"), neuromorphic.price(c, "event")
    e_clock = 36 * 10000 * LOIHI["nu_inactive_J"].value
    assert clk.energy_J > e_clock                            # the clock alone costs this much
    assert evt.energy_J < clk.energy_J                       # sparse activity: events win
    assert clk.label == evt.label == "modeled"
    with pytest.raises(ValueError):
        neuromorphic.price(c, "magic")


def test_m33_cycles_to_time():
    cost = conventional.price({"neuron_update": 150e6 / 25}, "m33")   # 150e6 cycles
    assert cost.time_s == pytest.approx(150e6 / M33_CLOCK_HZ.value)
    assert cost.energy_J == pytest.approx(cost.time_s * 30e-3)
    with pytest.raises(KeyError):
        conventional.price({"teleport": 1}, "m33")


def test_gpu_launch_bound_for_tiny_work():
    tiny = gpu.price(launches=100)
    assert tiny.time_s == pytest.approx(100 * 5e-6)
    assert tiny.energy_J == pytest.approx(tiny.time_s * 70.0)


def test_cost_addition_keeps_worst_label():
    s = Cost(1, 2, "measured", "a") + Cost(1, 1, "guessed", "b")
    assert (s.time_s, s.energy_J, s.label) == (2, 3, "guessed")


def test_every_price_is_labelled():
    labels = {r[3] for r in table()}
    assert labels <= {"PUBLISHED", "MEASURED", "ASSUMED", "GUESSED"}
    assert all(r[4] for r in table())                       # every price has a source/reason


def test_scheduler_rules():
    assert route(Job("sum", "exact", 1.0), HYBRID)[0] == "conventional"
    assert route(Job("taste", "spiking"), HYBRID)[0] == "neuromorphic"
    assert route(Job("pong", "adaptive-bio"), HYBRID_LIVING)[0] == "living"
    assert route(Job("pong", "adaptive-bio"), HYBRID)[0] == "neuromorphic"
    est = {"neuromorphic": (0.6, 1e-6), "conventional": (0.9, 1e-3)}
    assert route(Job("odour", "learning", 0.8), HYBRID, est)[0] == "conventional"
    assert route(Job("odour", "learning", 0.5), HYBRID, est)[0] == "neuromorphic"
    with pytest.raises(ValueError):
        route(Job("sum", "exact"), ("neuromorphic",))


def test_electrodes_hear_crowds_and_noise_matters():
    xy = np.random.default_rng(0).random((500, 2)) * 1000
    arr = electrodes.ElectrodeArray(4, 1000)
    p = arr.detect_prob(xy)
    assert p.shape == (4, 500) and (p > 0.5).sum(1).min() >= 1     # each hears several cells
    noisy = electrodes.ElectrodeArray(4, 1000, noise_uv=20.0).detect_prob(xy)
    assert noisy.sum() < p.sum()                                   # more noise, fewer detections
    reach = electrodes.stim_reach(np.array([[500.0, 500.0]]), xy)
    assert (reach > 0.3).sum() > 1                                 # one electrode reaches many cells


def test_culture_fatigue_drift_death_plasticity():
    cult = Culture(CultureParams(n=200, dish_um=600.0), seed=0)
    reach = electrodes.stim_reach(np.array([[300.0, 300.0]]), cult.xy)
    e0 = cult._efficacy(0)
    for k in range(5):
        cult.trial([(0.0, 0)], 20.0, reach, iti_s=0.1, seed=k)
    assert cult._efficacy(0) < e0                        # fatigue
    cult.clock_s += 1000.0
    assert cult._efficacy(0) > 0.99                      # recovery after rest
    w0 = cult.w.copy()
    cult.age(30)
    assert not np.allclose(cult.w, w0) and cult.alive.mean() < 1.0   # drift and death
    assert np.all(np.sign(cult.w) == np.sign(w0))       # drift never flips a synapse's sign
    w1 = cult.w.copy()
    n = cult.hebbian(np.ones(cult.p.n))
    assert n > 0 and (cult.w >= w1 - 1e-12).all()

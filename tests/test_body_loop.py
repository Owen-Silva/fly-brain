"""Tests for the Phase 9 brain-body loop (sim/body/).

Fast checks only (no long physics runs):
* the window-by-window brain gives spike-for-spike the same result as one
  uninterrupted FastBrain run (so carrying state across windows is exact);
* the odor world uses the published 1 / distance^2 rule;
* the sensor -> ORN rate and DN -> drive mappings do what their docstrings say,
  including the turn SIGN;
* the hand-written comparison rule equals FlyGym 1.x's example code;
* one very short closed-loop trial runs (only where FlyGym is installed,
  i.e. in .venv-body; skipped in the main .venv).
"""

import importlib.util

import numpy as np
import pytest

from sim.body.brain_stepper import BrainStepper
from sim.body.mapping import (
    DN_IDS, DriveMapping, LABELS_630, SensorMapping, dm1_orn_ids, orn_ids,
    published_taxis_turn, turn_to_drive,
)
from sim.body.odor import SENSOR_ORDER, OdorWorld, sensor_positions
from sim.fast_engine import FastBrain

HAS_FLYGYM = importlib.util.find_spec("flygym") is not None


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _tiny_brain(seed=1, n=150, p=0.08):
    rng = np.random.default_rng(seed)
    ids = (720575940600000000 + rng.choice(10**8, n, replace=False)).astype(np.int64)
    mask = rng.random((n, n)) < p
    np.fill_diagonal(mask, False)
    pre, post = np.nonzero(mask)
    cnt = rng.integers(1, 12, pre.size) * np.where(rng.random(n) < 0.7, 1, -1)[pre]
    return FastBrain.from_arrays(ids, pre, post, cnt), ids, rng


def _rates(**kw):
    r = {k: 0.0 for k in DN_IDS}
    r.update(kw)
    return r


# ---------------------------------------------------------------------------
# 1. brain stepper == FastBrain
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("window_steps", [1, 7, 18, 50, 173, 3000])
def test_windowed_brain_matches_one_fastbrain_run(window_steps):
    brain, ids, rng = _tiny_brain()
    exc, sil = ids[:15], ids[20:23]
    n_steps = 3000
    steps = rng.integers(0, n_steps, 900)
    who = exc[rng.integers(0, 15, 900)]
    ref = brain.run_with_input_events([(steps, who)], excite=exc, silence=sil,
                                      duration_ms=n_steps * 0.1)
    assert ref.step.size > 100                      # the network is really active
    st = BrainStepper(brain, exc, silence=sil)
    got_s, got_n, t = [], [], 0
    while t < n_steps:
        w = min(window_steps, n_steps - t)
        sel = (steps >= t) & (steps < t + w)
        r = st.step_events(steps[sel] - t, who[sel], w * 0.1)
        assert r.start_ms == pytest.approx(t * 0.1)
        got_s.append(r.spike_steps)
        got_n.append(r.spike_index)
        t += w
    np.testing.assert_array_equal(np.concatenate(got_s), ref.step)
    np.testing.assert_array_equal(np.concatenate(got_n), ref.neuron)
    assert st.n_active == ref.neurons_reached[0]


def test_poisson_windows_zero_rate_gives_no_input_and_rates_are_counted():
    brain, ids, _ = _tiny_brain()
    st = BrainStepper(brain, ids[:10], seed=3)
    w0 = st.step(0.0, 20.0)
    assert w0.n_input_kicks == 0 and w0.spike_index.size == 0
    w1 = st.step(np.full(10, 500.0), 20.0)          # expected 10 x 500 Hz x 20 ms = 100 kicks
    assert 60 < w1.n_input_kicks < 140
    idx = np.arange(brain.n_neurons)
    np.testing.assert_allclose(w1.rates_hz(idx).sum() * 0.02, w1.spike_index.size)
    assert st.time_ms == pytest.approx(40.0)


# ---------------------------------------------------------------------------
# 2. odor world
# ---------------------------------------------------------------------------
def test_odor_is_inverse_square_and_sums_over_sources():
    w = OdorWorld([[0, 0, 0]], [2.0])
    np.testing.assert_allclose(w.intensity([[1, 0, 0], [0, 2, 0], [0, 0, 4]]),
                               [2.0, 0.5, 2.0 / 16])
    w2 = OdorWorld([[0, 0, 0], [10, 0, 0]], [1.0, 1.0])
    assert w2.intensity([[5, 0, 0]])[0] == pytest.approx(2 / 25)
    off = OdorWorld.no_odor([[0, 0, 0]])
    assert off.intensity([[1, 0, 0]])[0] == 0.0


def test_sensor_positions_follow_parent_rotation():
    eye = np.eye(3)
    pos = {"Rostrum": np.zeros(3), "LFuniculus": np.array([1.0, 0.2, 1.0]),
           "RFuniculus": np.array([1.0, -0.2, 1.0])}
    out = sensor_positions(pos, {k: eye for k in pos})
    np.testing.assert_allclose(out[SENSOR_ORDER.index("LAntenna")], [1.02, 0.2, 0.9])
    np.testing.assert_allclose(out[SENSOR_ORDER.index("LPalp")], [-0.15, 0.15, -0.15])
    yaw90 = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])   # facing +y
    out = sensor_positions(pos, {k: yaw90 for k in pos})
    np.testing.assert_allclose(out[SENSOR_ORDER.index("LPalp")], [-0.15, -0.15, -0.15])


# ---------------------------------------------------------------------------
# 3. sensors -> ORN rates
# ---------------------------------------------------------------------------
def test_sensor_mapping_shape():
    m = SensorMapping()
    assert m.rate(0.0) == 0.0
    assert m.rate(m.i_half) == pytest.approx(m.r_max_hz / 2)
    assert m.rate(1e6) == pytest.approx(m.r_max_hz, rel=1e-3)
    assert m.rate(-1.0) == 0.0
    xs = np.logspace(-5, 1, 50)
    assert np.all(np.diff(m.rate(xs)) > 0)
    r = m.orn_rates(0.02, 0.005, 3, 2)
    np.testing.assert_allclose(r, [100, 100, 100, 50, 50])


@pytest.mark.skipif(not LABELS_630.exists(), reason="630 label table not downloaded")
def test_dm1_orns_are_the_phase5_set():
    left, right = dm1_orn_ids()
    assert (left.size, right.size) == (35, 33)
    assert np.intersect1d(left, right).size == 0
    # Other glomeruli can be swapped in (e.g. DA1 for docs/phase6-steering.md).
    l1, r1 = orn_ids("ORN_DA1")
    assert l1.size > 0 and r1.size > 0 and np.intersect1d(l1, left).size == 0
    with pytest.raises(ValueError):
        orn_ids("ORN_NOPE")


# ---------------------------------------------------------------------------
# 4. DN rates -> drive
# ---------------------------------------------------------------------------
def test_turn_to_drive():
    np.testing.assert_allclose(turn_to_drive(0.0), [1.0, 1.0])
    np.testing.assert_allclose(turn_to_drive(1.0), [0.2, 1.0])     # full LEFT turn
    np.testing.assert_allclose(turn_to_drive(-0.5), [1.0, 0.6])    # half RIGHT turn
    np.testing.assert_allclose(turn_to_drive(5.0, forward=0.5), [0.1, 0.5])


def test_more_left_dna02_lowers_left_drive_ie_turns_left():
    m = DriveMapping()
    drive, turn, fwd = m.drive(_rates(DNa02_L=40.0))
    assert turn > 0 and drive[0] < drive[1] and fwd == 1.0
    drive_r, turn_r, _ = m.drive(_rates(DNa02_R=40.0))
    assert turn_r == pytest.approx(-turn)
    np.testing.assert_allclose(drive_r, drive[::-1])
    assert m.turn(_rates(DNa02_L=20.0)) == pytest.approx(np.tanh(1.0))
    assert m.turn(_rates(DNa01_L=20.0)) == pytest.approx(np.tanh(0.5))
    drive0, turn0, _ = m.drive(_rates())
    assert turn0 == 0.0
    np.testing.assert_allclose(drive0, [1.0, 1.0])
    # Walking neurons do not steer.
    assert m.turn(_rates(DNg100_L=50.0, DNp09_R=50.0)) == 0.0


def test_readout_is_swappable_in_one_config_entry():
    """A different steering read-out drops in through DriveMapping alone."""
    m = DriveMapping(neuron_ids={"X_L": 1, "X_R": 2},
                     turn_weights={"X_L": 1.0, "X_R": -1.0}, forward_weights={},
                     turn_scale_hz=10.0)
    assert m.readout_names == ["X_L", "X_R"]
    assert m.turn({"X_L": 10.0, "X_R": 0.0}) == pytest.approx(np.tanh(1.0))
    with pytest.raises(KeyError):
        DriveMapping(neuron_ids={"X_L": 1}, turn_weights={"Y": 1.0}, forward_weights={})


def test_forward_drive_from_walking_dns_in_brain_mode():
    m = DriveMapping(forward_mode="brain")
    assert m.forward(_rates()) == 0.0
    assert m.forward(_rates(DNg100_L=20.0, DNg100_R=20.0)) == pytest.approx(0.5)
    assert m.forward(_rates(DNg100_L=80, DNg100_R=80, DNp09_L=80, DNp09_R=80)) == 1.0
    with pytest.raises(ValueError):
        DriveMapping(forward_mode="nope").forward(_rates())


# ---------------------------------------------------------------------------
# 5. hand-written comparison rule (NOT brain-driven) == FlyGym 1.x example
# ---------------------------------------------------------------------------
def _example_control_signal(odor_intensity_row):
    """Verbatim logic of flygym-gymnasium 1.3.2 simple_odor_taxis.py
    (attractive dimension only)."""
    attractive = np.average(np.asarray(odor_intensity_row).reshape(2, 2), axis=0,
                            weights=(1, 9))
    bias = -500 * (attractive[0] - attractive[1]) / attractive.mean()
    norm = np.tanh(bias ** 2) * np.sign(bias)
    control = np.ones((2,))
    control[int(norm > 0)] -= np.abs(norm) * 0.8
    return control


@pytest.mark.parametrize("inten", [[0.010, 0.011, 0.0100, 0.0102],
                                   [0.020, 0.019, 0.0200, 0.0199],
                                   [0.010, 0.010, 0.0100, 0.0100],
                                   [0.001, 0.003, 0.0011, 0.0010]])
def test_hand_rule_equals_published_example(inten):
    np.testing.assert_allclose(turn_to_drive(published_taxis_turn(inten)),
                               _example_control_signal(inten), atol=1e-12)


def test_hand_rule_turns_toward_stronger_side():
    assert published_taxis_turn([0.01, 0.01, 0.0102, 0.0100]) > 0     # left stronger
    assert published_taxis_turn([0.01, 0.01, 0.0100, 0.0102]) < 0
    assert published_taxis_turn([0, 0, 0, 0]) == 0.0                   # no odor


# ---------------------------------------------------------------------------
# 6. the loop itself (one very short step; FlyGym only)
# ---------------------------------------------------------------------------
def _toy_brain_with_loop_ids():
    """A tiny brain containing the real DM1 ORN and DN root IDs, wired so the
    LEFT DM1 ORNs excite the LEFT DNa02 strongly."""
    left, right = dm1_orn_ids()
    dns = np.array(list(DN_IDS.values()), np.int64)
    ids = np.concatenate([left, right, dns])
    dna02_l = ids.size - len(DN_IDS)                 # row of DNa02_L (first DN)
    pre = np.arange(left.size)
    return FastBrain.from_arrays(ids, pre, np.full(pre.size, dna02_l),
                                 np.full(pre.size, 40)), left


@pytest.mark.skipif(not LABELS_630.exists(), reason="630 label table not downloaded")
def test_brain_interface_silencing_dns_cuts_what_the_body_receives():
    if not HAS_FLYGYM:
        pytest.skip("FlyGym not installed here (use .venv-body)")
    from sim.body.loop import BrainInterface
    brain, left = _toy_brain_with_loop_ids()
    rates = np.full(68, 150.0)
    seen, fired = BrainInterface(brain, "none", seed=0).run_window(rates, 50.0)
    assert fired["DNa02_L"] > 20 and seen == fired
    seen, fired = BrainInterface(brain, "dns", seed=0).run_window(rates, 50.0)
    assert fired["DNa02_L"] > 20 and all(v == 0.0 for v in seen.values())
    seen, fired = BrainInterface(brain, "orns", seed=0).run_window(rates, 50.0)
    assert fired["DNa02_L"] == 0.0


@pytest.mark.skipif(not HAS_FLYGYM, reason="FlyGym not installed here (use .venv-body)")
@pytest.mark.skipif(not LABELS_630.exists(), reason="630 label table not downloaded")
def test_one_short_closed_loop_step():
    from sim.body.loop import TrialConfig, run_trial
    brain, _ = _toy_brain_with_loop_ids()
    cfg = TrialConfig("test", steering="brain", duration_s=0.02, window_ms=10.0,
                      source_xy_mm=(3.0, 3.0), spawn_heading_rad=0.0)
    out = run_trial(cfg, brain=brain)
    assert len(out["rows"]) == 2
    r0 = out["rows"][0]
    # Odor is to the front-left, so the left antenna smells more.
    assert r0["I_Lant"] > r0["I_Rant"] > 0
    assert r0["orn_rate_L"] > r0["orn_rate_R"] > 0
    # The toy brain's left ORNs drive the left DNa02 -> a LEFT turn command.
    assert r0["DNa02_L_hz"] > 0 and r0["turn"] > 0 and r0["drive_L"] < r0["drive_R"]
    assert out["final"]["t_s"] > r0["t_s"]

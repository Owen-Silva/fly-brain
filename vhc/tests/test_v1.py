"""Checks of the v1 parts: calibrated neuromorphic timing, static power, the 400-neuron default,
the living module's sourced settings and the DishBrain-style Pong workload."""
import numpy as np
import pytest

from vhc import neurocal
from vhc.cores import neuromorphic
from vhc.cores.living import CultureParams
from vhc.paths import MINIMAL
from vhc.prices import DISHBRAIN, NEURO_STATIC_W_CHIP, SANDIA_WALL_S_PER_SIM_S_DT01, table
from vhc.workloads import feeding, pong

SMALL = CultureParams(n=200, dish_um=700.0)


def test_calibration_fit_and_held_out_check():
    f = neurocal.fit()
    assert f["A_s_per_step"] > 0 and f["B_s_per_spike"] > 0
    assert f["v0_ratio_measured_over_model"]["dt0.1"] == pytest.approx(5.75, abs=0.05)   # v0's known gap
    # the fitted point is reproduced exactly; the held-out point within 30%
    s = neurocal.SUGAR
    c = {"steps": 10000, "neurons": s["neurons"], "spikes": s["spikes"], "syn_event": s["syn_event"],
         "input_event": s["input_event"]}
    t = neuromorphic.price(c, "clocked", n_cores=1440).time_s
    assert t == pytest.approx(SANDIA_WALL_S_PER_SIM_S_DT01.value, rel=1e-9)
    assert abs(f["check_sugar_dt1"]["error_pct"]) < 30
    # one term alone fails the held-out check badly (why v1 needs both)
    assert abs(f["one_term_A_only"]["check_sugar_dt1_error_pct"]) > 50
    assert abs(f["one_term_B_only"]["check_sugar_dt1_error_pct"]) > 50
    assert max(abs(x) for x in f["check_sweep_dt0.1_error_pct"]) < 50


def test_v1_prices_slower_and_adds_static_power():
    c = {"steps": 10000, "neurons": 400, "spikes": 3000, "syn_event": 20000, "input_event": 2000}
    v0 = neuromorphic.price(c, "clocked", version="v0")
    v1 = neuromorphic.price(c, "clocked")
    assert v1.time_s > v0.time_s
    assert v1.energy_J > v0.energy_J + 0.9 * NEURO_STATIC_W_CHIP["mid"].value * v1.time_s
    lo, hi = neuromorphic.price_range(c, "clocked")
    assert lo.energy_J < v1.energy_J < hi.energy_J and lo.time_s <= v1.time_s <= hi.time_s
    ev0, ev1 = neuromorphic.price(c, "event", version="v0"), neuromorphic.price(c, "event")
    assert ev1.time_s == ev0.time_s and ev1.energy_J > ev0.energy_J      # event mode: static only
    assert neuromorphic.chips_for(1440) == 12
    with pytest.raises(ValueError):
        neuromorphic.price(c, "clocked", version="v9")


def test_new_labels_and_sources():
    labels = {r[3] for r in table()}
    assert "DERIVED" in labels and labels <= {"PUBLISHED", "DERIVED", "FITTED", "MEASURED", "ASSUMED", "GUESSED"}
    lo, hi = NEURO_STATIC_W_CHIP["low"].value, NEURO_STATIC_W_CHIP["high"].value
    assert lo < NEURO_STATIC_W_CHIP["mid"].value < hi
    assert all(p.source for p in DISHBRAIN.values())


@pytest.mark.skipif(not (MINIMAL / "results" / "robust_circuit.json").exists(), reason="circuit file missing")
def test_default_circuit_is_the_robust_400():
    assert feeding.DEFAULT_CIRCUIT == "400"
    net, mn9, pos = feeding.load_circuit()
    assert net.n == 400
    r = feeding.run(n_trials=3, seed=0)
    assert r["bitter"]["mn9_hz"].max() == 0.0
    assert feeding.accuracy(r) >= 0.9


def test_pong_summary_and_never_missed():
    s = pong.summarise(np.array([0.0, 100.0, 400.0]), np.array([0, 2, 1]), 1200.0)
    assert s["rally_length"] == pytest.approx(1.0) and s["rally_length_t2"] == 1.0
    assert s["hit_rate"] == pytest.approx(3 / 6) and s["aces_pct"] == pytest.approx(100 / 3)
    n = pong.summarise(np.array([]), np.array([]), 60.0, open_hits=12)
    assert n["never_missed"] and n["hit_rate"] == 1.0 and n["rally_length"] == 12


def test_pong_controller_beats_random_paddle():
    ctl = pong.play("controller", minutes=5.0, seed=0)
    rnd = pong.play("random", minutes=60.0, seed=0)
    assert ctl["hit_rate"] > 0.9
    assert 0.4 < rnd["rally_length"] < 1.3                 # fitted near DishBrain's 0.80
    assert ctl["hit_rate"] > rnd["hit_rate"]


def test_pong_living_and_silicon_play_and_are_priced():
    liv = pong.play("living", 16, minutes=0.5, seed=0, params=SMALL)
    sil = pong.play("silicon", minutes=0.5, seed=0, params=SMALL)
    for r in (liv, sil):
        c = r["counts_per_game_s"]
        assert c["steps"] == pytest.approx(1000 / pong.DT_MS)
        assert c["spikes"] > 0 and c["syn_event"] > 0 and c["input_event"] > 0
        assert r["rallies"] + r["hits"] > 0
    assert liv["motor_channels"] > 0 and liv["electrode_mean_hz"] > 0
    p_liv, p_sil = pong.price_per_game_s(liv), pong.price_per_game_s(sil)
    p_ctl = pong.price_per_game_s(pong.play("controller", minutes=0.5, seed=0))
    assert p_liv.time_s == 1.0 and p_liv.energy_J == pytest.approx(25.0, rel=0.01)   # CL1 box, real time
    assert p_ctl.energy_J < p_sil.energy_J < p_liv.energy_J
    p_sil0 = pong.price_per_game_s(sil, version="v0")
    assert p_sil0.energy_J < p_sil.energy_J                 # v1 adds static power


def test_pong_learning_changes_weights_only_when_on():
    on = pong.play("silicon", minutes=0.5, seed=1, params=SMALL, eta=0.3)
    off = pong.play("silicon", minutes=0.5, seed=1, params=SMALL, eta=0.0)
    assert off["counts_per_game_s"]["syn_update"] == 0
    assert on["counts_per_game_s"]["syn_update"] > 0 or on["rallies"] + on["hits"] == 0

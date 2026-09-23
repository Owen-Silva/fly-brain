"""Tests for the 2026-09-23 additions to sim/realism.py (docs/phase7-conductance.md).

Plain English: the conductance upgrade got two new knobs, one factor for the
excitatory and one for the inhibitory synapse conductances. These tests check
that (1) leaving both at 1.0 changes nothing at all, (2) each knob changes only
its own kind of synapse, and (3) the new helper that builds the realistic
engine on top of a sign fix gives exactly the sign-fixed brain when every
upgrade is off.
"""

import gc

import numpy as np
import pytest

from sim.fast_engine import DEFAULT_PARAMS, FastBrain
from sim.realism import REALISM_DEFAULTS, RealisticBrain

SUGAR_630 = [
    720575940624963786, 720575940630233916, 720575940637568838, 720575940638202345,
    720575940617000768, 720575940630797113, 720575940632889389, 720575940621754367,
    720575940621502051, 720575940640649691, 720575940639332736, 720575940616885538,
    720575940639198653, 720575940620900446, 720575940617937543, 720575940632425919,
    720575940633143833, 720575940612670570, 720575940628853239, 720575940629176663,
    720575940611875570,
]


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
    return (np.array_equal(a.trial, b.trial) and np.array_equal(a.step, b.step)
            and np.array_equal(a.neuron, b.neuron))


def _two_inputs(c_exc, c_inh, realism=None):
    ids = np.arange(3, dtype=np.int64) + 10**17
    return RealisticBrain.from_arrays(ids, [0, 1], [2, 2], [c_exc, -c_inh], realism=realism)


def _psp_peak(brain, which, n_steps=400):
    ids = brain.root_ids
    res = brain.run_with_input_events([(np.array([10]), ids[which:which + 1])],
                                      excite=ids[:2], duration_ms=n_steps * 0.1,
                                      record_v=ids[2:3])
    d = res.voltages_V[int(ids[2])][0] * 1e3 - DEFAULT_PARAMS["v_0"]
    return d[np.argmax(abs(d))]


def test_new_defaults_are_neutral():
    assert REALISM_DEFAULTS["cond_exc_scale"] == 1.0
    assert REALISM_DEFAULTS["cond_inh_scale"] == 1.0


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_scales_at_one_change_nothing(seed):
    """Both new factors at 1.0 = the conductance model exactly as before
    (and with conductance off they are ignored)."""
    ids, pre, post, signed = _random_arrays(seed)
    brain = RealisticBrain.from_arrays(ids, pre, post, signed)
    kw = dict(excite=ids[:6], rate_hz=150, duration_ms=300, n_trials=3, seed=seed)
    brain.set_realism(conductance=True, cond_weight_scale=1.7)
    a = brain.run(**kw)
    brain.set_realism(cond_exc_scale=1.0, cond_inh_scale=1.0)
    b = brain.run(**kw)
    assert a.step.size > 50 and _same(a, b)
    # conductance off: new factors ignored, still the baseline engine exactly
    brain.set_realism(conductance=False, cond_exc_scale=3.0, cond_inh_scale=0.2)
    c = brain.run(**kw)
    base = FastBrain.from_arrays(ids, pre, post, signed).run(**kw)
    assert _same(base, c)


@pytest.mark.parametrize("seed", [0, 1])
def test_equal_scales_equal_the_global_scale(seed):
    """cond_exc_scale = cond_inh_scale = 2 gives the same spikes as the old
    single factor cond_weight_scale = 2 (multiplying by 2 is exact)."""
    ids, pre, post, signed = _random_arrays(seed)
    kw = dict(excite=ids[:6], rate_hz=150, duration_ms=300, n_trials=3, seed=seed)
    a = RealisticBrain.from_arrays(ids, pre, post, signed,
                                   realism=dict(conductance=True, cond_weight_scale=2.0)).run(**kw)
    b = RealisticBrain.from_arrays(ids, pre, post, signed,
                                   realism=dict(conductance=True, cond_exc_scale=2.0,
                                                cond_inh_scale=2.0)).run(**kw)
    assert a.step.size > 50 and _same(a, b)


def test_each_scale_touches_only_its_own_synapses():
    on = dict(conductance=True)
    e1, i1 = _psp_peak(_two_inputs(1, 1, on), 0), _psp_peak(_two_inputs(1, 1, on), 1)
    r = dict(on, cond_exc_scale=2.0)
    assert abs(_psp_peak(_two_inputs(1, 1, r), 0) / e1 - 2.0) < 0.01
    assert _psp_peak(_two_inputs(1, 1, r), 1) == i1
    r = dict(on, cond_inh_scale=0.5)
    assert abs(_psp_peak(_two_inputs(1, 1, r), 1) / i1 - 0.5) < 0.01
    assert _psp_peak(_two_inputs(1, 1, r), 0) == e1


def test_describe_reports_the_scales_only_when_used():
    b = _two_inputs(1, 1, dict(conductance=True))
    d = b.describe()
    assert "cond_exc_scale" not in d                  # old output unchanged
    b.set_realism(cond_exc_scale=1.5, cond_inh_scale=0.5)
    d2 = b.describe()
    assert d2["cond_exc_scale"] == 1.5 and d2["cond_inh_scale"] == 0.5
    assert abs(d2["g_exc_per_synapse"] / d["g_exc_per_synapse"] - 1.5) < 1e-12
    assert abs(d2["g_inh_per_synapse"] / d["g_inh_per_synapse"] - 0.5) < 1e-12


@pytest.mark.slow
def test_whole_brain_fixed_realistic_equals_sign_fixed_brain():
    """build_realistic_brain(fix) with every upgrade off gives exactly the
    spikes of sign_fixes.build_brain(fix). The two brains are built one after
    the other (never both in memory)."""
    from sim import sign_fixes as S
    from sim.realism import build_realistic_brain
    kw = dict(excite=SUGAR_630, rate_hz=100, duration_ms=300, n_trials=2, seed=0)
    fb = S.build_brain("al_ln_literature", n_threads=2)
    a = fb.run(**kw)
    n_conn = fb.n_connections
    del fb
    gc.collect()
    rb = build_realistic_brain("al_ln_literature", n_threads=2)
    assert rb.n_connections == n_conn
    b = rb.run(**kw)
    assert a.step.size > 1000 and _same(a, b)
    c = rb.run_baseline(**kw)
    assert _same(a, c)


def test_preset_is_what_the_experiments_validated():
    """The named preset equals the configuration validated in
    experiments/phase7_cond (config "sep") and gives the documented
    per-synapse conductances."""
    import json
    from pathlib import Path

    from sim.realism import CONDUCTANCE_SEPARATE_SCALES as P
    cfg = json.loads((Path(__file__).resolve().parents[1] / "experiments" / "phase7_cond"
                      / "results" / "configs.json").read_text())["sep"]
    for k, v in cfg.items():
        assert P[k] == v, k
    b = _two_inputs(1, 1, P)
    d = b.describe()
    assert abs(d["g_exc_per_synapse"] - 1.2 * 0.275 / 52) < 1e-12
    assert abs(d["g_inh_per_synapse"] - 0.87 * 0.275 / 8) < 1e-12


def test_sign_fixed_brain_reads_the_plain_snapshot_positions(tmp_path, monkeypatch):
    """Bug reported by the app lane (2026-09-23): a brain named after its sign
    fix ("630+fix") looked for a position file named after the fix, so
    fix + distance delays could not be built. position_snapshot points the
    loader at the plain snapshot's file."""
    import pandas as pd

    import sim.realism as R
    ids = np.arange(3, dtype=np.int64) + 10**17
    pd.DataFrame({"root_id": ids,
                  "anchor_x_nm": [0.0, 100_000.0, 0.0], "anchor_y_nm": [0.0, 0.0, 0.0],
                  "anchor_z_nm": [0.0, 0.0, 0.0], "soma_x_nm": [0.0, 100_000.0, 0.0],
                  "soma_y_nm": [0.0, 0.0, 0.0], "soma_z_nm": [0.0, 0.0, 0.0]}
                 ).to_parquet(tmp_path / "connectome_630_neurons.parquet")
    monkeypatch.setattr(R, "CACHE_DIR", tmp_path)
    def fresh(snapshot, position_snapshot=None):
        b = RealisticBrain.from_arrays(ids, [0, 1], [2, 2], [3, 3], realism=dict(delays=True))
        b.snapshot = snapshot
        if position_snapshot is not None:
            b.position_snapshot = position_snapshot
        return b

    # neuron 1 sits 100 um away: 1.8 ms + 100 um / 0.2 m/s = 2.3 ms = 23 steps
    for b in (fresh("630+al_ln_literature", "630"),   # what build_realistic_brain sets
              fresh("630+al_ln_literature"),          # any other "<snap>+<fix>" name
              fresh("630")):                          # plain snapshot: as before
        d = b.delay_steps_per_connection()
        assert d.max() == 23 and d.min() == 18
    with pytest.raises(FileNotFoundError):            # unknown snapshot: clear error
        fresh("783+al_ln_literature").delay_steps_per_connection()


@pytest.mark.slow
def test_whole_brain_sign_fix_with_delays_builds():
    from sim.realism import build_realistic_brain
    rb = build_realistic_brain("al_ln_literature", n_threads=2,
                               realism=dict(delays=True))
    d = rb.delay_steps_per_connection()
    assert d.size == rb.n_connections and d.min() >= 18
    assert rb.distance_notes["anchor_out_of_brain_dropped"] == 2
    r = rb.run(excite=SUGAR_630, rate_hz=100, duration_ms=100, n_trials=1, seed=0)
    assert r.step.size > 0

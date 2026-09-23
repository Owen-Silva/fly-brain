"""Phase 1 checkpoint: the toy spiking network behaves like neurons should.

Plain English: we run the same 100-neuron network under different inputs and
count spikes. Every run uses a fixed random seed, so the answer never changes
from one test run to the next.
"""
import ast
from pathlib import Path
from textwrap import dedent

import pytest
from brian2 import Hz, mV, ms

from sim.toy_network import (EQUATIONS, REFERENCE_PARAMS, THRESHOLD,
                              run_toy_network)

DURATION = 300 * ms
SEED = 7
REFERENCE_MODEL = Path(__file__).resolve().parents[1] / "data" / "reference" / "model.py"


@pytest.fixture(scope="module")
def baseline():
    """Background input only: the network fires at a moderate rate."""
    return run_toy_network("none", background=True, duration=DURATION, seed=SEED)


def test_excitatory_input_increases_firing(baseline):
    driven = run_toy_network("excitatory", background=True,
                             duration=DURATION, seed=SEED)
    assert baseline.n_spikes > 0
    # Clearly more, not just a hair more: at least 1.5x the baseline.
    assert driven.n_spikes > 1.5 * baseline.n_spikes


def test_inhibitory_input_decreases_firing(baseline):
    assert baseline.n_spikes > 0, "baseline must fire so a drop can be seen"
    inhibited = run_toy_network("inhibitory", background=True,
                                duration=DURATION, seed=SEED)
    # Clearly less: at most half the baseline.
    assert inhibited.n_spikes < 0.5 * baseline.n_spikes


def test_zero_input_gives_no_spikes():
    silent = run_toy_network("none", background=False,
                             duration=DURATION, seed=SEED)
    assert silent.n_spikes == 0
    # With nothing coming in, the voltage sits exactly at rest the whole time.
    assert abs(silent.voltage_mV - float(REFERENCE_PARAMS["v_0"] / mV)).max() < 1e-9


def test_same_seed_same_result():
    a = run_toy_network("excitatory", background=True, duration=100 * ms, seed=3)
    b = run_toy_network("excitatory", background=True, duration=100 * ms, seed=3)
    assert a.n_spikes == b.n_spikes > 0
    assert (a.spike_neurons == b.spike_neurons).all()


@pytest.mark.skipif(not REFERENCE_MODEL.exists(),
                    reason="reference repo not cloned into data/reference")
def test_neuron_numbers_match_reference_code():
    """Read the reference paper's parameter table (without running its code)
    and check every neuron number we copied is identical."""
    tree = ast.parse(REFERENCE_MODEL.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.Assign)
                and getattr(n.targets[0], "id", None) == "default_params")
    ref = eval(compile(ast.Expression(node.value), str(REFERENCE_MODEL), "eval"),
               {"mV": mV, "ms": ms, "Hz": Hz, "dedent": dedent})
    for name, value in REFERENCE_PARAMS.items():
        assert ref[name] == value, name
    # Same equations and firing rule too (ignoring spacing).
    assert " ".join(ref["eqs"].split()) == " ".join(EQUATIONS.split())
    assert ref["eq_th"] == THRESHOLD

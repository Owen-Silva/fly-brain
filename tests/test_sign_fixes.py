"""Tests for sim/sign_fixes.py (Phase 7 upgrade 5, neurotransmitter signs).

Plain English: (1) the "none" fix must give exactly the paper's model, spike
for spike; (2) each fix must change exactly the connections it says it
changes, and nothing else. Only one whole brain is kept in memory at a time.
"""

import gc

import numpy as np
import pytest

from sim import sign_fixes as S
from sim.fast_engine import FastBrain


@pytest.fixture(scope="module")
def data():
    rid, pre, post, signed = S.load_reference_arrays("630")
    lab = S.neuron_table(rid)
    return rid, pre, post, signed, lab


def test_known_nt_parser():
    assert S.known_nt_sign("acetylcholine") == (1, "fast")
    assert S.known_nt_sign("acetylcholine; gaba-negative") == (1, "fast")
    assert S.known_nt_sign("glutamate, gaba; glutamate") == (-1, "fast")
    assert S.known_nt_sign("gaba, nitric oxide") == (-1, "fast")
    assert S.known_nt_sign("acetylcholine, glutamate") == (0, "mixed_fast")
    assert S.known_nt_sign("dopamine; dopamine") == (0, "monoamine")
    assert S.known_nt_sign("histamine") == (0, "histamine")
    assert S.known_nt_sign("histamine; acetylcholine, histamine") == (0, "histamine")
    assert S.known_nt_sign("allatostatin-a") == (0, "other")
    assert S.known_nt_sign(None) == (0, "none")
    assert S.known_nt_sign("gaba-negative") == (0, "none")


def test_default_fix_is_the_recommended_fix():
    """Since 2026-09-23 the builders default to the recommended fix; the paper's
    model is fix="none" (FastBrain itself stays the published-weights loader)."""
    import inspect
    from sim.realism import build_realistic_brain
    assert S.RECOMMENDED_FIX == "al_ln_literature"
    for f in (S.build_brain, build_realistic_brain):
        assert inspect.signature(f).parameters["fix"].default == S.RECOMMENDED_FIX


def test_eln_set(data):
    rid, pre, post, signed, lab = data
    eln = S.eln_mask(lab)
    assert eln.sum() == 44
    types = set(lab.hemibrain_type[eln]) | set(lab.cell_type[eln])
    assert {"lLN1_b,lLN1_c", "lLN2T_b", "lLN2T_c", "lLN2X03"} <= types
    sign = S.neuron_signs(len(rid), pre, signed)
    assert (sign[eln] == 1).all()          # excitatory in the reference already
    assert S.ln53_mask(lab).sum() == 53


def test_none_changes_nothing(data):
    rid, pre, post, signed, lab = data
    p2, q2, s2, rep = S.apply_fix("none", rid, pre, post, signed, lab)
    assert p2 is pre and q2 is post and s2 is signed
    assert rep.removed_connections == 0 and not rep.flipped_neurons


def test_eln_electrical_removes_exactly_the_intended_connections(data):
    rid, pre, post, signed, lab = data
    p2, q2, s2, rep = S.apply_fix("eln_electrical", rid, pre, post, signed, lab)
    eln = S.eln_mask(lab)
    sign = S.neuron_signs(len(rid), pre, signed)
    intended = eln[pre] & (sign[post] != -1)
    assert rep.removed_connections == intended.sum() == pre.size - p2.size
    assert rep.removed_connections == 18_248          # counted once, pinned here
    assert rep.removed_synapses == int(np.abs(signed[intended]).sum())
    # what is left is the original list minus exactly those rows, same order
    keep = ~intended
    assert np.array_equal(p2, pre[keep]) and np.array_equal(q2, post[keep])
    assert np.array_equal(s2, signed[keep])
    # eLN connections onto inhibitory neurons survive, unchanged and positive
    kept_eln = eln[p2]
    assert kept_eln.sum() == (eln[pre] & (sign[post] == -1)).sum() > 0
    assert (s2[kept_eln] > 0).all() and (sign[q2[kept_eln]] == -1).all()
    assert not rep.flipped_neurons


def test_al_ln_literature_changes_exactly_the_intended_connections(data):
    rid, pre, post, signed, lab = data
    p2, q2, s2, rep = S.apply_fix("al_ln_literature", rid, pre, post, signed, lab)
    sign = S.neuron_signs(len(rid), pre, signed)
    al = lab.cell_class.to_numpy() == "ALLN"
    ks = lab.known_sign.to_numpy()
    to_inh = al & (sign == 1) & (ks == -1)
    assert to_inh.sum() == 13 == rep.to_inhibitory
    assert set(rep.flipped_neurons) == set(rid[to_inh].tolist())
    new_sign = np.where(to_inh, -1, sign)
    exc_ln = al & (new_sign == 1)
    assert exc_ln.sum() == 137 and (exc_ln | S.eln_mask(lab) == exc_ln).all()  # eLNs included
    drop = exc_ln[pre] & (new_sign[post] != -1)
    assert rep.removed_connections == drop.sum() == pre.size - p2.size == 51_539
    keep = ~drop
    assert np.array_equal(p2, pre[keep]) and np.array_equal(q2, post[keep])
    flipped_rows = to_inh[pre[keep]]
    assert rep.flipped_connections == flipped_rows.sum() > 0
    assert np.array_equal(s2[flipped_rows], -np.abs(signed[keep][flipped_rows]))
    assert np.array_equal(s2[~flipped_rows], signed[keep][~flipped_rows])   # nothing else
    assert (sign[q2[exc_ln[p2]]] == -1).all() or (new_sign[q2[exc_ln[p2]]] == -1).all()


@pytest.mark.parametrize("fix", ["known_nt", "ln53_inhibitory"])
def test_sign_flips_touch_only_the_flipped_neurons(data, fix):
    rid, pre, post, signed, lab = data
    p2, q2, s2, rep = S.apply_fix(fix, rid, pre, post, signed, lab)
    assert p2.size == pre.size and np.array_equal(p2, pre) and np.array_equal(q2, post)
    flipped = np.isin(rid, np.array(rep.flipped_neurons, dtype=np.int64))
    changed = s2 != signed
    assert np.array_equal(changed, flipped[pre])           # all and only their rows
    assert np.array_equal(s2[changed], -signed[changed])   # same size, opposite sign
    assert rep.flipped_connections == changed.sum()
    sign = S.neuron_signs(len(rid), pre, signed)
    if fix == "known_nt":
        ks = lab.known_sign.to_numpy()
        assert (ks[flipped] != 0).all() and (ks[flipped] != sign[flipped]).all()
        expected = (ks != 0) & (sign != 0) & (ks != sign)
        assert flipped.sum() == expected.sum() == 1334
        assert rep.to_inhibitory + rep.to_excitatory == 1334
    else:
        assert flipped.sum() == 53 and (sign[flipped] == 1).all()


def _paper_list(name):
    """Read an ID list from sim/shiu_model.py as text (importing it loads Brian2)."""
    import ast
    tree = ast.parse((S.ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and getattr(node.targets[0], "id", None) == name:
            return ast.literal_eval(node.value)
    raise KeyError(name)


def _spikes(brain):
    """Sugar at 200 Hz (2 trials) plus a 10-ORN DM1 volley, which ignites the
    paper's model (a large, demanding comparison)."""
    r1 = brain.run(excite=_paper_list("SUGAR_R_630"), rate_hz=200, duration_ms=300.0,
                   n_trials=2, seed=5)
    lab = S.neuron_table(brain.root_ids)
    dm1 = lab.root_id.to_numpy()[lab.hemibrain_type.to_numpy() == "ORN_DM1"][:10]
    r2 = brain.run_with_input_events([(np.full(dm1.size, 50), dm1)], excite=dm1,
                                     duration_ms=150.0)
    assert r2.step.size > 10_000          # it really did ignite
    return (r1.trial.copy(), r1.step.copy(), r1.neuron.copy(), r2.step.copy(),
            r2.neuron.copy())


def test_none_reproduces_baseline_spike_for_spike():
    b = FastBrain("630")
    ref = _spikes(b)
    assert ref[1].size > 0
    del b
    gc.collect()
    b2 = S.build_brain("none")
    got = _spikes(b2)
    assert b2.n_connections == 14_687_178
    del b2
    gc.collect()
    for a, c in zip(ref, got):
        assert np.array_equal(a, c)

"""Tests for the neuromodulator fixes in sim/sign_fixes.py (Phase 7 item 5).

Plain English: (1) the old fixes and the recommended default must be exactly
as before; (2) each new fix must be "al_ln_literature" with exactly the
outgoing connections of the chosen dopamine (and serotonin) cells taken out,
and nothing else changed; (3) the cells it picks must follow the stated rules
(for example Kenyon cells, which the literature says are cholinergic, are
never touched; SMP384, which the literature calls serotonergic, is touched
only by the fixes that include serotonin; the literature-only fix never touches
cells known only from the machine prediction). Only one whole brain in memory
at a time.
"""

import gc

import numpy as np
import pytest

from sim import sign_fixes as S

NEW = list(S.NEUROMOD_FIXES)


def _mask(lab, sign0, fix):
    return S.modulatory_mask(lab, sign0, S.NEUROMOD_FIXES[fix],
                             S.NEUROMOD_EVIDENCE.get(fix, ("literature", "prediction")))


@pytest.fixture(scope="module")
def data():
    rid, pre, post, signed = S.load_reference_arrays("630")
    lab = S.neuron_table(rid)
    p0, q0, s0, rep0 = S.apply_fix("al_ln_literature", rid, pre, post, signed, lab)
    sign0 = S.neuron_signs(len(rid), p0, s0)
    return rid, pre, post, signed, lab, (p0, q0, s0, rep0), sign0


def _rows_of(lab, name):
    hb = lab.hemibrain_type.to_numpy()
    ct = lab.cell_type.to_numpy()
    return np.flatnonzero((hb == name) | (ct == name))


def test_old_fixes_and_default_unchanged(data):
    rid, pre, post, signed, lab, (p0, q0, s0, rep0), _ = data
    assert S.FIXES[:5] == ("none", "eln_electrical", "al_ln_literature", "known_nt",
                           "ln53_inhibitory")
    assert S.RECOMMENDED_FIX == "al_ln_literature"
    # al_ln_literature's own numbers, as recorded in experiments/phase7_signs (2026-09-23)
    assert rep0.n_connections_after == 14_635_639
    assert rep0.removed_connections == 51_539 and rep0.removed_synapses == 351_448
    assert len(rep0.flipped_neurons) == 13 and rep0.flipped_connections == 10_455
    # old fixes refuse the new option instead of silently ignoring it
    for fix in S.FIXES[:5]:
        with pytest.raises(ValueError):
            S.apply_fix(fix, rid, pre, post, signed, lab, keep_outputs=[int(rid[0])])


@pytest.mark.parametrize("fix", NEW)
def test_new_fix_removes_exactly_the_modulatory_outputs(data, fix):
    rid, pre, post, signed, lab, (p0, q0, s0, rep0), sign0 = data
    p1, q1, s1, rep = S.apply_fix(fix, rid, pre, post, signed, lab)
    mod = _mask(lab, sign0, fix)
    keep = ~mod[p0]
    # the result is al_ln_literature minus exactly these rows, order and signs kept
    assert np.array_equal(p1, p0[keep])
    assert np.array_equal(q1, q0[keep])
    assert np.array_equal(s1, s0[keep])
    assert not np.isin(p1, np.flatnonzero(mod)).any()
    # report counts match the arrays
    assert rep.n_connections_after == p1.size
    assert rep.details["modulatory_connections_removed"] == int((~keep).sum())
    assert rep.details["modulatory_synapses_removed"] == int(np.abs(s0[~keep]).sum())
    assert rep.removed_connections == rep0.removed_connections + int((~keep).sum())
    assert rep.flipped_neurons == rep0.flipped_neurons
    assert rep.details["modulatory_neurons"] == int(mod.sum()) == len(rep.target_neurons)
    by = rep.details["by_amine_and_evidence"]
    assert sum(v["neurons"] for v in by.values()) == int(mod.sum())
    assert sum(v["connections"] for v in by.values()) == int((~keep).sum())
    # the rules: excitatory in the model, a listed monoamine, no ALLN, no Kenyon cell,
    # no CSD, no sensory cell known only from the prediction
    amine, evidence = S.monoamine_of(lab)
    assert (sign0[mod] == 1).all()
    assert np.isin(amine[mod], S.NEUROMOD_FIXES[fix]).all()
    cc = lab.cell_class.to_numpy()
    assert not (mod & (cc == "ALLN")).any()
    assert not (mod & (cc == "Kenyon_Cell")).any()
    assert not mod[_rows_of(lab, "CSD")].any()
    sc = lab.super_class.to_numpy()
    assert not (mod & (sc == "sensory") & (evidence == "prediction")).any()
    if fix in S.NEUROMOD_EVIDENCE:
        assert np.isin(evidence[mod], S.NEUROMOD_EVIDENCE[fix]).all()
    # literature naming a fast transmitter always wins
    assert not (mod & np.isin(lab.known_kind.to_numpy(), ["fast", "mixed_fast", "histamine"])).any()
    del p1, q1, s1
    gc.collect()


def test_which_cells_each_fix_picks(data):
    rid, pre, post, signed, lab, _, sign0 = data
    da = _mask(lab, sign0, "al_ln_literature+da_modulatory")
    d5 = _mask(lab, sign0, "al_ln_literature+da_5ht_modulatory")
    lit = _mask(lab, sign0, "al_ln_literature+da_5ht_literature")
    assert not (da & ~d5).any()                       # dopamine set is inside the wider set
    assert not (lit & ~d5).any()                      # literature set is inside it too
    for name in ("PPL101", "PPL107", "PAM01"):        # literature dopamine neurons
        r = _rows_of(lab, name)
        assert r.size and da[r].all() and d5[r].all() and lit[r].all(), name
    for name in ("SMP384", "SMP504"):                 # literature serotonin (Chiang et al. 2011)
        r = _rows_of(lab, name)
        assert r.size == 2 and not da[r].any() and d5[r].all() and lit[r].all(), name
    for name in ("CB0573", "CB0461", "CB0088"):       # SEZ cells: dopamine by prediction only
        r = _rows_of(lab, name)
        assert r.size and da[r].all() and not lit[r].any(), name
    for name in ("DPM", "CSD", "OA-VPM3", "OA-VPM4", "APL", "CRE069"):
        r = _rows_of(lab, name)
        assert r.size and not d5[r].any(), name
    assert da.sum() == 494 and d5.sum() == 997 and lit.sum() == 445   # 2026-09-23 (docs)


def test_keep_outputs_leaves_those_rows(data):
    rid, pre, post, signed, lab, (p0, q0, s0, _), sign0 = data
    fix = "al_ln_literature+da_modulatory"
    ppl = _rows_of(lab, "PPL101")
    p1, q1, s1, rep = S.apply_fix(fix, rid, pre, post, signed, lab,
                                  keep_outputs=rid[ppl].tolist())
    mod = _mask(lab, sign0, fix)
    mod[ppl] = False
    keep = ~mod[p0]
    assert np.array_equal(p1, p0[keep]) and np.array_equal(s1, s0[keep])
    assert rep.details["kept_outputs"] == 2
    assert np.isin(p1, ppl).sum() == np.isin(p0, ppl).sum() > 0
    del p1, q1, s1
    gc.collect()


def test_build_brain_with_new_fix():
    fix = "al_ln_literature+da_5ht_modulatory"
    b, rep = S.build_brain(fix, return_report=True)
    assert b.n_connections == rep.n_connections_after == 14_430_027
    assert b.sign_fix == fix and b.snapshot == f"630+{fix}"
    del b
    gc.collect()

"""Diagnostic: which antennal-lobe change stops the self-sustaining state under
STRONG smell input (all 68 DM1 smell neurons at 150 Hz)?

Plain English: the first timing run showed that the literature eLN fix (44
eLNs keep their sign, lose their chemical synapses onto non-inhibitory
neurons) stops weak triggers but NOT strong DM1 input: after the input stops
at 300 ms, ~3,700 neurons keep firing. This script tries a few variants, each
changed in memory on one brain and restored afterwards (checked), and
measures: does firing continue after the input stops? how many Kenyon cells
fire while the input is on? Ir94e 200 Hz runaway count over 30 trials.
Output: results/diag_variants.csv. A diagnostic, not the validation itself.
"""

from contextlib import contextmanager

import numpy as np
import pandas as pd

import common as C
from sim import sign_fixes as S

rid, pre0, post0, signed0 = S.load_reference_arrays()
lab = S.neuron_table(rid)
sets = C.input_sets(lab)
sign = S.neuron_signs(len(rid), pre0, signed0)
del pre0, post0, signed0
brain = S.build_brain("none", n_threads=2, lab=lab)
rd = C.Readout(brain, lab)
pre = np.repeat(np.arange(brain.n_neurons), np.diff(brain._indptr))
post = brain._post
al = lab.cell_class.to_numpy() == "ALLN"
eln = S.eln_mask(lab)
l53 = S.ln53_mask(lab)
ks = lab.known_sign.to_numpy()
exc_ln = al & (sign == 1)
known_inh_ln = al & (ks == -1) & (sign == 1)
other19 = l53 & ~eln


@contextmanager
def variant(electrical=None, to_inh=None):
    """electrical: mask of presynaptic neurons whose chemical synapses onto
    non-inhibitory targets are zeroed; to_inh: mask of neurons made inhibitory."""
    saved = brain._count.copy()
    try:
        cnt = brain._count
        if to_inh is not None:
            m = to_inh[pre]
            cnt[m] = -np.abs(cnt[m])
        if electrical is not None:
            new_sign = np.where(to_inh, -1, sign) if to_inh is not None else sign
            m = electrical[pre] & (new_sign[post] != -1)
            cnt[m] = 0
        yield
    finally:
        brain._count[:] = saved


VARIANTS = {
    "none": {},
    "V1 eLN44 electrical (= eln_electrical)": dict(electrical=eln),
    "V2 V1 + 13 known-GABA/Glu LNs inhibitory": dict(electrical=eln, to_inh=known_inh_ln),
    "V3 V1 + other 19 of the 53 inhibitory": dict(electrical=eln, to_inh=other19),
    "V4 all 150 excitatory LNs electrical": dict(electrical=exc_ln),
    "V5 V4 but 13 known-GABA/Glu LNs inhibitory": dict(electrical=exc_ln & ~known_inh_ln,
                                                     to_inh=known_inh_ln),
    "V6 ln53 inhibitory (Phase 5 LN-fix)": dict(to_inh=l53),
}


def cut_input_trial(excite, seed, cut_ms, dur_ms=1000.0):
    p = brain._params_for(None)
    ids = np.array(list(excite), np.int64)
    exc_idx = brain.index_of(ids)
    n_steps = int(dur_ms / p["dt"])
    prob = np.array(list(excite.values())) * p["dt"] * 1e-3
    rng = np.random.default_rng(np.random.SeedSequence(seed).spawn(1)[0])
    ev_ptr, ev_n = brain._poisson_events(rng, exc_idx, prob, n_steps)
    steps = np.repeat(np.arange(n_steps), np.diff(ev_ptr))
    keep = steps < int(cut_ms / p["dt"])
    ev = brain._pack_events(steps[keep], ev_n[keep].astype(np.int64), n_steps)
    return brain._run_events([ev], exc_idx, (), n_steps, p, ())


rows = []
dm1 = C.excite_for("dm1_both_150Hz", sets)
ir = C.excite_for("ir94e_200Hz", sets)
print({k: int(v.sum()) for k, v in dict(eln=eln, exc_ln=exc_ln, known_inh_ln=known_inh_ln,
                                        other19=other19).items()}, flush=True)
for name, kw in VARIANTS.items():
    with variant(**kw):
        for seed in (0, 1):
            r = cut_input_trial(dm1, seed, 300)
            st, nu = r.step, r.neuron
            on = np.unique(nu[st < 3000])
            late = nu[st >= 4000]
            rows.append(dict(variant=name, test=f"DM1 150 Hz, input off at 300 ms, seed {seed}",
                             spikes_input_on=int((st < 3000).sum()),
                             kc_active_input_on=int(rd.is_kc[on].sum()),
                             neurons_firing_after_400ms=int(np.unique(late).size),
                             spikes_after_400ms=int(late.size)))
            print(rows[-1], flush=True)
        res = C.run_chunk(brain, ir, 0, 0, 30)
        tr, _ = C.trial_rows(res, rd, {})
        rows.append(dict(variant=name, test="Ir94e 200 Hz, 30 trials (seed 0)",
                         runaway_trials=int(sum(t["runaway"] for t in tr))))
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(C.RESULTS / "diag_variants.csv", index=False)
# restore check
chk = S.load_reference_arrays()[3]
order = np.argsort(S.load_reference_arrays()[1], kind="stable")
assert np.array_equal(brain._count, chk[order].astype(np.int32)), "restore failed"
print("restore ok; finished", flush=True)

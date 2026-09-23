"""Step 3e: the eLNs are the way IN; what keeps the state going?

Plain English
-------------
Step 3c showed: silencing the 38 excitatory local neurons (eLNs) stops the
natural triggers (smell neurons, Ir94e input), but if we FORCE the 20
first-firing neurons to fire once, the brain still ignites without the eLNs.
So the eLNs are the entry point, and the self-sustaining loop is wider.
Here we force a strong kick (the 20 first-firing neurons, or all antennal-lobe
projection neurons, fire once) while silencing bigger groups, to find which
groups the self-sustaining state cannot do without:
  * all 150 antennal-lobe local neurons the model treats as excitatory
  * all 424 antennal-lobe local neurons
  * all antennal-lobe projection neurons (PNs)
  * all Kenyon cells (mushroom body)
  * lateral-horn local neurons
We also try one "what if": 40 antennal-lobe local neurons are predicted to
release serotonin, but the only serotonin neurons known in the antennal lobe
are the two CSD neurons, so most of these predictions must be wrong. What if
the ones NOT known to be cholinergic were inhibitory (like most local
neurons)? (A diagnostic, not a model change.)

Output: results/sustain_tests.csv
"""
import importlib
import sys
from contextlib import contextmanager
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
R = common.RESULTS
ids = common.paper_ids()
lab = common.labels(brain)
rid, cc, ht, nt = (lab.root_id.to_numpy(), lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy(),
                   lab.top_nt.to_numpy())
n = brain.n_neurons
has = np.diff(brain._indptr) > 0
sign = np.zeros(n, int)
sign[has] = np.sign(brain._count[brain._indptr[:-1][has]])
aln = cc == "ALLN"
eln = aln & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
mono = aln & np.isin(nt, ["serotonin", "dopamine", "octopamine"]) & ~eln
first20 = pd.read_csv(R / "onset_ranking.csv").root_id.head(20).to_numpy(np.int64)
pns = rid[cc == "ALPN"]
dm1 = rid[ht == "ORN_DM1"][:10]
print(f"monoamine-predicted AL local neurons outside eLN types: {mono.sum()}", flush=True)
rows = []


def volley(trig, silence=()):
    trig = np.setdiff1d(np.asarray(trig, np.int64), np.asarray(silence, np.int64))
    return brain.run_with_input_events([(np.full(trig.size, 50), trig)], excite=trig,
                                       duration_ms=1000.0, silence=silence), trig.size


def add(test, group, res_rows, n_trig=None):
    d = pd.DataFrame(res_rows)
    rows.append(dict(test=test, group=group, n=len(d), runaway=int(d.runaway.sum()),
                     trigger_size=n_trig, median_spikes=int(d.total_spikes.median()),
                     neurons_last_100ms=int(d.distinct_last_100ms.median())))
    pd.DataFrame(rows).to_csv(R / "sustain_tests.csv", index=False)
    print(rows[-1], flush=True)


groups = {
    "150 model-excitatory AL local neurons": rid[aln & (sign > 0)],
    "all 424 AL local neurons": rid[aln],
    f"all {pns.size} AL projection neurons": pns,
    "all Kenyon cells": rid[cc == "Kenyon_Cell"],
    "all lateral-horn local neurons": rid[cc == "LHLN"],
}
for g, sil in groups.items():
    for name, trig in (("20 first-firing neurons fire once", first20),
                       ("all AL projection neurons fire once", pns)):
        if name.startswith("all AL projection") and "projection" in g:
            continue
        res, k = volley(trig, sil)
        add(name, g, [common.trial_summary(res, brain, ids)[0]], k)


@contextmanager
def mono_inhibitory():
    rows_ = np.flatnonzero(mono)
    saved = []
    for i in rows_:
        a, b = brain._indptr[i], brain._indptr[i + 1]
        saved.append(brain._count[a:b].copy())
        brain._count[a:b] = -np.abs(brain._count[a:b])
    try:
        yield
    finally:
        for i, s in zip(rows_, saved):
            brain._count[brain._indptr[i]:brain._indptr[i + 1]] = s


with mono_inhibitory():
    g = f"what-if: {mono.sum()} serotonin/dopamine-predicted AL local neurons made inhibitory"
    for name, trig in (("olfactory trigger: 10 DM1 ORNs fire once", dm1),
                       ("20 first-firing neurons fire once", first20),
                       ("all AL projection neurons fire once", pns)):
        res, k = volley(trig)
        add(name, g, [common.trial_summary(res, brain, ids)[0]], k)
    ir = {i: 200.0 for i in ids["IR94E"]}
    add("Ir94e 200 Hz, 60 trials (seeds 0-1)", g,
        [common.trial_summary(common.run_one(brain, ir, s, k, 1000.0), brain, ids)[0]
         for s in (0, 1) for k in range(30)])
    sug = {i: 100.0 for i in ids["SUGAR"]}
    rr = [common.trial_summary(common.run_one(brain, sug, 0, k, 1000.0), brain, ids)[0] for k in range(30)]
    add("sugar 100 Hz, 30 trials (MN9 check)", g, rr)
    print("  MN9:", round(pd.DataFrame(rr).mn9_hz.mean(), 2), flush=True)
# confirm the in-place change was undone
res, k = volley(dm1)
add("olfactory trigger after restoring the model (must ignite)", "intact", [common.trial_summary(res, brain, ids)[0]], k)
print("finished", flush=True)

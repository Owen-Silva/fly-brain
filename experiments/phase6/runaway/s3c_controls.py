"""Step 3c: controls for the lesion tests.

Plain English
-------------
Step 3b's "paired" test (re-run a trial that ran away, with a group silenced)
turned out to be too sensitive: silencing 38 RANDOM excitatory neurons also
stopped 15 of 16 runaways. That is because a runaway is a rare tipping event
(4-13% of trials): change anything that fires early and the trial follows a
different path, and most paths do not tip. So the fair tests are:
  * rates over many trials (60 Ir94e-200 trials), and
  * triggers that ignite the intact model EVERY time (10 DM1 smell neurons
    firing once; the 20 first-firing neurons firing once),
each with the eLNs silenced versus size-matched random control groups
silenced. If the eLNs are the loop, only the eLN lesion should stop the
deterministic triggers.

Output: results/lesion_controls.csv
"""
import importlib
import sys
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
rid = lab.root_id.to_numpy()
cc, ht = lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy()
aln = cc == "ALLN"
eln = aln & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
l2t = aln & np.isin(ht, ["lLN2T_a", "lLN2T_b", "lLN2T_c"])
core = pd.read_csv(R / "core_neurons.csv")
cand = core[(core.sign > 0) & (~core.cell_class.isin(["ALLN", "ALPN", "olfactory"]))].root_id.to_numpy(np.int64)
first20 = pd.read_csv(R / "onset_ranking.csv").root_id.head(20).to_numpy(np.int64)
dm1 = rid[ht == "ORN_DM1"][:10]
ir = {i: 200.0 for i in ids["IR94E"]}
groups = {"intact": np.zeros(0, np.int64),
          f"{eln.sum()} eLNs (lLN1_b/c + lLN2T_a-c)": rid[eln],
          f"{l2t.sum()} lLN2T_a-c only": rid[l2t]}
for k in range(3):
    groups[f"control {k + 1}: {eln.sum()} random excitatory runaway neurons outside AL"] = \
        np.random.default_rng(100 + k).choice(cand, size=int(eln.sum()), replace=False)
rows = []


def add(test, group, res_rows):
    d = pd.DataFrame(res_rows)
    rows.append(dict(test=test, group=group, n=len(d), runaway=int(d.runaway.sum()),
                     neurons_firing_last_100ms=d.distinct_last_100ms.tolist() if len(d) == 1 else "",
                     median_spikes=int(d.total_spikes.median())))
    pd.DataFrame(rows).to_csv(R / "lesion_controls.csv", index=False)
    print({k: rows[-1][k] for k in ("test", "group", "n", "runaway")}, flush=True)


def volley(ids_, silence):
    ids_ = np.asarray(ids_, np.int64)
    return brain.run_with_input_events([(np.full(ids_.size, 50), ids_)], excite=ids_,
                                       duration_ms=1000.0, silence=silence)


for g, sil in groups.items():
    for name, trig in (("olfactory trigger: 10 DM1 ORNs fire once", dm1),
                       ("20 first-firing neurons fire once", first20)):
        trig = np.setdiff1d(trig, sil)            # a silenced neuron cannot be the trigger
        add(name, g, [common.trial_summary(volley(trig, sil), brain, ids)[0]])
for g, sil in groups.items():
    if g == "intact":
        continue                                   # intact rate is known from step 1a (9/60, seeds 0-1)
    rr = [common.trial_summary(common.run_one(brain, ir, s, k, 1000.0, silence=sil), brain, ids)[0]
          for s in (0, 1) for k in range(30)]
    add("Ir94e 200 Hz, 60 trials (seeds 0-1)", g, rr)
print("finished", flush=True)

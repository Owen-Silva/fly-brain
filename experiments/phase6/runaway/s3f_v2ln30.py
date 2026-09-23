"""Step 3f: the hub of the strongest loops, v2LN30, has an uncertain transmitter.

Plain English
-------------
The two biggest "one spike is enough" loops (step 3d) both run through one
antennal-lobe local neuron per side, type v2LN30: each lLN2T_c neuron sends
it 400-520 synapses, and it sends 190-390 synapses to projection neurons,
which feed back. Its transmitter is a coin toss: the automatic prediction
says serotonin (right, confidence 0.29) or glutamate (left, 0.28), and no
measured value is on record. The model counts it as excitatory. What if it is
inhibitory (as glutamatergic local neurons are in the model)? We flip the
sign of just these 2 neurons (a diagnostic, restored afterwards) and repeat
the trigger tests.

Output: results/v2ln30_flip.csv
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
rid, ht = lab.root_id.to_numpy(), lab.hemibrain_type.to_numpy()
v2 = np.flatnonzero(ht == "v2LN30")
print("v2LN30 rows:", rid[v2].tolist(), flush=True)
dm1 = rid[ht == "ORN_DM1"][:10]
first20 = pd.read_csv(R / "onset_ranking.csv").root_id.head(20).to_numpy(np.int64)
mem = pd.read_csv(R / "strong_loop_members.csv")
loop7 = mem[mem.loop_group == mem.loop_group.value_counts().idxmax()].root_id.to_numpy(np.int64)
ir = {i: 200.0 for i in ids["IR94E"]}
sug = {i: 100.0 for i in ids["SUGAR"]}
rows = []


def volley(trig):
    trig = np.asarray(trig, np.int64)
    return brain.run_with_input_events([(np.full(trig.size, 50), trig)], excite=trig, duration_ms=1000.0)


def add(test, variant, rr):
    d = pd.DataFrame(rr)
    rows.append(dict(test=test, variant=variant, n=len(d), runaway=int(d.runaway.sum()),
                     median_spikes=int(d.total_spikes.median()), mn9_mean_hz=round(d.mn9_hz.mean(), 2)))
    pd.DataFrame(rows).to_csv(R / "v2ln30_flip.csv", index=False)
    print(rows[-1], flush=True)


saved = [brain._count[brain._indptr[i]:brain._indptr[i + 1]].copy() for i in v2]
try:
    for i in v2:
        a, b = brain._indptr[i], brain._indptr[i + 1]
        brain._count[a:b] = -np.abs(brain._count[a:b])
    var = "2 v2LN30 neurons made inhibitory"
    add("olfactory trigger: 10 DM1 ORNs fire once", var, [common.trial_summary(volley(dm1), brain, ids)[0]])
    add("20 first-firing neurons fire once", var, [common.trial_summary(volley(first20), brain, ids)[0]])
    add(f"largest strong loop ({loop7.size} neurons) fires once", var,
        [common.trial_summary(volley(loop7), brain, ids)[0]])
    add("Ir94e 200 Hz, 60 trials (seeds 0-1; intact: 9/60)", var,
        [common.trial_summary(common.run_one(brain, ir, s, k, 1000.0), brain, ids)[0]
         for s in (0, 1) for k in range(30)])
    add("sugar 100 Hz, 30 trials (MN9; intact 67.63 Hz)", var,
        [common.trial_summary(common.run_one(brain, sug, 0, k, 1000.0), brain, ids)[0] for k in range(30)])
finally:
    for i, s in zip(v2, saved):
        brain._count[brain._indptr[i]:brain._indptr[i + 1]] = s
add("olfactory trigger after restoring (must ignite)", "intact", [common.trial_summary(volley(dm1), brain, ids)[0]])
print("finished", flush=True)

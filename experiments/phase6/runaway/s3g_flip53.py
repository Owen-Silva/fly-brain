"""Step 3g: the olfaction lane's explanation, tested on the taste runaway.

Plain English
-------------
The Phase 5 olfaction lane found that its "ignition" goes away if 53
antennal-lobe local neurons whose transmitter is predicted (at low
confidence) to be serotonin or dopamine are made inhibitory, on the view that
these types (lLN1, lLN2T, ...) are really GABAergic. The coordinator asked us
to test the same change on the sugar 200 + Ir94e 200 runaway, and more
broadly whether other low-confidence "monoamine" neurons (serotonin, dopamine,
octopamine: all treated as excitatory by the model) form the loop.

Caution recorded in the write-up: FlyWire's own curated annotation lists 28 of
these 53 (types lLN1_b/c and lLN2T_a-c) as CHOLINERGIC (Shang et al. 2007,
antibody staining), i.e. excitatory, so flipping them is a what-if, not a fix.

Variants (each applied in this process only, restored afterwards):
  F53  : the 53 serotonin/dopamine-predicted AL local neurons made inhibitory
  F25  : only the 25 of them NOT in the FlyWire-cholinergic types
  MONO : every neuron predicted serotonin/dopamine/octopamine with confidence
         < 0.5, outside the Kenyon cells (which are known cholinergic), and
         without a measured transmitter on record, made inhibitory
Tests per variant: sugar 200 + Ir94e 200 (150 trials, seeds 0-4 = step 1a's
inputs; intact 6/150), Ir94e 200 (60 trials, seeds 0-1; intact 9/60), the
olfactory trigger, the 38 eLNs firing once, sugar 100 MN9 (30 trials).
Also: how many neurons of the runaway core are monoamine-predicted.

Output: results/flip_tests.csv, results/monoamine_in_core.txt
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
conf = pd.read_parquet(common.LABELS_630, columns=["root_id", "top_nt_conf"]).set_index("root_id") \
    .top_nt_conf.reindex(lab.root_id).to_numpy()
A = pd.read_csv(common.ROOT / "data/flywire/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                usecols=["root_id", "known_nt"], dtype={"root_id": "int64"}, low_memory=False) \
    .set_index("root_id").known_nt
known = A.reindex(lab.root_id).fillna("").to_numpy()
rid, cc, ht, nt = (lab.root_id.to_numpy(), lab.cell_class.to_numpy(), lab.hemibrain_type.to_numpy(),
                   lab.top_nt.to_numpy())
n = brain.n_neurons
has = np.diff(brain._indptr) > 0
sign = np.zeros(n, int)
sign[has] = np.sign(brain._count[brain._indptr[:-1][has]])
aln = cc == "ALLN"
eln = aln & np.isin(ht, ["lLN1_b,lLN1_c", "lLN2T_a", "lLN2T_b", "lLN2T_c"])
monoamine = np.isin(nt, ["serotonin", "dopamine", "octopamine"])
f53 = aln & np.isin(nt, ["serotonin", "dopamine"])
f25 = f53 & ~eln
mono = monoamine & (conf < 0.5) & (cc != "Kenyon_Cell") & (known == "") & (sign > 0)
print(f"F53 {f53.sum()} (of which FlyWire-cholinergic types {int((f53 & eln).sum())}), F25 {f25.sum()}, "
      f"MONO {mono.sum()}", flush=True)

# how much of the runaway core is monoamine-predicted?
core = pd.read_csv(R / "core_neurons.csv")
cm = np.isin(rid, core.root_id.to_numpy(np.int64))
lines = [f"runaway core neurons: {cm.sum()}",
         f"  predicted serotonin/dopamine/octopamine: {int((cm & monoamine).sum())}, of which Kenyon "
         f"cells {int((cm & monoamine & (cc == 'Kenyon_Cell')).sum())}, AL local neurons "
         f"{int((cm & monoamine & aln).sum())}, other {int((cm & monoamine & (cc != 'Kenyon_Cell') & ~aln).sum())}",
         f"  in the MONO flip set: {int((cm & mono).sum())}",
         "  MONO set by cell class: " + str(pd.Series(cc[mono]).replace("", "(none)").value_counts().head(10).to_dict())]
(R / "monoamine_in_core.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines), flush=True)


@contextmanager
def inhibitory(mask):
    rows_ = np.flatnonzero(mask & has)
    saved = [brain._count[brain._indptr[i]:brain._indptr[i + 1]].copy() for i in rows_]
    try:
        for i in rows_:
            a, b = brain._indptr[i], brain._indptr[i + 1]
            brain._count[a:b] = -np.abs(brain._count[a:b])
        yield
    finally:
        for i, s in zip(rows_, saved):
            brain._count[brain._indptr[i]:brain._indptr[i + 1]] = s


both = {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}}
ir = {i: 200.0 for i in ids["IR94E"]}
sug = {i: 100.0 for i in ids["SUGAR"]}
dm1 = rid[ht == "ORN_DM1"][:10]
rows = []


def volley(trig):
    trig = np.asarray(trig, np.int64)
    return brain.run_with_input_events([(np.full(trig.size, 50), trig)], excite=trig, duration_ms=1000.0)


def add(test, variant, rr):
    d = pd.DataFrame(rr)
    rows.append(dict(test=test, variant=variant, n=len(d), runaway=int(d.runaway.sum()),
                     median_spikes=int(d.total_spikes.median()), mn9_mean_hz=round(d.mn9_hz.mean(), 2)))
    pd.DataFrame(rows).to_csv(R / "flip_tests.csv", index=False)
    print(rows[-1], flush=True)


for name, mask in ((f"F53: {f53.sum()} 5-HT/DA-predicted AL local neurons inhibitory", f53),
                   (f"F25: {f25.sum()} of them outside FlyWire-cholinergic types inhibitory", f25),
                   (f"MONO: {mono.sum()} low-confidence monoamine neurons (not KCs, no measured NT) inhibitory", mono)):
    with inhibitory(mask):
        add("olfactory trigger: 10 DM1 ORNs fire once", name, [common.trial_summary(volley(dm1), brain, ids)[0]])
        add("38 eLNs fire once", name, [common.trial_summary(volley(rid[eln]), brain, ids)[0]])
        add("sugar 100 Hz, 30 trials (MN9; intact 67.63)", name,
            [common.trial_summary(common.run_one(brain, sug, 0, k, 1000.0), brain, ids)[0] for k in range(30)])
        add("Ir94e 200 Hz, 60 trials (intact 9/60)", name,
            [common.trial_summary(common.run_one(brain, ir, s, k, 1000.0), brain, ids)[0]
             for s in (0, 1) for k in range(30)])
        add("sugar 200 + Ir94e 200, 150 trials (intact 6/150)", name,
            [common.trial_summary(common.run_one(brain, both, s, k, 1000.0), brain, ids)[0]
             for s in range(5) for k in range(30)])
add("olfactory trigger after restoring (must ignite)", "intact", [common.trial_summary(volley(dm1), brain, ids)[0]])
print("finished", flush=True)

"""Step 2 bug checks that need no simulation.

Plain English
-------------
* Are the 18 Ir94e (and 21 sugar) IDs the paper's, all present, unique, and
  what does FlyWire's own annotation call them (type, side, transmitter)?
* Signs: does the model's +/- for each stimulated neuron agree with its
  predicted transmitter, and with the reference file's sign? Is every
  neuron's sign the same on all its outgoing connections?
* Indexing: does the brain's row order equal the reference completeness
  file, and does ID -> row -> ID round-trip?
* Autapses (a neuron connected to itself) with excitatory weight could make
  one neuron re-excite itself forever; count them.

Output: results/static_checks.txt
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
ids = common.paper_ids()
lab = common.labels(brain)
out = []


def say(s):
    out.append(s)
    print(s, flush=True)


# indexing
comp = pd.read_csv(common.ROOT / "data/reference/2023_03_23_completeness_630_final.csv", index_col=0)
say(f"row order equals reference completeness file: {np.array_equal(comp.index.to_numpy(np.int64), brain.root_ids)}")
for k in ("SUGAR", "IR94E", "BITTER", "WATER"):
    v = np.array(ids[k], np.int64)
    idx = brain.index_of(v)
    say(f"{k}: {v.size} IDs, unique {np.unique(v).size}, round-trip ID->row->ID ok: "
        f"{np.array_equal(brain.root_ids[idx], v)}")
say(f"sugar/Ir94e overlap: {len(set(ids['SUGAR']) & set(ids['IR94E']))}")

# per-neuron sign consistency
pre = np.repeat(np.arange(brain.n_neurons), np.diff(brain._indptr))
sg = np.sign(brain._count)
mn = np.full(brain.n_neurons, 2)
mx = np.full(brain.n_neurons, -2)
np.minimum.at(mn, pre, sg)
np.maximum.at(mx, pre, sg)
has = np.diff(brain._indptr) > 0
say(f"neurons whose outgoing connections mix + and -: {int((mn[has] != mx[has]).sum())} of {int(has.sum())}")
model_sign = np.where(has, mx, 0)
m = has & lab.sign.notna().to_numpy()
say(f"model sign == sign from Phase 2 transmitter labels: {np.mean(model_sign[m] == lab.sign.to_numpy()[m]):.5f} "
    f"(n={int(m.sum())}); == reference sign column: {np.mean(model_sign[m] == lab.ref_sign.to_numpy()[m]):.5f}")
say(f"zero-weight connections: {int((brain._count == 0).sum())}")

# the stimulated neurons
A = pd.read_csv(common.ROOT / "data/flywire/Supplemental_file1_neuron_annotations.tsv", sep="\t",
                usecols=["root_id", "cell_sub_class", "cell_type", "side", "top_nt"],
                dtype={"root_id": "int64"}, low_memory=False).set_index("root_id")
for k in ("IR94E", "SUGAR"):
    v = np.array(ids[k], np.int64)
    idx = brain.index_of(v)
    L = lab.iloc[idx]
    a783 = A.reindex(v)
    say(f"\n{k} (n={v.size}): class {L.cell_class.value_counts().to_dict()}, "
        f"side (630 labels) {L.side.value_counts().to_dict()}, nerve {L.nerve.value_counts().to_dict()}")
    say(f"  transmitter {L.top_nt.value_counts().to_dict()}; model sign {pd.Series(model_sign[idx]).value_counts().to_dict()}; "
        f"reference sign {L.ref_sign.value_counts().to_dict()}")
    say(f"  FlyWire v783 annotation types for the same IDs: {a783.cell_type.value_counts(dropna=False).to_dict()}, "
        f"sub-class {a783.cell_sub_class.value_counts(dropna=False).to_dict()}")
    outs = [brain._count[brain._indptr[i]:brain._indptr[i + 1]] for i in idx]
    say(f"  outgoing synapses: total {int(sum(np.abs(o).sum() for o in outs))}, "
        f"excitatory {int(sum(o[o > 0].sum() for o in outs))}, inhibitory {int(-sum(o[o < 0].sum() for o in outs))}")

# autapses
self_m = brain._post == pre
say(f"\nautapses (neuron -> itself): {int(self_m.sum())}; excitatory {int((self_m & (brain._count > 0)).sum())}, "
    f"largest excitatory autapse {int(brain._count[self_m & (brain._count > 0)].max()) if (self_m & (brain._count > 0)).any() else 0} synapses")
# whole-brain E/I
say(f"excitatory neurons {int((model_sign > 0).sum())}, inhibitory {int((model_sign < 0).sum())}; "
    f"excitatory synapses {int(brain._count[brain._count > 0].sum())}, inhibitory {int(-brain._count[brain._count < 0].sum())}")
(common.RESULTS / "static_checks.txt").write_text("\n".join(out) + "\n", encoding="utf-8")
print("finished", flush=True)

"""Wiring check (no simulation): how many synaptic steps separate the DM1 /
DA2 smell neurons from the steering and walking descending neurons, and
who talks directly to those descending neurons?

Plain English
-------------
"Hops" = the smallest number of neuron-to-neuron connections a signal has to
cross, counting only connections with at least 5 synapses (weaker ones are
often reconstruction noise and carry little drive in the model). We also
count only *excitatory* hops separately, because in this model only
excitatory connections can make a silent neuron start firing.

Output: results/paths_hops.csv, results/dn_inputs.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "competition"))
sys.path.insert(0, str(HERE))
from phase5_common import get_brain, labels  # noqa: E402
from steering_ids import STEERING  # noqa: E402

OUT = HERE / "results"
OUT.mkdir(exist_ok=True)
brain = get_brain(globals())
lab = labels()
assert np.array_equal(lab.root_id.to_numpy(), brain.root_ids)
indptr, post, cnt = brain._indptr, brain._post, brain._count
pre = np.repeat(np.arange(brain.n_neurons), np.diff(indptr))


def hops_from(src_rows, min_syn=5, excit_only=False, max_hops=8):
    keep = np.abs(cnt) >= min_syn
    if excit_only:
        keep &= cnt > 0
    p, q = pre[keep], post[keep]
    order = np.argsort(p, kind="stable")
    p, q = p[order], q[order]
    ptr = np.zeros(brain.n_neurons + 1, np.int64)
    np.cumsum(np.bincount(p, minlength=brain.n_neurons), out=ptr[1:])
    dist = np.full(brain.n_neurons, -1, np.int64)
    frontier = np.asarray(src_rows, np.int64)
    dist[frontier] = 0
    for h in range(1, max_hops + 1):
        nxt = np.concatenate([q[ptr[i]:ptr[i + 1]] for i in frontier]) if frontier.size else frontier
        nxt = np.unique(nxt)
        nxt = nxt[dist[nxt] < 0]
        dist[nxt] = h
        frontier = nxt
        if not frontier.size:
            break
    return dist


rows = []
for odor in ("DM1", "DA2"):
    for side in ("left", "right"):
        src = lab.index[(lab.hemibrain_type == f"ORN_{odor}") & (lab.side == side)].to_numpy()
        for excit in (False, True):
            d = hops_from(src, excit_only=excit)
            for name, rid in STEERING.items():
                rows.append(dict(odor=odor, orn_side=side, excitatory_only=excit, target=name,
                                 hops=int(d[brain.index_of([rid])[0]])))
pd.DataFrame(rows).to_csv(OUT / "paths_hops.csv", index=False)
print(pd.DataFrame(rows).pivot_table(index="target", columns=["odor", "orn_side", "excitatory_only"],
                                     values="hops").to_string())

# direct inputs to each steering DN (top 8 by synapse count)
out = []
for name, rid in STEERING.items():
    r = brain.index_of([rid])[0]
    m = post == r
    pr, c = pre[m], cnt[m]
    order = np.argsort(-np.abs(c))[:8]
    for k in order:
        L = lab.iloc[pr[k]]
        out.append(dict(target=name, pre_root_id=int(L.root_id), synapses=int(c[k]),
                        pre_cell_type=L.cell_type, pre_hemibrain_type=L.hemibrain_type,
                        pre_class=L.cell_class, pre_side=L.side, pre_nt=L.top_nt,
                        total_inputs=int(np.abs(c).sum())))
pd.DataFrame(out).to_csv(OUT / "dn_inputs.csv", index=False)
print("saved dn_inputs.csv")

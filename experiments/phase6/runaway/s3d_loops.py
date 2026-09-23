"""Step 3d: the smallest self-exciting loops, shown and tested.

Plain English
-------------
A single spike raises a partner's voltage by about 0.043 mV per synapse, so
a connection needs about 162 synapses before ONE spike alone can make the
partner fire. Step 3a found only 3 closed loops in the whole brain built
purely from such "one spike is enough" excitatory connections among the
runaway neurons, all in the antennal lobe. Here we list them, then test:
  * make just the neurons of these loops fire once (no other input): does
    the whole brain ignite?
  * silence just these neurons: does the olfactory trigger (10 DM1 smell
    neurons firing once) and Ir94e 200 Hz (60 trials) still ignite it?

Output: results/strong_loops.txt, results/strong_loops_tests.csv
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
R = common.RESULTS
ids = common.paper_ids()
lab = common.labels(brain)
n = brain.n_neurons
rid, ht = lab.root_id.to_numpy(), lab.hemibrain_type.to_numpy()
core = np.isin(rid, pd.read_csv(R / "core_neurons.csv").root_id.to_numpy(np.int64))
pre = np.repeat(np.arange(n), np.diff(brain._indptr))
post = brain._post.astype(np.int64)
cnt = brain._count.astype(np.int64)
m = (cnt >= 162) & core[pre] & core[post]
G = sp.csr_matrix((cnt[m].astype(float), (pre[m], post[m])), shape=(n, n))
nc, comp = connected_components(G, directed=True, connection="strong")
sizes = np.bincount(comp)
lines = []
members_all = []
for c in np.flatnonzero(sizes > 1):
    mem = np.flatnonzero(comp == c)
    members_all.extend(mem.tolist())
    lines.append(f"Loop group of {mem.size} neurons:")
    for u in mem:
        lines.append(f"  {rid[u]}  {lab.cell_class[u]}/{ht[u] or lab.cell_type[u]}  side {lab.side[u]}  "
                     f"predicted {lab.top_nt[u]}  model sign {'+' if lab.sign[u] > 0 else '-'}")
    sub = G[mem][:, mem].tocoo()
    for a, b, w in zip(sub.row, sub.col, sub.data):
        lines.append(f"    {ht[mem[a]] or rid[mem[a]]} -> {ht[mem[b]] or rid[mem[b]]}: {int(w)} synapses")
(R / "strong_loops.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines), flush=True)
loop_ids = rid[np.array(members_all, np.int64)]

rows = []
dm1 = rid[ht == "ORN_DM1"][:10]


def volley(ids_, silence=()):
    ids_ = np.asarray(ids_, np.int64)
    return brain.run_with_input_events([(np.full(ids_.size, 50), ids_)], excite=ids_,
                                       duration_ms=1000.0, silence=silence)


def add(test, res_rows):
    d = pd.DataFrame(res_rows)
    rows.append(dict(test=test, n=len(d), runaway=int(d.runaway.sum()),
                     median_spikes=int(d.total_spikes.median()),
                     last100_neurons=int(d.distinct_last_100ms.median())))
    pd.DataFrame(rows).to_csv(R / "strong_loops_tests.csv", index=False)
    print(rows[-1], flush=True)


add(f"volley: the {loop_ids.size} loop neurons fire once, no other input",
    [common.trial_summary(volley(loop_ids), brain, ids)[0]])
biggest = np.flatnonzero(comp == np.argmax(sizes))
add(f"volley: the largest loop ({biggest.size} neurons) fires once",
    [common.trial_summary(volley(rid[biggest]), brain, ids)[0]])
add(f"olfactory trigger with the {loop_ids.size} loop neurons silenced",
    [common.trial_summary(volley(dm1, loop_ids), brain, ids)[0]])
ir = {i: 200.0 for i in ids["IR94E"]}
add(f"Ir94e 200 Hz, 60 trials, {loop_ids.size} loop neurons silenced",
    [common.trial_summary(common.run_one(brain, ir, s, k, 1000.0, silence=loop_ids), brain, ids)[0]
     for s in (0, 1) for k in range(30)])
print("finished", flush=True)

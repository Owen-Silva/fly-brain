"""Wiring check (no simulation): where do the DM1 / DA2 smell neurons and the
antennal-lobe neurons send their synapses, and with which sign?

Plain English
-------------
The simulation showed that driving one kind of smell neuron lights up most of
the antennal lobe. This script looks at the wiring to see which connections
could spread the activity: for each group of senders it adds up the synapses
it makes onto each kind of receiver, split into excitatory (+) and
inhibitory (-) as the model uses them.

Output: results/al_wiring.csv
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "competition"))
from phase5_common import get_brain, labels  # noqa: E402

OUT = HERE / "results"
brain = get_brain(globals())
lab = labels()
indptr, post, cnt = brain._indptr, brain._post, brain._count
tclass = lab.cell_class.where(lab.cell_class != "", lab.super_class).to_numpy()
tclass = np.where(lab.hemibrain_type.str.startswith("ORN_"), "ORN", tclass)

senders = {
    "ORN_DM1": lab.hemibrain_type == "ORN_DM1",
    "ORN_DA2": lab.hemibrain_type == "ORN_DA2",
    "ORN_all": lab.hemibrain_type.str.startswith("ORN_"),
    "PN_DM1": lab.hemibrain_type.str.startswith("DM1_"),
    "PN_DA2": lab.hemibrain_type.str.startswith("DA2_"),
    "ALPN_excit": (lab.cell_class == "ALPN") & (lab.top_nt == "acetylcholine"),
    "ALLN_excit": (lab.cell_class == "ALLN") & (lab.top_nt == "acetylcholine"),
    "ALLN_inhib": (lab.cell_class == "ALLN") & lab.top_nt.isin(["gaba", "glutamate"]),
    "KC": lab.cell_class == "Kenyon_Cell",
    "APL": lab.cell_type == "APL",
}
rows = []
for name, mask in senders.items():
    src = np.flatnonzero(mask.to_numpy())
    seg = [np.arange(indptr[i], indptr[i + 1]) for i in src]
    e = np.concatenate(seg) if seg else np.zeros(0, np.int64)
    d = pd.DataFrame({"target_class": tclass[post[e]], "syn": cnt[e]})
    d["sign"] = np.where(d.syn > 0, "+", "-")
    agg = d.groupby(["target_class", "sign"]).syn.agg(lambda x: int(np.abs(x).sum())).reset_index()
    total = agg.syn.sum()
    agg = agg.sort_values("syn", ascending=False).head(8)
    for _, r in agg.iterrows():
        rows.append(dict(sender=name, n_senders=src.size, target_class=r.target_class, sign=r.sign,
                         synapses=int(r.syn), pct_of_sender_output=round(100 * r.syn / total, 1)))
df = pd.DataFrame(rows)
df.to_csv(OUT / "al_wiring.csv", index=False)
print(df.to_string(index=False))

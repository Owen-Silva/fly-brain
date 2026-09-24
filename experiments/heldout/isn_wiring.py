"""Why do the ISNs push MN9 the 'wrong' way in the model? (wiring only, no simulation)

Plain English
-------------
Test G3/G4 found that driving the four ISNs lowers MN9's response to sugar and
raises its response to water, the reverse of real flies. This script reads the
published model's wiring (snapshot 630, the paper's signs) and lists:
  1. the ISNs' strongest direct targets (type, transmitter, sign, synapses);
  2. two-step routes ISN -> X -> MN9 (signed synapse products);
  3. which ISN targets also receive input straight from the sugar or water
     taste neurons (where the ISNs could meet the taste signal).
It reads the edge table in filtered pieces (a few MB at a time), so it does not
load the whole connectome. Output: results/isn_wiring.txt
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from feeding_heldout import ISN, MN9_CONTRA, OA_VPM4, SUGAR, WATER  # noqa: E402

CACHE = ROOT / "data" / "cache"
nt = pd.read_parquet(CACHE / "connectome_630_neurons.parquet",
                     columns=["root_id", "cell_type", "hemibrain_type", "top_nt", "sign", "side"])
comp = pd.read_csv(ROOT / "data" / "reference" / "2023_03_23_completeness_630_final.csv", usecols=[0])
assert np.array_equal(nt.root_id.to_numpy(), comp.iloc[:, 0].to_numpy()), "row order != model index"
idx = {int(r): i for i, r in enumerate(nt.root_id.to_numpy())}


def name(i):
    r = nt.iloc[i]
    t = r.cell_type if isinstance(r.cell_type, str) else (r.hemibrain_type if isinstance(r.hemibrain_type, str) else "?")
    return f"{t} ({r.top_nt}, {r.side}, {int(r.root_id)})"


def edges(col, members):
    """All edges whose `col` ('pre' or 'post') is in members (model indices)."""
    f = pq.ParquetFile(CACHE / "connectome_630_edges.parquet")
    keep = set(members)
    out = []
    for g in range(f.metadata.num_row_groups):
        t = f.read_row_group(g, columns=["pre", "post", "syn_count", "sign"]).to_pandas()
        out.append(t[t[col].isin(keep)])
    return pd.concat(out, ignore_index=True)


L = []
isn_i = [idx[r] for r in ISN]
mn9 = idx[MN9_CONTRA]
out_isn = edges("pre", isn_i)
out_isn["w"] = out_isn.syn_count * out_isn.sign
tgt = out_isn.groupby("post").w.sum().sort_values(key=np.abs, ascending=False)
L.append(f"ISNs: {len(ISN)} cells, {int(out_isn.syn_count.sum())} output synapses onto {len(tgt)} partners "
         f"(signs: {sorted(set(out_isn.sign.tolist()))})")
tsign = nt.sign.to_numpy()[out_isn.post.to_numpy()]
L.append(f"Share of ISN output synapses onto cells the model treats as inhibitory (their own sign -1): "
         f"{out_isn.syn_count[tsign < 0].sum() / out_isn.syn_count.sum():.0%}")
L.append("Top 15 direct targets (signed synapses summed over the 4 ISNs):")
for p, w in tgt.head(15).items():
    L.append(f"  {int(w):+5d}  {name(int(p))}")
L.append(f"Direct ISN -> MN9 synapses: {int(tgt.get(mn9, 0))}")

into_mn9 = edges("post", [mn9])
into_mn9["w"] = into_mn9.syn_count * into_mn9.sign
w_mn9 = into_mn9.groupby("pre").w.sum()
two = pd.DataFrame({"isn_to_x": tgt}).join(w_mn9.rename("x_to_mn9"), how="inner")
two["product"] = two.isn_to_x * two.x_to_mn9
L.append(f"Two-step routes ISN -> X -> MN9: {len(two)} X cells; signed sum of products "
         f"{int(two['product'].sum()):+d} (positive = net excitation)")
for x, r in two.reindex(two["product"].abs().sort_values(ascending=False).index).head(8).iterrows():
    L.append(f"  ISN->X {int(r.isn_to_x):+4d}, X->MN9 {int(r.x_to_mn9):+4d}: {name(int(x))}")

for lab, grn in (("sugar", SUGAR), ("water", WATER)):
    out_g = edges("pre", [idx[r] for r in grn])
    gt = out_g.groupby("post").syn_count.sum()
    shared = pd.DataFrame({"isn_to_x": tgt}).join(gt.rename(f"{lab}_to_x"), how="inner")
    shared = shared.reindex(shared[f"{lab}_to_x"].sort_values(ascending=False).index)
    L.append(f"ISN targets that also get direct {lab}-neuron input: {len(shared)}")
    for x, r in shared.head(8).iterrows():
        L.append(f"  ISN->X {int(r.isn_to_x):+4d}, {lab}->X {int(r[f'{lab}_to_x']):4d}, "
                 f"X->MN9 {int(w_mn9.get(x, 0)):+4d}: {name(int(x))}")

oa = edges("pre", [idx[r] for r in OA_VPM4])
L.append(f"OA-VPM4: {int(oa.syn_count.sum())} output synapses; onto the 21 sugar neurons: "
         f"{int(oa[oa.post.isin([idx[r] for r in SUGAR])].syn_count.sum())}; onto MN9: "
         f"{int(oa[oa.post == mn9].syn_count.sum())}")
(HERE / "results" / "isn_wiring.txt").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))

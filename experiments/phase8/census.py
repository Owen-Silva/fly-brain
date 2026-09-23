"""What the learning rule acts on, and a check of the compartment tables.

Writes results/census.md. Uses the MB circuit (it contains every connection
between projection neurons, Kenyon cells, MBONs, DANs, APL and DPM, so the
numbers are the same as in the whole brain).

The cross-check (research doc section 2.4): DANs also make direct synapses
onto MBONs. If our compartment tables are right, most of each DAN type's
synapses onto MBONs should land on MBONs that share one of its compartments.
"""

import numpy as np
import pandas as pd

from analyze_phase8 import md
from common import RES, get_model
from sim.plasticity import DAN_COMPARTMENTS, MBON_COMPARTMENTS

pb, lab, _ = get_model("circuit")
b = pb.brain
hb = lab.hemibrain_type.to_numpy()
cc = lab.cell_class.to_numpy()
pre = np.repeat(np.arange(b.n_neurons), np.diff(b._indptr))
post, cnt = b._post, np.abs(b._count)

out = ["# Phase 8 census (snapshot 630)\n"]
parts = {k: int((cc == v).sum()) for k, v in
         [("projection neurons", "ALPN"), ("Kenyon cells", "Kenyon_Cell"), ("MBONs", "MBON"),
          ("DANs", "DAN")]}
parts["APL + DPM"] = int(np.isin(hb, ["APL", "DPM"]).sum())
out.append("Circuit: " + ", ".join(f"{v} {k}" for k, v in parts.items())
           + f"; {b.n_connections} connections among them.\n")
t = pb.plastic_table
out.append(f"Plastic KC->MBON connections: {len(t)} (from {t.kc_row.nunique()} KCs onto "
           f"{t.mbon_row.nunique()} MBONs, {int(t['count'].sum())} synapses) in "
           f"{len(pb.groups)} synapse groups (compartment set x hemisphere).\n")
kc_mbon_all = int(((cc[pre] == "Kenyon_Cell") & (cc[post] == "MBON")).sum())
out.append(f"All KC->MBON connections in the data: {kc_mbon_all} (so every one is plastic; "
           "the 1 untyped MBON gets no KC input).\n")
out.append(f"DANs that feed the dopamine signal: {pb.dan_rows.size} "
           f"(types {sorted(set(hb[pb.dan_rows]))[0]}..{sorted(set(hb[pb.dan_rows]))[-1]}); "
           "not assigned: PPL107, PPL201-203 and 13 untyped DANs.\n")

# per MBON type: which compartments its KC synapses were put in
g = t.groupby(["mbon_type", "compartments"])["count"].sum().unstack(fill_value=0)
out.append("\n## KC->MBON synapses per MBON type and assigned compartment\n")
comp_tab = t.groupby("mbon_type").apply(
    lambda x: ", ".join(f"{c}: {n}" for c, n in x.groupby("compartments")["count"].sum().items()),
    include_groups=False)
out.append(md(comp_tab.rename("synapses by compartment").to_frame()))

# DAN hemisphere split
fl = pb.dan_frac_left
s = pd.DataFrame({"type": hb[fl.index.to_numpy()], "label_side": lab.side.to_numpy()[fl.index],
                  "frac_left": fl.to_numpy()})
sd = s.groupby("type").agg(cells=("frac_left", "size"), mean_frac_left=("frac_left", "mean"),
                           min_frac_left=("frac_left", "min"), max_frac_left=("frac_left", "max"))
out.append("\n\n## DAN hemisphere split (fraction of each DAN's KC synapses in the LEFT mushroom "
           "body)\n\nMany DANs innervate both mushroom bodies in FlyWire, so dopamine is split by "
           "these measured fractions, not by the soma side.\n")
out.append(md(sd))

# cross-check
dm = (cc[pre] == "DAN") & (cc[post] == "MBON")
x = pd.DataFrame({"dan": hb[pre[dm]], "mbon": hb[post[dm]], "n": cnt[dm]})
x = x[x.dan.isin(list(DAN_COMPARTMENTS)) & x.mbon.isin(list(MBON_COMPARTMENTS))]
x["shares"] = [bool(set(DAN_COMPARTMENTS[d]) & set(MBON_COMPARTMENTS[m]))
               for d, m in zip(x.dan, x.mbon)]
cx = x.groupby("dan").apply(lambda y: pd.Series({
    "DAN->MBON synapses": int(y.n.sum()),
    "to MBONs sharing a compartment": int(y.n[y.shares].sum()),
    "fraction": y.n[y.shares].sum() / y.n.sum(),
    "top target": y.groupby("mbon").n.sum().idxmax()}), include_groups=False)
tot = x.n[x.shares].sum() / x.n.sum()
out.append(f"\n\n## Cross-check: DAN -> MBON synapses that join a DAN and an MBON sharing a "
           f"compartment\n\nOverall: {tot:.1%} of {int(x.n.sum())} synapses.\n\n")
out.append(md(cx))
(RES / "census.md").write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out[:6]))
print(f"cross-check overall {tot:.1%}")
print(cx.to_string())

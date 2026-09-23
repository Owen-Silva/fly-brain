"""Where does the smell-driven firing of PPL1-γ1pedc (PPL101) come from in the whole brain?

Plain English
-------------
In the whole brain a smell alone makes the "punishment" dopamine neurons PPL1-γ1pedc fire,
while in the mushroom-body circuit on its own they stay silent. This script gives the
whole brain one 1-s sniff of each odor (the same input and random seeds as the first test
sniff of the conditioning runs, learning off) and adds up, for the two PPL101 cells, the
input from every neuron that connects to them: spikes of that neuron x (signed) number of
synapses. The result is grouped by the input neuron's type and marked "in circuit" or
"outside" (outside = not a PN, KC, MBON, DAN, APL or DPM, so absent from the circuit model).

Usage: python trace_ppl1.py [model]     (default brain_alln; one whole brain in memory)
Writes results/trace_ppl1_<model>.csv (by input type) and prints the top inputs.
"""

import sys

import numpy as np
import pandas as pd

from common import ORN_RATE_HZ, RES, get_model, odor_input_rows, type_rows
from run_phase8 import TEST_MS, WINDOW, load_calibration, rule_from
from sim.plasticity import mb_circuit_rows

model = sys.argv[1] if len(sys.argv) > 1 else "brain_alln"
pb, lab, kind = get_model(model, dan_mode="modulatory", rule=rule_from(load_calibration()))
assert kind == "orn"
odors = odor_input_rows(lab, kind)
b = pb.brain
target = type_rows(lab, "PPL101")
pre_of_edge = np.repeat(np.arange(b.n_neurons), np.diff(b._indptr))
m = np.isin(b._post, target)
e_pre, e_cnt = pre_of_edge[m], b._count[m].astype(np.int64)
# in "modulatory" mode the fast outputs of the compartment DANs are switched off
# (sim/plasticity.py), so their connections onto PPL101 do not act: count them as 0
e_cnt = np.where(np.isin(e_pre, pb.dan_rows), 0, e_cnt)
in_circ = np.isin(e_pre, mb_circuit_rows(lab))
typ = lab.hemibrain_type.fillna("").to_numpy()
ctype = lab.cell_type.fillna("").to_numpy()
cls = lab.cell_class.fillna("").to_numpy()
name = np.where(typ[e_pre] != "", typ[e_pre], ctype[e_pre])
name = np.where(name != "", name, "untyped")

rows = []
for od in ("A", "B"):
    for seed in (0, 1, 2):
        rng_seed = [seed, 1, 0, 0 if od == "A" else 1]           # = first test sniff
        res = pb.run([(odors[od], ORN_RATE_HZ, 0.0, 1000.0)], TEST_MS, rng_seed,
                     plastic=False)
        s0, s1 = int(WINDOW[0] / res.dt_ms), int(WINDOW[1] / res.dt_ms)
        w = (res.step >= s0) & (res.step < s1)
        c = np.bincount(res.neuron[w], minlength=b.n_neurons)
        drive = c[e_pre] * e_cnt
        rows.append(pd.DataFrame(dict(odor=od, seed=seed, input_type=name,
                                      input_class=cls[e_pre], in_circuit=in_circ,
                                      synapses=e_cnt, pre_spikes=c[e_pre], drive=drive)))
        print(f"odor {od} seed {seed}: PPL101 spikes {int(c[target].sum())}, "
              f"summed input {int(drive.sum())} (outside circuit {int(drive[~in_circ].sum())})",
              flush=True)
d = pd.concat(rows)
g = (d.groupby(["input_type", "input_class", "in_circuit"])
     .agg(n_links=("synapses", "size"), synapses=("synapses", "sum"),
          drive_per_sniff=("drive", "sum"))
     .reset_index())
g[["n_links", "synapses", "drive_per_sniff"]] /= 6.0            # 2 odors x 3 seeds
g = g.sort_values("drive_per_sniff", ascending=False)
g.to_csv(RES / f"trace_ppl1_{model}.csv", index=False)
tot = g.drive_per_sniff.sum()
exc = g.drive_per_sniff.clip(lower=0).sum()
print(f"net input per sniff {tot:.0f}; excitatory part {exc:.0f}; share of the excitatory "
      f"part from outside the circuit: "
      f"{g[~g.in_circuit].drive_per_sniff.clip(lower=0).sum() / max(exc, 1):.1%}")
print(g.head(15).to_string(index=False))

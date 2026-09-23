"""Phase 6 steering check: who drives the left and right DNa02 in the simulations?

Plain English
-------------
For each steering neuron, "drive" from one input neuron = that input's mean
firing rate (Hz) x its signed synapse count onto the steering neuron (plus for
excitatory, minus for inhibitory). Adding them up shows why one side wins. The
signs are the reference file's; the al_ln_literature fix only changes antennal-
lobe local neurons, none of which connect directly to DNa02 or DNa01 (checked
below). Uses the mean rates saved by s2_simulate.py (seed-averaged).

Output: results/dn_drivers.csv (top inputs per condition) and a printed summary.
"""
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RES = HERE / "results"
SIM = RES / "sim"
STEER = {"DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708,
         "DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551}


def main(variants=("al_ln", "al_ln_ipsi", "none"), gloms=("DM1", "DA1", "DM4", "DM2", "VA2", "DA2")):
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                        columns=["root_id", "cell_class", "cell_type", "hemibrain_type", "side"])
    e = pd.read_parquet(ROOT / "data/cache/connectome_630_edges.parquet", columns=["pre", "post", "syn_count", "ref_sign"])
    typ = n.cell_type.astype(object).where(n.cell_type.notna(), n.hemibrain_type.astype(object)).fillna("untyped").to_numpy()
    side = n.side.astype(object).fillna("na").to_numpy()
    rid = pd.Index(n.root_id.to_numpy())
    rows = []
    for k, r in STEER.items():
        i = rid.get_indexer([r])[0]
        inp = e[e.post == i]
        n_al_ln = int((n.cell_class.astype(object).fillna("").to_numpy()[inp.pre.to_numpy()] == "ALLN").sum())
        assert n_al_ln == 0, f"{k} has direct AL local-neuron input; signs would need the fix"
        w = (inp.syn_count * inp.ref_sign).to_numpy()
        pre = inp.pre.to_numpy()
        for v in variants:
            for g in gloms:
                for s in ("left", "right"):
                    fs = [SIM / f"{v}_{g}_{s}_s{sd}.npz" for sd in (0, 1, 2)]
                    if not all(f.exists() for f in fs):
                        continue
                    rate = np.mean([np.load(f)["rates"] for f in fs], axis=0)
                    d = rate[pre] * w
                    order = np.argsort(-np.abs(d))[:6]
                    rows.append(dict(variant=v, glomerulus=g, odor_side=s, dn=k,
                                     exc_drive=round(float(d[d > 0].sum()), 0), inh_drive=round(float(d[d < 0].sum()), 0),
                                     top_inputs="; ".join(f"{typ[pre[j]]}({side[pre[j]][0]}) {d[j]:+.0f}" for j in order
                                                          if d[j] != 0)))
    out = pd.DataFrame(rows)
    out.to_csv(RES / "dn_drivers.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_colwidth", 150)
    print(out[(out.glomerulus == "DM1") & out.dn.str.startswith("DNa02")].to_string(index=False))


if __name__ == "__main__":
    main()

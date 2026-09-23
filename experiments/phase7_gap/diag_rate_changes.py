"""Which cell types change most when the gap junctions are added? (diagnostic)

Plain English: for a condition (default DM1 left and right, 150 Hz), compares
every neuron's mean firing rate (3 seeds x 30 trials) between al_ln_literature
(experiments/phase7_signs counts) and a gap-junction version (this lane's
counts), sums the change per cell type and lists the biggest movers.
No simulation. Output: results/rate_changes_<config>.csv and stdout.
Usage: diag_rate_changes.py [config] (default gap_x1)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
SIGNS = ROOT / "experiments" / "phase7_signs" / "results" / "counts"
CONDS = ["dm1_left_150Hz", "dm1_right_150Hz", "dm1_both_150Hz"]


def rates(path, n):
    z = np.load(path)
    c = np.zeros(n)
    c[z["nz_idx"]] = z["nz_count"]
    return c / float(z["n_trials"])


def main(cfg="gap_x1"):
    lab = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                          columns=["root_id", "cell_class", "cell_type", "hemibrain_type", "side"])
    comp = pd.read_csv(ROOT / "data/reference/2023_03_23_completeness_630_final.csv", index_col=0)
    lab = lab.set_index("root_id").reindex(comp.index.to_numpy()).reset_index()
    for c in ("cell_class", "cell_type", "hemibrain_type", "side"):
        lab[c] = lab[c].astype(object).where(lab[c].notna(), "").astype(str)
    lab["label"] = np.where(lab.hemibrain_type != "", lab.hemibrain_type, lab.cell_type)
    lab["label"] = lab.label.where(lab.label != "", lab.cell_class)
    n = len(lab)
    out = []
    for cond in CONDS:
        b = np.mean([rates(SIGNS / f"al_ln_literature__{cond}__s{k}.npz", n) for k in (0, 1, 2)], 0)
        f = [RES / "counts" / f"{cfg}__{cond}__s{k}.npz" for k in (0, 1, 2)]
        if not all(x.exists() for x in f):
            continue
        g = np.mean([rates(x, n) for x in f], 0)
        d = pd.DataFrame({"label": lab.label, "side": lab.side, "cell_class": lab.cell_class,
                          "base_hz": b, "gap_hz": g, "diff_hz": g - b})
        t = d.groupby(["label", "side", "cell_class"]).agg(
            n=("diff_hz", "size"), base_hz_sum=("base_hz", "sum"), gap_hz_sum=("gap_hz", "sum"),
            diff_hz_sum=("diff_hz", "sum")).reset_index()
        t = t.reindex(t.diff_hz_sum.abs().sort_values(ascending=False).index)
        t.insert(0, "condition", cond)
        out.append(t.head(40))
        print(f"== {cond}: total spikes/s base {b.sum():.0f}, {cfg} {g.sum():.0f}")
        print(t.head(15).round(1).to_string(index=False))
    pd.concat(out).round(3).to_csv(RES / f"rate_changes_{cfg}.csv", index=False)


if __name__ == "__main__":
    main(*(sys.argv[1:] or []))

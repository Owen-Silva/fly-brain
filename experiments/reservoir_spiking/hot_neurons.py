"""Where does the activity go? From the saved per-neuron spike totals (seed 0).

For each network and input level: how many non-sensory neurons fire above
100 Hz, what share of all non-sensory spikes they make, the mean rate of the
neurons that fire at all, and (real network) which cell classes / types the
hot neurons are. Writes results/hot_neurons.json. No simulation.
"""
import json

import numpy as np

import lib_spk as L
from sim.sign_fixes import load_reference_arrays

rid = load_reference_arrays("630")[0]
lab = L.rlib.labels(rid)
full = __import__("pandas").read_parquet(L.rlib.LABELS_630, columns=["root_id", "cell_type"])
lab["cell_type"] = full.set_index("root_id").reindex(rid)["cell_type"].astype(str).to_numpy()
ns = (lab.super_class != "sensory").to_numpy(bool)
out = {}
for net in ("real_fix", "shuffle", "er"):
    for pk in (150, 400):
        t_all = np.load(L.RAW / f"main_{net}_s0_p{pk}_w100.npz")["totals"] / 40.0
        t = t_all[ns]
        a = t[t > 0]
        hot = t > 100
        rec = {"n_gt_100hz": int(hot.sum()), "share_spikes_gt_100hz": float(t[hot].sum() / t.sum()),
               "mean_rate_of_active_hz": float(a.mean()), "n_active": int(a.size)}
        if net == "real_fix":
            h = lab[ns][hot]
            rec["hot_super_class"] = h.super_class.value_counts().head(6).to_dict()
            rec["hot_cell_class"] = h.cell_class.value_counts().head(8).to_dict()
            rec["hot_cell_type"] = h.cell_type.value_counts().head(10).to_dict()
        out[f"{net}_{pk}"] = rec
(L.RESULTS / "hot_neurons.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out, indent=1))

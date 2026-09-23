"""Why does a little smell input light up so much of the brain?

Plain English
-------------
Driving the 68 DM1 smell neurons, even at only 10 Hz, made about 8,400
neurons fire (sugar at 100 Hz makes about 400 fire). This script tests
whether the smell circuits in the model *keep themselves going* once
started (like a microphone next to its own speaker), and which neurons
form the loop:

1. Volley test: every DM1 ORN fires exactly once at t = 5 ms, then no more
   input. If activity is still going at t = 1,000 ms, the circuit sustains
   itself. Also with 10 ORNs and with 1 ORN.
2. Very low input: DM1 ORNs at 1, 2 and 5 Hz.
3. Time course at 150 Hz: spikes per 50 ms, per brain area.
4. Lesion test at 20 Hz: silence (set the output to zero of) one group at a
   time and see whether the spread stops. Groups: the other ORNs, the
   Kenyon cells, the excitatory AL local neurons, the multiglomerular PNs,
   and all PNs except the DM1 ones.

Output: results/ignition_summary.csv, results/ignition_timecourse.csv
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
ht = lab.hemibrain_type
area = np.full(len(lab), "other", dtype=object)
area[(lab.cell_class == "ALPN").to_numpy()] = "PN"
area[(lab.cell_class == "ALLN").to_numpy()] = "AL local"
area[lab.cell_class.isin(["LHLN", "LHCENT"]).to_numpy()] = "lateral horn"
area[(lab.cell_class == "Kenyon_Cell").to_numpy()] = "Kenyon cell"
area[lab.cell_class.isin(["MBON", "DAN", "MBIN"]).to_numpy()] = "MBON/DAN/APL"
area[(lab.super_class == "descending").to_numpy()] = "descending"
area[ht.str.startswith("ORN_").to_numpy()] = "ORN (other)"
area[(ht == "ORN_DM1").to_numpy()] = "ORN_DM1 (driven)"
AREAS = ["ORN_DM1 (driven)", "ORN (other)", "PN", "AL local", "lateral horn", "Kenyon cell",
         "MBON/DAN/APL", "descending", "other"]

dm1 = lab.root_id[ht == "ORN_DM1"].tolist()
groups = {
    "other ORNs": lab.root_id[ht.str.startswith("ORN_") & (ht != "ORN_DM1")].tolist(),
    "Kenyon cells": lab.root_id[lab.cell_class == "Kenyon_Cell"].tolist(),
    "excitatory AL local neurons": lab.root_id[(lab.cell_class == "ALLN")
                                               & (lab.top_nt == "acetylcholine")].tolist(),
    "multiglomerular PNs": lab.root_id[(lab.cell_class == "ALPN")
                                       & (lab.cell_sub_class != "uniglomerular")].tolist(),
    "all PNs except DM1 PNs": lab.root_id[(lab.cell_class == "ALPN")
                                          & ~ht.str.startswith("DM1_")].tolist(),
}
rows, tc = [], []


def summarise(label, res, extra=None):
    r = res.rates_hz
    act = r > 0
    last = res.step >= int(900 / res.dt_ms)          # spikes in the last 100 ms
    row = dict(test=label, n_trials=res.n_trials, n_active=int(act.sum()),
               spikes_per_trial=len(res.step) / res.n_trials,
               n_firing_in_last_100ms=int(np.unique(res.neuron[last]).size),
               **{f"active_{a}": int((act & (area == a)).sum()) for a in AREAS})
    if extra:
        row.update(extra)
    rows.append(row)
    print({k: row[k] for k in ("test", "n_active", "n_firing_in_last_100ms")}, flush=True)
    pd.DataFrame(rows).to_csv(OUT / "ignition_summary.csv", index=False)


# 1. volleys
for n in (68, 10, 1):
    ids = dm1[:n]
    res = brain.run_with_input_events([(np.full(len(ids), 50), ids)], excite=ids, duration_ms=1000.0)
    summarise(f"volley: {n} DM1 ORNs fire once", res)
    if n == 68:
        b = res.step // int(50 / res.dt_ms)
        for a in AREAS:
            m = area[res.neuron] == a
            cnts = np.bincount(b[m], minlength=20)[:20]
            for k, c in enumerate(cnts):
                tc.append(dict(test="volley68", area=a, t_ms=50 * k, spikes=int(c)))
# 2. low rates
for rate in (1, 2, 5):
    summarise(f"DM1 ORNs at {rate} Hz", brain.run(excite=dm1, rate_hz=rate, n_trials=2, seed=0))
# 3. time course at 150 Hz
res = brain.run(excite=dm1, rate_hz=150, n_trials=1, seed=0)
summarise("DM1 ORNs at 150 Hz (time course)", res)
b = res.step // int(50 / res.dt_ms)
for a in AREAS:
    m = area[res.neuron] == a
    for k, c in enumerate(np.bincount(b[m], minlength=20)[:20]):
        tc.append(dict(test="150Hz", area=a, t_ms=50 * k, spikes=int(c)))
pd.DataFrame(tc).to_csv(OUT / "ignition_timecourse.csv", index=False)
# 4. lesions at 20 Hz
summarise("DM1 20 Hz, nothing silenced", brain.run(excite=dm1, rate_hz=20, n_trials=2, seed=0))
for name, ids in groups.items():
    res = brain.run(excite=dm1, rate_hz=20, silence=ids, n_trials=2, seed=0)
    summarise(f"DM1 20 Hz, silence {name}", res, dict(n_silenced=len(ids)))

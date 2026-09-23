"""Step 1 of Phase 8: are the two odors sensible before any learning?

For each model and input rate: what fraction of Kenyon cells fire (real
flies: roughly 5-10% per odor; UNVERIFIED figure from the research doc), how
much the KC sets of odor A and B overlap, how strongly the output neurons
(MBONs) and dopamine neurons (DANs) respond, and how long a trial takes.
Learning is OFF here.

Usage: python experiments/phase8/odor_check.py circuit 50 100 150
       python experiments/phase8/odor_check.py brain_alln 50 100
Output: results/odor_check_<model>.csv (one row per model x rate x odor x trial).
"""

import sys
import time

import numpy as np
import pandas as pd

from common import RES, get_model, odor_input_rows, type_rows

model = sys.argv[1]
rates = [float(r) for r in sys.argv[2:]] or [100.0]
N_TRIALS = 3
pb, lab, kind = get_model(model, dan_mode="modulatory")
odors = odor_input_rows(lab, kind)
kc = np.flatnonzero(lab.cell_class.to_numpy() == "Kenyon_Cell")
mbon = np.flatnonzero(lab.cell_class.to_numpy() == "MBON")
dan = np.flatnonzero(lab.cell_class.to_numpy() == "DAN")
pn = np.flatnonzero(lab.cell_class.to_numpy() == "ALPN")
m11 = type_rows(lab, "MBON11")
print(f"{model}: {len(lab)} neurons; odor rows A={odors['A'].size} B={odors['B'].size}", flush=True)
out = RES / f"odor_check_{model}.csv"
rows = []
for rate in rates:
    kc_sets = {}
    for od, r in odors.items():
        for t in range(N_TRIALS):
            t0 = time.perf_counter()
            res = pb.run([(r, rate, 0.0, 1000.0)], 1200.0, seed=1000 + t, plastic=False)
            wall = time.perf_counter() - t0
            kc_c = res.counts(kc, 0, 1100)
            kc_sets.setdefault(od, []).append(kc_c > 0)
            m_c = res.counts(mbon, 0, 1100)
            d_c = res.counts(dan, 0, 1100)
            tot = res.step.size
            late = int(((res.step >= 11000)).sum())      # spikes in the last 100 ms (after odor)
            rows.append(dict(model=model, rate=rate, odor=od, trial=t,
                             kc_frac=float((kc_c > 0).mean()), kc_spikes=int(kc_c.sum()),
                             kc_spikes_per_active=float(kc_c[kc_c > 0].mean()) if (kc_c > 0).any() else 0,
                             pn_active=int((res.counts(pn, 0, 1100) > 0).sum()),
                             mbon11_hz=float(res.counts(m11, 0, 1100).mean() / 1.1),
                             mbon_active=int((m_c > 0).sum()), mbon_spikes=int(m_c.sum()),
                             dan_active=int((d_c > 0).sum()), dan_spikes=int(d_c.sum()),
                             total_spikes=int(tot), spikes_after_odor=late,
                             touched=res.n_touched, wall_s=wall))
            print(rows[-1], flush=True)
    a = np.array(kc_sets["A"]).mean(0) > 0.5          # "reliable" responders
    b = np.array(kc_sets["B"]).mean(0) > 0.5
    print(f"rate {rate}: reliable KCs A={a.sum()} B={b.sum()} both={int((a & b).sum())}", flush=True)
    rows.append(dict(model=model, rate=rate, odor="overlap", trial=-1,
                     kc_frac=float((a & b).sum() / max(1, a.sum())),
                     kc_spikes=int((a & b).sum())))
    pd.DataFrame(rows).to_csv(out, index=False)
print("saved", out)

"""Phase 6 follow-up: which antennal-lobe local neurons (LNs) keep the
self-sustained smell activity going?

Plain English
-------------
In the real fly most antennal-lobe local neurons are inhibitory (GABA or
glutamate); a minority are excitatory (acetylcholine). In the model's
reference file, 144 of the 424 LNs are treated as excitatory, including 53
whose transmitter the machine-learning prediction called serotonin or
dopamine (unusual for LNs) and 21 predicted GABA that the reference file
nonetheless marks excitatory. We silence (zero the output of) these groups
and fire a 10-ORN DM1 volley, and ask whether activity still keeps itself
going for the full second.

Output: results/phase6_ignition_lesions.csv
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
dm1 = lab.root_id[lab.hemibrain_type == "ORN_DM1"].tolist()[:10]
ln = lab[lab.cell_class == "ALLN"]
groups = {
    "nothing": [],
    "LNs excitatory in the model (ref_sign +1), all": ln.root_id[ln.ref_sign > 0].tolist(),
    "LNs predicted serotonin/dopamine (treated excitatory)": ln.root_id[ln.top_nt.isin(["serotonin", "dopamine"])].tolist(),
    "LNs predicted GABA/glutamate but excitatory in the model": ln.root_id[ln.top_nt.isin(["gaba", "glutamate"]) & (ln.ref_sign > 0)].tolist(),
    "LNs predicted acetylcholine": ln.root_id[ln.top_nt == "acetylcholine"].tolist(),
    "all LNs": ln.root_id.tolist(),
}
rows = []
for name, sil in groups.items():
    res = brain.run_with_input_events([(np.full(len(dm1), 50), dm1)], excite=dm1,
                                      silence=sil, duration_ms=1000.0)
    row = dict(silenced=name, n_silenced=len(sil), n_active=int((res.rates_hz > 0).sum()),
               n_firing_in_last_100ms=int(np.unique(res.neuron[res.step >= 9000]).size))
    rows.append(row)
    pd.DataFrame(rows).to_csv(OUT / "phase6_ignition_lesions.csv", index=False)
    print(row, flush=True)

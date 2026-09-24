"""Step 0c: does the model's excite/inhibit sign follow FlyWire's transmitter
guess (top_nt) equally well in both snapshots?

Plain English: the model file of each snapshot gives every neuron one sign.
We cross-tabulate it against the machine transmitter guess in that snapshot's
annotation, for all neurons and for the antennal-lobe local neurons (ALLN).
Output: results/sign_vs_top_nt.csv (and printed).
"""

import gc

import numpy as np
import pandas as pd

import common783 as C
from sim import sign_fixes as S

rows = []
for snap in ("630", "783"):
    rid, pre, post, signed = S.load_reference_arrays(snap)
    sign = C.neuron_signs(rid.size, pre, signed)
    del pre, post, signed
    gc.collect()
    lab = C.labels(snap, rid)
    top = lab.top_nt.to_numpy()
    al = lab.cell_class.to_numpy() == "ALLN"
    for group, m in (("all", np.ones(rid.size, bool)), ("ALLN", al)):
        for nt in ("acetylcholine", "gaba", "glutamate", "dopamine", "serotonin", "octopamine", ""):
            k = m & (top == nt)
            rows.append(dict(snapshot=snap, group=group, top_nt=nt or "(none)", neurons=int(k.sum()),
                             model_plus=int((k & (sign == 1)).sum()),
                             model_minus=int((k & (sign == -1)).sum()),
                             model_zero=int((k & (sign == 0)).sum())))
df = pd.DataFrame(rows)
df.to_csv(C.RESULTS / "sign_vs_top_nt.csv", index=False)
print(df.to_string())

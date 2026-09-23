"""Is the recommended fix spike-for-spike identical to the baseline on the
Phase 3 taste experiments? (Not just the same MN9 rate: every spike of every
neuron at the same time step.)

Plain English: runs 10 trials of seed index 0 of each taste condition on the
baseline, keeps the spikes, frees that brain, builds the fixed brain, runs the
same trials and compares. Only one brain in memory at a time.
Output: results/identity_check.csv
"""

import gc
import sys

import numpy as np
import pandas as pd

import common as C
from sim import sign_fixes as S

FIX = sys.argv[1] if len(sys.argv) > 1 else "al_ln_literature"
TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]

rid = S.load_reference_arrays()[0]
lab = S.neuron_table(rid)
sets = C.input_sets(lab)


def spikes(fix):
    b = S.build_brain(fix, n_threads=2, lab=lab)
    out = {}
    for cond in TASTE:
        r = C.run_chunk(b, C.excite_for(cond, sets), C.CONDITIONS[cond][1], 0, 10)
        out[cond] = (r.trial.copy(), r.step.copy(), r.neuron.copy())
    del b
    gc.collect()
    return out


base = spikes("none")
fixed = spikes(FIX)
rows = []
for cond in TASTE:
    same = all(np.array_equal(a, b) for a, b in zip(base[cond], fixed[cond]))
    rows.append(dict(fix=FIX, condition=cond, trials=10, spikes_baseline=int(base[cond][1].size),
                     spikes_fixed=int(fixed[cond][1].size), identical=same))
    print(rows[-1], flush=True)
pd.DataFrame(rows).to_csv(C.RESULTS / f"identity_check_{FIX}.csv", index=False)

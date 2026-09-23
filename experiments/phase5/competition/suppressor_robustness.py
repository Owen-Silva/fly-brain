"""Phase 6 check for the suppressor result: does silencing CB0219 (left,
720575940624600840) still undo the bitter suppression when the synapse
strength w_syn is 20% weaker or 20% stronger?

Plain English
-------------
For w_syn at 80%, 100% and 120% of the paper's value we run (30 trials,
seeds 0-2): sugar 100 Hz alone, sugar 100 Hz + bitter 80 Hz, and the same
with CB0219-left silenced. Also silencing its right-side twin
(720575940620062288) and both together.

Output: results/suppressor_robustness.csv
"""

import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from phase5_common import get_brain, paper_ids, per_trial_rates  # noqa: E402

OUT = HERE / "results"
brain = get_brain(globals())
ids = paper_ids()
MN9 = brain.index_of([ids["MN9"]])
CB0219_L, CB0219_R = 720575940624600840, 720575940620062288
rows = []
for f in (0.8, 1.0, 1.2):
    for seed in (0, 1, 2):
        for bitter in (0, 80):
            for label, sil in (("none", []), ("CB0219 left", [CB0219_L]),
                               ("CB0219 right", [CB0219_R]), ("CB0219 both", [CB0219_L, CB0219_R])):
                if bitter == 0 and label != "none":
                    continue
                exc = {int(i): 100.0 for i in ids["SUGAR"]}
                if bitter:
                    exc.update({int(i): float(bitter) for i in ids["BITTER"]})
                res = brain.run(excite=exc, silence=sil, n_trials=30, seed=seed,
                                params={"w_syn": brain.params["w_syn"] * f})
                m = per_trial_rates(res, MN9)[:, 0]
                rows.append(dict(w_syn_factor=f, seed=seed, bitter_hz=bitter, silenced=label,
                                 mn9_mean=m.mean(), mn9_sd=m.std()))
                pd.DataFrame(rows).to_csv(OUT / "suppressor_robustness.csv", index=False)
                print(rows[-1], flush=True)

"""Step 1d (part 2): does the runaway keep itself going with NO input?

Plain English
-------------
(s1_duration.py looked for runaway trials in seed 0 only, and seed 0 had
none, so its persistence part ran only the healthy controls. This script
does the persistence test on the runaway trials of all seeds.)

For every runaway trial of sugar 200 + Ir94e 200 (6) and the first 3 of
Ir94e 200 alone, re-run it with exactly the same input, but switch the input
OFF at: onset + 20 ms (is it self-sustaining?), onset - 20 ms and onset - 50
ms (was it already locked in?). Simulate 2 s in total.

Output: results/persistence.csv (appended to the controls from s1_duration.py)
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
ids = common.paper_ids()
EX = {"sugar200_ir94e200": {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}},
      "ir94e200_alone": {i: 200.0 for i in ids["IR94E"]}}
rep = pd.read_csv(common.RESULTS / "reproduce_trials.csv")
known = pd.concat([rep[(rep.condition == "sugar200_ir94e200") & rep.runaway],
                   rep[(rep.condition == "ir94e200_alone") & rep.runaway].head(3)])
out = common.RESULTS / "persistence.csv"
rows = pd.read_csv(out).to_dict("records") if out.exists() else []


def run_cut(excite, seed, trial, cutoff_ms, total_ms=2000.0):
    (ev_ptr, ev_neuron), exc_idx, n1, p = common.make_input(brain, excite, seed, trial, 1000.0,
                                                            cutoff_ms=cutoff_ms)
    steps = np.repeat(np.arange(n1), np.diff(ev_ptr))
    n_steps = int(round(total_ms / p["dt"]))
    ev = brain._pack_events(steps, ev_neuron.astype(np.int64), n_steps)
    return brain._run_events([ev], exc_idx, (), n_steps, p, ())


for _, t in known.iterrows():
    for shift, label in ((20, "input off 20 ms AFTER onset"), (-20, "input off 20 ms BEFORE onset"),
                         (-50, "input off 50 ms BEFORE onset")):
        cut = float(t.onset_ms + shift)
        res = run_cut(EX[t.condition], int(t.seed), int(t.trial), cut)
        row, s1, d10 = common.trial_summary(res, brain, ids)
        rows.append(dict(test=label, condition=t.condition, seed=int(t.seed), trial=int(t.trial),
                         original_onset_ms=t.onset_ms, input_off_ms=cut, sim_ms=2000, **row,
                         spikes_last_100ms=int(s1[-100:].sum())))
        print({k: rows[-1][k] for k in ("test", "condition", "seed", "trial", "original_onset_ms",
                                         "runaway", "onset_ms", "distinct_last_100ms")}, flush=True)
        pd.DataFrame(rows).to_csv(out, index=False)
print("finished", flush=True)

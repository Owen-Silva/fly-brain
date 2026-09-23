"""Step 1d: does trial length matter, and does runaway keep itself going?

Plain English
-------------
(a) 3-second trials of sugar 200 + Ir94e 200 (30 trials, seed 20). If
    runaway is a random "tipping" event that can happen at any moment, longer
    trials should run away more often, and the start times should be spread
    over the whole trial.
(b) Take runaway trials from step 1a (seed 0) and switch the taste input OFF
    shortly after the runaway starts (onset + 20 ms), then keep simulating
    for 2 s in total. If the brain keeps firing with no input at all, the
    runaway is self-sustaining (a second stable state of the model).
(c) Switch the input off 20 ms and 50 ms BEFORE the onset: is the runaway
    already locked in, or does it need the last moments of input?
(d) Control: healthy trials with the input switched off at 500 ms should go
    silent.

Outputs: results/duration.csv, results/duration_series.npz,
         results/persistence.csv
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
both = {**{i: 200.0 for i in ids["SUGAR"]}, **{i: 200.0 for i in ids["IR94E"]}}

# (b)-(d) first (quick), then (a)
rep = pd.read_csv(common.RESULTS / "reproduce_trials.csv")
main0 = rep[(rep.condition == "sugar200_ir94e200") & (rep.seed == 0)]
run_tr = main0[main0.runaway].sort_values("onset_ms")
heal_tr = main0[~main0.runaway].head(3)


def run_cut(trial, cutoff_ms, total_ms=2000.0):
    """Trial `trial` of seed 0 with exactly its 1 s input, input stopped at
    cutoff_ms, simulated for total_ms."""
    (ev_ptr, ev_neuron), exc_idx, n1, p = common.make_input(brain, both, 0, trial, 1000.0,
                                                            cutoff_ms=cutoff_ms)
    steps = np.repeat(np.arange(n1), np.diff(ev_ptr))
    n_steps = int(round(total_ms / p["dt"]))
    ev = brain._pack_events(steps, ev_neuron.astype(np.int64), n_steps)
    return brain._run_events([ev], exc_idx, (), n_steps, p, ())


rows = []
pick = run_tr.iloc[np.linspace(0, len(run_tr) - 1, min(6, len(run_tr))).astype(int)]
for _, t in pick.iterrows():
    for shift, label in ((20, "input off 20 ms AFTER onset"), (-20, "input off 20 ms BEFORE onset"),
                         (-50, "input off 50 ms BEFORE onset")):
        cut = float(t.onset_ms + shift)
        if cut <= 0:
            continue
        res = run_cut(int(t.trial), cut)
        row, s1, d10 = common.trial_summary(res, brain, ids)
        rows.append(dict(test=label, trial=int(t.trial), original_onset_ms=t.onset_ms,
                         input_off_ms=cut, sim_ms=2000, **row,
                         spikes_last_100ms=int(s1[-100:].sum())))
        print(rows[-1], flush=True)
        pd.DataFrame(rows).to_csv(common.RESULTS / "persistence.csv", index=False)
for _, t in heal_tr.iterrows():
    res = run_cut(int(t.trial), 500.0, 1000.0)
    row, s1, d10 = common.trial_summary(res, brain, ids)
    rows.append(dict(test="healthy trial, input off at 500 ms", trial=int(t.trial),
                     original_onset_ms=np.nan, input_off_ms=500.0, sim_ms=1000, **row,
                     spikes_last_100ms=int(s1[-100:].sum())))
    print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(common.RESULTS / "persistence.csv", index=False)

conds = [dict(name="sugar200_ir94e200_3s", excite=both, seed=20, n_trials=30, duration_ms=3000.0)]
common.run_batch(brain, conds, "duration", ids)
print("finished", flush=True)

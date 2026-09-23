"""Step 2 bug check: do the Brian2 port and the fast engine agree on runaway?

Plain English
-------------
The Phase 3 Brian2 run saved every spike, including the spikes of the 39
stimulated taste neurons. A stimulated neuron fires on the time step right
after each random input "kick" (the kick is 68.75 mV, ten times what is
needed), so its spike times tell us exactly which kicks it got. We feed those
same kicks into the fast engine and check whether the same trials run away,
at the same moment, with the same neurons. If two independent programs agree
trial by trial, the runaway is a property of the model, not of either program.

Output: results/brian2_replay.csv (one row per trial, both engines side by side)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import RESULTS, ROOT, paper_ids, run_events, trial_summary, series  # noqa: E402

brain = globals().get("brain")
if brain is None:
    sys.path.insert(0, str(ROOT))
    from sim.fast_engine import FastBrain
    brain = FastBrain("630", n_threads=1)

ids = paper_ids()
stim = np.array(ids["SUGAR"] + ids["IR94E"], dtype=np.int64)
b2 = pd.read_parquet(ROOT / "experiments/phase3/results/v630/sugar200_ir94e200_spikes.parquet")
b2["step"] = np.round(b2.t.to_numpy() / 1e-4).astype(np.int64)
rows = []
for tr, g in b2.groupby("trial"):
    kicks = g[g.flywire_id.isin(stim)]
    ev_steps = kicks.step.to_numpy() - 1
    ev_ids = kicks.flywire_id.to_numpy(np.int64)
    res = run_events(brain, ev_steps, ev_ids, stim, duration_ms=1000.0)
    fast, _, _ = trial_summary(res, brain, ids)
    # Brian2 trial measured with the same yardstick
    idx = brain.index_of(g.flywire_id.to_numpy(np.int64))
    s1, d10 = series(g.step.to_numpy(), idx, 10000)
    b2_run = bool(d10.max() > 1500)
    b2_onset = float(np.flatnonzero(s1 > 200)[0]) if b2_run else np.nan
    # per-neuron spike counts, both engines
    cb = np.bincount(idx, minlength=brain.n_neurons)
    cf = np.bincount(res.neuron, minlength=brain.n_neurons)
    both = (cb > 0) | (cf > 0)
    r = float(np.corrcoef(cb[both], cf[both])[0, 1])
    stim_idx = brain.index_of(stim)
    stim_same = int((cb[stim_idx] == cf[stim_idx]).sum())
    # first 100 ms (before any runaway): exact spike-for-spike check
    early_b = set(zip(g.step[g.step < 1000], idx[g.step.to_numpy() < 1000]))
    m = res.step < 1000
    early_f = set(zip(res.step[m].tolist(), res.neuron[m].tolist()))
    rows.append(dict(
        trial=int(tr),
        brian2_total=int(len(g)), fast_total=fast["total_spikes"],
        brian2_runaway=b2_run, fast_runaway=fast["runaway"],
        brian2_onset_ms=b2_onset, fast_onset_ms=fast["onset_ms"],
        brian2_active=int((cb > 0).sum()), fast_active=fast["n_active"],
        brian2_mn9_hz=float(cb[brain.index_of([ids["MN9"]])[0]]), fast_mn9_hz=fast["mn9_hz"],
        per_neuron_r=round(r, 5),
        stim_neurons_same_count=f"{stim_same}/{stim.size}",
        first100ms_spikes_brian2=len(early_b), first100ms_spikes_fast=len(early_f),
        first100ms_identical=len(early_b ^ early_f) == 0,
        fast_wall_s=fast["wall_s"],
    ))
    print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(RESULTS / "brian2_replay.csv", index=False)

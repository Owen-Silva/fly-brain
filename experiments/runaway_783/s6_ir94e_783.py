"""Step 6: the taste-triggered runaway on 783, looked at more closely.

Plain English
-------------
With Ir94e taste input (200 Hz) the published model ran away in 10 of 90 trials
on 630 but only 4 of 90 on 783 (step 2), and the fix gave 0 of 90. With so few
events, 90 trials cannot tell "rarer" from "the same", nor show that the fix
removes it. Cheap follow-ups:
  A. 210 more trials (seeds 3-9) for the published 783 model AND the ported fix
     ("fix_rule"), so each has 300 trials in all;
  B. the published model of both snapshots with every synapse 5% and 10%
     stronger (seed 0, 30 trials): how close is each to the tipping point?
Output: results/ir94e_extra_trials.csv (resumable).
"""

import gc
import json

import numpy as np
import pandas as pd

import common783 as C

OUT = C.RESULTS
CSV = OUT / "ir94e_extra_trials.csv"
W0 = 0.275
P = C.paper_ids()
IR630 = [int(i) for i in P["IR94E"]]
# (snapshot, config, fix, synapse-strength factor, seed)
PLAN = ([("783", "published", "none", 1.0, s) for s in range(3, 10)]
        + [("783", "published", "none", f, 0) for f in (1.05, 1.1)]
        + [("783", "fix_rule", "al_ln_literature", 1.0, s) for s in range(3, 10)]
        + [("630", "published", "none", f, 0) for f in (1.05, 1.1)])


def main():
    sets = json.loads((OUT / "input_sets_783.json").read_text())
    done = set()
    if CSV.exists():
        d = pd.read_csv(CSV)
        done = set(zip(d.snapshot.astype(str), d.config, d.wsyn_factor, d.seed, d.trial))
    labs = {}
    for snap, cfg, fix in (("783", "published", "none"), ("783", "fix_rule", "al_ln_literature"),
                           ("630", "published", "none")):
        todo = [(f, s, a) for sn, c, _, f, s in PLAN if (sn, c) == (snap, cfg) for a in (0, 10, 20)
                if not all((snap, cfg, f, s, t) in done for t in range(a, a + 10))]
        if not todo:
            continue
        rid = pd.read_csv(C.ROOT / "data/reference" / ("Completeness_783.csv" if snap == "783" else
                                                       "2023_03_23_completeness_630_final.csv"),
                          index_col=0).index.to_numpy(np.int64)
        if snap not in labs:
            labs[snap] = C.labels(snap, rid)
        lab = labs[snap]
        C.wait_for_ram(1.5)
        brain = C.build(snap, fix, lab=lab, n_threads=2)
        rd = C.Readout(brain, lab)
        ex = {int(i): 200.0 for i in (sets["ir94e"] if snap == "783" else IR630)}
        for f, s, a in todo:
            C.wait_for_ram(1.0)
            res = C.run_chunk(brain, ex, s, a, a + 10, params={"w_syn": W0 * f})
            rows, _ = C.trial_rows(res, rd, dict(snapshot=snap, config=cfg, wsyn_factor=f,
                                                 condition="ir94e_200Hz", seed=s, trial0=a))
            C.append_csv(CSV, rows)
            d = pd.DataFrame(rows)
            print(f"  {snap} {cfg} w_syn x{f} seed {s} trials {a}-{a + 9}: runaway {int(d.runaway.sum())}/10, "
                  f"max distinct/10ms max {int(d.max_distinct_10ms.max())}", flush=True)
            del res
        del brain
        gc.collect()
    print("finished", flush=True)


if __name__ == "__main__":
    main()

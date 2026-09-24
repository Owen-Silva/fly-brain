"""Step 5: is the fix on 783 on a knife edge? Synapse strength -10% / +10% / +20%.

Plain English
-------------
Phase 7 checked that the fix still removes the runaway on 630 when every
synapse is made 10% weaker, or 10% or 20% stronger (1 seed x 30 trials). The
same check on 783, for the main version of the ported fix ("fix_rule") and,
for comparison, the published model at -10% (does a weaker brain still run
away?). Inputs: DM1 smell 150 Hz both sides, Ir94e 200 Hz, sugar 100 Hz.
Output: rows appended to results/wsyn_trials.csv (resumable).
"""

import gc

import json
import numpy as np
import pandas as pd

import common783 as C

OUT = C.RESULTS
CSV = OUT / "wsyn_trials.csv"
W0 = 0.275
PLAN = [("fix_rule", "al_ln_literature", f) for f in (0.9, 1.1, 1.2)] + [("published", "none", 0.9)]
CONDS = {"dm1_both_150Hz": ("dm1", 150.0, 0), "ir94e_200Hz": ("ir94e", 200.0, 0),
         "sugar_100Hz": ("sugar", 100.0, 1000)}


def main():
    sets = json.loads((OUT / "input_sets_783.json").read_text())
    rid = pd.read_csv(C.ROOT / "data/reference/Completeness_783.csv", index_col=0).index.to_numpy(np.int64)
    lab = C.labels("783", rid)
    done = set()
    if CSV.exists():
        d = pd.read_csv(CSV)
        done = set(zip(d.config, d.wsyn_factor, d.condition, d.trial))
    brains = {}
    for cfg, fix, f in PLAN:
        todo = [(c, a) for c in CONDS for a in (0, 10, 20)
                if not all((cfg, f, c, t) in done for t in range(a, a + 10))]
        if not todo:
            continue
        if cfg not in brains:
            brains.clear()
            gc.collect()
            C.wait_for_ram(1.5)
            brains[cfg] = C.build("783", fix, lab=lab, n_threads=2)
        brain = brains[cfg]
        rd = C.Readout(brain, lab)
        params = {"w_syn": W0 * f}
        for cond, a in todo:
            s_name, rate, seed = CONDS[cond]
            ex = {int(i): rate for i in sets[s_name]}
            C.wait_for_ram(1.0)
            res = C.run_chunk(brain, ex, seed, a, a + 10, params=params)
            rows, _ = C.trial_rows(res, rd, dict(config=cfg, wsyn_factor=f, condition=cond, seed=seed,
                                                 trial0=a))
            C.append_csv(CSV, rows)
            d = pd.DataFrame(rows)
            print(f"  {cfg} w_syn x{f} {cond} trials {a}-{a + 9}: runaway {int(d.runaway.sum())}/10, "
                  f"MN9 {d.mn9_hz.mean():.2f}, KC {d.kc_active.mean():.0f}", flush=True)
            del res
    print("finished", flush=True)


if __name__ == "__main__":
    main()

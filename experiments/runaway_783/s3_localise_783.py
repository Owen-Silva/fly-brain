"""Step 3 (optional task 5): repeat the Phase 6 localisation test on snapshot 783.

Plain English
-------------
On the published 783 model, silence a group of neurons (their outgoing
connections set to zero) and see whether the runaway still happens:
  * the 44 excitatory local neurons (eLNs; literature-typed, Shang et al. 2007);
  * three control groups of 44 random excitatory neurons OUTSIDE the antennal
    lobe that take part in the 783 runaway state (as Phase 6 did on 630);
  * all excitatory antennal-lobe local neurons of the 783 model (166), and one
    random control group of the same size.
Tests (as Phase 6 plus the Phase 7 smell test):
  * volley: 10 DM1 smell neurons fire once, nothing else (one trial);
  * DM1 smell 150 Hz both sides, 30 trials (seed 0).
  (Phase 6's third test, the Ir94e 200 Hz runaway rate, is dropped: the intact
  783 model ran away in only 4 of 90 Ir94e trials in step 2, too rare to test.)
"Take part in the runaway state" = fired in at least half of the published
model's DM1 runaway trials (from step 2's saved results).
Output: results/localise_trials.csv (one row per trial), results/localise_groups.json
"""

import gc
import json

import numpy as np
import pandas as pd

import common783 as C
from s2_runaway_783 import first10_dm1_630_in_783

OUT = C.RESULTS
CSV = OUT / "localise_trials.csv"
ACT = OUT / "active"


def core_neurons(n):
    """Fraction of the published model's DM1 runaway trials in which each
    neuron fired."""
    d = pd.read_csv(OUT / "trials.csv")
    d = d[(d.config == "published") & (d.condition == "dm1_both_150Hz")]
    tot = np.zeros(n)
    k = 0
    for (s, a), g in d.groupby(["seed_index", d.trial // 10 * 10]):
        z = np.load(ACT / f"published__dm1_both_150Hz__s{s}__{a}.npz")
        act = np.unpackbits(z["active"], axis=1, count=n).astype(bool)
        run = g.sort_values("trial").runaway.to_numpy()
        tot += act[run].sum(0)
        k += int(run.sum())
    return tot / max(k, 1), k


def main():
    sets = json.loads((OUT / "input_sets_783.json").read_text())
    rid = pd.read_csv(C.ROOT / "data/reference/Completeness_783.csv", index_col=0).index.to_numpy(np.int64)
    lab = C.labels("783", rid)
    C.wait_for_ram(1.5)
    brain = C.build("783", "none", lab=lab, n_threads=2)
    rd = C.Readout(brain, lab)
    from sim import sign_fixes as S
    _, pre, _, signed = S.load_reference_arrays("783")
    sign = C.neuron_signs(rid.size, pre, signed)
    del pre, signed
    gc.collect()
    cc = lab.cell_class.to_numpy()
    eln = C.eln_mask(lab)
    exc_ln = (cc == "ALLN") & (sign == 1)
    frac, n_run = core_neurons(rid.size)
    cand = np.flatnonzero((frac >= 0.5) & (sign == 1) & ~np.isin(cc, ["ALLN", "ALPN", "olfactory"]))
    groups = {"intact": np.zeros(0, np.int64), f"{int(eln.sum())} eLNs": rid[eln]}
    for k in range(3):
        groups[f"control {k + 1}: {int(eln.sum())} random excitatory runaway neurons outside AL"] = \
            rid[np.random.default_rng(100 + k).choice(cand, size=int(eln.sum()), replace=False)]
    groups[f"all {int(exc_ln.sum())} excitatory AL local neurons"] = rid[exc_ln]
    groups[f"control 4: {int(exc_ln.sum())} random excitatory runaway neurons outside AL"] = \
        rid[np.random.default_rng(200).choice(cand, size=int(exc_ln.sum()), replace=False)]
    (OUT / "localise_groups.json").write_text(json.dumps(
        dict(runaway_trials_used=n_run, core_neurons=int((frac >= 0.5).sum()),
             control_pool=int(cand.size), groups={g: [int(i) for i in v] for g, v in groups.items()}),
        indent=1))
    print(f"core (fired in >= half of {n_run} DM1 runaways): {int((frac >= 0.5).sum())} neurons; "
          f"control pool {cand.size}", flush=True)
    done = set()
    if CSV.exists():
        d = pd.read_csv(CSV)
        done = set(zip(d.test, d.group, d.seed_index))
    dm1_10 = first10_dm1_630_in_783()
    ir = {int(i): 200.0 for i in sets["ir94e"]}
    dm1 = {int(i): 150.0 for i in sets["dm1"]}
    plan = []
    for g in groups:
        plan.append(("volley: 10 DM1 smell neurons fire once", g, 0))
    # Phase 6 also used the Ir94e 200 Hz runaway rate. On 783 the intact model ran away in
    # only 4 of 90 Ir94e trials (step 2): too rare for a silencing test of practical size
    # (about 300 trials per group would be needed); dropped.
    for g in groups:
        if g != "intact":
            plan.append(("DM1 150 Hz both sides", g, 0))
    for test, g, s in plan:
        if (test, g, s) in done:
            continue
        sil = groups[g]
        meta = dict(test=test, group=g, n_silenced=len(sil), seed_index=s)
        if test.startswith("volley"):
            trig = np.setdiff1d(dm1_10, sil)
            rows, _ = C.trial_rows(C.run_volley(brain, trig, silence=sil), rd, meta)
        else:
            ex = ir if test.startswith("Ir94e") else dm1
            rows = []
            for a in range(0, 30, 10):
                C.wait_for_ram(1.0)
                r, _ = C.trial_rows(C.run_chunk(brain, ex, s, a, a + 10, silence=sil), rd,
                                    dict(meta, trial0=a))
                rows += r
        C.append_csv(CSV, rows)
        d = pd.DataFrame(rows)
        print(f"  {test} | {g} | seed {s}: runaway {int(d.runaway.sum())}/{len(d)}, median spikes "
              f"{int(d.total_spikes.median()):,}", flush=True)
    print("finished", flush=True)


if __name__ == "__main__":
    main()

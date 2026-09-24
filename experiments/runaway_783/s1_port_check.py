"""Step 1: PROVE the port before using it.

Plain English
-------------
Our re-implementation of the fix (common783.fix_al_ln_literature) is applied
to snapshot 630 and compared with the project's own
``sim/sign_fixes.build_brain(fix="al_ln_literature")``:
  A. the fixed connection lists (who connects to whom, with what signed
     synapse count) must be identical, element by element;
  B. the two built brains must hold identical internal arrays;
  C. the same seed must give the same spikes (every spike, every time step):
     10 trials each of DM1 smell 150 Hz, Ir94e 200 Hz and sugar 100 Hz;
  D. those trials must match the saved Phase 7 results (trials.csv) too.
Then two 783 checks:
  E. our "published" 783 brain (built from arrays) equals FastBrain("783");
  F. the "same cells" variant touches exactly the intended cells.
Output: results/port_check.txt
"""

import gc

import numpy as np
import pandas as pd

import common783 as C
from sim import sign_fixes as S
from sim.fast_engine import FastBrain

lines = []


def say(s):
    print(s, flush=True)
    lines.append(s)


def internals(b):
    return b._indptr.copy(), b._post.copy(), b._count.copy()


C.wait_for_ram(1.5)
rid, pre, post, signed = S.load_reference_arrays("630")
lab = S.neuron_table(rid)
# A. connection lists
p1, q1, s1, rep = S.apply_fix("al_ln_literature", rid, pre, post, signed, lab)
p2, q2, s2, info = C.fix_al_ln_literature(pre, post, signed, lab.cell_class.to_numpy() == "ALLN",
                                          lab.known_sign.to_numpy())
same = all(np.array_equal(a, b) for a, b in ((p1, p2), (q1, q2), (s1, s2)))
say(f"A. 630 connection lists identical (pre, post, signed count): {same}; "
    f"{p1.size:,} vs {p2.size:,} connections")
say(f"   sim/sign_fixes report: {rep.summary()}")
say(f"   port: removed {info['removed_connections']:,} connections ({info['removed_synapses']:,} synapses), "
    f"{info['to_inhibitory']} made inhibitory ({info['flipped_connections']:,} connections, "
    f"{info['flipped_synapses']:,} synapses), {info['excitatory_lns']} excitatory LNs limited")
same_cells = (sorted(rid[np.r_[info['to_inh_idx'], info['exc_ln_idx']]].tolist())
              == sorted(rep.target_neurons))
say(f"   same target cells ({len(rep.target_neurons)}): {same_cells}")
del p1, q1, s1, p2, q2, s2, pre, post, signed
gc.collect()

# B. brains
b1 = S.build_brain("al_ln_literature", lab=lab, n_threads=2)
b2 = C.build("630", "al_ln_literature", lab=lab)
i1, i2 = internals(b1), internals(b2)
same_b = all(np.array_equal(a, b) for a, b in zip(i1, i2))
say(f"B. built brains identical (row pointers, targets, signed counts): {same_b}")
del i1, i2
gc.collect()

# C. spikes
P = C.paper_ids()
dm1 = lab.root_id.to_numpy()[lab.hemibrain_type.to_numpy() == "ORN_DM1"]
conds = {"dm1_both_150Hz": ({int(i): 150.0 for i in dm1}, 0),
         "ir94e_200Hz": ({int(i): 200.0 for i in P["IR94E"]}, 0),
         "sugar_100Hz": ({int(i): 100.0 for i in P["SUGAR"]}, 1000)}
saved = pd.read_csv(C.ROOT / "experiments" / "phase7_signs" / "results" / "trials.csv",
                    usecols=["config", "condition", "seed_index", "trial", "total_spikes", "runaway"])
all_same = True
for cond, (ex, seed) in conds.items():
    r1 = C.run_chunk(b1, ex, seed, 0, 10)
    r2 = C.run_chunk(b2, ex, seed, 0, 10)
    eq = all(np.array_equal(getattr(r1, k), getattr(r2, k)) for k in ("trial", "step", "neuron"))
    all_same &= eq
    per_trial = np.bincount(r2.trial, minlength=10)
    sv = saved[(saved.config == "al_ln_literature") & (saved.condition == cond)
               & (saved.seed_index == 0) & (saved.trial < 10)].sort_values("trial")
    match_saved = sv.total_spikes.to_numpy().tolist() == per_trial.tolist()
    say(f"C/D. {cond} seed {seed}, 10 trials: spikes identical = {eq} ({r1.step.size:,} vs "
        f"{r2.step.size:,} spikes); per-trial totals equal the saved Phase 7 run = {match_saved}")
    del r1, r2
    gc.collect()
del b1, b2
gc.collect()

# E. published 783 via arrays == FastBrain("783")
C.wait_for_ram(1.5)
b3 = FastBrain("783", n_threads=2)
i3 = internals(b3)
del b3
gc.collect()
b4 = C.build("783", "none")
same_783 = all(np.array_equal(a, b) for a, b in zip(i3, internals(b4)))
say(f"E. published 783 built from arrays identical to FastBrain('783'): {same_783}")
del b4, i3
gc.collect()

# F. same-cells variant
rid783, pre, post, signed = S.load_reference_arrays("783")
target, ks = C.same_cells_masks(rid783)
_, _, _, inf = C.fix_al_ln_literature(pre, post, signed, target, ks)
say(f"F. 783 'same cells' variant: {int(target.sum())} target cells found; {inf['to_inhibitory']} made "
    f"inhibitory, {inf['excitatory_lns']} excitatory LNs limited; removed "
    f"{inf['removed_connections']:,} connections ({inf['removed_synapses']:,} synapses); flipped "
    f"{inf['flipped_connections']:,} connections")
lab783 = C.labels("783", rid783)
_, _, _, inr = C.fix_al_ln_literature(pre, post, signed, lab783.cell_class.to_numpy() == "ALLN",
                                      lab783.known_sign.to_numpy())
say(f"   783 rule-based port: {inr['to_inhibitory']} made inhibitory, {inr['excitatory_lns']} limited; removed "
    f"{inr['removed_connections']:,} connections ({inr['removed_synapses']:,} synapses); flipped "
    f"{inr['flipped_connections']:,} connections ({inr['flipped_synapses']:,} synapses)")
say(f"ALL 630 CHECKS PASS: {same and same_cells and same_b and all_same}")
(C.RESULTS / "port_check.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

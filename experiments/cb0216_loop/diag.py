"""Step 2c (PRELIMINARY): why does CB0216 hold its activity when other strong
reciprocal pairs (LT1a<->LT1b, CB0756<->CB0756, 180-270 synapses each way) do not?

For the CB0216 pair and the strongest pairs that failed R3:
  1. the pair ALONE (a 2-neuron network with only its mutual synapses): one kick
     to one member, 1 s; does it hold?
  2. in the whole default brain: one kick to one member; who else fires in the
     next 100 ms, and how many inhibitory synapses do those cells send back onto
     the pair (feedback inhibition)?
Writes results/diag_pairs.csv.
"""
import numpy as np
import pandas as pd

import lib_cb as C

root_ids, pre, post, signed, lab = C.arrays()
n = len(root_ids)
cand = pd.read_csv(C.RESULTS / "loop_candidates.csv")
pairs = cand[cand.kind == "pair"].head(5)          # CB0216 + the next four by weakest link
brain = C.brain_from(root_ids, pre, post, signed)
rows = []
for _, c in pairs.iterrows():
    a, b = (int(x) for x in c.members.split())
    wab = int(signed[(pre == a) & (post == b)].sum())
    wba = int(signed[(pre == b) & (post == a)].sum())
    # 1. isolated pair
    iso = C.FastBrain.from_arrays(root_ids[[a, b]], np.array([0, 1]), np.array([1, 0]),
                                  np.array([wab, wba]), n_threads=1)
    ev = C.FastBrain._pack_events(np.array([100]), np.array([0]), 10100)
    st, nr, _ = C.run_onoff(iso, np.zeros(0, np.int64), None, 10.0, 1000.0, 0, events=ev)
    iso_hz = C.pair_rates(st, nr, [0, 1], 510, 1010)
    # 2. whole brain, one kick to member a
    ev = C.FastBrain._pack_events(np.array([100]), np.array([a]), 10100)
    st, nr, _ = C.run_onoff(brain, np.zeros(0, np.int64), None, 10.0, 1000.0, 0, events=ev)
    brain_hz = C.pair_rates(st, nr, [a, b], 510, 1010)
    early = C.window_counts(st, nr, n, 10, 110)
    early[[a, b]] = 0
    fired = np.flatnonzero(early)
    m_back = np.isin(pre, fired) & np.isin(post, [a, b]) & (signed < 0)
    inh_back = int(-signed[m_back].sum())
    m_exc_back = np.isin(pre, fired) & np.isin(post, [a, b]) & (signed > 0)
    top = pd.Series(early[fired], index=fired).sort_values(ascending=False).head(4)
    rows.append(dict(names=c.names, w_ab=wab, w_ba=wba, alone_hz=" ".join(f"{x:.0f}" for x in iso_hz),
                     whole_brain_hz=" ".join(f"{x:.0f}" for x in brain_hz),
                     member_spikes_first100ms=int(((nr == a) | (nr == b))[(st >= 100) & (st < 1100)].sum()),
                     n_other_cells_fired_first100ms=int(fired.size),
                     inh_synapses_back_from_them=inh_back,
                     exc_synapses_back_from_them=int(signed[m_exc_back].sum()),
                     top_other_cells=", ".join(f"{lab.cell_type[i] or '?'}({lab.top_nt[i][:4]}):{int(k)}"
                                               for i, k in top.items())))
    print(rows[-1], flush=True)
    del iso
pd.DataFrame(rows).to_csv(C.RESULTS / "diag_pairs.csv", index=False)
print("wrote results/diag_pairs.csv")

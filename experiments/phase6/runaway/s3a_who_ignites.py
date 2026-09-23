"""Step 3a: which neurons ignite first, and which loop keeps it going?

Plain English
-------------
Uses the 150 trials of sugar 200 + Ir94e 200 from step 1a.
1. "Recruited" neurons: fire in a runaway trial but in fewer than 5% of the
   healthy trials. For each one we take the time of its first spike relative
   to the runaway onset. Neurons that are recruited early in (almost) every
   runaway trial are the ignition point.
2. The runaway state itself: which neurons fire, how fast, by cell class and
   transmitter.
3. Same state as the olfaction lane's "ignition"? Overlap with the neurons
   active when the DM1 smell neurons are driven (read-only from Phase 5).
4. The loop: among neurons that fire fast in every runaway, which excitatory
   connections are strong enough that ONE spike of the sender alone can push
   the receiver over threshold (about 162+ synapses), and do those form
   closed loops (a signal that goes round and round)?

Outputs: results/onset_ranking.csv, results/runaway_state_by_class.csv,
         results/core_neurons.csv, results/loops.txt
"""
import importlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402
importlib.reload(common)

brain = common.get_brain(globals())
R = common.RESULTS
lab = common.labels(brain)
n = brain.n_neurons
rep = pd.read_csv(R / "reproduce_trials.csv")
main = rep[rep.condition == "sugar200_ir94e200"].reset_index(drop=True)
st = np.load(R / "main_neuron_stats.npz")
run_t = main[main.runaway]
heal_t = main[~main.runaway]
print(f"runaway trials: {len(run_t)}, healthy: {len(heal_t)}", flush=True)

# healthy firing frequency per neuron
f_h = np.zeros(n)
for _, t in heal_t.iterrows():
    f_h[st[f"{t.seed}_{t.trial}_idx"]] += 1
f_h /= max(len(heal_t), 1)

# ---- 1. onset ranking ---------------------------------------------------------
rel = np.full((len(run_t), n), np.nan)       # first spike minus onset, ms
rate_ign = np.zeros((len(run_t), n))          # rate after onset + 50 ms
for j, (_, t) in enumerate(run_t.iterrows()):
    idx, cnt, first = (st[f"{t.seed}_{t.trial}_{k}"] for k in ("idx", "cnt", "first"))
    rec = f_h[idx] < 0.05
    rel[j, idx[rec]] = first[rec] * 0.1 - t.onset_ms
    # rate in the runaway part (approximation: all spikes / time after onset)
    rate_ign[j, idx] = cnt / max((1000.0 - t.onset_ms) / 1000.0, 0.05)
n_rec = np.sum(~np.isnan(rel), axis=0)
with np.errstate(all="ignore"):
    import warnings
    warnings.simplefilter("ignore", RuntimeWarning)
    med_rel = np.nanmedian(rel, axis=0)   # over the runaway trials where it was recruited
cols = ["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type", "hemibrain_type",
        "side", "top_nt", "sign"]
rank = lab[cols].copy()
rank["n_runaway_trials_recruited"] = n_rec
rank["frac_recruited"] = n_rec / max(len(run_t), 1)
rank["median_first_spike_rel_onset_ms"] = med_rel
rank["healthy_frac"] = f_h
rank["mean_rate_in_runaway_hz"] = rate_ign.mean(axis=0) if len(run_t) else 0
rank = rank[rank.frac_recruited >= 0.5].sort_values("median_first_spike_rel_onset_ms")
rank.to_csv(R / "onset_ranking.csv", index=False)
print("\nEarliest recruited neurons (recruited in >=50% of runaways):")
print(rank.head(40)[["root_id", "super_class", "cell_class", "cell_type", "hemibrain_type", "side",
                     "top_nt", "frac_recruited", "median_first_spike_rel_onset_ms"]].to_string(index=False))
early = rank[rank.median_first_spike_rel_onset_ms <= 5]
print(f"\n{len(early)} neurons recruited by onset+5 ms; by cell_class:")
print(early.groupby(["super_class", "cell_class"]).size().sort_values(ascending=False).head(15).to_string())
print("by hemibrain_type:", early.hemibrain_type.value_counts().head(15).to_dict())

# per-trial: class of the first 30 recruited neurons
fc = []
for j in range(len(run_t)):
    r = rel[j]
    order = np.argsort(np.where(np.isnan(r), np.inf, r))[:30]
    fc.append(lab.cell_class.to_numpy()[order])
fc = pd.Series(np.concatenate(fc)).value_counts() if fc else pd.Series(dtype=int)
print("\nClass of the first 30 recruited neurons, pooled over runaway trials:", fc.head(12).to_dict())

# ---- 2. runaway state composition -----------------------------------------------
if len(run_t):
    core_mask = (np.mean(rate_ign > 20, axis=0) >= 0.8)
    act_mask = np.mean(rate_ign > 0, axis=0) >= 0.5
    lab2 = lab.assign(rate=rate_ign.mean(axis=0), core=core_mask, active=act_mask)
    byc = lab2[lab2.active].groupby(["super_class", "cell_class", "top_nt"]).agg(
        n_neurons=("rate", "size"), n_core=("core", "sum"), mean_rate_hz=("rate", "mean")
    ).sort_values("n_neurons", ascending=False).reset_index()
    byc.to_csv(R / "runaway_state_by_class.csv", index=False)
    print(f"\nRunaway state: {act_mask.sum()} neurons fire in >=50% of runaways; "
          f"{core_mask.sum()} fire >20 Hz in >=80% (the 'core').")
    print(byc.head(20).to_string(index=False))
    print("transmitter of active neurons:", lab2[lab2.active].top_nt.value_counts().to_dict())
    print("model sign of active neurons:", lab2[lab2.active].sign.value_counts().to_dict())
    print("mean rate by sign (Hz):", lab2[lab2.active].groupby("sign").rate.mean().round(1).to_dict())

    # ---- 3. overlap with the olfaction lane's ignition ------------------------
    olf_p = common.ROOT / "experiments/phase5/unexplored/results/olf_DM1_both_10Hz_seed0_t5_rates.npy"
    if olf_p.exists():
        olf = np.load(olf_p) > 0
        ours = act_mask
        jac = (olf & ours).sum() / (olf | ours).sum()
        print(f"\nOverlap with Phase 5 olfactory ignition (DM1 10 Hz): ours {ours.sum()}, "
              f"theirs {olf.sum()}, shared {(olf & ours).sum()}, Jaccard {jac:.3f}")
        # compare with our healthy-set removed
        hs = f_h > 0.05
        print(f"  excluding neurons active in healthy trials: shared "
              f"{(olf & ours & ~hs).sum()} of ours {(ours & ~hs).sum()}")

    # ---- 4. loops of single-spike-strong excitatory connections ---------------
    p = brain.params
    tm, tau = p["t_mbr"], p["tau"]
    tpk = np.log(tm / tau) * tau * tm / (tm - tau)
    peak_per_syn = p["w_syn"] * tau / (tm - tau) * (np.exp(-tpk / tm) - np.exp(-tpk / tau))
    need = int(np.ceil((p["v_th"] - p["v_0"]) / peak_per_syn))
    pre = np.repeat(np.arange(n), np.diff(brain._indptr))
    post = brain._post.astype(np.int64)
    cnt = brain._count.astype(np.int64)
    lines = [f"Peak voltage bump from ONE spike per synapse: {peak_per_syn:.4f} mV; "
             f"a lone spike fires its target if it has >= {need} synapses onto it "
             f"(threshold is {p['v_th'] - p['v_0']:.0f} mV above rest)."]
    for label, mask in (("whole brain", np.ones(n, bool)), ("runaway core", core_mask),
                        ("runaway active set", act_mask)):
        for thr in (need, need // 2, need // 4):
            m = (cnt >= thr) & mask[pre] & mask[post]
            G = sp.csr_matrix((np.ones(m.sum()), (pre[m], post[m])), shape=(n, n))
            nc, labs_ = connected_components(G, directed=True, connection="strong")
            sizes = np.bincount(labs_)
            big = np.flatnonzero(sizes > 1)
            members = np.flatnonzero(np.isin(labs_, big))
            lines.append(f"{label}: excitatory edges with >= {thr} synapses: {int(m.sum())}; "
                         f"closed loops (strongly connected groups >1 neuron): {big.size}, "
                         f"neurons in them: {members.size}; largest {sizes.max() if sizes.size else 0}")
            if members.size and label != "whole brain":
                comp = lab.iloc[members].groupby(["cell_class", "hemibrain_type"]).size() \
                    .sort_values(ascending=False).head(12)
                lines.append("    members by class/type: " + "; ".join(
                    f"{a}/{b}: {c}" for (a, b), c in comp.items()))
            if label == "runaway core" and thr == need // 4 and members.size:
                keep = lab.iloc[members][cols].assign(loop_group=labs_[members],
                                                      rate_in_runaway_hz=rate_ign.mean(0)[members])
                keep.to_csv(R / "core_loop_members.csv", index=False)
    (R / "loops.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n" + "\n".join(lines))
    lab2[lab2.core][cols + ["rate"]].sort_values("rate", ascending=False) \
        .to_csv(R / "core_neurons.csv", index=False)
print("finished", flush=True)

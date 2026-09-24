"""Step 4: tables, the comparison with snapshot 630, and the figure.

Plain English
-------------
Reads the saved trials (this lane's 783 runs and the Phase 7 630 runs, same
seeds and same runaway rule) and writes:
  results/table_runaway.csv    runaway counts per snapshot / version / input
  results/table_taste.csv      sugar 100 Hz -> MN9, and whether the fix changed it
  results/table_volleys.csv    one-off volleys, 783 next to 630
  results/table_localise.csv   the silencing test on 783 (if step 3 ran)
  results/state_overlap.csv    is the 783 runaway the same set of neurons as 630's?
  results/summary_stats.txt    every number quoted in docs/runaway-783.md
  plots/fig_runaway_783.png
"""

import json

import matplotlib
import numpy as np
import pandas as pd
from scipy import stats

import common783 as C

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

R = C.RESULTS
P7 = C.ROOT / "experiments" / "phase7_signs" / "results"
INK, MUTED, GRID = "#1f1f1e", "#6b6a64", "#e6e5e0"
COLOR = {"published": "#2a78d6", "fix_rule": "#eb6834", "fix_same_cells": "#1baf7a"}
NAME = {"published": "published model", "fix_rule": "fix (rule on own labels)",
        "fix_same_cells": "fix (same 150 cells as 630)"}
MAP630 = {"none": "published", "al_ln_literature": "fix_rule"}
lines = []


def say(s=""):
    print(s, flush=True)
    lines.append(s)


def ci(k, n):
    lo, hi = stats.binomtest(int(k), int(n)).proportion_ci(0.95)
    return f"{100 * lo:.1f}-{100 * hi:.1f}%"


def fisher(k1, n1, k2, n2):
    return float(f"{stats.fisher_exact([[k1, n1 - k1], [k2, n2 - k2]])[1]:.2g}")


# ---- data -------------------------------------------------------------------
T = pd.read_csv(R / "trials.csv")
T["snapshot"] = "783"
t6 = pd.read_csv(P7 / "trials.csv")
t6 = t6[t6.config.isin(MAP630)].copy()
t6["config"] = t6.config.map(MAP630)
t6["snapshot"] = "630"
rid783 = pd.read_csv(C.ROOT / "data/reference/Completeness_783.csv", index_col=0).index.to_numpy(np.int64)
lab783 = C.labels("783", rid783)
N_KC = {"630": 5177, "783": int((lab783.cell_class.to_numpy() == "Kenyon_Cell").sum())}
cols = ["snapshot", "config", "condition", "seed_index", "trial", "total_spikes", "n_active",
        "max_distinct_10ms", "runaway", "distinct_last_100ms", "mn9_hz", "kc_active"]
A = pd.concat([T[cols + ["onset_ms"]], t6[cols]], ignore_index=True)
say(f"Kenyon cells: 630 {N_KC['630']}, 783 {N_KC['783']}")

# ---- runaway table ------------------------------------------------------------
rows = []
conds = [c for c in ["dm1_both_150Hz", "ir94e_200Hz", "dm1_left_150Hz", "dm1_right_150Hz", "sugar_100Hz"]
         if c in set(T.condition)]
for cond in conds:
    for snap in ("630", "783"):
        pub = A[(A.snapshot == snap) & (A.config == "published") & (A.condition == cond)]
        for cfg in ("published", "fix_rule", "fix_same_cells"):
            d = A[(A.snapshot == snap) & (A.config == cfg) & (A.condition == cond)]
            if d.empty:
                continue
            k, n = int(d.runaway.sum()), len(d)
            other = A[(A.snapshot != snap) & (A.config == cfg) & (A.condition == cond)]
            row = dict(condition=cond, snapshot=snap, config=cfg, trials=n, runaway=k,
                       per_seed="/".join(str(int(v)) for v in d.groupby("seed_index").runaway.sum()),
                       rate_pct=round(100 * k / n, 1), ci95=ci(k, n),
                       p_vs_published_same_snapshot=(fisher(k, n, int(pub.runaway.sum()), len(pub))
                                                     if cfg != "published" and len(pub) else np.nan),
                       p_vs_other_snapshot=(fisher(k, n, int(other.runaway.sum()), len(other))
                                            if len(other) else np.nan),
                       median_spikes=int(d.total_spikes.median()),
                       median_active=int(d.n_active.median()),
                       max_distinct_10ms_median=int(d.max_distinct_10ms.median()),
                       max_distinct_10ms_healthy_max=int(d[~d.runaway].max_distinct_10ms.max())
                       if (~d.runaway).any() else np.nan,
                       max_distinct_10ms_runaway_min=int(d[d.runaway].max_distinct_10ms.min())
                       if d.runaway.any() else np.nan,
                       still_firing_last_100ms_median=int(d.distinct_last_100ms.median()),
                       kc_pct_per_trial=round(100 * d.kc_active.mean() / N_KC[snap], 2))
            if "onset_ms" in d and d.runaway.any() and d.onset_ms.notna().any():
                on = d[d.runaway].onset_ms
                row["onset_ms_median"] = float(on.median())
            rows.append(row)
RW = pd.DataFrame(rows)
RW.to_csv(R / "table_runaway.csv", index=False)
say("\nRUNAWAY (more than 1,500 different neurons firing in some 10 ms slice)")
for _, r in RW[RW.condition != "sugar_100Hz"].iterrows():
    say(f"  {r.condition:16s} {r.snapshot} {r.config:15s} {r.runaway:3d}/{r.trials} ({r.per_seed}) "
        f"{r.rate_pct:5.1f}% [{r.ci95}] p_vs_pub={r.p_vs_published_same_snapshot} "
        f"p_vs_other_snap={r.p_vs_other_snapshot}; median spikes {r.median_spikes:,}, active "
        f"{r.median_active:,}, still firing at end {r.still_firing_last_100ms_median:,}, "
        f"KC {r.kc_pct_per_trial}%/trial, healthy max {r.max_distinct_10ms_healthy_max}, runaway min "
        f"{r.max_distinct_10ms_runaway_min}, onset median {r.get('onset_ms_median', np.nan)} ms")
h = T[~T.runaway].max_distinct_10ms
w = T[T.runaway].max_distinct_10ms
say(f"  783, all trials: healthy trials top out at {int(h.max()) if len(h) else 'n/a'} distinct neurons "
    f"per 10 ms; runaways never drop below {int(w.min()) if len(w) else 'n/a'} "
    f"({len(h)} healthy, {len(w)} runaway trials)")

# ---- taste --------------------------------------------------------------------
rows = []
for snap in ("630", "783"):
    base = A[(A.snapshot == snap) & (A.config == "published") & (A.condition == "sugar_100Hz")]
    base = base.sort_values(["seed_index", "trial"])
    for cfg in ("published", "fix_rule", "fix_same_cells"):
        d = A[(A.snapshot == snap) & (A.config == cfg) & (A.condition == "sugar_100Hz")]
        if d.empty:
            continue
        d = d.sort_values(["seed_index", "trial"])
        same = bool(len(d) == len(base) and np.array_equal(d.total_spikes.to_numpy(), base.total_spikes.to_numpy())
                    and np.array_equal(d.mn9_hz.to_numpy(), base.mn9_hz.to_numpy()))
        rows.append(dict(snapshot=snap, config=cfg, trials=len(d), mn9_hz=round(d.mn9_hz.mean(), 2),
                         mn9_sd=round(d.mn9_hz.std(ddof=0), 2),
                         seed_means="/".join(f"{v:.2f}" for v in d.groupby("seed_index").mn9_hz.mean()),
                         change_vs_published=round(d.mn9_hz.mean() - base.mn9_hz.mean(), 3),
                         every_trial_same_totals_and_mn9=same, runaway=int(d.runaway.sum())))
TT = pd.DataFrame(rows)
spk = {}
for cfg in ("published", "fix_rule", "fix_same_cells"):
    f = R / "spikes" / f"{cfg}__sugar_100Hz__s0__0.npz"
    if f.exists():
        z = np.load(f)
        spk[cfg] = (z["trial"], z["step"], z["neuron"])
TT["spike_for_spike_first_10_trials"] = [
    (all(np.array_equal(a, b) for a, b in zip(spk[r.config], spk["published"]))
     if r.snapshot == "783" and r.config in spk and "published" in spk else np.nan)
    for _, r in TT.iterrows()]
TT.to_csv(R / "table_taste.csv", index=False)
say("\nSUGAR 100 Hz -> MN9 (spikes/s; 3 seeds x 30 trials)")
for _, r in TT.iterrows():
    say(f"  {r.snapshot} {r.config:15s} MN9 {r.mn9_hz:.2f} (sd {r.mn9_sd}; seeds {r.seed_means}); change "
        f"{r.change_vs_published:+.3f}; every trial same = {r.every_trial_same_totals_and_mn9}; "
        f"spike-for-spike (10 trials) = {r.spike_for_spike_first_10_trials}; runaway {r.runaway}")

# ---- volleys ------------------------------------------------------------------
if (R / "volleys.csv").exists():
    V = pd.read_csv(R / "volleys.csv")
    V["snapshot"] = "783"
    v6 = pd.read_csv(P7 / "volleys.csv")
    v6 = v6[v6.config.isin(MAP630)].copy()
    v6["config"] = v6.config.map(MAP630)
    v6["snapshot"] = "630"
    v6["trigger"] = v6.trigger.replace({"10 DM1 ORNs fire once": "10 DM1 smell neurons fire once",
                                         "all 685 AL projection neurons fire once":
                                             "all antennal-lobe projection neurons fire once"})
    VV = pd.concat([V, v6], ignore_index=True)[["snapshot", "config", "trigger", "total_spikes", "n_active",
                                                "max_distinct_10ms", "runaway", "distinct_last_100ms"]]
    VV.sort_values(["trigger", "config", "snapshot"]).to_csv(R / "table_volleys.csv", index=False)
    say("\nVOLLEYS (a group fires once at 5 ms, nothing else; 1 s)")
    for _, r in VV.sort_values(["trigger", "config", "snapshot"]).iterrows():
        say(f"  {r.trigger:48s} {r.snapshot} {r.config:15s} {r.total_spikes:>9,} spikes, runaway "
            f"{r.runaway}, still firing at end {r.distinct_last_100ms}")

# ---- is it the same state? ---------------------------------------------------------
a630 = pd.read_csv(C.ANN_630, sep="\t", usecols=["supervoxel_id", "root_id"],
                   dtype={"root_id": "int64", "supervoxel_id": "int64"}).drop_duplicates("root_id")
a783 = pd.read_csv(C.ANN_783, sep="\t", usecols=["supervoxel_id", "root_id"],
                   dtype={"root_id": "int64", "supervoxel_id": "int64"}).drop_duplicates("supervoxel_id")
mp = a630.merge(a783, on="supervoxel_id", suffixes=("_630", "_783"))
m630 = dict(zip(mp.root_id_630, mp.root_id_783))
rid630 = pd.read_csv(C.ROOT / "data/reference/2023_03_23_completeness_630_final.csv",
                     index_col=0).index.to_numpy(np.int64)
set783 = set(rid783.tolist())


def to783(ids630):
    out = []
    for i in ids630:
        j = m630.get(int(i), int(i))
        if j in set783:
            out.append(j)
    return set(out)


rows = []
n = rid783.size
act_any = np.zeros(n, bool)
frac = np.zeros(n)
k_run = 0
for s in (0, 1, 2):
    for a in (0, 10, 20):
        f = R / "active" / f"published__dm1_both_150Hz__s{s}__{a}.npz"
        if not f.exists():
            continue
        act = np.unpackbits(np.load(f)["active"], axis=1, count=n).astype(bool)
        d = T[(T.config == "published") & (T.condition == "dm1_both_150Hz") & (T.seed_index == s)
              & (T.trial >= a) & (T.trial < a + 10)].sort_values("trial")
        run = d.runaway.to_numpy()
        frac += act[run].sum(0)
        k_run += int(run.sum())
        if s == 0:
            act_any |= act.any(0)
if k_run:
    frac /= k_run
    core783 = set(rid783[frac >= 0.5].tolist())
    any783 = set(rid783[act_any].tolist())
    z = np.load(P7 / "counts" / "none__dm1_both_150Hz__s0.npz")
    any630 = to783(rid630[z["nz_idx"]])
    core630 = to783(pd.read_csv(C.ROOT / "experiments/phase6/runaway/results/core_neurons.csv").root_id)
    for name, a_, b_ in (("DM1 150 Hz, seed 0, fired at all in 30 trials: 630 vs 783", any630, any783),
                         ("630 Phase 6 runaway core (Ir94e-triggered) vs 783 DM1 core (fired in >= half "
                          "of runaways)", core630, core783)):
        inter = len(a_ & b_)
        rows.append(dict(comparison=name, n_630_mapped=len(a_), n_783=len(b_), both=inter,
                         share_of_630=round(inter / max(len(a_), 1), 3),
                         share_of_783=round(inter / max(len(b_), 1), 3),
                         jaccard=round(inter / max(len(a_ | b_), 1), 3)))
    SO = pd.DataFrame(rows)
    SO.to_csv(R / "state_overlap.csv", index=False)
    cc = lab783.cell_class.to_numpy()
    in_core = frac >= 0.5
    by = pd.Series(cc[in_core]).replace("", "(no class)").value_counts().head(8)
    say(f"\nSTATE: 783 DM1 runaway core (fired in >= half of {k_run} runaway trials): {int(in_core.sum()):,} "
        f"neurons; biggest classes: " + ", ".join(f"{k} {v:,}" for k, v in by.items()))
    for _, r in SO.iterrows():
        say(f"  {r.comparison}: 630 {r.n_630_mapped:,}, 783 {r.n_783:,}, both {r.both:,} "
            f"({100 * r.share_of_630:.0f}% of 630's, {100 * r.share_of_783:.0f}% of 783's; Jaccard {r.jaccard})")

# ---- localisation -------------------------------------------------------------------
if (R / "localise_trials.csv").exists():
    L = pd.read_csv(R / "localise_trials.csv")
    pub = T[T.config == "published"]
    intact = {"Ir94e 200 Hz": pub[(pub.condition == "ir94e_200Hz") & (pub.seed_index < 2)],
              "DM1 150 Hz both sides": pub[(pub.condition == "dm1_both_150Hz") & (pub.seed_index == 0)]}
    rows = []
    for (test, g), d in L.groupby(["test", "group"], sort=False):
        k, nn = int(d.runaway.sum()), len(d)
        b = intact.get(test)
        rows.append(dict(test=test, group=g, trials=nn, runaway=k,
                         p_vs_intact=(fisher(k, nn, int(b.runaway.sum()), len(b)) if b is not None else np.nan),
                         median_spikes=int(d.total_spikes.median()),
                         still_firing_last_100ms_median=int(d.distinct_last_100ms.median())))
    for test, b in intact.items():
        if test not in set(L.test):
            continue
        rows.append(dict(test=test, group="intact (from step 2)", trials=len(b), runaway=int(b.runaway.sum()),
                         p_vs_intact=np.nan, median_spikes=int(b.total_spikes.median()),
                         still_firing_last_100ms_median=int(b.distinct_last_100ms.median())))
    LT = pd.DataFrame(rows)
    LT.to_csv(R / "table_localise.csv", index=False)
    say("\nLOCALISATION on 783 (published model, a group silenced)")
    for _, r in LT.iterrows():
        say(f"  {r.test:40s} | {r.group:62s} {r.runaway:3d}/{r.trials:<3d} p={r.p_vs_intact} "
            f"median spikes {r.median_spikes:,}")

# ---- synapse strength (step 5) and the Ir94e follow-ups (step 6) ------------------------------
if (R / "wsyn_trials.csv").exists():
    W = pd.read_csv(R / "wsyn_trials.csv")
    rows = []
    for (cfg, f, cond), d in W.groupby(["config", "wsyn_factor", "condition"]):
        rows.append(dict(config=cfg, wsyn_factor=f, condition=cond, trials=len(d), runaway=int(d.runaway.sum()),
                         mn9_hz=round(d.mn9_hz.mean(), 2), kc_pct_per_trial=round(100 * d.kc_active.mean() / N_KC["783"], 2),
                         still_firing_last_100ms_median=int(d.distinct_last_100ms.median())))
    WT = pd.DataFrame(rows)
    WT.to_csv(R / "table_wsyn.csv", index=False)
    say("\nSYNAPSE STRENGTH on 783 (1 seed x 30 trials; w_syn = 0.275 mV x factor)")
    for _, r in WT.iterrows():
        say(f"  {r.config:10s} x{r.wsyn_factor:<4} {r.condition:15s} runaway {r.runaway}/{r.trials}, MN9 {r.mn9_hz}, "
            f"KC {r.kc_pct_per_trial}%/trial, still firing at end {r.still_firing_last_100ms_median}")
if (R / "ir94e_extra_trials.csv").exists():
    X = pd.read_csv(R / "ir94e_extra_trials.csv")
    X["snapshot"] = X.snapshot.astype(str)
    rows = []
    for (snap, cfg, f), d in X.groupby(["snapshot", "config", "wsyn_factor"]):
        rows.append(dict(snapshot=snap, config=cfg, wsyn_factor=f,
                         seeds=",".join(str(s) for s in sorted(set(d.seed))),
                         trials=len(d), runaway=int(d.runaway.sum()), ci95=ci(int(d.runaway.sum()), len(d)),
                         max_distinct_10ms_max=int(d.max_distinct_10ms.max())))
    XT = pd.DataFrame(rows)
    say("\nIr94e 200 Hz follow-ups (step 6)")
    for _, r in XT.iterrows():
        say(f"  {r.snapshot} {r.config} x{r.wsyn_factor} seeds {r.seeds}: runaway {r.runaway}/{r.trials} [{r.ci95}], "
            f"largest max-distinct/10ms {r.max_distinct_10ms_max}")
    tot = {}
    for cfg in ("published", "fix_rule"):
        b = T[(T.config == cfg) & (T.condition == "ir94e_200Hz")]
        x1 = X[(X.snapshot == "783") & (X.config == cfg) & (X.wsyn_factor == 1.0)]
        tot[cfg] = (int(b.runaway.sum()) + int(x1.runaway.sum()), len(b) + len(x1))
        rows.append(dict(snapshot="783", config=cfg, wsyn_factor=1.0, seeds="0-9 (steps 2 + 6)",
                         trials=tot[cfg][1], runaway=tot[cfg][0], ci95=ci(*tot[cfg]),
                         max_distinct_10ms_max=np.nan))
    pd.DataFrame(rows).to_csv(R / "table_ir94e_extra.csv", index=False)
    k6 = A[(A.snapshot == "630") & (A.config == "published") & (A.condition == "ir94e_200Hz")]
    (kp, np_), (kf, nf) = tot["published"], tot["fix_rule"]
    say(f"  783 published, seeds 0-9: {kp}/{np_} [{ci(kp, np_)}]; vs 630 published {int(k6.runaway.sum())}/{len(k6)}: "
        f"Fisher p = {fisher(kp, np_, int(k6.runaway.sum()), len(k6))}")
    say(f"  783 fix_rule, seeds 0-9: {kf}/{nf} [{ci(kf, nf)}]; vs 783 published: Fisher p = {fisher(kf, nf, kp, np_)}")

(R / "summary_stats.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

# ---- figure ---------------------------------------------------------------------------
def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=8)
    ax.yaxis.grid(True, color=GRID, lw=0.6)
    ax.set_axisbelow(True)


def xpos(snap, cfg, present):
    """Bars of one snapshot group are centred on the group's tick."""
    i = present.index(cfg)
    return (0 if snap == "630" else 1) + (i - (len(present) - 1) / 2) * 0.26


fig, axes = plt.subplots(1, 3, figsize=(11, 3.9))
cfgs = ["published", "fix_rule", "fix_same_cells"]
TICKS = ["snapshot 630\n(the paper's)", "snapshot 783\n(public release)"]
for ax, cond, title in zip(axes[:2], ["dm1_both_150Hz", "ir94e_200Hz"],
                           ["DM1 smell input 150 Hz, both sides", "Ir94e taste input 200 Hz"]):
    for snap in ("630", "783"):
        sub = RW[(RW.condition == cond) & (RW.snapshot == snap)].set_index("config")
        present = [c for c in cfgs if c in sub.index]
        for cfg in present:
            r = sub.loc[cfg]
            x = xpos(snap, cfg, present)
            ax.bar(x, max(r.rate_pct, 0.6), width=0.24, color=COLOR[cfg], edgecolor="white", linewidth=1.5,
                   label=NAME[cfg] if snap == "783" else None)
            ax.text(x, r.rate_pct + 2.5, f"{int(r.runaway)}/{int(r.trials)}", ha="center", fontsize=7.5, color=INK)
    ax.set_xticks([0, 1], TICKS, fontsize=8)
    ax.set_xlim(-0.6, 1.6)
    ax.set_ylim(0, 112)
    ax.set_ylabel("runaway trials (%)", fontsize=8.5, color=INK)
    ax.set_title(title, fontsize=9.5, color=INK, loc="left")
    style(ax)
ax = axes[2]
for snap in ("630", "783"):
    sub = TT[TT.snapshot == snap].set_index("config")
    present = [c for c in cfgs if c in sub.index]
    for cfg in present:
        r = sub.loc[cfg]
        x = xpos(snap, cfg, present)
        ax.bar(x, r.mn9_hz, width=0.24, color=COLOR[cfg], edgecolor="white", linewidth=1.5)
        ax.text(x, r.mn9_hz + 1.5, f"{r.mn9_hz:.1f}", ha="center", fontsize=7.5, color=INK)
ax.set_xticks([0, 1], TICKS, fontsize=8)
ax.set_xlim(-0.6, 1.6)
ax.set_ylim(0, 85)
ax.set_ylabel("MN9 firing (spikes/s)", fontsize=8.5, color=INK)
ax.set_title("Sugar 100 Hz -> feeding neuron MN9", fontsize=9.5, color=INK, loc="left")
style(ax)
fig.text(0.01, 0.975, "Runaway = more than 1,500 neurons firing in some 10 ms slice. "
         "3 seeds x 30 one-second trials per bar.", fontsize=8.5, color=MUTED, ha="left", va="top")
h_, l_ = axes[0].get_legend_handles_labels()
fig.legend(h_, l_, loc="upper left", ncol=3, fontsize=8, frameon=False, bbox_to_anchor=(0.005, 0.92))
fig.tight_layout(rect=(0, 0, 1, 0.83))
fig.savefig(C.PLOTS / "fig_runaway_783.png", dpi=150)
plt.close(fig)
print("figure written", flush=True)

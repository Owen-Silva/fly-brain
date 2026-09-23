"""Tables and plots for the Phase 7 sign-fix validation.

Plain English: reads results/trials.csv, volleys.csv, counts/*.npz (written
by run_validation.py) and writes:
  results/table_phase3.csv     MN9 per taste condition and model version
  results/table_runaway.csv    runaway trials (Ir94e 200 Hz, DM1 150 Hz)
  results/table_kc.csv         Kenyon cells active under DM1 smell input
  results/table_steering.csv   steering neurons, left-only vs right-only DM1
  results/table_volleys.csv    one-spike "volley" triggers
  results/table_params.csv     synapse strength +/-, recommended fix
  plots/*.png
Runs on partial results too (whatever is on disk).
"""

import json

import matplotlib
import numpy as np
import pandas as pd
from scipy import stats

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import common as C  # noqa: E402

R = C.RESULTS
PLOTS = C.HERE / "plots"
PLOTS.mkdir(exist_ok=True)
N_KC = 5177
ORDER = ["none", "al_ln_literature", "eln_electrical", "known_nt", "ln53_inhibitory"]
LABEL = {"none": "baseline\n(paper)", "al_ln_literature": "AL-LN\nliterature",
         "eln_electrical": "44 eLNs\nelectrical", "known_nt": "known_nt\nsigns",
         "ln53_inhibitory": "53 LNs\ninhibitory"}
COLOR = dict(zip(ORDER, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]))
INK, MUTED = "#1f1f1e", "#6b6a64"
TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
PAPER = {"sugar_100Hz": "65.7 (paper, Fig. 1)", "sugar_200Hz": "", "water_200Hz": "",
         "bitter_200Hz": "0 expected", "sugar100_bitter120": "near 0 expected"}

T = pd.read_csv(R / "trials.csv")
main = T[T.config.isin(ORDER)]
configs = [c for c in ORDER if c in set(main.config)]


def ci(k, n):
    lo, hi = stats.binomtest(int(k), int(n)).proportion_ci(0.95)
    return f"{100 * lo:.1f}-{100 * hi:.1f}%"


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelcolor=INK, labelsize=8)
    ax.yaxis.grid(True, color="#e6e5e0", lw=0.6)
    ax.set_axisbelow(True)


# 1. Phase 3 taste results -------------------------------------------------
rows = []
for cfg in configs:
    for cond in TASTE:
        d = main[(main.config == cfg) & (main.condition == cond)]
        if d.empty:
            continue
        b = main[(main.config == "none") & (main.condition == cond)]
        per_seed = d.groupby("seed_index").mn9_hz.mean()
        rows.append(dict(config=cfg, condition=cond, trials=len(d),
                         mn9_hz=round(d.mn9_hz.mean(), 2), mn9_sd=round(d.mn9_hz.std(ddof=0), 2),
                         seed_means="/".join(f"{v:.1f}" for v in per_seed),
                         change_vs_baseline=round(d.mn9_hz.mean() - b.mn9_hz.mean(), 2) if len(b) else np.nan,
                         identical_to_baseline=bool(len(b) == len(d) and np.array_equal(
                             d.sort_values(["seed_index", "trial"]).total_spikes.to_numpy(),
                             b.sort_values(["seed_index", "trial"]).total_spikes.to_numpy())),
                         mn9_ipsi_hz=round(d.mn9_ipsi_hz.mean(), 2),
                         runaway=int(d.runaway.sum()), paper=PAPER[cond]))
p3 = pd.DataFrame(rows)
p3.to_csv(R / "table_phase3.csv", index=False)

# 2. runaway -----------------------------------------------------------------
rows = []
for cond in ["ir94e_200Hz", "dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz"]:
    b = main[(main.config == "none") & (main.condition == cond)]
    for cfg in configs:
        d = main[(main.config == cfg) & (main.condition == cond)]
        if d.empty:
            continue
        k, n = int(d.runaway.sum()), len(d)
        p = np.nan
        if len(b) and cfg != "none":
            p = stats.fisher_exact([[k, n - k], [int(b.runaway.sum()), len(b) - int(b.runaway.sum())]])[1]
        rows.append(dict(condition=cond, config=cfg, trials=n, runaway=k,
                         per_seed="/".join(str(int(v)) for v in d.groupby("seed_index").runaway.sum()),
                         rate_pct=round(100 * k / n, 1), ci95=ci(k, n),
                         fisher_p_vs_baseline=np.nan if np.isnan(p) else float(f"{p:.2g}"),
                         median_spikes=int(d.total_spikes.median()),
                         max_distinct_10ms_median=int(d.max_distinct_10ms.median()),
                         still_firing_last_100ms_median=int(d.distinct_last_100ms.median())))
rw = pd.DataFrame(rows)
rw.to_csv(R / "table_runaway.csv", index=False)

# 3. Kenyon cells under DM1 ----------------------------------------------------
lab_cc = None
rows = []
for cfg in configs:
    d = main[(main.config == cfg) & (main.condition == "dm1_both_150Hz")]
    if d.empty:
        continue
    fr = 100 * d.kc_active / N_KC
    # Phase 5 definition: mean rate over all trials > 0.5 Hz
    files = sorted((R / "counts").glob(f"{cfg}__dm1_both_150Hz__s*.npz"))
    kc5 = np.nan
    if files:
        if lab_cc is None:
            from sim import sign_fixes as S
            lab_cc = S.neuron_table(S.load_reference_arrays()[0]).cell_class.to_numpy() == "Kenyon_Cell"
        tot = np.zeros(lab_cc.size)
        k = 0
        for f in files:
            z = np.load(f)
            tot[z["nz_idx"]] += z["nz_count"]
            k += int(z["n_trials"])
        kc5 = 100 * ((tot / k > 0.5) & lab_cc).sum() / N_KC
    rows.append(dict(config=cfg, trials=len(d), kc_pct_per_trial_mean=round(fr.mean(), 2),
                     kc_pct_per_trial_sd=round(fr.std(ddof=0), 2),
                     kc_pct_per_trial_nonrunaway=round(fr[~d.runaway].mean(), 2) if (~d.runaway).any() else np.nan,
                     kc_pct_rate_over_0p5Hz=round(kc5, 2), runaway_trials=int(d.runaway.sum()),
                     real_flies="about 5-10% (Turner 2008; Honegger 2011, background, not re-read)"))
kc = pd.DataFrame(rows)
kc.to_csv(R / "table_kc.csv", index=False)

# 4. steering ------------------------------------------------------------------
NEUR = ["DNa02_L", "DNa02_R", "DNa01_L", "DNa01_R", "DNg100_L", "DNg100_R", "DNp09_L", "DNp09_R",
        "DNa03_L", "DNa03_R"]
rows = []
for cfg in configs:
    L = main[(main.config == cfg) & (main.condition == "dm1_left_150Hz")]
    Rr = main[(main.config == cfg) & (main.condition == "dm1_right_150Hz")]
    if L.empty or Rr.empty:
        continue
    for nn in NEUR:
        ps = []
        for s in sorted(set(L.seed_index) & set(Rr.seed_index)):
            a, b = L[L.seed_index == s][nn], Rr[Rr.seed_index == s][nn]
            ps.append(stats.ttest_ind(a, b, equal_var=False).pvalue if (a.std() + b.std()) > 0 else 1.0)
        rows.append(dict(config=cfg, neuron=nn, left_odor_hz=round(L[nn].mean(), 1),
                         right_odor_hz=round(Rr[nn].mean(), 1),
                         left_minus_right=round(L[nn].mean() - Rr[nn].mean(), 1),
                         welch_p_per_seed="/".join(f"{p:.2g}" for p in ps)))
    rows.append(dict(config=cfg, neuron="turn signal DNa02_L - DNa02_R",
                     left_odor_hz=round((L.DNa02_L - L.DNa02_R).mean(), 1),
                     right_odor_hz=round((Rr.DNa02_L - Rr.DNa02_R).mean(), 1),
                     left_minus_right=round((L.DNa02_L - L.DNa02_R).mean() - (Rr.DNa02_L - Rr.DNa02_R).mean(), 1),
                     welch_p_per_seed=""))
st = pd.DataFrame(rows)
st.to_csv(R / "table_steering.csv", index=False)

# 5. volleys and params ----------------------------------------------------------
if (R / "volleys.csv").exists():
    V = pd.read_csv(R / "volleys.csv")
    V[["config", "trigger", "total_spikes", "n_active", "max_distinct_10ms", "runaway",
       "distinct_last_100ms", "kc_active"]].to_csv(R / "table_volleys.csv", index=False)
P = T[T.config.str.contains("wsyn")]
if len(P):
    rows = []
    for (cfg, cond), d in P.groupby(["config", "condition"]):
        rows.append(dict(config=cfg, condition=cond, trials=len(d), runaway=int(d.runaway.sum()),
                         mn9_hz=round(d.mn9_hz.mean(), 2),
                         kc_pct_per_trial=round(100 * d.kc_active.mean() / N_KC, 2),
                         still_firing_last_100ms_median=int(d.distinct_last_100ms.median())))
    pd.DataFrame(rows).to_csv(R / "table_params.csv", index=False)

# plots ----------------------------------------------------------------------
if len(rw):
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.4))
    for ax, cond, title in zip(axes, ["ir94e_200Hz", "dm1_both_150Hz"],
                               ["Ir94e taste input, 200 Hz", "DM1 smell input, 150 Hz (both sides)"]):
        d = rw[rw.condition == cond].set_index("config").reindex([c for c in configs])
        x = np.arange(len(d))
        ax.bar(x, d.rate_pct.fillna(0), color=[COLOR[c] for c in d.index], width=0.6,
               edgecolor="white", linewidth=2)
        for xi, (_, r) in zip(x, d.iterrows()):
            if not np.isnan(r.rate_pct):
                ax.text(xi, r.rate_pct + 2, f"{int(r.runaway)}/{int(r.trials)}", ha="center",
                        fontsize=8, color=INK)
        ax.set_xticks(x, [LABEL[c] for c in d.index], fontsize=7.5)
        ax.set_ylim(0, 112)
        ax.set_title(title, fontsize=9.5, color=INK, loc="left")
        ax.set_ylabel("runaway trials (%)", fontsize=8.5, color=INK)
        style(ax)
    fig.suptitle("Runaway trials (more than 1,500 neurons firing in some 10 ms slice); 3 seeds x 30 trials",
                 fontsize=9, color=MUTED, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PLOTS / "fig1_runaway.png", dpi=150)
    plt.close(fig)

if len(kc):
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    x = np.arange(len(kc))
    ax.axhspan(5, 10, color="#e6e5e0", zorder=0)
    ax.text(len(kc) - 0.5, 7.5, "real flies ~5-10%", ha="right", va="center", fontsize=8, color=MUTED)
    ax.bar(x, kc.kc_pct_per_trial_mean, color=[COLOR[c] for c in kc.config], width=0.6)
    for xi, v in zip(x, kc.kc_pct_per_trial_mean):
        ax.text(xi, v + 1, f"{v:.1f}%", ha="center", fontsize=8, color=INK)
    ax.set_xticks(x, [LABEL[c] for c in kc.config], fontsize=7.5)
    ax.set_ylabel("Kenyon cells firing per trial (%)", fontsize=8.5, color=INK)
    ax.set_title("DM1 smell input (150 Hz, both sides): Kenyon cells recruited", fontsize=9.5,
                 color=INK, loc="left")
    style(ax)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig2_kenyon_cells.png", dpi=150)
    plt.close(fig)

if len(st):
    cfgs = [c for c in configs if c in set(st.config)]
    fig, axes = plt.subplots(1, len(cfgs), figsize=(2.6 * len(cfgs) + 0.6, 3.2), sharey=True)
    axes = np.atleast_1d(axes)
    show = ["DNa02_L", "DNa02_R", "DNa01_L", "DNa01_R"]
    for ax, cfg in zip(axes, cfgs):
        d = st[(st.config == cfg) & st.neuron.isin(show)].set_index("neuron").reindex(show)
        x = np.arange(len(show))
        ax.bar(x - 0.19, d.left_odor_hz, width=0.36, color="#2a78d6", label="left-only DM1")
        ax.bar(x + 0.19, d.right_odor_hz, width=0.36, color="#eb6834", label="right-only DM1")
        ax.set_xticks(x, [s.replace("_", " ") for s in show], fontsize=7.5)
        ax.set_title(LABEL[cfg].replace("\n", " "), fontsize=9, color=INK, loc="left")
        style(ax)
    axes[0].set_ylabel("firing rate (Hz)", fontsize=8.5, color=INK)
    axes[-1].legend(fontsize=7.5, frameon=False, loc="upper right")
    fig.suptitle("Steering descending neurons: does the side of the smell change the signal?",
                 fontsize=9, color=MUTED, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PLOTS / "fig3_steering.png", dpi=150)
    plt.close(fig)

with pd.option_context("display.width", 200, "display.max_columns", 20):
    for name, df in [("PHASE 3", p3), ("RUNAWAY", rw), ("KC", kc), ("STEERING", st)]:
        print(f"== {name}")
        print(df.to_string(index=False, max_colwidth=40))

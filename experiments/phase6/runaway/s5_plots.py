"""Plots for the Phase 6 runaway write-up (reads saved results only; no simulation).

fig1_spikes_per_trial.png  total spikes in every trial, healthy vs runaway
fig2_timecourse.png        spikes per ms through a trial, runaway vs healthy
fig3_onsets.png            share of trials that have run away by time t
fig4_grid.png              runaway share for each sugar x Ir94e rate pair
fig5_wsyn.png              runaway share vs synapse strength
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import PLOTS, RESULTS  # noqa: E402

HEALTHY, RUNAWAY = "#2a78d6", "#eb6834"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "axes.spines.top": False,
                     "axes.spines.right": False, "figure.facecolor": "#fcfcfb",
                     "axes.facecolor": "#fcfcfb", "savefig.dpi": 130})


def jitter(n, seed=0):
    return np.random.default_rng(seed).uniform(-0.25, 0.25, n)


rep = pd.read_csv(RESULTS / "reproduce_trials.csv")
b2 = pd.read_csv(RESULTS / "brian2_replay.csv")

# ---- fig 1 ------------------------------------------------------------------------
order = [("sugar200_ir94e200", "sugar 200 + Ir94e 200\n(fast engine)"),
         ("sugar200_alone", "sugar 200 alone"), ("ir94e200_alone", "Ir94e 200 alone")]
fig, ax = plt.subplots(figsize=(7.5, 4))
for x, (c, lbl) in enumerate(order):
    d = rep[rep.condition == c]
    xs = x + jitter(len(d), x)
    for flag, col in ((False, HEALTHY), (True, RUNAWAY)):
        m = (d.runaway == flag).to_numpy()
        ax.scatter(xs[m], d.total_spikes[m], s=14, color=col, alpha=0.8, lw=0)
    ax.text(x, 1.3e6, f"{int(d.runaway.sum())} of {len(d)}\nran away", ha="center", color=INK, fontsize=9)
x = len(order)
ax.scatter(x + jitter(len(b2), 9), b2.brian2_total, s=22,
           color=np.where(b2.brian2_runaway, RUNAWAY, HEALTHY), lw=0)
ax.text(x, 1.3e6, f"{int(b2.brian2_runaway.sum())} of {len(b2)}\nran away", ha="center", color=INK, fontsize=9)
ax.set_xticks(range(len(order) + 1), [o[1] for o in order] + ["sugar 200 + Ir94e 200\n(Phase 3 Brian2)"])
ax.set_yscale("log")
ax.set_ylim(3e3, 3e6)
ax.set_ylabel("spikes in the whole brain, one 1-s trial")
ax.grid(axis="y", color=GRID, lw=0.6)
ax.scatter([], [], color=HEALTHY, s=14, label="healthy trial")
ax.scatter([], [], color=RUNAWAY, s=14, label="runaway trial")
ax.legend(frameon=False, loc="lower right", fontsize=9)
ax.set_title("Runaway trials are rare and all-or-nothing", color=INK, loc="left")
fig.tight_layout()
fig.savefig(PLOTS / "fig1_spikes_per_trial.png")
plt.close(fig)

# ---- fig 2 ------------------------------------------------------------------------
ser = np.load(RESULTS / "reproduce_series.npz")
keys = list(ser["keys"])
main = rep[rep.condition == "sugar200_ir94e200"]
fig, ax = plt.subplots(figsize=(7.5, 3.6))
t = np.arange(ser["spikes_1ms"].shape[1])
for flag, col, lbl in ((False, HEALTHY, "healthy trials"), (True, RUNAWAY, "runaway trials")):
    d = main[main.runaway == flag].head(4)
    for j, (_, r) in enumerate(d.iterrows()):
        s = ser["spikes_1ms"][keys.index(f"sugar200_ir94e200|{r.seed}|{r.trial}")]
        s10 = s.reshape(-1, 10).sum(1)
        ax.plot(t[::10] + 5, s10 / 10, color=col, lw=1.2, alpha=0.85, label=lbl if j == 0 else None)
ax.set_yscale("log")
ax.set_xlabel("time in the trial (ms)")
ax.set_ylabel("spikes per ms (whole brain)")
ax.grid(axis="y", color=GRID, lw=0.6)
ax.legend(frameon=False, fontsize=9)
ax.set_title("Runaway switches on suddenly and stays on (sugar 200 + Ir94e 200)", color=INK, loc="left")
fig.tight_layout()
fig.savefig(PLOTS / "fig2_timecourse.png")
plt.close(fig)

# ---- fig 3 ------------------------------------------------------------------------
fig, ax = plt.subplots(figsize=(7.5, 3.6))
curves = [(main, 1000, "1-s trials (150)", HEALTHY)]
DARK = "#52514e"
if (RESULTS / "duration.csv").exists():
    dur = pd.read_csv(RESULTS / "duration.csv")
    curves.append((dur, 3000, f"3-s trials ({len(dur)})", DARK))
for d, T, lbl, col in curves:
    on = np.sort(d.onset_ms.dropna().to_numpy())
    tt = np.arange(0, T + 1, 5)
    frac = np.searchsorted(on, tt, side="right") / len(d)
    ax.step(tt, 100 * frac, where="post", color=col, lw=2, label=lbl)
ax.set_xlabel("time in the trial (ms)")
ax.set_ylabel("% of trials that have run away")
ax.grid(axis="y", color=GRID, lw=0.6)
ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_title("The longer the trial, the more trials run away", color=INK, loc="left")
fig.tight_layout()
fig.savefig(PLOTS / "fig3_onsets.png")
plt.close(fig)

# ---- fig 4 ------------------------------------------------------------------------
if (RESULTS / "grid.csv").exists():
    g = pd.read_csv(RESULTS / "grid.csv")
    gg = g[g.other.fillna("") == ""]
    tab = gg.groupby(["sugar_hz", "ir94e_hz"]).runaway.agg(["sum", "size"]).reset_index()
    S = sorted(tab.sugar_hz.unique())
    I = sorted(tab.ir94e_hz.unique())
    M = np.full((len(S), len(I)), np.nan)
    for _, r in tab.iterrows():
        M[S.index(r.sugar_hz), I.index(r.ir94e_hz)] = r["sum"] / r["size"]
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue", ["#f4f8fd", "#86b6ef", "#2a78d6", "#104281"])
    fig, ax = plt.subplots(figsize=(5.2, 4.2))
    im = ax.imshow(M, origin="lower", cmap=cmap, vmin=0, vmax=max(0.2, np.nanmax(M)))
    for _, r in tab.iterrows():
        i, j = S.index(r.sugar_hz), I.index(r.ir94e_hz)
        v = r["sum"] / r["size"]
        ax.text(j, i, f"{int(r['sum'])}/{int(r['size'])}", ha="center", va="center", fontsize=9,
                color="white" if v > 0.6 * max(0.2, np.nanmax(M)) else INK)
    ax.set_xticks(range(len(I)), [int(x) for x in I])
    ax.set_yticks(range(len(S)), [int(x) for x in S])
    ax.set_xlabel("Ir94e input rate (Hz)")
    ax.set_ylabel("sugar input rate (Hz)")
    ax.set_title("Runaway trials per condition", color=INK, loc="left")
    fig.colorbar(im, ax=ax, label="share of trials that ran away", shrink=0.8)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig4_grid.png")
    plt.close(fig)

# ---- fig 5 ------------------------------------------------------------------------
if (RESULTS / "wsyn.csv").exists():
    w = pd.read_csv(RESULTS / "wsyn.csv")
    lp = pd.read_csv(RESULTS / "lesion_population.csv") if (RESULTS / "lesion_population.csv").exists() else None
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    series = [("sugar200_ir94e200", "sugar 200 + Ir94e 200", RUNAWAY, "o"),
              ("ir94e200_alone", "Ir94e 200 alone", HEALTHY, "o"),
              ("sugar200_alone", "sugar 200 alone", INK2, "s"),
              ("sugar100_alone", "sugar 100 alone", INK2, "^")]
    for stim, lbl, col, mk in series:
        d = w[w.stim == stim].groupby("w_factor").runaway.agg(["sum", "size"])
        b = rep[rep.condition == stim]
        if len(b):                                  # paper value: all 150 trials (seeds 0-4)
            d.loc[1.0] = [b.runaway.sum(), len(b)]
        elif stim == "sugar100_alone" and lp is not None:
            r = lp[(lp.variant == "intact model") & lp.test.str.startswith("D sugar 100")].iloc[0]
            d.loc[1.0] = [r.runaway, r.n]
        d = d.sort_index()
        y = 100 * d["sum"] / d["size"]
        ax.plot(d.index * 100, y, marker=mk, ms=7, lw=2, color=col, label=lbl,
                markeredgecolor="#fcfcfb", markeredgewidth=1.5)
        if stim != "sugar100_alone":
            txt = "sugar 100 or 200 alone" if stim == "sugar200_alone" else lbl
            ax.annotate(txt, (d.index[-1] * 100, y.iloc[-1]), xytext=(7, 0 if stim != "sugar200_alone" else 7),
                        textcoords="offset points", va="center", fontsize=8.5, color=INK2)
    ax.set_xlim(88, 125)
    ax.set_xlabel("synapse strength, % of the paper's value (0.275 mV)")
    ax.set_ylabel("% of trials that ran away")
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.legend(frameon=False, fontsize=9, loc="upper left")
    ax.set_title("Runaway rate vs synapse strength (30 trials per point; 100% point: 150 trials)",
                 color=INK, loc="left", fontsize=10)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig5_wsyn.png")
    plt.close(fig)
print("plots written to", PLOTS)

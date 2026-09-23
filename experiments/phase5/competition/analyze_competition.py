"""Turn results/grid.csv (and the suppressor files) into tables and plots.

Plain English
-------------
* Heatmap: MN9's firing rate for every sugar x bitter pair (mean of 3 seeds).
* Curves: MN9 versus bitter rate at each sugar rate, with the paper's own
  numbers drawn on top so the match can be seen.
* Tipping point: a smooth S-shaped curve (a "Hill curve") is fitted to MN9
  versus bitter rate. It has two numbers that answer the question directly:
    - b50 = the bitter rate that halves MN9 (the tipping point);
    - n   = how steep the drop is. n near 1 = a gradual trade-off; n of 4 or
      more = switch-like. We also report the "10-90 width": how many times
      larger the bitter rate must be to go from 10% suppressed to 90%
      suppressed (81 ** (1/n); 3 = sharp, 81 = very gradual).
* The same for sugar + Ir94e and sugar + water (smaller grids).
* Suppressor silencing results as a bar chart of how much MN9 recovers.
Writes results/*.csv and *.png in this folder.
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from scipy.optimize import curve_fit  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
g = pd.read_csv(RES / "grid.csv")

INK, INK2, MUTED, SURF = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
BLUES = LinearSegmentedColormap.from_list(
    "seq_blue", ["#f4f8fd", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"])
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": "#e6e5e1",
                     "grid.linewidth": 0.6})

PAPER_BITTER = {0: 67.0, 40: 45.3, 80: 11.7, 120: 1.5, 200: 0.0}   # sugar 100 Hz, Fig. 3b


def summary(kind):
    d = g[g.kind == kind]
    s = d.groupby(["sugar_hz", "other_hz"]).agg(
        mn9=("mn9_mean", "mean"), seed_sd=("mn9_mean", "std"), trial_sd=("mn9_sd", "mean"),
        n_seeds=("seed", "nunique"), active=("mn9_active_frac", "mean"),
        n_active_neurons=("n_active_neurons", "mean")).reset_index()
    return s


def hill(b, m0, b50, n):
    return m0 / (1.0 + (np.maximum(b, 1e-9) / b50) ** n)


def fit(d):
    b, m = d.other_hz.to_numpy(float), d.mn9.to_numpy(float)
    m0 = m[b == 0].mean() if (b == 0).any() else m.max()
    try:
        (m0f, b50, n), cov = curve_fit(hill, b, m, p0=[m0, np.median(b[b > 0]), 2.0],
                                       bounds=([0, 1, 0.3], [200, 2000, 30]), maxfev=20000)
        err = np.sqrt(np.diag(cov))
        return dict(m0=m0f, b50=b50, b50_se=err[1], n=n, n_se=err[2], width_10_90=81 ** (1 / n))
    except Exception as e:  # noqa: BLE001
        return dict(m0=m0, b50=np.nan, b50_se=np.nan, n=np.nan, n_se=np.nan, width_10_90=np.nan,
                    note=str(e))


def heatmap(s, kind, label, fname, title):
    piv = s.pivot(index="sugar_hz", columns="other_hz", values="mn9").sort_index(ascending=False)
    fig, ax = plt.subplots(figsize=(max(5.6, 1.0 + 0.9 * piv.shape[1]), 1.3 + 0.7 * piv.shape[0]))
    ax.grid(False)
    im = ax.imshow(piv.to_numpy(), cmap=BLUES, vmin=0, vmax=100, aspect="auto")
    for (r, c), v in np.ndenumerate(piv.to_numpy()):
        if np.isfinite(v):
            ax.text(c, r, f"{v:.1f}", ha="center", va="center", fontsize=9,
                    color="#ffffff" if v > 55 else INK)
    ax.set_xticks(range(piv.shape[1]), [f"{int(x)}" for x in piv.columns])
    ax.set_yticks(range(piv.shape[0]), [f"{int(x)}" for x in piv.index])
    ax.set_xlabel(f"{label} GRN input rate (Hz)")
    ax.set_ylabel("Sugar GRN input rate (Hz)")
    ax.set_title(title, loc="left", fontsize=11)
    cb = fig.colorbar(im, ax=ax, shrink=0.85)
    cb.set_label("MN9 firing rate (Hz)", color=INK2)
    cb.outline.set_visible(False)
    fig.tight_layout()
    fig.savefig(HERE / fname, dpi=150)
    plt.close(fig)


out = {}
# ---- bitter --------------------------------------------------------------
sb = summary("bitter")
sb.to_csv(RES / "bitter_summary.csv", index=False)
main = sb[sb.sugar_hz.isin([50, 100, 150, 200]) & sb.other_hz.isin([0, 25, 50, 100, 150, 200])]
heatmap(main, "bitter", "Bitter", "heatmap_sugar_bitter.png",
        "MN9 rate (Hz): sugar + bitter\nmean of 3 seeds x 30 trials")

fits = []
for sug in (50, 100, 150, 200):
    d = sb[sb.sugar_hz == sug]
    for src, dd in (("main grid (3 seeds)", d[d.n_seeds >= 3]), ("fine sweep", d)):
        if src == "fine sweep" and len(dd) < 15:
            continue
        f = fit(dd)
        f.update(sugar_hz=sug, source=src, n_points=len(dd))
        fits.append(f)
fits = pd.DataFrame(fits)
fits.to_csv(RES / "bitter_hill_fits.csv", index=False)

fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
ax = axes[0]
for k, sug in enumerate((50, 100, 150, 200)):
    d = sb[sb.sugar_hz == sug].sort_values("other_hz")
    ax.plot(d.other_hz, d.mn9, color=SERIES[k], lw=2, marker="o", ms=4, label=f"sugar {sug} Hz")
ax.plot(list(PAPER_BITTER), list(PAPER_BITTER.values()), ls="none", marker="D", ms=8,
        mfc="none", mec=INK, mew=1.5, label="paper, sugar 100 Hz (Fig. 3b)")
ax.set_xlabel("Bitter GRN input rate (Hz)")
ax.set_ylabel("MN9 firing rate (Hz)")
ax.set_title("MN9 falls as bitter rises, at every sugar level", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=8)
ax.set_ylim(bottom=0)
ax = axes[1]
for k, sug in enumerate((50, 100, 150, 200)):
    d = sb[sb.sugar_hz == sug].sort_values("other_hz")
    base = d[d.other_hz == 0].mn9.iloc[0]
    ax.plot(d.other_hz, 100 * d.mn9 / base, color=SERIES[k], lw=2, marker="o", ms=4,
            label=f"sugar {sug} Hz")
ax.axhline(50, color=MUTED, lw=1, ls="--")
ax.text(200, 52, "half of sugar-alone", color=INK2, fontsize=8, ha="right")
ax.set_xlabel("Bitter GRN input rate (Hz)")
ax.set_ylabel("MN9, % of its sugar-alone rate")
ax.set_title("Same data as % of sugar alone: where it tips", loc="left", fontsize=11)
ax.legend(frameon=False, fontsize=8)
ax.set_ylim(0, 115)
fig.tight_layout()
fig.savefig(HERE / "curves_sugar_bitter.png", dpi=150)
plt.close(fig)

# ---- ir94e and water -----------------------------------------------------
for kind, label in (("ir94e", "Ir94e"), ("water", "Water")):
    s = summary(kind)
    if s.empty:
        continue
    s.to_csv(RES / f"{kind}_summary.csv", index=False)
    heatmap(s, kind, label, f"heatmap_sugar_{kind}.png",
            f"MN9 rate (Hz): sugar + {label}\nmean of 3 seeds x 30 trials")
    if kind == "ir94e":
        rows = []
        for sug in sorted(s.sugar_hz.unique()):
            if sug > 0:
                f = fit(s[s.sugar_hz == sug])
                f.update(sugar_hz=sug)
                rows.append(f)
        pd.DataFrame(rows).to_csv(RES / "ir94e_hill_fits.csv", index=False)

# ---- suppressor silencing ------------------------------------------------
sil_path = RES / "suppressor_silencing.csv"
if sil_path.exists():
    sil = pd.read_csv(sil_path)
    base = sil[sil.label == "none"].groupby(["bitter_hz", "seed"]).mn9_mean.mean()
    rows = []
    for (lbl, b), d in sil.groupby(["label", "bitter_hz"]):
        for _, r in d.iterrows():
            s_alone = base.get((0, r.seed), np.nan)
            sb_base = base.get((b, r.seed), np.nan)
            rec = (r.mn9_mean - sb_base) / (s_alone - sb_base) if b > 0 else np.nan
            rows.append(dict(label=lbl, bitter_hz=b, seed=r.seed, mn9=r.mn9_mean,
                             recovery_pct=100 * rec, n_silenced=r.n_silenced))
    rec = pd.DataFrame(rows)
    rec.to_csv(RES / "suppressor_recovery.csv", index=False)
    grp = rec[~rec.label.str.startswith("single")].groupby(["label", "bitter_hz"]).agg(
        mn9=("mn9", "mean"), rec=("recovery_pct", "mean"), rec_sd=("recovery_pct", "std"),
        n=("n_silenced", "first")).reset_index()
    order = sorted(grp.label.unique(), key=lambda x: (x != "none", int("".join(c for c in x if c.isdigit()) or 0)))
    fig, ax = plt.subplots(figsize=(8, 4))
    width = 0.27
    for k, b in enumerate((0, 80, 200)):
        d = grp[grp.bitter_hz == b].set_index("label").reindex(order)
        x = np.arange(len(order)) + (k - 1) * width
        ax.bar(x, d.mn9, width=width - 0.03, color=SERIES[k],
               label="sugar alone" if b == 0 else f"sugar + bitter {b} Hz")
    ax.set_xticks(np.arange(len(order)), [o.replace("top", "top ").replace("all", "all ") for o in order])
    ax.set_xlabel("Inhibitory candidates silenced (ranked by inhibition onto the sugar pathway)")
    ax.set_ylabel("MN9 firing rate (Hz)")
    ax.set_title("Silencing the bitter-activated inhibitory neurons (sugar 100 Hz; 3 seeds)",
                 loc="left", fontsize=11)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(HERE / "suppressor_silencing.png", dpi=150)
    plt.close(fig)

print(fits.round(2).to_string())

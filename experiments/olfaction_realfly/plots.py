"""Figures for docs/olfaction-vs-real-fly.md (reads the CSVs analyze.py writes)."""
from __future__ import annotations

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyze import OLSEN_GLOM, pn_eq  # noqa: E402
from common import PLOTS, RES  # noqa: E402

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"   # categorical slots 1-3, fixed order
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
REAL = "#8a8986"
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "axes.grid": True, "grid.color": GRID,
                     "grid.linewidth": 0.6, "axes.axisbelow": True})


def kc_plot(po):
    cols = [("kc_resp_frac", "Measured inputs (23 glomeruli)", BLUE),
            ("kc_resp_frac_setB", "Plus DoOR estimates (46 glomeruli)", AQUA),
            ("kc_resp_frac_noAPL_6tr", "Measured inputs, APL silenced", ORANGE)]
    cols = [c for c in cols if c[0] in po.columns and po[c[0]].notna().any()]
    fig, ax = plt.subplots(figsize=(8, 1.2 + 0.8 * len(cols)))
    ax.axvspan(5, 10, color=GRID, alpha=0.9, lw=0)
    ax.axvline(5, color=REAL, lw=1.5, ls="--")
    ax.text(5.2, len(cols) - 0.45, "real flies: ~5% on average\n(Honegger 2011; 6% Turner 2008)",
            color=INK2, fontsize=8, va="top")
    rng = np.random.default_rng(0)
    for k, (c, lab, col) in enumerate(cols):
        v = 100 * po[c].dropna().to_numpy()
        y = len(cols) - 1 - k + rng.uniform(-0.18, 0.18, v.size)
        ax.scatter(v, y, s=16, color=col, alpha=0.75, lw=0)
        ax.plot([v.mean()] * 2, [len(cols) - 1 - k - 0.3, len(cols) - 1 - k + 0.3], color=INK, lw=2)
        ax.text(v.mean(), len(cols) - 1 - k + 0.33, f"mean {v.mean():.1f}%", fontsize=8, ha="center",
                color=INK)
    ax.set_yticks(range(len(cols)))
    ax.set_yticklabels([c[1] for c in cols][::-1])
    ax.set_xlabel("Kenyon cells responding to the odour (%), one dot per odour")
    ax.set_ylim(-0.6, len(cols) - 0.2)
    ax.set_title("How many Kenyon cells does one odour switch on?", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS / "kc_sparseness.png", dpi=150)
    plt.close(fig)


def transfer_plot(gd):
    gloms = [x for x in ["DL5", "DM4", "DM1", "VM7d"] if x in set(gd.glom)]
    fig, axes = plt.subplots(1, len(gloms), figsize=(3.1 * len(gloms), 3.2), sharey=True)
    axes = np.atleast_1d(axes)
    xx = np.linspace(0, 160, 200)
    for ax, glo in zip(axes, gloms):
        d = gd[gd.glom == glo].groupby(["public_scale", "private_delta"]).upn_hz.mean()
        base = d.loc[(0.0, 0)]
        rmax, sig = OLSEN_GLOM[glo]
        ax.plot(xx, pn_eq(xx, 0, rmax, sig), color=REAL, ls="--", lw=1.5, label="real fly (Olsen 2010 fit)")
        for sc, col, lab in ((0.0, BLUE, "model, this glomerulus alone"),
                             (1.0, ORANGE, "model, + pentyl acetate elsewhere")):
            if sc in d.index.get_level_values(0):
                c = d.loc[sc] - base
                ax.plot(c.index, c.to_numpy(), color=col, lw=2, marker="o", ms=4, label=lab)
        ax.set_title(glo, loc="left", fontsize=10)
        ax.set_xlabel("ORN response (spikes/s)")
    axes[0].set_ylabel("PN response (spikes/s)")
    axes[0].legend(fontsize=7, frameon=False, loc="upper left")
    fig.suptitle("Smell neuron in, projection neuron out: model vs real fly", x=0.01, ha="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS / "orn_pn_transfer.png", dpi=150)
    plt.close(fig)


def sparseness_plot(ls):
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    ax.plot([0, 1], [0, 1], color=REAL, lw=1, ls="--")
    ax.scatter(ls.S_orn, ls.S_pn, s=28, color=BLUE, lw=0)
    for r in ls.itertuples():
        ax.annotate(r.glomerulus, (r.S_orn, r.S_pn), fontsize=6.5, color=INK2, xytext=(3, 2),
                    textcoords="offset points")
    ax.text(0.97, 0.05, "below the line: PN more broadly\ntuned than its ORNs (real flies)",
            ha="right", fontsize=8, color=INK2, transform=ax.transAxes)
    ax.set_xlabel("ORN selectivity (lifetime sparseness)")
    ax.set_ylabel("PN selectivity in the model")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_title("Selectivity per glomerulus (110 odours)", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS / "lifetime_sparseness.png", dpi=150)
    plt.close(fig)


def pn_eq_plot(pe):
    fig, ax = plt.subplots(figsize=(4.6, 4.4))
    m = max(pe.olsen_eq_hz.max(), pe.model_pn_evoked_hz.max())
    ax.plot([0, m], [0, m], color=REAL, lw=1, ls="--")
    ax.scatter(pe.olsen_eq_hz, pe.model_pn_evoked_hz, s=6, color=BLUE, alpha=0.4, lw=0)
    r = np.corrcoef(pe.olsen_eq_hz, pe.model_pn_evoked_hz)[0, 1]
    ax.text(0.03, 0.95, f"r = {r:.2f}, {len(pe)} glomerulus-odour pairs", transform=ax.transAxes,
            fontsize=8, va="top", color=INK2)
    ax.set_xlabel("Real-fly equation prediction (spikes/s)")
    ax.set_ylabel("Model PN response (spikes/s)")
    ax.set_title("PN responses vs Olsen 2010 equation", loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(PLOTS / "pn_vs_equation.png", dpi=150)
    plt.close(fig)


def corr_plot(s):
    f6 = s.get("F6", {})
    f7 = s.get("F7", {})
    items = [("ORN input", f6.get("corr_orn"), BLUE), ("uPNs, all 282", f6.get("corr_upn"), BLUE),
             ("uPNs, 23 measured glomeruli", f6.get("corr_upn_measured_glomeruli_neurons"), BLUE),
             ("KCs", f6.get("corr_kc"), BLUE), ("KCs, APL silenced*", f7.get("corr_kc_noAPL"), ORANGE)]
    items = [i for i in items if i[1] is not None]
    fig, ax = plt.subplots(figsize=(6.2, 3.3))
    for k, (lab, v, col) in enumerate(items):
        ax.barh(len(items) - 1 - k, v, color=col, height=0.55)
        ax.text(v + 0.01, len(items) - 1 - k, f"{v:.2f}", va="center", fontsize=8, color=INK)
    ax.set_yticks(range(len(items)))
    ax.set_yticklabels([i[0] for i in items][::-1])
    ax.set_xlabel("mean correlation between two odours' activity patterns")
    ax.set_title("How similar do different odours look?", loc="left", fontsize=11)
    if f7:
        ax.text(0.99, -0.32, f"*paired trials; intact KCs on the same trials: {f7['corr_kc_intact']:.2f}",
                transform=ax.transAxes, ha="right", fontsize=7, color=INK2)
    ax.set_xlim(0, 1)
    fig.tight_layout()
    fig.savefig(PLOTS / "odour_correlations.png", dpi=150)
    plt.close(fig)


def main():
    s = json.loads((RES / "summary.json").read_text())
    if (RES / "per_odour.csv").exists():
        kc_plot(pd.read_csv(RES / "per_odour.csv"))
    if (RES / "gain_trials.csv").exists():
        transfer_plot(pd.read_csv(RES / "gain_trials.csv"))
    if (RES / "lifetime_sparseness.csv").exists():
        sparseness_plot(pd.read_csv(RES / "lifetime_sparseness.csv"))
    if (RES / "pn_vs_olsen_eq.csv").exists():
        pn_eq_plot(pd.read_csv(RES / "pn_vs_olsen_eq.csv"))
    corr_plot(s)
    print("plots written to", PLOTS)


if __name__ == "__main__":
    main()

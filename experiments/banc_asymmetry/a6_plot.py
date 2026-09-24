"""Step 6: one figure, plots/fly_comparison.png.

Four small panels on the same axes, one dot per glomerulus:
  x = same-side factor w   = sqrt(LL*RR / (LR*RL))  (how much more a PN gets from same-side ORNs)
  y = left/right size factor rho = sqrt(LL*RL / (LR*RR))  (how much more the LEFT PNs get, from either side)
A glomerulus mirrors at the first synapse exactly when it lies inside the shaded wedge
1/w < rho < w (the same-side advantage beats the size imbalance). Filled blue = mirrors,
hollow orange = one side wins either way. Dots beyond the axes are drawn on the edge as triangles.
Colours: the project's existing plot palette (experiments/phase6/steering/s4_plots.py),
checked with the dataviz palette validator (all checks pass, light surface #fcfcfb).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)
BLUE, ORANGE, INK, INK2, GRID, SURF, WEDGE = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb", "#e8f0fb"
plt.rcParams.update({"font.size": 9.5, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "axes.spines.top": False, "axes.spines.right": False})
XL, YL = (0.35, 12.0), (0.3, 3.4)
PANELS = [
    ("flywire_783_glomerulus_map.csv", "FlyWire (fly 1), all ORNs"),
    ("banc_main_glomerulus_map.csv", "BANC (fly 2), all ORNs, as released"),
    ("complete_orns_BANC_v2_glomerulus_map.csv", "BANC (fly 2), only ORNs with both branches"),
    ("malecns_side_glomerulus_map.csv", "maleCNS (fly 3, male), all ORNs"),
]


def factors(g):
    LL, LR, RL, RR = (g[c].astype(float).clip(lower=0.5) for c in
                      ("Lorn_to_Lpn", "Lorn_to_Rpn", "Rorn_to_Lpn", "Rorn_to_Rpn"))
    return np.sqrt(LL * RR / (LR * RL)), np.sqrt(LL * RL / (LR * RR))


def main():
    fig, axes = plt.subplots(2, 2, figsize=(10.2, 8.4), sharex=True, sharey=True)
    xs = np.geomspace(1, XL[1], 200)
    for ax, (f, title) in zip(axes.ravel(), PANELS):
        g = pd.read_csv(RES / f)
        w, rho = factors(g)
        ax.fill_between(xs, 1 / xs, xs, color=WEDGE, lw=0, zorder=0)
        ax.plot(xs, xs, color=GRID, lw=1, zorder=1)
        ax.plot(xs, 1 / xs, color=GRID, lw=1, zorder=1)
        ax.axhline(1, color=GRID, lw=1, zorder=1)
        ax.axvline(1, color=GRID, lw=1, zorder=1)
        ok = g.mirror_ok_total.to_numpy(bool)
        wc, rc = np.clip(w, *XL), np.clip(rho, *YL)
        out = (w != wc) | (rho != rc)
        for m_ok, face, edge in ((True, BLUE, SURF), (False, "none", ORANGE)):
            sel = (ok == m_ok)
            ax.scatter(wc[sel & ~out], rc[sel & ~out], s=40, facecolor=face, edgecolor=edge,
                       lw=1.5 if m_ok else 1.8, zorder=3)
            ax.scatter(wc[sel & out], rc[sel & out], s=48, marker=">", facecolor=face, edgecolor=edge,
                       lw=1.5 if m_ok else 1.8, zorder=3)
        for gname in ("DM1", "DA1"):
            i = np.flatnonzero(g.glomerulus.to_numpy() == gname)
            if len(i):
                i = i[0]
                low = rc.iloc[i] < 0.45
                off = (-34, 3) if low else (6, 4 if gname == "DM1" else -12)
                ax.annotate(gname, (wc.iloc[i], rc.iloc[i]), xytext=off,
                            textcoords="offset points", color=INK, fontsize=9.5, fontweight="bold")
        n, k = len(g), int(ok.sum())
        ax.set_title(f"{title}\n{k} of {n} glomeruli mirror; median same-side factor {np.median(w):.2f}",
                     fontsize=9.5, color=INK, loc="left")
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlim(*XL)
        ax.set_ylim(*YL)
        ax.set_xticks([0.5, 1, 1.5, 2, 3, 5, 10])
        ax.xaxis.set_major_formatter(mt.FormatStrFormatter("%g"))
        ax.set_yticks([0.33, 0.5, 0.67, 1, 1.5, 2, 3])
        ax.yaxis.set_major_formatter(mt.FormatStrFormatter("%g"))
        ax.xaxis.set_minor_formatter(mt.NullFormatter())
        ax.yaxis.set_minor_formatter(mt.NullFormatter())
    for ax in axes[1]:
        ax.set_xlabel("same-side factor: how much more a PN gets from its own side's ORNs")
    for ax in axes[:, 0]:
        ax.set_ylabel("size factor: left PNs' input / right PNs' input")
    h = [plt.Line2D([], [], marker="o", ls="", markerfacecolor=BLUE, markeredgecolor=SURF, markersize=8,
                    label="mirrors at the first synapse"),
         plt.Line2D([], [], marker="o", ls="", markerfacecolor="none", markeredgecolor=ORANGE, markeredgewidth=1.8,
                    markersize=8, label="one side wins either way (size beats same-side)"),
         plt.Rectangle((0, 0), 1, 1, color=WEDGE, label="wedge where a glomerulus mirrors"),
         plt.Line2D([], [], marker=">", ls="", markerfacecolor=INK2, markeredgecolor=INK2, markersize=7,
                    label="beyond the axis, drawn at the edge")]
    fig.legend(handles=h, loc="lower center", ncol=2, frameon=False, fontsize=9.5)
    fig.suptitle("Left/right wiring of the first smell synapse (ORN -> PN), one dot per glomerulus",
                 fontsize=11, color=INK, x=0.06, ha="left")
    fig.tight_layout(rect=(0, 0.07, 1, 0.97))
    fig.savefig(PLOTS / "fly_comparison.png", dpi=150)
    print("wrote", PLOTS / "fly_comparison.png")


if __name__ == "__main__":
    main()

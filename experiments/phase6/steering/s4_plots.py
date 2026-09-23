"""Phase 6 steering check: plots.

1. plots/glomerulus_map.png: for every glomerulus, how much stronger same-side
   ORN input is (x) against how much bigger the left PNs' total input is (y).
   Filled dots: a left-only smell gives the LEFT PNs more input and a right-only
   smell the RIGHT PNs (a mirror). Hollow dots: one side wins either way.
2. plots/steering_turn.png: DNa02 "turn signal" (left DNa02 rate minus right
   DNa02 rate) for a left-only (blue) and a right-only (orange) smell, per
   glomerulus and brain version. A usable steering signal needs blue above zero
   and orange below zero.
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker  # noqa: E402,F401
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)
BLUE, ORANGE, INK, INK2, GRID, SURF = "#2a78d6", "#eb6834", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({"font.size": 10, "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2,
                     "ytick.color": INK2, "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "axes.spines.top": False, "axes.spines.right": False})
LABELLED = ["DM1", "DM2", "DM4", "VA2", "DA1", "DA2", "DM6", "VM7d"]


def glomerulus_map():
    g = pd.read_csv(RES / "glomerulus_map_630.csv")
    fig, ax = plt.subplots(figsize=(7.2, 5.6))
    ax.axhline(0, color=GRID, lw=1, zorder=0)
    ax.axvline(1, color=GRID, lw=1, zorder=0)
    ok = g.mirror_ok_total
    ax.scatter(g.ipsi_over_contra[ok], g.left_right_asym[ok] * 100, s=46, color=BLUE,
               edgecolor=SURF, lw=1.5, label=f"mirror at the first synapse ({ok.sum()} of {len(g)})", zorder=3)
    ax.scatter(g.ipsi_over_contra[~ok], g.left_right_asym[~ok] * 100, s=46, facecolor="none",
               edgecolor=ORANGE, lw=2, label=f"one side wins either way ({(~ok).sum()} of {len(g)})", zorder=3)
    for _, r in g[g.glomerulus.isin(LABELLED)].iterrows():
        off = (6, -11) if r.glomerulus == "VA2" else (-30, 3) if r.glomerulus == "DM2" else (6, 3)
        ax.annotate(r.glomerulus, (r.ipsi_over_contra, r.left_right_asym * 100), xytext=off,
                    textcoords="offset points", color=INK, fontsize=9)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.7, 1, 1.4, 2, 3, 4])
    ax.set_xticklabels(["0.5", "0.7", "1", "1.4", "2", "3", "4"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlabel("same-side / other-side ORN synapses onto a glomerulus's PNs")
    ax.set_ylabel("left PNs' total ORN input minus right PNs' (% of sum)")
    ax.set_title("Snapshot 630: ORN -> PN wiring, one dot per glomerulus", loc="left", color=INK)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.13), ncol=2, fontsize=9)
    fig.tight_layout()
    fig.savefig(PLOTS / "glomerulus_map.png", dpi=150)
    plt.close(fig)


def steering_turn():
    st = pd.read_csv(RES / "steering_table.csv")
    st = st[st.pair == "DNa02"]
    names = {"none": "published model", "al_ln": "al_ln_literature fix",
             "al_ln_ipsi": "fix + same-side release x1.4 (exploratory)"}
    variants = [v for v in ["none", "al_ln", "al_ln_ipsi"] if v in set(st.variant)]
    fig, axes = plt.subplots(1, len(variants), figsize=(4.2 * len(variants), 4.2), sharey=False)
    axes = np.atleast_1d(axes)
    for ax, v in zip(axes, variants):
        s = st[st.variant == v].set_index("glomerulus")
        gl = [g for g in ["DM1", "DM2", "DM4", "VA2", "DA1", "DA2"] if g in s.index]
        x = np.arange(len(gl))
        ax.axhline(0, color=INK2, lw=1)
        ax.bar(x - 0.2, s.loc[gl, "turn_left_odor"], 0.38, color=BLUE, label="left-only smell")
        ax.bar(x + 0.2, s.loc[gl, "turn_right_odor"], 0.38, color=ORANGE, label="right-only smell")
        ax.set_xticks(x)
        ax.set_xticklabels(gl)
        ax.set_title(names[v], loc="left", color=INK, fontsize=10)
        ax.grid(axis="y", color=GRID, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].set_ylabel("DNa02 left minus right (Hz)\n> 0 = 'turn left'")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, frameon=False, fontsize=9, loc="lower center", ncol=2)
    fig.suptitle("Steering neuron DNa02: a mirror needs blue > 0 and orange < 0", x=0.01, ha="left", color=INK)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(PLOTS / "steering_turn.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    glomerulus_map()
    if (RES / "steering_table.csv").exists():
        steering_turn()

"""Two figures, light background, sized to stay readable at phone width.
fig_incremental.png   accuracy on all odours taught so far, after each task (both halves)
fig_real_vs_random.png  real minus random wiring, final accuracy, every condition run
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import RES  # noqa: E402

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
COL = {"fly_real": "#2a78d6", "fly_shuffled": "#eb6834", "fly_uniform": "#1baf7a",
       "mlp_seq": "#eda100", "mlp_joint": "#e87ba4"}
NAME = {"fly_real": "fly, real wiring", "fly_shuffled": "fly, shuffled", "fly_uniform": "fly, uniform",
        "mlp_seq": "MLP, one task at a time", "mlp_joint": "MLP, all at once"}
plt.rcParams.update({"font.size": 11, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def fig_incremental():
    cv = pd.read_csv(RES / "incremental_curve_main.csv")
    fig, axes = plt.subplots(1, 2, figsize=(8.0, 4.4), sharey=True)
    for ax, side in zip(axes, ("left", "right")):
        c = cv[cv.side == side]
        ends = []
        for m in ("fly_real", "fly_shuffled", "fly_uniform", "mlp_seq"):
            g = c[c.model == m].groupby("after_task").acc
            mu, se = g.mean() * 100, g.sem() * 100
            x = mu.index + 1
            ax.plot(x, mu, color=COL[m], lw=2, ls="-" if m.startswith("fly") else "--",
                    marker="o" if m == "fly_real" else None, ms=4)
            ax.fill_between(x, mu - 2 * se, mu + 2 * se, color=COL[m], alpha=0.15, lw=0)
            ends.append((m, float(mu.iloc[-1])))
        j = c[c.model == "mlp_joint"].acc * 100
        if len(j):
            ax.scatter([10], [j.mean()], color=COL["mlp_joint"], marker="*", s=140, zorder=5,
                       edgecolor=SURF, linewidth=1.5)
            ends.append(("mlp_joint", float(j.mean())))
        ax.set_title(f"{side} mushroom body", fontsize=11)
        ax.set_xlabel("tasks taught (11 odours each)")
        ax.set_xticks([1, 2, 4, 6, 8, 10])
        ax.set_xlim(0.7, 10.3)
        ax.set_ylim(0, 102)
        style(ax)
    axes[0].set_ylabel("% correct on all odours taught so far")
    handles = [plt.Line2D([], [], color=COL[m], lw=2, ls="-" if m.startswith("fly") else "--",
                          marker="*" if m == "mlp_joint" else ("o" if m == "fly_real" else None),
                          ms=9 if m == "mlp_joint" else 4) for m in COL]
    fig.legend(handles, [NAME[m] for m in COL], loc="lower center", ncol=3, frameon=False,
               fontsize=10, bbox_to_anchor=(0.5, -0.01))
    fig.suptitle("Learning 110 real odours in 10 steps (mean of seeds; band = 2 SE)",
                 fontsize=12, y=0.99)
    fig.tight_layout(rect=(0, 0.12, 1, 0.96))
    fig.savefig(RES / "fig_incremental.png", dpi=150)
    plt.close(fig)


def fig_real_vs_random():
    v = pd.read_csv(RES / "variants_summary.csv")
    v = v[v.control.isin(["shuffled", "uniform"])].copy()
    label = {"k2": "2% KCs active", "k3": "3% active", "k5": "MAIN: 5% active", "k7.5": "7.5% active",
             "k10": "10% active", "T0.02": "noisier (20 ms)", "T0.1": "less noise (100 ms)",
             "T0.2": "less noise (200 ms)", "T0.5": "less noise (500 ms)",
             "syn5": ">= 5 synapses only", "kcnorm": "input / KC synapses", "setA": "23 glomeruli input"}
    order = [k for k in label if k in set(v.variant)]
    fig, ax = plt.subplots(figsize=(7.0, 0.42 * len(order) + 1.6))
    offs = {("left", "shuffled"): -0.27, ("right", "shuffled"): -0.09,
            ("left", "uniform"): 0.09, ("right", "uniform"): 0.27}
    for i, var in enumerate(order):
        for (side, ctl), o in offs.items():
            r = v[(v.variant == var) & (v.side == side) & (v.control == ctl)]
            if not len(r):
                continue
            r = r.iloc[0]
            se = max(r.se_paired, r.se_unpaired) * 100
            col = COL["fly_shuffled"] if ctl == "shuffled" else COL["fly_uniform"]
            ax.errorbar(r["diff"] * 100, i + o, xerr=2 * se, fmt="o" if side == "left" else "s",
                        color=col, ms=5, lw=1.4, capsize=0)
    ax.axvline(0, color=INK2, lw=1)
    ax.set_yticks(range(len(order)))
    ax.set_yticklabels([label[k] for k in order])
    ax.invert_yaxis()
    ax.set_xlabel("real minus random wiring, final accuracy (percentage points)\n"
                  "bar = 2 SE; right of 0 = real wiring better")
    style(ax)
    h = [plt.Line2D([], [], color=COL["fly_shuffled"], marker="o", ls="", ms=6),
         plt.Line2D([], [], color=COL["fly_uniform"], marker="o", ls="", ms=6),
         plt.Line2D([], [], color=INK2, marker="o", ls="", ms=6),
         plt.Line2D([], [], color=INK2, marker="s", ls="", ms=6)]
    ax.legend(h, ["vs shuffled", "vs uniform", "left half", "right half"], loc="upper center",
              bbox_to_anchor=(0.5, -0.22 if len(order) > 6 else -0.35), ncol=4, frameon=False,
              fontsize=10, handletextpad=0.2, columnspacing=1.0)
    ax.set_title("Does the real wiring beat random wiring?", fontsize=12)
    fig.tight_layout()
    fig.savefig(RES / "fig_real_vs_random.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    fig_incremental()
    fig_real_vs_random()
    print("figures written")

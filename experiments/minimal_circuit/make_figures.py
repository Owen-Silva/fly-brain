"""Figures for docs/minimal-circuit.md (PRELIMINARY).

fig_size_curve.png        circuit size vs how well it matches the whole brain
fig_circuit_vs_brain.png  MN9 in the whole brain vs the smallest passing circuit
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import CONDITIONS, HERE, RES  # noqa: E402

SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE = "#2a78d6", "#eb6834"
plt.rcParams.update({"font.size": 11, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
                     "figure.facecolor": SURF, "axes.facecolor": SURF,
                     "savefig.facecolor": SURF, "font.family": "DejaVu Sans"})


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def fig_curve():
    log = pd.read_csv(RES / "search_log.csv")
    cps = json.loads((RES / "checkpoints.json").read_text())["checkpoints"]
    val = json.loads((RES / "validation.json").read_text())
    chosen = cps[val["chosen_checkpoint"]]
    log["worst_err"] = 100 * log[["err_S100", "err_S200"]].abs().max(axis=1)
    fam = log[log["stage"].isin(["0-touched", "1-spiking", "2-path"])].sort_values("n_neurons")
    traj = pd.DataFrame([c["row"] for c in cps])
    traj["worst_err"] = 100 * traj[["err_S100", "err_S200"]].abs().max(axis=1)
    traj["cp"] = range(len(traj))
    traj = traj[traj["n_neurons"] <= 700]
    # one point per size: the last accepted circuit with that many neurons
    traj = traj.sort_values("cp").groupby("n_neurons").tail(1).sort_values("n_neurons")

    fig, axes = plt.subplots(2, 1, figsize=(6.4, 7.2), sharex=True)
    for ax, col, lim, lab in ((axes[0], "worst_err", 10, "worst sugar error vs whole brain (%)"),
                              (axes[1], "brake_ratio", 0.5, "bitter brake kept (1 = same as brain)")):
        style(ax)
        ax.plot(fam["n_neurons"], fam[col], "-", color=BLUE, lw=2, zorder=2)
        p = fam[fam["pass_search"]]
        f = fam[~fam["pass_search"]]
        ax.plot(p["n_neurons"], p[col], "o", ms=8, color=BLUE, mec=SURF, mew=2, zorder=3,
                label="strongest-path circuits (pass)")
        ax.plot(f["n_neurons"], f[col], "o", ms=8, mfc=SURF, mec=BLUE, mew=2, zorder=3,
                label="strongest-path circuits (fail)")
        ax.plot(traj["n_neurons"], traj[col], "-", color=ORANGE, lw=2, zorder=2)
        ax.plot(traj["n_neurons"], traj[col], "s", ms=6, color=ORANGE, mec=SURF, mew=1.5,
                zorder=3, label="greedy pruning (accepted steps)")
        ax.axhline(lim, color=INK2, ls="--", lw=1)
        ax.set_ylabel(lab)
        ax.set_xscale("log")
    axes[0].set_ylim(0, max(30, min(100, float(fam["worst_err"].max()) * 1.1)))
    axes[0].text(axes[0].get_xlim()[1], 10, " rule: 10%", va="bottom", ha="right", color=INK2,
                 fontsize=9)
    axes[1].text(axes[1].get_xlim()[1], 0.5, " rule: 0.5", va="bottom", ha="right", color=INK2,
                 fontsize=9)
    n = chosen["n_neurons"]
    axes[0].annotate(f"smallest passing:\n{n} neurons", xy=(n, 100 * max(
        abs(chosen["row"]["err_S100"]), abs(chosen["row"]["err_S200"]))),
        xytext=(n * 0.55, 30), color=INK, fontsize=10, ha="left",
        arrowprops=dict(arrowstyle="-", color=INK2, lw=1))
    axes[1].set_xlabel("neurons in the circuit (log scale)")
    axes[0].legend(frameon=False, fontsize=9, loc="upper left")
    axes[0].set_title("Circuit size vs match (search seed, 10 trials) - PRELIMINARY",
                      fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(HERE / "fig_size_curve.png", dpi=150)
    plt.close(fig)


def fig_bars():
    val = json.loads((RES / "validation.json").read_text())
    ho = next(h for h in val["heldout"] if h["checkpoint"] == val["chosen_checkpoint"])
    conds = list(CONDITIONS)
    wb = np.array([np.mean([ho["seeds"][s]["whole"][c] for s in ho["seeds"]]) for c in conds])
    ci = np.array([np.mean([ho["seeds"][s]["circuit"][c] for s in ho["seeds"]]) for c in conds])
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    style(ax)
    ax.grid(False, axis="x")
    x = np.arange(len(conds))
    w = 0.38
    ax.bar(x - w / 2 - 0.01, wb, w, color=BLUE, label="whole brain (127,400 neurons)")
    ax.bar(x + w / 2 + 0.01, ci, w, color=ORANGE, label=f"smallest circuit ({ho['n_neurons']} neurons)")
    for xi, a, b in zip(x, wb, ci):
        ax.text(xi - w / 2, a + 1.5, f"{a:.0f}", ha="center", fontsize=8, color=INK2)
        ax.text(xi + w / 2, b + 1.5, f"{b:.0f}", ha="center", fontsize=8, color=INK2)
    ax.set_xticks(x)
    names = {"S100": "sugar\n100 Hz", "S200": "sugar\n200 Hz", "W100": "water\n100 Hz",
             "W200": "water\n200 Hz", "B100": "bitter\n100 Hz", "B200": "bitter\n200 Hz",
             "S100+B100": "sugar +\nbitter"}
    ax.set_xticklabels([names[c] for c in conds], fontsize=9)
    ax.set_ylabel("MN9 firing rate (Hz)")
    ax.set_ylim(0, max(wb.max(), ci.max()) * 1.18)
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("Held-out test: seeds 0-2, 90 trials - PRELIMINARY", fontsize=11, loc="left")
    fig.tight_layout()
    fig.savefig(HERE / "fig_circuit_vs_brain.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    fig_curve()
    fig_bars()
    print("figures written")

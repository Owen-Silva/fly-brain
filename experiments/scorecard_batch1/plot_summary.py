"""Scorecard batch 1: one summary figure (plots/scorecard_batch1.png).

Ten small panels, one per test, same layout each: bars = the model's key read-outs
(blue = published model, orange = recommended fix, aqua = fix + gap junctions where
run), thin black lines = range over the 3 seeds, open black diamonds = the real-fly
number where the paper gives one. Each panel title carries the verdicts as words.

Usage:  python experiments/scorecard_batch1/plot_summary.py   (after analyze.py)
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
COL = {"none": "#2a78d6", "al_ln_literature": "#eb6834", "al_ln_literature+gap": "#1baf7a"}
NAME = {"none": "published model", "al_ln_literature": "recommended fix (al_ln_literature)",
        "al_ln_literature+gap": "fix + gap junctions (test 7 only)"}
SHORT = {"MATCH": "MATCH", "PARTIAL": "PARTIAL", "MISMATCH": "MISMATCH",
         "CAN'T TELL": "CAN'T TELL", "NOT RUN": "NOT RUN"}

M = pd.read_csv(RES / "measures.csv")
SC = pd.read_csv(RES / "scorecard.csv")


def vals(variant, test, measure):
    x = M[(M.variant == variant) & (M.test == test) & (M.measure == measure)].value.to_numpy()
    return x


def verdicts(test, with_gap=False):
    s = SC[SC.test == test].set_index("variant").verdict
    parts = [f"published: {s.get('none', 'NOT RUN')}", f"fix: {s.get('al_ln_literature', 'NOT RUN')}"]
    if with_gap:
        g = SC[SC.test == test + " (+gap)"].set_index("variant").verdict
        parts.append(f"+gap: {g.get('al_ln_literature+gap', 'NOT RUN')}")
    return "   ".join(parts)


def bars(ax, cats, series, ylabel, real=None, ylim=None):
    """cats: category labels; series: {variant: [array per category]}"""
    n = len(series)
    w = 0.8 / n
    x = np.arange(len(cats))
    for j, (v, arrs) in enumerate(series.items()):
        for i, a in enumerate(arrs):
            a = np.asarray(a, float)
            if a.size == 0 or np.all(np.isnan(a)):
                continue
            xi = x[i] - 0.4 + w * (j + 0.5)
            ax.bar(xi, np.nanmean(a), width=w * 0.9, color=COL[v], edgecolor=SURFACE,
                   linewidth=1.0, zorder=2)
            if a.size > 1:
                ax.plot([xi, xi], [np.nanmin(a), np.nanmax(a)], color=INK, lw=0.8, zorder=3)
    if real is not None:
        for i, r in enumerate(real):
            if r is not None:
                ax.plot(x[i], r, marker="D", ms=6, mfc="none", mec=INK, mew=1.2, zorder=4)
    ax.set_xticks(x)
    ax.set_xticklabels(cats, fontsize=7.5, color=INK2)
    ax.set_ylabel(ylabel, fontsize=8, color=INK2)
    ax.tick_params(axis="y", labelsize=7.5, colors=INK2)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.set_facecolor(SURFACE)
    if ylim:
        ax.set_ylim(*ylim)


def title(ax, head, test, with_gap=False):
    ax.set_title(f"{head}\n{verdicts(test, with_gap)}", fontsize=8.5, color=INK, loc="left")


def note(ax, text, y=0.97, headroom=1.0):
    if headroom > 1.0:
        lo, hi = ax.get_ylim()
        ax.set_ylim(lo, hi * headroom)
    ax.text(0.98, y, text, transform=ax.transAxes, ha="right", va="top", fontsize=7,
            color=INK2, bbox=dict(facecolor=SURFACE, edgecolor=GRID, boxstyle="round,pad=0.3"))


RUNAWAY = "published model: whole-brain runaway\nin every trial of these conditions"


def main():
    V = ["none", "al_ln_literature"]
    fig, axs = plt.subplots(2, 5, figsize=(19, 8.2), facecolor=SURFACE)
    axs = axs.ravel()

    # 1 FC2
    t = "1 FC2"
    subs = ["pC1a", "pC1b", "pC1c", "pC1d", "pC1e"]
    bars(axs[0], subs, {v: [vals(v, t, f"{s} rate Hz") for s in subs] for v in V}, "firing rate (Hz)")
    title(axs[0], "1  SAG input -> pC1 subtypes\n(fly: pC1a strong, pC1b weak, c-e ~0)", t)

    # 2 FC5
    t = "2 FC5"
    cats = ["aSP-g", "aSP-f", "aSP-h"]
    bars(axs[1], cats, {v: [100 * vals(v, t, f"FC5_DA1_150 {c} fraction responding") for c in cats]
                        for v in V}, "% of cells responding", real=[73, 3, 25], ylim=(0, 105))
    title(axs[1], "2  cVA smell -> lateral-horn cells\n(diamonds = real female flies)", t)
    note(axs[1], "no aSP-g or aSP-h cell fires in either version;\n"
                 "1 of 45 aSP-f fires (published, runaway)", y=0.60)

    # 3 FC1
    t = "3 FC1"
    cats = ["vpoEN", "pC1", "both"]
    ms = ["FC1_A_vpoEN vpoDN Hz", "FC1_B_pC1 vpoDN Hz", "FC1_C_both vpoDN Hz"]
    bars(axs[2], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "vpoDN rate (Hz)")
    title(axs[2], "3  vpoEN / pC1 -> vpoDN\n(fly: both excite)", t)

    # 4 SD4
    t = "4 SD4"
    cats = ["left PFL3", "right PFL3"]
    bars(axs[3], cats, {v: [100 * vals(v, t, "left stim: fraction toward"),
                            100 * vals(v, t, "right stim: fraction toward")] for v in V},
         "% trials turning toward stimulated side", real=[92, 92], ylim=(0, 105))
    title(axs[3], "4  one-sided PFL3 -> DNa02 turn\n(diamonds = real flies, ~92%)", t)

    # 5 TH3
    t = "5 TH3"
    cats = ["background", "+ cool", "+ cool,\nTPN-II silenced"]
    ms = ["8mV DN1a T0 Hz", "8mV DN1a T1 Hz", "8mV DN1a T2 Hz"]
    bars(axs[4], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "DN1a rate (Hz)")
    title(axs[4], "5  cold -> TPN-II -> DN1a\n(fly: DN1a inhibited, GABA-dependent)", t)
    note(axs[4], "published model: runaway in every\ntrial with cool input", y=0.97, headroom=1.45)

    # 6 TH2
    t = "6 TH2"
    cats = ["warm PNs:\nwarm", "warm PNs:\nwarm + cool", "cool PNs:\ncool"]
    ms = ["warm PNs W Hz", "warm PNs W+C Hz", "cool PNs C Hz"]
    bars(axs[5], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "firing rate (Hz)")
    title(axs[5], "6  cool sensors -> warm projection neurons\n(fly: cool inhibits warm PNs)", t)
    note(axs[5], RUNAWAY.replace(chr(10), " ") + "\n (1 seed)", y=0.97, headroom=1.3)

    # 7 OS4
    t = "7 OS4"
    cats = ["sister\n(spont.)", "cross-glom.\n(spont.)", "sister\n(DA1 odour)"]
    ms = ["S sister median r", "S cross median r", "O sister median r"]
    ser = {v: [vals(v, t, m) for m in ms] for v in V}
    ser["al_ln_literature+gap"] = [vals("al_ln_literature+gap", t, m) for m in ms]
    bars(axs[6], cats, ser, "median spike correlation (5 ms bins)")
    title(axs[6], "7  sister projection neurons in sync\n(fly: sisters >> cross; odour raises)", t,
          with_gap=True)
    note(axs[6], "fix: DA1 projection neurons silent at 10 Hz\nspontaneous input, no pairs to score\n"
                 "published: runaway in every trial (1 seed)", y=0.97, headroom=1.45)

    # 8 LL1
    t = "8 LL1"
    cats = ["M4/6:\nodour", "M4/6: odour\n+ MVP2", "V2:\nodour", "V2: odour\n+ MVP2"]
    ms = ["M4/6 odour Hz", "M4/6 odour+MVP2 Hz", "V2 odour Hz", "V2 odour+MVP2 Hz"]
    bars(axs[7], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "firing rate (Hz)")
    title(axs[7], "8  MVP2 -> M4/6 but not V2\n(fly: M4/6 drop, V2 unchanged)", t)
    note(axs[7], "published: runaway in every trial (1 seed)\nfix: V2 cells silent (0 Hz)", y=0.97, headroom=1.35)

    # 9 SD1
    t = "9 SD1"
    cats = ["both\n100 Hz", "both\n50 Hz", "L only:\nMDN L", "L only:\nMDN R",
            "R only:\nMDN L", "R only:\nMDN R"]
    ms = ["MDN both-sided LC16 100 Hz", "MDN both-sided LC16 50 Hz", "left LC16: MDN left Hz",
          "left LC16: MDN right Hz", "right LC16: MDN left Hz", "right LC16: MDN right Hz"]
    bars(axs[8], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "MDN rate (Hz)")
    title(axs[8], "9  LC16 -> MDN (backward walking)\n(fly: MDN driven; one side -> unequal)", t)

    # 10 TF4
    t = "10 TF4"
    cats = ["Usnea\nwater", "Usnea\nsugar", "Phantom\nwater", "Phantom\nsugar", "Clavicle\nwater",
            "Clavicle\nsugar"]
    ms = ["Usnea water Hz", "Usnea sugar Hz", "Phantom water Hz", "Phantom sugar Hz",
          "Clavicle water Hz", "Clavicle sugar Hz"]
    bars(axs[9], cats, {v: [vals(v, t, m) for m in ms] for v in V}, "firing rate (Hz)")
    axs[9].tick_params(axis="x", labelsize=6.6)
    title(axs[9], "10  water vs sugar feeding neurons\n(fly: Usnea water only, Phantom both, "
                  "Clavicle sugar)", t)

    handles = [plt.Rectangle((0, 0), 1, 1, color=COL[k]) for k in COL]
    handles.append(plt.Line2D([], [], marker="D", ls="none", mfc="none", mec=INK, ms=6))
    labels = [NAME[k] for k in COL] + ["real-fly number"]
    fig.legend(handles, labels, loc="upper center", ncol=4, frameon=False, fontsize=9,
               labelcolor=INK, bbox_to_anchor=(0.5, 0.965))
    fig.suptitle("Real-fly scorecard, batch 1: model read-outs per test "
                 "(bars = mean of 3 seeds x 30 trials; black line = seed range)",
                 y=0.995, fontsize=11, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = PLOTS / "scorecard_batch1.png"
    fig.savefig(out, dpi=130, facecolor=SURFACE)
    print("wrote", out)


if __name__ == "__main__":
    main()

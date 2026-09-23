"""Summarise and plot the Phase 8 conditioning runs.

Usage: python analyze_phase8.py <name> [<name> ...]   (name = e.g. circuit_modulatory)
Writes results/summary_<name>.csv, results/summary_<name>.md and plots/<name>_*.png.

Plain English
-------------
For every simulated fly (seed) and every output neuron type we compare the
average response to each odor after training with the average before
training: change = after / before - 1 (so -0.9 = 90% weaker).
"CS+" is the odor that was (or, in the control conditions, would have been)
paired with dopamine; "CS-" is the other odor. The learning score is
change(CS+) - change(CS-): clearly negative = the fly learned something
about the CS+ specifically; about zero = no odor-specific learning.
"""

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from common import PLOTS, RES  # noqa: E402
from run_phase8 import CONDITIONS  # noqa: E402

CSPLUS = {c: ("B" if c.endswith("_recip") else "A") for c in CONDITIONS}
LABEL = {
    "aversive_paired": "paired\n(PPL1-γ1pedc)",
    "aversive_paired_recip": "paired,\nodors swapped",
    "aversive_unpaired": "unpaired",
    "aversive_backward": "backward\n(DAN first)",
    "odor_only": "odor only\n(no DAN)",
    "dan_only": "DAN only\n(no odor)",
    "no_training": "no\ntraining",
    "appetitive_paired": "appetitive\npaired (PAM)",
    "appetitive_unpaired": "appetitive\nunpaired",
    "alpha1_paired": "α1 paired\n(PAM-α1)",
    "alpha2_short": "α2 paired\n1 s",
    "alpha2_long": "α2 paired\n60 s",
}
C_PLUS, C_MINUS = "#2a78d6", "#eb6834"      # validated categorical slots 1 and 2
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
APPROACH = ("MBON11", "MBON12")
AVOID = ("MBON01", "MBON02", "MBON03", "MBON04")


def md(df, index=True):
    """A pandas table as Markdown (no extra packages needed)."""
    df = df.reset_index() if index else df
    cols = [str(c) for c in df.columns]
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for _, r in df.iterrows():
        out.append("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v)
                                     for v in r.to_list()) + " |")
    return "\n".join(out)


def per_seed(d, value):
    """(condition, seed, mbon_type, odor role) -> change after/before - 1."""
    g = d.groupby(["condition", "seed", "mbon_type", "odor", "phase"])[value].mean().unstack("phase")
    g = g[g["pre"] > 0]
    g["change"] = g["post"] / g["pre"] - 1.0
    g = g.reset_index()
    g["role"] = np.where(g.odor == g.condition.map(CSPLUS), "CS+", "CS-")
    return g


def summarise(name):
    d = pd.read_csv(RES / f"cond_{name}.csv")
    w = pd.read_csv(RES / f"cond_{name}_weights.csv")
    misc = pd.read_csv(RES / f"cond_{name}_misc.csv")
    dr = per_seed(d, "drive_mV")
    sp = per_seed(d, "spikes_per_cell")
    rows = []
    for cond in [c for c in CONDITIONS if c in set(d.condition)]:
        r = CONDITIONS[cond]["readout"]
        for kind, tab in (("drive", dr), ("spikes", sp)):
            x = tab[(tab.condition == cond) & (tab.mbon_type == r)]
            if x.empty:
                continue
            p = x[x.role == "CS+"].set_index("seed")
            m = x[x.role == "CS-"].set_index("seed")
            score = (p.change - m.change).dropna()
            # net of the no-training control run on the same seeds (same test input)
            ctl = tab[(tab.condition == "no_training") & (tab.mbon_type == r)]
            cp = ctl[ctl.odor == CSPLUS[cond]].set_index("seed").change
            cm = ctl[ctl.odor != CSPLUS[cond]].set_index("seed").change
            net_p, net_m = (p.change - cp).dropna(), (m.change - cm).dropna()
            net_s = (net_p - net_m).dropna()
            rows.append(dict(
                net_csplus=net_p.mean(), net_csplus_sd=net_p.std(),
                net_csminus=net_m.mean(), net_csminus_sd=net_m.std(),
                net_score=net_s.mean(), net_score_min=net_s.min(), net_score_max=net_s.max(),
                condition=cond, readout=r, measure=kind, n_seeds=int(score.size),
                pre_csplus=p.pre.mean(), post_csplus=p.post.mean(),
                pre_csminus=m.pre.mean(), post_csminus=m.post.mean(),
                change_csplus=p.change.mean(), change_csplus_sd=p.change.std(),
                change_csminus=m.change.mean(), change_csminus_sd=m.change.std(),
                score=score.mean(), score_sd=score.std(),
                score_min=score.min(), score_max=score.max(),
                all_seeds_negative=bool((score < 0).all()) if score.size else False))
    s = pd.DataFrame(rows)
    s.to_csv(RES / f"summary_{name}.csv", index=False)

    # valence read-out: approach minus avoidance (relative drive change)
    # summed KC drive of the approach MBONs and of the avoidance MBONs, per odor
    g = d.assign(grp=np.where(d.mbon_type.isin(APPROACH), "approach",
                              np.where(d.mbon_type.isin(AVOID), "avoid", "")))
    g = g[g.grp != ""].groupby(["condition", "seed", "odor", "grp", "phase", "rep"]).drive_mV.sum()
    g = g.groupby(["condition", "seed", "odor", "grp", "phase"]).mean().unstack("phase")
    g = (g["post"] / g["pre"] - 1.0).unstack("grp")
    g["valence"] = g["approach"] - g["avoid"]          # > 0: odor now drives approach more
    g = g.reset_index()
    if "no_training" in set(g.condition):
        ctl = g[g.condition == "no_training"].set_index(["seed", "odor"]).valence
        g["valence_net"] = g.valence - g.set_index(["seed", "odor"]).index.map(ctl).to_numpy()
    else:
        g["valence_net"] = np.nan
    g["role"] = np.where(g.odor == g.condition.map(CSPLUS), "CS+", "CS-")
    val = g.groupby(["condition", "role"])[["approach", "avoid", "valence", "valence_net"]].agg(
        ["mean", "std"])
    val.columns = [f"{a}_{b}" for a, b in val.columns]
    val = val.reset_index()
    val.to_csv(RES / f"valence_{name}.csv", index=False)

    # weights: which MBON types changed at all (compartment specificity)
    wt = w.groupby(["condition", "mbon_type"]).rel_w_end.mean().unstack("mbon_type")
    wt.to_csv(RES / f"weights_by_type_{name}.csv")

    # KC sparseness and odor-evoked DAN activity during the test trials
    t = misc[misc.phase.isin(["pre", "post"])]
    kc = t.groupby("odor").kc_frac.agg(["mean", "std"])

    with open(RES / f"summary_{name}.md", "w", encoding="utf-8") as f:
        f.write(f"# Phase 8 summary: {name}\n\n")
        f.write("Change = after / before - 1, mean over seeds (sd). Score = change(CS+) - "
                "change(CS-).\n\n")
        f.write("| condition | read-out | measure | seeds | CS+ change | CS- change | score "
                "(min..max) | all seeds < 0 | CS+ net of no-training | CS- net | net score "
                "(min..max) |\n|---|---|---|---|---|---|---|---|---|---|---|\n")
        for _, r in s.iterrows():
            f.write(f"| {r.condition} | {r.readout} | {r.measure} | {r.n_seeds} | "
                    f"{r.change_csplus:+.1%} ({r.change_csplus_sd:.1%}) | "
                    f"{r.change_csminus:+.1%} ({r.change_csminus_sd:.1%}) | "
                    f"{r.score:+.1%} ({r.score_min:+.1%}..{r.score_max:+.1%}) | "
                    f"{'yes' if r.all_seeds_negative else 'no'} | "
                    f"{r.net_csplus:+.1%} ({r.net_csplus_sd:.1%}) | "
                    f"{r.net_csminus:+.1%} ({r.net_csminus_sd:.1%}) | "
                    f"{r.net_score:+.1%} ({r.net_score_min:+.1%}..{r.net_score_max:+.1%}) |\n")
        f.write("\n## Approach minus avoidance (relative change of summed KC drive of "
                "MBON11+12 minus that of MBON01-04; 'net' = minus the no-training control)\n\n")
        f.write(md(val, index=False))
        f.write("\n\n## KC fraction active in test trials\n\n")
        f.write(md(kc))
        f.write("\n\n## Mean relative KC->MBON weight at the end, types that moved > 1%\n\n")
        moved = wt.loc[:, (wt < 0.99).any(axis=0)]
        f.write(md(moved.T))
        f.write("\n")
    return s, dr, sp, wt


def plot_bars(name, s, dr, measure="drive"):
    s = s[s.measure == measure]
    conds = list(s.condition)
    fig, ax = plt.subplots(figsize=(max(8, 1.0 * len(conds) + 1.5), 4.6))
    x = np.arange(len(conds))
    wd = 0.36
    tab = dr
    for off, role, col in ((-wd / 2, "CS+", C_PLUS), (wd / 2, "CS-", C_MINUS)):
        vals = s["change_csplus" if role == "CS+" else "change_csminus"].to_numpy() * 100
        ax.bar(x + off, vals, wd * 0.94, color=col, label=f"{role} odor", zorder=2)
        for i, c in enumerate(conds):
            y = tab[(tab.condition == c) & (tab.mbon_type == CONDITIONS[c]["readout"])
                    & (tab.role == role)].change.to_numpy() * 100
            ax.scatter(np.full(y.size, x[i] + off), y, s=12, color=INK, zorder=3, linewidths=0)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.axhline(-90, color=INK2, lw=0.8, ls=":")
    ax.text(-0.6, -92, "Hige 2015, paired odor: -90% current, -80% spikes", ha="left",
            va="top", fontsize=7.5, color=INK2)
    ax.set_xticks(x, [LABEL.get(c, c) + f"\n[{CONDITIONS[c]['readout']}]" for c in conds],
                  fontsize=7.5)
    ax.set_ylabel(f"change in odor response ({'KC drive' if measure == 'drive' else 'spikes'}),"
                  " %", color=INK)
    ax.set_ylim(-110, 30)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    for sp_ in ("top", "right"):
        ax.spines[sp_].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2)
    ax.set_title(f"Change in odor response after training: trained odor (CS+) vs other odor "
                 f"(CS-); dots = seeds  [{name}]", fontsize=9.5, color=INK, loc="right")
    fig.tight_layout()
    fig.savefig(PLOTS / f"{name}_change_{measure}.png", dpi=130)
    plt.close(fig)


def plot_before_after(name, dr):
    conds = [c for c in CONDITIONS if c in set(dr.condition)]
    n = len(conds)
    cols = 4
    rws = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rws, cols, figsize=(3.0 * cols, 2.6 * rws), squeeze=False)
    for ax, c in zip(axes.flat, conds):
        r = CONDITIONS[c]["readout"]
        x = dr[(dr.condition == c) & (dr.mbon_type == r)]
        for j, (role, col) in enumerate((("CS+", C_PLUS), ("CS-", C_MINUS))):
            y = x[x.role == role]
            for _, q in y.iterrows():
                ax.plot([j * 2, j * 2 + 1], [q.pre, q.post], color=col, lw=1, alpha=0.5)
            ax.plot([j * 2, j * 2 + 1], [y.pre.mean(), y.post.mean()], color=col, lw=2.2,
                    marker="o", ms=5)
        ax.set_xticks([0, 1, 2, 3], ["CS+\nbefore", "CS+\nafter", "CS-\nbefore", "CS-\nafter"],
                      fontsize=7)
        ax.set_title(LABEL.get(c, c).replace("\n", " ") + f"  [{r}]", fontsize=7.5, color=INK)
        ax.set_ylim(bottom=0)
        ax.tick_params(labelsize=7)
        for sp_ in ("top", "right"):
            ax.spines[sp_].set_visible(False)
        ax.grid(axis="y", color=GRID, lw=0.6)
    for ax in axes.flat[n:]:
        ax.axis("off")
    axes[0, 0].set_ylabel("KC drive during odor (mV)", fontsize=8)
    fig.suptitle(f"Output-neuron response before and after training (thin: each seed; "
                 f"thick: mean) [{name}]", fontsize=10, color=INK)
    fig.tight_layout()
    fig.savefig(PLOTS / f"{name}_before_after.png", dpi=130)
    plt.close(fig)


def plot_weights(name, wt):
    keep = [c for c in ("aversive_paired", "appetitive_paired", "alpha1_paired", "alpha2_short",
                        "alpha2_long", "odor_only", "dan_only") if c in wt.index]
    w = wt.loc[keep]
    types = [t for t in w.columns if (w[t] < 0.995).any()] or list(w.columns[:10])
    v = (w[types].to_numpy() - 1.0) * 100
    fig, ax = plt.subplots(figsize=(0.55 * len(types) + 2.5, 0.45 * len(keep) + 1.6))
    lo = min(float(np.nanmin(v)), -1.0) * 1.05
    im = ax.imshow(v, cmap="Blues_r", vmin=lo, vmax=0, aspect="auto")
    ax.set_xticks(range(len(types)), types, rotation=60, fontsize=7, ha="right")
    ax.set_yticks(range(len(keep)), [LABEL.get(k, k).replace("\n", " ") for k in keep], fontsize=7)
    for i in range(v.shape[0]):
        for j in range(v.shape[1]):
            if v[i, j] < -0.5:
                ax.text(j, i, f"{v[i, j]:.0f}", ha="center", va="center", fontsize=6,
                        color="white" if v[i, j] < 0.6 * lo else INK)
    cb = fig.colorbar(im, ax=ax, shrink=0.8)
    cb.set_label("weight change, %\n(mean over ALL KCs)", fontsize=7)
    ax.set_title(f"Which output neurons' synapses changed (all KCs, end of experiment) [{name}]",
                 fontsize=8.5, color=INK)
    fig.tight_layout()
    fig.savefig(PLOTS / f"{name}_weights.png", dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    for name in sys.argv[1:]:
        s, dr, sp, wt = summarise(name)
        plot_bars(name, s, dr, "drive")
        plot_before_after(name, dr)
        plot_weights(name, wt)
        print((RES / f"summary_{name}.md").read_text(encoding="utf-8"))

"""Cross-run comparison plots for Phase 8 (run after analyze_phase8.py).

plots/tau_da_sensitivity.png : how the dopamine-trace time constant changes the
    paired / backward / unpaired results (MB circuit; eta re-calibrated each time).
plots/models_compare.png     : the main conditions in the MB circuit and in the
    whole brain (recommended fix al_ln_literature, no fix, the superseded eln_electrical,
    and the Phase 5 LN-fix); raw change after vs before training.
results/models_compare.csv   : the numbers behind the second plot.
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from analyze_phase8 import C_MINUS, C_PLUS, GRID, INK, INK2, LABEL  # noqa: E402
from common import PLOTS, RES  # noqa: E402


def load(name):
    p = RES / f"summary_{name}.csv"
    if not p.exists():
        return None
    s = pd.read_csv(p)
    return s[s.measure == "drive"].set_index("condition")


def style(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
    ax.axhline(0, color=INK2, lw=0.8)


def tau_plot():
    runs = [("0.1 s", "circuit_modulatory_tauda100"), ("0.2 s (main)", "circuit_modulatory"),
            ("0.5 s", "circuit_modulatory_tauda500")]
    conds = ["aversive_paired", "aversive_backward", "aversive_unpaired"]
    fig, axes = plt.subplots(1, 3, figsize=(10, 3.4), sharey=True)
    for ax, c in zip(axes, conds):
        for i, (lab, name) in enumerate(runs):
            s = load(name)
            if s is None or c not in s.index:
                continue
            ax.bar(i - 0.18, 100 * s.loc[c, "net_csplus"], 0.34, color=C_PLUS,
                   label="CS+ (trained odor)" if i == 0 else None, zorder=2)
            ax.bar(i + 0.18, 100 * s.loc[c, "net_csminus"], 0.34, color=C_MINUS,
                   label="CS- (other odor)" if i == 0 else None, zorder=2)
        ax.set_xticks(range(len(runs)), [r[0] for r in runs], fontsize=8)
        ax.set_title(LABEL[c].replace("\n", " "), fontsize=9, color=INK)
        ax.set_xlabel("dopamine trace time constant", fontsize=8, color=INK2)
        style(ax)
    axes[0].set_ylabel("change in MBON11 KC drive, % (net of no-training)", fontsize=8)
    axes[0].set_ylim(-100, 10)
    axes[2].legend(frameon=False, fontsize=7.5, loc="lower left")
    fig.suptitle("Hige 2015: paired -90% (current), backward: no change. Only a short dopamine "
                 "trace (0.1 s) reproduces both (eta re-calibrated for each)", fontsize=9, color=INK)
    fig.tight_layout()
    fig.savefig(PLOTS / "tau_da_sensitivity.png", dpi=130)
    plt.close(fig)


def models_plot():
    models = [("MB circuit", "circuit_modulatory"),
              ("whole brain,\nrecommended fix\n(al_ln_literature)", "brain_alln_modulatory"),
              ("whole brain,\nno fix (published)", "brain_none_modulatory"),
              ("whole brain, earlier fix\n(eln_electrical, superseded)", "brain_eln_modulatory"),
              ("whole brain,\nLN-fix (comparison only)", "brain_ln53_modulatory")]
    conds = ["aversive_paired", "aversive_unpaired", "aversive_backward", "odor_only",
             "dan_only", "no_training", "appetitive_paired"]
    # RAW change (after vs before), not net of no-training: in the whole brain the
    # no-training control itself collapses (test sniffs teach), and a net value would
    # hide that. The no-training bar is shown so the reader sees it.
    avail = [(a, b, load(b)) for a, b in models if load(b) is not None]
    rows = []
    fig, axes = plt.subplots(1, len(avail), figsize=(3.3 * len(avail), 3.8), sharey=True,
                             squeeze=False)
    for ax, (lab, name, s) in zip(axes[0], avail):
        cs = [c for c in conds if c in s.index]
        x = np.arange(len(cs))
        ax.bar(x - 0.2, [100 * s.loc[c, "change_csplus"] for c in cs], 0.38, color=C_PLUS,
               label="CS+", zorder=2)
        ax.bar(x + 0.2, [100 * s.loc[c, "change_csminus"] for c in cs], 0.38, color=C_MINUS,
               label="CS-", zorder=2)
        ax.set_xticks(x, [LABEL[c] for c in cs], fontsize=6.5, rotation=90)
        ax.set_title(lab, fontsize=8.5, color=INK)
        style(ax)
        for c in cs:
            rows.append(dict(model=name, condition=c, readout=s.loc[c, "readout"],
                             n_seeds=s.loc[c, "n_seeds"],
                             net_csplus=s.loc[c, "net_csplus"], net_csminus=s.loc[c, "net_csminus"],
                             net_score=s.loc[c, "net_score"],
                             raw_csplus=s.loc[c, "change_csplus"],
                             raw_csminus=s.loc[c, "change_csminus"]))
    axes[0, 0].set_ylabel("change in KC drive of the read-out MBON, %\n(after vs before training)",
                          fontsize=8)
    axes[0, 0].set_ylim(-105, 20)
    axes[0, 0].legend(frameon=False, fontsize=7.5, loc="lower center")
    fig.suptitle("Same experiments in the mushroom-body circuit and in the whole brain",
                 fontsize=9.5, color=INK)
    fig.tight_layout()
    fig.savefig(PLOTS / "models_compare.png", dpi=130)
    plt.close(fig)
    pd.DataFrame(rows).to_csv(RES / "models_compare.csv", index=False)
    print(pd.DataFrame(rows).round(3).to_string())


if __name__ == "__main__":
    tau_plot()
    models_plot()

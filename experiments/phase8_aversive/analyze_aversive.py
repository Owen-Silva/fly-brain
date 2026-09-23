"""Summarise the whole-brain conditioning runs with the neuromodulator fixes.

Usage: python analyze_aversive.py
Writes results/summary_<variant>.csv, results/summary_all.md and plots/aversive_compare.png.

Plain English
-------------
For every simulated fly (seed) we compare the read-out output neuron's KC input ("KC drive",
the Phase 8 main read-out) after training with before: change = after / before - 1
(-0.9 = 90% weaker). CS+ = the odor that was (or in a control would have been) paired, CS- =
the other one. "Net" = the same change minus that of the no-training run with the same seed
(same random test input), exactly as in docs/phase8-learning.md. The Phase 8 numbers for the
circuit and for the whole brain with al_ln_literature are read from experiments/phase8/results
for comparison (not re-run). PPL101 spikes per test sniff come from the run logs (_misc.csv).
"""

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)
P8 = ROOT / "experiments" / "phase8" / "results"
sys.path.insert(0, str(ROOT / "experiments" / "phase8"))
from run_phase8 import CONDITIONS  # noqa: E402

CSPLUS = {c: ("B" if c.endswith("_recip") else "A") for c in CONDITIONS}
C_PLUS, C_MINUS = "#2a78d6", "#eb6834"      # palette validated (dataviz validator, light)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
SOURCES = {  # name -> (file prefix, directory)
    "MB circuit (Phase 8)": ("cond_circuit_modulatory", P8),
    "whole brain, al_ln_literature (Phase 8)": ("cond_brain_alln_modulatory", P8),
    "whole brain, +da_modulatory": ("cond_da_modulatory", RES),
    "whole brain, +da_5ht_modulatory": ("cond_da_5ht_modulatory", RES),
    "whole brain, +da_5ht_literature": ("cond_da_5ht_literature", RES),
}


def per_seed(d):
    g = d.groupby(["condition", "seed", "mbon_type", "odor", "phase"]).drive_mV.mean().unstack("phase")
    g = g[g["pre"] > 0]
    g["change"] = g["post"] / g["pre"] - 1.0
    g = g.reset_index()
    g["role"] = np.where(g.odor == g.condition.map(CSPLUS), "CS+", "CS-")
    return g


def ppl101_per_sniff(misc):
    m = misc[misc.phase.isin(["pre", "post"])].copy()
    m["ppl101"] = m.dan.fillna("").astype(str).str.extract(r"PPL101:(\d+)")[0].fillna(0).astype(int)
    return m


def summarise(prefix, where):
    f = where / f"{prefix}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f)
    misc = pd.read_csv(where / f"{prefix}_misc.csv")
    tab = per_seed(d)
    pm = ppl101_per_sniff(misc)
    rows = []
    for cond in [c for c in CONDITIONS if c in set(d.condition)]:
        r = CONDITIONS[cond]["readout"]
        x = tab[(tab.condition == cond) & (tab.mbon_type == r)]
        p = x[x.role == "CS+"].set_index("seed")
        m = x[x.role == "CS-"].set_index("seed")
        ctl = tab[(tab.condition == "no_training") & (tab.mbon_type == r)]
        cp = ctl[ctl.odor == CSPLUS[cond]].set_index("seed").change
        cm = ctl[ctl.odor != CSPLUS[cond]].set_index("seed").change
        net_p, net_m = (p.change - cp).dropna(), (m.change - cm).dropna()
        net_s = (net_p - net_m).dropna()
        score = (p.change - m.change).dropna()
        q = pm[pm.condition == cond]
        kc = q.kc_frac.mean() if "kc_frac" in q else np.nan
        # first-sniff vs second-sniff KC drive of the read-out, per odor (pre phase)
        pre = d[(d.condition == cond) & (d.mbon_type == r) & (d.phase == "pre")]
        s1 = pre[pre.rep == 0].groupby("odor").drive_mV.mean()
        s2 = pre[pre.rep == 1].groupby("odor").drive_mV.mean()
        rows.append(dict(
            condition=cond, readout=r, n_seeds=int(score.size),
            change_csplus=p.change.mean(), change_csminus=m.change.mean(),
            score=score.mean(), score_min=score.min(), score_max=score.max(),
            seeds_learned=int((score < -0.2).sum()),
            net_csplus=net_p.mean(), net_csminus=net_m.mean(), net_score=net_s.mean(),
            net_score_min=net_s.min(), net_score_max=net_s.max(),
            net_seeds_below_minus20=int((net_s < -0.2).sum()),
            pre_csplus=p.pre.mean(), post_csplus=p.post.mean(),
            pre_csminus=m.pre.mean(), post_csminus=m.post.mean(),
            sniff1_A=s1.get("A", np.nan), sniff2_A=s2.get("A", np.nan),
            ppl101_per_test_sniff=q.ppl101.mean(),
            ppl101_per_test_sniff_pre=q[q.phase == "pre"].ppl101.mean(),
            kc_frac_A=q[q.odor == "A"].kc_frac.mean(), kc_frac_B=q[q.odor == "B"].kc_frac.mean(),
            kc_frac=kc))
    return pd.DataFrame(rows)


def pct(v):
    return "n/a" if pd.isna(v) else f"{100 * v:+.1f}%"


def main(variants):
    out, md = {}, []
    for name, (prefix, where) in SOURCES.items():
        s = summarise(prefix, where)
        if s is None:
            continue
        out[name] = s
        if where == RES:
            s.to_csv(RES / f"summary_{prefix[5:]}.csv", index=False)
        md.append(f"\n### {name}\n")
        md.append("| condition | read-out | CS+ change | CS- change | learned (CS+ minus CS-), range | "
                  "net CS+ / CS- | net learned, range (seeds below -20%) | PPL101 spikes per test sniff "
                  "| KCs responding A / B | seeds |")
        md.append("|---|---|---|---|---|---|---|---|---|---|")
        for _, r in s.iterrows():
            md.append(f"| {r.condition} | {r.readout} | {pct(r.change_csplus)} | "
                      f"{pct(r.change_csminus)} | {pct(r.score)} ({pct(r.score_min)} .. "
                      f"{pct(r.score_max)}) | {pct(r.net_csplus)} / {pct(r.net_csminus)} | "
                      f"{pct(r.net_score)} ({pct(r.net_score_min)} .. {pct(r.net_score_max)}; "
                      f"{r.net_seeds_below_minus20} of {r.n_seeds}) | "
                      f"{r.ppl101_per_test_sniff:.1f} | {100 * r.kc_frac_A:.1f}% / "
                      f"{100 * r.kc_frac_B:.1f}% | {r.n_seeds} |")
    (RES / "summary_all.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))

    # plot: raw change of the read-out for CS+ and CS-, per model, main conditions
    conds = ["aversive_paired", "aversive_paired_recip", "aversive_unpaired", "aversive_backward",
             "odor_only", "no_training", "appetitive_paired"]
    labels = ["paired", "paired,\nswapped", "unpaired", "backward", "odor\nonly", "no\ntraining",
              "reward\npaired"]
    names = list(out)
    fig, axes = plt.subplots(len(names), 1, figsize=(9, 2.3 * len(names)), sharex=True)
    axes = np.atleast_1d(axes)
    x = np.arange(len(conds))
    w = 0.36
    for ax, name in zip(axes, names):
        s = out[name].set_index("condition")
        vp = [100 * s.change_csplus.get(c, np.nan) for c in conds]
        vm = [100 * s.change_csminus.get(c, np.nan) for c in conds]
        ax.bar(x - w / 2 - 0.01, vp, w, color=C_PLUS, label="trained odor (CS+)")
        ax.bar(x + w / 2 + 0.01, vm, w, color=C_MINUS, label="other odor (CS-)")
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_ylim(-105, 15)
        ax.set_yticks([-100, -50, 0])
        ax.set_ylabel("change, %", color=INK2, fontsize=8)
        ax.set_title(name, loc="left", fontsize=9, color=INK)
        ax.grid(axis="y", color=GRID, lw=0.6)
        ax.set_axisbelow(True)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(colors=INK2, labelsize=8)
        for i, c in enumerate(conds):
            if c not in s.index:
                ax.text(i, -50, "not run", ha="center", va="center", fontsize=7, color=INK2)
    axes[0].legend(frameon=False, fontsize=8, loc="lower right", ncol=2)
    axes[-1].set_xticks(x, labels, fontsize=8)
    fig.suptitle("Read-out MBON input after vs before training (punishment: MBON-γ1pedc>α/β; "
                 "reward: MBON-γ5β'2a); mean of seeds", fontsize=9, color=INK, x=0.01, ha="left")
    fig.tight_layout()
    fig.savefig(PLOTS / "aversive_compare.png", dpi=150)
    print("saved", PLOTS / "aversive_compare.png")


if __name__ == "__main__":
    main(sys.argv[1:])

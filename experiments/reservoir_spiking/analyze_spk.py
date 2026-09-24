"""Verdicts, tables and figures for the spiking reservoir lane.

Reads results/main_grid.csv and results/main_activity.csv, writes
results/best_settings.csv, results/verdicts.csv, results/activity_summary.csv,
results/bottleneck.csv, results/summary.json, results/fig_bottleneck.png and
results/fig_activity.png. The pass rule is the rate lane's
(experiments/reservoir/analyze.py verdicts(), reused unchanged).
"""
import json

import numpy as np
import pandas as pd

import lib_spk as L
import analyze as ranalyze   # the rate lane's analysis (experiments/reservoir)

TASKS = ranalyze.TASKS
NETS = ("real_fix", "shuffle", "er")
LABEL = {"real_fix": "Real wiring", "shuffle": "Shuffled (same degrees)",
         "er": "Random (Erdős-Rényi)"}
COL = {"real_fix": "#1b6ca8", "shuffle": "#d9711c", "er": "#6b6b6b"}


def best_settings(g, keys=("network", "readout", "N", "noise"), setting="peak_hz"):
    """Per network x readout x N x noise x task: the setting with the best
    seed-averaged VALIDATION score, and the TEST scores there."""
    out = []
    for k, d in g.groupby(list(keys)):
        for task, (tcol, vcol, sgn) in TASKS.items():
            v = d.groupby(setting)[vcol].mean()
            best = v.idxmax() if sgn > 0 else v.idxmin()
            dd = d[d[setting] == best].sort_values("seed")
            s = dd[tcol].to_numpy()
            out.append({**dict(zip(keys, k)), "task": task, setting: best,
                        "n_seeds": s.size, "mean": s.mean(),
                        "sd": s.std(ddof=1) if s.size > 1 else np.nan,
                        "min": s.min(), "max": s.max(), "range": s.max() - s.min(),
                        "seeds": ";".join(f"{x:.4f}" for x in s)})
    return pd.DataFrame(out)


def fig_bottleneck(bs, path, dn_n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(5.6, 11.0), sharex=True)
    for ax, (task, (_, _, sgn)) in zip(axes, TASKS.items()):
        for net in NETS:
            for noise, ls, mk in ((0, "-", "o"), (1, "--", "s")):
                d = bs[(bs.network == net) & (bs.readout == "rand") & (bs.noise == noise)
                       & (bs.task == task)].sort_values("N")
                if d.empty:
                    continue
                ax.errorbar(d.N, d["mean"], yerr=[d["mean"] - d["min"], d["max"] - d["mean"]],
                            color=COL[net], ls=ls, marker=mk, ms=4, lw=1.8, capsize=2,
                            label=f"{LABEL[net]}{'' if noise == 0 else ', noisy'}",
                            alpha=1.0 if noise == 0 else 0.7)
                dd = bs[(bs.network == net) & (bs.readout == "DN") & (bs.noise == noise)
                        & (bs.task == task)]
                if not dd.empty:
                    ax.plot([dn_n], dd["mean"], marker="*", ms=13 if noise == 0 else 9,
                            color=COL[net], mfc=COL[net] if noise == 0 else "white", ls="none")
        ax.set_xscale("log")
        extra = {"memory capacity": "", "NARMA-10 error": "; dotted = guessing",
                 "delayed XOR accuracy": "; dotted = chance"}[task]
        ax.set_title(task + (" (higher is better" if sgn > 0 else " (lower is better")
                     + extra + ")", fontsize=11.5, loc="left")
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=11)
        if task.startswith("delayed"):
            ax.axhline(0.5, color="k", lw=0.8, ls=":")
        if task.startswith("NARMA"):
            ax.axhline(1.0, color="k", lw=0.8, ls=":")
    axes[-1].set_xlabel("Number of neurons read (random, not sensory)", fontsize=12)
    axes[0].legend(fontsize=9, loc="best", frameon=True)
    fig.text(0.01, 0.004, "Stars: all 1,299 descending neurons (filled = clean, open = noisy)."
             + chr(10) + "Dashed = count noise (80% of spikes seen + 5 Hz false). "
             "Bars: range over 3 seeds." + chr(10) + "Spiking model, 20 ms bins. PRELIMINARY.",
             fontsize=8.5)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)


def fig_activity(act, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 1, figsize=(5.6, 11.0), sharex=True)
    act = act.copy()
    act["rate_of_active_hz"] = act.mean_rate_hz / act.frac_active
    peaks = sorted(act.peak_hz.unique())
    x = np.arange(len(peaks))
    wd = 0.26
    for ax, col, title in ((axes[0], "frac_active", "Share of neurons that fire at all"),
                           (axes[1], "mean_rate_hz", "Mean firing rate, all neurons, Hz"),
                           (axes[2], "rate_of_active_hz",
                            "Mean rate of the neurons that do fire, Hz")):
        for i, net in enumerate(NETS):
            d = act[act.network == net].groupby("peak_hz")[col]
            m, lo, hi = d.mean(), d.min(), d.max()
            m, lo, hi = (s.reindex(peaks).to_numpy() for s in (m, lo, hi))
            ax.bar(x + (i - 1) * wd, m * (100 if col == "frac_active" else 1), wd,
                   color=COL[net], label=LABEL[net],
                   yerr=[(m - lo) * (100 if col == "frac_active" else 1),
                         (hi - m) * (100 if col == "frac_active" else 1)], capsize=2)
        ax.set_title(title + (" (%)" if col == "frac_active" else ""), fontsize=13, loc="left")
        ax.grid(alpha=0.3, axis="y")
        ax.tick_params(labelsize=11)
    axes[-1].set_xticks(x, [f"{int(p)} Hz" for p in peaks])
    axes[-1].set_xlabel("Peak input rate on the 9,145 sensory neurons", fontsize=12)
    axes[0].legend(fontsize=9.5, frameon=True)
    fig.text(0.01, 0.004, "Non-sensory neurons (118,255), while the input is on. Bars: mean of 3"
             + chr(10) + "seeds, whiskers: range. Runaway runs: " + str(int(act.runaway.sum())) + " of "
             + str(len(act)) + ". PRELIMINARY.", fontsize=8.5)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)


def main():
    g = pd.read_csv(L.RESULTS / "main_grid.csv")
    act = pd.read_csv(L.RESULTS / "main_activity.csv")
    # Amendment 1 (00:20): best settings from 150 and 400 Hz only
    g = g[(g.wsyn == 1.0) & g.peak_hz.isin([150.0, 400.0])]
    act = act[act.peak_hz.isin([150.0, 400.0])]
    bs = best_settings(g)
    bs.to_csv(L.RESULTS / "best_settings.csv", index=False)
    v = ranalyze.verdicts(bs)
    v.to_csv(L.RESULTS / "verdicts.csv", index=False)
    head = v[(v.noise == 0) & ((v.readout == "DN") | (v.N == 1000))]
    # activity summary
    cols = ["frac_active", "mean_rate_hz", "frac_gt_50hz", "frac_gt_100hz", "max_rate_hz",
            "dn_frac_active", "dn_mean_rate_hz", "pop_off_late_hz", "runaway", "sim_wall_s"]
    asum = act.groupby(["network", "peak_hz"])[cols].agg(["mean", "min", "max"])
    asum.columns = ["_".join(c) for c in asum.columns]
    asum.reset_index().to_csv(L.RESULTS / "activity_summary.csv", index=False)
    # bottleneck table (each network at its own best rate)
    bt = bs[bs.readout == "rand"].pivot_table(index=["task", "noise", "N"], columns="network",
                                              values="mean").reset_index()
    bt.to_csv(L.RESULTS / "bottleneck.csv", index=False)
    fig_bottleneck(bs, L.RESULTS / "fig_bottleneck.png", 1299)
    fig_activity(act[act.wsyn == 1.0], L.RESULTS / "fig_activity.png")
    summ = {"headline": head[["readout", "N", "task", "real_mean", "shuffle_mean", "er_mean",
                              "vs_shuffle", "vs_er", "overall"]].to_dict("records"),
            "counts": head.overall.value_counts().to_dict(),
            "all_counts": v.overall.value_counts().to_dict(),
            "runaway_any": bool(act.runaway.any())}
    (L.RESULTS / "summary.json").write_text(json.dumps(summ, indent=1, default=str))
    pd.set_option("display.width", 200)
    print(head[["readout", "N", "task", "real_mean", "real_range", "shuffle_mean",
                "shuffle_range", "er_mean", "er_range", "vs_shuffle", "vs_er",
                "overall"]].round(3).to_string(index=False))
    print(bs[(bs.noise == 0) & ((bs.readout == "DN") | (bs.N == 1000))][
        ["network", "readout", "task", "peak_hz", "mean", "range"]].round(3).to_string(index=False))
    print(asum.reset_index()[["network", "peak_hz", "frac_active_mean", "mean_rate_hz_mean",
                              "frac_gt_100hz_mean", "dn_frac_active_mean", "pop_off_late_hz_mean",
                              "runaway_max", "sim_wall_s_mean"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()

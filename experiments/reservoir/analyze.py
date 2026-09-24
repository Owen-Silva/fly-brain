"""Apply the pre-registered pass rule and make the summary tables and figures.

Reads results/grid.csv (from run_grid.py). Writes:
  results/best_settings.csv  every network x readout x task at its own best (rho, a)
  results/verdicts.csv       the pass rule applied (real vs each control)
  results/summary.json       headline numbers
  results/fig_bottleneck.png score vs number of read neurons
  results/fig_memory.png     memory curves at the best settings

Run: .venv\\Scripts\\python.exe experiments\\reservoir\\analyze.py [--grid path]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402

TASKS = {  # task -> (test column, validation column, +1 if higher is better)
    "memory capacity": ("mc", "mc_val", 1),
    "NARMA-10 error": ("narma_nrmse", "narma_val", -1),
    "delayed XOR accuracy": ("xor_acc", "xor_val", 1),
}
LABEL = {"real_fix": "Real wiring", "real_none": "Real wiring (published)",
         "shuffle": "Shuffled", "er": "Random (ER)"}
CONTROLS = ("shuffle", "er")


def best_settings(g):
    """For every network x readout x N x noise x task: the (rho, leak) with the
    best seed-averaged VALIDATION score, and the TEST scores there."""
    out = []
    keys = ["network", "readout", "N", "noise"]
    for (net, ro, N, noise), d in g.groupby(keys):
        for task, (tcol, vcol, sgn) in TASKS.items():
            v = d.groupby(["rho", "leak"])[vcol].mean()
            rho, leak = (v.idxmax() if sgn > 0 else v.idxmin())
            dd = d[(d.rho == rho) & (d.leak == leak)].sort_values("seed")
            s = dd[tcol].to_numpy()
            out.append({"network": net, "readout": ro, "N": int(N), "noise": noise,
                        "task": task, "rho": round(float(rho), 2), "leak": round(float(leak), 2), "n_seeds": s.size,
                        "mean": s.mean(), "sd": s.std(ddof=1) if s.size > 1 else np.nan,
                        "min": s.min(), "max": s.max(), "range": s.max() - s.min(),
                        "seeds": ";".join(f"{x:.4f}" for x in s)})
    return pd.DataFrame(out)


def verdict(real, ctrl, sgn):
    gap = sgn * (real["mean"] - ctrl["mean"])
    spread = max(real["range"], ctrl["range"])
    v = "WIN" if gap > spread else ("LOSE" if -gap > spread else "TIE")
    return v, gap, spread


def verdicts(bs, real_name="real_fix"):
    rows = []
    for (ro, N, noise), d in bs.groupby(["readout", "N", "noise"]):
        for task, (_, _, sgn) in TASKS.items():
            dt = d[d.task == task].set_index("network")
            if real_name not in dt.index:
                continue
            per = {}
            for c in CONTROLS:
                if c in dt.index:
                    per[c] = verdict(dt.loc[real_name], dt.loc[c], sgn)
            if not per:
                continue
            overall = ("WIN" if all(v[0] == "WIN" for v in per.values()) and len(per) == 2
                       else "LOSE" if any(v[0] == "LOSE" for v in per.values()) else "TIE")
            row = {"real": real_name, "readout": ro, "N": int(N), "noise": noise, "task": task,
                   "real_mean": dt.loc[real_name, "mean"], "real_range": dt.loc[real_name, "range"],
                   "overall": overall}
            for c, (v, gap, spread) in per.items():
                row.update({f"{c}_mean": dt.loc[c, "mean"], f"{c}_range": dt.loc[c, "range"],
                            f"vs_{c}": v, f"gap_{c}": gap, f"spread_{c}": spread})
            rows.append(row)
    return pd.DataFrame(rows)


def fig_bottleneck(bs, path, dn_n):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {"real_fix": "#1b6ca8", "shuffle": "#e07b39", "er": "#7a7a7a"}
    fig, axes = plt.subplots(3, 1, figsize=(5.6, 11.0), sharex=True)
    for ax, (task, (_, _, sgn)) in zip(axes, TASKS.items()):
        for net in ("real_fix", "shuffle", "er"):
            for noise, ls, mk in ((0.0, "-", "o"), (bs.noise.max(), "--", "s")):
                d = bs[(bs.network == net) & (bs.readout == "rand") & (bs.noise == noise)
                       & (bs.task == task)].sort_values("N")
                if d.empty:
                    continue
                lab = f"{LABEL[net]}{'' if noise == 0 else ', noisy'}"
                ax.errorbar(d.N, d["mean"], yerr=[d["mean"] - d["min"], d["max"] - d["mean"]],
                            color=col[net], ls=ls, marker=mk, ms=4, lw=1.8, capsize=2,
                            label=lab, alpha=1.0 if noise == 0 else 0.75)
                dd = bs[(bs.network == net) & (bs.readout == "DN") & (bs.noise == noise)
                        & (bs.task == task)]
                if not dd.empty:
                    ax.plot([dn_n], dd["mean"], marker="*", ms=13 if noise == 0 else 9,
                            color=col[net], mfc=col[net] if noise == 0 else "white", ls="none")
        ax.set_xscale("log")
        ax.set_title(task + (" (higher is better)" if sgn > 0 else " (lower is better)"),
                     fontsize=13, loc="left")
        ax.grid(alpha=0.3)
        ax.tick_params(labelsize=11)
        if task.startswith("delayed"):
            ax.axhline(0.5, color="k", lw=0.8, ls=":")
            ax.text(3000, 0.49, "chance", fontsize=9, ha="right", va="top")
        if task.startswith("NARMA"):
            ax.axhline(1.0, color="k", lw=0.8, ls=":")
            ax.text(300, 1.01, "no better than guessing the average", fontsize=9, va="bottom",
                    ha="center")
    axes[-1].set_xlabel("Number of neurons read (random, not sensory)", fontsize=12)
    axes[0].legend(fontsize=9.5, loc="best", frameon=True)
    fig.text(0.01, 0.004, "Stars: all 1,299 descending neurons (filled = clean, open = noisy)."
             + chr(10) + "Dashed = read noise 0.01. Bars: range over 3 seeds. PRELIMINARY.",
             fontsize=9)
    fig.tight_layout(rect=(0, 0.035, 1, 1))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)


def fig_memory(curves, bs, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    col = {"real_fix": "#1b6ca8", "shuffle": "#e07b39", "er": "#7a7a7a"}
    kcols = [f"k{k}" for k in range(lib.N_MC)]
    fig, axes = plt.subplots(2, 1, figsize=(5.6, 8.0), sharex=True)
    for ax, (ro, N, title) in zip(axes, (("DN", None, "Read from all 1,299 descending neurons"),
                                         ("rand", 1000, "Read from 1,000 random neurons"))):
        for net in ("real_fix", "shuffle", "er"):
            b = bs[(bs.network == net) & (bs.readout == ro) & (bs.noise == 0)
                   & (bs.task == "memory capacity")]
            if ro == "rand":
                b = b[b.N == N]
            if b.empty:
                continue
            b = b.iloc[0]
            c = curves[(curves.network == net) & (curves.readout == ro)
                       & np.isclose(curves.rho, b.rho, atol=1e-3)
                       & np.isclose(curves.leak, b.leak, atol=1e-3)]
            if ro == "rand":
                c = c[c.N == N]
            if c.empty:
                continue
            m = c[kcols].to_numpy().mean(0)
            ax.plot(np.arange(lib.N_MC), m, color=col[net], lw=2,
                    label=f"{LABEL[net]}: total {m.sum():.1f} (rho {b.rho:.2f}, a {b.leak:.1f})")
        ax.set_title(title, fontsize=13, loc="left")
        ax.set_ylabel("recall of input k steps ago\n(squared correlation)", fontsize=10)
        ax.grid(alpha=0.3)
        ax.legend(fontsize=9.5, loc="upper right")
        ax.set_xlim(0, 60)
    axes[-1].set_xlabel("delay k (steps)", fontsize=12)
    fig.text(0.01, 0.005, "Mean of 3 seeds at each network's best setting. PRELIMINARY.",
             fontsize=8.5)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    fig.savefig(path, dpi=130, facecolor="white")
    plt.close(fig)


def samegain_table(out):
    """EXPLORATORY (not pre-registered): all networks divided by the same
    number (the Erdos-Renyi seed-0 radius). Seed 0 only. The Erdos-Renyi rows
    come from the main grid (its own radius is that same number)."""
    p = out / "samegain_grid.csv"
    if not p.exists():
        return None
    s = pd.read_csv(p)
    g = pd.read_csv(out / "grid.csv")
    er = g[(g.network == "er") & (g.seed == 0)]
    both = pd.concat([s, er], ignore_index=True)
    bs = best_settings(both[both.seed == 0])
    keep = bs[((bs.readout == "DN") | ((bs.readout == "rand") & bs.N.isin([10, 100, 1000])))]
    keep = keep[["network", "readout", "N", "noise", "task", "rho", "leak", "mean"]]
    keep.to_csv(out / "samegain_best.csv", index=False, float_format="%.4g")
    return keep


def noself_verdicts(g, out):
    """SENSITIVITY CHECK (added after the main run): the seed-1 controls had
    their spectral radius set by one accidental self-connection. Replace those
    two batches by versions without self-connections and re-apply the rule
    (primary readouts only, as the no-self runs use --lite)."""
    p = out / "noself_grid.csv"
    if not p.exists():
        return None
    ns = pd.read_csv(p)
    ns["network"] = ns.network.str.replace("_noself", "", regex=False)
    swapped = set(zip(ns.network, ns.seed))
    keep = ~pd.Series([(a, b) in swapped for a, b in zip(g.network, g.seed)], index=g.index)
    g2 = pd.concat([g[keep], ns], ignore_index=True)
    g2 = g2[(g2.readout == "DN") | ((g2.readout == "rand") & (g2.N == 1000))]
    g2 = g2[g2.network.isin(["real_fix", "shuffle", "er"])]
    v = verdicts(best_settings(g2), "real_fix")
    v.to_csv(out / "verdicts_noself.csv", index=False, float_format="%.5g")
    return v


def extended_verdicts(g, out):
    """EXPLORATORY (added after the main run): the real and shuffled networks
    were also run at rho 2-10 (results/highgain_grid.csv, primary readouts).
    Best settings are re-picked over rho 0.5-10 for them; Erdos-Renyi keeps
    rho 0.5-1.5 (its best settings were inside that range). Seed-1 controls
    are the versions without self-connections."""
    p, pn = out / "highgain_grid.csv", out / "noself_grid.csv"
    if not (p.exists() and pn.exists()):
        return None
    parts = [g, pd.read_csv(pn), pd.read_csv(p)]
    for d in parts[1:]:
        d["network"] = d.network.str.replace("_noself", "", regex=False)
    ns = parts[1]
    swapped = set(zip(ns.network, ns.seed))
    keep = ~pd.Series([(a, b) in swapped for a, b in zip(g.network, g.seed)], index=g.index)
    g2 = pd.concat([g[keep], ns, parts[2]], ignore_index=True)
    g2 = g2[(g2.readout == "DN") | ((g2.readout == "rand") & (g2.N == 1000))]
    g2 = g2[g2.network.isin(["real_fix", "shuffle", "er"])]
    bs = best_settings(g2)
    bs.to_csv(out / "best_settings_extended.csv", index=False, float_format="%.5g")
    v = verdicts(bs, "real_fix")
    v.to_csv(out / "verdicts_extended.csv", index=False, float_format="%.5g")
    return v, bs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--grid", default=str(lib.RESULTS / "grid.csv"))
    ap.add_argument("--curves", default=str(lib.RAW / "mc_curves.csv"))
    ap.add_argument("--out", default=str(lib.RESULTS))
    a = ap.parse_args()
    out = Path(a.out)
    g = pd.read_csv(a.grid)
    bs = best_settings(g)
    bs.to_csv(out / "best_settings.csv", index=False, float_format="%.5g")
    v = verdicts(bs, "real_fix")
    vn = verdicts(bs, "real_none")
    allv = pd.concat([v, vn], ignore_index=True)
    allv.to_csv(out / "verdicts.csv", index=False, float_format="%.5g")
    prim = v[(v.noise == 0) & (((v.readout == "DN")) | ((v.readout == "rand") & (v.N == 1000)))]
    summary = {"PRELIMINARY": True,
               "headline_verdicts": prim[["readout", "N", "task", "overall", "vs_shuffle", "vs_er",
                                          "real_mean", "shuffle_mean", "er_mean"]]
               .to_dict(orient="records"),
               "seeds_per_network": g.groupby("network").seed.nunique().to_dict()}
    json.dump(summary, open(out / "summary.json", "w"), indent=1, default=float)
    dn_n = int(g[g.readout == "DN"].N.iloc[0])
    fig_bottleneck(bs, out / "fig_bottleneck.png", dn_n)
    if Path(a.curves).exists():
        fig_memory(pd.read_csv(a.curves), bs, out / "fig_memory.png")
    pd.set_option("display.width", 200)
    nv = noself_verdicts(g, out)
    if nv is not None:
        print("SENSITIVITY: seed-1 controls without self-connections:")
        print(nv[["readout", "N", "noise", "task", "real_mean", "shuffle_mean", "er_mean",
                  "vs_shuffle", "vs_er", "overall"]].to_string(index=False))
    ev = extended_verdicts(g, out)
    if ev is not None:
        v2, bs2 = ev
        print("EXPLORATORY: rho up to 10 for real and shuffled; seed-1 controls without self-connections:")
        print(v2[["readout", "noise", "task", "real_mean", "shuffle_mean", "er_mean", "vs_shuffle",
                  "vs_er", "overall"]].to_string(index=False))
        print(bs2[bs2.noise == 0][["network", "readout", "task", "rho", "leak", "mean"]]
              .to_string(index=False))
    sg = samegain_table(out)
    if sg is not None:
        print("EXPLORATORY same-gain (seed 0):")
        print(sg[(sg.noise == 0)].pivot_table(index=["readout", "N", "task"], columns="network",
                                               values="mean").round(3).to_string())
    print(prim[["readout", "N", "task", "real_mean", "shuffle_mean", "er_mean", "vs_shuffle",
                "vs_er", "overall"]].to_string(index=False))


if __name__ == "__main__":
    main()

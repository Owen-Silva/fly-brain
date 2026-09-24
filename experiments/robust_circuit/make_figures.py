"""Figures for docs/robust-circuit.md (PRELIMINARY).

fig_size_curve.png       size vs pass: worst sugar error over the four versions,
                         and which test each rejected candidate failed first
fig_circuit_vs_brain.png final circuit vs whole brain, seeds 0-2, four versions
"""

import csv
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from rcommon import HERE, MC_RES, RAW, RES, VARIANTS  # noqa: E402

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GREY, INK, INK2, SURF = "#8a8984", "#0b0b0b", "#52514e", "#fcfcfb"
NAME = {"w-20": "weights -20%", "w+20": "weights +20%", "int8": "8-bit", "normal": "normal"}
plt.rcParams.update({"font.size": 9, "axes.edgecolor": INK2, "axes.labelcolor": INK,
                     "xtick.color": INK2, "ytick.color": INK2, "figure.facecolor": SURF,
                     "axes.facecolor": SURF, "axes.spines.top": False,
                     "axes.spines.right": False})


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return np.nan


def worst(row):
    e = [abs(f(row.get(f"{v}_{k}"))) for v in VARIANTS for k in ("err_S100", "err_S200")]
    return np.nanmax(e)


def size_curve():
    rows = list(csv.DictReader(open(RES / "search_log.csv")))
    cps = json.loads((RAW / "checkpoints.json").read_text())["checkpoints"]
    val = json.loads((RES / "validation.json").read_text())
    prev = list(csv.DictReader(open(MC_RES / "robustness_scan.csv")))
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 6.4), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 2], "hspace": 0.12})
    # previous lane: pruning that only checked normal weights (seed 0, 30 trials)
    pv = sorted(((int(r["n_neurons"]), 100 * max(abs(f(r[k])) for k in
                 ("err_S100_w-20", "err_S200_w-20", "err_S100_w+20", "err_S200_w+20")))
                 for r in prev), key=lambda t: -t[0])
    a1.plot([p[0] for p in pv], [min(p[1], 60) for p in pv], "-o", color=GREY, lw=1.5, ms=3,
            label="previous lane's pruning (only normal weights checked), worst +/-20% error")
    fam = [r for r in rows if r["stage"] == "F-path"]
    for ok, mk in ((True, "o"), (False, "o")):
        sel = [r for r in fam if (r["pass_search"] == "True") == ok]
        a1.scatter([int(r["n_neurons"]) for r in sel], [min(100 * worst(r), 60) for r in sel],
                   s=42, marker=mk, facecolor=BLUE if ok else SURF, edgecolor=BLUE, lw=2,
                   zorder=4, label="strongest-path circuits: " + ("pass" if ok else "fail"))
    acc = [(c["n_neurons"], 100 * worst(c["row"])) for c in cps]
    a1.plot([a[0] for a in acc], [a[1] for a in acc], "-o", color=ORANGE, lw=2, ms=4, zorder=5,
            label="this search: accepted steps (all four versions pass)")
    ch = val.get("chosen_checkpoint")
    if ch is not None:
        t = [x for x in val["tried"] if x["checkpoint"] == ch][0]
        e = max(abs(r.get(k, 0)) for s in t["seeds"].values() for r in s["versions"].values()
                for k in ("err_S100", "err_S200"))
        a1.scatter([t["n_neurons"]], [100 * e], marker="*", s=180, color=AQUA, edgecolor=INK,
                   lw=0.8, zorder=6, label=f"final circuit, seeds 0-2, used to pick it (worst {100 * e:.1f}%)")
    fp = RES / "fresh_seeds.json"
    if fp.exists():
        fr = json.loads(fp.read_text())["circuits"]
        for k, c in fr.items():
            e = max(abs(r[q]) for s in c["seeds"].values() for r in s["versions"].values()
                    for q in ("err_S100", "err_S200"))
            a1.scatter([c["n_neurons"]], [100 * e], marker="D", s=46, zorder=7,
                       facecolor=AQUA if c["pass_all"] else SURF, edgecolor=INK, lw=1,
                       label=("fresh seeds 3-5 (filled = pass, open = fail)"
                              if k == "411" else None))
    a1.axhline(10, color=INK2, ls="--", lw=1)
    a1.axhline(7.5, color=INK2, ls=":", lw=1)
    a1.text(1.01, 10, "rule 10%", transform=a1.get_yaxis_transform(), va="center", color=INK2)
    a1.text(1.01, 7.5, "search 7.5%", transform=a1.get_yaxis_transform(), va="center", color=INK2)
    a1.set_ylim(0, 62)
    a1.set_ylabel("worst sugar error vs whole brain (%)\n(capped at 60)")
    a1.legend(frameon=False, fontsize=7.5, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    a1.grid(axis="y", color="#e6e5e0", lw=0.6)

    cats = ["passed", "w-20", "w+20", "int8", "normal"]
    col = {"passed": ORANGE, "w-20": BLUE, "w+20": AQUA, "int8": YELLOW, "normal": GREY}
    lab = {"passed": "passed (accepted)", "w-20": "failed first at -20%",
           "w+20": "failed first at +20%", "int8": "failed first at 8-bit",
           "normal": "failed first at normal"}
    cand = [r for r in rows if r["stage"] != "F-path"]
    rng = np.random.default_rng(0)
    for k, c in enumerate(cats):
        sel = [r for r in cand if (r["pass_search"] == "True" if c == "passed"
                                   else r["first_fail"] == c)]
        if not sel:
            continue
        a2.scatter([int(r["n_neurons"]) for r in sel], k + rng.uniform(-0.25, 0.25, len(sel)),
                   s=10, color=col[c], alpha=0.7, lw=0)
        a2.text(1.01, k, f"{lab[c]} ({len(sel)})", transform=a2.get_yaxis_transform(),
                va="center", color=INK2, fontsize=7.5)
    a2.set_yticks([])
    a2.set_ylim(-0.6, len(cats) - 0.4)
    a2.set_xscale("log")
    a2.set_xticks([20, 50, 100, 200, 400, 600])
    a2.set_xticklabels(["20", "50", "100", "200", "400", "600"])
    a2.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    a2.set_xlabel("neurons in the circuit (log scale)")
    a2.set_title("every candidate the search tried, by the first test it failed (seed 7)",
                 fontsize=8.5, color=INK2, loc="left")
    fig.text(0.99, 0.005, "PRELIMINARY", ha="right", va="bottom", fontsize=7, color=INK2)
    fig.savefig(HERE / "fig_size_curve.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


def circuit_vs_brain():
    val = json.loads((RES / "validation.json").read_text())
    ch = val["chosen_checkpoint"]
    t = [x for x in val["tried"] if x["checkpoint"] == ch][0]
    conds = ["S100", "S200", "S100+B100", "B200", "W200"]
    fig, axs = plt.subplots(1, 4, figsize=(9.6, 2.9), sharey=True)
    for ax, v in zip(axs, ["normal", "w-20", "w+20", "int8"]):
        cs = [c for c in conds if c in t["seeds"]["seed0"]["versions"][v]["circuit"]]
        wb = [np.mean([t["seeds"][s]["versions"][v]["whole"].get(c, np.nan)
                       for s in t["seeds"]]) for c in cs]
        cc = [np.mean([t["seeds"][s]["versions"][v]["circuit"][c] for s in t["seeds"]])
              for c in cs]
        x = np.arange(len(cs))
        ax.bar(x - 0.2, wb, 0.38, color=BLUE, label="whole brain")
        ax.bar(x + 0.2, cc, 0.38, color=ORANGE, label=f"{t['n_neurons']}-neuron circuit")
        for xi, (a, b) in enumerate(zip(wb, cc)):
            if not np.isnan(a):
                ax.text(xi - 0.2, a + 1.5, f"{a:.0f}", ha="center", fontsize=6.5, color=INK2)
            ax.text(xi + 0.2, b + 1.5, f"{b:.0f}", ha="center", fontsize=6.5, color=INK2)
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("S100+B100", "S+B") for c in cs], fontsize=7.5)
        ax.set_title(NAME[v], fontsize=9, color=INK)
        ax.grid(axis="y", color="#e6e5e0", lw=0.6)
        ax.set_axisbelow(True)
    axs[0].set_ylabel("MN9 firing rate (Hz)")
    axs[0].set_ylim(0, 115)
    h, lb = axs[0].get_legend_handles_labels()
    fig.tight_layout()
    fig.legend(h, lb, frameon=False, fontsize=8, loc="lower center", ncol=2,
               bbox_to_anchor=(0.5, 0.98))
    fig.text(0.99, -0.02, "PRELIMINARY", ha="right", va="top", fontsize=7, color=INK2)
    fig.savefig(HERE / "fig_circuit_vs_brain.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    size_curve()
    circuit_vs_brain()
    print("figures written")

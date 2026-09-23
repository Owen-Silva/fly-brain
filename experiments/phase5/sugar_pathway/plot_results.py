"""Figures for the Phase 5 sugar-pathway write-up (PNG, in results/).

fig_pathway.png      wiring diagram: sugar GRNs -> relay neurons -> MN9, the
                     strongest excitatory routes plus all 2-hop relays, each
                     neuron coloured by what silencing it did at 100 Hz.
fig_singles.png      every silenced neuron, sorted by effect (100 Hz and 50 Hz).
fig_vs_paper.png     our silencing effect vs the paper's (same neurons).
fig_groups.png       group silencing (named cell types, pathway sets, top-k).
"""
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ids import SUGAR, MN9  # noqa: E402

RES = HERE / "results"
SURF, INK, INK2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
CLS = {  # one blue ramp for "how much MN9 dropped", grey = no change, orange = went up
    "blocks": "#104281", "reduces (strong, >=20%)": "#2a78d6",
    "reduces (weak, <20%)": "#86b6ef", "redundant": "#b9b8b3", "increases": "#eb6834",
}
ORDER = list(CLS)
plt.rcParams.update({"figure.facecolor": SURF, "axes.facecolor": SURF, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
                     "text.color": INK, "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False})


def short(r):
    pn = r.get("paper_name") if isinstance(r.get("paper_name"), str) else ""
    ct = r.get("cell_type") if isinstance(r.get("cell_type"), str) else ""
    return pn or ct or str(r.get("root_id"))[-6:]


def legend(ax, present, loc="lower right"):
    hs = [plt.Line2D([], [], marker="o", ls="", ms=7, mfc=CLS[c], mec=SURF, label=c)
          for c in ORDER if c in present]
    ax.legend(handles=hs, frameon=False, loc=loc, fontsize=8)


def fig_singles(s):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), sharey=True)
    for ax, hz in zip(axes, (100, 50)):
        g = s[s["stim_hz"] == hz].sort_values("ratio").reset_index(drop=True)
        if g.empty:
            continue
        ax.axhline(1.0, color=GRID, lw=1, zorder=0)
        ax.axhline(0.8, color=INK2, lw=0.8, ls="--", zorder=0)
        ax.text(len(g) - 1, 0.8, " paper's 20% line", va="bottom", ha="right", fontsize=7, color=INK2)
        ax.scatter(np.arange(len(g)), g["ratio"], s=14, c=[CLS[c] for c in g["class"]],
                   edgecolors=SURF, linewidths=0.6, zorder=3)
        for i, r in g.head(4).iterrows():
            ax.annotate(short(r), (i, r["ratio"]), xytext=(45, 0.36 + 0.09 * i), textcoords="data",
                        fontsize=7, color=INK2, va="center",
                        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))
        b30 = g.loc[g["n_trials"] == 30, "mn9_base_hz"]
        ax.set_title(f"sugar GRNs at {hz} Hz: silence one neuron at a time "
                     f"(baseline MN9 {b30.iloc[0] if len(b30) else float('nan'):.1f} Hz)", fontsize=9, loc="left")
        ax.set_xlabel("silenced neurons, sorted by effect")
        legend(ax, set(g["class"]), loc="upper left")
    axes[0].set_ylabel("MN9 rate with neuron silenced / baseline")
    fig.tight_layout()
    fig.savefig(RES / "fig_singles.png", dpi=150)
    plt.close(fig)


def fig_vs_paper(s):
    fig, axes = plt.subplots(1, 2, figsize=(9, 4.2))
    for ax, hz, col in zip(axes, (100, 50), ("paper_ratio_100hz", "paper_ratio_50hz")):
        g = s[(s["stim_hz"] == hz) & s[col].notna()]
        if g.empty:
            continue
        lo = min(g["ratio"].min(), g[col].min(), 0.5) - 0.05
        hi = max(g["ratio"].max(), g[col].max(), 1.2) + 0.05
        ax.plot([lo, hi], [lo, hi], color=GRID, lw=1, zorder=0)
        ax.axhline(0.8, color=INK2, lw=0.6, ls="--")
        ax.axvline(0.8, color=INK2, lw=0.6, ls="--")
        ax.scatter(g[col], g["ratio"], s=16, c=[CLS[c] for c in g["class"]], edgecolors=SURF,
                   linewidths=0.6, zorder=3)
        for k, (_, r) in enumerate(g.nsmallest(3, "ratio").iterrows()):
            ax.annotate(short(r), (r[col], r["ratio"]), xytext=(8, -4 + 9 * k), textcoords="offset points",
                        fontsize=7, color=INK2, arrowprops=dict(arrowstyle="-", color=INK2, lw=0.5))
        r_ = np.corrcoef(g[col], g["ratio"])[0, 1]
        ax.set_title(f"{hz} Hz sugar: {len(g)} neurons both screens tested (r = {r_:.2f})",
                     fontsize=9, loc="left")
        ax.set_xlabel("paper (Shiu et al. 2024, Supp. Table 1C): MN9 / control")
        ax.set_ylabel("this project: MN9 / baseline")
        ax.set_xlim(lo, hi)
        ax.set_ylim(lo, hi)
        legend(ax, set(g["class"]), loc="upper left")
    fig.tight_layout()
    fig.savefig(RES / "fig_vs_paper.png", dpi=150)
    plt.close(fig)


def fig_groups(g):
    g = g[g["source"].isin(["named", "pathway", "topk"])].copy()
    if g.empty:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 0.22 * len(g) / 2 + 1.6), sharex=True)
    for ax, hz in zip(axes, (100, 50)):
        x = g[g["stim_hz"] == hz].sort_values("ratio", ascending=False)
        y = np.arange(len(x))
        ax.barh(y, x["ratio"], color=[CLS[c] for c in x["class"]], height=0.7, edgecolor=SURF)
        ax.set_yticks(y)
        ax.set_yticklabels(x["label"], fontsize=7)
        ax.axvline(1.0, color=GRID, lw=1)
        ax.axvline(0.8, color=INK2, lw=0.6, ls="--")
        ax.axvline(0.5, color=INK2, lw=0.6, ls=":")
        for yy, v in zip(y, x["ratio"]):
            ax.text(v + 0.02, yy, f"{v:.2f}", va="center", fontsize=6.5, color=INK2)
        ax.set_title(f"{hz} Hz sugar: silence a group at once", fontsize=9, loc="left")
        ax.set_xlabel("MN9 with group silenced / baseline")
    hs = [plt.Line2D([], [], marker="s", ls="", ms=7, mfc=CLS[c], mec=SURF, label=c) for c in ORDER]
    fig.legend(handles=hs, frameon=False, loc="lower center", ncol=5, fontsize=8)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(RES / "fig_groups.png", dpi=150)
    plt.close(fig)


def fig_pathway(s):
    """Layered diagram of the routes found by trace_paths.py."""
    nr = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                         columns=["root_id", "cell_type", "ref_sign"])
    nr["root_id"] = nr["root_id"].astype(np.int64)
    st = pd.read_csv(RES / "paths_strongest_MN9_main.csv")
    routes = st[st["variant"] == "exc_only_pooled"].head(12)["route_ids"].tolist()
    hop = pd.read_csv(RES / "paths_hops_MN9_main_all.csv")
    relays2 = hop[hop["hop_from_grn"] == 1]["root_id"].astype(np.int64).tolist()
    layer = {}
    edges = set()
    for r in routes:
        ids = r.split()
        for k, i in enumerate(ids):
            if i == "GRNS":
                continue
            i = int(i)
            layer[i] = min(layer.get(i, 99), k)
        for a, b in zip(ids[:-1], ids[1:]):
            edges.add((a, b))
    for i in relays2:
        layer[i] = min(layer.get(i, 99), 1)
        edges.add(("GRNS", str(i)))
        edges.add((str(i), str(MN9)))
    layer[MN9] = max(v for v in layer.values()) + 1 if layer else 3
    lab = nr.set_index("root_id")
    sil = s[s["stim_hz"] == 100].set_index("root_id") if not s.empty else pd.DataFrame()
    from trace_paths import paper_name_map
    names = paper_name_map()
    nodes = {"GRNS": 0}
    nodes.update({str(k): v for k, v in layer.items()})
    nodes[str(MN9)] = layer[MN9]
    cols = {}
    for n_, L in nodes.items():
        cols.setdefault(L, []).append(n_)
    pos = {}
    for L, ns in cols.items():
        ns.sort(key=lambda z: (names.get(int(z), "zz") if z != "GRNS" else ""))
        for k, n_ in enumerate(ns):
            pos[n_] = (L, (k - (len(ns) - 1) / 2) * 1.0)
    # synapse counts for the drawn connections (GRNs pooled)
    import pyarrow.parquet as pq
    from matplotlib.patches import FancyArrowPatch
    idx = pd.Series(np.arange(len(nr)), index=nr["root_id"])
    node_ids = [int(z) for z in nodes if z != "GRNS"]
    pre_idx = [int(idx[i]) for i in node_ids] + [int(idx[i]) for i in SUGAR]
    tb = pq.read_table(ROOT / "data" / "cache" / "connectome_630_edges.parquet",
                       columns=["pre", "post", "syn_count"], filters=[("pre", "in", pre_idx)]).to_pandas()
    rid = nr["root_id"].to_numpy()
    tb["pre_id"] = rid[tb["pre"]]
    tb["post_id"] = rid[tb["post"]]
    tb["pre_key"] = np.where(tb["pre_id"].isin(SUGAR), "GRNS", tb["pre_id"].astype(str))
    syn = tb.groupby(["pre_key", "post_id"])["syn_count"].sum()
    fig, ax = plt.subplots(figsize=(11, max(4.5, 0.42 * max(len(v) for v in cols.values()) + 1.5)))
    for a, b in edges:
        if a in pos and b in pos:
            (x0, y0), (x1, y1) = pos[a], pos[b]
            n_syn = int(syn.get((a, int(b)), 0))
            same = abs(x0 - x1) < 1e-9
            ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=7,
                                         connectionstyle=f"arc3,rad={0.5 if same else 0.0}",
                                         color="#bdbcb6", lw=0.4 + 0.25 * np.sqrt(n_syn),
                                         shrinkA=7, shrinkB=7, zorder=1))
    for n_, (x, y) in pos.items():
        if n_ == "GRNS":
            ax.scatter(x, y, s=500, c="#1baf7a", edgecolors=INK2, zorder=3)
            ax.text(x - 0.08, y, "21 sugar GRNs\n(stimulated)", ha="right", va="center", fontsize=8)
            continue
        i = int(n_)
        if i == MN9:
            ax.scatter(x, y, s=500, c="#eda100", edgecolors=INK2, zorder=3)
            ax.text(x + 0.08, y, "MN9\n(feeding motor neuron)", ha="left", va="center", fontsize=8)
            continue
        cls = sil.loc[i, "class"] if i in sil.index else "redundant"
        inhib = lab.loc[i, "ref_sign"] < 0
        ax.scatter(x, y, s=150, c=CLS[cls], edgecolors=INK if inhib else SURF,
                   linewidths=1.6 if inhib else 0.8, marker="s" if inhib else "o", zorder=3)
        nm = names.get(i) or (lab.loc[i, "cell_type"] if isinstance(lab.loc[i, "cell_type"], str) else str(i)[-6:])
        ratio = f" {sil.loc[i, 'ratio']:.2f}" if i in sil.index else ""
        ax.text(x, y + 0.28, f"{nm}{ratio}", ha="center", va="bottom", fontsize=6.5, color=INK2)
    hs = [plt.Line2D([], [], marker="o", ls="", ms=7, mfc=CLS[c], mec=SURF, label=f"silencing {c}")
          for c in ORDER if c in set(sil.get("class", []))]
    hs.append(plt.Line2D([], [], marker="s", ls="", ms=7, mfc="white", mec=INK, label="inhibitory neuron"))
    ax.legend(handles=hs, frameon=False, fontsize=7, loc="lower center", ncol=3,
              bbox_to_anchor=(0.5, -0.16))
    ax.set_axis_off()
    ax.set_title("Sugar -> MN9: 12 strongest excitatory routes + every 2-hop relay. Line width ~ synapse count;\n"
                 "number = MN9 rate with that neuron silenced / baseline (sugar at 100 Hz)", fontsize=9, loc="left")
    ax.autoscale_view()
    fig.tight_layout()
    fig.savefig(RES / "fig_pathway.png", dpi=150, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    s = pd.read_csv(RES / "silencing_singles.csv") if (RES / "silencing_singles.csv").exists() else pd.DataFrame()
    if not s.empty:
        fig_singles(s)
        fig_vs_paper(s)
    if (RES / "silencing_groups.csv").exists():
        fig_groups(pd.read_csv(RES / "silencing_groups.csv"))
    fig_pathway(s)
    print("figures written")

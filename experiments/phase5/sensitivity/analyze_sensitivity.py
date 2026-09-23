"""Turn the cached sensitivity runs into tables, verdicts and plots.

Reads only experiments/phase5/sensitivity/cache/ (no simulation, no brain
load), so it can be run at any time, also on a partly finished sweep:
variations whose 3 seeds are not all on disk yet are left out and listed.

Writes to experiments/phase5/sensitivity/results/:
  table.csv       tidy: one row per (variation, seed, readout)
  verdicts.csv    holds / flips per (claim, variation), with the rule
  summary.csv     per variation: mean over seeds, sd, % change from baseline
  ranking.csv     Spearman + overlap of the top-50 downstream neurons
  summary.json    the key numbers quoted in docs/phase5-sensitivity.md
and the plots tornado.png, mn9_vs_change.png, ranking.png next to it.
"""

import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[2]))
sys.path.insert(0, str(HERE))

from sim import validation as V  # noqa: E402
from run_sensitivity import (CACHE, CLAIMS, SEEDS, STIMULATED, MAX_RATIO, ON_HZ,  # noqa: E402
                             make_experiment, ordered_variations)

OUT = HERE / "results"
CONDS = [("sugar", "Sugar 100 Hz"), ("water", "Water 200 Hz"),
         ("sugar_bitter", "Sugar 100 Hz + bitter 120 Hz")]
LABELS = {
    "w_syn": "Synaptic weight",
    "threshold_gap": "Threshold gap (rest to threshold)",
    "t_mbr": "Membrane time constant",
    "tau": "Synaptic time constant",
    "t_rfc": "Refractory period",
    "t_dly": "Synaptic delay",
    "r_poi": "Poisson input rate",
    "weight_jitter": "Every weight jittered ±20%",
}
# colours: diverging blue (lower) / red (higher); neutral greys for context
C_LO, C_LO10, C_HI, C_HI10 = "#2a78d6", "#86b6ef", "#e34948", "#f2a09f"
C_GREY, C_INK, C_INK2, C_BAND = "#8a8984", "#0b0b0b", "#52514e", "#e6e5e1"
C_COND = {"sugar": "#2a78d6", "water": "#1baf7a", "sugar_bitter": "#eb6834"}


def complete_variations():
    """Variations with every seed on disk (so a partial sweep can be analysed)."""
    have, missing = [], []
    for v in ordered_variations():
        files = [V._cache_file(CACHE, v, s) for s in SEEDS]
        (have if all(f.exists() for f in files) else missing).append(v)
    return have, missing


def style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color("#bdbcb6")
    ax.tick_params(colors=C_INK2, labelsize=8.5)
    ax.grid(axis="x", color="#ecebe7", linewidth=0.8)
    ax.set_axisbelow(True)


def main():
    OUT.mkdir(exist_ok=True)
    have, missing = complete_variations()
    if missing:
        print(f"NOTE: {len(missing)} variation(s) not finished yet, left out: "
              + ", ".join(v.name for v in missing))

    def not_cached(brain, params, seed):
        raise RuntimeError("analysis reads the cache only")

    res = V.run_validation(not_cached, have, seeds=SEEDS, claims=CLAIMS, cache_dir=CACHE, log=None)
    res.table.to_csv(OUT / "table.csv", index=False)
    verdicts = res.verdicts
    verdicts.to_csv(OUT / "verdicts.csv", index=False)

    # ---- summary table -------------------------------------------------------
    keys = ["sugar_mn9", "water_mn9", "sugar_bitter_mn9", "bitter_ratio",
            "sugar_active", "water_active", "sugar_bitter_active"]
    parts = []
    for k in keys:
        s = res.summary(k)[["mean", "sd_over_seeds", "change_pct"]]
        parts.append(s.add_prefix(k + "_"))
    meta = pd.DataFrame([{"variation": v.name, "parameter": v.parameter, "change": v.change,
                          "note": v.note, **V.effective_steps(v.params)} for v in have]
                        ).set_index("variation")
    summary = meta.join(pd.concat(parts, axis=1))
    summary.to_csv(OUT / "summary.csv", float_format="%.4g")

    # ---- top-50 ranking change ---------------------------------------------
    rk = []
    for cond, _ in CONDS:
        r = res.ranking_change(f"{cond}_rates", k=50, exclude=STIMULATED[cond])
        r.insert(0, "condition", cond)
        rk.append(r)
    ranking = pd.concat(rk, ignore_index=True)
    ranking.to_csv(OUT / "ranking.csv", index=False, float_format="%.4g")

    # ---- noise floor: 6 baseline seeds (3 original + 3 new) ------------------
    t = res.table
    base6 = t[t["variation"].isin(["baseline", "baseline_new_seeds"])]
    noise = {}
    for cond, _ in CONDS:
        vals = base6[base6["readout"] == f"{cond}_mn9"]["value"]
        # 2 standard errors of the difference between two 3-seed means, in %
        noise[cond] = float(2 * vals.std(ddof=1) * np.sqrt(2 / 3) / vals.mean() * 100)
    ratio6 = base6[base6["readout"] == "bitter_ratio"]["value"]
    noise["bitter_ratio_pts"] = float(2 * ratio6.std(ddof=1) * np.sqrt(2 / 3) * 100)

    # ---- key numbers --------------------------------------------------------
    key = {"variations_done": len(have), "variations_missing": [v.name for v in missing],
           "seeds": list(SEEDS), "trials_per_seed": 30, "on_hz": ON_HZ, "max_ratio": MAX_RATIO,
           "verdict_rule": V.VERDICT_RULE, "noise_2se_pct": noise, "claims": {}}
    for cname, claim in CLAIMS.items():
        vc = verdicts[verdicts["claim"] == cname]
        key["claims"][cname] = {
            "rule": claim.text, "robust": res.robust(cname),
            "flips": vc[vc["verdict"] == "flips"][["variation", "seeds_holding"]].values.tolist(),
            "identical_to_baseline": vc[vc["identical_to_baseline"]]["variation"].tolist()}
    for k in ("sugar_mn9", "water_mn9", "sugar_bitter_mn9", "bitter_ratio"):
        s = summary[f"{k}_mean"]
        key[k] = {"baseline": float(s["baseline"]),
                  "min": [float(s.min()), s.idxmin()], "max": [float(s.max()), s.idxmax()]}
    # how the verdicts would change with other cut-offs (the cut-offs are a choice)
    alt = {}
    for hz in (1.0, 5.0, 10.0):
        alt[f"sugar_on_{hz:g}Hz"] = V.at_least("sugar_mn9", hz)
        alt[f"water_on_{hz:g}Hz"] = V.at_least("water_mn9", hz)
    for ratio in (0.25, 0.5, 0.75):
        alt[f"bitter_ratio_{ratio:g}"] = V.suppressed("sugar_bitter_mn9", "sugar_mn9", ratio, ON_HZ)
    av = V.ValidationResult(table=res.table, vectors={}, variations=have, claims=alt).verdicts
    key["cutoff_sensitivity"] = {c: av[(av["claim"] == c) & (av["verdict"] == "flips")][
        "variation"].tolist() for c in alt}
    key["ranking_min"] = {c: ranking[ranking["condition"] == c].nsmallest(3, "spearman_top50")[
        ["variation", "spearman_top50", "overlap_top50"]].values.tolist() for c, _ in CONDS}
    key["ranking_noise_floor"] = {c: ranking[(ranking["condition"] == c) & (
        ranking["variation"] == "baseline_new_seeds")][["spearman_top50", "overlap_top50"]
    ].values.tolist() for c, _ in CONDS}
    (OUT / "summary.json").write_text(json.dumps(key, indent=1, default=str))

    params = [p for p in V.PARAMETER_RULES if (summary["parameter"] == p).any()]
    jit = summary[summary["parameter"] == "weight_jitter"]
    if params:
        plot_tornado(summary, params, jit, noise, verdicts)
        plot_curves(summary, params)
        plot_ranking(ranking, params)
    else:
        print("NOTE: no parameter variations finished yet; plots skipped")
    print(json.dumps({c: key["claims"][c]["robust"] for c in CLAIMS}))
    print("wrote", OUT)


def _value(summary, param, change, col):
    m = summary[(summary["parameter"] == param) & np.isclose(summary["change"], change)]
    return float(m[col].iloc[0]) if len(m) else np.nan


def plot_tornado(summary, params, jit, noise, verdicts):
    """Three panels; each row is one parameter: bars to the -20% (blue) and
    +20% (red) values, dots at -10% / +10%, grey band = seed noise."""
    panels = [("sugar_mn9_change_pct", "sugar", "Sugar → MN9\nchange in MN9 rate (%)"),
              ("water_mn9_change_pct", "water", "Water → MN9\nchange in MN9 rate (%)"),
              ("bitter_ratio_mean", "bitter", "Bitter + sugar → MN9\nMN9 as % of sugar alone")]
    # order rows by the biggest swing in the sugar panel
    swing = {p: abs(_value(summary, p, 0.2, panels[0][0]) - _value(summary, p, -0.2, panels[0][0]))
             for p in params}
    rows = sorted(params, key=lambda p: -np.nan_to_num(swing[p]))
    has_jit = len(jit) > 0
    labels = [LABELS[p] for p in rows] + ([LABELS["weight_jitter"]] if has_jit else [])
    y = np.arange(len(labels))[::-1]
    fig, axes = plt.subplots(1, 3, figsize=(13, 0.52 * len(labels) + 2.2), sharey=True)
    for ax, (col, which, title) in zip(axes, panels):
        style(ax)
        is_ratio = which == "bitter"
        scale = 100.0 if is_ratio else 1.0
        base = _value(summary, "baseline", 0.0, col) * scale if is_ratio else 0.0
        half = noise["bitter_ratio_pts"] if is_ratio else noise[which]
        ax.axvspan(base - half, base + half, color=C_BAND, zorder=0, lw=0)
        ax.axvline(base, color=C_INK2, lw=1)
        if is_ratio:
            ax.axvline(MAX_RATIO * 100, color=C_INK, lw=1, ls="--")
            ax.text(MAX_RATIO * 100 - 1, float(np.mean(y)), "claim fails past this line",
                    fontsize=7.5, color=C_INK, va="center", ha="right", rotation=90)
        claim = {"sugar": "sugar_on", "water": "water_on", "bitter": "bitter_suppresses"}[which]
        flips = set(verdicts[(verdicts["claim"] == claim) & (verdicts["verdict"] == "flips")]
                    ["variation"])
        for yi, p in zip(y, rows):
            # upper half-row: setting lowered (blue); lower half-row: raised (red)
            for dy, big, small, c_big, c_small in ((0.17, -0.2, -0.1, C_LO, C_LO10),
                                                   (-0.17, 0.2, 0.1, C_HI, C_HI10)):
                v = _value(summary, p, big, col) * scale
                v10 = _value(summary, p, small, col) * scale
                if np.isfinite(v):
                    ax.barh(yi + dy, v - base, left=base, height=0.3, color=c_big, zorder=2)
                    if f"{p}{big:+.0%}" in flips:
                        ax.text(v, yi + dy, " flips " if v >= base else " flips ", fontsize=7.5,
                                color=C_INK, va="center", fontweight="bold",
                                ha="left" if v >= base else "right")
                if np.isfinite(v10):
                    ax.plot(v10, yi + dy, "o", ms=5.5, color=c_small, mec="white", mew=1.0,
                            zorder=3)
        if has_jit:
            vals = jit[col].to_numpy() * scale
            ax.plot([vals.min(), vals.max()], [y[-1], y[-1]], color=C_GREY, lw=2, zorder=2)
            ax.plot(vals, np.full(vals.size, y[-1]), "o", ms=6.5, color=C_GREY,
                    mec="white", mew=1.2, zorder=3)
            n_flip = sum(name in flips for name in jit.index)
            if n_flip:
                ax.text(vals.min(), y[-1] + 0.3, f"{n_flip} of {len(vals)} flip", fontsize=7.5,
                        color=C_INK, fontweight="bold", ha="left", va="bottom")
        ax.set_title(title, fontsize=10, color=C_INK, loc="left")
        if is_ratio:
            ax.set_xlim(left=0)
    axes[0].set_yticks(y, labels, fontsize=9, color=C_INK)
    handles = [plt.Rectangle((0, 0), 1, 1, color=C_LO), plt.Rectangle((0, 0), 1, 1, color=C_HI),
               plt.Line2D([], [], marker="o", ls="", color=C_LO10, ms=6.5),
               plt.Line2D([], [], marker="o", ls="", color=C_HI10, ms=6.5),
               plt.Line2D([], [], marker="o", ls="-", color=C_GREY, ms=6.5),
               plt.Rectangle((0, 0), 1, 1, color=C_BAND)]
    fig.legend(handles, ["setting −20%", "setting +20%", "−10%", "+10%",
                         "jitter: each random pattern", "random-seed noise (±2 SE)"],
               loc="lower center", ncol=6, frameon=False, fontsize=8.5)
    fig.suptitle("How much MN9 moves when one model setting changes (30 trials x 3 seeds per bar)",
                 fontsize=11, color=C_INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(HERE / "tornado.png", dpi=150, facecolor="white")
    plt.close(fig)


def plot_curves(summary, params):
    """Small multiples: MN9 rate (Hz) against the % change of each setting."""
    n = len(params)
    ncol = 4
    nrow = int(np.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(13, 3.0 * nrow + 0.8), sharey=True)
    axes = np.atleast_1d(axes).ravel()
    xs = [-0.2, -0.1, 0.0, 0.1, 0.2]
    for ax, p in zip(axes, params):
        style(ax)
        ax.grid(axis="y", color="#ecebe7", linewidth=0.8)
        ax.axhline(ON_HZ, color=C_INK2, lw=1, ls="--")
        for cond, label in CONDS:
            m = [_value(summary, p if x else "baseline", x, f"{cond}_mn9_mean") for x in xs]
            sd = [_value(summary, p if x else "baseline", x, f"{cond}_mn9_sd_over_seeds")
                  for x in xs]
            ax.errorbar(np.array(xs) * 100, m, yerr=sd, color=C_COND[cond], lw=2, marker="o",
                        ms=5, capsize=0, label=label)
        ax.set_title(LABELS[p], fontsize=9.5, color=C_INK, loc="left")
        ax.set_xticks([-20, -10, 0, 10, 20], ["−20%", "−10%", "0", "+10%", "+20%"])
    for ax in axes[n:]:
        ax.axis("off")
    for ax in axes[::ncol]:
        ax.set_ylabel("MN9 rate (Hz)", fontsize=9, color=C_INK2)
    axes[0].text(20, ON_HZ + 1.5, "'on' cut-off 5 Hz", fontsize=7.5, color=C_INK2, ha="right")
    h, lab = axes[0].get_legend_handles_labels()
    fig.legend(h, lab, loc="lower center", ncol=3, frameon=False, fontsize=9)
    fig.suptitle("MN9 firing rate as each setting changes (dots: mean of 3 seeds x 30 trials;"
                 " whiskers: sd over seeds)", fontsize=11, color=C_INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(HERE / "mn9_vs_change.png", dpi=150, facecolor="white")
    plt.close(fig)


def plot_ranking(ranking, params):
    """Spearman correlation of the top-50 most active downstream neurons."""
    rows = params + (["weight_jitter"] if (ranking["parameter"] == "weight_jitter").any() else [])
    y = np.arange(len(rows))[::-1]
    fig, axes = plt.subplots(1, 3, figsize=(13, 0.5 * len(rows) + 2.2), sharey=True,
                             sharex=True)
    colors = {-0.2: C_LO, -0.1: C_LO10, 0.1: C_HI10, 0.2: C_HI}
    for ax, (cond, label) in zip(axes, CONDS):
        style(ax)
        r = ranking[ranking["condition"] == cond]
        floor = r[r["variation"] == "baseline_new_seeds"]["spearman_top50"]
        if len(floor):
            ax.axvline(float(floor.iloc[0]), color=C_INK2, lw=1, ls="--")
        for yi, p in zip(y, rows):
            rp = r[r["parameter"] == p]
            if p == "weight_jitter":
                ax.plot(rp["spearman_top50"], np.full(len(rp), yi), "o", ms=6.5, color=C_GREY,
                        mec="white", mew=1.2)
                continue
            for _, row in rp.iterrows():
                ax.plot(row["spearman_top50"], yi, "o", ms=7, mec="white", mew=1.2,
                        color=colors[round(row["change"], 1)])
        ax.set_title(label, fontsize=10, color=C_INK, loc="left")
        ax.set_xlabel("Spearman vs baseline (1 = same order)", fontsize=8.5, color=C_INK2)
        ax.set_xlim(min(0.5, float(ranking["spearman_top50"].min()) - 0.02), 1.01)
    axes[0].set_yticks(y, [LABELS[p] for p in rows], fontsize=9, color=C_INK)
    handles = [plt.Line2D([], [], marker="o", ls="", color=c, ms=7) for c in colors.values()]
    handles += [plt.Line2D([], [], marker="o", ls="", color=C_GREY, ms=7),
                plt.Line2D([], [], color=C_INK2, ls="--")]
    fig.legend(handles, ["−20%", "−10%", "+10%", "+20%", "jitter pattern",
                         "same model, new random seeds"],
               loc="lower center", ncol=6, frameon=False, fontsize=8.5)
    fig.suptitle("Does the order of the 50 most active downstream neurons survive? "
                 "(stimulated neurons excluded)", fontsize=11, color=C_INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.06, 1, 0.95))
    fig.savefig(HERE / "ranking.png", dpi=150, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()

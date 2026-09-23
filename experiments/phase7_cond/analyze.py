"""Summarise the conductance-on-top-of-the-sign-fix runs (docs/phase7-conductance.md).

Plain English
-------------
Reads results/trials.csv (this lane) and the sign-fix lane's trials and
per-neuron counts for the "fix only" model (experiments/phase7_signs/results,
config al_ln_literature: same seeds, same inputs, current-based synapses), and
writes:
  results/table_mn9.csv        MN9 (feeding motor neuron) rate per config, condition, seed
  results/table_runaway.csv    runaway trials (Phase 6 definition: > 1,500 different
                               neurons fire in some 10 ms slice), with 95% ranges and
                               Fisher's test against the fix-only model
  results/table_checks.csv     the Phase 3 checks, pass/fail per seed
  results/table_neurons.csv    neuron-by-neuron comparison with the fix-only model
  results/summary.md           all of the above as text tables
  plots/*.png
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))
import common as C  # noqa: E402

RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)
SIGNS = ROOT / "experiments" / "phase7_signs" / "results"
FIXONLY = "fix_only"
VOLLEYS = RES / "volleys.csv"
TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
ORDER = TASTE + ["ir94e_200Hz", "dm1_both_150Hz"]


def load_trials():
    d = pd.read_csv(RES / "trials.csv")
    s = pd.read_csv(SIGNS / "trials.csv")
    s = s[s.config == "al_ln_literature"].copy()
    s["config"] = FIXONLY
    cols = [c for c in d.columns if c in s.columns]
    return pd.concat([s[cols], d[cols]], ignore_index=True)


def wilson(k, n, z=1.96):
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (max(0.0, c - h), min(1.0, c + h))


def counts_for(config, cond, k):
    f = (SIGNS / "counts" / f"al_ln_literature__{cond}__s{k}.npz") if config == FIXONLY \
        else (RES / "counts" / f"{config}__{cond}__s{k}.npz")
    if not f.exists():
        return None
    z = np.load(f)
    return z


def dense(z, n):
    out = np.zeros(n, np.float64)
    out[z["nz_idx"]] = z["nz_count"]
    return out / float(z["n_trials"])


def compare(ra, rb, keep, k=50):
    act = keep & ((ra > 0) | (rb > 0))
    r = float(np.corrcoef(ra[act], rb[act])[0, 1]) if act.sum() > 2 else float("nan")
    ta = set(np.argsort(-np.where(keep, ra, -1))[:k])
    tb = set(np.argsort(-np.where(keep, rb, -1))[:k])
    return r, len(ta & tb), int(act.sum())


def md(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for _, row in df.iterrows():
        lines.append("| " + " | ".join(f"{v:.3g}" if isinstance(v, float) else str(v)
                                        for v in row) + " |")
    return "\n".join(lines)


def main():
    from sim import sign_fixes as S
    d = load_trials()
    # root IDs only (cheap): the completeness file that load_reference_arrays reads first,
    # so the whole connection list is not loaded next to a running simulation
    rid = pd.read_csv(S.REFERENCE_DIR / S.SNAPSHOTS["630"][0], index_col=0).index.to_numpy()
    n = rid.size
    lab = S.neuron_table(rid)
    sets = C.input_sets(lab)
    configs = [FIXONLY] + [c for c in pd.read_csv(RES / "trials.csv").config.unique()]
    out = ["# Conductance synapses on top of the sign fix: summary (PRELIMINARY)\n",
           "fix_only = sign fix al_ln_literature with the paper's current-based synapses "
           "(numbers from experiments/phase7_signs). Runaway = more than 1,500 different "
           "neurons fire in some 10 ms slice (Phase 6 definition).\n"]

    # --- MN9 and activity per config / condition / seed ---
    g = d.groupby(["config", "condition", "seed_index"])
    t = g.agg(n=("trial", "size"), mn9_hz=("mn9_hz", "mean"), mn9_ipsi_hz=("mn9_ipsi_hz", "mean"),
              runaway=("runaway", "sum"), median_spikes=("total_spikes", "median"),
              max_distinct_10ms=("max_distinct_10ms", "max")).reset_index()
    t.to_csv(RES / "table_mn9.csv", index=False)

    # --- runaway table ---
    fx = d[d.config == FIXONLY]
    fx_med = fx.groupby("condition").total_spikes.median()
    rows = []
    for cfg in configs:
        for cond in ORDER:
            x = d[(d.config == cfg) & (d.condition == cond)]
            if x.empty:
                continue
            k, nn = int(x.runaway.sum()), len(x)
            lo, hi = wilson(k, nn)
            per = "/".join(str(int(x[x.seed_index == s].runaway.sum())) for s in sorted(x.seed_index.unique()))
            f = fx[fx.condition == cond]
            p = fisher_exact([[k, nn - k], [int(f.runaway.sum()), len(f) - int(f.runaway.sum())]])[1] \
                if cfg != FIXONLY and len(f) else np.nan
            big5 = int((x.total_spikes > 5 * fx_med.get(cond, np.inf)).sum())
            rows.append(dict(config=cfg, condition=cond, runaway=f"{k}/{nn}", per_seed=per,
                             ci95=f"{100 * lo:.1f}-{100 * hi:.1f}%", fisher_p_vs_fix_only=p,
                             mn9_hz=x.mn9_hz.mean(), median_spikes=x.total_spikes.median(),
                             median_vs_fix_only=x.total_spikes.median() / fx_med.get(cond, np.nan),
                             over_5x_fix_only_median=f"{big5}/{nn}"))
    rt = pd.DataFrame(rows)
    rt.to_csv(RES / "table_runaway.csv", index=False)
    out += ["## Runaway and activity (all trials)\n", md(rt), ""]

    # --- Phase 3 checks per seed ---
    crow = []
    for cfg in configs:
        x = t[t.config == cfg]
        if not set(TASTE) <= set(x.condition):
            continue
        for s in sorted(x.seed_index.unique()):
            m = {c: x[(x.condition == c) & (x.seed_index == s)].mn9_hz.values for c in TASTE}
            mi = {c: x[(x.condition == c) & (x.seed_index == s)].mn9_ipsi_hz.values for c in TASTE}
            if any(v.size == 0 for v in m.values()):
                continue
            m = {c: float(v[0]) for c, v in m.items()}
            mi = {c: float(v[0]) for c, v in mi.items()}
            crow.append({"config": cfg, "seed": s,
                         "sugar100 >= 20 Hz": m["sugar_100Hz"] >= 20,
                         "sugar200 > sugar100": m["sugar_200Hz"] > m["sugar_100Hz"],
                         "contra > ipsi": (m["sugar_100Hz"] > mi["sugar_100Hz"])
                         and (m["sugar_200Hz"] > mi["sugar_200Hz"]),
                         "water >= 5 Hz and < sugar200": 5 <= m["water_200Hz"] < m["sugar_200Hz"],
                         "bitter <= 1 Hz": m["bitter_200Hz"] <= 1.0,
                         "sugar+bitter <= 10% sugar": m["sugar100_bitter120"] <= 0.1 * m["sugar_100Hz"],
                         **{f"MN9 {c}": round(m[c], 2) for c in TASTE}})
    if crow:
        ct = pd.DataFrame(crow)
        ct.to_csv(RES / "table_checks.csv", index=False)
        out += ["## Phase 3 checks (MN9, per seed; a check holds only if it passes for every seed)\n",
                md(ct), ""]

    # --- neuron by neuron vs fix-only ---
    nrow = []
    for cond in ORDER:
        stim = np.zeros(n, bool)
        for s, _ in C.CONDITIONS[cond][0]:
            stim[np.isin(rid, sets[s])] = True
        keep = ~stim
        fz = [counts_for(FIXONLY, cond, k) for k in (0, 1, 2)]
        if any(z is None for z in fz):
            continue
        fr = [dense(z, n) for z in fz]
        # noise floor: fix-only seed vs fix-only other seed (30 vs 30 trials)
        nf = [compare(fr[a], fr[b], keep) for a, b in ((0, 1), (0, 2), (1, 2))]
        nrow.append(dict(config="noise floor (fix_only seed vs seed)", condition=cond, seeds=3,
                         pearson_r_per_seed=np.mean([x[0] for x in nf]),
                         top50_per_seed=np.mean([x[1] for x in nf]),
                         pearson_r_pooled=np.nan, top50_pooled=np.nan))
        fpool = np.mean(fr, axis=0)
        for cfg in configs[1:]:
            cz = {k: counts_for(cfg, cond, k) for k in (0, 1, 2)}
            cz = {k: z for k, z in cz.items() if z is not None}
            if not cz:
                continue
            cr = {k: dense(z, n) for k, z in cz.items()}
            per = [compare(fr[k], cr[k], keep) for k in cr]
            pooled = compare(fpool, np.mean(list(cr.values()), axis=0), keep) \
                if len(cr) == 3 else (np.nan, np.nan, 0)
            nrow.append(dict(config=cfg, condition=cond, seeds=len(cr),
                             pearson_r_per_seed=np.mean([x[0] for x in per]),
                             top50_per_seed=np.mean([x[1] for x in per]),
                             pearson_r_pooled=pooled[0], top50_pooled=pooled[1]))
    if nrow:
        nt = pd.DataFrame(nrow)
        nt.to_csv(RES / "table_neurons.csv", index=False)
        out += ["## Neuron by neuron vs the fix-only model (stimulated neurons left out)\n",
                "per_seed: seed k of this model vs seed k of fix-only (same inputs), 30 vs 30 "
                "trials, averaged over the 3 seeds; pooled: 90 vs 90 trials. Noise floor: "
                "fix-only seed vs another fix-only seed (30 vs 30).\n", md(nt), ""]

    # --- sensitivity (+-10%), seed 0 only, same inputs for every config ---
    sens = ["fix_only", "sep", "sep_exc0.9", "sep_exc1.1", "sep_inh0.9", "sep_inh1.1",
            "sep_all0.9", "sep_all1.1", "cur_ref", "cur_exc0.9", "cur_exc1.1",
            "cur_inh0.9", "cur_inh1.1"]
    t0 = t[t.seed_index == 0]
    srow = []
    for cfg in sens:
        x = t0[t0.config == cfg].set_index("condition")
        if not set(TASTE) <= set(x.index):
            continue
        m = x.mn9_hz
        fx0 = t0[t0.config == FIXONLY].set_index("condition")
        checks = [m["sugar_100Hz"] >= 20, m["sugar_200Hz"] > m["sugar_100Hz"],
                  (m["sugar_100Hz"] > x.mn9_ipsi_hz["sugar_100Hz"])
                  and (m["sugar_200Hz"] > x.mn9_ipsi_hz["sugar_200Hz"]),
                  5 <= m["water_200Hz"] < m["sugar_200Hz"], m["bitter_200Hz"] <= 1.0,
                  m["sugar100_bitter120"] <= 0.1 * m["sugar_100Hz"]]
        names = ["sugar100>=20", "sugar200>sugar100", "contra>ipsi", "water", "bitter",
                 "sugar+bitter<=10%"]
        conds = [c for c in ORDER if c in x.index]
        srow.append(dict(config=cfg,
                         **{f"MN9 {c}": round(float(m[c]), 2) for c in TASTE},
                         sugar_bitter_pct=round(100 * m["sugar100_bitter120"] / m["sugar_100Hz"], 1),
                         checks_passed=f"{sum(map(bool, checks))}/6",
                         failed=", ".join(n for n, ok in zip(names, checks) if not ok) or "-",
                         runaways=f"{int(x.runaway[conds].sum())}/{30 * len(conds)}",
                         activity_vs_fix_only=round(float(np.median(
                             [x.median_spikes[c] / fx0.median_spikes[c] for c in conds
                              if c in fx0.index])), 2)))
    if srow:
        st = pd.DataFrame(srow)
        st.to_csv(RES / "table_sensitivity.csv", index=False)
        out += ["## Sensitivity (seed 0 x 30 trials; same inputs for every row)\n",
                "sep_* = the chosen conductance setting with one scale changed (exc/inh) or both "
                "(all); cur_* = the paper's current-based synapses (fix only) written as a "
                "conductance model with far-away reversal potentials, with its excitatory or "
                "inhibitory synapses scaled. activity_vs_fix_only = median over conditions of "
                "(median spikes per trial / fix-only's).\n", md(st), ""]

    # --- calibration points ---
    if (RES / "fit.csv").exists():
        ft = pd.read_csv(RES / "fit.csv")
        out += ["## Calibration points (sugar 100 Hz, seed 900; target MN9 65.7 Hz)\n", md(ft), ""]

    # --- one-spike triggers ---
    if VOLLEYS.exists():
        v = pd.read_csv(VOLLEYS)
        sv = pd.read_csv(SIGNS / "volleys.csv")
        sv = sv[sv.config == "al_ln_literature"].assign(config=FIXONLY)
        v = pd.concat([sv, v], ignore_index=True)[["config", "trigger", "total_spikes",
                                                   "max_distinct_10ms", "runaway"]]
        v.to_csv(RES / "table_volleys.csv", index=False)
        out += ["## One-spike triggers (one 1 s run each)\n", md(v), ""]

    plots(d, t, configs)
    (RES / "summary.md").write_text("\n".join(out), encoding="utf-8")
    print("\n".join(out))


BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
LABEL = {FIXONLY: "fix only (paper's synapses)", "g2": "conductance, one scale x2",
         "sep": "conductance, separate scales (1.2 / 0.87)"}


def _style(ax):
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_color(INK2)
    ax.tick_params(colors=INK2)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)


def plots(d, t, configs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    show = [c for c in (FIXONLY, "g2", "sep") if c in configs]
    cols = dict(zip((FIXONLY, "g2", "sep"), (BLUE, ORANGE, AQUA)))
    names = {"sugar_100Hz": "sugar 100", "sugar_200Hz": "sugar 200", "water_200Hz": "water 200",
             "bitter_200Hz": "bitter 200", "sugar100_bitter120": "sugar 100\n+ bitter 120",
             "ir94e_200Hz": "Ir94e 200", "dm1_both_150Hz": "DM1 smell\n150"}
    for fname, conds, col, ylab, title in (
            ("fig1_mn9.png", TASTE, "mn9_hz", "MN9 firing rate (Hz)",
             "Feeding motor neuron MN9 in the Phase 3 checks (bars: mean; lines: seed range)"),
            ("fig2_activity.png", ORDER, "median_spikes", "median spikes per trial (whole brain)",
             "Everyday activity of the whole brain (bars: mean of seeds; lines: seed range)")):
        fig, ax = plt.subplots(figsize=(9, 4.2), dpi=130)
        w = 0.8 / max(1, len(show))
        for j, cfg in enumerate(show):
            for i, cond in enumerate(conds):
                x = t[(t.config == cfg) & (t.condition == cond)][col]
                if x.empty:
                    continue
                xpos = i + (j - (len(show) - 1) / 2) * w
                ax.bar(xpos, x.mean(), w * 0.92, color=cols[cfg],
                       label=LABEL[cfg] if i == 0 else None)
                ax.vlines(xpos, x.min(), x.max(), color=INK, lw=1)
        if col == "mn9_hz":
            ax.axhline(65.7, color=INK2, ls="--", lw=1)
            ax.text(len(conds) - 0.5, 66.5, "paper: 65.7 Hz at sugar 100", ha="right",
                    va="bottom", color=INK2, fontsize=8)
        ax.set_xticks(range(len(conds)), [names[c] for c in conds], fontsize=8)
        ax.set_ylabel(ylab, color=INK2)
        ax.set_title(title, color=INK, fontsize=10, loc="left")
        _style(ax)
        ax.legend(frameon=False, fontsize=8, loc="upper right")
        fig.tight_layout()
        fig.savefig(PLOTS / fname)
        plt.close(fig)

    # sensitivity: the two checks that break, conductance model vs the paper's synapses
    t0 = t[t.seed_index == 0]
    pairs = [("as chosen / published", "sep", "fix_only"),
             ("excitation -10%", "sep_exc0.9", "cur_exc0.9"),
             ("excitation +10%", "sep_exc1.1", "cur_exc1.1"),
             ("inhibition -10%", "sep_inh0.9", "cur_inh0.9"),
             ("inhibition +10%", "sep_inh1.1", "cur_inh1.1")]

    def val(cfg, what):
        x = t0[t0.config == cfg].set_index("condition").mn9_hz
        if not {"water_200Hz", "sugar100_bitter120", "sugar_100Hz"} <= set(x.index):
            return np.nan
        return x["water_200Hz"] if what == "water" else \
            100 * x["sugar100_bitter120"] / x["sugar_100Hz"]

    if all(np.isfinite(val(c, "water")) for _, a, b in pairs for c in (a, b)):
        fig, axes = plt.subplots(1, 2, figsize=(10, 3.8), dpi=130, sharey=True)
        ypos = np.arange(len(pairs))[::-1]
        for ax, what, bar, xl in ((axes[0], "water", 5.0, "MN9 with water 200 Hz (Hz)"),
                                  (axes[1], "sb", 10.0, "MN9 with sugar + bitter, % of sugar alone")):
            for j, (col, lab, key) in enumerate(((AQUA, "conductance, separate scales", 1),
                                                 (BLUE, "paper's synapses (fix only)", 2))):
                vals = [val(p[key], what) for p in pairs]
                ax.barh(ypos + (0.2 if j == 0 else -0.2), vals, 0.36, color=col, label=lab)
                off = 0.012 * max(val(p[k], what) for p in pairs for k in (1, 2))
                for yy, v in zip(ypos + (0.2 if j == 0 else -0.2), vals):
                    ax.text(v + off, yy, f"{v:.1f}", va="center", fontsize=7, color=INK2)
            ax.axvline(bar, color=INK2, ls="--", lw=1)
            ax.text(bar, len(pairs) - 0.45, "pass: >= 5 Hz" if what == "water" else "pass: <= 10%",
                    fontsize=7, color=INK2, ha="left" if what == "water" else "right")
            ax.set_xlabel(xl, color=INK2, fontsize=8)
            for sp in ("top", "right"):
                ax.spines[sp].set_visible(False)
            ax.tick_params(colors=INK2, labelsize=8)
            ax.xaxis.grid(True, color=GRID, lw=0.8)
            ax.set_axisbelow(True)
        axes[0].set_yticks(ypos, [p[0] for p in pairs])
        axes[0].legend(frameon=False, fontsize=7, loc="lower right")
        fig.suptitle("The two checks that sit on a ridge: a 10% change of one synapse type "
                     "(seed 0, 30 trials)", x=0.01, ha="left", fontsize=10, color=INK)
        fig.tight_layout()
        fig.savefig(PLOTS / "fig4_sensitivity.png")
        plt.close(fig)

    if (RES / "fit.csv").exists():
        f = pd.read_csv(RES / "fit.csv")
        f = f[f.conductance.astype(str) == "True"]
        fig, ax = plt.subplots(figsize=(6.4, 5), dpi=130)
        ok = f.runaways == 0
        ax.scatter(f[ok].cond_exc_scale, f[ok].cond_inh_scale, s=46, color=BLUE,
                   edgecolor="white", lw=1.5, zorder=3, label="calibration run (label: MN9 Hz)")
        ax.scatter(f[~ok].cond_exc_scale, f[~ok].cond_inh_scale, s=60, marker="X",
                   color="#e34948", zorder=3, label="brain ran away in every trial")
        near = (f.cond_exc_scale.between(1.1, 1.3)) & (f.cond_inh_scale.between(0.8, 1.0))
        for _, r in f[~near].drop_duplicates(["cond_exc_scale", "cond_inh_scale"],
                                             keep="last").iterrows():
            ax.annotate(f"{r.mn9_hz:.0f}", (r.cond_exc_scale, r.cond_inh_scale),
                        xytext=(5, 4), textcoords="offset points", fontsize=7, color=INK2)
        cl = f[near & (f.cond_inh_scale != 0.87)]
        if len(cl):
            ax.annotate(f"{len(cl)} nearby runs: {cl.mn9_hz.min():.0f}-{cl.mn9_hz.max():.0f} Hz",
                        (1.25, 1.0), xytext=(1.02, 1.12), fontsize=7, color=INK2,
                        arrowprops=dict(arrowstyle="-", color=INK2, lw=0.8))
        ax.plot([0.8, 2.05], [0.8, 2.05], color=INK2, ls="--", lw=1)
        ax.text(1.85, 1.95, "one shared scale", color=INK2, fontsize=8, ha="right")
        ax.scatter([2.0], [2.0], s=46, color=ORANGE, zorder=4,
                   label="Phase 7 retune (x2): 54 Hz")
        ax.scatter([1.2], [0.87], s=160, facecolor="none", edgecolor=AQUA, lw=2.5, zorder=4,
                   label="chosen: 1.2 / 0.87 (66 Hz)")
        ax.set_xlabel("excitatory scale (x rest-matched conductance)", color=INK2)
        ax.set_ylabel("inhibitory scale (x rest-matched conductance)", color=INK2)
        ax.set_title("Calibration: MN9 at sugar 100 Hz (seed 900)", color=INK,
                     fontsize=11, loc="left")
        _style(ax)
        ax.legend(frameon=False, fontsize=7, loc="upper left")
        fig.tight_layout()
        fig.savefig(PLOTS / "fig3_calibration.png")
        plt.close(fig)


if __name__ == "__main__":
    main()

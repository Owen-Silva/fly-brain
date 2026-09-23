"""Tables and plots for the electrical-synapse upgrade (Phase 7 item 5).

Plain English
-------------
Compares al_ln_literature (the baseline: numbers from experiments/phase7_signs
and, for DA1, experiments/phase6/steering, both proven identical to this lane's
engine by the identity checks below) with the gap-junction upgrade at 0.5x, 1x
and 2x the calibrated strength. Writes results/table_*.csv, results/identity.txt,
results/analysis.txt and plots/fig*.png.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
RES = HERE / "results"
PLOTS = HERE / "plots"
PLOTS.mkdir(exist_ok=True)
SIGNS = ROOT / "experiments" / "phase7_signs" / "results"
STEER = ROOT / "experiments" / "phase6" / "steering" / "results" / "sim"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase5" / "unexplored"))
from steering_ids import STEERING  # noqa: E402

GAP = ["gap_x0.5", "gap_x1", "gap_x2"]
DIAG = ["gap_x1_eln_only", "gap_x1_sister_only", "al_ln_eln_silenced"]
ORDER = ["al_ln"] + GAP
TASTE = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
RUN = ["ir94e_200Hz", "dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz",
       "da1_left_150Hz", "da1_right_150Hz"]
N_KC = None
lines = []


def say(s=""):
    print(s)
    lines.append(s)


def da1_baseline():
    """al_ln DA1 left/right from the Phase 6 steering files, as trial rows."""
    dn_ids = np.load(STEER / "dn_root_ids.npy")
    col = {k: int(np.flatnonzero(dn_ids == v)[0]) for k, v in STEERING.items() if v in dn_ids}
    rows = []
    for side in ("left", "right"):
        for sd in (0, 1, 2):
            z = np.load(STEER / f"al_ln_DA1_{side}_s{sd}.npz")
            for t in range(z["dn"].shape[0]):
                r = dict(config="al_ln", condition=f"da1_{side}_150Hz", seed_index=sd, trial=t,
                         n_active=int(z["n_active"][t]))
                for k, c in col.items():
                    r[k] = float(z["dn"][t, c])
                rows.append(r)
    return pd.DataFrame(rows)


def load():
    g = pd.read_csv(RES / "trials.csv")
    s = pd.read_csv(SIGNS / "trials.csv")
    s = s[s.config == "al_ln_literature"].assign(config="al_ln")
    base = pd.concat([s, da1_baseline()], ignore_index=True)
    return g, base


def identity(g, base):
    say("== Identity checks (seed 0, trials 0-9) ==")
    chk = g[g.config == "al_ln_check"]
    zero = g[g.config == "gap_x0_check"]
    key = ["condition", "seed_index", "trial"]
    cols = ["total_spikes", "n_active", "max_distinct_10ms", "mn9_hz", "kc_active",
            "DNa02_L", "DNa02_R"]
    b = base[base.condition.isin(chk.condition.unique()) & ~base.condition.str.startswith("da1")]
    m = chk.merge(b, on=key, suffixes=("", "_b"))
    ok1 = all((m[c] == m[c + "_b"]).all() for c in cols)
    say(f"old engine on this brain vs experiments/phase7_signs al_ln_literature: "
        f"{len(m)} trials compared, all of {cols} identical: {ok1}")
    d = chk[chk.condition.str.startswith("da1")].merge(
        base[base.condition.str.startswith("da1")], on=key, suffixes=("", "_b"))
    ok2 = all(np.allclose(d[c], d[c + "_b"], rtol=1e-6) for c in ("DNa02_L", "DNa02_R", "n_active"))
    say(f"old engine vs experiments/phase6/steering al_ln DA1: {len(d)} trials, DNa02 L/R and "
        f"active-neuron counts identical: {ok2}")
    z = zero.merge(chk, on=key, suffixes=("", "_c"))
    ok3 = all((z[c] == z[c + "_c"]).all() for c in cols + ["eln_hz", "pn_other_hz"])
    say(f"new engine with all junctions at strength 0 vs old engine: {len(z)} trials, identical: {ok3}")
    (RES / "identity.txt").write_text("\n".join(lines[-4:]) + "\n")
    return ok1 and ok2 and ok3


def pooled(df, cond, cfg, col):
    x = df[(df.condition == cond) & (df.config == cfg)]
    return x[col].to_numpy(float), x


def tables(g, base):
    allr = pd.concat([base, g[g.config.isin(GAP + DIAG)]], ignore_index=True)
    # Phase 3
    rows = []
    for cond in TASTE:
        r = dict(condition=cond)
        for cfg in ORDER:
            x, xx = pooled(allr, cond, cfg, "mn9_hz")
            r[cfg] = round(x.mean(), 2)
            r[cfg + "_n"] = x.size
            r[cfg + "_per_seed"] = "/".join(f"{v:.2f}" for v in xx.groupby("seed_index").mn9_hz.mean())
        rows.append(r)
    t3 = pd.DataFrame(rows)
    t3.to_csv(RES / "table_phase3.csv", index=False)
    say("\n== Phase 3: MN9 Hz (3 seeds x 30 trials) ==")
    say(t3[["condition"] + ORDER].to_string(index=False))
    # runaway
    rows = []
    for cond in RUN:
        r = dict(condition=cond)
        for cfg in ORDER:
            x, xx = pooled(allr, cond, cfg, "runaway") if "runaway" in allr else (np.array([]), None)
            if cond.startswith("da1") and cfg == "al_ln":
                r[cfg] = "n/a (not stored)"
                continue
            per = "/".join(str(int(v)) for v in xx.groupby("seed_index").runaway.sum())
            r[cfg] = f"{int(x.sum())}/{x.size} ({per})"
        rows.append(r)
    tr = pd.DataFrame(rows)
    tr.to_csv(RES / "table_runaway.csv", index=False)
    say("\n== Runaway (trials with >1,500 distinct neurons in some 10 ms) ==")
    say(tr.to_string(index=False))
    # Kenyon cells
    rows = []
    for cond in ("dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz", "da1_left_150Hz",
                 "da1_right_150Hz"):
        r = dict(condition=cond)
        for cfg in ORDER:
            x, xx = pooled(allr, cond, cfg, "kc_active")
            if x.size == 0 or np.isnan(x).all():
                r[cfg] = np.nan
                continue
            r[cfg] = round(100 * x.mean() / N_KC, 2)
            r[cfg + "_per_seed"] = "/".join(f"{100 * v / N_KC:.2f}"
                                           for v in xx.groupby("seed_index").kc_active.mean())
        rows.append(r)
    tk = pd.DataFrame(rows)
    tk.to_csv(RES / "table_kc.csv", index=False)
    say(f"\n== Kenyon cells firing per trial, % of {N_KC} ==")
    say(tk[["condition"] + ORDER].to_string(index=False))
    return allr


def dprime(a, b):
    s = np.sqrt(0.5 * (a.var(ddof=1) + b.var(ddof=1)))
    return (a.mean() - b.mean()) / s if s > 0 else np.inf


def steering(allr):
    rows = []
    say("\n== Steering: turn = DNa02 left - right (Hz); left odour / right odour ==")
    for glom in ("dm1", "da1"):
        for cfg in ORDER + DIAG:
            L = allr[(allr.condition == f"{glom}_left_150Hz") & (allr.config == cfg)]
            R = allr[(allr.condition == f"{glom}_right_150Hz") & (allr.config == cfg)]
            if L.empty or R.empty:
                continue
            tl = (L.DNa02_L - L.DNa02_R).to_numpy()
            tr_ = (R.DNa02_L - R.DNa02_R).to_numpy()
            ps = []
            for sd in (0, 1, 2):
                a = (L[L.seed_index == sd].DNa02_L - L[L.seed_index == sd].DNa02_R).to_numpy()
                b = (R[R.seed_index == sd].DNa02_L - R[R.seed_index == sd].DNa02_R).to_numpy()
                ps.append(stats.mannwhitneyu(a, b).pvalue if a.std() + b.std() > 0 else 1.0)
            rR = [stats.mannwhitneyu(R[R.seed_index == sd].DNa02_R, L[L.seed_index == sd].DNa02_R,
                                     alternative="greater").pvalue for sd in (0, 1, 2)]
            r = dict(glomerulus=glom.upper(), config=cfg,
                     DNa02_L_left=L.DNa02_L.mean(), DNa02_R_left=L.DNa02_R.mean(),
                     DNa02_L_right=R.DNa02_L.mean(), DNa02_R_right=R.DNa02_R.mean(),
                     DNa01_L_left=L.DNa01_L.mean(), DNa01_R_left=L.DNa01_R.mean(),
                     DNa01_L_right=R.DNa01_L.mean(), DNa01_R_right=R.DNa01_R.mean(),
                     turn_left_odour=tl.mean(), turn_right_odour=tr_.mean(),
                     mirrors=bool(tl.mean() > 0 > tr_.mean()),
                     d_prime=dprime(tl, tr_),
                     p_turn_differs_per_seed="/".join(f"{p:.2g}" for p in ps),
                     p_right_DNa02_higher_for_right_odour="/".join(f"{p:.2g}" for p in rR),
                     n_trials=f"{len(L)}+{len(R)}")
            rows.append(r)
            say(f"{glom.upper():4s} {cfg:9s} DNa02 L/R left odour {r['DNa02_L_left']:.1f}/"
                f"{r['DNa02_R_left']:.1f}, right odour {r['DNa02_L_right']:.1f}/{r['DNa02_R_right']:.1f};"
                f" turn {r['turn_left_odour']:+.1f} / {r['turn_right_odour']:+.1f}; mirrors "
                f"{r['mirrors']}; d' {r['d_prime']:.2f}; p(turn differs) {r['p_turn_differs_per_seed']};"
                f" p(right DNa02 up for right odour) {r['p_right_DNa02_higher_for_right_odour']}")
    ts = pd.DataFrame(rows).round(3)
    ts.to_csv(RES / "table_steering.csv", index=False)
    return ts


def al_table(g):
    """Mean rates (Hz) of antennal-lobe groups, 3 seeds x 30 trials, from the
    per-neuron spike counts (baseline: phase7_signs counts; DA1: phase6 rates)."""
    from sim import sign_fixes as S
    rid = pd.read_csv(ROOT / "data/reference/2023_03_23_completeness_630_final.csv", index_col=0).index.to_numpy()  # no wiring table needed
    lab = S.neuron_table(rid)
    upn = pd.read_csv(RES / "upn_glomeruli.csv")
    grp = {"eln_hz": np.flatnonzero(S.eln_mask(lab))}
    for glom in ("DM1", "DA1"):
        for side, s in (("left", "L"), ("right", "R")):
            grp[f"pn_{glom.lower()}_{s}_hz"] = upn[(upn.glomerulus == glom) & (upn.side == side)].idx.to_numpy()
    grp["pn_other_hz"] = upn[~upn.glomerulus.isin(["DM1", "DA1"])].idx.to_numpy()
    n = rid.size

    def rates(cfg, cond, sd):
        if cfg == "al_ln" and cond.startswith("da1"):
            side = cond.split("_")[1]
            return np.load(STEER / f"al_ln_DA1_{side}_s{sd}.npz")["rates"].astype(float)
        f = (SIGNS / "counts" / f"al_ln_literature__{cond}__s{sd}.npz" if cfg == "al_ln"
             else RES / "counts" / f"{cfg}__{cond}__s{sd}.npz")
        if not f.exists():
            return None
        z = np.load(f)
        c = np.zeros(n)
        c[z["nz_idx"]] = z["nz_count"]
        return c / float(z["n_trials"])          # 1-s trials: spikes per trial = Hz

    rows = []
    for cond in TASTE + RUN:
        for cfg in ORDER + DIAG:
            rs = [rates(cfg, cond, sd) for sd in (0, 1, 2)]
            if any(r is None for r in rs):
                continue
            r = np.mean(rs, axis=0)
            rows.append(dict(condition=cond, config=cfg,
                             **{k: round(float(r[idx].mean()), 3) for k, idx in grp.items()}))
    ta = pd.DataFrame(rows)
    ta.to_csv(RES / "table_antennal_lobe.csv", index=False)
    say("\n== Antennal lobe mean rates (Hz, 3 seeds x 30 trials) ==")
    say(ta[ta.condition.str.startswith(("dm1", "da1", "ir94e"))].to_string(index=False))
    return ta


def plots(allr, ts, ta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    lab = {"al_ln": "al_ln_literature", "gap_x0.5": "+gap x0.5", "gap_x1": "+gap x1",
           "gap_x2": "+gap x2"}
    col = {"al_ln": "#777777", "gap_x0.5": "#9ecae1", "gap_x1": "#3182bd", "gap_x2": "#08519c"}
    # fig1: taste + KC + runaway
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    w = 0.2
    for i, cfg in enumerate(ORDER):
        v = [allr[(allr.condition == c) & (allr.config == cfg)].mn9_hz.mean() for c in TASTE]
        ax[0].bar(np.arange(len(TASTE)) + (i - 1.5) * w, v, w, color=col[cfg], label=lab[cfg])
    ax[0].set_xticks(range(len(TASTE)), ["sugar\n100", "sugar\n200", "water\n200", "bitter\n200",
                                         "sugar100\n+bitter120"])
    ax[0].set_ylabel("MN9 rate (Hz)")
    ax[0].set_title("Phase 3 taste checks")
    ax[0].legend(fontsize=8)
    conds = ["dm1_both_150Hz", "da1_left_150Hz"]
    for i, cfg in enumerate(ORDER):
        v = [100 * allr[(allr.condition == c) & (allr.config == cfg)].kc_active.mean() / N_KC
             for c in conds]
        ax[1].bar(np.arange(2) + (i - 1.5) * w, v, w, color=col[cfg])
    ax[1].axhspan(5, 10, color="#dddddd", zorder=0)
    ax[1].text(1.45, 7.5, "real flies\n~5-10%", fontsize=8, ha="right", va="center")
    ax[1].set_xticks(range(2), ["DM1 both sides", "DA1 left"])
    ax[1].set_ylabel("Kenyon cells firing per trial (%)")
    ax[1].set_title("Mushroom body sparseness")
    rc = ["ir94e_200Hz", "dm1_both_150Hz", "dm1_left_150Hz", "dm1_right_150Hz"]
    for i, cfg in enumerate(ORDER):
        v = [100 * allr[(allr.condition == c) & (allr.config == cfg)].runaway.astype(float).mean()
             for c in rc]
        ax[2].bar(np.arange(len(rc)) + (i - 1.5) * w, v, w, color=col[cfg])
    ax[2].set_xticks(range(len(rc)), ["Ir94e 200", "DM1 both", "DM1 left", "DM1 right"])
    ax[2].set_ylabel("runaway trials (%)")
    ax[2].set_ylim(0, 100)
    ax[2].set_title("Runaway (90 trials each)")
    fig.tight_layout()
    fig.savefig(PLOTS / "fig1_checks.png", dpi=120)
    plt.close(fig)
    # fig2: steering
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for j, glom in enumerate(("DM1", "DA1")):
        s = ts[ts.glomerulus == glom].set_index("config")
        cfgs = [c for c in ORDER if c in s.index]
        x = np.arange(len(cfgs))
        ax[j].bar(x - 0.18, s.loc[cfgs, "turn_left_odour"], 0.36, color="#e6550d", label="left odour")
        ax[j].bar(x + 0.18, s.loc[cfgs, "turn_right_odour"], 0.36, color="#3182bd", label="right odour")
        ax[j].axhline(0, color="k", lw=0.8)
        ax[j].set_xticks(x, [lab[c] for c in cfgs], fontsize=8)
        ax[j].set_ylabel("turn signal: DNa02 left - right (Hz)")
        ax[j].set_title(f"{glom}: correct = orange above 0, blue below 0")
        ax[j].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig2_steering.png", dpi=120)
    plt.close(fig)
    # fig3: antennal lobe rates
    fig, ax = plt.subplots(1, 2, figsize=(11, 4.2))
    for j, cond in enumerate(("dm1_both_150Hz", "dm1_left_150Hz")):
        t = ta[ta.condition == cond].set_index("config")
        cfgs = [c for c in ORDER if c in t.index]
        cols = ["eln_hz", "pn_dm1_L_hz", "pn_dm1_R_hz", "pn_other_hz"]
        x = np.arange(len(cols))
        for i, cfg in enumerate(cfgs):
            ax[j].bar(x + (i - 1.5) * 0.2, t.loc[cfg, cols], 0.2,
                      color=col[cfg], label=lab[cfg])
        ax[j].set_xticks(x, ["44 eLNs", "DM1 uPNs\nleft", "DM1 uPNs\nright", "other uPNs"])
        ax[j].set_ylabel("mean rate (Hz)")
        ax[j].set_title(cond.replace("_150Hz", " 150 Hz"))
        ax[j].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig3_antennal_lobe.png", dpi=120)
    plt.close(fig)
    # fig4: DM1 diagnostics (which part of the upgrade moves the steering?)
    s = ts[ts.glomerulus == "DM1"].set_index("config")
    cfgs = [c for c in ["al_ln", "gap_x1", "gap_x1_eln_only", "gap_x1_sister_only",
                        "al_ln_eln_silenced"] if c in s.index]
    names = {"al_ln": "al_ln_literature", "gap_x1": "+all junctions",
             "gap_x1_eln_only": "+eLN-PN only", "gap_x1_sister_only": "+sister PN only",
             "al_ln_eln_silenced": "no junctions,\n44 eLNs silenced"}
    fig, ax = plt.subplots(figsize=(8, 4.2))
    x = np.arange(len(cfgs))
    ax.bar(x - 0.18, s.loc[cfgs, "turn_left_odour"], 0.36, color="#e6550d", label="left odour")
    ax.bar(x + 0.18, s.loc[cfgs, "turn_right_odour"], 0.36, color="#3182bd", label="right odour")
    ax.axhline(0, color="k", lw=0.8)
    ax.set_xticks(x, [names[c] for c in cfgs], fontsize=8)
    ax.set_ylabel("turn signal: DNa02 left - right (Hz)")
    ax.set_title("DM1 steering: what moves it (3 seeds x 30 trials each)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(PLOTS / "fig4_dm1_diagnostics.png", dpi=120)
    plt.close(fig)


def main():
    global N_KC
    import pyarrow.parquet as pq
    cc = pq.read_table(ROOT / "data/cache/connectome_630_neurons.parquet",
                       columns=["cell_class"]).column("cell_class").to_pandas()
    N_KC = int((cc == "Kenyon_Cell").sum())
    g, base = load()
    ok = identity(g, base)
    allr = tables(g, base)
    ts = steering(allr)
    ta = al_table(g)
    plots(allr, ts, ta)
    (RES / "analysis.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    say(f"\nidentity all OK: {ok}")


if __name__ == "__main__":
    main()

"""Summarise the Phase 7 runs (experiments/phase7/results/<config>/*.npz).

Writes experiments/phase7/results/summary.md and CSV tables:
  * readouts.csv   : MN9 (both sides), active neurons, runaway trials, per config x condition
  * checks.csv     : the Phase 3 yes/no checks, per config, per seed
  * per_neuron.csv : every neuron's rate vs the comparison model (Pearson r, top-50 overlap)

Usage: python experiments/phase7/analyze.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.phase7.run_phase7 import CONDITIONS, SETS, N_TRIALS, RUNAWAY_CONDITION  # noqa: E402

RES = ROOT / "experiments" / "phase7" / "results"
N_NEURONS = 127400
ROOT_IDS = pd.read_csv(ROOT / "data/reference/2023_03_23_completeness_630_final.csv",
                       index_col=0).index.to_numpy()

# config -> the model it is compared with, neuron by neuron (besides the baseline)
COMPARE_WITH = {"U12": "U1_delays", "U12_tuned": "U1_delays", "U123": "U12_tuned",
                "U13": "U1_delays"}
ORDER = ["baseline", "baseline_newseeds", "U1_delays", "U1_delays_slow0.129",
         "U1_delays_fast2.07", "U1_delays_soma", "U2_cond", "U2_cond_Ei-70",
         "U2_diag_exc_only", "U2_diag_inh_only", "U2_cond_tuned", "U12", "U12_tuned",
         "U3_adapt", "U3_adapt_half", "U3_adapt_tau300", "U3_adapt_half_RW",
         "U3_adapt_tau300_RW", "U13", "U123"]


def load(config, cond):
    files = sorted((RES / config).glob(f"{cond}_s*.npz"))
    if not files:
        return None
    counts = np.zeros(N_NEURONS, np.int64)
    mn9, tot, seeds = [], [], []
    for f in files:
        z = np.load(f)
        counts[z["nz_idx"]] += z["nz_count"]
        mn9.append(z["mn9"])
        tot.append(z["per_trial_total"])
        seeds.append(int(z["seed"]))
    return {"counts": counts, "mn9": np.stack(mn9), "tot": np.stack(tot), "seeds": seeds,
            "n_trials": len(files) * N_TRIALS}


def md_table(df, index=False):
    """Markdown table without the optional 'tabulate' package."""
    if index:
        df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v)
                                       for v in row) + " |")
    return chr(10).join(lines)


def wilson(k, n, z=1.96):
    """95% range for a proportion k/n (Wilson score interval)."""
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def stim_idx(cond):
    ids = [i for s, _ in CONDITIONS[cond][0] for i in SETS[s]]
    return np.flatnonzero(np.isin(ROOT_IDS, np.array(ids, np.int64)))


def compare(a, b, cond, k=50):
    """Pearson r of per-neuron rates and top-k overlap, over neurons active in
    either model, stimulated neurons left out (they fire at the set rate in
    every model and would inflate the agreement)."""
    ra = a["counts"] / a["n_trials"]
    rb = b["counts"] / b["n_trials"]
    keep = np.ones(N_NEURONS, bool)
    keep[stim_idx(cond)] = False
    act = keep & ((ra > 0) | (rb > 0))
    r = float(np.corrcoef(ra[act], rb[act])[0, 1]) if act.sum() > 2 else float("nan")
    ta = set(np.argsort(-np.where(keep, ra, -1))[:k])
    tb = set(np.argsort(-np.where(keep, rb, -1))[:k])
    only_a = int(((ra > 0) & (rb == 0) & keep).sum())
    only_b = int(((rb > 0) & (ra == 0) & keep).sum())
    return {"pearson_r": r, f"top{k}_overlap": len(ta & tb), "n_compared": int(act.sum()),
            "active_only_in_reference": only_a, "active_only_in_this": only_b}


def main():
    configs = [c for c in ORDER if (RES / c).exists()]
    base = {c: load("baseline", c) for c in CONDITIONS}
    base_median = {c: float(np.median(base[c]["tot"])) for c in CONDITIONS if base[c]}
    rows, checks, pn = [], [], []
    for cfg in configs:
        data = {c: load(cfg, c) for c in CONDITIONS}
        for cond, d in data.items():
            if d is None:
                continue
            mc, mi = d["mn9"][:, 0, :], d["mn9"][:, 1, :]
            tot = d["tot"]
            run_b = tot > 5 * base_median[cond] if cond in base_median else np.zeros_like(tot, bool)
            run_own = tot > 5 * np.median(tot)
            row = {"config": cfg, "condition": cond, "trials": d["n_trials"],
                   "mn9_contra_hz": mc.mean(), "mn9_contra_sd": mc.std(),
                   "mn9_contra_seed_means": "/".join(f"{x:.1f}" for x in mc.mean(axis=1)),
                   "mn9_ipsi_hz": mi.mean(), "mn9_ipsi_sd": mi.std(),
                   "active_neurons": int((d["counts"] > 0).sum()),
                   "spikes_per_trial_median": float(np.median(tot)),
                   "runaway_trials_vs_baseline_median": int(run_b.sum()),
                   "runaway_trials_vs_own_median": int(run_own.sum()),
                   "runaway_per_seed": "/".join(str(int(x)) for x in run_b.sum(axis=1))}
            if run_b.any() and (~run_b).any():
                row["mn9_contra_hz_nonrunaway"] = mc[~run_b].mean()
                row["mn9_contra_hz_runaway"] = mc[run_b].mean()
            rows.append(row)
            if base.get(cond) is not None and cfg != "baseline":
                pn.append({"config": cfg, "vs": "baseline", "condition": cond,
                           **compare(base[cond], d, cond)})
            if cfg in COMPARE_WITH:
                ref = load(COMPARE_WITH[cfg], cond)
                if ref is not None:
                    pn.append({"config": cfg, "vs": COMPARE_WITH[cfg], "condition": cond,
                               **compare(ref, d, cond)})
        # the Phase 3 checks, seed by seed
        need = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120"]
        if all(data.get(c) is not None for c in need):
            # the first 3 seeds of every condition (the runaway condition has 2 extra)
            m = {c: data[c]["mn9"][:3, 0, :].mean(axis=1) for c in data if data[c] is not None}
            mi = {c: data[c]["mn9"][:3, 1, :].mean(axis=1) for c in data if data[c] is not None}
            tests = {
                "sugar 100 Hz drives MN9 (>= 20 Hz)": m["sugar_100Hz"] >= 20,
                "sugar 200 Hz > sugar 100 Hz": m["sugar_200Hz"] > m["sugar_100Hz"],
                "sugar: contra MN9 > ipsi MN9": (m["sugar_100Hz"] > mi["sugar_100Hz"])
                & (m["sugar_200Hz"] > mi["sugar_200Hz"]),
                "water 200 Hz drives MN9 (>= 5 Hz), less than sugar 200": (m["water_200Hz"] >= 5)
                & (m["water_200Hz"] < m["sugar_200Hz"]),
                "bitter alone: MN9 silent (<= 1 Hz)": m["bitter_200Hz"] <= 1.0,
                "sugar 100 + bitter 120: MN9 near 0 (<= 10% of sugar alone)":
                    m["sugar100_bitter120"] <= 0.1 * m["sugar_100Hz"],
            }
            if data.get("sugar200_ir94e200") is not None:
                tests["sugar 200 + Ir94e 200: MN9 lower than sugar alone, not abolished (>= 10 Hz)"] = \
                    (m["sugar200_ir94e200"] < m["sugar_200Hz"]) & (m["sugar200_ir94e200"] >= 10)
            for name, ok in tests.items():
                checks.append({"config": cfg, "check": name,
                               "per_seed": "/".join("pass" if x else "FAIL" for x in ok),
                               "holds (all seeds)": bool(np.all(ok))})
    R = pd.DataFrame(rows)
    # runaway: how often, with a 95% range, and is it different from the baseline?
    from scipy.stats import fisher_exact
    rw = []
    rb = R[(R.config == "baseline") & (R.condition == RUNAWAY_CONDITION)]
    for _, row in R[R.condition == RUNAWAY_CONDITION].iterrows():
        k, n = int(row.runaway_trials_vs_baseline_median), int(row.trials)
        lo, hi = wilson(k, n)
        p = float("nan")
        if len(rb) and row.config != "baseline":
            kb, nb = int(rb.iloc[0].runaway_trials_vs_baseline_median), int(rb.iloc[0].trials)
            p = fisher_exact([[k, n - k], [kb, nb - kb]])[1]
        rw.append({"config": row.config, "trials": n, "runaway_trials": k,
                   "fraction": f"{k / n:.3f}", "95% range": f"{lo:.3f}-{hi:.3f}",
                   "p vs baseline (Fisher)": "" if np.isnan(p) else f"{p:.3g}",
                   "MN9 contra, non-runaway trials (Hz)": f"{(row.mn9_contra_hz if pd.isna(row.get('mn9_contra_hz_nonrunaway', float('nan'))) else row.mn9_contra_hz_nonrunaway):.1f}"})
    W = pd.DataFrame(rw)
    W.to_csv(RES / "runaway.csv", index=False)
    C = pd.DataFrame(checks)
    P = pd.DataFrame(pn)
    R.to_csv(RES / "readouts.csv", index=False)
    C.to_csv(RES / "checks.csv", index=False)
    P.to_csv(RES / "per_neuron.csv", index=False)

    md = ["# Phase 7 upgrades 1-3: whole-brain checks (snapshot 630)", "",
          "PRELIMINARY (PLAN.md Phase 6 not complete: seeds rerun, parameter "
          "variants run for each upgrade, literature check done; no independent review).", "",
          f"Each condition: 3 seeds x {N_TRIALS} trials x 1 s ({RUNAWAY_CONDITION}: 5 seeds). MN9 rates are means over all "
          "trials (sd = trial-to-trial). 'Runaway' = a trial with more than 5x the baseline "
          "model's median spike count for that condition.", ""]
    for cfg in configs:
        f = RES / cfg / "config.json"
        if f.exists():
            md.append(f"- **{cfg}**: `{json.dumps(json.loads(f.read_text())['realism'], default=float)}`")
    md += ["", "## MN9 and network size", ""]
    show = R.copy()
    for c in ["mn9_contra_hz", "mn9_contra_sd", "mn9_ipsi_hz", "mn9_ipsi_sd",
              "mn9_contra_hz_nonrunaway", "mn9_contra_hz_runaway"]:
        if c in show:
            show[c] = show[c].map(lambda x: "" if pd.isna(x) else f"{x:.1f}")
    md.append(md_table(show))
    md += ["", f"## Runaway activity ({RUNAWAY_CONDITION}, 5 seeds x {N_TRIALS} trials)", "",
           md_table(W) if len(W) else "(not run)"]
    md += ["", "## Phase 3 checks (a check holds only if it passes for every seed)", ""]
    if len(C):
        piv = C.pivot(index="check", columns="config", values="per_seed")
        piv = piv[[c for c in configs if c in piv.columns]]
        md.append(md_table(piv, index=True))
    md += ["", "## Neuron by neuron (stimulated neurons excluded)", "",
           "Noise floor = `baseline_newseeds` vs `baseline`: how much two runs of the SAME "
           "model differ from randomness alone.", ""]
    if len(P):
        Ps = P.copy()
        Ps["pearson_r"] = Ps["pearson_r"].map(lambda x: f"{x:.4f}")
        md.append(md_table(Ps))
    (RES / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

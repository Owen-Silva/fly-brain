"""Summarise the upgrade-4 runs (experiments/phase7_celltype/results/<config>/*.npz).

Writes to experiments/phase7_celltype/results/:
  * readouts.csv    : MN9 (both sides), active neurons, runaway trials, per config x condition
  * checks.csv      : the Phase 3 yes/no checks, per config, per seed
  * runaway.csv     : Phase 6 runaway rate with a 95% range and a test against the baseline
  * per_neuron.csv  : every neuron's rate vs the baseline (Pearson r, top-50 overlap)
  * group_rates.csv : mean firing rate of each changed cell group, baseline vs upgrade
  * top_changes.csv : the neurons whose rate changed most (sugar 100 Hz and Ir94e)
  * summary.md      : all of the above as tables

Usage: python experiments/phase7_celltype/analyze.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.phase7_celltype.run_celltype import (  # noqa: E402
    CHECK_CONDITIONS, CONDITIONS, N_TRIALS, RUNAWAY_CONDITIONS, RUNAWAY_DISTINCT_10MS, SETS)

RES = ROOT / "experiments" / "phase7_celltype" / "results"
P7_BASE = ROOT / "experiments" / "phase7" / "results" / "baseline"
LABELS = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                         columns=["root_id", "cell_class", "cell_sub_class", "cell_type",
                                  "hemibrain_type", "top_nt", "super_class"])
N_NEURONS = len(LABELS)
ORDER = ["baseline", "baseline_newseeds", "CT_main", "CT_only_uPN", "CT_only_KC",
         "CT_only_PEN", "CT_only_lLNv", "CT_PNgap17.8", "CT_KCtau200"]


def groups():
    from sim.celltype_params import SELECTORS, group_members
    return group_members(LABELS, SELECTORS)


def load(config, cond, first=None):
    files = sorted((RES / config).glob(f"{cond}_s*.npz"))[:first]
    if not files:
        return None
    counts = np.zeros(N_NEURONS, np.int64)
    per_seed = []
    mn9, tot, maxd, onset, seeds = [], [], [], [], []
    for f in files:
        z = np.load(f)
        c = np.zeros(N_NEURONS, np.int64)
        c[z["nz_idx"]] = z["nz_count"]
        counts += c
        per_seed.append(c)
        mn9.append(z["mn9"])
        tot.append(z["per_trial_total"])
        maxd.append(z["max_distinct_10ms"])
        onset.append(z["onset_ms"])
        seeds.append(int(z["seed"]))
    return {"counts": counts, "per_seed": per_seed, "mn9": np.stack(mn9), "tot": np.stack(tot),
            "maxd": np.stack(maxd), "onset": np.stack(onset), "seeds": seeds,
            "n_trials": len(files) * N_TRIALS}


def md_table(df, index=False):
    if index:
        df = df.reset_index()
    cols = [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for row in df.itertuples(index=False):
        lines.append("| " + " | ".join("" if (isinstance(v, float) and np.isnan(v)) else str(v)
                                       for v in row) + " |")
    return "\n".join(lines)


def wilson(k, n, z=1.96):
    if n == 0:
        return float("nan"), float("nan")
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, c - h), min(1.0, c + h)


def stim_idx(cond):
    ids = np.array([i for s, _ in CONDITIONS[cond][0] for i in SETS[s]], np.int64)
    return np.flatnonzero(np.isin(LABELS["root_id"].to_numpy(np.int64), ids))


def compare(a, b, cond, k=50):
    ra = a["counts"] / a["n_trials"]
    rb = b["counts"] / b["n_trials"]
    keep = np.ones(N_NEURONS, bool)
    keep[stim_idx(cond)] = False
    act = keep & ((ra > 0) | (rb > 0))
    r = float(np.corrcoef(ra[act], rb[act])[0, 1]) if act.sum() > 2 else float("nan")
    ta = set(np.argsort(-np.where(keep, ra, -1))[:k])
    tb = set(np.argsort(-np.where(keep, rb, -1))[:k])
    return {"pearson_r": r, f"top{k}_overlap": len(ta & tb), "n_compared": int(act.sum()),
            "active_only_in_baseline": int(((ra > 0) & (rb == 0) & keep).sum()),
            "active_only_in_this": int(((rb > 0) & (ra == 0) & keep).sum())}


def main():
    configs = [c for c in ORDER if (RES / c).exists()]
    G = groups()
    notes = []
    # 0. our baseline must equal the Phase 7 baseline (same engine, same seeds)
    same = []
    for cond in CONDITIONS:
        ours = sorted((RES / "baseline").glob(f"{cond}_s*.npz"))
        for f in ours:
            g = P7_BASE / f.name
            if g.exists():
                same.append(bool(np.array_equal(np.load(f)["mn9"], np.load(g)["mn9"])
                                 and np.array_equal(np.load(f)["per_trial_total"],
                                                    np.load(g)["per_trial_total"])))
    notes.append(f"Baseline here vs experiments/phase7/results/baseline (same seeds): "
                 f"{sum(same)}/{len(same)} files identical (MN9 per trial and spikes per trial).")

    base = {c: load("baseline", c) for c in CONDITIONS}
    rows, checks, pn, gr, rw, top = [], [], [], [], [], []
    for cfg in configs:
        data = {c: load(cfg, c) for c in CONDITIONS}
        for cond, d in data.items():
            if d is None:
                continue
            mc, mi = d["mn9"][:, 0, :], d["mn9"][:, 1, :]
            run = d["maxd"] > RUNAWAY_DISTINCT_10MS
            row = {"config": cfg, "condition": cond, "trials": d["n_trials"],
                   "mn9_contra_hz": round(float(mc.mean()), 1),
                   "mn9_contra_sd": round(float(mc.std()), 1),
                   "mn9_contra_seed_means": "/".join(f"{x:.1f}" for x in mc.mean(axis=1)),
                   "mn9_ipsi_hz": round(float(mi.mean()), 1),
                   "active_neurons": int((d["counts"] > 0).sum()),
                   "spikes_per_trial_median": float(np.median(d["tot"])),
                   "runaway_trials": int(run.sum()),
                   "mn9_contra_hz_healthy_trials": round(float(mc[~run].mean()), 1) if (~run).any() else float("nan")}
            rows.append(row)
            if cond in RUNAWAY_CONDITIONS:
                k, n = int(run.sum()), int(run.size)
                lo, hi = wilson(k, n)
                p = float("nan")
                b = base.get(cond)
                if b is not None and cfg != "baseline":
                    kb = int((b["maxd"] > RUNAWAY_DISTINCT_10MS).sum())
                    nb = int(b["maxd"].size)
                    p = fisher_exact([[k, n - k], [kb, nb - kb]])[1]
                rw.append({"config": cfg, "condition": cond, "trials": n, "runaway_trials": k,
                           "fraction": f"{k / n:.3f}", "95% range": f"{lo:.3f}-{hi:.3f}",
                           "p vs baseline (Fisher)": "" if np.isnan(p) else f"{p:.3g}",
                           "median onset (ms)": "" if k == 0 else f"{np.nanmedian(d['onset'][run]):.0f}"})
            if base.get(cond) is not None and cfg != "baseline":
                # neuron by neuron on the SAME seeds (the baseline's first seeds)
                bb = load("baseline", cond, first=len(d["seeds"]))
                pn.append({"config": cfg, "vs": "baseline", "condition": cond,
                           **compare(bb, d, cond)})
            # changed cell groups: mean rate (Hz) per neuron
            for g, idx in G.items():
                gr.append({"config": cfg, "condition": cond, "group": g, "n": idx.size,
                           "mean_rate_hz": round(float(d["counts"][idx].sum() / idx.size / d["n_trials"]), 3),
                           "active": int((d["counts"][idx] > 0).sum())})
        if all(data.get(c) is not None for c in CHECK_CONDITIONS):
            ns = min(data[c]["mn9"].shape[0] for c in CHECK_CONDITIONS)
            m = {c: data[c]["mn9"][:ns, 0, :].mean(axis=1) for c in data if data[c] is not None}
            mi = {c: data[c]["mn9"][:ns, 1, :].mean(axis=1) for c in data if data[c] is not None}
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
                m2 = data["sugar200_ir94e200"]["mn9"][:ns, 0, :].mean(axis=1)
                tests["sugar 200 + Ir94e 200: MN9 lower than sugar alone, not abolished (>= 10 Hz)"] = \
                    (m2 < m["sugar_200Hz"]) & (m2 >= 10)
            for name, ok in tests.items():
                checks.append({"config": cfg, "check": name,
                               "per_seed": "/".join("pass" if x else "FAIL" for x in ok),
                               "holds (all seeds)": bool(np.all(ok))})
    # biggest single-neuron changes, CT_main vs baseline, healthy trials only
    lab = LABELS.assign(type=LABELS["cell_type"].fillna(LABELS["hemibrain_type"]).astype(str))
    in_group = np.zeros(N_NEURONS, bool)
    for idx in G.values():
        in_group[idx] = True
    if (RES / "CT_main").exists():
        for cond in ("sugar_100Hz", "ir94e_200Hz", "sugar200_ir94e200", "dm1_orn_150Hz"):
            a, b = load("baseline", cond), load("CT_main", cond)
            if a is None or b is None:
                continue
            ra = a["counts"] / a["n_trials"]
            rb = b["counts"] / b["n_trials"]
            diff = rb - ra
            # the 10 biggest changes inside the changed groups and the 10 outside
            o_in = [i for i in np.argsort(-np.abs(diff)) if in_group[i]][:10]
            o_out = [i for i in np.argsort(-np.abs(np.where(in_group, 0, diff)))[:10]]
            for i in o_in + o_out:
                if diff[i] == 0:
                    continue
                top.append({"condition": cond, "root_id": int(LABELS.root_id.iloc[i]),
                            "type": lab.type.iloc[i], "class": str(lab.cell_class.iloc[i]),
                            "in_changed_group": bool(in_group[i]),
                            "baseline_hz": round(float(ra[i]), 2), "CT_main_hz": round(float(rb[i]), 2)})
    # smell (DM1 receptor neurons) and the runaway conditions: how many Kenyon
    # cells / PNs fire per trial, split by healthy and runaway trials
    sm = []
    dm1_pn = np.flatnonzero((LABELS["hemibrain_type"] == "DM1_lPN").fillna(False).to_numpy(bool))
    for cfg in configs:
        for cond in ("dm1_orn_150Hz", "ir94e_200Hz", "sugar200_ir94e200"):
            files = sorted((RES / cfg).glob(f"{cond}_s*.npz"))
            if not files:
                continue
            zs = [np.load(f) for f in files]
            if "active_KC" not in zs[0]:
                continue
            run = np.concatenate([z["max_distinct_10ms"] for z in zs]) > RUNAWAY_DISTINCT_10MS
            kc = np.concatenate([z["active_KC"] for z in zs])
            pn_ = np.concatenate([z["active_uPN_ACh"] for z in zs])
            d = load(cfg, cond)
            row = {"config": cfg, "condition": cond, "trials": run.size,
                   "runaway_trials": int(run.sum()),
                   "DM1 PN rate (Hz)": round(float(d["counts"][dm1_pn].mean() / d["n_trials"]), 1)}
            for lab_, m in (("healthy", ~run), ("runaway", run)):
                row[f"KCs firing per {lab_} trial (mean)"] = round(float(kc[m].mean()), 1) if m.any() else ""
                row[f"% of 5,177 KCs ({lab_})"] = round(100 * float(kc[m].mean()) / 5177, 2) if m.any() else ""
                row[f"uPNs firing per {lab_} trial"] = round(float(pn_[m].mean()), 1) if m.any() else ""
            sm.append(row)
    S = pd.DataFrame(sm)
    S.to_csv(RES / "smell_and_kc.csv", index=False)
    R, C, P, GR, W, T = (pd.DataFrame(x) for x in (rows, checks, pn, gr, rw, top))
    for df, name in ((R, "readouts"), (C, "checks"), (P, "per_neuron"), (GR, "group_rates"),
                     (W, "runaway"), (T, "top_changes")):
        df.to_csv(RES / f"{name}.csv", index=False)

    md = ["# Phase 7 upgrade 4 (cell-type-specific parameters): whole-brain checks (snapshot 630)", "",
          "PRELIMINARY (PLAN.md Phase 6 not complete: seeds rerun and variants run; no independent "
          "review).", "",
          f"Each check condition: 3 seeds x {N_TRIALS} trials x 1 s (variants: 1 seed). Runaway "
          f"conditions: 5 seeds = 150 trials. Runaway (Phase 6 definition) = a trial where more "
          f"than {RUNAWAY_DISTINCT_10MS} different neurons fire in one 10 ms slice.", "",
          *[f"- {n}" for n in notes], ""]
    for cfg in configs:
        f = RES / cfg / "config.json"
        if f.exists():
            ct = json.loads(f.read_text())["celltype"]
            if isinstance(ct, dict):
                gs = {g: {k: v[k] for k in ("n_neurons", "t_mbr", "gap")} for g, v in ct["groups"].items()}
                md.append(f"- **{cfg}**: {ct['n_neurons_changed']} neurons changed; `{json.dumps(gs)}`")
            else:
                md.append(f"- **{cfg}**: {ct}")
    md += ["", "## MN9 and network size", "", md_table(R)]
    md += ["", "## Phase 3 checks (a check holds only if it passes for every seed)", ""]
    if len(C):
        piv = C.pivot(index="check", columns="config", values="per_seed")
        md.append(md_table(piv[[c for c in configs if c in piv.columns]], index=True))
    md += ["", "## Runaway activity (Phase 6 definition)", "", md_table(W) if len(W) else "(not run)"]
    md += ["", "## Neuron by neuron vs the baseline (stimulated neurons excluded; same seeds)", "",
           "Noise floor = `baseline_newseeds` vs `baseline`.", ""]
    if len(P):
        Ps = P.copy()
        Ps["pearson_r"] = Ps["pearson_r"].map(lambda x: f"{x:.4f}")
        md.append(md_table(Ps))
    md += ["", "## Changed cell groups: mean rate per neuron (Hz)", ""]
    if len(GR):
        piv = GR.pivot_table(index=["condition", "group"], columns="config", values="mean_rate_hz")
        md.append(md_table(piv[[c for c in configs if c in piv.columns]].round(3), index=True))
    md += ["", "## Kenyon cells and PNs per trial (runs saved with per-trial group counts)", "",
           "Turner et al. 2008 (p. 739): on average 6 +/- 5% of Kenyon cells respond to a given "
           "odor (their own response criterion).", "",
           md_table(S) if len(S) else "(not run)"]
    md += ["", "## Largest single-neuron changes, CT_main vs baseline (all trials)", "",
           md_table(T) if len(T) else "(none)"]
    (RES / "summary.md").write_text("\n".join(md), encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()

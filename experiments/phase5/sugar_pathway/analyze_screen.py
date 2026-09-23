"""Statistics, classification and paper comparison for the silencing screen.

Plain English
-------------
For every silenced neuron we have 30 trials of MN9 firing, and 30 trials of
the unsilenced baseline that used exactly the same random sugar input
(same seed). So trial 1 is compared with trial 1, trial 2 with trial 2, and
so on ("paired" comparison). The test is the Wilcoxon signed-rank test: it
asks whether the silenced trials are consistently lower (or higher) than
their baseline twins, more than chance would allow. Because we test
hundreds of neurons at once, some would look "significant" by luck; the
Benjamini-Hochberg correction keeps the expected share of such false alarms
at 5% (q < 0.05).

Classes (ratio = silenced MN9 rate / baseline MN9 rate):
  blocks            q < 0.05 and ratio <= 0.50  (MN9 loses half or more)
  reduces (strong)  q < 0.05 and 0.50 < ratio <= 0.80  (the paper's 20% line)
  reduces (weak)    q < 0.05 and 0.80 < ratio < 1
  increases         q < 0.05 and ratio > 1  (silencing a brake)
  redundant         q >= 0.05  (no detectable change)

Usage: python analyze_screen.py singles|robust
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ids import SUGAR, MN9, MN9_B  # noqa: E402
import paper_tables  # noqa: E402
from trace_paths import paper_name_map  # noqa: E402

RES = HERE / "results"
CACHE = ROOT / "data" / "cache"


def bh(p):
    p = np.asarray(p, float)
    n = len(p)
    order = np.argsort(p)
    q = p[order] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(q, 1.0)
    return out


def per_trial(runs, cond_id, col="mn9_hz"):
    r = runs[runs["cond_id"] == cond_id].sort_values("trial")
    return r[col].to_numpy(float)


def paired_test(x, base):
    d = x - base
    if np.all(d == 0):
        return 1.0
    try:
        return float(stats.wilcoxon(x, base, zero_method="wilcox").pvalue)
    except ValueError:
        return 1.0


def classify(ratio, q):
    if not np.isfinite(ratio) or q >= 0.05:
        return "redundant"
    if ratio <= 0.5:
        return "blocks"
    if ratio <= 0.8:
        return "reduces (strong, >=20%)"
    if ratio < 1:
        return "reduces (weak, <20%)"
    return "increases"


def labels():
    nr = pd.read_parquet(CACHE / "connectome_630_neurons.parquet",
                         columns=["root_id", "cell_type", "super_class", "cell_class", "side",
                                  "top_nt", "ref_sign"])
    nr["root_id"] = nr["root_id"].astype(np.int64)
    names = paper_name_map()
    nr["paper_name"] = nr["root_id"].map(names).fillna("")
    return nr.set_index("root_id")


def stats_table(runs, kind, seed=0):
    """One row per silencing condition of this kind (or list of kinds) and seed.
    A 10-trial (stage-1) run is compared with the first 10 baseline trials,
    which had exactly the same random input."""
    kinds = [kind] if isinstance(kind, str) else list(kind)
    sub = runs[runs["kind"].isin(kinds) & (runs["seed"] == seed)]
    rows = []
    for cid, g in sub.groupby("cond_id", sort=False):
        hz = int(g["stim_hz"].iloc[0])
        x = g.sort_values("trial")["mn9_hz"].to_numpy(float)
        xb = g.sort_values("trial")["mn9b_hz"].to_numpy(float)
        base = per_trial(runs, f"base_{hz}_s{seed}")[: len(x)]
        base_b = per_trial(runs, f"base_{hz}_s{seed}", "mn9b_hz")[: len(x)]
        d = x - base
        se = d.std(ddof=1) / np.sqrt(len(d)) if len(d) > 1 else np.nan
        rows.append({"n_trials": len(x), "stage": g["kind"].iloc[0],
            "diff_hz": d.mean(), "se_paired_hz": se,
            "stage1_flag": bool((se > 0 and abs(d.mean()) > 2 * se)
                                or (base.mean() > 0 and not 0.9 <= x.mean() / base.mean() <= 1.1)),
            "cond_id": cid, "stim_hz": hz, "seed": seed, "label": g["label"].iloc[0],
            "silenced": g["silenced"].iloc[0], "n_silenced": int(g["n_silenced"].iloc[0]),
            "mn9_base_hz": base.mean(), "mn9_hz": x.mean(), "mn9_sd": x.std(),
            "ratio": x.mean() / base.mean() if base.mean() > 0 else np.nan,
            "p_wilcoxon": paired_test(x, base),
            "p_mannwhitney": float(stats.mannwhitneyu(x, base).pvalue) if not np.array_equal(x, base) else 1.0,
            "mn9b_base_hz": base_b.mean(), "mn9b_hz": xb.mean(),
            "ratio_mn9b": xb.mean() / base_b.mean() if base_b.mean() > 0 else np.nan,
            "p_wilcoxon_mn9b": paired_test(xb, base_b),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["q_bh"] = np.nan
    df["q_bh_mn9b"] = np.nan
    for hz, g in df.groupby("stim_hz"):
        df.loc[g.index, "q_bh"] = bh(g["p_wilcoxon"])
        df.loc[g.index, "q_bh_mn9b"] = bh(g["p_wilcoxon_mn9b"])
    df["class"] = [classify(r, q) for r, q in zip(df["ratio"], df["q_bh"])]
    df["class_mn9b"] = [classify(r, q) for r, q in zip(df["ratio_mn9b"], df["q_bh_mn9b"])]
    return df


def rebh(df):
    """Benjamini-Hochberg over the WHOLE family of neurons tested at each
    frequency (stage-1-only neurons included with their 10-trial p-values;
    neurons silent at 50 Hz included with p = 1), then classify."""
    for hz, g in df.groupby("stim_hz"):
        df.loc[g.index, "q_bh"] = bh(g["p_wilcoxon"])
        df.loc[g.index, "q_bh_mn9b"] = bh(g["p_wilcoxon_mn9b"])
    df["class"] = [classify(r, q) for r, q in zip(df["ratio"], df["q_bh"])]
    df["class_mn9b"] = [classify(r, q) for r, q in zip(df["ratio_mn9b"], df["q_bh_mn9b"])]
    return df


def stage1():
    """Flag stage-1 (10-trial) results for a full 30-trial re-run.
    Flag = paired MN9 change more than 2 standard errors from zero, OR MN9
    outside 90-110% of baseline."""
    runs = pd.read_csv(RES / "runs.csv")
    t = stats_table(runs, ["single_stage1", "group_stage1"])
    t["flagged"] = t["stage1_flag"]
    t.to_csv(RES / "stage1_flagged.csv", index=False)
    print(t.groupby(["stage", "stim_hz"])["flagged"].agg(["size", "sum"]).to_string())


def singles():
    runs = pd.read_csv(RES / "runs.csv")
    lab = labels()
    full = stats_table(runs, "single")
    st1 = stats_table(runs, "single_stage1")
    if not st1.empty:   # keep stage-1 rows only where no 30-trial run exists
        have = set(full["cond_id"].str.replace("sil_", "", n=1))
        st1 = st1[~st1["cond_id"].str.replace("st1_", "", n=1).isin(have)]
    sk = pd.read_csv(RES / "singles_50_skipped_silent.csv")
    silent = pd.DataFrame({"cond_id": [f"silent_50_s0_{r}" for r in sk["root_id"]], "stim_hz": 50,
                           "seed": 0, "silenced": sk["root_id"].astype(str), "n_silenced": 1,
                           "n_trials": 0, "stage": "not run: silent at 50 Hz, cannot matter",
                           "ratio": 1.0, "ratio_mn9b": 1.0, "p_wilcoxon": 1.0,
                           "p_wilcoxon_mn9b": 1.0, "diff_hz": 0.0})
    df = pd.concat([full, st1, silent], ignore_index=True)
    for hz in (100, 50):   # silent-at-50-Hz rows: MN9 is exactly the baseline
        m = (df["stim_hz"] == hz) & df["n_trials"].eq(0)
        base30 = per_trial(runs, f"base_{hz}_s0").mean()
        df.loc[m, ["mn9_base_hz", "mn9_hz"]] = base30
    df = rebh(df)
    df["root_id"] = df["silenced"].astype(np.int64)
    df = df.join(lab, on="root_id")
    cand = pd.read_csv(RES / "candidates.csv")
    df = df.merge(cand[["root_id", "rate_100hz_s0", "in_paper_top200", "is_sugar_grn"]],
                  on="root_id", how="left")
    # paper side by side
    p = paper_tables.st1c()
    normcols = [f"norm_{f}" for f in paper_tables.FREQS_1C]
    p["paper_min_norm_50_120"] = p[normcols].min(axis=1)
    p["paper_required_any_freq"] = p["paper_min_norm_50_120"] <= 0.8
    act = paper_tables.st1b()[["root_id", "act_100", "act_200"]].rename(
        columns={"act_100": "paper_mn9_when_stim_alone_100hz", "act_200": "paper_mn9_when_stim_alone_200hz"})
    df = df.merge(p[["root_id", "paper_name", "norm_100", "norm_50", "paper_min_norm_50_120",
                     "paper_required_any_freq"]].rename(columns={"paper_name": "paper_st1c_name",
                                                                 "norm_100": "paper_ratio_100hz",
                                                                 "norm_50": "paper_ratio_50hz"}),
                  on="root_id", how="left").merge(act, on="root_id", how="left")
    df = df.sort_values(["stim_hz", "ratio"], ascending=[False, True])
    df.to_csv(RES / "silencing_singles.csv", index=False)

    summ = {}
    for hz, g in df.groupby("stim_hz"):
        summ[int(hz)] = {"n_tested": int(len(g)), "baseline_mn9_hz": float(g["mn9_base_hz"].iloc[0]),
                         "classes": g["class"].value_counts().to_dict(),
                         "min_ratio": float(g["ratio"].min())}
        both = g[g["paper_ratio_100hz"].notna()]
        pcol = "paper_ratio_100hz" if hz == 100 else "paper_ratio_50hz"
        if len(both) > 2:
            summ[int(hz)]["vs_paper"] = {
                "n_overlap": int(len(both)),
                "pearson_r": float(np.corrcoef(both["ratio"], both[pcol])[0, 1]),
                "spearman_r": float(stats.spearmanr(both["ratio"], both[pcol]).statistic),
                "ours_le_0.8": int((both["ratio"] <= 0.8).sum()),
                "paper_le_0.8": int((both[pcol] <= 0.8).sum()),
                "both_le_0.8": int(((both["ratio"] <= 0.8) & (both[pcol] <= 0.8)).sum()),
            }
    (RES / "silencing_singles_summary.json").write_text(json.dumps(summ, indent=1), encoding="utf-8")
    print(json.dumps(summ, indent=1))
    return df


def groups():
    """Group silencing (cell types, named types, pathway sets, top-k)."""
    runs = pd.read_csv(RES / "runs.csv")
    full = stats_table(runs, "group")
    st1 = stats_table(runs, "group_stage1")
    if not st1.empty:
        have = set(full["cond_id"].str.split("_s0_", n=1).str[1] + "@" + full["stim_hz"].astype(str))
        st1 = st1[~(st1["cond_id"].str.split("_s0_", n=1).str[1] + "@" + st1["stim_hz"].astype(str)).isin(have)]
    g = rebh(pd.concat([full, st1], ignore_index=True))
    byname = {d["name"]: d for d in json.loads((RES / "groups.json").read_text(encoding="utf-8"))}
    defs = {c: byname[c.split("_s0_", 1)[1]] for c in g["cond_id"]}
    g["source"] = [defs[c]["source"] for c in g["cond_id"]]
    g["member_ids"] = [" ".join(defs[c]["ids"]) for c in g["cond_id"]]
    # how did the members do one at a time (same frequency)?
    s = pd.read_csv(RES / "silencing_singles.csv")
    single = {(int(r.stim_hz), int(r.root_id)): (r.ratio, r["class"]) for _, r in s.iterrows()}
    worst, all_red = [], []
    for c, hz in zip(g["cond_id"], g["stim_hz"]):
        vals = [single.get((int(hz), int(i))) for i in defs[c]["ids"]]
        vals = [v for v in vals if v is not None]
        worst.append(min((v[0] for v in vals), default=np.nan))
        all_red.append(bool(vals) and all(v[1] == "redundant" for v in vals))
    g["lowest_single_ratio"] = worst
    g["all_members_singly_redundant"] = all_red
    g["group_matters_beyond_singles"] = g["all_members_singly_redundant"] & (g["class"] != "redundant")
    g = g.sort_values(["stim_hz", "ratio"], ascending=[False, True])
    g.to_csv(RES / "silencing_groups.csv", index=False)
    summ = g.groupby(["stim_hz", "source"])["class"].value_counts().unstack(fill_value=0)
    print(summ.to_string())
    print(g[["cond_id", "ratio", "class", "lowest_single_ratio", "all_members_singly_redundant"]]
          .head(25).to_string(index=False))


def pick_robust():
    """Choose what to re-run with seeds 1-3: every single neuron or group that
    blocks or strongly reduces MN9, plus the 5 largest single effects at each
    frequency whatever their class (so 'reduces (weak)' is checked too), plus
    the most-increasing single neuron at each frequency (sign check)."""
    s = pd.read_csv(RES / "silencing_singles.csv")
    g = pd.read_csv(RES / "silencing_groups.csv") if (RES / "silencing_groups.csv").exists() else pd.DataFrame()
    strong = ("blocks", "reduces (strong, >=20%)")
    pick = []
    for hz in (100, 50):
        x = s[s["stim_hz"] == hz]
        sel = pd.concat([x[x["class"].isin(strong)], x.nsmallest(5, "ratio"),
                         x[x["class"] == "increases"].nlargest(1, "ratio")]).drop_duplicates("cond_id")
        for _, r in sel.iterrows():
            pick.append({"cond_id": r["cond_id"], "kind": "single", "stim_hz": int(hz),
                         "label": str(r.get("paper_name") or r.get("cell_type") or ""),
                         "silence": [str(int(r["root_id"]))]})
    if not g.empty:
        defs = {f"grp_{hz}_s0_{d['name']}": d
                for d in json.loads((RES / "groups.json").read_text(encoding="utf-8")) for hz in (100, 50)}
        for _, r in g[g["class"].isin(strong)].iterrows():
            pick.append({"cond_id": r["cond_id"], "kind": "group", "stim_hz": int(r["stim_hz"]),
                         "label": r["label"], "silence": defs[r["cond_id"]]["ids"]})
    (RES / "robust_list.json").write_text(json.dumps(pick, indent=1), encoding="utf-8")
    print(len(pick), "conditions picked for seeds 1-3")


def params():
    """w_syn +/-20% check of the key blocking results (seed 0, 100 Hz):
    each silenced run is compared with the normal run at the same w_syn."""
    runs = pd.read_csv(RES / "runs.csv")
    rows = []
    for tag in ("wsyn0.22", "wsyn0.33"):
        base = per_trial(runs, f"base_100_s0_{tag}")
        if base.size == 0:
            continue
        rows.append({"w_syn": tag[4:], "condition": "normal (no silencing)", "mn9_hz": base.mean(),
                     "ratio": 1.0, "p_wilcoxon": np.nan})
        for cid in sorted(runs.loc[runs["cond_id"].str.startswith(f"par_100_s0_{tag}_"), "cond_id"].unique()):
            x = per_trial(runs, cid)
            rows.append({"w_syn": tag[4:], "condition": cid.split(f"{tag}_", 1)[1], "mn9_hz": x.mean(),
                         "ratio": x.mean() / base.mean() if base.mean() > 0 else np.nan,
                         "p_wilcoxon": paired_test(x, base)})
    df = pd.DataFrame(rows)
    df.to_csv(RES / "wsyn_check.csv", index=False)
    print(df.to_string(index=False))


def robust():
    """Re-runs with seeds 1-3; each seed is compared with its own baseline."""
    runs = pd.read_csv(RES / "runs.csv")
    out = []
    for kind in ("single_robust", "group_robust"):
        for seed in (1, 2, 3):
            t = stats_table(runs, kind, seed)
            if not t.empty:
                t["kind"] = kind
                out.append(t)
    if not out:
        print("no robust runs yet")
        return
    rob = pd.concat(out, ignore_index=True)
    rob["base_cond"] = rob["cond_id"].str.replace(r"_s[123]_", "_s0_", regex=True)
    rob.to_csv(RES / "robustness_seeds.csv", index=False)
    s0 = []
    for f in ("silencing_singles.csv", "silencing_groups.csv"):
        if (RES / f).exists():
            s0.append(pd.read_csv(RES / f)[["cond_id", "ratio", "class"]])
    s0 = pd.concat(s0).set_index("cond_id")
    agg = rob.groupby("base_cond").agg(
        label=("label", "first"), stim_hz=("stim_hz", "first"),
        ratio_seed1=("ratio", lambda s: s.iloc[0] if len(s) > 0 else np.nan),
        ratios_seeds123=("ratio", lambda s: " / ".join(f"{v:.3f}" for v in s)),
        classes_seeds123=("class", lambda s: " / ".join(s)),
        max_q=("q_bh", "max"))
    agg = agg.join(s0.rename(columns={"ratio": "ratio_seed0", "class": "class_seed0"}))
    agg["same_class_all_4_seeds"] = [
        all(c == c0 for c in cl.split(" / ")) for cl, c0 in zip(agg["classes_seeds123"], agg["class_seed0"])]
    agg.drop(columns=["ratio_seed1"]).to_csv(RES / "robustness_summary.csv")
    print(agg[["stim_hz", "ratio_seed0", "ratios_seeds123", "class_seed0",
               "same_class_all_4_seeds"]].to_string(max_colwidth=40))


if __name__ == "__main__":
    {"stage1": stage1, "singles": singles, "groups": groups, "pick_robust": pick_robust, "params": params,
     "robust": robust}[sys.argv[1]]()

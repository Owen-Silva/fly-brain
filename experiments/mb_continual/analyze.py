"""Summaries, the pre-registered verdicts and the figures.

Reads results/raw/incr_*.csv.gz, results/raw/capacity.csv (and mnist.csv if present).
Writes small tables to results/: incremental_summary.csv, verdicts.csv,
variants_summary.csv, groups.csv, exposure_test.csv, capacity_summary.csv, cost.csv,
summary.json; figures to results/fig_*.png.
"""
import json

import numpy as np
import pandas as pd
from scipy import stats

from common import CHEM_CLASSES, FRUIT_CLASSES, RAW, RES, load_odours, save_json

N_TASKS = 10
FLY = ["fly_real", "fly_shuffled", "fly_uniform"]


def load_incr(variant):
    d = pd.read_csv(RAW / f"incr_{variant}.csv.gz")
    f = RAW / f"incr_{variant}_tasks.csv"
    if f.exists():
        tasks = pd.read_csv(f)
    else:   # run still going: rebuild the (deterministic) task order, as run_incremental.py
        tasks = pd.DataFrame([{"seed": s, "odour": int(o), "task": ti}
                              for s in sorted(d.seed.unique())
                              for ti, t in enumerate(np.array_split(
                                  np.random.default_rng([s, 202]).permutation(110), N_TASKS))
                              for o in t])
    return d, tasks


def per_run(d, tasks):
    """(seed, side, model) -> final accuracy and memory loss (Shen et al. definition)."""
    d = d.merge(tasks, on=["seed", "odour"])
    last = d[d.after_task == N_TASKS - 1]
    fin = last.groupby(["seed", "side", "model"]).apply(
        lambda x: x.correct.sum() / x.n.sum(), include_groups=False).rename("final_acc")
    # immediate accuracy of task i = right after task i, on task i's odours
    imm = d[d.after_task == d.task]
    fin_t = last[last.task < N_TASKS - 1]
    a = imm[imm.task < N_TASKS - 1].groupby(["seed", "side", "model", "task"])[["correct", "n"]].sum()
    b = fin_t.groupby(["seed", "side", "model", "task"])[["correct", "n"]].sum()
    ml = ((a.correct / a.n) - (b.correct / b.n)).groupby(["seed", "side", "model"]).mean()
    out = pd.concat([fin, ml.rename("memory_loss")], axis=1).reset_index()
    return out


def curve(d):
    """Accuracy on everything taught so far, after each task."""
    g = d.groupby(["seed", "side", "model", "after_task"])[["correct", "n"]].sum()
    return (g.correct / g.n).rename("acc").reset_index()


def compare(x, y):
    """Paired comparison over seeds (x, y aligned by seed). Returns dict with mean
    difference, paired SE, unpaired SE and the pre-registered 2-SE call."""
    x, y = np.asarray(x, float), np.asarray(y, float)
    d = x - y
    n = d.size
    se_p = d.std(ddof=1) / np.sqrt(n)
    se_u = np.sqrt(x.var(ddof=1) / n + y.var(ddof=1) / n)
    m = d.mean()
    if m > 2 * se_p and m > 2 * se_u:
        call = "higher"
    elif m < -2 * se_p and m < -2 * se_u:
        call = "lower"
    else:
        call = "no clear difference"
    return {"n_seeds": n, "mean_a": x.mean(), "mean_b": y.mean(), "diff": m, "se_paired": se_p,
            "se_unpaired": se_u, "diff_over_se_paired": m / se_p if se_p > 0 else np.nan,
            "call": call}


def real_vs_controls(runs, metric="final_acc"):
    rows = []
    for side in ("left", "right"):
        r = runs[(runs.side == side)].pivot(index="seed", columns="model", values=metric)
        for ctl in ("fly_shuffled", "fly_uniform"):
            c = compare(r["fly_real"], r[ctl])
            rows.append({"side": side, "control": ctl.replace("fly_", ""), **c})
    return pd.DataFrame(rows)


def verdict(tab):
    """Pre-registered rule: WIN if 'higher' for both controls in both halves; LOSE if,
    for at least one control, 'lower' in both halves; else NO CLEAR DIFFERENCE."""
    if (tab.call == "higher").all():
        return "REAL WIRING WINS"
    for ctl in ("shuffled", "uniform"):
        t = tab[tab.control == ctl]
        if len(t) == 2 and (t.call == "lower").all():
            return "REAL WIRING LOSES"
    return "NO CLEAR DIFFERENCE"


def main():
    summary = {}
    # ------------------------------------------------------------------ main run
    d, tasks = load_incr("main")
    runs = per_run(d, tasks)
    runs.to_csv(RES / "incremental_runs_main.csv", index=False)
    tab = runs.groupby(["side", "model"]).agg(
        n_seeds=("final_acc", "size"), final_acc=("final_acc", "mean"),
        final_acc_se=("final_acc", lambda x: x.std(ddof=1) / np.sqrt(x.size)),
        memory_loss=("memory_loss", "mean"),
        memory_loss_se=("memory_loss", lambda x: x.std(ddof=1) / np.sqrt(x.size))).reset_index()
    tab.to_csv(RES / "incremental_summary.csv", index=False)
    rv = real_vs_controls(runs)
    rv.to_csv(RES / "verdicts.csv", index=False)
    summary["primary_verdict"] = verdict(rv)
    summary["primary_table"] = rv.round(4).to_dict("records")
    # fly (real) vs MLP sequential: forgetting and final accuracy (unpaired, 2 SE)
    q1 = []
    for side in ("left", "right"):
        r = runs[runs.side == side]
        f = r[r.model == "fly_real"]
        m = r[r.model == "mlp_seq"]
        j = r[r.model == "mlp_joint"]
        for metric in ("final_acc", "memory_loss"):
            if len(m) == 0:
                continue
            x, y = f[metric].to_numpy(), m[metric].to_numpy()
            se = np.sqrt(x.var(ddof=1) / x.size + y.var(ddof=1) / y.size)
            q1.append({"side": side, "metric": metric, "fly_real": x.mean(), "mlp_seq": y.mean(),
                       "diff": x.mean() - y.mean(), "se_unpaired": se,
                       "call": ("fly higher" if x.mean() - y.mean() > 2 * se else
                                "fly lower" if x.mean() - y.mean() < -2 * se else "no clear difference"),
                       "mlp_joint_final_acc": j.final_acc.mean() if len(j) else np.nan})
    q1 = pd.DataFrame(q1)
    q1.to_csv(RES / "fly_vs_mlp.csv", index=False)
    summary["fly_vs_mlp"] = q1.round(4).to_dict("records")
    cv = curve(d)
    cv.to_csv(RES / "incremental_curve_main.csv", index=False)

    # ------------------------------------------------------------------ cost
    cost = pd.read_csv(RAW / "incr_main_cost.csv")
    # run_incremental.py counted all 110 outputs for mlp_seq; while training task t only the
    # 11 * t outputs seen so far get gradients (mean 60.5). Back out the active hidden share
    # from the stored number and recount with 60.5 outputs.
    s = cost.model == "mlp_seq"
    a = (cost.loc[s, "changed_per_example"] - 110) / (55 + 1 + 110) / cost.loc[s, "n_hidden"]
    cost.loc[s, "changed_per_example"] = a * cost.loc[s, "n_hidden"] * (55 + 1 + 60.5) + 60.5
    ct = cost.groupby("model")[["changed_per_example", "frac_active_test", "n_hidden"]].mean()
    if "n_weights" in cost:
        ct["n_weights"] = cost.groupby("model").n_weights.mean()
    ct.to_csv(RES / "cost.csv")
    summary["cost"] = ct.round(4).reset_index().to_dict("records")

    # ------------------------------------------------------------------ odour groups
    od = load_odours()
    last = d[d.after_task == N_TASKS - 1].copy()
    last["chem"] = od.chem[last.odour.to_numpy()]
    last["fruit"] = np.where(np.isin(last.chem, FRUIT_CLASSES), "fruit (esters+alcohols+acids)",
                             "other")
    # post hoc grouping: odours whose PN drive runs most / least through the food community
    from common import pn_mean as _pn
    _c = pd.read_csv(RES / "communities.csv")
    _fg = set(_c[_c.glomeruli.str.split().apply(lambda g: "DM1" in g)].iloc[0].glomeruli.split())
    _P = _pn(od.delta, od.set_a)
    _sh = _P[:, [g in _fg for g in od.gloms]].sum(1) / np.maximum(_P.sum(1), 1e-9)
    last["foodshare"] = np.where(_sh[last.odour.to_numpy()] >= np.median(_sh),
                                 "high food-community share (post hoc)",
                                 "low food-community share (post hoc)")
    grp_rows = []
    for gcol in ("fruit", "chem", "foodshare"):
        g = last[last.model.isin(FLY)].groupby(["seed", "side", "model", gcol])[["correct", "n"]].sum()
        g = (g.correct / g.n).rename("acc").reset_index()
        for side in ("left", "right"):
            for grp in sorted(g[gcol].unique()):
                x = g[(g.side == side) & (g[gcol] == grp)].pivot(index="seed", columns="model",
                                                                 values="acc")
                for ctl in ("fly_shuffled", "fly_uniform"):
                    c = compare(x["fly_real"], x[ctl])
                    grp_rows.append({"grouping": gcol, "group": grp, "side": side,
                                     "control": ctl.replace("fly_", ""), **c})
    groups = pd.DataFrame(grp_rows)
    groups.to_csv(RES / "groups.csv", index=False)
    # post hoc: is the real-wiring deficit smaller for fruit odours than for the others?
    g = last[last.model.isin(FLY)].groupby(["seed", "side", "model", "fruit"])[["correct", "n"]].sum()
    g = (g.correct / g.n).rename("acc").reset_index()
    inter = []
    for side in ("left", "right"):
        x = g[g.side == side].pivot_table(index="seed", columns=["fruit", "model"], values="acc")
        for ctl in ("fly_shuffled", "fly_uniform"):
            fr = x[("fruit (esters+alcohols+acids)", "fly_real")] - x[("fruit (esters+alcohols+acids)", ctl)]
            ot = x[("other", "fly_real")] - x[("other", ctl)]
            inter.append({"side": side, "control": ctl.replace("fly_", ""),
                          **compare(fr.to_numpy(), ot.to_numpy())})
    pd.DataFrame(inter).to_csv(RES / "groups_fruit_vs_other_posthoc.csv", index=False)

    # ------------------------------------------------------------------ exposure test
    ex = pd.read_csv(RES / "odour_exposure.csv")
    po = last[last.model.isin(FLY)].groupby(["side", "model", "odour"])[["correct", "n"]].sum()
    po = (po.correct / po.n).rename("acc").reset_index()
    ex_rows = []
    for side in ("left", "right"):
        x = po[po.side == side].pivot(index="odour", columns="model", values="acc")
        for ctl in ("fly_shuffled", "fly_uniform"):
            diff = (x["fly_real"] - x[ctl]).to_numpy()
            rho = stats.spearmanr(ex.exposure.to_numpy()[x.index], diff)
            ex_rows.append({"side": side, "control": ctl.replace("fly_", ""),
                            "spearman_rho": rho.statistic, "p": rho.pvalue})
    exposure = pd.DataFrame(ex_rows)
    exposure.to_csv(RES / "exposure_test.csv", index=False)
    summary["exposure_test"] = exposure.round(4).to_dict("records")
    # S6b, POST HOC (not pre-registered): the same test with the community that holds the
    # classic food glomeruli (DM1-DM4 ...), which had the 2nd-highest within-cluster z.
    from common import pn_mean
    comm = pd.read_csv(RES / "communities.csv")
    food = comm[comm.glomeruli.str.split().apply(lambda g: "DM1" in g)].iloc[0]
    fg = set(food.glomeruli.split())
    P = pn_mean(od.delta, od.set_a)
    fmask = np.array([g in fg for g in od.gloms])
    ex_food = P[:, fmask].sum(1) / np.maximum(P.sum(1), 1e-9)
    pd.DataFrame({"odour": od.names, "chem_class": od.chem, "food_community_share": ex_food}).to_csv(
        RES / "odour_exposure_food_community.csv", index=False)
    fx_rows = []
    for side in ("left", "right"):
        x = po[po.side == side].pivot(index="odour", columns="model", values="acc")
        for ctl in ("fly_shuffled", "fly_uniform"):
            diff = (x["fly_real"] - x[ctl]).to_numpy()
            rho = stats.spearmanr(ex_food[x.index], diff)
            hi = ex_food[x.index] >= np.median(ex_food)
            fx_rows.append({"side": side, "control": ctl.replace("fly_", ""),
                            "spearman_rho": rho.statistic, "p": rho.pvalue,
                            "mean_diff_top_half_share": diff[hi].mean(),
                            "mean_diff_bottom_half_share": diff[~hi].mean()})
    fx = pd.DataFrame(fx_rows)
    fx.to_csv(RES / "exposure_test_food_community_posthoc.csv", index=False)
    summary["food_community_posthoc"] = {"glomeruli": sorted(fg),
                                         "tests": fx.round(4).to_dict("records")}

    # ------------------------------------------------------------------ variants
    var_rows = []
    for v in ("k2", "k3", "k5", "k7.5", "k10", "T0.02", "T0.1", "T0.2", "T0.5",
              "syn5", "kcnorm", "setA"):
        vv = "main" if v == "k5" else v
        if not (RAW / f"incr_{vv}.csv.gz").exists():
            continue
        dv, tv = load_incr(vv)
        rv_v = per_run(dv, tv)
        t = real_vs_controls(rv_v)
        for _, r in t.iterrows():
            var_rows.append({"variant": v, **r.to_dict()})
        for side in ("left", "right"):
            for mdl in ("fly_real", "fly_shuffled", "fly_uniform", "mlp_seq", "mlp_joint"):
                s = rv_v[(rv_v.side == side) & (rv_v.model == mdl)]
                if len(s):
                    var_rows.append({"variant": v, "side": side, "control": f"[{mdl}]",
                                     "mean_a": s.final_acc.mean(), "n_seeds": len(s)})
        summary.setdefault("variant_verdicts", {})[v] = verdict(t)
    pd.DataFrame(var_rows).to_csv(RES / "variants_summary.csv", index=False)

    # ------------------------------------------------------------------ capacity
    # "" = pre-registered S4 (T = 0.05 s); "_T0.5" = post hoc, fly only, less noise
    for tag in ("", "_T0.5"):
        if not (RAW / f"capacity{tag}.csv").exists():
            continue
        cap = pd.read_csv(RAW / f"capacity{tag}.csv")
        cap.groupby(["side", "model", "N"]).error.agg(["mean", "sem", "size"]).reset_index().to_csv(
            RES / f"capacity_curve{tag}.csv", index=False)

        def n_at_10(x):
            x = x.sort_values("N")
            e, n = x.error.to_numpy(), x.N.to_numpy()
            above = np.flatnonzero(e > 0.10)
            if above.size == 0:
                return np.nan          # never above 10% up to N = 110
            i = above[0]
            if i == 0:
                return float(n[0])
            # linear interpolation between the last point <= 10% and the first > 10%
            return float(n[i - 1] + (0.10 - e[i - 1]) * (n[i] - n[i - 1]) / (e[i] - e[i - 1]))

        capn = cap.groupby(["seed", "side", "model"]).apply(n_at_10, include_groups=False)
        capn = capn.rename("capacity").reset_index()
        capn.to_csv(RES / f"capacity_runs{tag}.csv", index=False)
        cs = capn.groupby(["side", "model"]).capacity.agg(
            ["mean", "sem", "size", lambda x: int(x.isna().sum())]).reset_index()
        cs.columns = ["side", "model", "capacity_mean", "capacity_se", "n_seeds", "n_never_above_10pct"]
        e110 = cap[cap.N == 110].groupby(["side", "model"]).error.mean().rename("error_at_110")
        cs = cs.merge(e110.reset_index(), on=["side", "model"], how="left")
        cs.to_csv(RES / f"capacity_summary{tag}.csv", index=False)
        crow = []
        for capname in ("capped", "uncapped"):
            for side in ("left", "right"):
                x = capn[capn.side == side].pivot(index="seed", columns="model", values="capacity")
                for ctl in ("shuffled", "uniform"):
                    a_, b_ = x[f"fly_real_{capname}"], x[f"fly_{ctl}_{capname}"]
                    ok = a_.notna() & b_.notna()
                    crow.append({"weights": capname, "side": side, "control": ctl,
                                 **compare(a_[ok], b_[ok])})
        crt = pd.DataFrame(crow)
        crt.to_csv(RES / f"capacity_verdicts{tag}.csv", index=False)
        summary[f"capacity{tag}_verdict_capped"] = verdict(crt[crt.weights == "capped"])
        summary[f"capacity{tag}_verdict_uncapped"] = verdict(crt[crt.weights == "uncapped"])
    # ------------------------------------------------------------------ MNIST (S8)
    if (RAW / "mnist.csv").exists():
        mn = pd.read_csv(RAW / "mnist.csv")
        sat = mn[mn.after_task == -1].groupby(["side", "model"]).acc.mean().rename("saturated_share")
        mn = mn[mn.after_task >= 0].copy()
        mn["correct"] = mn.acc * mn.n
        tasks_of = {d_: d_ // 2 for d_ in range(10)}
        mn["task"] = mn.digit.map(tasks_of)
        fin = mn[mn.after_task == 4].groupby(["seed", "side", "model"])[["correct", "n"]].sum()
        fin = (fin.correct / fin.n).rename("final_acc")
        imm = mn[(mn.after_task == mn.task) & (mn.task < 4)].groupby(
            ["seed", "side", "model", "task"])[["correct", "n"]].sum()
        end = mn[(mn.after_task == 4) & (mn.task < 4)].groupby(
            ["seed", "side", "model", "task"])[["correct", "n"]].sum()
        ml = ((imm.correct / imm.n) - (end.correct / end.n)).groupby(["seed", "side", "model"]).mean()
        mr = pd.concat([fin, ml.rename("memory_loss")], axis=1).reset_index()
        mr.to_csv(RES / "mnist_runs.csv", index=False)
        ms = mr.groupby(["side", "model"]).agg(n_seeds=("final_acc", "size"),
                                               final_acc=("final_acc", "mean"),
                                               final_acc_se=("final_acc", "sem"),
                                               memory_loss=("memory_loss", "mean")).reset_index()
        ms = ms.merge(sat.reset_index(), on=["side", "model"], how="left")
        ms.to_csv(RES / "mnist_summary.csv", index=False)
        mrow = []
        for capname in ("capped", "uncapped"):
            for side in ("left", "right"):
                x = mr[mr.side == side].pivot(index="seed", columns="model", values="final_acc")
                for ctl in ("shuffled", "uniform"):
                    mrow.append({"weights": capname, "side": side, "control": ctl,
                                 **compare(x[f"fly_real_{capname}"], x[f"fly_{ctl}_{capname}"])})
        mv = pd.DataFrame(mrow)
        mv.to_csv(RES / "mnist_verdicts.csv", index=False)
        summary["mnist_verdict_capped"] = verdict(mv[mv.weights == "capped"])
        summary["mnist_summary"] = ms.round(4).to_dict("records")
    save_json(summary, RES / "summary.json")
    print(json.dumps({k: summary[k] for k in summary if "verdict" in k}, indent=1))


if __name__ == "__main__":
    main()

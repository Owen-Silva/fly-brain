"""Score every variant on the pre-registered held-out tests (docs/heldout-validation.md).

Plain English
-------------
Reads results/<variant>/ written by run_heldout.py and the paper's own numbers
(results/published_summary.json, results/published_top300.csv, and the
published Fig. 5b file) and writes:

  results/summary.json   every number used, per variant and seed
  results/summary.md     the tables that go into the doc
  plots/abn1_curves.png  aBN1 firing vs stimulation rate, ours vs the paper's

It also scores the held-out feeding tests G1-G5 (results/feeding/<variant>.csv,
from feeding_heldout.py) and the Phase 6 robustness checks (results/robustness.csv,
from robustness.py).

Pass / fail rules are copied from section 1 of the doc, not tuned afterwards.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ids  # noqa: E402
from run_heldout import CONDITIONS, DNGE220, KEY, SEEDS  # noqa: E402

RESULTS = HERE / "results"
PLOTS = HERE / "plots"
PUB = json.loads((RESULTS / "published_summary.json").read_text(encoding="utf-8"))
TOP = pd.read_csv(RESULTS / "published_top300.csv")
NONJON_TOP = [int(i) for i in TOP.root_id if int(i) not in set(ids.JON_ALL)]
VARIANTS = ["none", "al_ln_literature", "al_ln_literature+da_5ht_literature",
            "delays", "adaptation", "celltype", "gap"]
REST_MV = -52.0


def vdir(v):
    return RESULTS / v.replace("+", "__")


def load_cond(v, name):
    """{seed k: npz} for the seeds that exist."""
    out = {}
    for k in range(len(SEEDS)):
        f = vdir(v) / f"{name}_s{k}.npz"
        if f.exists():
            out[k] = np.load(f)
    return out


def key_rates(z):
    names = [str(s) for s in z["key_names"]]
    r = z["key_trials"].mean(axis=1)          # 1 s trials -> Hz
    return dict(zip(names, r))


def rates_by_seed(v, name):
    return {k: key_rates(z) for k, z in load_cond(v, name).items()}


def all_seeds(d, n=len(SEEDS)):
    return len(d) == n


def fmt(x, nd=1):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def mean_over(d, key):
    return float(np.mean([r[key] for r in d.values()])) if d else float("nan")


def test_A(v):
    ce100, ce220 = rates_by_seed(v, "CE_100"), rates_by_seed(v, "CE_220")
    f100, f220 = rates_by_seed(v, "F_100"), rates_by_seed(v, "F_220")
    if not all(all_seeds(d) for d in (ce100, ce220, f100, f220)):
        return None
    ok = all(ce100[k]["aBN1"] >= 10 and ce220[k]["aBN1"] >= 40
             and f100[k]["aBN1"] <= 0.25 * ce100[k]["aBN1"]
             and f220[k]["aBN1"] <= 0.25 * ce220[k]["aBN1"] for k in ce100)
    return {"pass": bool(ok),
            "aBN1_CE_100": mean_over(ce100, "aBN1"), "aBN1_CE_220": mean_over(ce220, "aBN1"),
            "aBN1_F_100": mean_over(f100, "aBN1"), "aBN1_F_220": mean_over(f220, "aBN1"),
            "per_seed_CE_100": [ce100[k]["aBN1"] for k in sorted(ce100)],
            "per_seed_F_220": [f220[k]["aBN1"] for k in sorted(f220)]}


def test_B(v):
    s100, s220 = rates_by_seed(v, "Fsil_100"), rates_by_seed(v, "Fsil_220")
    f100, f220 = rates_by_seed(v, "F_100"), rates_by_seed(v, "F_220")
    if not all(all_seeds(d) for d in (s100, s220, f100, f220)):
        return None
    ok = all(s100[k]["aBN1"] >= 10 and s220[k]["aBN1"] >= 40
             and s100[k]["aBN1"] >= 5 * f100[k]["aBN1"] and s220[k]["aBN1"] >= 5 * f220[k]["aBN1"]
             for k in s100)
    return {"pass": bool(ok), "aBN1_Fsil_100": mean_over(s100, "aBN1"),
            "aBN1_Fsil_220": mean_over(s220, "aBN1")}


def _published_5b():
    b = pd.read_csv(RESULTS / "published/results/figure_5/fig_5b_rate.csv", index_col=0)
    b = b[[c for c in b.columns if c.startswith("JON_All_")]]
    b.columns = [int(c.split("_")[-1][:-2]) for c in b.columns]
    return b


def pattern_similarity(v, name, rate, root_ids):
    """Pearson r (and on log(1+rate)) between our and the paper's per-neuron rates,
    non-JON neurons that fired in either run, all seeds pooled."""
    zs = load_cond(v, name)
    if not zs:
        return None
    counts = np.zeros(len(root_ids))
    for z in zs.values():
        counts[z["nz_idx"]] += z["nz_count"]
    ours = pd.Series(counts / (30 * len(zs)), index=root_ids)
    pub = _published_5b()[rate]
    jon = set(ids.JON_ALL)
    union = sorted((set(ours[ours > 0].index) | set(pub[pub > 0].index)) - jon)
    a = ours.reindex(union).fillna(0).to_numpy()
    b = pub.reindex(union).fillna(0).to_numpy()
    # neurons that fired, counted per seed (30 trials, like the paper's one run of 30)
    jon_mask = np.isin(root_ids, list(jon))
    per_seed = [int((~jon_mask[z["nz_idx"]]).sum()) for z in zs.values()]
    return {"n_nonJON_fired_ours": float(np.mean(per_seed)),
            "n_nonJON_fired_ours_per_seed": per_seed,
            "n_nonJON_fired_ours_all_seeds_pooled": int(((ours > 0) & ~ours.index.isin(list(jon))).sum()),
            "n_nonJON_fired_paper": int(((pub > 0) & ~pub.index.isin(list(jon))).sum()),
            "pearson_r": float(np.corrcoef(a, b)[0, 1]),
            "pearson_r_log": float(np.corrcoef(np.log1p(a), np.log1p(b))[0, 1]),
            "n_union": len(union)}


def test_C(v, root_ids):
    a100, a140, a220 = (rates_by_seed(v, n) for n in ("ALL_100", "ALL_140", "ALL_220"))
    if not all(all_seeds(d) for d in (a140, a220)):      # 100 Hz is optional (not in the rule)
        return None
    ok = all(a220[k]["aBN1"] >= 5 and a220[k]["aDN1"] >= 5 and a220[k]["aDN2"] >= 5
             and a140[k]["aDN1"] >= 5 for k in a220)
    out = {"pass": bool(ok)}
    for lab, d in (("100", a100), ("140", a140), ("220", a220)):
        if not d:
            continue
        for n in ("aBN1", "aDN1", "aDN2", "DNge220"):
            out[f"{n}_{lab}"] = mean_over(d, n)
        out[f"aBN2_2026_{lab}"] = float(np.mean([np.mean([r["aBN2_1"], r["aBN2_2"], r["aBN2_3"]])
                                                 for r in d.values()]))
    out["similarity_220"] = pattern_similarity(v, "ALL_220", 220, root_ids)
    out["similarity_140"] = pattern_similarity(v, "ALL_140", 140, root_ids)
    return out


def test_D(v):
    f = vdir(v) / "sufficiency.csv"
    if not f.exists():
        return None
    s = pd.read_csv(f)
    if not set(NONJON_TOP) <= set(s.root_id):
        return {"complete": False, "n": len(s)}
    n_jon_run = int(s.root_id.isin(ids.JON_ALL).sum())
    s = s[s.root_id != ids.ADN1]
    hits = s[s.aDN1_hz > 2]
    names = {ids.ABN1: "aBN1", ids.ADN2: "aDN2", DNGE220: "DNge220"}
    got = sorted(names.get(int(i), str(int(i))) for i in hits.root_id)
    weak = s[(s.aDN1_hz > 0) & (s.aDN1_hz <= 2)]
    return {"complete": True, "pass": set(hits.root_id) == {ids.ABN1, ids.ADN2},
            "drive_aDN1_gt2": got,
            "rates_gt2": {names.get(int(r.root_id), str(int(r.root_id))): float(r.aDN1_hz)
                          for r in hits.itertuples()},
            "n_weak_0_to_2": int(len(weak)),
            "weak_ids": [int(i) for i in weak.root_id], "n_JON_run": n_jon_run}


def test_E(v):
    f = vdir(v) / "necessity.csv"
    if not f.exists():
        return None
    s = pd.read_csv(f)
    if not (set(NONJON_TOP) | {0}) <= set(s.root_id):
        return {"complete": False, "n": len(s)}
    ctrl = s[s.root_id == 0].iloc[0]
    s = s[s.root_id != 0].copy()
    s["norm"] = s.aDN1_hz / ctrl.aDN1_hz if ctrl.aDN1_hz > 0 else np.nan
    s["norm2"] = s.aDN2_hz / ctrl.aDN2_hz if ctrl.aDN2_hz > 0 else np.nan
    jon = set(ids.JON_ALL)
    non = s[~s.root_id.isin(list(jon)) & (s.root_id != ids.ADN1)]
    hits = non[non.norm < 0.8]
    names = {ids.ABN1: "aBN1", ids.ADN2: "aDN2", DNGE220: "DNge220"}
    want = {ids.ABN1, ids.ADN2, DNGE220}
    got = set(int(i) for i in hits.root_id)
    ok = want <= got and len(got - want) <= 1
    jon_hits = s[s.root_id.isin(list(jon)) & (s.norm < 0.8)]
    return {"complete": True, "pass": bool(ok), "control_aDN1_hz": float(ctrl.aDN1_hz),
            "control_aDN2_hz": float(ctrl.aDN2_hz),
            "required_nonJON": {names.get(int(r.root_id), str(int(r.root_id))): round(float(r.norm), 3)
                                for r in hits.itertuples()},
            "n_JON_required": int(len(jon_hits)), "n_JON_run": int(s.root_id.isin(list(jon)).sum()),
            "aBN2_2026_in_top300": bool(set(TOP.root_id) & {720575940634683237, 720575940618961857,
                                                            720575940621355759})}


def test_F(v):
    f220 = rates_by_seed(v, "F_220")
    b1 = rates_by_seed(v, "aBN1_200")
    b2 = load_cond(v, "aBN2x3_200")
    dn = load_cond(v, "DNge220_200")
    if not (all_seeds(f220) and all_seeds(b1) and all_seeds(b2) and all_seeds(dn)):
        return None
    b2r = {k: key_rates(z) for k, z in b2.items()}
    dnr = {k: key_rates(z) for k, z in dn.items()}

    def abn2(r):
        return float(np.mean([r["aBN2_1"], r["aBN2_2"], r["aBN2_3"]]))

    out = {}
    # F1: JO-F -> aBN1, aBN2, aDN1 each >= 2 Hz (every seed)
    f1 = {n: all((abn2(r) if n == "aBN2" else r[n]) >= 2 for r in f220.values())
          for n in ("aBN1", "aBN2", "aDN1")}
    out["F1"] = {"right": all(f1.values()), "per_cell_right": f1,
                 "aBN1": mean_over(f220, "aBN1"), "aBN2_2026": float(np.mean([abn2(r) for r in f220.values()])),
                 "aDN1": mean_over(f220, "aDN1"), "aDN2": mean_over(f220, "aDN2"),
                 "DNge220": mean_over(f220, "DNge220")}
    # F2: aDN2 weak: below half of aDN1; can't tell if aDN1 < 2 Hz
    a1, a2 = mean_over(f220, "aDN1"), mean_over(f220, "aDN2")
    out["F2"] = {"verdict": "can't tell" if a1 < 2 else ("right" if a2 < 0.5 * a1 else "wrong"),
                 "aDN1": a1, "aDN2": a2}
    # F3: aBN1 alone -> aBN2 >= 2 Hz
    x = float(np.mean([abn2(r) for r in b1.values()]))
    out["F3"] = {"verdict": "right" if all(abn2(r) >= 2 for r in b1.values()) else "wrong",
                 "aBN2_2026": x, "DNge220": mean_over(b1, "DNge220")}
    # F4: aBN2 -> aBN1 (reported, not scored)
    out["F4"] = {"verdict": "not scored", "aBN1": mean_over(b2r, "aBN1")}
    # F5: aBN1 alone -> aDN1 or aDN2 >= 2 Hz
    out["F5"] = {"verdict": "right" if all(max(r["aDN1"], r["aDN2"]) >= 2 for r in b1.values()) else "wrong",
                 "aDN1": mean_over(b1, "aDN1"), "aDN2": mean_over(b1, "aDN2")}
    # F6: aBN2_1-3 together -> aDN1 >= 2 Hz
    out["F6"] = {"verdict": "right" if all(r["aDN1"] >= 2 for r in b2r.values()) else "wrong",
                 "aDN1": mean_over(b2r, "aDN1"), "stim_aBN2_rate": float(np.mean([abn2(r) for r in b2r.values()]))}
    # F7: aBN2_1-3 together -> aDN2 voltage below rest, no spikes
    vkey = f"v_mean_per_trial_{ids.ADN2}"
    vm = float(np.mean([z[vkey].mean() for z in b2.values()]))
    fires = mean_over(b2r, "aDN2")
    if vm <= REST_MV - 0.1 and fires == 0:
        verdict = "right"
    elif vm >= REST_MV + 0.1 or fires > 0:
        verdict = "wrong"
    else:
        verdict = "can't tell"
    out["F7"] = {"verdict": verdict, "aDN2_mean_v_mV": vm, "aDN2_hz": fires,
                 "aDN2_max_mean_trace_mV": float(np.max([z[f"v_mean_trace_{ids.ADN2}"].max() for z in b2.values()]))}
    # The same three tests with the paper's aBN2 (DNge220) instead
    vm_d = float(np.mean([z[vkey].mean() for z in dn.values()]))
    out["alt_DNge220"] = {"F1_JO-F_to_DNge220_hz": mean_over(f220, "DNge220"),
                          "F3_aBN1_to_DNge220_hz": mean_over(b1, "DNge220"),
                          "F6_DNge220_to_aDN1_hz": mean_over(dnr, "aDN1"),
                          "F7_DNge220_to_aDN2_mean_v_mV": vm_d,
                          "F7_DNge220_to_aDN2_hz": mean_over(dnr, "aDN2")}
    return out


def curves(v):
    out = {}
    for grp in ("CE", "F", "Fsil"):
        pts = {}
        for name in CONDITIONS:
            if name.startswith(grp + "_"):
                d = rates_by_seed(v, name)
                if d:
                    rate = int(name.split("_")[1])
                    vals = [r["aBN1"] for r in d.values()]
                    pts[rate] = (float(np.mean(vals)), float(np.std(vals)))
        out[grp] = dict(sorted(pts.items()))
    return out


def identity_vs_none(v):
    """For every condition+seed saved for both v and the published model: are the
    per-neuron spike counts exactly equal? (Same seed = same random input.)"""
    if v == "none":
        return None
    same, diff = [], []
    for f in sorted(vdir(v).glob("*.npz")):
        g = vdir("none") / f.name
        if not g.exists():
            continue
        a, b = np.load(f), np.load(g)
        eq = (np.array_equal(a["nz_idx"], b["nz_idx"]) and np.array_equal(a["nz_count"], b["nz_count"]))
        (same if eq else diff).append(f.stem)
    return {"n_identical": len(same), "n_different": len(diff), "different": diff}


FEED = RESULTS / "feeding"
ROBUST = RESULTS / "robustness.csv"
FEED_READ = "MN9_contra_hz"   # the paper's default MN9 (sim/shiu_model.py MN9_LEFT)


def _pair(d, base, test, right_if):
    """One pre-registered feeding pair (doc section 1.5), seeds matched by position.
    'right' if MN9 moves the real-fly way (right_if = 'up' / 'down') by more than 20%
    and more than 1 Hz in every seed, 'wrong' if it moves the other way by those
    amounts, otherwise "can't tell"."""
    b = d[d.condition == base].sort_values("seed")[FEED_READ].to_numpy()
    t = d[d.condition == test].sort_values("seed")[FEED_READ].to_numpy()
    if len(b) != len(SEEDS) or len(t) != len(SEEDS):
        return {"pair": f"{base} vs {test}", "verdict": "not run"}
    up = bool(np.all((t - b > 1.0) & (t > 1.2 * b)))
    down = bool(np.all((b - t > 1.0) & (t < 0.8 * b)))
    moved = "up" if up else ("down" if down else "neither")
    return {"pair": f"{base} vs {test}", "without": [round(float(x), 2) for x in b],
            "with": [round(float(x), 2) for x in t], "moved": moved,
            "verdict": "can't tell" if moved == "neither" else ("right" if moved == right_if else "wrong")}


def _combine(pairs):
    """Right if at least half of the pairs are right and none wrong; wrong the
    other way round; mixed if both occur; otherwise can't tell."""
    v = [p["verdict"] for p in pairs]
    if all(x == "not run" for x in v):
        return "not run"
    r, w = v.count("right"), v.count("wrong")
    if r and w:
        return "mixed"
    if 2 * r >= len(v):
        return "right"
    if 2 * w >= len(v):
        return "wrong"
    return "can't tell"


def _fires(d, cond, col):
    x = d[d.condition == cond].sort_values("seed")[col].to_numpy()
    return (len(x) == len(SEEDS) and bool(np.all(x >= 1.0))), [round(float(y), 2) for y in x]


def score_feeding(v):
    """Tests G1-G5 (doc section 1.5) for one variant, from results/feeding/<v>.csv."""
    f = FEED / f"{v.replace('+', '__')}.csv"
    if not f.exists():
        return None
    d = pd.read_csv(f).drop_duplicates(["condition", "seed"], keep="last")
    out = {"mean_MN9_hz": {c: round(float(g[FEED_READ].mean()), 2) for c, g in d.groupby("condition")},
           "mean_OA_VPM4_hz": {c: round(float(g.OA_VPM4_mean_hz.mean()), 2) for c, g in d.groupby("condition")},
           "mean_ISN_hz": {c: round(float(g.ISN_mean_hz.mean()), 2) for c, g in d.groupby("condition")}}
    g1 = [_pair(d, f"sug{s}", f"sug{s}+OA{r}", "up") for s in (40, 50) for r in (50, 100)]
    g3 = [_pair(d, f"sug{s}", f"sug{s}+ISN{r}", "up") for s in (40, 50) for r in (50, 100)]
    g4 = [_pair(d, "wat160", f"wat160+ISN{r}", "down") for r in (50, 100)]
    out["G1"] = {"verdict": _combine(g1), "pairs": g1}
    out["G3"] = {"verdict": _combine(g3), "pairs": g3}
    out["G4"] = {"verdict": _combine(g4), "pairs": g4}
    # G2 / G5: only testable if the cells fire during taste input
    def _silence_pair(base, test, want, col, lab):
        ok, x = _fires(d, base, col)
        if ok or len(x) < len(SEEDS):   # fires, or not run yet (then _pair says "not run")
            return _pair(d, base, test, want)
        return {"pair": f"{base} vs {test}", "verdict": "can't tell",
                "why": f"{lab}: the cells fire {x} Hz (needs >= 1 Hz in every seed)"}

    p2 = [_silence_pair("sug50", "sug50_silOA", "down", "OA_VPM4_mean_hz", "OA-VPM4 during sugar 50 Hz")]
    out["G2"] = {"verdict": _combine(p2), "pairs": p2}
    p5 = [_silence_pair("sug50", "sug50_silISN", "down", "ISN_mean_hz", "ISNs during sugar 50 Hz"),
          _silence_pair("wat160", "wat160_silISN", "up", "ISN_mean_hz", "ISNs during water 160 Hz")]
    out["G5"] = {"verdict": _combine(p5), "pairs": p5}
    out["complete"] = all(p["verdict"] != "not run" for p in g1 + g3 + g4 + p2 + p5)
    return out


def score_robustness():
    """Phase 6 checks on F1 / F7 (and Test C) in the published model: results/robustness.csv."""
    if not ROBUST.exists():
        return None
    d = pd.read_csv(ROBUST).drop_duplicates(["variation", "condition", "seed"], keep="last")
    out = {}
    for (var, c), g in d.groupby(["variation", "condition"], sort=False):
        abn2 = g[["aBN2_1_hz", "aBN2_2_hz", "aBN2_3_hz"]].mean(axis=1)
        row = {"n_seeds": int(len(g)), "aBN1": float(g.aBN1_hz.mean()), "aDN1": float(g.aDN1_hz.mean()),
               "aDN2": float(g.aDN2_hz.mean()), "DNge220": float(g.DNge220_hz.mean()),
               "aBN2_2026": float(abn2.mean())}
        if c == "F_220":   # F1: JO-F -> aBN1, aBN2, aDN1 each >= 2 Hz in every seed
            row["F1"] = "right" if (bool((abn2 >= 2).all()) and bool((g.aBN1_hz >= 2).all())
                                    and bool((g.aDN1_hz >= 2).all())) else "wrong"
        if c == "ALL_220":  # Test C at 220 Hz
            row["C"] = "holds" if all(bool((g[f"{n}_hz"] >= 5).all()) for n in ("aBN1", "aDN1", "aDN2")) else "breaks"
        if c.startswith("aBN2"):  # F7 and F6
            vm, fires = float(g.aDN2_mean_v_mV.mean()), float(g.aDN2_hz.mean())
            row["aDN2_mean_v_mV"] = vm
            row["F7"] = ("right" if (vm <= REST_MV - 0.1 and fires == 0) else
                         "wrong" if (vm >= REST_MV + 0.1 or fires > 0) else "can't tell")
            row["F6"] = "right" if bool((g.aDN1_hz >= 2).all()) else "wrong"
        out[f"{var} | {c}"] = row
    return out


def verdict(test, base, key_names):
    """holds / changes / breaks versus the published model ('none')."""
    if test is None:
        return "not run"
    if not test.get("pass", False):
        return "breaks"
    if base is None:
        return "holds"
    for k in key_names:
        a, b = test.get(k), base.get(k)
        if a is None or b is None:
            continue
        if b == 0 and a == 0:
            continue
        if abs(a - b) > 0.2 * max(abs(b), 1.0):
            return "changes"
    return "holds"


def main():
    comp = pd.read_csv(HERE.parents[1] / "data" / "reference" / "2023_03_23_completeness_630_final.csv",
                       index_col=0)
    root_ids = comp.index.to_numpy()
    summary = {}
    for v in VARIANTS:
        if not vdir(v).exists():
            continue
        summary[v] = {"A": test_A(v), "B": test_B(v), "C": test_C(v, root_ids), "D": test_D(v),
                      "E": test_E(v), "F": test_F(v), "curves": curves(v),
                      "identity_vs_none": identity_vs_none(v), "G": score_feeding(v)}
    base = summary.get("none", {})
    for v, s in summary.items():
        s["verdicts"] = {
            "A": verdict(s["A"], base.get("A") if v != "none" else None,
                         ["aBN1_CE_100", "aBN1_CE_220"]),
            "B": verdict(s["B"], base.get("B") if v != "none" else None,
                         ["aBN1_Fsil_100", "aBN1_Fsil_220"]),
            "C": verdict(s["C"], base.get("C") if v != "none" else None,
                         ["aBN1_220", "aDN1_220", "aDN2_220", "aDN1_140"]),
            "D": "not run" if not s["D"] or not s["D"].get("complete") else ("holds" if s["D"]["pass"] else "breaks"),
            "E": "not run" if not s["E"] or not s["E"].get("complete") else ("holds" if s["E"]["pass"] else "breaks"),
        }
    rob = score_robustness()
    (RESULTS / "summary.json").write_text(json.dumps({"variants": summary, "robustness": rob}, indent=1,
                                                     default=float), encoding="utf-8")
    write_md(summary, rob)
    plot(summary)


def write_md(S, rob=None):
    L = ["# Held-out grooming tests: summary (generated by analyze_heldout.py)", ""]
    L += ["## Verdicts", "", "| variant | A: JO-CE vs JO-F -> aBN1 | B: silence 3 -> aBN1 | C: all JONs | D: sufficiency | E: necessity |",
          "|---|---|---|---|---|---|"]
    for v, s in S.items():
        vv = s["verdicts"]
        L.append(f"| {v} | {vv['A']} | {vv['B']} | {vv['C']} | {vv['D']} | {vv['E']} |")
    P = PUB
    L += ["", "## Test A/B: aBN1 (Hz, mean of seeds)", "",
          "| variant | CE 100 | CE 220 | F 100 | F 220 | F+silence 100 | F+silence 220 |",
          "|---|---|---|---|---|---|---|",
          f"| paper (published model) | {P['aBN1_JO_CE']['100']:.1f} | {P['aBN1_JO_CE']['220']:.1f} | "
          f"{P['aBN1_JO_F']['100']:.1f} | {P['aBN1_JO_F']['220']:.1f} | {P['aBN1_JO_F_3silenced']['100']:.1f} | "
          f"{P['aBN1_JO_F_3silenced']['220']:.1f} |"]
    for v, s in S.items():
        a, b = s["A"] or {}, s["B"] or {}
        L.append(f"| {v} | {fmt(a.get('aBN1_CE_100'))} | {fmt(a.get('aBN1_CE_220'))} | {fmt(a.get('aBN1_F_100'))} | "
                 f"{fmt(a.get('aBN1_F_220'))} | {fmt(b.get('aBN1_Fsil_100'))} | {fmt(b.get('aBN1_Fsil_220'))} |")
    L += ["", "## Test C: all 146 JONs (Hz, mean of seeds)", "",
          "| variant | aBN1 140 / 220 | aDN1 140 / 220 | aDN2 140 / 220 | DNge220 220 | aBN2_1-3 220 | non-JON fired at 220 (ours / paper) | r with paper at 220 (log r) |",
          "|---|---|---|---|---|---|---|---|"]
    n = P["all_JON_named"]
    L.append(f"| paper | {n['aBN1']['140']:.1f} / {n['aBN1']['220']:.1f} | {n['aDN1']['140']:.1f} / {n['aDN1']['220']:.1f} | "
             f"{n['aDN2']['140']:.1f} / {n['aDN2']['220']:.1f} | {n['aBN2 (Descending BN2_3)']['220']:.1f} | 0 | "
             f"{P['all_JON_n_non_JON_fired_at_220']} | - |")
    for v, s in S.items():
        c = s["C"]
        if not c:
            continue
        sim = c.get("similarity_220") or {}
        L.append(f"| {v} | {fmt(c['aBN1_140'])} / {fmt(c['aBN1_220'])} | {fmt(c['aDN1_140'])} / {fmt(c['aDN1_220'])} | "
                 f"{fmt(c['aDN2_140'])} / {fmt(c['aDN2_220'])} | {fmt(c['DNge220_220'])} | {fmt(c['aBN2_2026_220'], 2)} | "
                 f"{fmt(sim.get('n_nonJON_fired_ours'))} / {sim.get('n_nonJON_fired_paper', '-')} | "
                 f"{fmt(sim.get('pearson_r'), 3)} ({fmt(sim.get('pearson_r_log'), 3)}) |")
    L += ["", "## Exact identity with the published model (same seed, same spike counts)", ""]
    for v, s in S.items():
        if s.get("identity_vs_none"):
            L.append(f"- **{v}**: {json.dumps(s['identity_vs_none'])}")
    L += ["", "## Tests D and E", ""]
    for v, s in S.items():
        L.append(f"- **{v}**: D = {json.dumps(s['D'], default=float)}; E = {json.dumps(s['E'], default=float)}")
    L += ["", "## Test F (Hampel et al. 2015, not scored by Shiu et al.)", ""]
    for v, s in S.items():
        L.append(f"- **{v}**: {json.dumps(s['F'], default=float)}")
    L += ["", "## Held-out feeding tests G1-G5 (doc section 1.5)", "",
          "| variant | G1 OA-VPM4 up | G2 OA-VPM4 silenced | G3 ISN up on sugar | G4 ISN down on water | G5 ISN silenced | complete |",
          "|---|---|---|---|---|---|---|"]
    for v, s in S.items():
        g = s.get("G")
        if g:
            L.append(f"| {v} | {g['G1']['verdict']} | {g['G2']['verdict']} | {g['G3']['verdict']} | "
                     f"{g['G4']['verdict']} | {g['G5']['verdict']} | {g['complete']} |")
    for v, s in S.items():
        g = s.get("G")
        if g:
            L += ["", f"**{v}** mean MN9 (Hz) per condition: {json.dumps(g['mean_MN9_hz'])}",
                  f"OA-VPM4 (Hz): {json.dumps(g['mean_OA_VPM4_hz'])}", f"ISN (Hz): {json.dumps(g['mean_ISN_hz'])}"]
            for t in ("G1", "G2", "G3", "G4", "G5"):
                L.append(f"- {t}: " + "; ".join(
                    f"{p['pair']}: {p['verdict']}" + (f" ({p['without']} -> {p['with']})" if "with" in p else "")
                    + (f" [{p['why']}]" if "why" in p else "") for p in g[t]["pairs"]))
    if rob:
        L += ["", "## Robustness of F1 / F7 / C in the published model (Phase 6 checks)", "",
              "| variation | condition | seeds | aBN1 | aDN1 | aDN2 | aBN2_1-3 mean | DNge220 | aDN2 mean V (mV) | verdicts |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for k, r in rob.items():
            var, c = k.split(" | ")
            vd = ", ".join(f"{t} {r[t]}" for t in ("F1", "C", "F6", "F7") if t in r)
            L.append(f"| {var} | {c} | {r['n_seeds']} | {fmt(r['aBN1'])} | {fmt(r['aDN1'])} | {fmt(r['aDN2'])} | "
                     f"{fmt(r['aBN2_2026'], 2)} | {fmt(r['DNge220'])} | {fmt(r.get('aDN2_mean_v_mV'), 2)} | {vd} |")
    (RESULTS / "summary.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def plot(S):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    PLOTS.mkdir(exist_ok=True)
    fig, axes = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    pub = {"CE": PUB["aBN1_JO_CE"], "F": PUB["aBN1_JO_F"], "Fsil": PUB["aBN1_JO_F_3silenced"]}
    titles = {"CE": "JO-CE (70) -> aBN1", "F": "JO-F (60) -> aBN1", "Fsil": "JO-F + 3 GABA cells silenced -> aBN1"}
    for ax, grp in zip(axes, ("CE", "F", "Fsil")):
        pr = sorted((int(k), v) for k, v in pub[grp].items())
        ax.plot([p[0] for p in pr], [p[1] for p in pr], "k-", lw=2, label="paper's published model")
        for j, (v, s) in enumerate(S.items()):
            c = s["curves"].get(grp, {})
            if c:
                xs = sorted(c)
                # markers only (rates are sparse); small x offset so identical
                # variants stay visible side by side
                ax.errorbar([x + 3 * (j - 1) for x in xs], [c[x][0] for x in xs],
                            yerr=[c[x][1] for x in xs], marker="o", ms=4, ls="none",
                            capsize=2, label=v)
        ax.set_title(titles[grp], fontsize=10)
        ax.set_xlabel("JON stimulation rate (Hz)")
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("aBN1 firing (Hz; mean of 3 seeds, bar = seed sd)")
    axes[0].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(PLOTS / "abn1_curves.png", dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()

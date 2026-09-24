"""Analysis of the same-side release closed-loop trials (run_sameside.py).

Same measures and tests as experiments/phase9_da1/analyze_da1.py (its
functions are imported): turn in the first second signed toward the source
(arena A, the 12 trials with the source left or right) or toward the smelling
antenna's side (arena B); closest approach; Mann-Whitney U (two-sided) against
each control; sign tests; paired Wilcoxon against the same-seed control.

Condition names here: old_* = experiments/phase9_da1 (switch off), rel_* =
arm 1 (release switch on), map_* = arm 2 (DIAGNOSTIC). A control that was not
re-run with the switch on is taken from phase9_da1 (it gets the straight drive
in every window whatever the brain) and listed in ctrl_source.csv as reused;
every re-run control is compared with its old twin (control_vs_old.csv).

Outputs (results/): ss_condition_table.csv, ss_stats.csv, ss_sign_tests.csv,
ss_paired_tests.csv, ss_brain_vs_brain.csv, control_vs_old.csv,
ctrl_source.csv, ss_window_offsets.csv; plots/trajectories_A.png,
plots/trajectories_B.png, plots/turn_first_second.png.
Run: .venv\\Scripts\\python.exe experiments/phase9_sameside/analyze_sameside.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "phase9_da1"))
import analyze_da1 as A  # noqa: E402

RES, PLOTS = HERE / "results", HERE / "plots"
OLD = ROOT / "experiments" / "phase9_da1" / "results"
CTRL_A = ["orns_off", "dna02_off", "no_odor"]
CTRL_B = ["one_orns_off", "one_dna02_off"]
LABEL = {"old_dna02": "switch OFF (phase9_da1), DNa02 steers",
         "rel_dna02": "ARM 1: release switch ON, DNa02 steers",
         "map_dna02": "ARM 2 (diagnostic): un-lopsided map, DNa02",
         "old_dnpe002": "switch OFF (phase9_da1), DNpe002 steers (sign assumed)",
         "rel_dnpe002": "ARM 1, DNpe002 steers (sign assumed)",
         "old_one_dna02": "switch OFF (phase9_da1), one antenna, DNa02",
         "rel_one_dna02": "ARM 1, one antenna, DNa02",
         "map_one_dna02": "ARM 2 (diagnostic), one antenna, DNa02",
         "map_one_dna02_dm1": "ARM 2 (diagnostic), one antenna, DM1 (vinegar), DNa02",
         "ctl_orns_off": "control: DA1 smell neurons silenced",
         "ctl_dna02_off": "control: DNa02 silenced",
         "ctl_no_odor": "control: no odor",
         "ctl_one_orns_off": "control: DA1 smell neurons silenced",
         "ctl_one_dna02_off": "control: DNa02 silenced"}


def load():
    tr = pd.read_csv(RES / "ss_trials.csv")
    win = pd.read_csv(RES / "ss_windows.csv")
    otr = pd.read_csv(OLD / "da1_trials.csv")
    owin = pd.read_csv(OLD / "da1_windows.csv")
    pre = {"release": "rel_", "map": "map_"}
    tr["condition"] = tr.variant.map(pre) + tr.condition
    win["condition"] = win.variant.map(pre) + win.condition
    keep = ["dna02", "one_dna02", "dnpe002"]
    o_b = otr[otr.condition.isin(keep)].assign(variant="off")
    o_bw = owin[owin.condition.isin(keep)].assign(variant="off")
    o_b["condition"] = "old_" + o_b.condition
    o_bw["condition"] = "old_" + o_bw.condition
    # controls: re-run (switch on) where available, else reused from phase9_da1
    ctl, ctlw, src = [], [], []
    for c in CTRL_A + CTRL_B:
        new = tr[tr.condition == "rel_" + c]
        old = otr[otr.condition == c]
        have = set(zip(new.layout, new.rep))
        reused = old[[(l, r) not in have for l, r in zip(old.layout, old.rep)]]
        ctl.append(pd.concat([new, reused.assign(variant="off")]).assign(condition="ctl_" + c))
        nw = win[win.condition == "rel_" + c]
        ow = owin[owin.condition == c]
        ow = ow[[(l, r) not in have for l, r in zip(ow.layout, ow.rep)]]
        ctlw.append(pd.concat([nw, ow.assign(variant="off")]).assign(condition="ctl_" + c))
        src.append({"control": c, "rerun_with_switch_on": len(new), "reused_from_phase9_da1": len(reused)})
    t = pd.concat([o_b, tr[~tr.condition.str.replace("rel_", "").isin(CTRL_A + CTRL_B)
                           | tr.condition.str.startswith("map_")]] + ctl, ignore_index=True)
    w = pd.concat([o_bw, win[~win.condition.str.replace("rel_", "").isin(CTRL_A + CTRL_B)
                             | win.condition.str.startswith("map_")]] + ctlw, ignore_index=True)
    return t, w, pd.DataFrame(src), tr, win, otr, owin


def control_vs_old(tr, win, owin):
    """Each re-run control (switch on) against the phase9_da1 trial with the
    same control, layout and replicate: largest path / heading difference."""
    out = []
    for c in CTRL_A + CTRL_B:
        for (lay, rep), g in win[win.condition == "rel_" + c].groupby(["layout", "rep"]):
            o = owin[(owin.condition == c) & (owin.layout == lay) & (owin.rep == rep)].set_index("window")
            g = g.set_index("window")
            j = g.index.intersection(o.index)
            if not len(j):
                continue
            out.append({"control": c, "layout": lay, "rep": rep, "windows": len(j),
                        "max_path_diff_mm": float(np.hypot(g.x_mm[j] - o.x_mm[j], g.y_mm[j] - o.y_mm[j]).max()),
                        "max_heading_diff_deg": float(np.degrees(np.abs(g.heading_rad[j] - o.heading_rad[j])).max()),
                        "all_drive_straight": bool(((g.drive_L == 1) & (g.drive_R == 1)).all())})
    return pd.DataFrame(out)


def paired(t):
    rows = []
    for arena, brains, ctrl, m in (("A", ["old_dna02", "rel_dna02", "map_dna02", "rel_dnpe002"],
                                    "ctl_orns_off", "turn_toward_source_1s_deg"),
                                   ("B", ["old_one_dna02", "rel_one_dna02", "map_one_dna02", "map_one_dna02_dm1"],
                                    "ctl_one_orns_off", "turn_toward_intact_1s_deg")):
        c = t[t.condition == ctrl].set_index(["layout", "rep"])[m]
        for b in brains:
            d = [r[m] - c[(r.layout, r.rep)] for _, r in t[t.condition == b].iterrows()
                 if (r.layout, r.rep) in c.index and np.isfinite(r[m])]
            if len(d) >= 3:
                d = np.array(d)
                rows.append({"arena": arena, "condition": b, "control": ctrl, "metric": m,
                             "n_pairs": len(d), "mean_diff": d.mean(), "n_positive": int((d > 0).sum()),
                             "wilcoxon_p": stats.wilcoxon(d).pvalue if np.any(d != 0) else 1.0})
    return pd.DataFrame(rows)


def brain_vs_brain(t):
    """Did the switch change the brain-driven fly? Mann-Whitney between variants."""
    rows = []
    for m, sub in (("turn_toward_source_1s_deg", lambda g: g[g.source_angle_deg != 0]),
                   ("heading_change_1s_deg", lambda g: g), ("min_dist_mm", lambda g: g)):
        for a, b in (("rel_dna02", "old_dna02"), ("map_dna02", "old_dna02"), ("map_dna02", "rel_dna02"),
                     ("rel_dnpe002", "old_dnpe002")):
            xa, xb = sub(t[t.condition == a])[m].dropna(), sub(t[t.condition == b])[m].dropna()
            if len(xa) >= 3 and len(xb) >= 3:
                rows.append({"metric": m, "condition": a, "vs": b, "mean": xa.mean(), "mean_vs": xb.mean(),
                             "mannwhitney_p": stats.mannwhitneyu(xa, xb, alternative="two-sided").pvalue})
    for a, b in (("rel_one_dna02", "old_one_dna02"), ("map_one_dna02", "old_one_dna02")):
        for side in ("left_only", "right_only"):
            xa = t[(t.condition == a) & (t.antennae == side)].turn_toward_intact_1s_deg.dropna()
            xb = t[(t.condition == b) & (t.antennae == side)].turn_toward_intact_1s_deg.dropna()
            if len(xa) >= 3 and len(xb) >= 3:
                rows.append({"metric": f"turn_toward_intact_1s_deg ({side})", "condition": a, "vs": b,
                             "mean": xa.mean(), "mean_vs": xb.mean(),
                             "mannwhitney_p": stats.mannwhitneyu(xa, xb, alternative="two-sided").pvalue})
    return pd.DataFrame(rows)


def window_offsets(w):
    """Mean DNa02 left / right per condition and source side (arena A brain flies)."""
    out = []
    for c in ("old_dna02", "rel_dna02", "map_dna02"):
        g = w[w.condition == c]
        for lay, h in g.groupby("layout"):
            out.append({"condition": c, "layout": lay, "windows": len(h),
                        "orn_L_minus_R_hz": (h.orn_rate_L - h.orn_rate_R).mean(),
                        "DNa02_L_hz": h.DNa02_L_hz.mean(), "DNa02_R_hz": h.DNa02_R_hz.mean(),
                        "DNae007_L_hz": h.get("DNae007_L_hz", pd.Series(dtype=float)).mean(),
                        "DNae007_R_hz": h.get("DNae007_R_hz", pd.Series(dtype=float)).mean(),
                        "frac_windows_turn_left": float((h.turn > 0.05).mean()),
                        "frac_windows_turn_right": float((h.turn < -0.05).mean())})
    return pd.DataFrame(out)


def main():
    PLOTS.mkdir(exist_ok=True)
    matplotlib.rcParams["savefig.bbox"] = "tight"  # the longer labels here would be clipped

    t, w, src, tr, win, otr, owin = load()
    src.to_csv(RES / "ctrl_source.csv", index=False)
    control_vs_old(tr, win, owin).to_csv(RES / "control_vs_old.csv", index=False, float_format="%.4f")
    have = set(t.condition)
    A.A_BRAIN = [c for c in ["old_dna02", "rel_dna02", "map_dna02", "old_dnpe002", "rel_dnpe002"]
                 if c in have and (c != "old_dnpe002" or "rel_dnpe002" in have)]
    A.A_CTRL = ["ctl_" + c for c in CTRL_A]
    A.B_BRAIN = [c for c in ["old_one_dna02", "rel_one_dna02", "map_one_dna02", "map_one_dna02_dm1"] if c in set(t.condition)]
    A.B_CTRL = ["ctl_" + c for c in CTRL_B]
    A.LABEL = LABEL
    order = A.A_BRAIN + A.A_CTRL + A.B_BRAIN + A.B_CTRL
    t = t[t.condition.isin(order)]
    t["condition"] = pd.Categorical(t.condition, order, ordered=True)
    t = t.sort_values(["condition", "rep", "layout"])
    t["condition"] = t.condition.astype(str)
    A.condition_table(t).to_csv(RES / "ss_condition_table.csv", index=False, float_format="%.3f")
    st, sign = A.tests(t)
    st.to_csv(RES / "ss_stats.csv", index=False, float_format="%.5g")
    sign.to_csv(RES / "ss_sign_tests.csv", index=False, float_format="%.5g")
    paired(t).to_csv(RES / "ss_paired_tests.csv", index=False, float_format="%.5g")
    brain_vs_brain(t).to_csv(RES / "ss_brain_vs_brain.csv", index=False, float_format="%.5g")
    window_offsets(w).to_csv(RES / "ss_window_offsets.csv", index=False, float_format="%.3f")
    lay_a = [l for l, _, _ in A_LAYOUTS]
    lay_b = [l for l, _, _ in B_LAYOUTS]
    A.traj_plot(w, t, A.A_BRAIN + ["ctl_orns_off"], lay_a, PLOTS / "trajectories_A.png",
                "Normal fly (both antennae smell cVA 6 mm away): switch off vs on")
    A.traj_plot(w, t, A.B_BRAIN + ["ctl_one_orns_off"], lay_b, PLOTS / "trajectories_B.png",
                "One-antenna fly: switch off vs on")
    A.strip_plot(t, PLOTS / "turn_first_second.png")
    print(A.condition_table(t)[["condition", "n_trials", "reached", "mean_min_dist_mm",
                                "frac_trials_turn_left_1s"]].to_string(index=False))
    print(st.to_string(index=False))
    print(sign.to_string(index=False))


sys.path.insert(0, str(ROOT))
A_LAYOUTS = [("A+90", "both", 90.0), ("A+45", "both", 45.0), ("A0", "both", 0.0),
             ("A-45", "both", -45.0), ("A-90", "both", -90.0)]
B_LAYOUTS = [("B_Lonly+90", "left_only", 90.0), ("B_Lonly-90", "left_only", -90.0),
             ("B_Ronly+90", "right_only", 90.0), ("B_Ronly-90", "right_only", -90.0)]

if __name__ == "__main__":
    main()

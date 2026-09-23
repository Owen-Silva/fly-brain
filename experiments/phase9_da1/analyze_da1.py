"""Analyse the DA1 (cVA) closed-loop trials (run_da1.py) -> tables, tests, plots.

Metrics (per trial), chosen so a circling fly cannot look good by staying
near its start (docs/phase9-body-loop.md 4.2):
  turn_toward_source_1s_deg  heading change in the first second, signed so
                             + = toward the source's side (source left or
                             right only; not defined for the source ahead)
  turn_toward_intact_1s_deg  same, + = toward the side of the antenna that
                             can smell (one-antenna fly, arena B)
  min_dist_mm                closest approach to the source
  reached / time_to_reach_s  within 2 mm of the source, and when
  heading_change_1s_deg      + = turned LEFT (to spot a fixed left bias)
Tests: Mann-Whitney U (two-sided) brain condition vs each control; a sign
(binomial) test of "turned toward in more trials than 50%".

Outputs (results/): da1_condition_table.csv, da1_stats.csv (Mann-Whitney),
da1_sign_tests.csv, da1_window_toward.csv (turn command per 50 ms window),
da1_drive_check.csv (did the controls ever get a non-straight drive?),
da1_control_identity.csv (are the control paths identical per seed?),
da1_paired_trials.csv / da1_paired_tests.csv (brain minus the no-input
control with the same layout and seed; Wilcoxon signed-rank);
plots/: trajectories_A.png, trajectories_B.png, turn_first_second.png.
Run (either venv): python experiments/phase9_da1/analyze_da1.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from scipy import stats  # noqa: E402

HERE = Path(__file__).resolve().parent
RES, PLOTS = HERE / "results", HERE / "plots"
REACH_MM = 2.0
A_BRAIN = ["dna02", "dnpe002", "published_dna02", "hand_rule"]
A_CTRL = ["no_odor", "orns_off", "dna02_off", "dnpe002_off"]
B_BRAIN = ["one_dna02", "one_dnpe002"]
B_CTRL = ["one_orns_off", "one_dna02_off", "one_dnpe002_off"]
LABEL = {
    "dna02": "brain, DNa02 steers", "dnpe002": "brain, DNpe002 steers (sign assumed)",
    "no_odor": "no odor", "orns_off": "DA1 smell neurons silenced",
    "dna02_off": "DNa02 silenced", "dnpe002_off": "DNpe002 silenced",
    "hand_rule": "hand-written rule (NOT brain-driven)",
    "published_dna02": "published model, DNa02 steers",
    "one_dna02": "1 antenna, DNa02 steers", "one_dnpe002": "1 antenna, DNpe002 steers",
    "one_orns_off": "1 antenna, DA1 silenced", "one_dna02_off": "1 antenna, DNa02 silenced",
    "one_dnpe002_off": "1 antenna, DNpe002 silenced",
}
# Categorical slots 1-5 (dataviz reference palette, light; validated: all pass,
# contrast WARN -> legend + tables carry identity too).
COL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
LAYOUT_NAME = {"A+90": "source left (+90°)", "A+45": "source +45°", "A0": "source ahead",
               "A-45": "source -45°", "A-90": "source right (-90°)",
               "B_Lonly+90": "left antenna, source left",
               "B_Lonly-90": "left antenna, source right",
               "B_Ronly+90": "right antenna, source left",
               "B_Ronly-90": "right antenna, source right"}
INK, MUTED, GRID = "#1a1a19", "#6b6a64", "#e4e3dc"


def condition_table(tr):
    out = []
    for c, g in tr.groupby("condition", sort=False):
        lat = g[g.source_angle_deg != 0]
        s = {"condition": c, "n_trials": len(g), "reps": ",".join(map(str, sorted(g.rep.unique()))),
             "reached": f"{int(g.reached.sum())}/{len(g)}",
             "mean_min_dist_mm": g.min_dist_mm.mean(),
             "median_time_to_reach_s": g.time_to_reach_s.median(),
             "mean_turn_left_1s_deg": g.heading_change_1s_deg.mean(),
             "frac_trials_turn_left_1s": (g.heading_change_1s_deg > 0).mean()}
        if g.antennae.iloc[0] == "both":
            s["mean_turn_toward_source_1s_deg"] = lat.turn_toward_source_1s_deg.mean()
            s["frac_lateral_trials_toward"] = (lat.turn_toward_source_1s_deg > 0).mean()
        else:
            s["mean_turn_toward_intact_1s_deg"] = g.turn_toward_intact_1s_deg.mean()
            s["frac_trials_toward_intact"] = (g.turn_toward_intact_1s_deg > 0).mean()
            near = g[np.sign(g.source_angle_deg) == g.antennae.map({"left_only": 1, "right_only": -1})]
            s["mean_min_dist_source_on_smelling_side_mm"] = near.min_dist_mm.mean()
            s["reached_source_on_smelling_side"] = f"{int(near.reached.sum())}/{len(near)}"
        for col in ("mean_DNa02_L_hz", "mean_DNa02_R_hz", "mean_DNpe002_L_hz",
                    "mean_DNpe002_R_hz", "mean_orn_rate_L", "mean_orn_rate_R", "mean_turn_cmd"):
            s[col] = g[col].mean()
        out.append(s)
    return pd.DataFrame(out)


def tests(tr):
    rows = []

    def add(arena, metric, a, b, sub_a, sub_b):
        xa, xb = sub_a[metric].dropna().to_numpy(), sub_b[metric].dropna().to_numpy()
        if len(xa) < 3 or len(xb) < 3:
            return
        u = stats.mannwhitneyu(xa, xb, alternative="two-sided")
        rows.append({"arena": arena, "metric": metric, "condition": a, "vs": b,
                     "n": len(xa), "n_vs": len(xb), "mean": xa.mean(), "mean_vs": xb.mean(),
                     "mannwhitney_p": u.pvalue})

    for arena, brains, ctrls, metric in (
            ("A", A_BRAIN, A_CTRL, "turn_toward_source_1s_deg"),
            ("A", A_BRAIN, A_CTRL, "min_dist_mm"),
            ("B", B_BRAIN, B_CTRL, "turn_toward_intact_1s_deg"),
            ("B", B_BRAIN, B_CTRL, "min_dist_mm")):
        for a in brains:
            for b in ctrls:
                sa, sb = tr[tr.condition == a], tr[tr.condition == b]
                if metric == "turn_toward_source_1s_deg":
                    sa, sb = sa[sa.source_angle_deg != 0], sb[sb.source_angle_deg != 0]
                if arena == "B" and metric == "min_dist_mm":   # source on the smelling side
                    side = {"left_only": 1, "right_only": -1}
                    sa = sa[np.sign(sa.source_angle_deg) == sa.antennae.map(side)]
                    sb = sb[np.sign(sb.source_angle_deg) == sb.antennae.map(side)]
                add(arena, metric, a, b, sa, sb)
    st = pd.DataFrame(rows)
    sign = []
    for c, g in tr.groupby("condition", sort=False):
        m = "turn_toward_source_1s_deg" if g.antennae.iloc[0] == "both" else "turn_toward_intact_1s_deg"
        x = g[m].dropna()
        x = x[x != 0]
        if len(x):
            k = int((x > 0).sum())
            sign.append({"arena": "A" if m.endswith("source_1s_deg") else "B", "metric": m,
                         "condition": c, "n": len(x), "n_toward": k,
                         "sign_test_p": stats.binomtest(k, len(x), 0.5).pvalue})
        if g.antennae.iloc[0] == "both":          # a fixed LEFT bias, whatever the source side
            x = g.heading_change_1s_deg[g.heading_change_1s_deg != 0]
            k = int((x > 0).sum())
            sign.append({"arena": "A", "metric": "turned_left_1s", "condition": c, "n": len(x),
                         "n_toward": k, "sign_test_p": stats.binomtest(k, len(x), 0.5).pvalue})
    return st, pd.DataFrame(sign)


def window_toward(win, tr):
    """Fraction of 50 ms windows whose turn command points to the source's
    side (arena A, lateral) or to the smelling antenna (arena B)."""
    m = win.merge(tr[["condition", "layout", "rep", "source_angle_deg", "antennae"]],
                  on=["condition", "layout", "rep"])
    out = []
    for c, g in m.groupby("condition", sort=False):
        if g.antennae.iloc[0] == "both":
            g = g[g.source_angle_deg != 0]
            want = np.sign(g.source_angle_deg)
        else:
            want = g.antennae.map({"left_only": 1.0, "right_only": -1.0})
        cmd = np.sign(np.where(np.abs(g.turn) > 0.05, g.turn, 0.0))
        out.append({"condition": c, "n_windows": len(g),
                    "frac_cmd_toward": float((cmd == want).mean()),
                    "frac_cmd_away": float((cmd == -want).mean()),
                    "frac_cmd_straight": float((cmd == 0).mean())})
    return pd.DataFrame(out)


def drive_check(win):
    """Per condition, over ALL windows: how often the body got anything other
    than the straight drive [1, 1], and the largest turn command. For the
    silenced / no-odor controls this should be never / 0."""
    out = []
    for c, g in win.groupby("condition", sort=False):
        straight = np.isclose(g.drive_L, 1.0) & np.isclose(g.drive_R, 1.0)
        out.append({"condition": c, "n_windows": len(g),
                    "frac_windows_not_straight": float((~straight).mean()),
                    "max_abs_turn_cmd": float(np.abs(g.turn).max()),
                    "mean_DNa02_L_hz": float(g.DNa02_L_hz.mean()),
                    "mean_DNa02_R_hz": float(g.DNa02_R_hz.mean()),
                    "mean_DNpe002_L_hz": float(g.DNpe002_L_hz.mean()),
                    "mean_DNpe002_R_hz": float(g.DNpe002_R_hz.mean())})
    return pd.DataFrame(out)


def control_identity(win):
    """The silenced / no-odor controls always get drive [1, 1], so for one
    walking-rhythm seed their paths should be the same whatever the control
    or the source position. Largest difference (mm, deg) from the first
    control trial of that replicate, over the windows both have."""
    ctrl = win[win.condition.isin(A_CTRL + B_CTRL)]
    out = []
    for rep, g in ctrl.groupby("rep"):
        keys = list(g.groupby(["condition", "layout"]).groups)
        ref = g[(g.condition == keys[0][0]) & (g.layout == keys[0][1])].set_index("window")
        dxy = dh = 0.0
        for c, lay in keys[1:]:
            o = g[(g.condition == c) & (g.layout == lay)].set_index("window")
            j = ref.index.intersection(o.index)
            dxy = max(dxy, float(np.hypot(ref.x_mm[j] - o.x_mm[j], ref.y_mm[j] - o.y_mm[j]).max()))
            dh = max(dh, float(np.degrees(np.abs(ref.heading_rad[j] - o.heading_rad[j])).max()))
        out.append({"rep": rep, "n_control_trials": len(keys), "max_path_diff_mm": dxy,
                    "max_heading_diff_deg": dh})
    return pd.DataFrame(out)


def paired(tr):
    """Each brain trial minus the no-input control with the SAME layout and
    replicate (same walking-rhythm seed): arena A vs no_odor, arena B vs
    one_orns_off. Wilcoxon signed-rank on the differences."""
    rows, tests_ = [], []
    for arena, brains, ctrl, m in (("A", ["dna02", "dnpe002", "published_dna02"], "no_odor",
                                    "turn_toward_source_1s_deg"),
                                   ("B", B_BRAIN, "one_orns_off", "turn_toward_intact_1s_deg")):
        c = tr[tr.condition == ctrl].set_index(["layout", "rep"])[m]
        for b in brains:
            g = tr[tr.condition == b]
            d = []
            for _, r in g.iterrows():
                if (r.layout, r.rep) in c.index and np.isfinite(r[m]):
                    d.append(r[m] - c[(r.layout, r.rep)])
                    rows.append({"arena": arena, "condition": b, "control": ctrl,
                                 "layout": r.layout, "rep": r.rep, "metric": m,
                                 "brain": r[m], "control_value": c[(r.layout, r.rep)],
                                 "diff": d[-1]})
            if len(d) >= 3:
                d = np.array(d)
                p = stats.wilcoxon(d).pvalue if np.any(d != 0) else 1.0
                tests_.append({"arena": arena, "condition": b, "control": ctrl, "metric": m,
                               "n_pairs": len(d), "mean_diff": d.mean(),
                               "n_positive": int((d > 0).sum()), "wilcoxon_p": p})
    return pd.DataFrame(rows), pd.DataFrame(tests_)


def style(ax):
    ax.set_aspect("equal")
    ax.grid(color=GRID, lw=0.6)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=MUTED, labelsize=7)


def traj_plot(win, tr, conds, layouts, path, title, ring_color=None):
    conds = [c for c in conds if c in set(tr.condition)]
    if not conds:
        return
    ncol = min(4, len(conds))
    nrow = int(np.ceil(len(conds) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.6 * ncol, 3.5 * nrow + 0.8), squeeze=False)
    for ax in axes.flat[len(conds):]:
        ax.axis("off")
    for ax, c in zip(axes.flat, conds):
        style(ax)
        for i, lay in enumerate(layouts):
            t = tr[(tr.condition == c) & (tr.layout == lay)]
            if t.empty:
                continue
            a = np.radians(t.source_angle_deg.iloc[0])
            d = t.start_dist_mm.iloc[0]
            src = (6.0 * np.cos(a), 6.0 * np.sin(a))
            rc = COL[i] if ring_color is None else ring_color
            ax.add_patch(plt.Circle(src, REACH_MM, fill=False, ec=rc, lw=1.2))
            ax.plot(*src, "+", color=rc, ms=6)
            for _, row in t.iterrows():
                w = win[(win.condition == c) & (win.layout == lay) & (win.rep == row.rep)]
                ax.plot(w.x_mm, w.y_mm, color=COL[i], lw=2 if row.rep == 0 else 1.2,
                        alpha=1.0 if row.rep == 0 else 0.6)
        ax.plot(0, 0, marker=">", color=INK, ms=7)
        ax.set_xlim(-10, 22)
        ax.set_ylim(-14, 14)
        ax.set_title(LABEL.get(c, c), fontsize=8.5, color=INK)
    handles = [plt.Line2D([], [], color=COL[i], lw=2, label=LAYOUT_NAME[l])
               for i, l in enumerate(layouts)]
    fig.legend(handles=handles, loc="lower center", ncol=len(layouts), fontsize=7.5, frameon=False)
    fig.suptitle(title, fontsize=10, color=INK)
    fig.tight_layout(rect=(0, 0.05, 1, 0.97))
    fig.savefig(path, dpi=110)
    plt.close(fig)


def strip_plot(tr, path):
    panels = [("A", [c for c in A_BRAIN + A_CTRL if c in set(tr.condition)],
               "turn_toward_source_1s_deg",
               "Normal fly (both antennae): turn toward the source in the 1st second (deg)"),
              ("B", [c for c in B_BRAIN + B_CTRL if c in set(tr.condition)],
               "turn_toward_intact_1s_deg",
               "One-antenna fly: turn toward the smelling antenna's side in the 1st second (deg)")]
    panels = [p for p in panels if p[1]]
    fig, axes = plt.subplots(len(panels), 1, figsize=(7.5, 0.42 * sum(len(p[1]) for p in panels) + 1.8),
                             squeeze=False)
    for ax, (arena, conds, m, title) in zip(axes[:, 0], panels):
        for j, c in enumerate(conds):
            g = tr[tr.condition == c]
            if arena == "A":
                g = g[g.source_angle_deg != 0]
            x = g[m].to_numpy()
            yj = j + np.linspace(-0.15, 0.15, len(x)) if len(x) > 1 else np.array([j])
            # colour = where the smell is: source side (A) or smelling antenna (B)
            left = ((g.source_angle_deg > 0) if arena == "A"
                    else (g.antennae == "left_only")).to_numpy()
            ax.scatter(x, yj, s=22, color=np.where(left, COL[0], COL[1]), edgecolor="white",
                       linewidth=0.8, zorder=3)
            if len(x):
                ax.plot([x.mean()] * 2, [j - 0.3, j + 0.3], color=INK, lw=2, zorder=4)
        ax.axvline(0, color=MUTED, lw=1)
        ax.set_yticks(range(len(conds)))
        ax.set_yticklabels([f"{LABEL.get(c, c)}  (n={int((tr.condition == c).sum() if arena == 'B' else ((tr.condition == c) & (tr.source_angle_deg != 0)).sum())})"
                            for c in conds], fontsize=7.5, color=INK)
        ax.invert_yaxis()
        ax.grid(axis="x", color=GRID, lw=0.6)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=MUTED, labelsize=7.5)
        ax.set_title(title + "\n(dots = trials, bar = mean; right of 0 = toward)", fontsize=8.5,
                     color=INK, loc="left")
        names = (("source on the left", "source on the right") if arena == "A"
                 else ("left antenna smells", "right antenna smells"))
        ax.legend(handles=[plt.Line2D([], [], ls="", marker="o", color=COL[0], label=names[0]),
                           plt.Line2D([], [], ls="", marker="o", color=COL[1], label=names[1])],
                  loc="lower right", fontsize=7, frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    PLOTS.mkdir(exist_ok=True)
    tr = pd.read_csv(RES / "da1_trials.csv")
    win = pd.read_csv(RES / "da1_windows.csv")
    ct = condition_table(tr)
    ct.to_csv(RES / "da1_condition_table.csv", index=False, float_format="%.3f")
    st, sign = tests(tr)
    st.to_csv(RES / "da1_stats.csv", index=False, float_format="%.4g")
    sign.to_csv(RES / "da1_sign_tests.csv", index=False, float_format="%.4g")
    wt = window_toward(win, tr)
    wt.to_csv(RES / "da1_window_toward.csv", index=False, float_format="%.3f")
    dc = drive_check(win)
    dc.to_csv(RES / "da1_drive_check.csv", index=False, float_format="%.3f")
    ci = control_identity(win)
    ci.to_csv(RES / "da1_control_identity.csv", index=False, float_format="%.6f")
    pr, pt = paired(tr)
    pr.to_csv(RES / "da1_paired_trials.csv", index=False, float_format="%.3f")
    pt.to_csv(RES / "da1_paired_tests.csv", index=False, float_format="%.4g")
    traj_plot(win, tr, A_BRAIN + A_CTRL, ["A+90", "A+45", "A0", "A-45", "A-90"],
              PLOTS / "trajectories_A.png",
              "Normal fly (both antennae smell), cVA source 6 mm away; ring = 2 mm 'reached'")
    traj_plot(win, tr, B_BRAIN + B_CTRL, ["B_Lonly+90", "B_Lonly-90", "B_Ronly+90", "B_Ronly-90"],
              PLOTS / "trajectories_B.png",
              "One-antenna fly (other antenna covered), cVA source 6 mm away (grey rings)",
              ring_color=MUTED)
    strip_plot(tr, PLOTS / "turn_first_second.png")
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(ct.round(2).to_string(index=False))
    print(st.round(4).to_string(index=False))
    print(sign.round(4).to_string(index=False))
    print(wt.round(3).to_string(index=False))
    print(dc.round(3).to_string(index=False))
    print(ci.to_string(index=False))
    print(pt.round(4).to_string(index=False))


if __name__ == "__main__":
    main()

"""Summarize and plot the Phase 9 demo (experiments/phase9/run_demo.py).

Writes experiments/phase9/results/demo_summary.csv and
experiments/phase9/results/trajectories.png (one small panel per condition).
Run: .venv-body\\Scripts\\python.exe experiments/phase9/analyze_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "experiments" / "phase9" / "results"
sys.path.insert(0, str(ROOT))

ORDER = ["brain", "brain_seedB", "brain_strong_odor", "brain_dns_off", "brain_no_odor", "hand_rule",
         "brain_published",
         "brain_eln", "brain_fwd_dns_eln", "brain_dns_off_eln", "brain_no_odor_eln"]
TITLES = {
    "brain": "Brain steers (al_ln fix, seeds 0-3)",
    "brain_seedB": "Brain steers (al_ln fix, seeds 10-13)",
    "brain_strong_odor": "Brain steers, 10x smell sensitivity (al_ln)",
    "brain_dns_off": "Control a: read-out DNs silenced",
    "brain_no_odor": "Control c: no odor",
    "hand_rule": "Control b: hand-written rule",
    "brain_published": "Brain steers (published model)",
    "brain_eln": "Brain steers (eln fix)",
    "brain_fwd_dns_eln": "Brain steers + sets speed (eln fix)",
    "brain_dns_off_eln": "Control a, eln brain loaded",
    "brain_no_odor_eln": "Control c, eln brain loaded",
}
TAGS = {c: "brain-driven steering" for c in ORDER}
TAGS["hand_rule"] = "NOT brain-driven"
TAGS["brain_dns_off"] = TAGS["brain_dns_off_eln"] = "brain output cut"
TAGS["brain_no_odor"] = TAGS["brain_no_odor_eln"] = "no smell input"
#: Panels in the figure (the *_eln controls are identical to the al_ln ones).
PLOT = ["brain", "brain_strong_odor", "brain_dns_off", "hand_rule",
        "brain_published", "brain_eln", "brain_fwd_dns_eln", "brain_no_odor"]
# Reference categorical palette, slots 1-4 in fixed order (validated with the
# dataviz skill's validate_palette.js, light mode: all checks pass; contrast
# WARN for slots 3-4 -> every trajectory is also direct-labelled).
COLORS = {45.0: "#2a78d6", -45.0: "#eb6834", 90.0: "#1baf7a", -90.0: "#eda100"}
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def summary(trials):
    g = trials.groupby("condition")
    out = pd.DataFrame({
        "n_trials": g.size(),
        "reached_source": g.reached.sum().astype(int),
        "mean_final_dist_mm": g.final_dist_mm.mean(),
        "mean_min_dist_mm": g.min_dist_mm.mean(),
        "mean_approach_mm": g.approach_mm.mean(),
        "mean_heading_error_deg": g.mean_heading_error_deg.mean(),
        "mean_net_turn_deg": g.net_turn_deg.mean(),
        "mean_turn_cmd": g.mean_turn_cmd.mean(),
        "mean_frac_windows_turn_left": g.frac_windows_turn_left.mean(),
        "mean_DNa02_L_hz": g.mean_DNa02_L_hz.mean(),
        "mean_DNa02_R_hz": g.mean_DNa02_R_hz.mean(),
        "mean_DNg100_L_hz": g.mean_DNg100_L_hz.mean(),
        "mean_orn_rate_L": g.mean_orn_rate_L.mean(),
        "mean_orn_rate_R": g.mean_orn_rate_R.mean(),
        "mean_path_mm": g.path_mm.mean(),
        "wall_brain_s": g.wall_brain_s.sum(),
        "wall_body_s": g.wall_body_s.sum(),
    })
    return out.reindex([c for c in ORDER if c in out.index])


def paired(trials, a, b, metric="final_dist_mm"):
    """Per start geometry: is condition a closer to the source than b (by ``metric``)?"""
    x = trials[trials.condition == a].set_index("source_angle_deg")[metric]
    y = trials[trials.condition == b].set_index("source_angle_deg")[metric]
    common = x.index.intersection(y.index)
    if len(common) == 0:
        return None
    d = (x[common] - y[common])
    return int((d < 0).sum()), len(common), float(d.mean())


def plot(trials, windows):
    conds = [c for c in PLOT if c in set(trials.condition)]
    ncol = 4
    nrow = int(np.ceil(len(conds) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=(4.6 * ncol, 4.2 * nrow), squeeze=False,
                             facecolor=SURF)
    for ax in axes.ravel():
        ax.set_visible(False)
    for ax, c in zip(axes.ravel(), conds):
        ax.set_visible(True)
        ax.set_facecolor(SURF)
        tr = trials[trials.condition == c]
        for _, t in tr.iterrows():
            ang = float(t.source_angle_deg)
            col = COLORS.get(ang, INK2)
            a = np.radians(ang)
            sx, sy = 15 * np.cos(a), 15 * np.sin(a)
            ax.add_patch(plt.Circle((sx, sy), 2.0, fill=False, lw=1.5, ec=col))
            ax.plot(sx, sy, marker="o", ms=4, color=col)
            ax.text(sx + (2.6 if sx >= 0 else -2.6), sy, f"{ang:+.0f}°", color=INK2,
                    fontsize=8, va="center", ha="left" if sx >= 0 else "right")
            w = windows[(windows.condition == c) & (windows.trial == t.trial)]
            ax.plot(w.x_mm, w.y_mm, color=col, lw=2, solid_capstyle="round")
            ax.plot(w.x_mm.iloc[-1], w.y_mm.iloc[-1], marker="o", ms=8, color=col,
                    mec=SURF, mew=2)
        ax.plot(0, 0, marker="^", ms=8, color=INK, mec=SURF, mew=1.5, zorder=5)
        ax.set_xlim(-14, 50)
        ax.set_ylim(-20, 20)
        ax.set_aspect("equal")
        ax.grid(color=GRID, lw=0.6)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.tick_params(colors=INK2, labelsize=7, length=0)
        n_reach = int(tr.reached.sum())
        ax.set_title(f"{TITLES.get(c, c)}\n({TAGS.get(c, '')}; reached {n_reach}/{len(tr)}, "
                     f"end {tr.final_dist_mm.mean():.0f} mm)", fontsize=8, color=INK,
                     loc="left")
        ax.set_xlabel("x (mm)", fontsize=7, color=INK2)
        ax.set_ylabel("y (mm; + = fly's starting left)", fontsize=7, color=INK2)
    handles = [plt.Line2D([], [], color=col, lw=2, label=f"odor at {ang:+.0f}°")
               for ang, col in COLORS.items()]
    handles.append(plt.Line2D([], [], color=INK, marker="^", lw=0, label="start (facing +x)"))
    fig.legend(handles=handles, loc="lower center", ncol=5, frameon=False, fontsize=8,
               labelcolor=INK2)
    fig.suptitle("Phase 9 demo: fly paths for 3 s (circles = odor source, 2 mm 'reached' radius)."
                 " PRELIMINARY.", fontsize=10, color=INK, x=0.01, ha="left")
    fig.tight_layout(rect=(0, 0.05, 1, 0.95))
    fig.savefig(RES / "trajectories.png", dpi=110, facecolor=SURF)
    plt.close(fig)


def main():
    trials = pd.read_csv(RES / "demo_trials.csv")
    windows = pd.read_csv(RES / "demo_windows.csv")
    s = summary(trials)
    s.to_csv(RES / "demo_summary.csv")
    pd.set_option("display.width", 200)
    print(s.round(2).T.to_string())
    for a, b in [("brain", "brain_dns_off"), ("brain_seedB", "brain_dns_off"),
                 ("brain_strong_odor", "brain_dns_off"),
                 ("brain", "brain_no_odor"), ("hand_rule", "brain_dns_off"),
                 ("brain_eln", "brain_dns_off_eln"), ("brain_published", "brain_dns_off_eln"),
                 ("brain", "hand_rule")]:
        for metric in ("final_dist_mm", "min_dist_mm"):
            r = paired(trials, a, b, metric)
            if r:
                print(f"{a} vs {b}, {metric}: {a} closer in {r[0]}/{r[1]} geometries "
                      f"(mean difference {r[2]:+.1f} mm)")
    # Does the turn command follow the SIDE of the smell, or just its strength?
    rows = []
    for c in ORDER:
        w = windows[(windows.condition == c) & windows.orn_rate_L.notna()]
        if len(w) < 10 or w.turn.std() == 0:
            continue
        side = w.orn_rate_L - w.orn_rate_R
        level = (w.orn_rate_L + w.orn_rate_R) / 2
        rows.append({"condition": c, "windows": len(w),
                     "mean_abs_orn_LR_diff_hz": float(side.abs().mean()),
                     "corr_turn_vs_LR_diff": float(np.corrcoef(w.turn, side)[0, 1]),
                     "corr_turn_vs_mean_rate": float(np.corrcoef(w.turn, level)[0, 1]),
                     "frac_turn_right": float((w.turn < -0.05).mean())})
    if rows:
        cor = pd.DataFrame(rows)
        cor.to_csv(RES / "demo_turn_correlations.csv", index=False)
        print(cor.round(3).to_string(index=False))
    plot(trials, windows)
    print(f"wrote {RES / 'demo_summary.csv'} and {RES / 'trajectories.png'}")


if __name__ == "__main__":
    main()

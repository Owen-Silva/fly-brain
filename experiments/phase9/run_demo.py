"""Phase 9 first demo: walking toward an attractive (DM1) odor, closed loop.

Conditions (each run from the same 4 start geometries):
  brain            brain-driven steering, sign-fixed brain (the fix
                   sim/sign_fixes.py recommends, if its tests pass; on
                   2026-09-23 that was "al_ln_literature")
  brain_seedB      same, with different brain random seeds (10-13)
  brain_dns_off    control (a): same, but the 8 read-out DNs are silenced
                   (their output is cut in the brain and the body gets 0 Hz)
  hand_rule        control (b): FlyGym 1.x's hand-written taxis rule,
                   NOT brain-driven
  brain_no_odor    control (c): same brain, every odor source off
  brain_published  the published model (sign fix "none"), for comparison
  brain_strong_odor sensitivity check: smell neurons 10x more sensitive
  brain_fwd_dns    exploratory: like "brain" but the forward drive ALSO comes
                   from the brain (DNg100 + DNp09), not fixed
  *_eln            the same with the "eln_electrical" fix, which was the
                   recommended fix when the first batch ran

Geometry: the fly starts at (0, 0) facing +x; the odor source is 15 mm away
at +45, -45, +90 or -90 degrees (+ = to the fly's left), 1.5 mm high.
Balanced left/right so a fly that always turns one way cannot look good.
Trial k uses CPG seed k and brain seed k (+10 for brain_seedB). 3 s per
trial, 50 ms windows. A trial stops early if the fly gets within 2 mm.

Leg control, walking rhythm and how a drive becomes a turn: FlyGym's
built-in controller, NOT brain-driven. In every condition except
brain_fwd_dns the forward drive is fixed at 1.0: NOT brain-driven.

Outputs (experiments/phase9/results/): demo_windows.csv (one row per 50 ms
window), demo_trials.csv (one row per trial), demo.log. Resumable: trials
already in demo_trials.csv are skipped.

Run: .venv-body\\Scripts\\python.exe experiments/phase9/run_demo.py [condition ...]
"""

from __future__ import annotations

import gc
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes  # noqa: E402
from sim.body.loop import TrialConfig, run_trial  # noqa: E402
from sim.body.mapping import DriveMapping, SensorMapping  # noqa: E402

OUT = ROOT / "experiments" / "phase9" / "results"
ANGLES_DEG = (45.0, -45.0, 90.0, -90.0)
SOURCE_DIST_MM = 15.0
DURATION_S = 3.0
WINDOW_MS = 50.0
WINDOW_COLS = ["condition", "trial", "window", "t_s", "x_mm", "y_mm", "heading_rad", "dist_mm",
               "I_Lpalp", "I_Rpalp", "I_Lant", "I_Rant", "orn_rate_L", "orn_rate_R",
               "DNa02_L_hz", "DNa02_R_hz", "DNa01_L_hz", "DNa01_R_hz", "DNg100_L_hz",
               "DNg100_R_hz", "DNp09_L_hz", "DNp09_R_hz", "brain_neurons_reached",
               "turn", "forward", "drive_L", "drive_R"]


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "demo.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def choose_fix():
    """The recommended sign fix, if tests/test_sign_fixes.py passes."""
    fix = sign_fixes.RECOMMENDED_FIX
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_sign_fixes.py", "-q",
                        "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    summary = (r.stdout.strip().splitlines() or ["(no output)"])[-1]
    if r.returncode == 0:
        log(f"sign fix: RECOMMENDED_FIX = {fix!r}; tests/test_sign_fixes.py: {summary}")
        return fix, summary
    log(f"!!! sign-fix tests FAILED ({summary}); falling back to the published model "
        f"('none'). LOUD CAVEAT: the published model's smell system runs away.")
    return "none", summary


def conditions(fix):
    """name -> (sign fix or None for no brain, TrialConfig keywords).
    ``fix`` = the currently recommended sign fix (``choose_fix``)."""
    base = dict(duration_s=DURATION_S, window_ms=WINDOW_MS)
    fwd = DriveMapping(forward_mode="brain")
    return {
        "brain": (fix, dict(steering="brain", **base)),
        "brain_seedB": (fix, dict(steering="brain", brain_seed_offset=10, **base)),
        "brain_dns_off": (fix, dict(steering="brain", silence="dns", **base)),
        "hand_rule": (None, dict(steering="hand_rule", **base)),
        "brain_no_odor": (fix, dict(steering="brain", odor_on=False, **base)),
        "brain_published": ("none", dict(steering="brain", **base)),
        "brain_fwd_dns": (fix, dict(steering="brain", drive_mapping=fwd, **base)),
        # Sensitivity check added AFTER seeing that the read-out DNs stayed
        # silent at the pre-set odor strengths: smell neurons 10x more
        # sensitive (i_half 0.001), so DM1 ORNs fire ~120-145 Hz in the arena.
        "brain_strong_odor": (fix, dict(steering="brain",
                                        sensor_mapping=SensorMapping(i_half=0.001), **base)),
        # Run first, while "eln_electrical" was the recommended fix (renamed
        # afterwards so every name has one fix).
        "brain_eln": ("eln_electrical", dict(steering="brain", **base)),
        "brain_dns_off_eln": ("eln_electrical", dict(steering="brain", silence="dns", **base)),
        "brain_no_odor_eln": ("eln_electrical", dict(steering="brain", odor_on=False, **base)),
        "brain_fwd_dns_eln": ("eln_electrical", dict(steering="brain", drive_mapping=fwd, **base)),
    }


def summarize(name, fix, k, angle, out):
    rows = pd.DataFrame(out["rows"])
    fin = out["final"]
    src = np.array(out["config"].source_xy_mm)
    bearing = np.arctan2(src[1] - rows.y_mm, src[0] - rows.x_mm)
    err = np.degrees(np.abs(np.angle(np.exp(1j * (bearing - rows.heading_rad)))))
    xs = np.append(rows.x_mm.to_numpy(), fin["x_mm"])
    ys = np.append(rows.y_mm.to_numpy(), fin["y_mm"])
    head = np.unwrap(np.append(rows.heading_rad.to_numpy(), fin["heading_rad"]))
    d0 = float(rows.dist_mm.iloc[0])
    s = {"condition": name, "fix": fix or "", "trial": k, "source_angle_deg": angle,
         "start_dist_mm": d0, "final_dist_mm": fin["dist_mm"],
         "min_dist_mm": float(min(rows.dist_mm.min(), fin["dist_mm"])),
         "approach_mm": d0 - fin["dist_mm"],
         "reached": out["reached_at_s"] is not None,
         "reached_at_s": out["reached_at_s"] if out["reached_at_s"] is not None else np.nan,
         "duration_s": fin["t_s"] - float(rows.t_s.iloc[0]),
         "path_mm": float(np.hypot(np.diff(xs), np.diff(ys)).sum()),
         "net_turn_deg": float(np.degrees(head[-1] - head[0])),
         "mean_heading_error_deg": float(err.mean()),
         "mean_turn_cmd": float(rows.turn.mean()),
         "frac_windows_turn_left": float((rows.turn > 0.05).mean()),
         "frac_windows_turn_right": float((rows.turn < -0.05).mean()),
         "final_thorax_z_mm": fin["thorax_z_mm"],
         "wall_brain_s": out["wall_brain_s"], "wall_body_s": out["wall_body_s"]}
    for col in ("DNa02_L_hz", "DNa02_R_hz", "DNa01_L_hz", "DNa01_R_hz", "DNg100_L_hz",
                "DNg100_R_hz", "orn_rate_L", "orn_rate_R", "brain_neurons_reached"):
        s["mean_" + col] = float(rows[col].mean()) if col in rows else np.nan
    return s, rows


def main(selected):
    OUT.mkdir(parents=True, exist_ok=True)
    fix, test_summary = choose_fix()
    conds = conditions(fix)
    selected = selected or list(conds)
    trials_csv, windows_csv = OUT / "demo_trials.csv", OUT / "demo_windows.csv"
    done = set()
    if trials_csv.exists():
        prev = pd.read_csv(trials_csv)
        done = set(zip(prev.condition, prev.trial))
    brain, brain_fix = None, None
    for name in selected:
        cfix, kw = conds[name]
        for k, angle in enumerate(ANGLES_DEG):
            if (name, k) in done:
                continue
            if cfix is not None and brain_fix != cfix:
                brain = None
                gc.collect()
                log(f"building brain with sign fix {cfix!r}")
                brain = sign_fixes.build_brain(cfix)
                brain_fix = cfix
            a = np.radians(angle)
            kw2 = dict(kw)
            brain_seed = k + kw2.pop("brain_seed_offset", 0)
            cfg = TrialConfig(name=f"{name}#{k}", seed=k, brain_seed=brain_seed,
                              source_xy_mm=(SOURCE_DIST_MM * np.cos(a), SOURCE_DIST_MM * np.sin(a)),
                              **kw2)
            log(f"start {name} trial {k} (source at {angle:+.0f} deg)")
            out = run_trial(cfg, brain=brain if cfix is not None else None, log=log)
            s, rows = summarize(name, cfix, k, angle, out)
            log(f"done  {name} trial {k}: final dist {s['final_dist_mm']:.1f} mm "
                f"(min {s['min_dist_mm']:.1f}), reached {s['reached']}, net turn "
                f"{s['net_turn_deg']:+.0f} deg, mean turn cmd {s['mean_turn_cmd']:+.2f}, "
                f"wall brain {s['wall_brain_s']:.0f} s body {s['wall_body_s']:.0f} s")
            rows.insert(0, "trial", k)
            rows.insert(0, "condition", name)
            rows = rows.reindex(columns=WINDOW_COLS)
            rows.to_csv(windows_csv, mode="a", header=not windows_csv.exists(), index=False)
            pd.DataFrame([s]).to_csv(trials_csv, mode="a", header=not trials_csv.exists(),
                                     index=False)
    log(f"all selected conditions finished (sign fix {fix!r}; sign-fix tests: {test_summary})")


if __name__ == "__main__":
    main(sys.argv[1:])

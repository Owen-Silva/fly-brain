"""Phase 9 video, step 1 of 2: re-run the four trials the video shows and
record the fly's full body state for rendering.

Plain English: this re-runs four trials of the DA1 (cVA) demo
(experiments/phase9_da1/run_da1.py) with exactly the same settings, seeds
and start layouts, 1.5 s of fly time each. While the physics runs, it copies
the fly's full pose (every joint) every 1 ms, so step 2 (render_video.py) can
draw the fly from any camera without re-running anything. Then it checks
that each re-run followed the SAME path as the saved trial
(experiments/phase9_da1/results/da1_windows.csv), window by window.

The four clips (all replicate 0 = walking-rhythm seed 0 and brain seed 0):
  a  one_dna02     B_Lonly+90  one antenna covered, the brain steers (DNa02)
  b  one_dna02_off B_Lonly+90  the same trial with DNa02 silenced (control)
  c  dna02         A-45        normal fly, source front-right (the failure)
  d  hand_rule     A-45        FlyGym 1.x hand-written rule, NOT brain-driven

Outputs (experiments/phase9_video/):
  states/clip_<k>.npz         pose every 1 ms (qpos) + physics step numbers, and the
                              pose one step before each 50 ms window boundary
  results/clip_<k>_windows.csv one row per 50 ms window (same columns as da1_windows.csv)
  results/path_check.csv      re-run vs saved trial, largest difference per column
  results/simulate.log        progress log

Run: .venv-body\\Scripts\\python.exe experiments/phase9_video/simulate_clips.py [a b c d]
"""

from __future__ import annotations

import gc
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes  # noqa: E402
from sim.body.loop import TrialConfig, run_trial  # noqa: E402
from sim.body.mapping import SensorMapping  # noqa: E402

HERE = ROOT / "experiments" / "phase9_video"
STATES, RESULTS = HERE / "states", HERE / "results"
SAVED = ROOT / "experiments" / "phase9_da1" / "results"
RECORD_EVERY_STEPS = 10          # physics step = 0.1 ms, so one pose per 1 ms
PHYSICS_DT_S = 1e-4              # FlyGym 2.1 timestep (render_video.py re-checks it)
MIN_FREE_GB = 1.5

# The DA1 demo script itself, loaded as a module so its settings are used
# as-is (conditions, layouts, distance, duration, window, sign fix).
_spec = importlib.util.spec_from_file_location("run_da1", SAVED.parent / "run_da1.py")
run_da1 = importlib.util.module_from_spec(_spec)
sys.dont_write_bytecode = True       # leave no __pycache__ in experiments/phase9_da1/
_spec.loader.exec_module(run_da1)
sys.dont_write_bytecode = False

CLIPS = {
    "a": ("one_dna02", "B_Lonly+90", 0),
    "b": ("one_dna02_off", "B_Lonly+90", 0),
    "c": ("dna02", "A-45", 0),
    "d": ("hand_rule", "A-45", 0),
}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(RESULTS / "simulate.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def wait_for_ram():
    while True:
        g = run_da1.free_gb()          # reads free RAM only; writes nothing
        if not (g < MIN_FREE_GB):
            return g
        log(f"free RAM {g:.2f} GB < {MIN_FREE_GB} GB; waiting 60 s")
        time.sleep(60)


def trial_config(condition, layout, rep):
    """The TrialConfig exactly as run_da1.main() builds it."""
    arena, cfix, kw = run_da1.conditions()[condition]
    layouts = run_da1.LAYOUTS_A if arena == "A" else run_da1.LAYOUTS_B
    (antennae, angle), = [(ant, ang) for lay, ant, ang in layouts if lay == layout]
    a = np.radians(angle)
    kw2 = dict(kw)
    if antennae != "both":
        kw2["sensor_mapping"] = SensorMapping(antennae=antennae)
    cfg = TrialConfig(name=f"{condition}/{layout}/{rep}", seed=rep, brain_seed=rep,
                      source_xy_mm=(run_da1.DIST_MM * np.cos(a), run_da1.DIST_MM * np.sin(a)),
                      **kw2)
    return cfg, cfix, antennae, angle


class PoseRecorder:
    """The read-only hook: copies qpos every RECORD_EVERY_STEPS physics steps,
    and also one step before every window boundary. (After a MuJoCo step the
    body positions still describe the state from before that step, so the
    pose the loop logs at a window start belongs to the qpos one step earlier;
    these extra copies let render_video.py check the posed fly exactly.)"""

    def __init__(self, win_steps):
        self.n, self.win_steps = 0, win_steps
        self.steps, self.t, self.qpos = [], [], []
        self.pre_steps, self.pre_qpos = [], []

    def __call__(self, body):
        self.n += 1
        d = body.sim.mj_data
        if self.n % RECORD_EVERY_STEPS == 0:
            self.steps.append(self.n)
            self.t.append(float(d.time))
            self.qpos.append(np.array(d.qpos, dtype=np.float64))
        if self.n % self.win_steps == self.win_steps - 1:
            self.pre_steps.append(self.n)
            self.pre_qpos.append(np.array(d.qpos, dtype=np.float64))


def compare(new_rows, condition, layout, rep):
    """Largest absolute difference per column, re-run vs saved da1_windows.csv."""
    saved = pd.read_csv(SAVED / "da1_windows.csv")
    s = saved[(saved.condition == condition) & (saved.layout == layout) & (saved.rep == rep)]
    s = s.reset_index(drop=True)
    out = {"n_windows_saved": len(s), "n_windows_rerun": len(new_rows)}
    cols = [c for c in run_da1.WINDOW_COLS[4:] if c in new_rows.columns and c in s.columns]
    n = min(len(s), len(new_rows))
    worst = 0.0
    for c in cols:
        a = pd.to_numeric(s[c].iloc[:n], errors="coerce").to_numpy(float)
        b = pd.to_numeric(new_rows[c].iloc[:n], errors="coerce").to_numpy(float)
        both_nan = np.isnan(a) & np.isnan(b)
        diff = np.where(both_nan, 0.0, np.abs(a - b))
        diff = np.where(np.isnan(diff), np.inf, diff)       # NaN on one side only
        out[f"maxdiff_{c}"] = float(diff.max()) if n else np.nan
        worst = max(worst, out[f"maxdiff_{c}"])
    out["worst_diff"] = worst
    out["same_path"] = bool(len(s) == len(new_rows) and worst <= 1e-9)
    return out


def main(selected):
    STATES.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    keys = [k for k in CLIPS if not selected or k in selected]
    brain, brain_fix = None, None
    checks = []
    for k in keys:
        condition, layout, rep = CLIPS[k]
        cfg, cfix, antennae, angle = trial_config(condition, layout, rep)
        if cfix is not None and brain_fix != cfix:
            brain = None
            gc.collect()
            wait_for_ram()
            log(f"building brain with sign fix {cfix!r} (n_threads=2, as run_da1.py)")
            brain = sign_fixes.build_brain(cfix, n_threads=2)
            brain_fix = cfix
        g = wait_for_ram()
        log(f"clip {k}: start {condition} {layout} rep {rep} (free RAM {g:.1f} GB)")
        rec = PoseRecorder(win_steps=int(round(cfg.window_ms * 1e-3 / PHYSICS_DT_S)))
        t0 = time.time()
        out = run_trial(cfg, brain=brain if cfix is not None else None, on_substep=rec)
        wall = time.time() - t0
        rows = pd.DataFrame(out["rows"])
        rows.insert(0, "rep", rep)
        rows.insert(0, "layout", layout)
        rows.insert(0, "condition", condition)
        rows.to_csv(RESULTS / f"clip_{k}_windows.csv", index=False)
        np.savez_compressed(
            STATES / f"clip_{k}.npz", steps=np.array(rec.steps, np.int64),
            t=np.array(rec.t), qpos=np.array(rec.qpos),
            pre_steps=np.array(rec.pre_steps, np.int64), pre_qpos=np.array(rec.pre_qpos),
            window_t0=float(rows.t_s.iloc[0]),
            meta=json.dumps({
                "clip": k, "condition": condition, "layout": layout, "rep": rep,
                "antennae": antennae, "source_angle_deg": angle,
                "source_xy_mm": [float(v) for v in cfg.source_xy_mm],
                "spawn_xy_mm": list(cfg.spawn_xy_mm), "spawn_heading_rad": cfg.spawn_heading_rad,
                "seed": cfg.seed, "brain_seed": cfg.brain_seed, "sign_fix": cfix,
                "steering": cfg.steering, "silence": cfg.silence,
                "duration_s": cfg.duration_s, "window_ms": cfg.window_ms,
                "reached_at_s": out["reached_at_s"], "final": out["final"],
                "record_every_steps": RECORD_EVERY_STEPS, "physics_dt_s": PHYSICS_DT_S,
                "wall_s": wall}))
        chk = {"clip": k, "condition": condition, "layout": layout, "rep": rep,
               **compare(rows, condition, layout, rep)}
        checks.append(chk)
        log(f"clip {k}: done in {wall:.0f} s, {len(rows)} windows, {len(rec.t)} poses; "
            f"same path as saved trial: {chk['same_path']} (largest difference "
            f"{chk['worst_diff']:.3g}; x {chk.get('maxdiff_x_mm', np.nan):.3g} mm, "
            f"y {chk.get('maxdiff_y_mm', np.nan):.3g} mm)")
        prev = RESULTS / "path_check.csv"
        old = pd.read_csv(prev) if prev.exists() else pd.DataFrame()
        if len(old):
            old = old[old["clip"] != k]
        pd.concat([old, pd.DataFrame([chk])], ignore_index=True).sort_values("clip").to_csv(
            prev, index=False)
        if not chk["same_path"]:
            log(f"clip {k}: DIFFERENT from the saved trial; stopping before the next clip")
            break
    log("finished")


if __name__ == "__main__":
    main(sys.argv[1:])

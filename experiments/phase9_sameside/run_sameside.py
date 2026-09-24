"""Closed-loop trials with the same-side release switch (arm 1) and the arm-2
diagnostic map. Conditions, arenas, seeds, trial length and summary measures
are imported unchanged from experiments/phase9_da1/run_da1.py; only the brain
differs (sameside.build(variant)).

Plain English: the physics fly walks in an arena with one cVA source; its
antennae drive the DA1 smell neurons; a descending-neuron pair of the brain
sets the left/right walking drive. Leg movements, walking rhythm and walking
speed are FlyGym's built-in controller: NOT brain-driven.

Variants: "release" = ARM 1 (every same-side ORN -> PN connection x1.39,
Gaudry et al. 2013 Fig. 3e); "map" = ARM 2, DIAGNOSTIC (arm 1 plus same-side
x1.30 more and every glomerulus's left/right size imbalance removed).

Queue order = the pre-registered priority (docs/phase9-sameside.md 1.4).
Outputs (results/): ss_trials.csv (one row per trial), ss_windows.csv (one
row per 50 ms window), ss.log. Resumable: a (variant, condition, layout, rep)
already in ss_trials.csv is skipped.
Run: .venv-body\\Scripts\\python.exe experiments/phase9_sameside/run_sameside.py [variant/condition ...]
"""

from __future__ import annotations

import dataclasses
import gc
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase9_da1"))

import run_da1 as D  # noqa: E402  (conditions, layouts, summarize: unchanged)
import sameside as S  # noqa: E402
from sim.body.loop import TrialConfig, run_trial  # noqa: E402
from sim.body.mapping import SensorMapping  # noqa: E402

OUT = HERE / "results"
MIN_FREE_GB = 2.0
QUEUE = [("release", "dna02", (0, 1, 2)),
         ("release", "one_dna02", (0, 1, 2)),
         ("release", "orns_off", (0, 1, 2)), ("release", "one_orns_off", (0, 1, 2)),
         ("map", "dna02", (0, 1, 2)),
         # ADDED AFTER the brain-only screen, NOT pre-registered, DIAGNOSTIC:
         # the one place where arm 2 changed the screen's answer (a one-antenna
         # DM1 fly, DNa02 +26.7 / -10.3 Hz, every seed right). Its controls are
         # the one-antenna silenced flies: they walk the same straight path.
         # Moved ahead of the remaining control re-runs at 20:25 (those cannot
         # change: straight drive in every window, 0.0 mm from their old twins
         # in all 27 DA1-silenced re-runs).
         ("map", "one_dna02_dm1", (0, 1, 2)),
         ("release", "dna02_off", (0, 1, 2)), ("release", "one_dna02_off", (0, 1, 2)),
         ("release", "no_odor", (0, 1, 2)),
         ("map", "one_dna02", (0, 1, 2)),
         ("release", "dnpe002", (0, 1, 2))]
WINDOW_COLS = ["variant"] + D.WINDOW_COLS + ["DNae007_L_hz", "DNae007_R_hz"]


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "ss.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def free_gb():
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command",
                            "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                           capture_output=True, text=True, timeout=60)
        return int(r.stdout.strip()) / 1024 ** 2
    except Exception:
        return float("nan")


def wait_for_ram():
    while True:
        g = free_gb()
        if not (g < MIN_FREE_GB):
            return g
        log(f"free RAM {g:.2f} GB < {MIN_FREE_GB} GB; waiting 60 s")
        time.sleep(60)


def main(selected):
    OUT.mkdir(parents=True, exist_ok=True)
    conds = D.conditions()
    arena, cfix, kw = conds["one_dna02"]
    conds["one_dna02_dm1"] = (arena, cfix, dict(kw, orn_type="ORN_DM1"))  # vinegar channel
    trials_csv, windows_csv = OUT / "ss_trials.csv", OUT / "ss_windows.csv"
    done = set()
    if trials_csv.exists():
        prev = pd.read_csv(trials_csv)
        done = set(zip(prev.variant, prev.condition, prev.layout, prev.rep))
    queue = [(v, c, reps) for v, c, reps in QUEUE if not selected or f"{v}/{c}" in selected]
    brain, brain_variant = None, None
    for variant, name, reps in queue:
        arena, cfix, kw = conds[name]
        assert cfix == S.FIX, (name, cfix)
        layouts = D.LAYOUTS_A if arena == "A" else D.LAYOUTS_B
        for rep in reps:
            for layout, antennae, angle in layouts:
                if (variant, name, layout, rep) in done:
                    continue
                if brain_variant != variant:
                    brain = None
                    gc.collect()
                    wait_for_ram()
                    t0 = time.perf_counter()
                    brain, rep_build = S.build(variant, n_threads=2, return_report=True)
                    brain_variant = variant
                    log(f"built brain '{variant}' in {time.perf_counter() - t0:.0f} s: "
                        f"{ {k: rep_build[k] for k in ('same_side_factor', 'balance', 'connections_changed') if k in rep_build} }")
                g = wait_for_ram()
                a = np.radians(angle)
                kw2 = dict(kw)
                if antennae != "both":
                    kw2["sensor_mapping"] = SensorMapping(antennae=antennae)
                # record DNae007 too (read-out only; the steering pair is unchanged)
                # (not in "dns" conditions, where every listed neuron is silenced)
                dm = kw2["drive_mapping"]
                if kw2.get("silence", "none") != "dns":
                    kw2["drive_mapping"] = dataclasses.replace(
                        dm, neuron_ids={**dm.neuron_ids, **S.DNAE007})
                cfg = TrialConfig(name=f"{variant}/{name}/{layout}/{rep}", seed=rep,
                                  brain_seed=rep,
                                  source_xy_mm=(D.DIST_MM * np.cos(a), D.DIST_MM * np.sin(a)),
                                  **kw2)
                log(f"start {variant}/{name} {layout} rep {rep} (free RAM {g:.1f} GB)")
                out = run_trial(cfg, brain=brain)
                s, rows = D.summarize(name, cfix, layout, antennae, angle, rep, out)
                s = {"variant": variant, **s}
                for col in ("DNae007_L_hz", "DNae007_R_hz"):
                    s["mean_" + col] = float(rows[col].mean()) if col in rows else np.nan
                log(f"done  {variant}/{name} {layout} rep {rep}: min dist {s['min_dist_mm']:.1f} mm, "
                    f"reached {s['reached']}, turn in 1st s {s['heading_change_1s_deg']:+.0f} deg, "
                    f"mean cmd {s['mean_turn_cmd']:+.2f}, DNa02 {s['mean_DNa02_L_hz']:.1f}/"
                    f"{s['mean_DNa02_R_hz']:.1f}, DNpe002 {s['mean_DNpe002_L_hz']:.1f}/"
                    f"{s['mean_DNpe002_R_hz']:.1f} Hz, wall {s['wall_body_s'] + s['wall_brain_s']:.0f} s")
                rows.insert(0, "rep", rep)
                rows.insert(0, "layout", layout)
                rows.insert(0, "condition", name)
                rows.insert(0, "variant", variant)
                rows.reindex(columns=WINDOW_COLS).to_csv(
                    windows_csv, mode="a", header=not windows_csv.exists(), index=False)
                pd.DataFrame([s]).to_csv(trials_csv, mode="a", header=not trials_csv.exists(),
                                         index=False)
    log("queue finished")


if __name__ == "__main__":
    main(sys.argv[1:])

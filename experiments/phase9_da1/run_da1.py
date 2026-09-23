"""Phase 9 DA1 (cVA) demo: closed-loop trials.

Plain English: the physics fly walks in an arena with one cVA source. Its
antennae smell the source; the smell drives the DA1 smell neurons of the
whole-brain model (sign fix "al_ln_literature"); a pair of the brain's
descending neurons sets the left/right walking drive. Leg movements, walking
rhythm and walking speed are FlyGym's built-in controller: NOT brain-driven.

Arenas (the fly always starts at (0, 0) facing +x; + angle = to its left):
  A  normal fly, both antennae smell. Source 6 mm away at +90 (left), +45,
     0 (ahead), -45, -90 (right) degrees.
  B  one-antenna fly (the other antenna covered; SensorMapping.antennae).
     Left antenna only with the source at +90 or -90, right antenna only with
     the source at +90 or -90. 6 mm.

Conditions (read-out = which descending-neuron pair steers):
  dna02, dnpe002            brain-driven steering (arena A)
  dna02_off, dnpe002_off    same, that DN pair silenced (brain AND body)
  orns_off                  DA1 smell neurons silenced (DNa02 read-out)
  no_odor                   the source is off (DNa02 read-out)
  hand_rule                 FlyGym 1.x hand-written rule, NOT brain-driven
  published_dna02           published model (sign fix "none"), DNa02 read-out
  one_*                     the same, arena B
In the non-silenced brain conditions both pairs are recorded; only the named
pair steers.

Replicate r uses CPG (walking-rhythm) seed r and brain seed r. 1.5 s per
trial, 50 ms windows, stop within 2 mm of the source.

Outputs (experiments/phase9_da1/results/): da1_windows.csv (one row per 50 ms
window), da1_trials.csv (one row per trial), da1.log. Resumable: a trial
already in da1_trials.csv is skipped. Trials are run in the priority order
of QUEUE; name conditions on the command line to run only those.

Run: .venv-body\\Scripts\\python.exe experiments/phase9_da1/run_da1.py [condition ...]
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
from sim.body.mapping import (  # noqa: E402
    DN_IDS, DNPE002_IDS, SensorMapping, dna02_drive_mapping, dnpe002_drive_mapping,
)

OUT = ROOT / "experiments" / "phase9_da1" / "results"
FIX = "al_ln_literature"
DIST_MM = 6.0
DURATION_S = 1.5
WINDOW_MS = 50.0
MIN_FREE_GB = 1.5
LAYOUTS_A = [("A+90", "both", 90.0), ("A+45", "both", 45.0), ("A0", "both", 0.0),
             ("A-45", "both", -45.0), ("A-90", "both", -90.0)]
LAYOUTS_B = [("B_Lonly+90", "left_only", 90.0), ("B_Lonly-90", "left_only", -90.0),
             ("B_Ronly+90", "right_only", 90.0), ("B_Ronly-90", "right_only", -90.0)]
BOTH = {"DNa02_L": DN_IDS["DNa02_L"], "DNa02_R": DN_IDS["DNa02_R"], **DNPE002_IDS}
WINDOW_COLS = ["condition", "layout", "rep", "window", "t_s", "x_mm", "y_mm", "heading_rad",
               "dist_mm", "I_Lant", "I_Rant", "orn_rate_L", "orn_rate_R", "DNa02_L_hz",
               "DNa02_R_hz", "DNpe002_L_hz", "DNpe002_R_hz", "brain_neurons_reached", "turn",
               "forward", "drive_L", "drive_R"]


def conditions():
    """name -> (arena, sign fix or None, TrialConfig keywords)."""
    rec_a = dna02_drive_mapping(neuron_ids=dict(BOTH))      # DNa02 steers, both recorded
    rec_p = dnpe002_drive_mapping(neuron_ids=dict(BOTH))    # DNpe002 steers, both recorded
    base = dict(steering="brain", orn_type="ORN_DA1", duration_s=DURATION_S,
                window_ms=WINDOW_MS)
    c = {}
    for arena, pre in (("A", ""), ("B", "one_")):
        c[pre + "dna02"] = (arena, FIX, dict(base, drive_mapping=rec_a))
        c[pre + "dnpe002"] = (arena, FIX, dict(base, drive_mapping=rec_p))
        c[pre + "dna02_off"] = (arena, FIX, dict(base, drive_mapping=dna02_drive_mapping(),
                                                 silence="dns"))
        c[pre + "dnpe002_off"] = (arena, FIX, dict(base, drive_mapping=dnpe002_drive_mapping(),
                                                   silence="dns"))
        c[pre + "orns_off"] = (arena, FIX, dict(base, drive_mapping=rec_a, silence="orns"))
        c[pre + "no_odor"] = (arena, FIX, dict(base, drive_mapping=rec_a, odor_on=False))
    c["hand_rule"] = ("A", None, dict(steering="hand_rule", duration_s=DURATION_S,
                                      window_ms=WINDOW_MS))
    c["published_dna02"] = ("A", "none", dict(base, drive_mapping=rec_a))
    return c


#: Priority order: (condition, replicates). Re-ordered 2026-09-23 07:15 after
#: a reboot stopped the run at 30 trials (dna02 and dnpe002, arena A, all
#: done): the arena-A brain flies turned LEFT whatever the source side, so
#: the one-antenna test (arena B) and the silenced / no-odor controls that
#: the checkpoint verdict needs go first.
QUEUE = [("dna02", (0, 1, 2)), ("dnpe002", (0, 1, 2)),
         ("one_dna02", (0, 1, 2)),
         ("one_orns_off", (0,)), ("one_dna02_off", (0,)),
         ("no_odor", (0,)), ("orns_off", (0,)), ("dna02_off", (0,)),
         ("hand_rule", (0,)), ("one_orns_off", (1, 2)),
         ("one_dnpe002", (0, 1, 2)), ("one_dnpe002_off", (0,)), ("dnpe002_off", (0,)),
         ("published_dna02", (0,)), ("no_odor", (1, 2)),
         ("one_dna02_off", (1, 2)), ("orns_off", (1, 2)), ("dna02_off", (1, 2))]
#: Dropped from the first plan to save compute: replicates 1-2 of
#: dnpe002_off / one_dnpe002_off / hand_rule / published_dna02, and a separate
#: no-odor control for arena B (there "DA1 smell neurons silenced" is the
#: no-input control). Everything in QUEUE ran (142 trials, finished 10:39).
#: Run a dropped one with e.g. ``run_da1.py dnpe002_off`` after adding it here.


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "da1.log", "a", encoding="utf-8") as f:
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


def heading_at(rows, fin, t_rel):
    """Unwrapped heading (rad) t_rel s after the start (last value if the
    trial ended earlier)."""
    t = np.append(rows.t_s.to_numpy(), fin["t_s"])
    h = np.unwrap(np.append(rows.heading_rad.to_numpy(), fin["heading_rad"]))
    k = np.searchsorted(t - t[0], t_rel - 1e-9)
    return h[min(k, len(h) - 1)] - h[0], t[min(k, len(t) - 1)] - t[0]


def summarize(name, fix, layout, antennae, angle, rep, out):
    rows = pd.DataFrame(out["rows"])
    fin = out["final"]
    src = np.array(out["config"].source_xy_mm)
    dh1, t1 = heading_at(rows, fin, 1.0)
    side = float(np.sign(angle))                      # +1 source left, -1 right, 0 ahead
    intact = {"left_only": 1.0, "right_only": -1.0}.get(antennae, np.nan)
    x = np.append(rows.x_mm.to_numpy(), fin["x_mm"])
    y = np.append(rows.y_mm.to_numpy(), fin["y_mm"])
    h = np.append(rows.heading_rad.to_numpy(), fin["heading_rad"])
    t = np.append(rows.t_s.to_numpy(), fin["t_s"]) - rows.t_s.iloc[0]
    k1 = min(np.searchsorted(t, 1.0 - 1e-9), len(t) - 1)
    bear = np.arctan2(src[1] - y, src[0] - x)
    err = np.degrees(np.abs(np.angle(np.exp(1j * (bear - h)))))
    s = {"condition": name, "fix": fix or "", "layout": layout, "antennae": antennae,
         "source_angle_deg": angle, "rep": rep, "start_dist_mm": float(rows.dist_mm.iloc[0]),
         "min_dist_mm": float(min(rows.dist_mm.min(), fin["dist_mm"])),
         "final_dist_mm": fin["dist_mm"], "reached": out["reached_at_s"] is not None,
         "time_to_reach_s": (out["reached_at_s"] - rows.t_s.iloc[0]
                             if out["reached_at_s"] is not None else np.nan),
         "duration_s": float(t[-1]),
         "heading_change_1s_deg": float(np.degrees(dh1)), "t_for_1s": float(t1),
         "turn_toward_source_1s_deg": float(np.degrees(dh1) * side) if side else np.nan,
         "turn_toward_intact_1s_deg": float(np.degrees(dh1) * intact),
         "bearing_error_start_deg": float(err[0]), "bearing_error_1s_deg": float(err[k1]),
         "net_turn_deg": float(np.degrees(np.unwrap(h)[-1] - h[0])),
         "mean_turn_cmd": float(rows.turn.mean()),
         "mean_turn_cmd_1s": float(rows.turn[(rows.t_s - rows.t_s.iloc[0]) < 1.0].mean()),
         "frac_win_turn_left": float((rows.turn > 0.05).mean()),
         "frac_win_turn_right": float((rows.turn < -0.05).mean()),
         "final_thorax_z_mm": fin["thorax_z_mm"],
         "wall_brain_s": out["wall_brain_s"], "wall_body_s": out["wall_body_s"]}
    for col in ("orn_rate_L", "orn_rate_R", "DNa02_L_hz", "DNa02_R_hz", "DNpe002_L_hz",
                "DNpe002_R_hz"):
        s["mean_" + col] = float(rows[col].mean()) if col in rows else np.nan
    return s, rows


def main(selected):
    OUT.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([sys.executable, "-m", "pytest", "tests/test_sign_fixes.py", "-q",
                        "-p", "no:cacheprovider"], cwd=ROOT, capture_output=True, text=True)
    log(f"tests/test_sign_fixes.py: {(r.stdout.strip().splitlines() or ['?'])[-1]}")
    conds = conditions()
    trials_csv, windows_csv = OUT / "da1_trials.csv", OUT / "da1_windows.csv"
    done = set()
    if trials_csv.exists():
        prev = pd.read_csv(trials_csv)
        done = set(zip(prev.condition, prev.layout, prev.rep))
    queue = [(c, reps) for c, reps in QUEUE if not selected or c in selected]
    brain, brain_fix = None, None
    for name, reps in queue:
        arena, cfix, kw = conds[name]
        layouts = LAYOUTS_A if arena == "A" else LAYOUTS_B
        for rep in reps:
            for layout, antennae, angle in layouts:
                if (name, layout, rep) in done:
                    continue
                if cfix is not None and brain_fix != cfix:
                    brain = None
                    gc.collect()
                    wait_for_ram()
                    log(f"building brain with sign fix {cfix!r} (n_threads=2)")
                    brain = sign_fixes.build_brain(cfix, n_threads=2)
                    brain_fix = cfix
                g = wait_for_ram()
                a = np.radians(angle)
                kw2 = dict(kw)
                if antennae != "both":
                    kw2["sensor_mapping"] = SensorMapping(antennae=antennae)
                cfg = TrialConfig(name=f"{name}/{layout}/{rep}", seed=rep, brain_seed=rep,
                                  source_xy_mm=(DIST_MM * np.cos(a), DIST_MM * np.sin(a)), **kw2)
                log(f"start {name} {layout} rep {rep} (free RAM {g:.1f} GB)")
                out = run_trial(cfg, brain=brain if cfix is not None else None)
                s, rows = summarize(name, cfix, layout, antennae, angle, rep, out)
                log(f"done  {name} {layout} rep {rep}: min dist {s['min_dist_mm']:.1f} mm, "
                    f"reached {s['reached']}, turn in 1st s {s['heading_change_1s_deg']:+.0f} deg, "
                    f"mean cmd {s['mean_turn_cmd']:+.2f}, DNa02 {s['mean_DNa02_L_hz']:.1f}/"
                    f"{s['mean_DNa02_R_hz']:.1f}, DNpe002 {s['mean_DNpe002_L_hz']:.1f}/"
                    f"{s['mean_DNpe002_R_hz']:.1f} Hz, wall {s['wall_body_s'] + s['wall_brain_s']:.0f} s")
                rows.insert(0, "rep", rep)
                rows.insert(0, "layout", layout)
                rows.insert(0, "condition", name)
                rows.reindex(columns=WINDOW_COLS).to_csv(
                    windows_csv, mode="a", header=not windows_csv.exists(), index=False)
                pd.DataFrame([s]).to_csv(trials_csv, mode="a", header=not trials_csv.exists(),
                                         index=False)
    log("queue finished")


if __name__ == "__main__":
    main(sys.argv[1:])

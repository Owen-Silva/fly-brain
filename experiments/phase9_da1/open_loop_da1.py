"""Phase 9 DA1 demo, step 0: open-loop check (brain only, no body).

Question: with the smell strengths a fly's antennae actually get in the body
arena, do the two DA1 read-outs (DNa02 pair, DNpe002 pair) say "turn toward
the smell" in the loop's 50 ms windows?

Stimuli (DA1 ORN rates, left / right, Hz), made with the loop's own sensor
curve (sim.body.mapping.SensorMapping) and the antenna geometry of the body
(antennae 0.317 mm apart, docs/phase9-body-loop.md section 5; source 0.5 mm
above the antennae, an approximation):
  bi_<side>_<d>mm   both antennae smell a source <d> mm straight to that side
  equal_10mm        both antennae smell the same (source straight ahead)
  one_<side>_10mm   only that antenna smells (the other covered), 10 mm
  p6_150_100 / p6_100_150  Phase 6's graded stimuli, now in 50 ms windows

Each stimulus: 2 s of brain time (40 windows of 50 ms, state kept between
windows, exactly like the loop), 3 Poisson seeds. Brain: sign fix
"al_ln_literature", snapshot 630.

Outputs (experiments/phase9_da1/results/): open_loop_windows.csv,
open_loop_summary.csv, open_loop.log. With the argument "sweep":
open_loop_sweep_windows.csv / _summary.csv (one antenna at 100-140 Hz, and
both antennae 3-4 mm from a source).
Run: .venv-body\\Scripts\\python.exe experiments/phase9_da1/open_loop_da1.py [sweep]
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes  # noqa: E402
from sim.body.brain_stepper import BrainStepper  # noqa: E402
from sim.body.mapping import DN_IDS, DNPE002_IDS, SensorMapping, orn_ids  # noqa: E402

OUT = ROOT / "experiments" / "phase9_da1" / "results"
HALF_SEP_MM, DZ_MM = 0.317 / 2, 0.5
N_WIN, WIN_MS, SEEDS = 40, 50.0, (0, 1, 2)
READ = {"DNa02_L": DN_IDS["DNa02_L"], "DNa02_R": DN_IDS["DNa02_R"], **DNPE002_IDS}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "open_loop.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def lateral_rates(d_mm, side):
    """(left, right) ORN rate for a source d_mm straight to one side."""
    sm = SensorMapping()
    near = 1.0 / ((d_mm - HALF_SEP_MM) ** 2 + DZ_MM ** 2)
    far = 1.0 / ((d_mm + HALF_SEP_MM) ** 2 + DZ_MM ** 2)
    rn, rf = float(sm.rate(near)), float(sm.rate(far))
    return (rn, rf) if side == "left" else (rf, rn)


def stimuli():
    s = {}
    for d in (5.0, 10.0, 15.0):
        for side in ("left", "right"):
            s[f"bi_{side}_{d:.0f}mm"] = (*lateral_rates(d, side), +1 if side == "left" else -1)
    r10 = float(SensorMapping().rate(1.0 / (10.0 ** 2 + DZ_MM ** 2)))
    s["equal_10mm"] = (r10, r10, 0)
    s["one_left_10mm"] = (r10, 0.0, +1)
    s["one_right_10mm"] = (0.0, r10, -1)
    s["p6_150_100"] = (150.0, 100.0, +1)
    s["p6_100_150"] = (100.0, 150.0, -1)
    return s


def sweep_stimuli():
    """One antenna only, at the ORN rates the body gives 3-8 mm from the
    source (run with the argument "sweep"; added after the first pass
    showed DNa02 barely fires at 75 Hz)."""
    s = {}
    for r in (100.0, 115.0, 130.0, 140.0):
        s[f"one_left_{r:.0f}hz"] = (r, 0.0, +1)
        s[f"one_right_{r:.0f}hz"] = (0.0, r, -1)
    for d in (3.0, 4.0):
        for side in ("left", "right"):
            s[f"bi_{side}_{d:.0f}mm"] = (*lateral_rates(d, side), +1 if side == "left" else -1)
    return s


def main(sweep=False):
    OUT.mkdir(parents=True, exist_ok=True)
    tag = "_sweep" if sweep else ""
    log("building brain al_ln_literature (n_threads=2)")
    brain = sign_fixes.build_brain("al_ln_literature", n_threads=2)
    left, right = orn_ids("ORN_DA1")
    ids = np.concatenate([left, right])
    ridx = brain.index_of(list(READ.values()))
    names = list(READ)
    rows = []
    for stim, (rl, rr, want) in (sweep_stimuli() if sweep else stimuli()).items():
        rates = np.concatenate([np.full(left.size, rl), np.full(right.size, rr)])
        for seed in SEEDS:
            t0 = time.perf_counter()
            st = BrainStepper(brain, ids, seed=seed)
            for k in range(N_WIN):
                hz = st.step(rates, WIN_MS).rates_hz(ridx)
                rows.append({"stimulus": stim, "seed": seed, "window": k, "orn_L_hz": rl,
                             "orn_R_hz": rr, "want_sign": want,
                             **{f"{n}_hz": float(h) for n, h in zip(names, hz)}})
            log(f"{stim} seed {seed}: L/R ORN {rl:.1f}/{rr:.1f} Hz, "
                f"{time.perf_counter() - t0:.1f} s")
    w = pd.DataFrame(rows)
    w.to_csv(OUT / f"open_loop{tag}_windows.csv", index=False)
    w["dna02_turn_hz"] = w.DNa02_L_hz - w.DNa02_R_hz
    w["dnpe002_turn_hz"] = w.DNpe002_L_hz - w.DNpe002_R_hz
    summ = []
    for stim, g in w.groupby("stimulus", sort=False):
        want = int(g.want_sign.iloc[0])
        s = {"stimulus": stim, "orn_L_hz": g.orn_L_hz.iloc[0], "orn_R_hz": g.orn_R_hz.iloc[0],
             "orn_diff_hz": g.orn_L_hz.iloc[0] - g.orn_R_hz.iloc[0], "want_sign": want}
        for p in ("dna02", "dnpe002"):
            col = g[f"{p}_turn_hz"]
            s[f"{p}_L_hz"] = g[f"{'DNa02' if p == 'dna02' else 'DNpe002'}_L_hz"].mean()
            s[f"{p}_R_hz"] = g[f"{'DNa02' if p == 'dna02' else 'DNpe002'}_R_hz"].mean()
            s[f"{p}_turn_hz"] = col.mean()
            s[f"{p}_frac_silent"] = float((col == 0).mean())
            if want != 0:
                s[f"{p}_frac_right_sign"] = float((np.sign(col) == want).mean())
                s[f"{p}_frac_wrong_sign"] = float((np.sign(col) == -want).mean())
            else:
                s[f"{p}_frac_left"] = float((col > 0).mean())
                s[f"{p}_frac_right"] = float((col < 0).mean())
        summ.append(s)
    pd.DataFrame(summ).to_csv(OUT / f"open_loop{tag}_summary.csv", index=False, float_format="%.3f")
    log("done")


if __name__ == "__main__":
    main(sweep="sweep" in sys.argv[1:])

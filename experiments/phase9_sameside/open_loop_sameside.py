"""Brain-only screen (no body) for the release switch and the arm-2 diagnostic.

Same design as experiments/phase9_da1/open_loop_da1.py: the DA1 (or DM1) smell
neurons get the firing rates the body's antennae would produce; the brain runs
2 s in the loop's 50 ms windows (state kept between windows), 3 Poisson seeds.
Read per window and per side: DNa02, DNpe002, DNae007 (the relay Phase 6 found
between DA1 and DNa02) and the glomerulus's projection neurons (PNs; the
uniglomerular PNs of experiments/phase6/steering/results/pn_ipsi_contra_630.csv).

Variants: sameside.VARIANTS (off = the old model).
Stimuli (left / right ORN rate): source 3 or 5 mm straight to the left or
right of a two-antenna fly; equal smell (5 mm straight ahead); Phase 6's graded
150/100 and 100/150 Hz; one antenna only at 115 Hz (the rate 6 mm from the
source). DM1 gets the one-antenna, graded and equal stimuli.

Outputs (results/): open_loop_<variant>.csv (windows), open_loop_summary.csv,
open_loop.log. Resumable by variant.
Run: .venv-body\\Scripts\\python.exe experiments/phase9_sameside/open_loop_sameside.py [variant ...]
"""

from __future__ import annotations

import gc
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

import sameside as S  # noqa: E402
from open_loop_da1 import lateral_rates  # noqa: E402  (same geometry and sensor curve)
from sim.body.brain_stepper import BrainStepper  # noqa: E402
from sim.body.mapping import DN_IDS, DNPE002_IDS, SensorMapping, orn_ids  # noqa: E402

OUT = HERE / "results"
N_WIN, WIN_MS, SEEDS = 40, 50.0, (0, 1, 2)
ORDER = ["off", "release", "map", "map_same_only", "map_balance_only"]
PN_TABLE = ROOT / "experiments" / "phase6" / "steering" / "results" / "pn_ipsi_contra_630.csv"


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "open_loop.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def stimuli():
    """(glomerulus, name) -> (left Hz, right Hz, wanted sign: +1 left, -1 right, 0 none)."""
    s = {}
    for d in (3.0, 5.0):
        for side in ("left", "right"):
            s[("DA1", f"bi_{side}_{d:.0f}mm")] = (*lateral_rates(d, side), 1 if side == "left" else -1)
    r5 = float(SensorMapping().rate(1.0 / (5.0 ** 2 + 0.5 ** 2)))
    for g in ("DA1", "DM1"):
        s[(g, "equal_5mm")] = (r5, r5, 0)
        s[(g, "p6_150_100")] = (150.0, 100.0, 1)
        s[(g, "p6_100_150")] = (100.0, 150.0, -1)
        s[(g, "one_left_115hz")] = (115.0, 0.0, 1)
        s[(g, "one_right_115hz")] = (0.0, 115.0, -1)
    return s


def readouts():
    pn = pd.read_csv(PN_TABLE)
    r = {"DNa02_L": DN_IDS["DNa02_L"], "DNa02_R": DN_IDS["DNa02_R"], **DNPE002_IDS, **S.DNAE007}
    groups = {}
    for g in ("DA1", "DM1"):
        for side, tag in (("left", "L"), ("right", "R")):
            groups[f"{g}_PN_{tag}"] = pn[(pn.glomerulus == g) & (pn.pn_side == side)].pn_root_id.to_numpy(np.int64)
    return r, groups


def run_variant(variant):
    f = OUT / f"open_loop_{variant}.csv"
    if f.exists():
        log(f"{variant}: already done")
        return
    t0 = time.perf_counter()
    brain = S.build(variant, n_threads=2)
    log(f"{variant}: brain built in {time.perf_counter() - t0:.0f} s")
    single, groups = readouts()
    names = list(single) + list(groups)
    idx_single = brain.index_of(list(single.values()))
    idx_groups = {k: brain.index_of(v) for k, v in groups.items()}
    orns = {g: orn_ids(f"ORN_{g}") for g in ("DA1", "DM1")}
    rows = []
    for (g, stim), (rl, rr, want) in stimuli().items():
        left, right = orns[g]
        ids = np.concatenate([left, right])
        rates = np.concatenate([np.full(left.size, rl), np.full(right.size, rr)])
        for seed in SEEDS:
            st = BrainStepper(brain, ids, seed=seed)
            allidx = np.concatenate([idx_single] + [idx_groups[k] for k in groups])
            for k in range(N_WIN):
                hz = st.step(rates, WIN_MS).rates_hz(allidx)
                row = {"variant": variant, "glom": g, "stimulus": stim, "seed": seed, "window": k,
                       "orn_L_hz": rl, "orn_R_hz": rr, "want_sign": want}
                row.update({n: float(h) for n, h in zip(single, hz[:len(single)])})
                pos = len(single)
                for gname, gi in idx_groups.items():
                    row[gname] = float(hz[pos:pos + gi.size].mean())
                    pos += gi.size
                rows.append(row)
        log(f"{variant} {g} {stim}: L/R ORN {rl:.1f}/{rr:.1f} Hz done")
    pd.DataFrame(rows).to_csv(f, index=False, float_format="%.3f")
    del brain
    gc.collect()
    del names


def summarize():
    frames = [pd.read_csv(OUT / f"open_loop_{v}.csv") for v in ORDER
              if (OUT / f"open_loop_{v}.csv").exists()]
    w = pd.concat(frames, ignore_index=True)
    w["dna02_turn"] = w.DNa02_L - w.DNa02_R
    w["dnpe002_turn"] = w.DNpe002_L - w.DNpe002_R
    out = []
    for (v, g, stim), d in w.groupby(["variant", "glom", "stimulus"], sort=False):
        want = int(d.want_sign.iloc[0])
        s = {"variant": v, "glom": g, "stimulus": stim, "orn_L_hz": d.orn_L_hz.iloc[0],
             "orn_R_hz": d.orn_R_hz.iloc[0], "want_sign": want}
        for c in ("DNa02_L", "DNa02_R", "DNpe002_L", "DNpe002_R", "DNae007_L", "DNae007_R",
                  f"{g}_PN_L", f"{g}_PN_R"):
            s[c.replace(f"{g}_", "")] = d[c].mean()
        for p in ("dna02", "dnpe002"):
            col = d[f"{p}_turn"]
            s[f"{p}_turn_hz"] = col.mean()
            per_seed = d.groupby("seed")[f"{p}_turn"].mean()
            s[f"{p}_turn_by_seed"] = "/".join(f"{x:+.1f}" for x in per_seed)
            s[f"{p}_frac_silent"] = float((col == 0).mean())
            if want:
                s[f"{p}_frac_right_sign"] = float((np.sign(col) == want).mean())
                s[f"{p}_frac_wrong_sign"] = float((np.sign(col) == -want).mean())
                s[f"{p}_seeds_right_sign"] = int((np.sign(per_seed) == want).sum())
        out.append(s)
    pd.DataFrame(out).to_csv(OUT / "open_loop_summary.csv", index=False, float_format="%.3f")
    log("summary written")


if __name__ == "__main__":
    todo = sys.argv[1:] or ORDER
    for v in todo:
        if v != "summary":
            run_variant(v)
    summarize()

"""Held-out FEEDING tests (docs/heldout-validation.md section 1.5, tests G1-G5).

Plain English
-------------
Two real-fly results about the proboscis-extension circuit that Shiu et al. 2024
did not use:
  * OA-VPM4 (2 octopamine cells): activating them makes flies extend the proboscis
    to sugar more (Youn et al. 2018);
  * ISNs (4 cells): activating them makes flies drink more sugar and less water
    (Jourjine et al. 2016).
For each model variant this drives the paper's sugar (or water) taste neurons at a
middling rate, with and without those cells driven too, and reads MN9 (the motor
neuron for proboscis extension). 3 seeds x 30 trials x 1 s per condition, saved
one row at a time to results/feeding/<variant>.csv, so a restart resumes.

Usage:  python experiments/heldout/feeding_heldout.py VARIANT [VARIANT ...]
"""

from __future__ import annotations

import ast
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from run_heldout import IN_RUN_MIN_GB, build, wait_for_ram  # noqa: E402

OUT = HERE / "results" / "feeding"
N_TRIALS = 30
SEEDS = (0, 1, 2)
OA_VPM4 = [720575940624971243, 720575940627702665]
ISN = [720575940617785817, 720575940619731393, 720575940621212654, 720575940624153528]


def _paper_ids():
    """Sugar / water GRNs and MN9 from sim/shiu_model.py (read without Brian2)."""
    want = {"SUGAR_R_630", "WATER_R_630", "MN9_LEFT", "MN9_RIGHT_630"}
    out = {}
    for node in ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in want):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    assert set(out) == want
    return out


P = _paper_ids()
SUGAR, WATER = list(P["SUGAR_R_630"]), list(P["WATER_R_630"])
MN9_CONTRA, MN9_IPSI = P["MN9_LEFT"], P["MN9_RIGHT_630"]
assert len(SUGAR) == 21 and len(WATER) == 18


def cond_list():
    """(name, {root_id: rate}, silenced IDs, base seed)."""
    c = []
    for s in (40, 50):
        c.append((f"sug{s}", {i: s for i in SUGAR}, [], 60_000 + s))
        for r in (50, 100):
            c.append((f"sug{s}+OA{r}", {**{i: s for i in SUGAR}, **{i: r for i in OA_VPM4}}, [], 61_000 + 10 * s + r))
            c.append((f"sug{s}+ISN{r}", {**{i: s for i in SUGAR}, **{i: r for i in ISN}}, [], 62_000 + 10 * s + r))
    c.append(("wat160", {i: 160 for i in WATER}, [], 63_000))
    for r in (50, 100):
        c.append((f"wat160+ISN{r}", {**{i: 160 for i in WATER}, **{i: r for i in ISN}}, [], 64_000 + r))
    c.append(("OA100_alone", {i: 100 for i in OA_VPM4}, [], 65_000))
    c.append(("ISN100_alone", {i: 100 for i in ISN}, [], 66_000))
    # G2 / G5: silencing during taste input (only informative if the cells fire)
    c.append(("sug50_silOA", {i: 50 for i in SUGAR}, OA_VPM4, 60_050))
    c.append(("sug50_silISN", {i: 50 for i in SUGAR}, ISN, 60_050))
    c.append(("wat160_silISN", {i: 160 for i in WATER}, ISN, 63_000))
    return c


def run_variant(variant):
    OUT.mkdir(parents=True, exist_ok=True)
    f = OUT / f"{variant.replace('+', '__')}.csv"
    done = set()
    if f.exists():
        d = pd.read_csv(f)
        done = set(zip(d.condition, d.seed))
    todo = [(n, e, s, b + k) for n, e, s, b in cond_list() for k in SEEDS if (n, b + k) not in done]
    if not todo:
        print(f"=== {variant}: nothing to do", flush=True)
        return
    wait_for_ram()
    brain, _ = build(variant, 2)
    idx = brain.index_of([MN9_CONTRA, MN9_IPSI] + OA_VPM4 + ISN)
    for name, excite, silence, seed in todo:
        wait_for_ram(IN_RUN_MIN_GB)
        t0 = time.perf_counter()
        res = brain.run(excite=excite, silence=silence, duration_ms=1000.0, n_trials=N_TRIALS, seed=seed)
        cnt = np.bincount(res.neuron, minlength=brain.n_neurons)[idx] / N_TRIALS
        row = {"variant": variant, "condition": name, "seed": seed,
               "MN9_contra_hz": cnt[0], "MN9_ipsi_hz": cnt[1],
               "OA_VPM4_mean_hz": cnt[2:4].mean(), "ISN_mean_hz": cnt[4:8].mean(),
               "spikes_per_trial": res.neuron.size / N_TRIALS,
               "wall_s": round(time.perf_counter() - t0, 1)}
        pd.DataFrame([row]).to_csv(f, mode="a", header=not f.exists(), index=False)
        print(f"  {variant} {name} seed {seed}: MN9 {cnt[0]:.1f} / {cnt[1]:.1f} Hz, "
              f"OA-VPM4 {row['OA_VPM4_mean_hz']:.1f}, ISN {row['ISN_mean_hz']:.1f}; {row['wall_s']} s", flush=True)
    del brain


if __name__ == "__main__":
    for v in sys.argv[1:]:
        run_variant(v)

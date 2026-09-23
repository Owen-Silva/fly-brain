"""Phase 7 upgrade 4 (cell-type-specific parameters): re-run the Phase 3 checks.

Plain English
-------------
For every model version ("config") below and every condition, this runs
independent random seeds x 30 trials x 1 s of the whole fly brain (snapshot
630) and saves, per seed:
  * how many spikes every neuron fired (summed over the 30 trials),
  * MN9 spike counts per trial (both sides),
  * total spikes per trial,
  * the Phase 6 runaway measure per trial: the largest number of DIFFERENT
    neurons firing in any 10 ms slice (runaway = more than 1,500), and the
    onset (first 1 ms bin with more than 200 spikes).
Results go to experiments/phase7_celltype/results/<config>/<condition>_s<k>.npz
and are skipped if they already exist, so the script can be restarted.

The seeds are the same as in experiments/phase7/run_phase7.py (base seed of the
condition + 0, 1, 2), so the "baseline" here must reproduce the Phase 7
baseline MN9 numbers exactly (checked by analyze.py).

Usage:  python experiments/phase7_celltype/run_celltype.py CONFIG [CONFIG ...]
        python experiments/phase7_celltype/run_celltype.py --list
"""

from __future__ import annotations

import ast
import ctypes
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim.celltype_params import CellTypeBrain  # noqa: E402

OUT = ROOT / "experiments" / "phase7_celltype" / "results"
N_TRIALS = 30
SEEDS = (0, 1, 2)
RUNAWAY_SEEDS = (0, 1, 2, 3, 4)          # 150 trials: runaway is rare (~4% in Phase 6)
NEW_SEEDS = (10, 11, 12)                 # "baseline with new seeds" = the noise floor
RUNAWAY_DISTINCT_10MS = 1500             # Phase 6 definition (docs/phase6-runaway-activity.md)
ONSET_SPIKES_1MS = 200


def _ids():
    """GRN and MN9 IDs from sim/shiu_model.py, read without importing Brian2."""
    want = {"SUGAR_R_630", "BITTER_R_630", "WATER_R_630", "IR94E_630", "MN9_LEFT",
            "MN9_RIGHT_630"}
    out = {}
    for node in ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8")).body:
        if (isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id in want):
            out[node.targets[0].id] = ast.literal_eval(node.value)
    assert set(out) == want, out.keys()
    return out


IDS = _ids()
MN9_CONTRA, MN9_IPSI = IDS["MN9_LEFT"], IDS["MN9_RIGHT_630"]
SETS = {"sugar": IDS["SUGAR_R_630"], "bitter": IDS["BITTER_R_630"],
        "water": IDS["WATER_R_630"], "ir94e": IDS["IR94E_630"]}


def _dm1_orns():
    import pandas as pd
    lab = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                          columns=["root_id", "hemibrain_type"])
    return [int(i) for i in lab.root_id[lab.hemibrain_type == "ORN_DM1"]]


SETS["dm1_orn"] = _dm1_orns()

# name: (list of (set, rate Hz), base seed). Base seeds as in Phase 3 / Phase 7.
CONDITIONS = {
    "sugar_100Hz": ([("sugar", 100)], 1_000),
    "sugar_200Hz": ([("sugar", 200)], 2_000),
    "water_200Hz": ([("water", 200)], 3_000),
    "bitter_200Hz": ([("bitter", 200)], 4_000),
    "sugar100_bitter120": ([("sugar", 100), ("bitter", 120)], 6_000),
    "sugar200_ir94e200": ([("sugar", 200), ("ir94e", 200)], 7_000),
    # Phase 6: Ir94e alone runs away more often (13%), so it is the most
    # sensitive test of whether an upgrade changes runaway activity.
    "ir94e_200Hz": ([("ir94e", 200)], 8_000),
    # Smell: the 68 DM1 olfactory receptor neurons (both antennae), 150 Hz, as
    # in the Phase 5 olfaction lane. Not a Phase 3 check: it shows what the
    # upgrade changes where the measured cell types (PNs, Kenyon cells) are.
    "dm1_orn_150Hz": ([("dm1_orn", 150)], 9_000),
}
CHECK_CONDITIONS = ("sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz",
                    "sugar100_bitter120")
RUNAWAY_CONDITIONS = ("sugar200_ir94e200", "ir94e_200Hz")

VARIANT_CONDITIONS = RUNAWAY_CONDITIONS + ("dm1_orn_150Hz",)


def _configs():
    return {
        # the untouched baseline loop (sim/fast_engine.py) on the same brain object
        "baseline": dict(engine="baseline"),
        "baseline_newseeds": dict(engine="baseline", seeds=NEW_SEEDS,
                                  conditions=CHECK_CONDITIONS),
        # THE upgrade: every measured value in celltype_params.csv
        "CT_main": dict(celltype=dict()),
        # Which cell group causes what, and the two judgement calls (celltype_params.csv
        # rows 5 and 9). Only the conditions where CT_main differs from the baseline at
        # all: in the five taste checks none of the changed neurons fires in either
        # model (stage 1), so those runs would be copies of the baseline.
        "CT_only_uPN": dict(celltype=dict(groups=["uPN_ACh"]), conditions=VARIANT_CONDITIONS, seeds=(0,)),
        "CT_only_KC": dict(celltype=dict(groups=["KC"]), conditions=VARIANT_CONDITIONS, seeds=(0,)),
        "CT_PNgap17.8": dict(celltype=dict(overrides={"uPN_ACh": {"v_th_gap_mV": 17.8}}),
                             conditions=VARIANT_CONDITIONS, seeds=(0,)),
        "CT_KCtau200": dict(celltype=dict(overrides={"KC": {"t_mbr_ms": 200.0}}),
                            conditions=VARIANT_CONDITIONS, seeds=(0,)),
    }


def free_ram_gb():
    class MEMSTAT(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MEMSTAT()
    m.dwLength = ctypes.sizeof(MEMSTAT)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30


def wait_for_ram(min_gb=1.5):
    while free_ram_gb() < min_gb:
        print(f"    free RAM {free_ram_gb():.2f} GB < {min_gb} GB, waiting 30 s", flush=True)
        time.sleep(30)


def runaway_measures(res, n_trials, n_steps, dt_ms):
    """Per trial: max different neurons in any 10 ms slice, and onset (ms) =
    first 1 ms bin with > 200 spikes (NaN if the trial is not runaway).
    Same definitions as experiments/phase6/runaway/common.py."""
    per_ms = int(round(1.0 / dt_ms))
    n_ms = n_steps // per_ms
    n10 = n_ms // 10
    step = res.step.astype(np.int64)
    neuron = res.neuron.astype(np.int64)
    trial = res.trial.astype(np.int64)
    key = np.unique((trial * n10 + step // (10 * per_ms)) * 1_000_000 + neuron)
    d10 = np.bincount(key // 1_000_000, minlength=n_trials * n10)[:n_trials * n10]
    maxd = d10.reshape(n_trials, n10).max(axis=1)
    s1 = np.bincount(trial * n_ms + step // per_ms, minlength=n_trials * n_ms)
    s1 = s1[:n_trials * n_ms].reshape(n_trials, n_ms)
    onset = np.full(n_trials, np.nan)
    for k in np.flatnonzero(maxd > RUNAWAY_DISTINCT_10MS):
        over = np.flatnonzero(s1[k] > ONSET_SPIKES_1MS)
        if over.size:
            onset[k] = float(over[0])
    return maxd, onset


def run_config(brain, name, cfg):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    base = cfg.get("engine") == "baseline"
    brain.set_celltype(**cfg.get("celltype", {})) if not base else brain.set_celltype(enabled=False)
    meta = {"config": name, "engine": "baseline" if base else "celltype",
            "celltype": "baseline engine" if base else brain.describe(),
            "n_trials_per_seed": N_TRIALS}
    (d / "config.json").write_text(json.dumps(meta, indent=1, default=float))
    print(f"=== {name}: {json.dumps(meta['celltype'], default=float)[:400]}", flush=True)
    seeds = cfg.get("seeds", SEEDS)
    mn9_idx = brain.index_of([MN9_CONTRA, MN9_IPSI])
    for cond, (inputs, base_seed) in CONDITIONS.items():
        if cond not in cfg.get("conditions", CONDITIONS):
            continue
        excite = {}
        for s, r in inputs:
            for i in SETS[s]:
                excite[int(i)] = float(r)
        cond_seeds = tuple(seeds)
        if cond in RUNAWAY_CONDITIONS and name != "baseline_newseeds":
            cond_seeds = RUNAWAY_SEEDS
        for k, sd in enumerate(cond_seeds):
            f = d / f"{cond}_s{k}.npz"
            if f.exists():
                continue
            wait_for_ram()
            runner = brain.run_baseline if base else brain.run
            t0 = time.perf_counter()
            res = runner(excite=excite, duration_ms=1000.0, n_trials=N_TRIALS, seed=base_seed + sd)
            counts = np.bincount(res.neuron, minlength=brain.n_neurons)
            nz = np.flatnonzero(counts)
            per_trial_total = np.bincount(res.trial, minlength=N_TRIALS)
            mn9 = np.zeros((2, N_TRIALS), np.int64)
            for r_, idx in enumerate(mn9_idx):
                m = res.neuron == idx
                mn9[r_] = np.bincount(res.trial[m], minlength=N_TRIALS)
            n_steps = int(round(res.duration_ms / res.dt_ms))
            maxd, onset = runaway_measures(res, N_TRIALS, n_steps, res.dt_ms)
            # per trial: how many neurons of each changed cell group fired at all
            grp_active = {}
            for g, idx in brain.members.items():
                m = np.isin(res.neuron, idx)
                key = np.unique(res.trial[m].astype(np.int64) * brain.n_neurons + res.neuron[m])
                grp_active[f"active_{g}"] = np.bincount(key // brain.n_neurons, minlength=N_TRIALS)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz].astype(np.int64),
                                per_trial_total=per_trial_total, mn9=mn9,
                                max_distinct_10ms=maxd, onset_ms=onset, **grp_active,
                                seed=base_seed + sd, wall_s=time.perf_counter() - t0,
                                neurons_reached=np.array(res.neurons_reached))
            print(f"  {cond} seed {base_seed + sd}: MN9 contra {mn9[0].mean():.1f} Hz, "
                  f"ipsi {mn9[1].mean():.1f} Hz, spikes/trial median {np.median(per_trial_total):.0f}, "
                  f"runaway {int((maxd > RUNAWAY_DISTINCT_10MS).sum())}/{N_TRIALS}, "
                  f"{time.perf_counter() - t0:.1f} s", flush=True)
            del res


def main(argv):
    configs = _configs()
    if not argv or argv[0] == "--list":
        print("\n".join(configs))
        return
    for a in argv:
        if a not in configs:
            raise SystemExit(f"unknown config {a}; use --list")
    wait_for_ram()
    brain = CellTypeBrain(snapshot="630", n_threads=2)
    for a in argv:
        run_config(brain, a, configs[a])


if __name__ == "__main__":
    main(sys.argv[1:])

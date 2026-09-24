"""Held-out validation: the Shiu et al. 2024 antennal-grooming tests on each model variant.

Plain English
-------------
For one model variant ("none" = the published model, or a sign fix / Phase 7
switch), this runs the pre-registered tests of docs/heldout-validation.md:

  A  JO-CE versus JO-F -> aBN1 (Fig. 5g)                 3 seeds x 30 trials
  B  JO-F with 3 inhibitory neurons silenced -> aBN1      3 seeds x 30 trials
  C  all 146 JONs -> aBN1, aDN1, aDN2 (Fig. 5b)           3 seeds x 30 trials
  F  single-group activations for the Hampel 2015 tests  3 seeds x 30 trials
  D  each of the paper's top-300 neurons alone at 200 Hz  1 seed x 10 trials each
  E  all JONs at 140 Hz with each of the 300 silenced     1 seed x 10 trials each,
     paired with a no-silencing control on the same random input

Every condition is saved to its own file as soon as it finishes
(results/<variant>/...), and existing files are skipped, so a crash or a Windows
restart only loses the condition that was running.

Usage:
  python experiments/heldout/run_heldout.py VARIANT [--tests ABCFDE] [--threads 2]
Variants: none, al_ln_literature, al_ln_literature+da_5ht_literature,
          delays, adaptation, celltype, gap
"""

from __future__ import annotations

import argparse
import ctypes
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

import ids  # noqa: E402

RESULTS = HERE / "results"
N_TRIALS = 30
SEEDS = (0, 1, 2)

ABN2_2026 = [720575940634683237, 720575940618961857, 720575940621355759]   # aBN2_1, _2, _3
DNGE220 = 720575940611163610          # the paper's "Descending BN2_3"
MN9 = 720575940660219265
KEY = {"aBN1": ids.ABN1, "aDN1": ids.ADN1, "aDN2": ids.ADN2, "DNge220": DNGE220,
       "aBN2_1": ABN2_2026[0], "aBN2_2": ABN2_2026[1], "aBN2_3": ABN2_2026[2],
       "inh_CB0443": ids.THREE_INHIBITORY[0], "inh_CB0496a": ids.THREE_INHIBITORY[1],
       "inh_CB0496b": ids.THREE_INHIBITORY[2], "MN9": MN9}

# name: (stimulated IDs, rate Hz, silenced IDs, voltage-recorded IDs, base seed)
CONDITIONS = {
    # Test A (and F1/F2 use F_220)
    "CE_60": (ids.JON_CE, 60, [], [], 11_000),
    "CE_100": (ids.JON_CE, 100, [], [], 12_000),
    "CE_140": (ids.JON_CE, 140, [], [], 13_000),
    "CE_220": (ids.JON_CE, 220, [], [], 14_000),
    "F_60": (ids.JON_F, 60, [], [], 21_000),
    "F_100": (ids.JON_F, 100, [], [], 22_000),
    "F_140": (ids.JON_F, 140, [], [], 23_000),
    "F_220": (ids.JON_F, 220, [], [], 24_000),
    # Test B
    "Fsil_100": (ids.JON_F, 100, ids.THREE_INHIBITORY, [], 32_000),
    "Fsil_220": (ids.JON_F, 220, ids.THREE_INHIBITORY, [], 34_000),
    # Test C
    "ALL_100": (ids.JON_ALL, 100, [], [], 42_000),
    "ALL_140": (ids.JON_ALL, 140, [], [], 43_000),
    "ALL_220": (ids.JON_ALL, 220, [], [], 44_000),
    # Test F (Hampel et al. 2015, Fig. 6)
    "aBN1_200": ([ids.ABN1], 200, [], [], 51_000),
    "aBN2x3_200": (ABN2_2026, 200, [], [ids.ADN2, ids.ABN1, ids.ADN1], 52_000),
    "DNge220_200": ([DNGE220], 200, [], [ids.ADN2], 53_000),
}
TEST_CONDS = {
    "A": ["CE_60", "CE_100", "CE_140", "CE_220", "F_60", "F_100", "F_140", "F_220"],
    "B": ["Fsil_100", "Fsil_220"],
    "C": ["ALL_100", "ALL_140", "ALL_220"],
    "F": ["aBN1_200", "aBN2x3_200", "DNge220_200"],
    # short versions for the variants (the rates the pass/fail rules use)
    "a": ["CE_100", "CE_220", "F_100", "F_220"],
    "c": ["ALL_140", "ALL_220"],
}
SUFF_RATE, SUFF_TRIALS, SUFF_SEED = 200, 10, 70_000
NEC_RATE, NEC_TRIALS, NEC_SEED = 140, 10, 80_000
# Free RAM needed before BUILDING a brain (1.5 GB, the shared-machine rule) and
# before each run inside an already-built process (needs only ~0.3 GB more).
IN_RUN_MIN_GB = 0.8


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


def build(variant, n_threads):
    """The model variant, built exactly as the project's own modules define it."""
    if variant in ("none", "al_ln_literature", "al_ln_literature+da_5ht_literature"):
        from sim.sign_fixes import build_brain
        return build_brain(fix=variant, n_threads=n_threads), {"fix": variant}
    if variant in ("delays", "adaptation"):
        from sim.realism import build_realistic_brain
        b = build_realistic_brain(fix="none", n_threads=n_threads, realism={variant: True})
        return b, {"fix": "none", "realism": {k: v for k, v in b.realism.items()}}
    if variant == "celltype":
        from sim.celltype_params import CellTypeBrain
        b = CellTypeBrain("630", n_threads=n_threads)
        b.set_celltype()
        return b, {"fix": "none", "celltype": "full table (sim/celltype_params.py)"}
    if variant == "gap":
        from sim.gap_junctions import build_gap_brain
        b = build_gap_brain(fix="al_ln_literature", n_threads=n_threads)
        return b, {"fix": "al_ln_literature", "gap_kappa": b.kappa_by_class,
                   "n_pairs": 0 if b.coupling is None else int(len(b.coupling))}
    raise ValueError(f"unknown variant {variant}")


def run_condition(brain, out_dir, name):
    stim, rate, silence, record, base = CONDITIONS[name]
    key_idx = brain.index_of(list(KEY.values()))
    for k, sd in enumerate(SEEDS):
        f = out_dir / f"{name}_s{k}.npz"
        if f.exists():
            continue
        wait_for_ram(IN_RUN_MIN_GB)
        t0 = time.perf_counter()
        res = brain.run(excite=list(stim), silence=list(silence), duration_ms=1000.0,
                        n_trials=N_TRIALS, seed=base + sd, rate_hz=float(rate),
                        record_v=list(record))
        counts = np.bincount(res.neuron, minlength=brain.n_neurons)
        nz = np.flatnonzero(counts)
        key_trials = np.zeros((len(KEY), N_TRIALS), np.int32)
        for r, idx in enumerate(key_idx):
            m = res.neuron == idx
            key_trials[r] = np.bincount(res.trial[m], minlength=N_TRIALS)
        extra = {}
        for rid in record:
            v = res.voltages_mV[int(rid)]            # (trials, steps), mV
            extra[f"v_mean_trace_{rid}"] = v.mean(axis=0).astype(np.float32)
            extra[f"v_mean_per_trial_{rid}"] = v.mean(axis=1)
        np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz].astype(np.int64),
                            key_names=np.array(list(KEY)), key_trials=key_trials,
                            per_trial_total=np.bincount(res.trial, minlength=N_TRIALS),
                            seed=base + sd, rate=rate, wall_s=time.perf_counter() - t0, **extra)
        kr = key_trials.mean(axis=1)
        print(f"  {name} seed {base + sd}: aBN1 {kr[0]:.1f}  aDN1 {kr[1]:.1f}  aDN2 {kr[2]:.1f}  "
              f"DNge220 {kr[3]:.1f}  aBN2(2026) {kr[4:7].mean():.2f} Hz; "
              f"{time.perf_counter() - t0:.1f} s", flush=True)
        del res


def top300(jons=True):
    """The paper's own top-300 list, non-JON neurons first (the pass/fail rules
    of Tests D and E only count non-JON neurons; the JONs come last and are
    skipped with jons=False)."""
    t = [int(i) for i in pd.read_csv(RESULTS / "published_top300.csv").root_id]
    jon = set(ids.JON_ALL)
    return [i for i in t if i not in jon] + ([i for i in t if i in jon] if jons else [])


def _append(path, row, header):
    new = not path.exists()
    with open(path, "a", encoding="utf-8") as fh:
        if new:
            fh.write(",".join(header) + "\n")
        fh.write(",".join(str(row[h]) for h in header) + "\n")


def _done(path):
    if not path.exists():
        return set()
    return set(pd.read_csv(path).root_id.astype(np.int64))


def run_sufficiency(brain, out_dir, jons=True):
    """Test D: each top-300 neuron driven alone; aDN1 / aDN2 rates."""
    path = out_dir / "sufficiency.csv"
    done = _done(path)
    header = ["root_id", "aDN1_hz", "aDN2_hz", "aBN1_hz", "total_spikes_per_trial", "wall_s"]
    idx = brain.index_of([ids.ADN1, ids.ADN2, ids.ABN1])
    t_all = time.perf_counter()
    for n, rid in enumerate(top300(jons)):
        if rid in done:
            continue
        t0 = time.perf_counter()
        res = brain.run(excite=[rid], duration_ms=1000.0, n_trials=SUFF_TRIALS,
                        seed=SUFF_SEED, rate_hz=float(SUFF_RATE))
        c = np.bincount(res.neuron, minlength=brain.n_neurons)
        _append(path, {"root_id": rid, "aDN1_hz": c[idx[0]] / SUFF_TRIALS,
                       "aDN2_hz": c[idx[1]] / SUFF_TRIALS, "aBN1_hz": c[idx[2]] / SUFF_TRIALS,
                       "total_spikes_per_trial": res.neuron.size / SUFF_TRIALS,
                       "wall_s": round(time.perf_counter() - t0, 3)}, header)
        if n % 50 == 0:
            print(f"  sufficiency {n}/300 ({time.perf_counter() - t_all:.0f} s)", flush=True)


def run_necessity(brain, out_dir, jons=True):
    """Test E: all JONs at 140 Hz, each top-300 neuron silenced, paired seed."""
    path = out_dir / "necessity.csv"
    done = _done(path)
    header = ["root_id", "aDN1_hz", "aDN2_hz", "aBN1_hz", "DNge220_hz", "total_spikes_per_trial",
              "wall_s"]
    idx = brain.index_of([ids.ADN1, ids.ADN2, ids.ABN1, DNGE220])
    t_all = time.perf_counter()
    todo = [0] + top300(jons)        # root_id 0 = the no-silencing control
    for n, rid in enumerate(todo):
        if rid in done:
            continue
        wait_for_ram(IN_RUN_MIN_GB)
        t0 = time.perf_counter()
        res = brain.run(excite=ids.JON_ALL, silence=[] if rid == 0 else [rid], duration_ms=1000.0,
                        n_trials=NEC_TRIALS, seed=NEC_SEED, rate_hz=float(NEC_RATE))
        c = np.bincount(res.neuron, minlength=brain.n_neurons)
        _append(path, {"root_id": rid, "aDN1_hz": c[idx[0]] / NEC_TRIALS,
                       "aDN2_hz": c[idx[1]] / NEC_TRIALS, "aBN1_hz": c[idx[2]] / NEC_TRIALS,
                       "DNge220_hz": c[idx[3]] / NEC_TRIALS,
                       "total_spikes_per_trial": res.neuron.size / NEC_TRIALS,
                       "wall_s": round(time.perf_counter() - t0, 3)}, header)
        if n % 50 == 0:
            print(f"  necessity {n}/301 ({time.perf_counter() - t_all:.0f} s)", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("--tests", default="ABCFDE")
    ap.add_argument("--threads", type=int, default=2)
    a = ap.parse_args()
    out_dir = RESULTS / a.variant.replace("+", "__")
    out_dir.mkdir(parents=True, exist_ok=True)
    wait_for_ram()
    t0 = time.perf_counter()
    brain, meta = build(a.variant, a.threads)
    try:
        import pyarrow as pa
        pa.default_memory_pool().release_unused()
    except Exception:  # noqa: BLE001
        pass
    meta.update(variant=a.variant, snapshot=brain.snapshot, n_trials=N_TRIALS, seeds=list(SEEDS),
                build_s=round(time.perf_counter() - t0, 1))
    (out_dir / "config.json").write_text(json.dumps(meta, indent=1, default=str), encoding="utf-8")
    print(f"=== {a.variant}: built in {meta['build_s']} s; free RAM {free_ram_gb():.2f} GB", flush=True)
    for t in a.tests:
        if t in TEST_CONDS:
            for name in TEST_CONDS[t]:
                run_condition(brain, out_dir, name)
        elif t in "Dd":
            run_sufficiency(brain, out_dir, jons=(t == "D"))
        elif t in "Ee":
            run_necessity(brain, out_dir, jons=(t == "E"))
    print(f"=== {a.variant}: done in {time.perf_counter() - t0:.0f} s", flush=True)


if __name__ == "__main__":
    main()

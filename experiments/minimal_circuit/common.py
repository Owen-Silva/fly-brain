"""Shared helpers for the minimal-circuit lane (PRELIMINARY).

Plain English
-------------
* ``paper_ids()`` reads the paper's taste-neuron lists and MN9 straight out of
  sim/shiu_model.py without importing it (importing it loads Brian2).
* ``CONDITIONS`` are the seven stimuli of the pass rule (docs/minimal-circuit.md).
* ``run_conditions()`` runs every stimulus on a brain (whole or pruned) and
  returns MN9's firing rate in every trial.
* ``check_rule()`` applies the fixed pass rule, or the stricter search version.
* ``wait_for_ram()`` blocks until at least 1.5 GB of memory is free (other
  lanes share this machine).
"""

import ast
import ctypes
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
RES = HERE / "results"
RAW = RES / "raw"
RES.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)

FIX = "al_ln_literature"
MN9 = 720575940660219265
SEARCH_SEED = 7
SEARCH_TRIALS = 10
VALID_SEEDS = (0, 1, 2)
VALID_TRIALS = 30

# name -> {group: rate in Hz}; group order (sugar, water, bitter) fixes the
# order in which random input is drawn.
CONDITIONS = {
    "S100": {"SUGAR": 100.0},
    "S200": {"SUGAR": 200.0},
    "W100": {"WATER": 100.0},
    "W200": {"WATER": 200.0},
    "B100": {"BITTER": 100.0},
    "B200": {"BITTER": 200.0},
    "S100+B100": {"SUGAR": 100.0, "BITTER": 100.0},
}
GROUP_ORDER = ("SUGAR", "WATER", "BITTER")

# The fixed rule (docs/minimal-circuit.md section 1) and the stricter search version.
RULE = dict(tol=0.10, bitter_max_hz=0.5, brake_frac=0.5)
SEARCH_RULE = dict(tol=0.075, bitter_max_hz=0.0, brake_frac=0.6)


def paper_ids():
    tree = ast.parse((ROOT / "sim" / "shiu_model.py").read_text(encoding="utf-8"))
    wanted = {"SUGAR_R_630": "SUGAR", "BITTER_R_630": "BITTER", "WATER_R_630": "WATER",
              "MN9_LEFT": "MN9"}
    out = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            name = getattr(node.targets[0], "id", None)
            if name in wanted:
                out[wanted[name]] = ast.literal_eval(node.value)
    assert out["MN9"] == MN9
    assert {k: len(out[k]) for k in GROUP_ORDER} == {"SUGAR": 21, "WATER": 18, "BITTER": 21}
    return out


def free_ram_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 1e9


def wait_for_ram(min_gb=1.5, poll_s=20, log=print):
    while True:
        f = free_ram_gb()
        if f >= min_gb:
            return f
        log(f"  waiting for RAM: {f:.2f} GB free (< {min_gb} GB)")
        time.sleep(poll_s)


def excite_for(cond, ids, present=None):
    """{root_id: rate} for a condition, limited to neurons in ``present``."""
    out = {}
    for grp in GROUP_ORDER:
        if grp in CONDITIONS[cond]:
            for rid in ids[grp]:
                if present is None or int(rid) in present:
                    out[int(rid)] = CONDITIONS[cond][grp]
    return out


def mn9_per_trial(res, mn9_idx, n_trials):
    sel = res.neuron == mn9_idx
    return np.bincount(res.trial[sel], minlength=n_trials).astype(float) / (res.duration_ms * 1e-3)


def run_conditions(brain, ids, seed, n_trials, params=None, conds=None, counts=False):
    """MN9 rate per trial for every condition. With ``counts=True`` also the
    total spike count of every neuron (over all trials) per condition."""
    present = set(int(r) for r in brain.root_ids)
    mn9_idx = int(brain.index_of([MN9])[0]) if MN9 in present else -1
    out, cnt = {}, {}
    for cond in (conds or CONDITIONS):
        exc = excite_for(cond, ids, present)
        if not exc or mn9_idx < 0:
            out[cond] = np.zeros(n_trials)
            if counts:
                cnt[cond] = np.zeros(brain.n_neurons, np.int64)
            continue
        res = brain.run(excite=exc, duration_ms=1000.0, n_trials=n_trials, seed=seed,
                        params=params)
        out[cond] = mn9_per_trial(res, mn9_idx, n_trials)
        if counts:
            cnt[cond] = res.spike_counts
        del res
    return (out, cnt) if counts else out


def means(per_trial):
    return {k: float(np.mean(v)) for k, v in per_trial.items()}


def check_rule(circ, whole, tol, bitter_max_hz, brake_frac):
    """Apply the pass rule to two {condition: mean MN9 Hz} dicts.
    Returns (passed, details)."""
    d = {}
    for c in ("S100", "S200"):
        err = (circ[c] - whole[c]) / whole[c] if whole[c] > 0 else np.inf
        d[f"err_{c}"] = err
    d["sugar_ok"] = all(abs(d[f"err_{c}"]) <= tol for c in ("S100", "S200"))
    d["water_ok"] = circ["W100"] < circ["S100"] and circ["W200"] < circ["S200"]
    if bitter_max_hz == 0.0:
        d["bitter_ok"] = circ["B100"] == 0.0 and circ["B200"] == 0.0
    else:
        d["bitter_ok"] = circ["B100"] < bitter_max_hz and circ["B200"] < bitter_max_hz
    drop_w = whole["S100"] - whole["S100+B100"]
    drop_c = circ["S100"] - circ["S100+B100"]
    d["brake_ratio"] = drop_c / drop_w if drop_w > 0 else np.nan
    d["brake_ok"] = drop_c >= brake_frac * drop_w
    d["max_sugar_err"] = max(abs(d["err_S100"]), abs(d["err_S200"]))
    passed = d["sugar_ok"] and d["water_ok"] and d["bitter_ok"] and d["brake_ok"]
    return bool(passed), d


def labels():
    import pandas as pd
    df = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                         columns=["root_id", "super_class", "cell_class", "cell_type",
                                  "hemibrain_type", "side", "top_nt"])
    for c in df.columns:
        if c != "root_id":
            df[c] = df[c].astype(object).where(df[c].notna(), "").astype(str)
    return df.set_index("root_id")

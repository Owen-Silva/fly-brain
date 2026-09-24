"""Shared helpers for the robust (hardware-ready) circuit lane (PRELIMINARY).

Reuses the minimal-circuit lane's code (common.py, circuit.py) by import.

Plain English
-------------
* ``VARIANTS`` are the four versions of a circuit the rule tests: normal
  weights, weights -20%, weights +20%, and 8-bit weights.
* ``variant_brain()`` builds a standalone circuit in one of those versions.
* ``RobustRule.score()`` runs a circuit through every version and applies the
  fixed rule (docs/robust-circuit.md section 1), optionally stopping at the
  first failed check (used by the search to save time).
"""

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MC = ROOT / "experiments" / "minimal_circuit"
for p in (str(ROOT), str(MC)):
    if p not in sys.path:
        sys.path.insert(0, p)

from common import (CONDITIONS, FIX, MN9, SEARCH_SEED, SEARCH_TRIALS, VALID_SEEDS,  # noqa: E402
                    VALID_TRIALS, excite_for, free_ram_gb, mn9_per_trial, paper_ids,
                    wait_for_ram)

RES = HERE / "results"
RAW = RES / "raw"
RES.mkdir(exist_ok=True)
RAW.mkdir(exist_ok=True)
MC_RES = MC / "results"
MC_RAW = MC_RES / "raw"

# The fixed rule and the stricter search version. Water is reported, not required.
RULE = dict(tol=0.10, bitter_max_hz=0.5, brake_frac=0.5)
SEARCH_RULE = dict(tol=0.075, bitter_max_hz=0.0, brake_frac=0.6)
RULE_CONDS = ("S100", "S200", "S100+B100", "B100", "B200")   # order = early-exit order
WATER_CONDS = ("W100", "W200")
VARIANTS = ("w-20", "w+20", "int8", "normal")                 # order = early-exit order
W_FACTOR = {"w-20": 0.8, "w+20": 1.2, "int8": 1.0, "normal": 1.0}
INT8_MAX = 127


def whole_key(variant, seed):
    """Key of the whole-brain reference to compare a variant with."""
    if variant in ("w-20", "w+20"):
        return f"seed{seed}_{variant}"
    return f"seed{seed}"


def load_refs():
    """{key|cond: MN9 per trial} from the previous lane plus this lane's new runs."""
    ref = dict(np.load(MC_RAW / "reference_mn9.npz"))
    p = RAW / "reference_pm20.npz"
    if p.exists():
        ref.update(dict(np.load(p)))
    return ref


def quantize(counts, max_int=INT8_MAX):
    """8-bit rescaling: largest |count| -> 127, round to nearest. Returns
    (integer weights, step in synapses per unit)."""
    counts = np.asarray(counts, np.int64)
    mx = int(np.abs(counts).max()) if counts.size else 1
    step = mx / float(max_int)
    q = np.round(counts / step).astype(np.int64)
    return q, step


def variant_brain(root_ids, pre, post, counts, variant):
    """Standalone FastBrain for one version of the circuit."""
    from sim.fast_engine import DEFAULT_PARAMS, FastBrain
    w0, f0 = DEFAULT_PARAMS["w_syn"], DEFAULT_PARAMS["f_poi"]
    if variant == "int8":
        q, step = quantize(counts)
        nz = q != 0
        return FastBrain.from_arrays(root_ids, pre[nz], post[nz], q[nz], n_threads=1,
                                     params={"w_syn": w0 * step, "f_poi": f0 / step})
    return FastBrain.from_arrays(root_ids, pre, post, counts, n_threads=1,
                                 params={"w_syn": w0 * W_FACTOR[variant]})


def run_cond(brain, ids, cond, seed, n_trials, counts=False):
    present = set(int(r) for r in brain.root_ids)
    exc = excite_for(cond, ids, present)
    if not exc or MN9 not in present:
        z = np.zeros(n_trials)
        return (z, np.zeros(brain.n_neurons, np.int64)) if counts else z
    mi = int(brain.index_of([MN9])[0])
    res = brain.run(excite=exc, duration_ms=1000.0, n_trials=n_trials, seed=seed)
    per = mn9_per_trial(res, mi, n_trials)
    return (per, res.spike_counts.copy()) if counts else per


def partial_check(c, w, tol, bitter_max_hz, brake_frac):
    """Checks that can be decided from the conditions run so far.
    Returns (ok_so_far, details)."""
    d, ok = {}, True
    for s in ("S100", "S200"):
        if s in c:
            d[f"err_{s}"] = (c[s] - w[s]) / w[s] if w[s] > 0 else np.inf
            ok &= abs(d[f"err_{s}"]) <= tol
    if "S100" in c and "S100+B100" in c:
        dw = w["S100"] - w["S100+B100"]
        dc = c["S100"] - c["S100+B100"]
        d["brake_ratio"] = dc / dw if dw > 0 else np.nan
        ok &= dc >= brake_frac * dw
    for b in ("B100", "B200"):
        if b in c:
            ok &= (c[b] == 0.0) if bitter_max_hz == 0.0 else (c[b] < bitter_max_hz)
    return bool(ok), d


def score(root_ids, pre, post, counts, ids, ref, seed, n_trials, rule, early_exit,
          water=False, trial_slice=None, log=None):
    """Run every version; returns (passed_all, {variant: {...}}, first_fail).
    ``trial_slice`` limits the whole-brain reference to the first n trials."""
    out, first_fail, passed_all = {}, None, True
    for v in VARIANTS:
        wait_for_ram(log=log or print)
        brain = variant_brain(root_ids, pre, post, counts, v)
        key = whole_key(v, seed)
        c, w = {}, {}
        ok = True
        conds = RULE_CONDS + (WATER_CONDS if water and v == "normal" else ())
        for cond in conds:
            c[cond] = float(np.mean(run_cond(brain, ids, cond, seed, n_trials)))
            rk = f"{key}|{cond}"
            if rk in ref:
                w[cond] = float(np.mean(ref[rk][:trial_slice] if trial_slice else ref[rk]))
            if cond in RULE_CONDS:
                ok, d = partial_check(c, w, **rule)
                if not ok and early_exit:
                    break
        ok, d = partial_check(c, w, **rule)
        out[v] = {"pass": ok, "circuit": c, "whole": w, **d}
        if not ok:
            passed_all = False
            if first_fail is None:
                first_fail = v
            if early_exit:
                break
        del brain
    return passed_all, out, first_fail


class Timer:
    def __init__(self):
        self.t0 = time.perf_counter()

    def log(self, msg):
        print(f"[{time.perf_counter() - self.t0:7.1f}s] {msg}", flush=True)

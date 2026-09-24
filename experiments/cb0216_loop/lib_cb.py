"""Shared helpers for the CB0216 loop lane (PRELIMINARY).

Plain English: build the project's default brain (fix "al_ln_literature",
exactly what sim.sign_fixes.build_brain feeds the engine), give some neurons
Poisson input for a while, then switch ALL input off and keep simulating, and
count who is still firing. Nothing in sim/, app/, tests/ or data/ is changed.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sim.fast_engine import FastBrain  # noqa: E402
from sim.sign_fixes import apply_fix, load_reference_arrays, neuron_table  # noqa: E402

RESULTS = HERE / "results"
RESULTS.mkdir(exist_ok=True)
FIX = "al_ln_literature"
PAIR = (720575940633316307, 720575940636552805)   # CB0216 right, left (snapshot 630)
MN9 = (720575940660219265, 720575940645521262)    # MN9 "left", "right" (sim.shiu_model)
DT_MS = 0.1


def free_gb():
    try:
        import psutil
        return psutil.virtual_memory().available / 2**30
    except Exception:  # noqa: BLE001
        import subprocess
        out = subprocess.run(["powershell", "-NoProfile", "-c",
                              "(Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory"],
                             capture_output=True, text=True).stdout.strip()
        return int(out) / 2**20


def wait_for_ram(gb=1.5, max_wait_s=1800):
    t0 = time.time()
    while free_gb() < gb and time.time() - t0 < max_wait_s:
        time.sleep(20)
    return free_gb()


_ARR = {}


def arrays(fix=FIX):
    """(root_ids, pre, post, signed, lab) with ``fix`` applied (cached)."""
    if fix not in _ARR:
        root_ids, pre, post, signed = load_reference_arrays("630")
        lab = _ARR.get("lab")
        if lab is None:
            lab = neuron_table(root_ids)
            _ARR["lab"] = lab
        p2, q2, s2, _ = apply_fix(fix, root_ids, pre, post, signed, lab)
        _ARR[fix] = (root_ids, p2, q2, s2)
    return (*_ARR[fix], _ARR["lab"])


def brain_from(root_ids, pre, post, signed, realism=None):
    wait_for_ram(1.5)
    if realism:
        from sim.realism import RealisticBrain
        return RealisticBrain.from_arrays(root_ids, np.asarray(pre, np.int64),
                                          np.asarray(post, np.int64),
                                          np.asarray(signed, np.int64), n_threads=1,
                                          realism=realism)
    return FastBrain.from_arrays(root_ids, np.asarray(pre, np.int64), np.asarray(post, np.int64),
                                 np.asarray(signed, np.int64), n_threads=1)


def onoff_events(exc_idx, rate_hz, on_ms, total_ms, rng):
    """Poisson kicks on ``exc_idx`` at ``rate_hz`` (scalar or per-neuron array)
    during [0, on_ms); nothing afterwards."""
    n_on = int(round(on_ms / DT_MS))
    n_steps = int(round(total_ms / DT_MS))
    rate = np.broadcast_to(np.asarray(rate_hz, float), (len(exc_idx),))
    steps, neurons = [], []
    for i, r in zip(exc_idx, rate):
        k = rng.binomial(n_on, r * DT_MS * 1e-3)
        if k:
            steps.append(rng.choice(n_on, size=k, replace=False))
            neurons.append(np.full(k, i, np.int64))
    if steps:
        steps, neurons = np.concatenate(steps), np.concatenate(neurons)
    else:
        steps = neurons = np.zeros(0, np.int64)
    return FastBrain._pack_events(steps, neurons, n_steps), n_steps


def run_onoff(brain, exc_idx, rate_hz, on_ms, off_ms, seed, silence=(), events=None,
              params=None, keep_refractory=False):
    """Drive ``exc_idx`` for ``on_ms``, then no input for ``off_ms``.
    The engine gives driven neurons no refractory period (as model.poi does
    for the paper's stimulated sensory neurons); ``keep_refractory=True`` keeps
    the normal 2.2 ms for them (used when driving internal neurons).
    Returns (step, neuron) arrays of all spikes and the wall time."""
    total = on_ms + off_ms
    if events is None:
        rng = np.random.default_rng(np.random.SeedSequence([int(seed), 216]))
        events, n_steps = onoff_events(np.asarray(exc_idx, np.int64), rate_hz, on_ms, total, rng)
    else:
        n_steps = int(round(total / DT_MS))
    p = brain._params_for(params)
    t0 = time.perf_counter()
    rfc_free = np.zeros(0, np.int64) if keep_refractory else np.asarray(exc_idx, np.int64)
    res = brain._run_events([events], rfc_free, silence, n_steps, p, ())
    return res.step.astype(np.int64), res.neuron.astype(np.int64), time.perf_counter() - t0


def window_counts(step, neuron, n, t0_ms, t1_ms):
    m = (step >= t0_ms / DT_MS) & (step < t1_ms / DT_MS)
    return np.bincount(neuron[m], minlength=n)


def pair_rates(step, neuron, idx_pair, t0_ms, t1_ms):
    m = (step >= t0_ms / DT_MS) & (step < t1_ms / DT_MS)
    dur = (t1_ms - t0_ms) / 1000.0
    return [float(((neuron == i) & m).sum() / dur) for i in idx_pair]


def last_spike_ms(step, neuron, i):
    s = step[neuron == i]
    return float(s.max() * DT_MS) if s.size else float("nan")

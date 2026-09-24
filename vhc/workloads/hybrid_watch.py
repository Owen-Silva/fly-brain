"""Workload (d), the hybrid task: an always-on odour watch with an exact log.

The neuromorphic core listens to every sniff (one per second, all day). A detector neuron
fires when the total projection-neuron input is unusually high (threshold = the 99th
percentile of 2,000 background sniffs, fixed before the run); the mushroom-body learner (all
110 odours already learned, workload b) then names the odour. Each detection is one event to
the conventional core, which wakes, appends an exact record (time, odour) and updates exact
per-odour counts, then sleeps.

Stream: 10% of sniffs carry one of the 110 odours (random), 90% are background air.
A day = 86,400 sniffs; a shorter stream is simulated and scaled.
"""
from __future__ import annotations

import numpy as np

from ..cores import conventional, neuromorphic
from ..prices import GPU_IDLE_W, M33_SLEEP_W, X86_IDLE_W, X86_POWER_W
from . import odour as O

DAY_S = 86_400
SNIFF_PERIOD_S = 1.0
ODOUR_FRAC = 0.10


def run(s: O.Setup, readout, n_sniffs=5000, seed=0):
    m = O.mb()
    n_od = s.P.shape[0]
    rng = np.random.default_rng([seed, 21])
    bg = np.zeros((1, s.P.shape[1]))
    Xcal, _ = m.make_trials(bg, 2000, O.T_S, rng, s.spont)
    thr = float(np.quantile(Xcal.sum(1), 0.99))
    truth = np.where(rng.random(n_sniffs) < ODOUR_FRAC, rng.integers(0, n_od, n_sniffs), -1)
    X = np.empty((n_sniffs, s.P.shape[1]), np.float32)
    for k, t in enumerate(truth):   # fresh noisy sniff of the true stimulus
        row = s.P[t] if t >= 0 else bg[0]
        X[k] = rng.poisson((s.spont + row) * O.T_S) / O.T_S - s.spont
    detected = X.sum(1) > thr
    H = m.kc_code(s.W, X[detected], O.K_FRAC)
    named = np.full(n_sniffs, -1)
    named[detected] = readout.predict(H, np.arange(n_od))
    # the conventional core's exact log
    log = [(k * SNIFF_PERIOD_S, int(named[k])) for k in np.flatnonzero(detected)]
    counts = np.bincount([o for _, o in log], minlength=n_od)
    log_exact = bool(np.array_equal(counts, np.bincount(named[detected], minlength=n_od)))
    od = truth >= 0
    res = {
        "threshold": thr,
        "hit_rate": float(np.mean(detected[od])),
        "false_alarm_rate": float(np.mean(detected[~od])),
        "named_correct_given_hit": float(np.mean(named[od & detected] == truth[od & detected])),
        "end_to_end_accuracy": float(np.mean(named == truth)),
        "log_exact": log_exact, "detections_per_sniff": float(detected.mean()),
    }
    Hbg = m.kc_code(s.W, X[:200], O.K_FRAC)
    res["neuro_counts"] = O.neuro_counts(s, X[:200], Hbg, n_od, train=False)
    res["active_per_sniff"] = float((Hbg > 0).sum(1).mean())
    return res


def per_day(res, s: O.Setup, x86_s_per_sniff, version="v1", static="mid"):
    """Energy per day and time per sniff for each design. v1: the neuromorphic chip listens
    all day, so its static (leakage) power runs all day too (ASSUMED: no power-gating between
    sniffs one second apart)."""
    n_od = s.P.shape[0]
    sniffs = DAY_S / SNIFF_PERIOD_S
    det = res["detections_per_sniff"] * sniffs
    log_ops = {"log_write": 1, "select": n_od}
    out = {}
    cores = neuromorphic.n_cores_for(res["neuro_counts"].get("neurons", 0))
    for mode in neuromorphic.MODES:
        nc = neuromorphic.price(res["neuro_counts"], mode, version=version, static=static)
        idle = 0.0
        if version == "v1":
            idle = neuromorphic.static_W(cores, static) * max(DAY_S - sniffs * nc.time_s, 0.0)
        wake = conventional.price(log_ops, "m33", wake=True)
        busy = det * wake.time_s
        e_h = sniffs * nc.energy_J + idle + det * wake.energy_J + (DAY_S - busy) * M33_SLEEP_W.value
        out[f"hybrid ({mode})"] = {"time_s": nc.time_s + res["detections_per_sniff"] * wake.time_s,
                                   "J_per_day": e_h, "log": "exact", "label": "modeled"}
        out[f"neuromorphic only ({mode})"] = {"time_s": nc.time_s, "J_per_day": sniffs * nc.energy_J + idle,
                                              "log": "none (no exact memory)", "label": "modeled"}
    mc = O.m33_cost(s, res["active_per_sniff"], n_od, train=False)
    lw = conventional.price(log_ops, "m33")
    e_m = sniffs * mc.energy_J + det * lw.energy_J + (DAY_S - sniffs * mc.time_s) * M33_SLEEP_W.value
    out["CPU only: M33 (modeled)"] = {"time_s": mc.time_s, "J_per_day": e_m, "log": "exact",
                                      "label": "modeled"}
    e_x = sniffs * x86_s_per_sniff * X86_POWER_W.value + DAY_S * X86_IDLE_W.value
    out["CPU only: laptop (measured time)"] = {"time_s": x86_s_per_sniff, "J_per_day": e_x,
                                               "log": "exact", "label": "measured time; energy modeled"}
    g = O.gpu_cost(s, n_od, train=False)
    e_g = sniffs * g.energy_J + DAY_S * (GPU_IDLE_W.value + X86_IDLE_W.value)
    out["GPU (modeled)"] = {"time_s": g.time_s, "J_per_day": e_g, "log": "exact (host CPU)",
                            "label": "modeled"}
    return out

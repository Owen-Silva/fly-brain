"""v1: calibrate the neuromorphic core's TIMING against real Loihi 2 hardware.

Data (vhc/prices.py, all PUBLISHED, Wang et al. 2025, Sandia, arXiv:2508.16792):
  * sugar experiment, whole FlyWire brain on 12 Loihi 2 chips (1,440 cores): 53.76 ms per
    simulated second with 0.1 ms steps, 12.40 ms with 1 ms steps;
  * background sweep: every neuron spiking on its own at 0.5-40 Hz, at both step sizes
    (14 more points).

v0 priced the sugar run at 9.3 ms (0.1 ms steps; 5.8x too fast) and 0.94 ms (1 ms steps; 13x
too fast). The two ratios differ, so no single fudge factor can fix v0.

v1 timing = v0 timing + two terms:
  A  seconds per time step, whole system: synchronisation beyond Loihi 1's on-chip barrier
     (chip-to-chip handshakes, step management);
  B  seconds per spike, whole system: spike-message traffic (routing each spike to the cores
     and chips that hold its targets).
  T_v1 = T_v0 + steps * A + spikes * B        (spikes include sensor/input spikes)

How it is fitted, keeping held-out checks:
  1. B = slope of wall time against spikes in the 1 ms-step background sweep (7 points; least
     squares on relative error). The sweep's intercept is thrown away: the sweep's on-chip
     random spike generator costs time per step that the sugar run does not have.
  2. A = the sugar run at 0.1 ms steps (ONE point), given B.
  Never used for fitting: the sugar run at 1 ms steps (THE check) and the whole 0.1 ms sweep.
  One-term fits (A only, or B only, from the same sugar 0.1 ms point) are reported too.

Run: .venv\\Scripts\\python.exe -m vhc.neurocal   -> vhc/results/neuro_calibration.json
"""
from __future__ import annotations

import json
from functools import lru_cache

import numpy as np

from .prices import (RESULTS, SANDIA_CONNECTIONS, SANDIA_CORES, SANDIA_NEURONS, SANDIA_SWEEP_HZ,
                     SANDIA_SWEEP_S_DT01, SANDIA_SWEEP_S_DT1, SANDIA_WALL_S_PER_SIM_S_DT01,
                     SANDIA_WALL_S_PER_SIM_S_DT1)

# This project's own whole-brain sugar decision (1 s of 100 Hz sugar input), MEASURED by the
# energy lane: experiments/energy_budget/results/decision_summary.csv, model al_ln_literature,
# decision sugar (40 trials). Sandia's sugar input was 150 Hz, so their run was somewhat busier.
SUGAR = {"neurons": 127400, "spikes": 9748.58, "input_event": 2087.8, "syn_event": 1.48397e6}


def _v0_time(steps, neurons, spikes, syn_event, input_event):
    from .cores import neuromorphic
    c = {"steps": steps, "neurons": neurons, "spikes": spikes, "syn_event": syn_event,
         "input_event": input_event}
    return neuromorphic.price(c, "clocked", n_cores=SANDIA_CORES, version="v0").time_s


def _sweep_counts(rate_hz):
    spikes = SANDIA_NEURONS * rate_hz
    return spikes, spikes * SANDIA_CONNECTIONS / SANDIA_NEURONS


@lru_cache(maxsize=1)
def fit():
    s = SUGAR
    spk_sugar = s["spikes"] + s["input_event"]
    t01, t1 = SANDIA_WALL_S_PER_SIM_S_DT01.value, SANDIA_WALL_S_PER_SIM_S_DT1.value
    v0_01 = _v0_time(10000, s["neurons"], s["spikes"], s["syn_event"], s["input_event"])
    v0_1 = _v0_time(1000, s["neurons"], s["spikes"], s["syn_event"], s["input_event"])

    # step 1: B from the 1 ms sweep (relative least squares, free intercept)
    r = np.array(SANDIA_SWEEP_HZ)
    y1, y01 = np.array(SANDIA_SWEEP_S_DT1), np.array(SANDIA_SWEEP_S_DT01)
    spk = SANDIA_NEURONS * r
    X = np.c_[np.ones_like(r), spk] / y1[:, None]
    intercept, B = np.linalg.lstsq(X, np.ones_like(r), rcond=None)[0]
    # step 2: A from the sugar run at 0.1 ms steps
    A = (t01 - v0_01 - B * spk_sugar) / 10000
    pred1 = v0_1 + 1000 * A + B * spk_sugar

    def sweep_pred(steps):
        out = []
        for rate in r:
            sp, ev = _sweep_counts(rate)
            out.append(_v0_time(steps, SANDIA_NEURONS, sp, ev, 0) + steps * A + sp * B)
        return np.array(out)

    p01, p1 = sweep_pred(10000), sweep_pred(1000)
    # one-term alternatives, each fitted on the same single sugar 0.1 ms point
    A_only = (t01 - v0_01) / 10000
    B_only = (t01 - v0_01) / spk_sugar
    return {
        "model": "T = T_v0 + steps * A + spikes * B",
        "A_s_per_step": float(A), "B_s_per_spike": float(B),
        "fit_data": "B: Sandia background sweep, 1 ms steps (7 points); A: Sandia sugar, 0.1 ms steps (1 point)",
        "sweep_1ms_intercept_discarded_s": float(intercept),
        "v0_sugar_s": {"dt0.1": v0_01, "dt1": v0_1},
        "measured_sugar_s": {"dt0.1": t01, "dt1": t1},
        "v0_ratio_measured_over_model": {"dt0.1": t01 / v0_01, "dt1": t1 / v0_1},
        "check_sugar_dt1": {"predicted_s": float(pred1), "measured_s": t1,
                            "error_pct": float(100 * (pred1 / t1 - 1))},
        "check_sweep_dt0.1_error_pct": [float(x) for x in 100 * (p01 / y01 - 1)],
        "fit_residual_sweep_dt1_error_pct": [float(x) for x in 100 * (p1 / y1 - 1)],
        "sweep_rates_hz": list(SANDIA_SWEEP_HZ),
        "one_term_A_only": {"A_s_per_step": float(A_only),
                            "check_sugar_dt1_error_pct": float(100 * ((v0_1 + 1000 * A_only) / t1 - 1))},
        "one_term_B_only": {"B_s_per_spike": float(B_only),
                            "check_sugar_dt1_error_pct": float(100 * ((v0_1 + B_only * spk_sugar) / t1 - 1))},
        "sugar_counts": dict(SUGAR),
        "label": "FITTED to PUBLISHED Loihi 2 measurements (Sandia); a 12-chip system",
    }


def main():
    f = fit()
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "neuro_calibration.json").write_text(json.dumps(f, indent=1))
    print(f"A = {f['A_s_per_step'] * 1e6:.2f} us per step, B = {f['B_s_per_spike'] * 1e6:.3f} us per spike")
    c = f["check_sugar_dt1"]
    print(f"held-out check, sugar at 1 ms steps: predicted {c['predicted_s'] * 1e3:.2f} ms, "
          f"measured {c['measured_s'] * 1e3:.2f} ms ({c['error_pct']:+.0f}%)")
    print("held-out check, 0.1 ms sweep errors (%):", np.round(f["check_sweep_dt0.1_error_pct"]))
    print("fit residuals, 1 ms sweep (%):", np.round(f["fit_residual_sweep_dt1_error_pct"]))
    print(f"one-term fits miss the check: A only {f['one_term_A_only']['check_sugar_dt1_error_pct']:+.0f}%, "
          f"B only {f['one_term_B_only']['check_sugar_dt1_error_pct']:+.0f}%")


if __name__ == "__main__":
    main()

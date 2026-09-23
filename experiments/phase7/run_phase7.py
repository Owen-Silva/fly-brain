"""Phase 7 upgrades 1-3: re-run the Phase 3 baseline checks with each upgrade.

Plain English
-------------
For every model version ("config") below, and every Phase 3 condition, this
runs 3 independent random seeds x 30 trials x 1 s of the whole fly brain
(snapshot 630) and saves, per seed:
  * how many spikes every neuron fired (summed over the 30 trials),
  * the MN9 spike counts per trial (both sides),
  * the total spike count per trial (to spot "runaway" trials).
Results go to experiments/phase7/results/<config>/<condition>_s<k>.npz and are
skipped if they already exist, so the script can be stopped and restarted.

Usage:  python experiments/phase7/run_phase7.py CONFIG [CONFIG ...]
        python experiments/phase7/run_phase7.py --list
"""

from __future__ import annotations

import ast
import ctypes
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from sim.realism import REALISM_DEFAULTS, RealisticBrain, calibrate_adaptation  # noqa: E402

OUT = ROOT / "experiments" / "phase7" / "results"
N_TRIALS = 30
SEEDS = (0, 1, 2)
NEW_SEEDS = (10, 11, 12)          # for the "baseline with new seeds" noise reference


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

# name: (list of (set, rate Hz), base seed). Base seeds as in Phase 3.
CONDITIONS = {
    "sugar_100Hz": ([("sugar", 100)], 1_000),
    "sugar_200Hz": ([("sugar", 200)], 2_000),
    "water_200Hz": ([("water", 200)], 3_000),
    "bitter_200Hz": ([("bitter", 200)], 4_000),
    "sugar100_bitter120": ([("sugar", 100), ("bitter", 120)], 6_000),
    "sugar200_ir94e200": ([("sugar", 200), ("ir94e", 200)], 7_000),
}


RUNAWAY_CONDITION = "sugar200_ir94e200"


#: Upgrade 2 re-fit: Shiu et al. fitted their one free weight parameter so
#: that sugar GRNs at 100 Hz drive MN9 strongly (paper: 65.7 +/- 3.3 Hz).
#: The conductance model gets its one global weight factor re-fitted to the
#: same number, on a seed used for nothing else. Every other check (sugar
#: 200 Hz, water, bitter, sugar + bitter, runaway) is then an honest test.
FIT_TARGET_HZ = 65.7
FIT_SEED = 900
FIT_TOL_HZ = 2.0            # the paper's own trial-to-trial sd is 3.3 Hz
FIT_TRIALS = 15
#: A run whose median trial has more than 5x the baseline's spikes for sugar
#: 100 Hz (9,620) has "ignited" (the whole network is firing); a weight
#: factor that does that is not a valid fit even if MN9 happens to hit 65.7.
IGNITION_SPIKES = 5 * 9620


def fit_cond_scale(brain, realism):
    """Find cond_weight_scale so that sugar 100 Hz -> MN9 contra = 65.7 Hz
    (seed 900, used for nothing else). MN9 does not rise forever with the
    weight: too strong and the whole network ignites and MN9 is shut down
    (factor 4 gave 16 Hz). So: walk up from the last factor known to be too
    weak in steps of x1.19, stop at the first factor that reaches the target
    (then bisect), and give up if MN9 starts falling or the network ignites
    before the target is reached. Every evaluation is saved to
    results/U2_fit.json."""
    cache = OUT / "U2_fit.json"
    key = json.dumps({k: v for k, v in realism.items() if k != "cond_weight_scale"},
                     sort_keys=True)
    data = json.loads(cache.read_text()) if cache.exists() else {}
    entry = data.get(key, {"trajectory": []})
    if entry.get("scale") is not None:
        return entry["scale"]
    excite = {int(i): 100.0 for i in SETS["sugar"]}
    known = {round(t[0], 6): t for t in entry["trajectory"]}

    def ev(k):
        """(MN9 Hz, median spikes per trial or None if not recorded)."""
        if round(k, 6) in known:
            t = known[round(k, 6)]
            return t[1], (t[3] if len(t) > 3 else None)
        brain.set_realism(**REALISM_OFF)
        brain.set_realism(**{**realism, "cond_weight_scale": k})
        wait_for_ram()
        t0 = time.perf_counter()
        res = brain.run(excite=excite, duration_ms=1000.0, n_trials=FIT_TRIALS, seed=FIT_SEED)
        r = res.rate(MN9_CONTRA)
        med = float(np.median(np.bincount(res.trial, minlength=FIT_TRIALS)))
        t = [k, r, FIT_TRIALS, med]
        known[round(k, 6)] = t
        entry["trajectory"].append(t)
        data[key] = entry
        cache.write_text(json.dumps(data, indent=1))
        print(f"  fit: cond_weight_scale {k:.4f} -> MN9 contra {r:.1f} Hz, median spikes/trial "
              f"{med:.0f} ({time.perf_counter() - t0:.0f} s)", flush=True)
        return r, med

    step = 2 ** 0.25
    # start from the largest factor already known to be too weak and not ignited
    below = [t for t in entry["trajectory"] if t[1] < FIT_TARGET_HZ
             and (len(t) < 4 or t[3] < IGNITION_SPIKES)]
    lo = 1.0
    r_lo, _ = ev(lo)
    for t in sorted(below):
        if t[0] > lo and t[1] > r_lo:        # still on the rising branch
            lo, r_lo = t[0], t[1]
    hi = None
    k = lo * step
    status = "target not reached before MN9 fell or the network ignited"
    while k < 8:
        r, med = ev(k)
        if med is not None and med > IGNITION_SPIKES:
            break
        if r >= FIT_TARGET_HZ:
            hi = k
            break
        if r < r_lo:
            break
        lo, r_lo = k, r
        k *= step
    if hi is not None:
        status = "fitted"
        for _ in range(6):
            mid = math.sqrt(lo * hi)
            r, med = ev(mid)
            if abs(r - FIT_TARGET_HZ) < FIT_TOL_HZ:
                break
            if r < FIT_TARGET_HZ:
                lo = mid
            else:
                hi = mid
    ok = [t for t in entry["trajectory"] if len(t) < 4 or t[3] < IGNITION_SPIKES]
    best = min(ok, key=lambda t: abs(t[1] - FIT_TARGET_HZ))
    entry.update(scale=best[0], mn9_at_scale=best[1], status=status,
                 target_hz=FIT_TARGET_HZ, fit_seed=FIT_SEED,
                 trajectory_columns=["scale", "mn9_hz", "trials", "median_spikes_per_trial"])
    data[key] = entry
    cache.write_text(json.dumps(data, indent=1))
    print(f"  fit {status}: cond_weight_scale = {best[0]:.4f} (MN9 {best[1]:.1f} Hz)", flush=True)
    return best[0]


#: Full reset before every model version: set_realism() only changes the
#: options it is given, so every option (not just the three switches) must be
#: put back to its default, or one version's settings leak into the next.
REALISM_OFF = dict(REALISM_DEFAULTS)

#: Parameter variants (sensitivity checks) get a shorter run: 1 seed x 30
#: trials of the five Phase 3 conditions (the machine is shared; a full run
#: of every variant would take many hours).
QUICK = dict(seeds=(0,), conditions=("sugar_100Hz", "sugar_200Hz", "water_200Hz",
                                     "bitter_200Hz", "sugar100_bitter120"),
             runaway_extra=False)


def _configs():
    inc100 = calibrate_adaptation(100.0)
    return {
        # the untouched baseline engine (sim/fast_engine.py's own loop)
        "baseline": dict(engine="baseline"),
        "baseline_newseeds": dict(engine="baseline", seeds=NEW_SEEDS, runaway_extra=False),
        # upgrade 1: distance-dependent delays
        "U1_delays": dict(realism=dict(delays=True, velocity_m_per_s=0.20)),
        "U1_delays_slow0.129": dict(realism=dict(delays=True, velocity_m_per_s=0.129), **QUICK),
        "U1_delays_fast2.07": dict(realism=dict(delays=True, velocity_m_per_s=2.07), **QUICK),
        "U1_delays_soma": dict(realism=dict(delays=True, velocity_m_per_s=0.20, distance="soma"),
                               **QUICK),
        # upgrade 2: conductance-based synapses (alone, then on top of upgrade 1)
        "U2_cond": dict(realism=dict(conductance=True, E_inh_mV=-60.0)),
        "U2_cond_Ei-70": dict(realism=dict(conductance=True, E_inh_mV=-70.0), **QUICK),
        "U12": dict(realism=dict(delays=True, velocity_m_per_s=0.20, conductance=True)),
        # diagnosis: which half of upgrade 2 weakens sugar -> MN9? A reversal
        # potential a million mV away makes that synapse type act exactly
        # like the baseline's fixed push (its driving force never changes).
        "U2_diag_exc_only": dict(realism=dict(conductance=True, E_inh_mV=-1e6), seeds=(0,),
                                 conditions=("sugar_100Hz", "sugar100_bitter120"),
                                 runaway_extra=False),
        "U2_diag_inh_only": dict(realism=dict(conductance=True, E_exc_mV=1e6), seeds=(0,),
                                 conditions=("sugar_100Hz", "sugar100_bitter120"),
                                 runaway_extra=False),
        # upgrade 2 with its one weight factor re-fitted (see fit_cond_scale)
        "U2_cond_tuned": dict(realism=dict(conductance=True, E_inh_mV=-60.0), fit=True,
                              runaway_extra=False),
        # (cumulative versions: 1 seed x 30 trials of every condition; each
        # upgrade was already checked on its own with 3 seeds, and the
        # conductance model runs ~10x slower on this shared machine)
        "U12_tuned": dict(realism=dict(delays=True, velocity_m_per_s=0.20, conductance=True),
                          fit=True, fit_realism=dict(conductance=True, E_inh_mV=-60.0),
                          seeds=(0,), runaway_extra=False),
        # upgrade 3: adaptation (alone, then on top of upgrades 1+2)
        "U3_adapt": dict(realism=dict(adaptation=True, tau_adapt_ms=100.0, adapt_mV=inc100)),
        "U3_adapt_half": dict(realism=dict(adaptation=True, tau_adapt_ms=100.0,
                                           adapt_mV=inc100 / 2), **QUICK),
        "U3_adapt_tau300": dict(realism=dict(adaptation=True, tau_adapt_ms=300.0,
                                             adapt_mV=calibrate_adaptation(300.0)), **QUICK),
        # does weaker or slower adaptation still stop the runaway? (150 trials each)
        "U3_adapt_half_RW": dict(realism=dict(adaptation=True, tau_adapt_ms=100.0,
                                              adapt_mV=inc100 / 2),
                                 conditions=(RUNAWAY_CONDITION,)),
        "U3_adapt_tau300_RW": dict(realism=dict(adaptation=True, tau_adapt_ms=300.0,
                                                adapt_mV=calibrate_adaptation(300.0)),
                                   conditions=(RUNAWAY_CONDITION,)),
        # upgrade 3 on top of the last VALIDATED stack (upgrade 1); upgrade 2
        # did not pass its checks, so it is not stacked (see docs/phase7-realism.md)
        "U13": dict(realism=dict(delays=True, velocity_m_per_s=0.20, adaptation=True,
                                 tau_adapt_ms=100.0, adapt_mV=inc100)),
        "U123": dict(realism=dict(delays=True, velocity_m_per_s=0.20, conductance=True,
                                  adaptation=True, tau_adapt_ms=100.0, adapt_mV=inc100),
                     fit=True, fit_realism=dict(conductance=True, E_inh_mV=-60.0),
                     seeds=(0,), runaway_extra=False),
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


def run_config(brain, name, cfg):
    d = OUT / name
    d.mkdir(parents=True, exist_ok=True)
    realism = dict(cfg.get("realism", {}))
    if cfg.get("fit"):
        realism["cond_weight_scale"] = fit_cond_scale(brain, cfg.get("fit_realism", realism))
    brain.set_realism(**REALISM_OFF)
    if cfg.get("engine") != "baseline":
        brain.set_realism(**realism)
    meta = {"config": name, "engine": cfg.get("engine", "realism"),
            "realism": brain.describe() if cfg.get("engine") != "baseline" else "baseline engine",
            "n_trials_per_seed": N_TRIALS}
    (d / "config.json").write_text(json.dumps(meta, indent=1, default=float))
    print(f"=== {name}: {meta['realism']}", flush=True)
    seeds = cfg.get("seeds", SEEDS)
    mn9_idx = brain.index_of([MN9_CONTRA, MN9_IPSI])
    for cond, (inputs, base_seed) in CONDITIONS.items():
        excite = {}
        for s, r in inputs:
            for i in SETS[s]:
                excite[int(i)] = float(r)
        if cond not in cfg.get("conditions", CONDITIONS):
            continue
        cond_seeds = tuple(seeds)
        if cond == RUNAWAY_CONDITION and cfg.get("runaway_extra", True):
            # runaway is rare (~4% of trials in Phase 6), so this condition gets
            # 2 extra seeds: 150 trials per model version
            cond_seeds = cond_seeds + (max(seeds) + 1, max(seeds) + 2)
        for k, sd in enumerate(cond_seeds):
            f = d / f"{cond}_s{k}.npz"
            if f.exists():
                continue
            wait_for_ram()
            runner = brain.run_baseline if cfg.get("engine") == "baseline" else brain.run
            t0 = time.perf_counter()
            res = runner(excite=excite, duration_ms=1000.0, n_trials=N_TRIALS, seed=base_seed + sd)
            counts = np.bincount(res.neuron, minlength=brain.n_neurons)
            nz = np.flatnonzero(counts)
            per_trial_total = np.bincount(res.trial, minlength=N_TRIALS)
            mn9 = np.zeros((2, N_TRIALS), np.int64)
            for r_, idx in enumerate(mn9_idx):
                m = res.neuron == idx
                mn9[r_] = np.bincount(res.trial[m], minlength=N_TRIALS)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz].astype(np.int64),
                                per_trial_total=per_trial_total, mn9=mn9,
                                seed=base_seed + sd, wall_s=time.perf_counter() - t0,
                                neurons_reached=np.array(res.neurons_reached))
            print(f"  {cond} seed {base_seed + sd}: MN9 contra {mn9[0].mean():.1f} Hz, "
                  f"ipsi {mn9[1].mean():.1f} Hz, spikes/trial median {np.median(per_trial_total):.0f}, "
                  f"max {per_trial_total.max()}, {time.perf_counter() - t0:.1f} s", flush=True)
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
    brain = RealisticBrain(snapshot="630", n_threads=2)
    for a in argv:
        run_config(brain, a, configs[a])


if __name__ == "__main__":
    main(sys.argv[1:])

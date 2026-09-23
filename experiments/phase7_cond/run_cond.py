"""Phase 7 upgrade 2 (conductance-based synapses) on top of the sign fix.

Plain English
-------------
The brain is built once with the validated sign fix "al_ln_literature"
(docs/phase7-neurotransmitter-audit.md) on the realistic engine
(sim/realism.py). Each "config" below is a set of realism switches; the same
brain object is re-used, and every config starts again from the full default
switches (so no setting leaks from one config to the next).

For each config and each condition it runs 3 seeds x 30 one-second trials
(the same seeds as Phase 3/6/7 and the sign-fix lane, so trial k of seed s
gets exactly the same random taste/smell input in every model) and saves,
after every 10 trials:
  * results/trials.csv: one row per trial (MN9 rate, total spikes, runaway =
    more than 1,500 different neurons firing in some 10 ms slice, the Phase 6
    definition, ...);
  * results/counts/<config>__<condition>__s<k>.npz: spikes per neuron summed
    over the 30 trials (for the neuron-by-neuron comparison).
So the run can be stopped and restarted without losing work.

The comparison model ("fix only", the paper's current-based synapses with the
sign fix) is NOT re-run: its trials and counts are read from
experiments/phase7_signs/results (same seeds, same inputs).

Usage:
  run_cond.py run CONFIG [CONDITION ...] [--seeds 0,1,2]
  run_cond.py fit CONFIG_JSON N_TRIALS         (one point of the calibration)
  run_cond.py volley CONFIG                     (one-spike triggers)
  run_cond.py --list
"""

from __future__ import annotations

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))

import common as C  # noqa: E402  (sign-fix lane helpers; read-only use)
from sim import realism as R  # noqa: E402
from sim import sign_fixes as S  # noqa: E402

FIX = "al_ln_literature"
RES = HERE / "results"
CNT = RES / "counts"
CNT.mkdir(parents=True, exist_ok=True)
TRIALS_CSV = RES / "trials.csv"
FIT_CSV = RES / "fit.csv"
VOLLEY_CSV = RES / "volleys.csv"
N_TRIALS, CHUNK = 30, 10

#: Calibration target: Shiu et al. 2024, sugar 100 Hz -> MN9 65.7 Hz. The fit
#: uses seed 900, used for nothing else (as in Phase 7).
FIT_SEED = 900
FIT_TARGET_HZ = 65.7

COND = dict(conductance=True, E_exc_mV=0.0)
CONFIGS = {
    # Question 1: the Phase 7 retune (one global factor 2.0) on the fixed brain.
    "g2": dict(COND, E_inh_mV=-60.0, cond_weight_scale=2.0),
    # drop-in (rest-matched, no retune) on the fixed brain, for reference
    "g1": dict(COND, E_inh_mV=-60.0, cond_weight_scale=1.0),
}
EXTRA = RES / "configs.json"          # configs added later (step 2), kept on disk
if EXTRA.exists():
    CONFIGS.update(json.loads(EXTRA.read_text()))


def build():
    C.wait_for_ram()
    t0 = time.perf_counter()
    rid, _, _, _ = S.load_reference_arrays()
    lab = S.neuron_table(rid)
    brain = R.build_realistic_brain(FIX, n_threads=2, lab=lab)
    gc.collect()
    print(f"built {brain.snapshot} ({brain.n_neurons} neurons) in "
          f"{time.perf_counter() - t0:.0f} s", flush=True)
    return brain, lab


def configure(brain, cfg):
    brain.realism = dict(R.REALISM_DEFAULTS)     # start clean every time
    brain.set_realism(**cfg)
    brain._describe_key = None


def append_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def done_trials():
    if not TRIALS_CSV.exists():
        return set()
    d = pd.read_csv(TRIALS_CSV, usecols=["config", "condition", "seed_index", "trial"])
    return set(zip(d.config, d.condition, d.seed_index, d.trial))


def run(name, conds, seeds):
    brain, lab = build()
    configure(brain, CONFIGS[name])
    print(f"=== {name}: {brain.describe()}", flush=True)
    rd = C.Readout(brain, lab)
    sets = C.input_sets(lab)
    done = done_trials()
    for cond in conds:
        base = C.CONDITIONS[cond][1]
        excite = C.excite_for(cond, sets)
        for k in seeds:
            f = CNT / f"{name}__{cond}__s{k}.npz"
            if f.exists():
                continue
            counts = np.zeros(brain.n_neurons, np.int64)
            ts = time.perf_counter()
            for a in range(0, N_TRIALS, CHUNK):
                part = CNT / f"_part_{name}__{cond}__s{k}__{a}.npy"
                if all((name, cond, k, t) in done for t in range(a, a + CHUNK)) and part.exists():
                    counts += np.load(part)
                    continue
                C.wait_for_ram()
                res = C.run_chunk(brain, excite, base + k, a, a + CHUNK)
                meta = dict(config=name, condition=cond, seed_index=k, seed=base + k, trial0=a)
                rows, cnt = C.trial_rows(res, rd, meta)
                del res
                np.save(part, cnt)
                append_csv(TRIALS_CSV, rows)
                counts += cnt
            nz = np.flatnonzero(counts)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz],
                                n_trials=N_TRIALS)
            for a in range(0, N_TRIALS, CHUNK):
                (CNT / f"_part_{name}__{cond}__s{k}__{a}.npy").unlink(missing_ok=True)
            d = pd.read_csv(TRIALS_CSV)
            d = d[(d.config == name) & (d.condition == cond) & (d.seed_index == k)]
            print(f"  {cond} s{k}: MN9 {d.mn9_hz.mean():.2f} Hz, runaway "
                  f"{int(d.runaway.sum())}/{len(d)}, spikes/trial median "
                  f"{d.total_spikes.median():.0f} max {d.total_spikes.max()} "
                  f"({time.perf_counter() - ts:.0f} s)", flush=True)
    print("finished", flush=True)


def fit_points(points, n_trials):
    """Each point: dict of realism settings. Runs sugar 100 Hz, seed 900,
    n_trials, and appends MN9 / activity to results/fit.csv."""
    brain, lab = build()
    rd = C.Readout(brain, lab)
    sets = C.input_sets(lab)
    excite = C.excite_for("sugar_100Hz", sets)
    for pt in points:
        cfg = dict(COND, **pt)
        configure(brain, cfg)
        C.wait_for_ram()
        ts = time.perf_counter()
        res = C.run_chunk(brain, excite, FIT_SEED, 0, n_trials)
        rows, _ = C.trial_rows(res, rd, dict(config="fit"))
        del res
        d = pd.DataFrame(rows)
        r = brain.realism
        out = dict(conductance=bool(r["conductance"]),
                   cond_weight_scale=float(r["cond_weight_scale"]),
                   cond_exc_scale=float(r["cond_exc_scale"]),
                   cond_inh_scale=float(r["cond_inh_scale"]),
                   E_inh_mV=float(r["E_inh_mV"]), n_trials=n_trials, fit_seed=FIT_SEED,
                   mn9_hz=d.mn9_hz.mean(), mn9_sem=d.mn9_hz.std(ddof=1) / np.sqrt(len(d)),
                   mn9_ipsi_hz=d.mn9_ipsi_hz.mean(),
                   median_spikes=d.total_spikes.median(), max_spikes=d.total_spikes.max(),
                   runaways=int(d.runaway.sum()), wall_s=time.perf_counter() - ts)
        append_csv(FIT_CSV, [out])
        print("  fit " + ", ".join(f"{k}={v:.4g}" if isinstance(v, float) else f"{k}={v}"
                                   for k, v in out.items()), flush=True)
    print("finished", flush=True)


def volley(name):
    """One-spike triggers (as the sign-fix lane): 10 DM1 smell neurons, the 44
    eLNs, all antennal-lobe projection neurons fire once; one 1 s run each."""
    brain, lab = build()
    configure(brain, CONFIGS[name])
    rd = C.Readout(brain, lab)
    sets = C.input_sets(lab)
    eln_ids = lab.root_id.to_numpy()[S.eln_mask(lab)]
    pn_ids = lab.root_id.to_numpy()[lab.cell_class.to_numpy() == "ALPN"]
    for trig_name, trig in (("10 DM1 ORNs fire once", sets["dm1"][:10]),
                            ("44 eLNs fire once", eln_ids),
                            (f"all {pn_ids.size} AL projection neurons fire once", pn_ids)):
        res = C.run_volley(brain, trig)
        rows, _ = C.trial_rows(res, rd, dict(config=name, trigger=trig_name))
        append_csv(VOLLEY_CSV, rows)
        print(f"  volley {trig_name}: {rows[0]['total_spikes']} spikes, "
              f"runaway={rows[0]['runaway']}", flush=True)
    print("finished", flush=True)


def main(argv):
    if not argv or argv[0] == "--list":
        print(json.dumps(CONFIGS, indent=1))
        print("conditions:", list(C.CONDITIONS))
        return
    seeds = (0, 1, 2)
    if "--seeds" in argv:
        i = argv.index("--seeds")
        seeds = tuple(int(x) for x in argv[i + 1].split(","))
        argv = argv[:i] + argv[i + 2:]
    if argv[0] == "run":
        conds = argv[2:] or list(C.CONDITIONS)
        run(argv[1], conds, seeds)
    elif argv[0] == "fit":
        src = Path(argv[1])
        pts = json.loads(src.read_text() if src.suffix == ".json" and src.exists() else argv[1])
        fit_points(pts if isinstance(pts, list) else [pts], int(argv[2]))
    elif argv[0] == "volley":
        volley(argv[1])
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])

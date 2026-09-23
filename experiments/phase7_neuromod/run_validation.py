"""Validate each neuromodulator fix alone against al_ln_literature (Phase 7 item 5).

Plain English
-------------
For each model version this runs, 3 seeds x 30 one-second trials each (the same seeds and
trials as experiments/phase7_signs, so results line up trial for trial):

* the Phase 3 taste checks: sugar 100 / 200 Hz, water 200 Hz, bitter 200 Hz alone,
  sugar 100 + bitter 120 Hz (read-out: MN9, the feeding motor neuron);
* runaway rate for Ir94e 200 Hz and for DM1 smell input at 150 Hz;
* how many Kenyon cells fire under DM1 smell input (sparseness).

"al_ln_literature" itself is re-run for seed 0, trials 0-9 of every condition only, as an
identity check against the numbers already in experiments/phase7_signs/results/trials.csv
(same code path, so they must match exactly); the full al_ln_literature numbers are read
from that file.

One brain in memory at a time; results are appended every 10 trials and the run resumes
where it stopped.
Usage: run_validation.py [config ...]   (default: all four CONFIGS)
Outputs: results/trials.csv, results/counts/<config>__<condition>__s<k>.npz,
results/validation_reports.json.
"""

import gc
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))
import common as C  # noqa: E402  (phase7_signs helpers, used read-only)
from sim import sign_fixes as S  # noqa: E402

OUT = HERE / "results"
CNT = OUT / "counts"
CNT.mkdir(parents=True, exist_ok=True)
TRIALS_CSV = OUT / "trials.csv"
N_TRIALS, CHUNK, SEEDS = 30, 10, (0, 1, 2)
CONDS = ["sugar_100Hz", "sugar_200Hz", "water_200Hz", "bitter_200Hz", "sugar100_bitter120",
         "ir94e_200Hz", "dm1_both_150Hz"]
CONFIGS = {
    "al_ln_check": dict(fix="al_ln_literature", seeds=(0,), n_trials=10),
    "da_modulatory": dict(fix="al_ln_literature+da_modulatory"),
    "da_5ht_modulatory": dict(fix="al_ln_literature+da_5ht_modulatory"),
    # added after the first two failed the water check (prediction-only SEZ "dopamine" cells)
    "da_5ht_literature": dict(fix="al_ln_literature+da_5ht_literature"),
}


def append_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, mode="a", header=not path.exists(), index=False)


def done_trials():
    if not TRIALS_CSV.exists():
        return set()
    d = pd.read_csv(TRIALS_CSV, usecols=["config", "condition", "seed_index", "trial"])
    return set(zip(d.config, d.condition, d.seed_index, d.trial))


def run_config(name, cfg, lab, sets, reports):
    C.wait_for_ram()
    t0 = time.perf_counter()
    brain, rep = S.build_brain(cfg["fix"], n_threads=2, return_report=True, lab=lab)
    reports[name] = dict(fix=cfg["fix"], summary=rep.summary(), **rep.details)
    (OUT / "validation_reports.json").write_text(json.dumps(reports, indent=1))
    print(f"=== {name}: {rep.summary()} (built in {time.perf_counter() - t0:.0f} s)", flush=True)
    rd = C.Readout(brain, lab)
    done = done_trials()
    n_trials = cfg.get("n_trials", N_TRIALS)
    for cond in CONDS:
        base = C.CONDITIONS[cond][1]
        excite = C.excite_for(cond, sets)
        for k in cfg.get("seeds", SEEDS):
            f = CNT / f"{name}__{cond}__s{k}.npz"
            if f.exists():
                continue
            counts = np.zeros(brain.n_neurons, np.int64)
            ts = time.perf_counter()
            for a in range(0, n_trials, CHUNK):
                part = CNT / f"_part_{name}__{cond}__s{k}__{a}.npy"
                if all((name, cond, k, t) in done for t in range(a, a + CHUNK)):
                    counts += np.load(part)
                    continue
                C.wait_for_ram()
                res = C.run_chunk(brain, excite, base + k, a, a + CHUNK)
                meta = dict(config=name, fix=cfg["fix"], condition=cond, seed_index=k,
                            seed=base + k, trial0=a)
                rows, cnt = C.trial_rows(res, rd, meta)
                del res
                np.save(part, cnt)
                append_csv(TRIALS_CSV, rows)
                counts += cnt
            nz = np.flatnonzero(counts)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz],
                                n_trials=n_trials)
            for a in range(0, n_trials, CHUNK):
                (CNT / f"_part_{name}__{cond}__s{k}__{a}.npy").unlink(missing_ok=True)
            d = pd.read_csv(TRIALS_CSV)
            d = d[(d.config == name) & (d.condition == cond) & (d.seed_index == k)]
            print(f"  {cond} s{k}: MN9 {d.mn9_hz.mean():.2f} Hz, runaway {int(d.runaway.sum())}/"
                  f"{len(d)}, KC active/trial {d.kc_active.mean():.0f}, spikes/trial "
                  f"{d.total_spikes.mean():.0f} ({time.perf_counter() - ts:.0f} s)", flush=True)
    del brain
    gc.collect()


def main(names):
    rid, _, _, _ = S.load_reference_arrays()
    lab = S.neuron_table(rid)
    sets = C.input_sets(lab)
    rp = OUT / "validation_reports.json"
    reports = json.loads(rp.read_text()) if rp.exists() else {}
    for name in names:
        run_config(name, CONFIGS[name], lab, sets, reports)
    print("VALIDATION_DONE", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(CONFIGS))

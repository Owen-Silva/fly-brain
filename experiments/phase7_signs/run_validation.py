"""Validate each sign fix alone against the baseline (Phase 7 upgrade 5).

Plain English
-------------
For each model version ("config") this runs every check below, 3 seeds x 30
one-second trials each, and saves the result after every 10 trials, so the
run can be stopped and restarted without losing work:

* Phase 3 taste results: sugar 100 / 200 Hz, water 200 Hz, bitter 200 Hz,
  sugar 100 + bitter 120 Hz (read-out: MN9, the feeding motor neuron);
* runaway rate for Ir94e 200 Hz and for DM1 smell input at 150 Hz;
* how many Kenyon cells (learning centre) fire under DM1 smell input;
* left-only versus right-only DM1 smell, read out at the steering
  descending neurons (DNa02, DNa01, ... from docs/phase5-olfaction.md);
* three "volley" triggers: 10 DM1 smell neurons fire once; the 44 eLNs fire
  once; all 685 antennal-lobe projection neurons fire once (a brute-force kick).

Only one brain is in memory at a time (configs run one after another).
Usage:  run_validation.py [stage ...]    stages: main, params, ln53 (default: all)
Outputs: results/trials.csv (one row per trial), results/volleys.csv,
results/counts/<config>__<condition>__s<k>.npz (spikes per neuron, summed over
the 30 trials), results/fix_reports.json.
"""

import gc
import json
import sys
import time

import numpy as np
import pandas as pd

import common as C
from sim import sign_fixes as S

N_TRIALS, CHUNK, SEEDS = 30, 10, (0, 1, 2)
OUT = C.RESULTS
CNT = OUT / "counts"
CNT.mkdir(exist_ok=True)
TRIALS_CSV = OUT / "trials.csv"
VOLLEY_CSV = OUT / "volleys.csv"
W0 = 0.275

ALL = list(C.CONDITIONS)
PARAM_CONDS = ["sugar_100Hz", "ir94e_200Hz", "dm1_both_150Hz"]
STAGES = {
    "main": [dict(name="none", fix="none"),
             dict(name="al_ln_literature", fix="al_ln_literature"),
             dict(name="eln_electrical", fix="eln_electrical"),
             dict(name="known_nt", fix="known_nt")],
    "params": [dict(name=f"al_ln_literature_wsyn{f}", fix="al_ln_literature",
                    params={"w_syn": W0 * f}, conds=PARAM_CONDS, seeds=(0,))
               for f in (0.9, 1.1, 1.2)],
    "ln53": [dict(name="ln53_inhibitory", fix="ln53_inhibitory")],
}


def append_csv(path, rows):
    df = pd.DataFrame(rows)
    df.to_csv(path, mode="a", header=not path.exists(), index=False)


def done_chunks():
    if not TRIALS_CSV.exists():
        return set()
    d = pd.read_csv(TRIALS_CSV, usecols=["config", "condition", "seed_index", "trial"])
    return set(zip(d.config, d.condition, d.seed_index, d.trial))


def run_config(cfg, lab, sets, reports):
    t0 = time.perf_counter()
    C.wait_for_ram()
    brain, rep = S.build_brain(cfg["fix"], n_threads=2, return_report=True, lab=lab)
    reports[cfg["name"]] = dict(summary=rep.summary(), removed_connections=rep.removed_connections,
                                removed_synapses=rep.removed_synapses,
                                flipped_neurons=len(rep.flipped_neurons),
                                flipped_connections=rep.flipped_connections,
                                to_inhibitory=rep.to_inhibitory, to_excitatory=rep.to_excitatory,
                                params=cfg.get("params"))
    (OUT / "fix_reports.json").write_text(json.dumps(reports, indent=1))
    print(f"=== {cfg['name']}: {rep.summary()} (built in {time.perf_counter() - t0:.0f} s)",
          flush=True)
    rd = C.Readout(brain, lab)
    done = done_chunks()
    params = cfg.get("params")

    # volleys (deterministic, one trial each)
    vdone = set()
    if VOLLEY_CSV.exists():
        vdone = set(pd.read_csv(VOLLEY_CSV).apply(lambda r: (r.config, r.trigger), axis=1))
    eln_ids = lab.root_id.to_numpy()[S.eln_mask(lab)]
    pn_ids = lab.root_id.to_numpy()[lab.cell_class.to_numpy() == "ALPN"]
    for trig_name, trig in (("10 DM1 ORNs fire once", sets["dm1"][:10]),
                            ("44 eLNs fire once", eln_ids),
                            (f"all {pn_ids.size} AL projection neurons fire once", pn_ids)):
        if (cfg["name"], trig_name) in vdone:
            continue
        res = brain.run_with_input_events([(np.full(len(trig), 50), np.asarray(trig, np.int64))],
                                          excite=trig, duration_ms=1000.0, params=params)
        rows, _ = C.trial_rows(res, rd, dict(config=cfg["name"], trigger=trig_name))
        append_csv(VOLLEY_CSV, rows)
        print(f"  volley {trig_name}: {rows[0]['total_spikes']} spikes, runaway={rows[0]['runaway']}",
              flush=True)

    for cond in cfg.get("conds", ALL):
        base = C.CONDITIONS[cond][1]
        excite = C.excite_for(cond, sets)
        for k in cfg.get("seeds", SEEDS):
            f = CNT / f"{cfg['name']}__{cond}__s{k}.npz"
            if f.exists():
                continue
            counts = np.zeros(brain.n_neurons, np.int64)
            ts = time.perf_counter()
            for a in range(0, N_TRIALS, CHUNK):
                if all((cfg["name"], cond, k, t) in done for t in range(a, a + CHUNK)):
                    part = np.load(CNT / f"_part_{cfg['name']}__{cond}__s{k}__{a}.npy")
                    counts += part
                    continue
                C.wait_for_ram()
                res = C.run_chunk(brain, excite, base + k, a, a + CHUNK, params=params)
                meta = dict(config=cfg["name"], fix=cfg["fix"], condition=cond, seed_index=k,
                            seed=base + k, trial0=a)
                rows, cnt = C.trial_rows(res, rd, meta)
                del res
                np.save(CNT / f"_part_{cfg['name']}__{cond}__s{k}__{a}.npy", cnt)
                append_csv(TRIALS_CSV, rows)
                counts += cnt
            nz = np.flatnonzero(counts)
            np.savez_compressed(f, nz_idx=nz.astype(np.int32), nz_count=counts[nz],
                                n_trials=N_TRIALS)
            for a in range(0, N_TRIALS, CHUNK):
                (CNT / f"_part_{cfg['name']}__{cond}__s{k}__{a}.npy").unlink(missing_ok=True)
            d = pd.read_csv(TRIALS_CSV)
            d = d[(d.config == cfg["name"]) & (d.condition == cond) & (d.seed_index == k)]
            print(f"  {cond} s{k}: MN9 {d.mn9_hz.mean():.2f} Hz, runaway {int(d.runaway.sum())}/"
                  f"{len(d)}, KC active/trial {d.kc_active.mean():.0f}, "
                  f"DNa02 L/R {d.DNa02_L.mean():.1f}/{d.DNa02_R.mean():.1f} "
                  f"({time.perf_counter() - ts:.0f} s)", flush=True)
    del brain
    gc.collect()


def main(stages):
    rid, _, _, _ = S.load_reference_arrays()
    lab = S.neuron_table(rid)
    sets = C.input_sets(lab)
    rp = OUT / "fix_reports.json"
    reports = json.loads(rp.read_text()) if rp.exists() else {}
    for st in stages:
        for cfg in STAGES[st]:
            run_config(cfg, lab, sets, reports)
    print("finished", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or list(STAGES))

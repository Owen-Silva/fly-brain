"""Step 2: the runaway tests on snapshot 783, published model vs ported fix.

Plain English
-------------
Three versions of the snapshot-783 brain, one in memory at a time:
  published       the paper's model on 783, unchanged;
  fix_rule        "al_ln_literature" ported by its rule to 783's own labels;
  fix_same_cells  the same rule applied to exactly the 630 fix's cells.
For each, 3 seeds x 30 one-second trials of (same seeds as the 630 runs):
  DM1 smell neurons 150 Hz on both sides   (runaway test 1)
  Ir94e taste neurons 200 Hz               (runaway test 2)
  sugar taste neurons 100 Hz -> MN9        (the paper's feeding result)
plus three one-off "volleys" (a group of neurons fires once, nothing else):
10 DM1 smell neurons, the 44 eLNs, all antennal-lobe projection neurons.
Stage "lr" adds DM1 left-only and right-only.
Results are saved after every 10 trials, so a rerun resumes where it stopped.
Outputs: results/trials.csv, results/volleys.csv, results/active/*.npz (which
neurons fired in each trial, packed bits, and spikes per neuron),
results/spikes/*.npz (every spike of the first 10 sugar trials, for the
spike-for-spike comparison), results/build_info.json.
Usage: s2_runaway_783.py [main] [lr]
"""

import gc
import json
import sys
import time

import numpy as np
import pandas as pd

import common783 as C

N_TRIALS, CHUNK, SEEDS = 30, 10, (0, 1, 2)
OUT = C.RESULTS
ACT = OUT / "active"
SPK = OUT / "spikes"
ACT.mkdir(exist_ok=True)
SPK.mkdir(exist_ok=True)
TRIALS_CSV = OUT / "trials.csv"
VOLLEY_CSV = OUT / "volleys.csv"
CONFIGS = [("published", "none"), ("fix_rule", "al_ln_literature"), ("fix_same_cells", "same_cells")]
CONDITIONS = {
    "dm1_both_150Hz": ("dm1", 150.0, 0),
    "ir94e_200Hz": ("ir94e", 200.0, 0),
    "sugar_100Hz": ("sugar", 100.0, 1000),
    "dm1_left_150Hz": ("dm1_left", 150.0, 0),
    "dm1_right_150Hz": ("dm1_right", 150.0, 0),
}
STAGES = {"main": ["dm1_both_150Hz", "ir94e_200Hz", "sugar_100Hz"],
          "lr": ["dm1_left_150Hz", "dm1_right_150Hz"]}


def done_trials():
    if not TRIALS_CSV.exists():
        return set()
    d = pd.read_csv(TRIALS_CSV, usecols=["config", "condition", "seed_index", "trial"])
    return set(zip(d.config, d.condition, d.seed_index, d.trial))


def first10_dm1_630_in_783():
    rid630 = pd.read_csv(C.ROOT / "data/reference/2023_03_23_completeness_630_final.csv",
                         index_col=0).index.to_numpy(np.int64)
    l630 = pd.read_parquet(C.ROOT / "data/cache/connectome_630_neurons.parquet",
                           columns=["root_id", "hemibrain_type"]).set_index("root_id").reindex(rid630)
    first10 = rid630[(l630.hemibrain_type.astype(str) == "ORN_DM1").to_numpy(bool)][:10]
    m = C.map_630_to_783(first10)
    out = np.array([m[int(i)][0] for i in first10], np.int64)
    assert (out > 0).all()
    return out


def main(stages):
    sets = json.loads((OUT / "input_sets_783.json").read_text())
    rid = pd.read_csv(C.ROOT / "data/reference/Completeness_783.csv", index_col=0).index.to_numpy(np.int64)
    lab = C.labels("783", rid)
    vtrig = {"10 DM1 smell neurons fire once": first10_dm1_630_in_783(),
             "44 eLNs fire once": rid[C.eln_mask(lab)],
             "all antennal-lobe projection neurons fire once": rid[lab.cell_class.to_numpy() == "ALPN"]}
    conds = [c for s in stages for c in STAGES[s]]
    infos = json.loads((OUT / "build_info.json").read_text()) if (OUT / "build_info.json").exists() else {}
    for cfg, fix in CONFIGS:
        done = done_trials()
        todo = [(c, k, a) for c in conds for k in SEEDS for a in range(0, N_TRIALS, CHUNK)
                if not all((cfg, c, k, t) in done for t in range(a, a + CHUNK))]
        vdone = set()
        if VOLLEY_CSV.exists():
            v = pd.read_csv(VOLLEY_CSV)
            vdone = set(zip(v.config, v.trigger))
        vtodo = [t for t in vtrig if (cfg, t) not in vdone]
        if not todo and not vtodo:
            continue
        C.wait_for_ram(1.5)
        t0 = time.perf_counter()
        brain, info = C.build("783", fix, lab=lab, n_threads=2, return_info=True)
        infos[cfg] = {k: v for k, v in info.items() if not k.endswith("_idx")}
        infos[cfg]["n_connections"] = brain.n_connections
        (OUT / "build_info.json").write_text(json.dumps(infos, indent=1))
        print(f"=== {cfg} ({fix}): {brain.n_connections:,} connections, built in "
              f"{time.perf_counter() - t0:.0f} s; {infos[cfg]}", flush=True)
        rd = C.Readout(brain, lab)
        for trig in vtodo:
            ids = vtrig[trig]
            res = C.run_volley(brain, ids)
            rows, _ = C.trial_rows(res, rd, dict(config=cfg, trigger=trig, n_trigger=len(ids)))
            C.append_csv(VOLLEY_CSV, rows)
            print(f"  volley {trig} ({len(ids)}): {rows[0]['total_spikes']:,} spikes, "
                  f"runaway={rows[0]['runaway']}", flush=True)
        for cond, k, a in todo:
            set_name, rate, base = CONDITIONS[cond]
            excite = {int(i): rate for i in sets[set_name]}
            C.wait_for_ram(1.0)
            ts = time.perf_counter()
            res = C.run_chunk(brain, excite, base + k, a, a + CHUNK)
            meta = dict(config=cfg, fix=fix, condition=cond, seed_index=k, seed=base + k, trial0=a)
            rows, cnt = C.trial_rows(res, rd, meta)
            act = np.zeros((res.n_trials, brain.n_neurons), bool)
            act[res.trial, res.neuron] = True
            np.savez_compressed(ACT / f"{cfg}__{cond}__s{k}__{a}.npz", active=np.packbits(act, axis=1),
                                n=brain.n_neurons, counts=cnt.astype(np.int32))
            if cond == "sugar_100Hz" and k == 0 and a == 0:
                np.savez_compressed(SPK / f"{cfg}__sugar_100Hz__s0__0.npz", trial=res.trial,
                                    step=res.step, neuron=res.neuron)
            C.append_csv(TRIALS_CSV, rows)
            d = pd.DataFrame(rows)
            print(f"  {cond} s{k} trials {a}-{a + CHUNK - 1}: runaway {int(d.runaway.sum())}/{len(d)}, "
                  f"max distinct/10ms median {int(d.max_distinct_10ms.median())}, MN9 "
                  f"{d.mn9_hz.mean():.2f} Hz, KC active {d.kc_active.mean():.0f} "
                  f"({time.perf_counter() - ts:.0f} s)", flush=True)
            del res, act
        del brain
        gc.collect()
    print("finished", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:] or ["main"])

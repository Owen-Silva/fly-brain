"""Step 3: drive the whole brain's ORNs with measured odour responses, one odour at a time.

Usage: python run_odours.py CONFIG
CONFIG (see CONFIGS below):
  alln_A        recommended fix "al_ln_literature", Hallem & Carlson inputs (set A)   [main]
  alln_A_noAPL  same, APL silenced (both APL cells' outputs set to 0)
  alln_B        same fix, set B = Hallem & Carlson + DoOR-extended glomeruli
  alln_B_noAPL  set B, APL silenced
  none_A        published brain, set A with spontaneous rates (short trials)
  none_evoked   published brain, odour response only (no spontaneous firing), short trials

Saves one file per odour: results/counts/CONFIG/NNN.npz with per-trial spike counts of the
read-out rows (ORNs, PNs, LNs, KCs, APL, MBONs, DANs, lateral-horn neurons) and per-trial
whole-brain stats (runaway test with the driven ORNs excluded). Re-running skips odours
already saved, so an interrupted run resumes.
"""
from __future__ import annotations

import gc
import json
import sys
import time

import numpy as np
import pandas as pd

from common import (N_THREADS, RES, groups, load_labels, odour_rates, readout_rows,
                    summarise, wait_for_ram)
from sim.sign_fixes import build_brain

CONFIGS = {
    "alln_A": dict(fix="al_ln_literature", inputs="A", silence="", seeds=(0, 1, 2), trials=4, dur=500.0, spont=True),
    # 2 trials per seed (time budget). Trial k gets the same input whatever n_trials is, so
    # these trials are exactly paired with trials 0-1 of each seed in alln_A.
    "alln_A_noAPL": dict(fix="al_ln_literature", inputs="A", silence="apl", seeds=(0, 1, 2), trials=2, dur=500.0, spont=True),
    "alln_B": dict(fix="al_ln_literature", inputs="B", silence="", seeds=(0, 1, 2), trials=2, dur=500.0, spont=True),
    "alln_B_noAPL": dict(fix="al_ln_literature", inputs="B", silence="apl", seeds=(0, 1, 2), trials=2, dur=500.0, spont=True,
                         skip=True),  # not run: time budget
    "none_A": dict(fix="none", inputs="A", silence="", seeds=(0,), trials=2, dur=300.0, spont=True),
    "none_evoked": dict(fix="none", inputs="A", silence="", seeds=(0,), trials=2, dur=300.0, spont=False),
}


def odour_table(inputs):
    hc = pd.read_csv(RES / "hc_delta.csv", index_col=0)
    if inputs == "B":
        ext = pd.read_csv(RES / "door_ext_delta.csv", index_col=0).drop(columns="odour")
        hc = hc.join(ext)
    return hc


def main(cfg_name):
    cfg = CONFIGS[cfg_name]
    if cfg.get("skip"):
        print(f"{cfg_name}: skipped (time budget)", flush=True)
        return
    out = RES / "counts" / cfg_name
    out.mkdir(parents=True, exist_ok=True)
    table = odour_table(cfg["inputs"])
    sfr = pd.read_csv(RES / "hc_sfr.csv", index_col=0)["sfr_hz"].to_dict()
    names = ["baseline"] + table.odour.tolist()
    todo = [i for i in range(len(names)) if not (out / f"{i:03d}.npz").exists()]
    print(f"{cfg_name}: {len(todo)} of {len(names)} inputs to run", flush=True)
    if not todo:
        return
    wait_for_ram()
    t0 = time.perf_counter()
    brain = build_brain(fix=cfg["fix"], n_threads=N_THREADS)
    lab = load_labels(brain.root_ids)
    g = groups(lab)
    rows, sl = readout_rows(g)
    silence = brain.root_ids[g["apl"]].tolist() if cfg["silence"] == "apl" else []
    meta = {"config": cfg_name, **cfg, "names": names, "slices": sl,
            "n_rows": int(rows.size), "silenced_root_ids": [int(s) for s in silence]}
    (out / "meta.json").write_text(json.dumps(meta, indent=1))
    np.save(out / "rows.npy", rows)
    print(f"  brain built in {time.perf_counter()-t0:.0f} s", flush=True)
    for i in todo:
        name = names[i]
        delta = {} if name == "baseline" else table.iloc[i - 1].drop(labels="odour").to_dict()
        s = sfr if cfg["spont"] else {k: 0.0 for k in set(g["orn_glom"])}
        rates = odour_rates(brain.root_ids, g, s, delta)
        cnts, stats = [], []
        t1 = time.perf_counter()
        for seed in cfg["seeds"]:
            if not rates:      # evoked-only baseline: nothing to drive
                cnts.append(np.zeros((cfg["trials"], rows.size), np.uint16))
                stats += [{"seed": seed, "trial": t, "total_spikes": 0, "n_active": 0,
                           "max_distinct_10ms": 0, "runaway": False, "tip_ms": -1}
                          for t in range(cfg["trials"])]
                continue
            res = brain.run(excite=rates, silence=silence, duration_ms=cfg["dur"],
                            n_trials=cfg["trials"], seed=seed)
            c, st = summarise(res, rows, brain.n_neurons, exclude=g["orn"])
            # tipping time: first 10 ms slice with > 1,500 distinct non-ORN neurons firing
            nonorn = ~np.isin(res.neuron, g["orn"])
            for t, d in enumerate(st):
                m = (res.trial == t) & nonorn
                b = res.step[m] // 100
                key = np.unique(b.astype(np.int64) * brain.n_neurons + res.neuron[m])
                per = np.bincount(key // brain.n_neurons)
                hit = np.flatnonzero(per > 1500)
                d["tip_ms"] = int(hit[0] * 10) if hit.size else -1
                d["seed"] = seed
            cnts.append(c)
            stats += st
        orn_in = np.array([rates.get(int(r), 0.0) for r in brain.root_ids[g["orn"]]])
        np.savez_compressed(out / f"{i:03d}.npz", counts=np.concatenate(cnts),
                            stats=json.dumps(stats), name=name, orn_rates=orn_in.astype(np.float32))
        run_frac = np.mean([d["runaway"] for d in stats])
        kc = np.concatenate(cnts)[:, sl["kc"][0]:sl["kc"][1]]
        print(f"  [{i:3d}] {name[:28]:28s} runaway {run_frac:.2f} KC>=1/trial "
              f"{100*(kc > 0).mean():5.2f}%  ({time.perf_counter()-t1:.1f} s)", flush=True)
    del brain
    gc.collect()


if __name__ == "__main__":
    for c in sys.argv[1:]:
        main(c)

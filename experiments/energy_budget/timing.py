"""Laptop timing pass (PRELIMINARY): both model versions timed back to back, under the same
background load, so their laptop costs can be compared fairly.

The main runs (run_decisions.py) were timed at different moments; other lanes loaded the
CPU far more during the fixed-model run (78% vs 37% total CPU), which slowed identical work
by about 1.6x. Here each decision gets 5 trials (seed 11, trials 0-4) on the published model
and then on the fixed model, with the CPU package power (Intel RAPL) logged each second.
Writes results/laptop_timing.csv and results/raw/power_timing.csv.
"""
from __future__ import annotations

import datetime as dt
import subprocess
import time

import numpy as np
import pandas as pd

from common import (DURATION_MS, MODELS, RAW, RES, decisions, free_ram_gb, load_labels, run_trial,
                    wait_for_ram)
from run_decisions import COUNTERS

N_TRIALS = 5


def main():
    lab = load_labels()
    power_csv = RAW / "power_timing.csv"
    logger = subprocess.Popen(["typeperf", *COUNTERS, "-si", "1", "-o", str(power_csv), "-y"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = []
    try:
        from sim.sign_fixes import build_brain
        for model in MODELS:
            wait_for_ram(1.5)
            brain = build_brain(fix=model, n_threads=1)
            labm = lab.set_index("root_id").reindex(brain.root_ids).reset_index()
            decs = decisions(labm)
            p = brain._params_for(None)
            n_steps = int(round(DURATION_MS / p["dt"]))
            brain.run(excite=decs["sugar"]["ids"][:1].tolist(), duration_ms=10, n_trials=1, seed=0)
            for name, d in decs.items():
                exc_idx = brain.index_of(d["ids"])
                prob = np.full(exc_idx.size, d["rate_hz"] * p["dt"] * 1e-3)
                for k in range(N_TRIALS):
                    ta = dt.datetime.now()
                    c0, w0 = time.process_time(), time.perf_counter()
                    r = run_trial(brain, exc_idx, prob, 11, k, n_steps, p)
                    c1, w1 = time.process_time(), time.perf_counter()
                    rows.append(dict(model=model, decision=name, trial=k, total_spikes=int(r.neuron.size),
                                     wall_total_s=w1 - w0, cpu_s=c1 - c0,
                                     t_start=ta.isoformat(timespec="milliseconds"),
                                     t_end=dt.datetime.now().isoformat(timespec="milliseconds")))
                    del r
                sub = [x for x in rows if x["model"] == model and x["decision"] == name]
                print(f"{model:>17} {name:<10} wall {np.median([x['wall_total_s'] for x in sub]):.2f} s, "
                      f"cpu {np.median([x['cpu_s'] for x in sub]):.2f} s, free RAM {free_ram_gb():.2f} GB",
                      flush=True)
            del brain
    finally:
        time.sleep(3)
        logger.terminate()
        logger.wait(timeout=10)
    pd.DataFrame(rows).to_csv(RES / "laptop_timing.csv", index=False)
    print("wrote", RES / "laptop_timing.csv")


if __name__ == "__main__":
    main()

"""One long-lived simulation worker for the Phase 5 sugar-pathway experiments.

Plain English
-------------
Loading the whole fly brain takes memory (about 1 GB), and this laptop is
short on memory. So instead of starting a new program for every experiment,
this one program loads the brain ONCE and then works through a queue of
experiments ("conditions") written as small JSON files in ``queue/``.

Each condition says: drive the 21 sugar-sensing neurons at some rate (Hz),
optionally silence some neurons (their outputs are set to zero, the paper's
method), use this random seed, run 30 one-second trials (or ``n_trials``:
the fast first-pass "stage 1" screen uses 10). Trial k always gets the same
random input whatever the number of trials, so a 10-trial run is exactly the
first 10 trials of the matching 30-trial run. For every trial the
worker records how many spikes the two MN9 feeding motor neurons fired.
Results are appended to ``results/runs.csv`` straight after each condition,
so nothing is lost if the program stops. Conditions already in that file are
skipped, so the worker can be restarted safely.

Same seed = same random input. With seed 0, trial 7 of the "silence neuron X"
run gets exactly the same sugar-neuron input spikes as trial 7 of the
unsilenced baseline, so any difference is caused by the silencing alone.

Usage:  .venv\\Scripts\\python.exe experiments\\phase5\\sugar_pathway\\worker.py
Stop:   create an empty file queue/STOP (or it exits after 90 idle minutes).
"""
import ctypes
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from sim.fast_engine import FastBrain  # noqa: E402
from ids import SUGAR, MN9, MN9_B  # noqa: E402

QUEUE = HERE / "queue"
RES = HERE / "results"
RUNS = RES / "runs.csv"
LOG = HERE / "logs" / "worker.log"
N_TRIALS = 30
IDLE_EXIT_MIN = 90


def free_gb():
    class MS(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MS()
    m.dwLength = ctypes.sizeof(MS)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.ullAvailPhys / 2**30


def log(msg):
    LOG.parent.mkdir(parents=True, exist_ok=True)
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)


def done_ids():
    if not RUNS.exists():
        return set()
    return set(pd.read_csv(RUNS, usecols=["cond_id"])["cond_id"].astype(str))


def run_condition(brain, c, i_mn9, i_mn9b):
    silence = [int(s) for s in c.get("silence", [])]
    nt = int(c.get("n_trials", N_TRIALS))   # stage-1 screening conditions use 10
    res = brain.run(excite=SUGAR, silence=silence, rate_hz=float(c["stim_hz"]),
                    duration_ms=1000.0, n_trials=nt, seed=int(c["seed"]),
                    params=c.get("params"))   # optional model-constant override, e.g. {"w_syn": 0.22}
    tr, nr = res.trial, res.neuron
    mn9 = np.bincount(tr[nr == i_mn9], minlength=nt)
    mn9b = np.bincount(tr[nr == i_mn9b], minlength=nt)
    tot = np.bincount(tr, minlength=nt)
    rows = pd.DataFrame({
        "cond_id": c["cond_id"], "kind": c.get("kind", ""), "label": c.get("label", ""),
        "stim_hz": float(c["stim_hz"]), "seed": int(c["seed"]),
        "n_silenced": len(silence),
        "silenced": ";".join(str(s) for s in silence) if len(silence) <= 5 else f"{len(silence)} neurons",
        "trial": np.arange(nt), "mn9_hz": mn9, "mn9b_hz": mn9b, "total_spikes": tot,
    })
    header = not RUNS.exists()
    rows.to_csv(RUNS, mode="a", header=header, index=False)
    if c.get("save_rates"):
        st = res.rate_stats()
        st.index.name = "root_id"
        st.reset_index().to_parquet(RES / f"rates_{c['cond_id']}.parquet", index=False)
    return mn9.mean(), res.wall_time_s


def main():
    QUEUE.mkdir(exist_ok=True)
    RES.mkdir(exist_ok=True)
    while free_gb() < 1.5:
        log(f"waiting: only {free_gb():.2f} GB free RAM (need 1.5)")
        time.sleep(60)
    t0 = time.perf_counter()
    brain = FastBrain(snapshot="630", n_threads=2)
    i_mn9, i_mn9b = brain.index_of([MN9, MN9_B])
    brain.run(excite=SUGAR[:1], duration_ms=10, n_trials=1, seed=0)  # compile / warm up
    log(f"loaded v630 ({brain.n_neurons} neurons) in {time.perf_counter()-t0:.1f} s; "
        f"free RAM {free_gb():.2f} GB")
    last_work = time.time()
    while True:
        if (QUEUE / "STOP").exists():
            log("STOP file found, exiting")
            break
        done = done_ids()
        todo = []
        for qf in sorted(QUEUE.glob("*.json")):
            for c in json.loads(qf.read_text(encoding="utf-8")):
                if str(c["cond_id"]) not in done:
                    todo.append(c)
        if not todo:
            if time.time() - last_work > IDLE_EXIT_MIN * 60:
                log("idle too long, exiting")
                break
            time.sleep(10)
            continue
        c = todo[0]
        fg = free_gb()
        if fg < 0.5:
            log(f"pausing: only {fg:.2f} GB free RAM")
            time.sleep(60)
            continue
        m, wall = run_condition(brain, c, i_mn9, i_mn9b)
        last_work = time.time()
        log(f"{c['cond_id']}: MN9 {m:.2f} Hz ({wall:.1f} s; {len(todo)-1} left; {fg:.2f} GB free)")


if __name__ == "__main__":
    main()

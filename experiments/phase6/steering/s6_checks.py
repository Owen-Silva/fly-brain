"""Phase 6 steering check: is the one working steering signal (DA1) robust, and
does anything work when BOTH antennae smell, as they would on a real walking fly?

Plain English
-------------
s2_simulate.py found that the DA1 channel (the cVA pheromone glomerulus) gives
mirror-image steering (left smell -> left DNa02, right smell -> right DNa02)
under the validated al_ln_literature fix, while DM1 (vinegar) does not. Here:

A. "Both antennae smell, one a bit more" (what a fly in an odor gradient gets):
   left/right ORN rates 150/150, 150/100 and 100/150 Hz, for DA1 and DM1,
   3 seeds x 30 trials. Spike counts of the steering neurons are also kept in
   50 ms bins, the window length the Phase 9 body loop reads.
B. Parameter variation (PLAN.md Phase 6 step 1) for DA1 left/right: synapse
   strength w_syn at 90% and 110%, and a weaker input (75 Hz). Seed 0, 30 trials.
C. Mechanism: DA1 left/right with the two il3LN6 neurons silenced (the GABAergic
   local neuron that Taisz et al. 2023 found gives DA1 PNs contralateral
   inhibition). Seed 0, 30 trials.

One brain (al_ln_literature) in memory; waits for s2_simulate.py to finish first
so that two brains are never loaded at once. Each condition is saved as it
finishes; a rerun skips finished ones.
"""
from pathlib import Path
import subprocess
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "results" / "checks"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))

from common import wait_for_ram  # noqa: E402
import s2_simulate as S  # noqa: E402

READOUT = {  # steering pairs to keep in 50 ms bins (DNa02/DNa01 + the best DA1 pairs)
    "DNa02": (720575940629327659, 720575940604737708),
    "DNa01": (720575940623860202, 720575940644438551),
}
IL3LN6 = [720575940625420531, 720575940635094423]
BIN_MS = 50.0


def s2_running():
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command",
                              "(Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
                              "Where-Object { $_.CommandLine -like '*s2_simulate*' }).Count"],
                             capture_output=True, text=True, timeout=60).stdout.strip()
        return int(out or 0) > 0
    except Exception:
        return True


def conditions():
    c = []
    for g in ("DA1", "DM1"):
        for rl, rr in ((150, 150), (150, 100), (100, 150)):
            for sd in (0, 1, 2):
                c.append(dict(name=f"graded_{g}_L{rl}_R{rr}_s{sd}", glom=g, rl=rl, rr=rr, seed=sd))
    for s in ("left", "right"):
        rl, rr = (150, 0) if s == "left" else (0, 150)
        for w in (0.9, 1.1):
            c.append(dict(name=f"wsyn{int(w*100)}_DA1_{s}_s0", glom="DA1", rl=rl, rr=rr, seed=0,
                          params={"w_syn": 0.275 * w}))
        c.append(dict(name=f"rate75_DA1_{s}_s0", glom="DA1", rl=rl // 2, rr=rr // 2, seed=0))
        c.append(dict(name=f"il3LN6off_DA1_{s}_s0", glom="DA1", rl=rl, rr=rr, seed=0, silence=IL3LN6))
    return c


def main():
    while s2_running():
        time.sleep(60)
    lab = S.labels()
    rid = lab.root_id.to_numpy()
    dn_idx = np.flatnonzero((lab.super_class == "descending").to_numpy())
    orn = {(g, s): rid[((lab.cell_class == "olfactory") & (lab.hemibrain_type == f"ORN_{g}")
                        & (lab.side == s)).to_numpy()]
           for g in ("DA1", "DM1") for s in ("left", "right")}
    todo = [c for c in conditions() if not (OUT / f"{c['name']}.npz").exists()]
    if not todo:
        print("all done", flush=True)
        return
    wait_for_ram(1.5)
    brain, note = S.build("al_ln")
    assert np.array_equal(brain.root_ids, rid)
    ro_idx = {k: brain.index_of(list(v)) for k, v in READOUT.items()}
    N, T = brain.n_neurons, S.N_TRIALS
    nb = int(1000.0 / BIN_MS)
    for c in todo:
        wait_for_ram(1.5)
        t1 = time.perf_counter()
        exc = {}
        if c["rl"]:
            exc.update({int(i): float(c["rl"]) for i in orn[c["glom"], "left"]})
        if c["rr"]:
            exc.update({int(i): float(c["rr"]) for i in orn[c["glom"], "right"]})
        res = brain.run(excite=exc, silence=c.get("silence", ()), duration_ms=1000.0, n_trials=T,
                        seed=c["seed"], params=c.get("params"))
        sel = np.isin(res.neuron, dn_idx)
        pos = np.searchsorted(dn_idx, res.neuron[sel])
        dn = np.bincount(res.trial[sel].astype(np.int64) * len(dn_idx) + pos,
                         minlength=T * len(dn_idx)).reshape(T, len(dn_idx)).astype(np.float32)
        bins = {}
        for k, (iL, iR) in ro_idx.items():
            for side, j in (("L", iL), ("R", iR)):
                m = res.neuron == j
                b = np.minimum((res.step[m] * res.dt_ms // BIN_MS).astype(np.int64), nb - 1)
                bins[f"{k}_{side}"] = np.bincount(res.trial[m].astype(np.int64) * nb + b,
                                                  minlength=T * nb).reshape(T, nb).astype(np.int16)
        rates = (np.bincount(res.neuron, minlength=N) / T).astype(np.float32)
        np.savez_compressed(OUT / f"{c['name']}.npz", dn=dn, rates=rates, **bins)
        print(f"{c['name']}: {time.perf_counter()-t1:.0f} s", flush=True)
        del res


if __name__ == "__main__":
    main()

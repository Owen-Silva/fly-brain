"""Where does the left lean sit? Per-PN rates, then the PNs driven directly.

Plain English: the brain-only screen showed the left DA1 projection neurons
(PNs) firing more than the right ones with equal smell, and the left DNae007 /
DNa02 winning every time, in every variant. Two checks, brain only, no body:

A. Equal smell on both antennae (DA1 smell neurons at 119.8 Hz each side, the
   rate 5 mm from the source), variants off / release / map: the rate of EACH
   DA1 PN. The right side's PN group in the screen includes one multi-glomerular
   PN (M_lvPNm44, only 47 receptor synapses), so the per-type comparison here
   (DA1_lPN and DA1_vPN only: 9 left, 8 right) is the fair one.
B. Smell neurons silent; the DA1-type PNs driven directly with Poisson input
   (old model; the switch changes nothing downstream of the receptor neurons):
   equal rate per PN; equal TOTAL per side (right x 9/8, because the right has
   one PN fewer); and the right side clearly stronger. If DNae007 / DNa02 still
   lean left, the lean sits downstream of the PNs.

Design: the loop's 50 ms windows, 2 s, 3 seeds (as open_loop_sameside.py).
DIAGNOSTIC. Outputs (results/): pn_rates_equal_smell.csv, pn_drive_summary.csv,
pn_drive.log.
Run: .venv-body\\Scripts\\python.exe experiments/phase9_sameside/pn_drive_check.py
"""

from __future__ import annotations

import gc
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT))

import sameside as S  # noqa: E402
from sim.body.brain_stepper import BrainStepper  # noqa: E402
from sim.body.mapping import DN_IDS, DNPE002_IDS, orn_ids  # noqa: E402

OUT = HERE / "results"
PN_TABLE = ROOT / "experiments" / "phase6" / "steering" / "results" / "pn_ipsi_contra_630.csv"
N_WIN, WIN_MS, SEEDS = 40, 50.0, (0, 1, 2)
EQUAL_ORN_HZ = 119.8
READ = {"DNa02_L": DN_IDS["DNa02_L"], "DNa02_R": DN_IDS["DNa02_R"], **DNPE002_IDS, **S.DNAE007}


def log(msg):
    line = f"{time.strftime('%H:%M:%S')} {msg}"
    print(line, flush=True)
    with open(OUT / "pn_drive.log", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def run(brain, input_ids, rates, read_ids):
    idx = brain.index_of(read_ids)
    out = np.zeros((len(SEEDS), N_WIN, len(read_ids)))
    for i, seed in enumerate(SEEDS):
        st = BrainStepper(brain, input_ids, seed=seed)
        for k in range(N_WIN):
            out[i, k] = st.step(rates, WIN_MS).rates_hz(idx)
    return out


def main():
    pn = pd.read_csv(PN_TABLE)
    pn = pn[pn.glomerulus == "DA1"].copy()
    pn_ids = pn.pn_root_id.to_numpy(np.int64)
    dn_ids = list(READ.values())
    # A. per-PN rates with equal smell
    left, right = orn_ids("ORN_DA1")
    orns = np.concatenate([left, right])
    orn_rates = np.full(orns.size, EQUAL_ORN_HZ)
    rows = []
    for v in ("off", "release", "map"):
        brain = S.build(v, n_threads=2)
        r = run(brain, orns, orn_rates, list(pn_ids) + dn_ids)
        m = r.mean(axis=(0, 1))
        for j, pid in enumerate(pn_ids):
            p = pn.iloc[j]
            rows.append({"variant": v, "pn_root_id": int(pid), "pn_type": p.pn_type,
                         "pn_side": p.pn_side, "orn_synapses": int(p.from_ipsi_orns + p.from_contra_orns),
                         "rate_hz": float(m[j])})
        for j, n in enumerate(READ):
            rows.append({"variant": v, "pn_root_id": 0, "pn_type": n, "pn_side": "",
                         "orn_synapses": 0, "rate_hz": float(m[len(pn_ids) + j])})
        log(f"A {v} done")
        del brain
        gc.collect()
    a = pd.DataFrame(rows)
    a.to_csv(OUT / "pn_rates_equal_smell.csv", index=False, float_format="%.2f")
    fair = a[a.pn_type.str.startswith("DA1_")]
    log("A: DA1-type PNs (DA1_lPN + DA1_vPN), mean rate per side, equal smell:\n"
        + fair.groupby(["variant", "pn_side"]).rate_hz.agg(["mean", "count"]).round(1).to_string())
    log("A: M_lvPNm44 and DNs:\n" + a[~a.pn_type.str.startswith("DA1_")]
        .pivot(index="pn_type", columns="variant", values="rate_hz").round(1).to_string())
    # B. drive the DA1-type PNs directly (old model)
    fl = pn[(pn.pn_side == "left") & pn.pn_type.str.startswith("DA1_")].pn_root_id.to_numpy(np.int64)
    fr = pn[(pn.pn_side == "right") & pn.pn_type.str.startswith("DA1_")].pn_root_id.to_numpy(np.int64)
    brain = S.build("off", n_threads=2)
    ids = np.concatenate([fl, fr])
    stim = {"equal_per_PN_100": (100.0, 100.0),
            "equal_total_100": (100.0, 100.0 * fl.size / fr.size),
            "right_stronger_100_150": (100.0, 150.0),
            "left_stronger_150_100": (150.0, 100.0),
            "right_only_100": (0.0, 100.0), "left_only_100": (100.0, 0.0)}
    out = []
    for name, (rl, rr) in stim.items():
        rates = np.concatenate([np.full(fl.size, rl), np.full(fr.size, rr)])
        r = run(brain, ids, rates, dn_ids)
        m = r.mean(axis=(0, 1))
        turn_seed = (r[:, :, 0] - r[:, :, 1]).mean(axis=1)
        out.append({"stimulus": name, "pn_L_hz": rl, "pn_R_hz": round(rr, 1),
                    "pns_left": fl.size, "pns_right": fr.size,
                    **{n: float(x) for n, x in zip(READ, m)},
                    "dna02_turn": float(m[0] - m[1]),
                    "dna02_turn_by_seed": "/".join(f"{x:+.1f}" for x in turn_seed),
                    "dnae007_diff": float(m[4] - m[5]), "dnpe002_turn": float(m[2] - m[3])})
        log(f"B {name} done")
    b = pd.DataFrame(out)
    b.to_csv(OUT / "pn_drive_summary.csv", index=False, float_format="%.2f")
    log("B:\n" + b.drop(columns=["pns_left", "pns_right"]).round(1).to_string(index=False))


if __name__ == "__main__":
    main()

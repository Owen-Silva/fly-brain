"""Phase 6 steering check, step 3: left-only vs right-only smell, several glomeruli.

Plain English
-------------
For each smell channel (glomerulus) we drive only the LEFT antenna's receptor
neurons (ORNs) of that channel, or only the RIGHT antenna's, at 150 Hz, and
record every descending neuron (the brain's output to the body), every
projection neuron (PN), and the mean firing of every neuron. 3 seeds x 30
trials per condition. Each finished condition is saved at once (one small
.npz file), so a crash loses at most one condition and a rerun skips what
is already done.

Brain versions ("variants"), built one at a time (never two in memory):
* ``al_ln``    : sim/sign_fixes.build_brain(fix="al_ln_literature"), the validated fix. 1 s trials.
* ``none``     : the published model (fix="none"). 300 ms trials, because it
                 reaches its fixed runaway state within ~50 ms (docs/phase5-olfaction.md 5b).
* ``al_ln_ipsi``: EXPLORATORY, not a project model. al_ln plus the one thing real
                 flies have that the wiring diagram does not: each ORN spike
                 releases ~40% more transmitter from its same-side branch
                 (Gaudry et al. 2013, Nature 493:424). Done by multiplying every
                 ORN -> PN connection whose ORN and PN are on the same side by 1.4
                 (rounded), in memory only.

Usage: python s2_simulate.py al_ln [al_ln_ipsi none ...]
"""
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / "results" / "sim"
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "experiments" / "phase7_signs"))

from common import wait_for_ram  # noqa: E402  (phase7_signs helper, read-only use)

GLOMERULI = ["DM1", "DA1", "DM4", "DM2", "VA2", "DA2"]
SIDES = ["left", "right"]
SEEDS = [0, 1, 2]
N_TRIALS = 30
RATE_HZ = 150.0
IPSI_GAIN = 1.4          # Gaudry et al. 2013: ~40% more release per spike, same-side branch
DURATION = {"al_ln": 1000.0, "al_ln_ipsi": 1000.0, "none": 300.0}
FIX = {"al_ln": "al_ln_literature", "al_ln_ipsi": "al_ln_literature", "none": "none"}


def labels():
    n = pd.read_parquet(ROOT / "data/cache/connectome_630_neurons.parquet",
                        columns=["root_id", "super_class", "cell_class", "cell_type",
                                 "hemibrain_type", "side"])
    for c in ("super_class", "cell_class", "cell_type", "hemibrain_type", "side"):
        n[c] = n[c].astype(object).where(n[c].notna(), "")
    return n


def build(variant, n_threads=2):
    from sim.fast_engine import FastBrain
    from sim.sign_fixes import apply_fix, load_reference_arrays
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre, post, signed, rep = apply_fix(FIX[variant], root_ids, pre, post, signed)
    note = rep.summary() if hasattr(rep, "summary") else str(rep)
    if variant == "al_ln_ipsi":
        lab = labels().set_index("root_id").reindex(root_ids)
        is_orn = ((lab.cell_class == "olfactory") &
                  lab.hemibrain_type.str.startswith("ORN_")).to_numpy()
        is_pn = (lab.cell_class == "ALPN").to_numpy()
        side = lab.side.to_numpy()
        m = is_orn[pre] & is_pn[post] & (side[pre] == side[post]) & np.isin(side[pre], ["left", "right"])
        signed = signed.copy()
        before = int(signed[m].sum())
        signed[m] = np.rint(signed[m] * IPSI_GAIN).astype(signed.dtype)
        note += (f"\nipsi release x{IPSI_GAIN}: {int(m.sum())} ORN->PN same-side connections, "
                 f"{before} -> {int(signed[m].sum())} synapse-equivalents")
    brain = FastBrain.from_arrays(root_ids, pre, post, signed, n_threads=n_threads)
    del pre, post, signed
    return brain, note


def main(variants):
    lab = labels()
    rid = lab.root_id.to_numpy()
    dn_idx = np.flatnonzero((lab.super_class == "descending").to_numpy())
    pn_idx = np.flatnonzero((lab.cell_class == "ALPN").to_numpy())
    np.save(OUT / "dn_root_ids.npy", rid[dn_idx])
    np.save(OUT / "pn_root_ids.npy", rid[pn_idx])
    orn = {(g, s): rid[((lab.cell_class == "olfactory") & (lab.hemibrain_type == f"ORN_{g}")
                        & (lab.side == s)).to_numpy()]
           for g in GLOMERULI for s in SIDES}
    for variant in variants:
        todo = [(g, s, sd) for g in GLOMERULI for s in SIDES for sd in SEEDS
                if not (OUT / f"{variant}_{g}_{s}_s{sd}.npz").exists()]
        if not todo:
            print(f"[{variant}] all done", flush=True)
            continue
        wait_for_ram(1.5)
        t0 = time.perf_counter()
        brain, note = build(variant)
        assert np.array_equal(brain.root_ids, rid), "label order differs from brain order"
        (OUT / f"{variant}_build_note.txt").write_text(note, encoding="utf-8")
        print(f"[{variant}] built in {time.perf_counter()-t0:.0f} s; {len(todo)} runs to do", flush=True)
        dur = DURATION[variant]
        N = brain.n_neurons
        for g, s, sd in todo:
            wait_for_ram(1.5)
            t1 = time.perf_counter()
            res = brain.run(excite=orn[g, s].tolist(), duration_ms=dur, n_trials=N_TRIALS,
                            seed=sd, rate_hz=RATE_HZ)
            sec = dur / 1000.0
            key = res.trial.astype(np.int64) * N + res.neuron
            def per_trial(idx, t_max_ms=None):
                sel = np.isin(res.neuron, idx)
                if t_max_ms is not None:
                    sel &= res.step * res.dt_ms < t_max_ms
                pos = np.searchsorted(idx, res.neuron[sel])
                c = np.bincount(res.trial[sel].astype(np.int64) * len(idx) + pos,
                                minlength=N_TRIALS * len(idx)).reshape(N_TRIALS, len(idx))
                return c
            dn = per_trial(dn_idx) / sec
            pn = per_trial(pn_idx) / sec
            pn_early = per_trial(pn_idx, 50.0) / 0.05
            rates = (np.bincount(res.neuron, minlength=N) / (N_TRIALS * sec)).astype(np.float32)
            n_active = np.array([np.unique(res.neuron[res.trial == k]).size for k in range(N_TRIALS)])
            np.savez_compressed(OUT / f"{variant}_{g}_{s}_s{sd}.npz", dn=dn.astype(np.float32),
                                pn=pn.astype(np.float32), pn_early=pn_early.astype(np.float32),
                                rates=rates, n_active=n_active, n_orn=len(orn[g, s]),
                                duration_ms=dur)
            del res, key
            print(f"[{variant}] {g} {s} seed {sd}: {len(orn[g, s])} ORNs, "
                  f"median active {int(np.median(n_active))}, {time.perf_counter()-t1:.0f} s",
                  flush=True)
        del brain


if __name__ == "__main__":
    main(sys.argv[1:] or ["al_ln"])

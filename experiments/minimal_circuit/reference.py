"""Step 1: whole-brain reference values (PRELIMINARY).

Runs the seven pass-rule stimuli on the whole brain (al_ln_literature fix):
  * seed 7, 30 trials (the search seed; the search uses its first 10 trials),
  * seeds 0, 1, 2, 30 trials each (held out for the final verdict),
  * seed 0, 30 trials, with the weight per synapse at -20% and +20%.
Saves MN9 per trial, every neuron's spike count, and the wiring among the
neurons that receive any input (the search starting point).

Outputs
  results/reference.json           MN9 means/SD per seed x condition
  results/raw/reference_mn9.npz    MN9 per trial
  results/raw/reference_counts.npz spike counts per neuron (seed 7 and 0)
  results/raw/touched_graph.npz    wiring among touched neurons (start set)
"""

import json
import time

import numpy as np

from common import (CONDITIONS, FIX, MN9, RAW, RES, SEARCH_SEED, VALID_SEEDS,
                    VALID_TRIALS, paper_ids, run_conditions, wait_for_ram)

T0 = time.perf_counter()


def log(msg):
    print(f"[{time.perf_counter() - T0:7.1f}s] {msg}", flush=True)


def main():
    from sim.fast_engine import DEFAULT_PARAMS, FastBrain
    from sim.sign_fixes import apply_fix, load_reference_arrays

    ids = paper_ids()
    log(f"free RAM {wait_for_ram(log=log):.2f} GB; loading arrays")
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre2, post2, signed2, rep = apply_fix(FIX, root_ids, pre, post, signed)
    del pre, post, signed
    pre2 = pre2.astype(np.int32)
    post2 = post2.astype(np.int32)
    signed2 = signed2.astype(np.int32)
    brain = FastBrain.from_arrays(root_ids, pre2, post2, signed2, n_threads=1)
    log(f"brain: {brain.n_neurons} neurons, {brain.n_connections} connections "
        f"({rep.notes[:80]}...)")

    w0 = DEFAULT_PARAMS["w_syn"]
    runs = [(f"seed{SEARCH_SEED}", SEARCH_SEED, None)]
    runs += [(f"seed{s}", s, None) for s in VALID_SEEDS]
    runs += [("seed0_w-20", 0, {"w_syn": w0 * 0.8}), ("seed0_w+20", 0, {"w_syn": w0 * 1.2})]

    mn9_all, counts_all, summary = {}, {}, {}
    for name, seed, params in runs:
        wait_for_ram(log=log)
        t = time.perf_counter()
        per, cnt = run_conditions(brain, ids, seed, VALID_TRIALS, params=params, counts=True)
        for c, v in per.items():
            mn9_all[f"{name}|{c}"] = v
        if name in (f"seed{SEARCH_SEED}", "seed0"):
            for c, v in cnt.items():
                counts_all[f"{name}|{c}"] = v.astype(np.int32)
        spikers = set()
        for v in cnt.values():
            spikers |= set(np.flatnonzero(v).tolist())
        summary[name] = {
            "seed": seed, "params": params or {}, "n_trials": VALID_TRIALS,
            "mn9_mean_hz": {c: float(np.mean(v)) for c, v in per.items()},
            "mn9_sd_hz": {c: float(np.std(v, ddof=1)) for c, v in per.items()},
            "n_spiking_neurons_any_condition": len(spikers),
            "n_spiking_per_condition": {c: int((v > 0).sum()) for c, v in cnt.items()},
        }
        log(f"{name}: " + ", ".join(f"{c}={np.mean(v):.1f}" for c, v in per.items())
            + f"  ({len(spikers)} spiking; {time.perf_counter() - t:.0f}s)")
        del cnt

    np.savez_compressed(RAW / "reference_mn9.npz", **mn9_all)
    np.savez_compressed(RAW / "reference_counts.npz", root_ids=root_ids.astype(np.int64),
                        **counts_all)

    # Start set: every neuron that spiked in any search-seed condition, plus
    # every neuron they connect to (= every neuron that received any input),
    # plus the stimulated taste neurons and MN9.
    spk = np.zeros(root_ids.size, bool)
    for k, v in counts_all.items():
        if k.startswith(f"seed{SEARCH_SEED}|"):
            spk |= v > 0
    stim = np.isin(root_ids, ids["SUGAR"] + ids["WATER"] + ids["BITTER"] + [MN9])
    spk |= stim
    touched = spk.copy()
    touched[post2[spk[pre2]]] = True
    keep_edge = touched[pre2] & touched[post2]
    log(f"spiking (seed {SEARCH_SEED}) + stimulus: {int(spk.sum())}; touched: "
        f"{int(touched.sum())}; edges among touched: {int(keep_edge.sum())}")
    np.savez_compressed(RAW / "touched_graph.npz", root_ids=root_ids[touched].astype(np.int64),
                        spiked=spk[touched], pre_root=root_ids[pre2[keep_edge]].astype(np.int64),
                        post_root=root_ids[post2[keep_edge]].astype(np.int64),
                        signed=signed2[keep_edge])
    out = {"label": "PRELIMINARY", "fix": FIX, "mn9": MN9,
           "whole_brain": {"n_neurons": int(brain.n_neurons),
                           "n_connections": int(brain.n_connections),
                           "n_synapses": int(np.abs(signed2).sum())},
           "start_set": {"n_spiking_plus_stimulus": int(spk.sum()),
                         "n_touched": int(touched.sum()),
                         "n_edges_touched": int(keep_edge.sum())},
           "runs": summary, "conditions": CONDITIONS,
           "wall_s": time.perf_counter() - T0}
    (RES / "reference.json").write_text(json.dumps(out, indent=1))
    log("done")


if __name__ == "__main__":
    main()

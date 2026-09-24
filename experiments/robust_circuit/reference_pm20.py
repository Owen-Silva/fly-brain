"""Step 1: whole-brain references at weights -20% and +20% (PRELIMINARY).

The previous lane ran the whole brain at +/-20% on seed 0 only. The new rule
needs it on the search seed (7, 30 trials; amended 02:08, was first 10) and on held-out seeds 1 and 2
(30 trials). Water is not part of the rule, so it is not run here.

Outputs
  results/raw/reference_pm20.npz   MN9 per trial, keys "seed{s}_w{-20,+20}|cond"
  results/reference_pm20.json      means
"""

import json

import numpy as np

from rcommon import FIX, RAW, RES, RULE_CONDS, Timer, paper_ids, run_cond, wait_for_ram

T = Timer()


def main():
    from sim.fast_engine import DEFAULT_PARAMS, FastBrain
    from sim.sign_fixes import apply_fix, load_reference_arrays
    ids = paper_ids()
    T.log(f"free RAM {wait_for_ram(log=T.log):.2f} GB; loading whole brain ({FIX})")
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre2, post2, signed2, _ = apply_fix(FIX, root_ids, pre, post, signed)
    del pre, post, signed
    w0 = DEFAULT_PARAMS["w_syn"]
    runs = [(7, 30), (1, 30), (2, 30)]
    out, summ = {}, {}
    for tag, f in (("w-20", 0.8), ("w+20", 1.2)):
        brain = FastBrain.from_arrays(root_ids, pre2.astype(np.int32), post2.astype(np.int32),
                                      signed2.astype(np.int32), n_threads=1,
                                      params={"w_syn": w0 * f})
        for seed, nt in runs:
            name = f"seed{seed}_{tag}"
            for cond in RULE_CONDS:
                wait_for_ram(log=T.log)
                out[f"{name}|{cond}"] = run_cond(brain, ids, cond, seed, nt)
            summ[name] = {c: float(np.mean(out[f"{name}|{c}"])) for c in RULE_CONDS}
            T.log(f"{name} ({nt} trials): " + ", ".join(f"{c}={v:.1f}" for c, v in summ[name].items()))
            np.savez_compressed(RAW / "reference_pm20.npz", **out)
        del brain
    (RES / "reference_pm20.json").write_text(json.dumps(
        {"label": "PRELIMINARY", "fix": FIX, "mn9_mean_hz": summ,
         "wall_s": round(T.t0 and (__import__("time").perf_counter() - T.t0), 1)}, indent=1))
    T.log("done")


if __name__ == "__main__":
    main()

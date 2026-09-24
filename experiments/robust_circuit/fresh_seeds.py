"""Step 6: the real held-out test on fresh seeds 3, 4, 5 (PRELIMINARY).

Seeds 0-2 were used by validate.py to choose among ~215 accepted circuits, so
they are no longer held out (amendment 03:15 in docs/robust-circuit.md). This
measures the whole brain at seeds 3, 4, 5 (normal, -20%, +20%; 30 trials) and
then runs exactly four pre-declared circuits through the fixed rule in all four
versions, without early exit: checkpoints 411, 79, 47 and 0.

Outputs
  results/raw/reference_fresh.npz   whole-brain MN9 per trial
  results/fresh_seeds.json          per circuit, seed and version
"""

import json

import numpy as np

from rcommon import (CONDITIONS, FIX, RAW, RES, RULE, RULE_CONDS, VALID_TRIALS, VARIANTS,
                     Timer, paper_ids, run_cond, score, wait_for_ram)
from circuit import TouchedGraph

T = Timer()


def arrays(g, cp):
    """Same as this lane's validate.arrays (that module name clashes on sys.path)."""
    kn = np.zeros(g.n, bool)
    kn[cp["nodes"]] = True
    ek = np.zeros(g.m, bool)
    ek[cp["edges"]] = True
    ek &= kn[g.pre] & kn[g.post]
    new = np.cumsum(kn) - 1
    return g.root_ids[kn], new[g.pre[ek]], new[g.post[ek]], g.signed[ek]
FRESH = (3, 4, 5)
CIRCUITS = (411, 79, 47, 0)


def whole_brain(ids):
    from sim.fast_engine import DEFAULT_PARAMS, FastBrain
    from sim.sign_fixes import apply_fix, load_reference_arrays
    p = RAW / "reference_fresh.npz"
    if p.exists():
        return dict(np.load(p))
    T.log(f"free RAM {wait_for_ram(log=T.log):.2f} GB; loading whole brain ({FIX})")
    root_ids, pre, post, signed = load_reference_arrays("630")
    pre2, post2, signed2, _ = apply_fix(FIX, root_ids, pre, post, signed)
    del pre, post, signed
    w0 = DEFAULT_PARAMS["w_syn"]
    out = {}
    for tag, f in (("", 1.0), ("_w-20", 0.8), ("_w+20", 1.2)):
        brain = FastBrain.from_arrays(root_ids, pre2.astype(np.int32), post2.astype(np.int32),
                                      signed2.astype(np.int32), n_threads=1,
                                      params={"w_syn": w0 * f})
        conds = list(CONDITIONS) if tag == "" else list(RULE_CONDS)
        for s in FRESH:
            for c in conds:
                wait_for_ram(log=T.log)
                out[f"seed{s}{tag}|{c}"] = run_cond(brain, ids, c, s, VALID_TRIALS)
            T.log(f"whole brain seed{s}{tag}: " + ", ".join(
                f"{c}={np.mean(out[f'seed{s}{tag}|{c}']):.1f}" for c in conds))
        del brain
    np.savez_compressed(p, **out)
    return out


def main():
    ids = paper_ids()
    ref = whole_brain(ids)
    g = TouchedGraph()
    cps = json.loads((RAW / "checkpoints.json").read_text())["checkpoints"]
    res = {}
    for ci in CIRCUITS:
        cp = cps[ci]
        rid, pre, post, cnt = arrays(g, cp)
        T.log(f"checkpoint {ci}: {cp['n_neurons']} neurons, {cp['n_connections']} conns")
        per = {}
        for s in FRESH:
            ok, r, ff = score(rid, pre, post, cnt, ids, ref, s, VALID_TRIALS, RULE,
                              early_exit=False, water=True, log=T.log)
            per[f"seed{s}"] = {"pass": ok, "first_fail": ff, "versions": r}
            T.log(f"  seed {s}: pass={ok} " + "; ".join(
                f"{v} {x['err_S100']:+.3f}/{x['err_S200']:+.3f} b{x['brake_ratio']:.2f}"
                f" bit{max(x['circuit']['B100'], x['circuit']['B200']):.2f}"
                for v, x in r.items()))
        res[str(ci)] = {"checkpoint": ci, "stage": cp["stage"], "n_neurons": cp["n_neurons"],
                        "n_connections": cp["n_connections"], "n_synapses": cp["n_synapses"],
                        "pass_all": all(d["pass"] for d in per.values()), "seeds": per}
        (RES / "fresh_seeds.json").write_text(json.dumps(
            {"label": "PRELIMINARY", "rule": RULE, "fresh_seeds": FRESH, "variants": VARIANTS,
             "circuits": res}, indent=1))
    T.log("done")


if __name__ == "__main__":
    main()

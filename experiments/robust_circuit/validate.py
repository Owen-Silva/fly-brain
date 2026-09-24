"""Step 3: held-out verdict (PRELIMINARY).

The fixed rule (rcommon.RULE) in all four versions on seeds 0, 1 and 2, 30
trials each, against the whole brain in the matching state. Starts with the
smallest accepted circuit and steps back through the accepted checkpoints
until one passes on every seed. Also validates the 400-neuron starting circuit
(the anchor of the size curve).

Usage: validate.py [checkpoint index]   (default: search from the last one)
Outputs
  results/validation.json
"""

import json
import sys

import numpy as np

from rcommon import (RAW, RES, RULE, VALID_SEEDS, VALID_TRIALS, VARIANTS, Timer, load_refs,
                     paper_ids, score)
from circuit import TouchedGraph

T = Timer()


def arrays(g, cp):
    kn = np.zeros(g.n, bool)
    kn[cp["nodes"]] = True
    ek = np.zeros(g.m, bool)
    ek[cp["edges"]] = True
    ek &= kn[g.pre] & kn[g.post]
    new = np.cumsum(kn) - 1
    return g.root_ids[kn], new[g.pre[ek]], new[g.post[ek]], g.signed[ek]


def verdict(g, cp, ref, ids, early_exit=True):
    rid, pre, post, cnt = arrays(g, cp)
    out = {}
    for s in VALID_SEEDS:
        ok, res, ff = score(rid, pre, post, cnt, ids, ref, s, VALID_TRIALS, RULE,
                            early_exit=early_exit, water=True, log=T.log)
        out[f"seed{s}"] = {"pass": ok, "first_fail": ff, "versions": res}
        T.log(f"  seed {s}: pass={ok} " + "; ".join(
            f"{v} {r['circuit'].get('S100', float('nan')):.1f}/{r['whole'].get('S100', float('nan')):.1f}"
            f" {r.get('err_S100', float('nan')):+.3f}/{r.get('err_S200', float('nan')):+.3f}"
            f" b{r.get('brake_ratio', float('nan')):.2f}" for v, r in res.items()))
        if not ok and early_exit:
            break
    return all(v["pass"] for v in out.values()) and len(out) == len(VALID_SEEDS), out


def main():
    g = TouchedGraph()
    ids = paper_ids()
    ref = load_refs()
    cps = json.loads((RAW / "checkpoints.json").read_text())["checkpoints"]
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None
    tried, chosen = [], None
    for i in ([only] if only is not None else range(len(cps) - 1, -1, -1)):
        cp = cps[i]
        T.log(f"checkpoint {i} ({cp['stage']}): {cp['n_neurons']} neurons, "
              f"{cp['n_connections']} conns")
        ok, out = verdict(g, cp, ref, ids)
        tried.append({"checkpoint": i, "stage": cp["stage"], "n_neurons": cp["n_neurons"],
                      "n_connections": cp["n_connections"], "n_synapses": cp["n_synapses"],
                      "pass_all": ok, "seeds": out})
        (RES / "validation.json").write_text(json.dumps(
            {"label": "PRELIMINARY", "rule": RULE, "tried": tried}, indent=1))
        if ok:
            chosen = i
            break
    T.log(f"chosen checkpoint: {chosen}")
    start = None
    if chosen != 0:
        T.log("400-neuron start circuit (checkpoint 0), for the size curve")
        ok0, out0 = verdict(g, cps[0], ref, ids, early_exit=False)
        start = {"checkpoint": 0, "n_neurons": cps[0]["n_neurons"], "pass_all": ok0,
                 "seeds": out0}
    (RES / "validation.json").write_text(json.dumps(
        {"label": "PRELIMINARY", "rule": RULE, "variants": VARIANTS, "chosen_checkpoint": chosen,
         "tried": tried, "start_circuit": start,
         "wall_s": round(__import__("time").perf_counter() - T.t0, 1)}, indent=1))
    T.log("done")


if __name__ == "__main__":
    main()

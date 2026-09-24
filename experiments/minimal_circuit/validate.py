"""Step 3: held-out check of the searched circuit, plus robustness (PRELIMINARY).

* The fixed pass rule (common.RULE) on seeds 0, 1 and 2, 30 trials each,
  against the whole brain on the same trials. If the final circuit fails, step
  back through the accepted checkpoints until one passes on all three seeds.
* The same circuit with the weight per synapse at -20% and +20%, against the
  whole brain with the same change (seed 0, 30 trials).
* Per-neuron firing rates of the chosen circuit (for the hardware arithmetic).

Outputs
  results/validation.json
  results/minimal_circuit.json   neurons (with labels) and connections
"""

import json
import sys
import time

import numpy as np

from circuit import TouchedGraph
from common import (CONDITIONS, MN9, RAW, RES, RULE, VALID_SEEDS, VALID_TRIALS, check_rule,
                    labels, means, run_conditions, wait_for_ram)

T0 = time.perf_counter()


def log(msg):
    print(f"[{time.perf_counter() - T0:7.1f}s] {msg}", flush=True)


def masks(g, cp):
    kn = np.zeros(g.n, bool)
    kn[cp["nodes"]] = True
    ke = np.zeros(g.m, bool)
    if cp["edges"] is None:
        ke[:] = True
    else:
        ke[cp["edges"]] = True
    return kn, ke


def heldout(g, kn, ke, ref, params=None, seeds=VALID_SEEDS, key="seed{s}", counts=False):
    out = {}
    cnt_all = None
    for s in seeds:
        wait_for_ram(log=log)
        brain = g.build(kn, ke, params=params)
        r = run_conditions(brain, g.ids, s, VALID_TRIALS, params=None, counts=counts)
        per, cnt = (r if counts else (r, None))
        if counts and cnt_all is None:
            cnt_all = (brain.root_ids.copy(), cnt)
        m = means(per)
        whole = {c: float(np.mean(ref[f"{key.format(s=s)}|{c}"])) for c in CONDITIONS}
        ok, d = check_rule(m, whole, **RULE)
        out[f"seed{s}"] = {"pass": ok, "circuit": m, "whole": whole,
                           "circuit_sd": {c: float(np.std(v, ddof=1)) for c, v in per.items()},
                           "details": {k: (float(v) if not isinstance(v, bool) else v)
                                       for k, v in d.items()}}
        log(f"  seed {s}{' ' + str(params) if params else ''}: pass={ok} "
            f"S100 {m['S100']:.1f} vs {whole['S100']:.1f}, S200 {m['S200']:.1f} vs "
            f"{whole['S200']:.1f}, brake {d['brake_ratio']:.2f}, W200 {m['W200']:.1f} vs "
            f"{whole['W200']:.1f}, B {m['B100']:.2f}/{m['B200']:.2f}")
    return out, cnt_all


def main():
    from sim.fast_engine import DEFAULT_PARAMS
    g = TouchedGraph()
    ref = np.load(RAW / "reference_mn9.npz")
    cps = json.loads((RES / "checkpoints.json").read_text())["checkpoints"]
    only = int(sys.argv[1]) if len(sys.argv) > 1 else None

    chosen, results = None, []
    order = list(range(len(cps) - 1, -1, -1)) if only is None else [only]
    for i in order:
        cp = cps[i]
        if cp["edges"] is None and cp["n_neurons"] > 5000:
            continue
        kn, ke = masks(g, cp)
        log(f"checkpoint {i} ({cp['stage']}): {cp['n_neurons']} neurons, "
            f"{cp['n_connections']} conns")
        res, _ = heldout(g, kn, ke, ref)
        allok = all(v["pass"] for v in res.values())
        results.append({"checkpoint": i, "stage": cp["stage"], "n_neurons": cp["n_neurons"],
                        "n_connections": cp["n_connections"], "n_synapses": cp["n_synapses"],
                        "pass_all_seeds": allok, "seeds": res})
        if allok:
            chosen = i
            break
    if chosen is None:
        log("no checkpoint passed on all held-out seeds")
        (RES / "validation.json").write_text(json.dumps({"label": "PRELIMINARY",
                                                         "heldout": results}, indent=1))
        return

    cp = cps[chosen]
    kn, ke = masks(g, cp)
    w0 = DEFAULT_PARAMS["w_syn"]
    log("weight -20% / +20% (seed 0)")
    wres = {}
    for tag, f in (("w-20", 0.8), ("w+20", 1.2)):
        r, _ = heldout(g, kn, ke, ref, params={"w_syn": w0 * f}, seeds=(0,),
                       key="seed{s}_" + tag)
        wres[tag] = r["seed0"]
    log("per-neuron rates of the chosen circuit (seed 0)")
    _, (rids, cnt) = heldout(g, kn, ke, ref, seeds=(0,), counts=True)
    rates = {c: (cnt[c] / VALID_TRIALS).tolist() for c in CONDITIONS}

    lab = labels()
    stim_role = {}
    for grp in ("SUGAR", "WATER", "BITTER"):
        for r in g.ids[grp]:
            stim_role[int(r)] = grp.lower() + " GRN"
    neurons = []
    for k, r in enumerate(rids):
        r = int(r)
        L = lab.loc[r] if r in lab.index else None
        neurons.append({
            "root_id": str(r), "role": "MN9" if r == MN9 else stim_role.get(r, "interneuron"),
            "cell_type": L["cell_type"] if L is not None else "",
            "hemibrain_type": L["hemibrain_type"] if L is not None else "",
            "super_class": L["super_class"] if L is not None else "",
            "cell_class": L["cell_class"] if L is not None else "",
            "side": L["side"] if L is not None else "", "top_nt": L["top_nt"] if L is not None else "",
            "rate_hz": {c: rates[c][k] for c in CONDITIONS}})
    ek = g.edges(kn, ke)
    conns = [{"pre": str(int(g.root_ids[a])), "post": str(int(g.root_ids[b])), "signed_synapses": int(s)}
             for a, b, s in zip(g.pre[ek], g.post[ek], g.signed[ek])]
    (RES / "minimal_circuit.json").write_text(json.dumps({
        "label": "PRELIMINARY", "checkpoint": chosen, "stage": cp["stage"],
        "n_neurons": cp["n_neurons"], "n_connections": cp["n_connections"],
        "n_synapses": cp["n_synapses"], "neurons": neurons, "connections": conns}, indent=1))
    (RES / "validation.json").write_text(json.dumps({
        "label": "PRELIMINARY", "rule": RULE, "chosen_checkpoint": chosen,
        "heldout": results, "weight_change_seed0": wres,
        "wall_s": time.perf_counter() - T0}, indent=1))
    log(f"chosen checkpoint {chosen}: {cp['n_neurons']} neurons; weights: "
        + ", ".join(f"{k} pass={v['pass']}" for k, v in wres.items()))


if __name__ == "__main__":
    main()

"""Step 3b: which circuit sizes survive a +/-20% change in synapse weight? (PRELIMINARY)

The smallest circuit passes the fixed rule at the model's normal weight but
not at -20% or +20% (validate.py). This walks back along the accepted search
checkpoints (every 5th, plus stage ends) and, for each, applies the fixed rule
with the weight per synapse at -20% and at +20% (seed 0, 30 trials, against
the whole brain with the same change). The smallest checkpoint that passes
both, and the normal-weight rule on all three held-out seeds, is saved.

Outputs
  results/robustness_scan.csv
  results/robust_circuit.json   (neurons and connections of that circuit)
"""

import csv
import json
import time

import numpy as np

from circuit import TouchedGraph
from common import CONDITIONS, MN9, RAW, RES, labels
from validate import heldout, masks

T0 = time.perf_counter()


def log(msg):
    print(f"[{time.perf_counter() - T0:7.1f}s] {msg}", flush=True)


def main():
    from sim.fast_engine import DEFAULT_PARAMS
    g = TouchedGraph()
    ref = np.load(RAW / "reference_mn9.npz")
    cps = json.loads((RES / "checkpoints.json").read_text())["checkpoints"]
    w0 = DEFAULT_PARAMS["w_syn"]
    ends = {i for i in range(len(cps) - 1) if cps[i]["stage"] != cps[i + 1]["stage"]}
    pick = sorted({i for i in range(len(cps)) if i % 5 == 0} | ends | {len(cps) - 1})
    pick = [i for i in pick if cps[i]["edges"] is not None and cps[i]["n_neurons"] <= 1000]
    rows = []
    for i in pick:
        cp = cps[i]
        kn, ke = masks(g, cp)
        row = {"checkpoint": i, "stage": cp["stage"], "n_neurons": cp["n_neurons"],
               "n_connections": cp["n_connections"]}
        for tag, f in (("w-20", 0.8), ("w+20", 1.2)):
            r, _ = heldout(g, kn, ke, ref, params={"w_syn": w0 * f}, seeds=(0,),
                           key="seed{s}_" + tag)
            d = r["seed0"]
            row[f"pass_{tag}"] = d["pass"]
            row[f"err_S100_{tag}"] = round(d["details"]["err_S100"], 3)
            row[f"err_S200_{tag}"] = round(d["details"]["err_S200"], 3)
            row[f"brake_{tag}"] = round(d["details"]["brake_ratio"], 3)
        rows.append(row)
        log(f"cp {i} {cp['n_neurons']} neurons: -20% {row['pass_w-20']} "
            f"({row['err_S100_w-20']:+.2f}/{row['err_S200_w-20']:+.2f}), +20% {row['pass_w+20']} "
            f"({row['err_S100_w+20']:+.2f}/{row['err_S200_w+20']:+.2f})")
    with open(RES / "robustness_scan.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # smallest checkpoint passing both weight changes and all held-out seeds
    best = None
    for row in sorted(rows, key=lambda r: (r["n_neurons"], r["n_connections"])):
        if not (row["pass_w-20"] and row["pass_w+20"]):
            continue
        kn, ke = masks(g, cps[row["checkpoint"]])
        res, _ = heldout(g, kn, ke, ref)
        if all(v["pass"] for v in res.values()):
            best = (row, res)
            break
        log(f"cp {row['checkpoint']} passes weights but fails a held-out seed")
    if best is None:
        log("no scanned checkpoint passes all tests")
        return
    row, res = best
    cp = cps[row["checkpoint"]]
    kn, ke = masks(g, cp)
    lab = labels()
    rids = g.root_ids[kn]
    stim = {int(r): grp.lower() + " GRN" for grp in ("SUGAR", "WATER", "BITTER")
            for r in g.ids[grp]}
    neurons = [{"root_id": str(int(r)),
                "role": "MN9" if int(r) == MN9 else stim.get(int(r), "interneuron"),
                "cell_type": lab.loc[int(r), "cell_type"] if int(r) in lab.index else "",
                "top_nt": lab.loc[int(r), "top_nt"] if int(r) in lab.index else ""}
               for r in rids]
    ek = g.edges(kn, ke)
    (RES / "robust_circuit.json").write_text(json.dumps({
        "label": "PRELIMINARY", "checkpoint": row["checkpoint"], "stage": cp["stage"],
        "n_neurons": cp["n_neurons"], "n_connections": cp["n_connections"],
        "n_synapses": cp["n_synapses"], "weight_scan_row": row, "heldout": res,
        "neurons": neurons,
        "connections": [{"pre": str(int(g.root_ids[a])), "post": str(int(g.root_ids[b])),
                         "signed_synapses": int(s)}
                        for a, b, s in zip(g.pre[ek], g.post[ek], g.signed[ek])]}, indent=1))
    log(f"robust smallest: checkpoint {row['checkpoint']} ({cp['stage']}), "
        f"{cp['n_neurons']} neurons, {cp['n_connections']} conns, {cp['n_synapses']} synapses")


if __name__ == "__main__":
    main()

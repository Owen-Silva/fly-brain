"""Step 5: numbers for the write-up (PRELIMINARY). No simulation.

Outputs
  results/summary.json   held-out table, size table, circuit contents, overlap
                         with the previous lane's 36-neuron circuit
"""

import json

import numpy as np

from rcommon import MC_RES, MN9, RAW, RES, VARIANTS, paper_ids
from circuit import TouchedGraph
from common import labels

SP = MC_RES.parents[2] / "experiments" / "phase5" / "sugar_pathway" / "results"
SCAPULA = 720575940624600840
CLAVICLE = 720575940655014049


def main():
    g = TouchedGraph()
    ids = paper_ids()
    val = json.loads((RES / "validation.json").read_text())
    cps = json.loads((RAW / "checkpoints.json").read_text())["checkpoints"]
    ch = val["chosen_checkpoint"]
    cp = cps[ch]
    t = [x for x in val["tried"] if x["checkpoint"] == ch][0]

    held = {}
    for s, d in t["seeds"].items():
        held[s] = {v: {"S100": [round(d["versions"][v]["circuit"]["S100"], 1),
                                round(d["versions"][v]["whole"]["S100"], 1)],
                       "S200": [round(d["versions"][v]["circuit"]["S200"], 1),
                                round(d["versions"][v]["whole"]["S200"], 1)],
                       "err_S100": round(d["versions"][v]["err_S100"], 3),
                       "err_S200": round(d["versions"][v]["err_S200"], 3),
                       "brake": round(d["versions"][v]["brake_ratio"], 2),
                       "SB": [round(d["versions"][v]["circuit"]["S100+B100"], 1),
                              round(d["versions"][v]["whole"]["S100+B100"], 1)],
                       "bitter_max": max(d["versions"][v]["circuit"]["B100"],
                                         d["versions"][v]["circuit"]["B200"])}
                   for v in VARIANTS}
        n = d["versions"]["normal"]
        held[s]["water"] = {c: [round(n["circuit"][c], 1), round(n["whole"].get(c, np.nan), 1)]
                            for c in ("W100", "W200")}

    lab = labels()
    rid = [int(g.root_ids[i]) for i in cp["nodes"]]
    grp = {int(r): k for k in ("SUGAR", "WATER", "BITTER") for r in ids[k]}
    comp = {k: sum(1 for r in rid if grp.get(r) == k) for k in ("SUGAR", "WATER", "BITTER")}
    relay = [r for r in rid if r not in grp and r != MN9]
    types = {}
    for r in relay:
        ct = lab.loc[r, "cell_type"] if r in lab.index else ""
        types.setdefault(ct or f"(unlabelled {r})", []).append(str(r))
    nts = {}
    for r in relay:
        nt = lab.loc[r, "top_nt"] if r in lab.index else ""
        nts[nt] = nts.get(nt, 0) + 1
    named = {}
    for grp_ in json.loads((SP / "groups.json").read_text()):
        if grp_["source"] == "named":
            gi = [int(x) for x in grp_["ids"]]
            named[grp_["name"].replace("named-", "")] = [sum(i in set(rid) for i in gi), len(gi)]
    named["Scapula"] = [int(SCAPULA in rid), 1]
    ek = np.zeros(g.m, bool)
    ek[cp["edges"]] = True
    kn = np.zeros(g.n, bool)
    kn[cp["nodes"]] = True
    ek &= kn[g.pre] & kn[g.post]
    sg = g.signed[ek]
    mc = json.loads((MC_RES / "minimal_circuit.json").read_text())
    small = {int(n["root_id"]) for n in mc["neurons"]}
    overlap = len(small & set(rid))

    # size table: family + accepted steps (seed 7) + held-out results of tried circuits
    import csv
    rows = list(csv.DictReader(open(RES / "search_log.csv")))
    fam = [{k: r[k] for k in ("note", "n_neurons", "n_connections", "n_synapses", "pass_search",
                              "pass_rule_seed7", "normal_W200")} |
           {f"{v}_{e}": r[f"{v}_{e}"] for v in VARIANTS for e in ("err_S100", "err_S200", "brake_ratio")}
           for r in rows if r["stage"] == "F-path"]
    marks = {}
    for i, c in enumerate(cps):
        n = c["n_neurons"]
        if n not in marks or c["n_connections"] < marks[n]["n_connections"]:
            marks[n] = {"checkpoint": i, "stage": c["stage"], "n_neurons": n,
                        "n_connections": c["n_connections"], "n_synapses": c["n_synapses"],
                        "worst_err_seed7": max(abs(float(c["row"][f"{v}_{e}"])) for v in VARIANTS
                                               for e in ("err_S100", "err_S200")),
                        "min_brake_seed7": min(float(c["row"][f"{v}_brake_ratio"]) for v in VARIANTS),
                        "W200_seed7": c["row"].get("normal_W200")}
    tried = [{"checkpoint": x["checkpoint"], "n_neurons": x["n_neurons"],
              "n_connections": x["n_connections"], "pass_all": x["pass_all"],
              "failed_seed": next((s for s, d in x["seeds"].items() if not d["pass"]), None),
              "failed_version": next((d["first_fail"] for d in x["seeds"].values() if not d["pass"]), None)}
             for x in val["tried"]]
    out = {"label": "PRELIMINARY", "chosen_checkpoint": ch, "stage": cp["stage"],
           "n_neurons": cp["n_neurons"], "n_connections": cp["n_connections"],
           "n_synapses": cp["n_synapses"], "n_inhibitory_connections": int((sg < 0).sum()),
           "max_synapses": int(np.abs(sg).max()), "heldout": held, "inputs": comp,
           "n_relay": len(relay), "relay_types": types, "relay_transmitters": nts,
           "named_types": named, "overlap_with_36_neuron_circuit": overlap,
           "family": fam, "accepted_smallest_per_size": sorted(marks.values(),
                                                               key=lambda d: -d["n_neurons"]),
           "validation_tried": tried}
    (RES / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("n_neurons", "n_connections", "n_synapses",
                                           "n_inhibitory_connections", "max_synapses", "inputs",
                                           "n_relay", "relay_transmitters", "named_types",
                                           "overlap_with_36_neuron_circuit")}))


if __name__ == "__main__":
    main()

"""Step 5: does the pruned circuit keep the literature's sugar -> MN9 cells? (PRELIMINARY)

Compares the chosen circuit with
  * the named cell types from the paper and earlier fly work
    (experiments/phase5/sugar_pathway/results/groups.json, "named-*" groups),
  * the 20 strongest all-excitatory sugar -> MN9 routes
    (experiments/phase5/sugar_pathway/results/paths_strongest_MN9_main.csv),
  * Scapula (CB0219), the bitter-brake neuron from docs/phase5-competition.md.

Output: results/pathway_comparison.json
"""

import json

import numpy as np
import pandas as pd

from common import MN9, RES, ROOT

SP = ROOT / "experiments" / "phase5" / "sugar_pathway" / "results"
SCAPULA = 720575940624600840


def main():
    mc = json.loads((RES / "minimal_circuit.json").read_text())
    kept = {int(n["root_id"]) for n in mc["neurons"]}
    edges = {(int(c["pre"]), int(c["post"])) for c in mc["connections"]}
    cps = json.loads((RES / "checkpoints.json").read_text())["checkpoints"]
    spiking = {int(x) for x in np.load(RES / "raw" / "touched_graph.npz")["root_ids"]}
    stage1 = next(c for c in cps if c["stage"] == "1-spiking")
    from circuit import TouchedGraph
    g = TouchedGraph()
    start = {int(g.root_ids[i]) for i in stage1["nodes"]}
    sugar = [int(x) for x in g.ids["SUGAR"]]

    named = []
    for grp in json.loads((SP / "groups.json").read_text()):
        if grp["source"] != "named":
            continue
        ids = [int(x) for x in grp["ids"]]
        named.append({"name": grp["name"].replace("named-", ""), "n": len(ids),
                      "in_touched_set": sum(i in spiking for i in ids),
                      "in_spiking_start_set": sum(i in start for i in ids),
                      "in_minimal_circuit": sum(i in kept for i in ids),
                      "kept_ids": [str(i) for i in ids if i in kept]})

    routes = pd.read_csv(SP / "paths_strongest_MN9_main.csv")
    routes = routes[routes["variant"] == "exc_only_pooled"]
    rrows = []
    for _, r in routes.iterrows():
        mids = [int(x) for x in r["route_ids"].split()[1:]]
        chain = mids
        nodes_kept = all(i in kept for i in chain)
        edges_kept = (nodes_kept
                      and all((a, b) in edges for a, b in zip(chain[:-1], chain[1:]))
                      and any((s, chain[0]) in edges for s in sugar))
        rrows.append({"rank": int(r["rank"]), "route": r["route"],
                      "neurons_kept": f"{sum(i in kept for i in chain[:-1])}/{len(chain) - 1}",
                      "route_intact": bool(edges_kept)})
    route_neurons = {int(x) for s in routes["route_ids"] for x in s.split()[1:]} - {MN9}
    out = {"label": "PRELIMINARY", "named_types": named, "strongest_exc_routes": rrows,
           "route_neurons_total": len(route_neurons),
           "route_neurons_kept": sum(i in kept for i in route_neurons),
           "routes_intact": sum(r["route_intact"] for r in rrows),
           "scapula_kept": SCAPULA in kept}
    (RES / "pathway_comparison.json").write_text(json.dumps(out, indent=1))
    for n in named:
        print(f"{n['name']:<10} n={n['n']} touched={n['in_touched_set']} "
              f"spiking={n['in_spiking_start_set']} kept={n['in_minimal_circuit']}")
    print(f"route neurons kept {out['route_neurons_kept']}/{out['route_neurons_total']}; "
          f"routes intact {out['routes_intact']}/{len(rrows)}; Scapula kept {out['scapula_kept']}")


if __name__ == "__main__":
    main()

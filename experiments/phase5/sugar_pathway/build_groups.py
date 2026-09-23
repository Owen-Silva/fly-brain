"""Define the group-silencing experiments (results/groups.json).

Plain English
-------------
If silencing one neuron changes nothing, maybe its twin on the other side of
the brain (or another neuron of the same type) covers for it. So we also
silence whole groups at once:

1. named: every cell type the paper (and the earlier experimental work,
   Shiu, Sterne et al. 2022) names in the sugar -> MN9 pathway, both brain
   sides together (e.g. both Roundup neurons).
2. celltype: every FlyWire cell type with 2 or more members among the
   sugar-activated neurons (all active members silenced together).
3. pathway: the neurons on the fewest-hop and strongest routes from the
   pathway tracing, silenced together.
4. topk (stage 2, needs the single-neuron results): silence the k neurons
   whose individual silencing lowered MN9 the most, for k = 2, 3, 5, 10, 20, 40,
   to see how many must go before MN9 stops.

Sugar GRNs and the two MN9s are never included (they are the input and the
readout). Usage: python build_groups.py [stage1|topk]
"""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
from ids import SUGAR, MN9, MN9_B  # noqa: E402
from trace_paths import paper_name_map  # noqa: E402

RES = HERE / "results"
EXCLUDE = set(SUGAR) | {MN9, MN9_B}

# paper name -> FlyWire 630 cell types (checked against paper_ST1A names + sez_neurons.pickle)
NAMED = {
    "Roundup": (["CB0553"], ["roundup"]), "G2N-1": (["CB0616"], ["g2n_1"]),
    "Zorro": (["CB0192"], ["zorro"]), "Rattle": (["CB0499"], ["rattle"]),
    "Clavicle": ([], ["clavicle"]), "FMIn": (["CB0366"], ["fmin"]),
    "Fdg": (["CB0038"], ["fdg"]), "Bract": (["DNge173", "DNge174"], ["bract"]),
    "Phantom": (["CB0062"], ["phantom"]), "Usnea": (["CB0008"], ["usnea"]),
    "Sternum": (["CB0051"], ["sternum"]), "Rounddown": (["DNge080"], ["rounddown"]),
    "Roundtree": (["CB0493"], ["roundtree"]), "DNge062": (["DNge062"], []),
    "CB0880": (["CB0880"], []),
}


def safe(s):
    return re.sub(r"[^A-Za-z0-9]+", "-", s).strip("-")


def ids_list(ids):
    return [str(int(i)) for i in sorted(set(int(x) for x in ids) - EXCLUDE)]


def stage1():
    nr = pd.read_parquet(ROOT / "data" / "cache" / "connectome_630_neurons.parquet",
                         columns=["root_id", "cell_type"])
    nr["root_id"] = nr["root_id"].astype(np.int64)
    names = paper_name_map()
    nr["pn"] = nr["root_id"].map(names).fillna("").str.lower()
    groups = []
    for nm, (types, pnames) in NAMED.items():
        m = nr["cell_type"].isin(types)
        for p in pnames:
            m |= nr["pn"].str.startswith(p)
        ids = ids_list(nr.loc[m, "root_id"])
        groups.append({"name": f"named-{safe(nm)}", "label": f"{nm} (all {len(ids)}, both sides)",
                       "ids": ids, "source": "named"})
    cand = pd.read_csv(RES / "candidates.csv")
    act = cand[cand["active_ge_1hz"]].merge(nr[["root_id", "cell_type"]], on="root_id", how="left")
    for ct, g in act.dropna(subset=["cell_type"]).groupby("cell_type"):
        ids = ids_list(g["root_id"])
        if len(ids) >= 2:
            groups.append({"name": f"type-{safe(ct)}", "label": f"cell type {ct} ({len(ids)} active)",
                           "ids": ids, "source": "celltype", "stim_hz": [100]})
    for var in ("all", "exc_only"):
        h = pd.read_csv(RES / f"paths_hops_MN9_main_{var}.csv")
        ids = ids_list(h.loc[h["hop_from_grn"] == 1, "root_id"])
        groups.append({"name": f"path-2hop-{var}", "label": f"all 2-hop relays to MN9 ({var}, {len(ids)})",
                       "ids": ids, "source": "pathway"})
    s = pd.read_csv(RES / "paths_strongest_MN9_main.csv")
    s = s[s["variant"] == "exc_only_pooled"]
    ids = ids_list(i for r in s["route_ids"] for i in r.split() if i != "GRNS")
    groups.append({"name": "path-top20-strongest-exc", "label": f"neurons on the 20 strongest excitatory routes ({len(ids)})",
                   "ids": ids, "source": "pathway"})
    (RES / "groups.json").write_text(json.dumps(groups, indent=1), encoding="utf-8")
    print(len(groups), "groups:", pd.Series([g["source"] for g in groups]).value_counts().to_dict())
    for g in groups:
        if g["source"] != "celltype":
            print(" ", g["name"], len(g["ids"]))


def topk():
    s = pd.read_csv(RES / "silencing_singles.csv")
    groups = json.loads((RES / "groups.json").read_text(encoding="utf-8"))
    groups = [g for g in groups if g["source"] != "topk"]
    for hz in (100, 50):
        g = s[(s["stim_hz"] == hz) & (~s["is_sugar_grn"].astype(bool))].sort_values("ratio")
        for k in (2, 3, 5, 10, 20, 40):
            ids = ids_list(g["root_id"].head(k))
            groups.append({"name": f"top{k}-at{hz}", "label": f"top {k} single-silencing effects at {hz} Hz",
                           "ids": ids, "source": "topk", "stim_hz": [hz]})
    (RES / "groups.json").write_text(json.dumps(groups, indent=1), encoding="utf-8")
    print(len(groups), "groups total")


if __name__ == "__main__":
    {"stage1": stage1, "topk": topk}[sys.argv[1] if len(sys.argv) > 1 else "stage1"]()

"""Find the snapshot-783 successors of paper neurons whose IDs changed.

Plain English: FlyWire gives a neuron a new ID every time someone edits its
reconstruction. Between snapshot 630 (used by the paper) and 783 (the public
release), three neurons this project needs got new IDs: one sugar-sensing
neuron, one bitter-sensing neuron and the second MN9. To find each one's new
ID we compare "connection fingerprints": the list of partners it connects to,
with synapse counts, in 630, against every candidate neuron of the same kind
in 783. The best match (cosine similarity close to 1, similar synapse total)
is the same neuron under its new name.

Sensory neurons are matched on their OUTPUT partners, MN9 on its INPUT
partners (a motor neuron has almost no outputs inside the brain). As a
yardstick, the unchanged MN9 (...660219265) is also matched against itself.

Writes experiments/phase3/id_map_630_to_783.csv. Runtime ~1-2 min, ~2 GB RAM.
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REF = ROOT / "data" / "reference"
ANNOT = ROOT / "data" / "flywire" / "Supplemental_file1_neuron_annotations.tsv"
COLS = ["Presynaptic_ID", "Postsynaptic_ID", "Connectivity"]

QUERIES = [
    # (630 id, role, which side of the synapse the neuron is on, candidate filter)
    (720575940620900446, "sugar GRN", "Presynaptic_ID", "gustatory"),
    (720575940618600651, "bitter GRN", "Presynaptic_ID", "gustatory"),
    (720575940645521262, "MN9 (code: right / ipsi)", "Postsynaptic_ID", "motor"),
    (720575940660219265, "MN9 (code: left / contra), self-check", "Postsynaptic_ID", "motor"),
]


def main():
    c630 = pd.read_parquet(REF / "2023_03_23_connectivity_630_final.parquet", columns=COLS)
    c783 = pd.read_parquet(REF / "Connectivity_783.parquet", columns=COLS)
    ids783 = set(pd.read_csv(REF / "Completeness_783.csv", index_col=0).index)
    ann = pd.read_csv(ANNOT, sep="\t", low_memory=False,
                      usecols=["root_id", "super_class", "cell_class", "cell_sub_class", "cell_type"])
    pools = {
        "gustatory": ann.loc[ann.cell_class == "gustatory", "root_id"].tolist(),
        "motor": ann.loc[ann.super_class == "motor", "root_id"].tolist(),
    }
    rows = []
    for nid, role, side, pool in QUERIES:
        other = "Postsynaptic_ID" if side == "Presynaptic_ID" else "Presynaptic_ID"
        v = c630[c630[side] == nid].groupby(other)["Connectivity"].sum()
        sub = c783[c783[side].isin(pools[pool])].groupby([side, other])["Connectivity"].sum()
        scores = []
        for cand, w in sub.groupby(level=0):
            w = w.droplevel(0)
            u = v.index.union(w.index)
            x, y = v.reindex(u, fill_value=0).to_numpy(float), w.reindex(u, fill_value=0).to_numpy(float)
            scores.append((float(x @ y / np.linalg.norm(x) / np.linalg.norm(y)), int(cand), int(w.sum())))
        scores.sort(reverse=True)
        (s1, best, n1), (s2, second, _) = scores[0], scores[1]
        info = ann.loc[ann.root_id == best, ["cell_class", "cell_sub_class", "cell_type"]].iloc[0]
        rows.append({
            "id_630": nid, "role": role, "in_783_unchanged": nid in ids783,
            "id_783": best, "cosine": round(s1, 3), "synapses_630": int(v.sum()), "synapses_783": n1,
            "runner_up_783": second, "runner_up_cosine": round(s2, 3),
            "annotation_783": f"{info.cell_class} / {info.cell_sub_class} / {info.cell_type}",
        })
        print(rows[-1], flush=True)
    out = ROOT / "experiments" / "phase3" / "id_map_630_to_783.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print("wrote", out)


if __name__ == "__main__":
    main()

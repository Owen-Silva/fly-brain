"""Write experiment lists (queue/*.json) for worker.py.

Stages
------
baselines : unsilenced sugar runs (100 Hz and 50 Hz, seeds 0-3; 200 Hz seed 0)
            plus a positive control (silence all 21 sugar GRNs -> MN9 must be 0).
singles   : silence each candidate neuron on its own (100 Hz and 50 Hz, seed 0).
            Candidates = neurons firing >= 1 Hz at 100 Hz sugar (seed 0), plus
            the paper's own top-200 list (Supplementary Table 1C), minus the two MN9s.
groups    : silence whole groups (cell types, left/right pairs, cumulative
            top-k) -- read from groups.json written by analyze_screen.py.
robust    : re-run the listed conditions with seeds 1, 2 and 3.

Usage: python make_queue.py <stage> [...]
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from ids import SUGAR, MN9, MN9_B  # noqa: E402
import paper_tables  # noqa: E402

Q = HERE / "queue"
RES = HERE / "results"
ACTIVE_HZ = 1.0


def write(name, conds):
    Q.mkdir(exist_ok=True)
    for c in conds:
        c["silence"] = [str(int(s)) for s in c.get("silence", [])]
    (Q / name).write_text(json.dumps(conds, indent=0), encoding="utf-8")
    print(f"wrote {name}: {len(conds)} conditions")


def baselines():
    conds = []
    for hz in (100, 50):
        for seed in (0, 1, 2, 3):
            conds.append({"cond_id": f"base_{hz}_s{seed}", "kind": "baseline", "stim_hz": hz,
                          "seed": seed, "save_rates": seed == 0})
    conds.append({"cond_id": "base_200_s0", "kind": "baseline", "stim_hz": 200, "seed": 0,
                  "save_rates": True})
    conds.append({"cond_id": "ctrl_all_grn_100_s0", "kind": "control", "label": "all 21 sugar GRNs",
                  "stim_hz": 100, "seed": 0, "silence": SUGAR})
    write("01_baselines.json", conds)


def candidates():
    r = pd.read_parquet(RES / "rates_base_100_s0.parquet")
    r["root_id"] = r["root_id"].astype(np.int64)
    act = r[r["mean_hz"] >= ACTIVE_HZ]
    paper = paper_tables.st1c()
    ids = pd.Index(act["root_id"]).union(pd.Index(paper["root_id"]))
    ids = ids.drop([MN9, MN9_B], errors="ignore")
    cand = pd.DataFrame({"root_id": ids.astype(np.int64)})
    cand = cand.merge(r[["root_id", "mean_hz"]].rename(columns={"mean_hz": "rate_100hz_s0"}),
                      on="root_id", how="left").fillna({"rate_100hz_s0": 0.0})
    cand["active_ge_1hz"] = cand["rate_100hz_s0"] >= ACTIVE_HZ
    cand["in_paper_top200"] = cand["root_id"].isin(paper["root_id"])
    cand["is_sugar_grn"] = cand["root_id"].isin(SUGAR)
    cand = cand.sort_values("rate_100hz_s0", ascending=False).reset_index(drop=True)
    cand.to_csv(RES / "candidates.csv", index=False)
    print(f"{len(cand)} candidates: {int(cand['active_ge_1hz'].sum())} active >= {ACTIVE_HZ} Hz, "
          f"{int(cand['in_paper_top200'].sum())} in paper top-200, "
          f"{int((cand['in_paper_top200'] & ~cand['active_ge_1hz']).sum())} only in paper list")
    return cand


def singles():
    cand = candidates()
    for hz in (100, 50):
        conds = [{"cond_id": f"sil_{hz}_s0_{rid}", "kind": "single", "stim_hz": hz, "seed": 0,
                  "silence": [rid]} for rid in cand["root_id"]]
        write(f"02_singles_{hz}.json", conds)


def groups():
    g = json.loads((RES / "groups.json").read_text(encoding="utf-8"))
    conds = []
    for grp in g:
        for hz in grp.get("stim_hz", [100, 50]):
            conds.append({"cond_id": f"grp_{hz}_s0_{grp['name']}", "kind": "group",
                          "label": grp["label"], "stim_hz": hz, "seed": 0,
                          "silence": grp["ids"]})
    write("02_singles_2groups.json", conds)


def stage1():
    """Two-stage design (switched to at 19:52 on 2026-09-22 to save time).
    Stage 1 = a fast first pass with 10 trials (seed 0) for every candidate and
    cell-type group that has no full 30-trial result yet. The named-cell-type
    and pathway groups (the ones the write-up leans on) go straight to 30."""
    runs = pd.read_csv(RES / "runs.csv", usecols=["cond_id"])
    done30 = set(runs["cond_id"].unique())
    cand = pd.read_csv(RES / "candidates.csv")
    fire50 = set(pd.read_parquet(RES / "rates_base_50_s0.parquet").query("mean_hz > 0")["root_id"]
                 .astype(np.int64))
    for hz, tag in ((100, "02a"), (50, "02c")):
        ids = [int(r) for r in cand["root_id"] if f"sil_{hz}_s0_{r}" not in done30
               and (hz == 100 or int(r) in fire50)]
        write(f"{tag}_stage1_{hz}.json",
              [{"cond_id": f"st1_{hz}_s0_{r}", "kind": "single_stage1", "stim_hz": hz, "seed": 0,
                "n_trials": 10, "silence": [r]} for r in ids])
    g = json.loads((RES / "groups.json").read_text(encoding="utf-8"))
    full, quick = [], []
    for grp in g:
        if grp["source"] in ("named", "pathway"):
            for hz in (100, 50):
                full.append({"cond_id": f"grp_{hz}_s0_{grp['name']}", "kind": "group",
                             "label": grp["label"], "stim_hz": hz, "seed": 0, "silence": grp["ids"]})
        elif grp["source"] == "celltype":
            quick.append({"cond_id": f"st1grp_100_s0_{grp['name']}", "kind": "group_stage1",
                          "label": grp["label"], "stim_hz": 100, "seed": 0, "n_trials": 10,
                          "silence": grp["ids"]})
    write("02b_groups_named_pathway.json", full)
    write("02d_stage1_celltype.json", quick)


def stage2():
    """Stage 2 = full 30-trial re-runs (seed 0) of everything stage 1 flagged
    (list written by analyze_screen.py stage1 to results/stage1_flagged.csv),
    plus the top-k groups."""
    f = pd.read_csv(RES / "stage1_flagged.csv")
    f = f[f["flagged"]]
    conds = []
    for _, r in f.iterrows():
        cid = r["cond_id"]
        if cid.startswith("st1_"):
            conds.append({"cond_id": cid.replace("st1_", "sil_", 1), "kind": "single",
                          "stim_hz": int(r["stim_hz"]), "seed": 0, "silence": [int(r["silenced"])]})
        else:
            name = cid.split("_s0_", 1)[1]
            grp = next(g for g in json.loads((RES / "groups.json").read_text(encoding="utf-8"))
                       if g["name"] == name)
            conds.append({"cond_id": f"grp_100_s0_{name}", "kind": "group", "label": grp["label"],
                          "stim_hz": 100, "seed": 0, "silence": grp["ids"]})
    g = json.loads((RES / "groups.json").read_text(encoding="utf-8"))
    for grp in g:
        if grp["source"] == "topk":
            for hz in grp["stim_hz"]:
                conds.append({"cond_id": f"grp_{hz}_s0_{grp['name']}", "kind": "group",
                              "label": grp["label"], "stim_hz": hz, "seed": 0, "silence": grp["ids"]})
    write("03_stage2.json", conds)


def robust():
    lst = json.loads((RES / "robust_list.json").read_text(encoding="utf-8"))
    conds = []
    for item in lst:
        for seed in (1, 2, 3):
            conds.append({"cond_id": item["cond_id"].replace("_s0_", f"_s{seed}_"),
                          "kind": item["kind"] + "_robust", "label": item.get("label", ""),
                          "stim_hz": item["stim_hz"], "seed": seed, "silence": item["silence"]})
    write("04_robust.json", conds)


if __name__ == "__main__":
    {"baselines": baselines, "singles": singles, "groups": groups, "stage1": stage1,
     "stage2": stage2, "robust": robust}[sys.argv[1]]()

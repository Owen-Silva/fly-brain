"""Scorecard batch 1, step 0: look up every neuron and the direct wiring. NO simulation.

Plain English
-------------
Reads the IDs the scorecard lane already found (experiments/scorecard/ids_630.csv),
adds each cell's FlyWire labels, splits PFL3 by the side its OUTPUT goes to (from the
connection list), lists the uniglomerular smell projection neurons and their
glomerulus (sim/gap_junctions.upn_glomeruli, the project's own rule), and counts the
direct synapses from every stimulated group to every read group. Everything is saved
in results/ so the simulation script and the write-up use exactly the same IDs.

Usage:  python experiments/scorecard_batch1/prep.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))

from sim import sign_fixes as S  # noqa: E402
from sim.gap_junctions import upn_glomeruli  # noqa: E402
from sim.plasticity import odor_rows  # noqa: E402

RES = HERE / "results"
RES.mkdir(exist_ok=True)

# (item, role, group in ids_630.csv) -> our group key
GROUP_KEYS = {
    ("FC2", "stimulate", "SAG"): "FC2_stim_SAG",
    ("FC2", "read", "pC1a"): "FC2_read_pC1a",
    ("FC2", "read", "pC1b"): "FC2_read_pC1b",
    ("FC2", "read", "pC1c, pC1d, pC1e"): "FC2_read_pC1cde",
    ("FC5", "stimulate", "cVA sensory neurons (ORN_DA1)"): "FC5_stim_DA1_ORN",
    ("FC5", "read", "aSP-g"): "FC5_read_aSPg",
    ("FC5", "read", "aSP-f"): "FC5_read_aSPf",
    ("FC5", "read", "aSP-h"): "FC5_read_aSPh",
    ("FC1", "stimulate", "vpoEN"): "FC1_stim_vpoEN",
    ("FC1", "stimulate", "pC1a-e"): "FC1_stim_pC1",
    ("FC1", "read", "vpoDN"): "FC1_read_vpoDN",
    ("SD4", "stimulate", "PFL3 (split by output side before running)"): "SD4_stim_PFL3",
    ("SD4", "read", "DNa02 (left, right)"): "SD4_read_DNa02",
    ("TH3", "stimulate", "cool sensory neurons"): "TH_stim_cool",
    ("TH3", "read", "TPN-II candidate VP3+_vPN"): "TH3_read_VP3vPN",
    ("TH3", "read", "DN1a"): "TH3_read_DN1a",
    ("TH2", "stimulate", "warm sensory neurons"): "TH_stim_warm",
    ("TH2", "read", "VP2 projection neurons"): "TH2_read_VP2PN",
    ("TH1", "read", "VP3 projection neurons"): "TH1_read_VP3PN",
    ("OS4", "read", "DA1 projection neurons (sister pairs)"): "OS4_read_DA1PN",
    ("LL1", "stimulate", "MVP2 = MBON11"): "LL1_stim_MBON11",
    ("LL1", "read", "M4/6: MBON01 (g5b'2a)"): "LL1_read_MBON01",
    ("LL1", "read", "M4/6: MBON02 (b2b'2a)"): "LL1_read_MBON02",
    ("LL1", "read", "M4/6: MBON03, MBON04 (b'2mp)"): "LL1_read_MBON0304",
    ("LL1", "read", "V2a: MBON18 (a2sc)"): "LL1_read_MBON18",
    ("LL1", "read", "V2a': MBON16, MBON17 (a'3)"): "LL1_read_MBON1617",
    ("SD1", "stimulate", "LC16"): "SD1_stim_LC16",
    ("SD2", "stimulate", "LC16, left"): "SD2_stim_LC16_L",
    ("SD2", "stimulate", "LC16, right"): "SD2_stim_LC16_R",
    ("SD1", "read", "MDN"): "SD1_read_MDN",
    ("TF4", "stimulate", "water taste neurons (model's standard set)"): "TF4_stim_water",
    ("TF4", "stimulate", "sugar taste neurons (model's standard set)"): "TF4_stim_sugar",
    ("TF4", "read", "Usnea"): "TF4_read_Usnea",
    ("TF4", "read", "Phantom"): "TF4_read_Phantom",
    ("TF4", "read", "Clavicle"): "TF4_read_Clavicle",
    ("TF4", "read", "Fdg"): "TF4_read_Fdg",
}
# Same cells listed again under another item (checked equal below, not re-keyed).
DUPLICATES = {("TH2", "stimulate", "cool sensory neurons"): "TH_stim_cool",
              ("TH1", "stimulate", "cool sensory neurons"): "TH_stim_cool",
              ("SD2", "read", "MDN"): "SD1_read_MDN"}

#: The body loop's steering read-out cells (sim/body/mapping.py).
DNA01 = {"DNa01_L": 720575940623860202, "DNa01_R": 720575940644438551}
DNA02 = {"DNa02_L": 720575940629327659, "DNa02_R": 720575940604737708}

#: Phase 8's standard "odour A" (experiments/phase8/common.py ODOR_GLOMERULI["A"]),
#: given to the smell receptor neurons (ORNs) in the whole brain at 100 Hz.
ODOUR_A = ("DM1", "DC1", "VA2", "DM4")


def main():
    ids = pd.read_csv(ROOT / "experiments" / "scorecard" / "ids_630.csv", dtype=str)
    root_ids, pre, post, signed = S.load_reference_arrays("630")
    lab = S.neuron_table(root_ids)
    rid = np.asarray(root_ids, np.int64)
    row_of = pd.Series(np.arange(rid.size), index=rid)

    groups = {}
    for (item, role, grp), key in GROUP_KEYS.items():
        sel = ids[(ids.item == item) & (ids.role == role) & (ids.group == grp)]
        if sel.empty:
            raise KeyError((item, role, grp))
        if sel.root_id_630.isna().any():
            raise ValueError(f"blank ID in {key}")
        groups[key] = [int(x) for x in sel.root_id_630]
    for (item, role, grp), key in DUPLICATES.items():
        sel = ids[(ids.item == item) & (ids.role == role) & (ids.group == grp)]
        if sorted(int(x) for x in sel.root_id_630) != sorted(groups[key]):
            raise ValueError(f"{item}/{grp} differs from {key}")
    for k, v in groups.items():
        missing = [x for x in v if x not in row_of.index]
        if missing:
            raise KeyError(f"{k}: {len(missing)} IDs not in snapshot 630")
    if sorted(groups["SD4_read_DNa02"]) != sorted(DNA02.values()):
        raise ValueError("DNa02 IDs differ from sim/body/mapping.py")
    groups["SD4_read_DNa01"] = list(DNA01.values())

    # ---- all smell receptor neurons (OS4) and odour A (LL1) ----------------
    cc = lab.cell_class.to_numpy()
    ht = pd.Series(lab.hemibrain_type.to_numpy(), dtype=object).astype(str)
    orn = (cc == "olfactory") & ht.str.startswith("ORN_").to_numpy()
    groups["OS4_stim_allORN"] = [int(x) for x in rid[orn]]
    da1_orn = orn & (ht == "ORN_DA1").to_numpy()
    groups["OS4_stim_DA1_ORN"] = [int(x) for x in rid[da1_orn]]
    if sorted(groups["OS4_stim_DA1_ORN"]) != sorted(groups["FC5_stim_DA1_ORN"]):
        print("NOTE: ORN_DA1 by rule differs from the FC5 list", flush=True)
    groups["LL1_odourA_ORN"] = [int(x) for x in rid[odor_rows(lab, ODOUR_A, kind="orn")]]

    # ---- PFL3 split by OUTPUT side -----------------------------------------
    side = lab.side.to_numpy().astype(str)
    pfl3 = np.array([row_of[x] for x in groups["SD4_stim_PFL3"]])
    m = np.isin(pre, pfl3)
    e = pd.DataFrame({"pre": pre[m], "post": post[m], "w": np.abs(signed[m]).astype(np.int64)})
    e["post_side"] = side[e.post.to_numpy()]
    tab = e.pivot_table(index="pre", columns="post_side", values="w", aggfunc="sum",
                        fill_value=0)
    for c in ("left", "right", "center", ""):
        if c not in tab.columns:
            tab[c] = 0
    tab["total"] = tab[["left", "right", "center", ""]].sum(axis=1)
    tab["frac_left"] = tab.left / (tab.left + tab.right)
    dl, dr = row_of[DNA02["DNa02_L"]], row_of[DNA02["DNa02_R"]]
    to_dl = e[e.post == dl].groupby("pre").w.sum()
    to_dr = e[e.post == dr].groupby("pre").w.sum()
    tab["syn_to_DNa02_L"] = to_dl.reindex(tab.index).fillna(0).astype(int)
    tab["syn_to_DNa02_R"] = to_dr.reindex(tab.index).fillna(0).astype(int)
    tab["output_side"] = np.where(tab.frac_left > 0.5, "left", "right")
    tab["soma_side"] = side[tab.index.to_numpy()]
    tab.insert(0, "root_id", rid[tab.index.to_numpy()])
    tab = tab.reset_index(drop=True)
    tab.to_csv(RES / "pfl3_split.csv", index=False)
    groups["SD4_stim_PFL3_toL"] = [int(x) for x in tab.root_id[tab.output_side == "left"]]
    groups["SD4_stim_PFL3_toR"] = [int(x) for x in tab.root_id[tab.output_side == "right"]]
    print(f"PFL3: {len(groups['SD4_stim_PFL3_toL'])} output left, "
          f"{len(groups['SD4_stim_PFL3_toR'])} output right; purity min "
          f"{np.minimum(tab.frac_left, 1 - tab.frac_left).max():.2f} (worst minority share)",
          flush=True)

    # ---- uniglomerular PNs (OS4 cross-glomerulus pairs) ---------------------
    up = upn_glomeruli(lab, pre, post, signed)
    up["hemibrain_type"] = lab.hemibrain_type.to_numpy()[up.idx.to_numpy()]
    up["top_nt"] = lab.top_nt.to_numpy()[up.idx.to_numpy()]
    up.to_csv(RES / "upn_glomeruli.csv", index=False)
    da1 = set(groups["OS4_read_DA1PN"])
    print(f"uPNs: {len(up)} in {up.glomerulus.nunique()} glomeruli; DA1 uPNs "
          f"{int(up.root_id.isin(da1).sum())} of the 17 DA1 PNs", flush=True)

    # ---- one table of every cell used --------------------------------------
    rows = []
    for k, v in groups.items():
        for x in v:
            i = row_of[x]
            rows.append(dict(group=k, root_id=x, hemibrain_type=lab.hemibrain_type[i],
                             cell_type=lab.cell_type[i], side=lab.side[i],
                             top_nt=lab.top_nt[i], known_nt=lab.known_nt[i]))
    cells = pd.DataFrame(rows)
    cells.to_csv(RES / "cells.csv", index=False)

    # ---- direct synapses, stimulated group -> read group ---------------------
    pairs = [("FC2_stim_SAG", g) for g in ("FC2_read_pC1a", "FC2_read_pC1b", "FC2_read_pC1cde")]
    pairs += [("FC5_stim_DA1_ORN", g) for g in ("FC5_read_aSPg", "FC5_read_aSPf", "FC5_read_aSPh")]
    pairs += [("FC1_stim_vpoEN", "FC1_read_vpoDN"), ("FC1_stim_pC1", "FC1_read_vpoDN")]
    pairs += [("SD4_stim_PFL3_toL", "SD4_read_DNa02"), ("SD4_stim_PFL3_toR", "SD4_read_DNa02")]
    pairs += [("TH_stim_cool", "TH3_read_VP3vPN"), ("TH3_read_VP3vPN", "TH3_read_DN1a"),
              ("TH_stim_cool", "TH3_read_DN1a"), ("TH_stim_warm", "TH2_read_VP2PN"),
              ("TH_stim_cool", "TH2_read_VP2PN"), ("TH_stim_cool", "TH1_read_VP3PN")]
    pairs += [("LL1_stim_MBON11", g) for g in ("LL1_read_MBON01", "LL1_read_MBON02",
                                              "LL1_read_MBON0304", "LL1_read_MBON18",
                                              "LL1_read_MBON1617")]
    pairs += [("SD1_stim_LC16", "SD1_read_MDN")]
    pairs += [(s, r) for s in ("TF4_stim_water", "TF4_stim_sugar")
              for r in ("TF4_read_Usnea", "TF4_read_Phantom", "TF4_read_Clavicle", "TF4_read_Fdg")]
    out = []
    for a, b in pairs:
        ra = np.array([row_of[x] for x in groups[a]])
        rb = np.array([row_of[x] for x in groups[b]])
        mm = np.isin(pre, ra) & np.isin(post, rb)
        # per read cell, so sides can be told apart
        for x in groups[b]:
            j = row_of[x]
            mj = mm & (post == j)
            out.append(dict(from_group=a, to_group=b, to_root_id=x,
                            to_type=lab.hemibrain_type[j], to_side=lab.side[j],
                            n_connections=int(mj.sum()), signed_synapses=int(signed[mj].sum())))
    pd.DataFrame(out).to_csv(RES / "direct_wiring.csv", index=False)

    (RES / "groups.json").write_text(json.dumps(groups, indent=0), encoding="utf-8")
    print("groups:", {k: len(v) for k, v in groups.items()}, flush=True)


if __name__ == "__main__":
    main()

"""Step 0: find the fix's cells and the stimulus cells in snapshot 783.

Plain English
-------------
The fix "al_ln_literature" is defined by a rule on labels: antennal-lobe local
neurons (cell class ALLN) that the model makes excitatory. This script
1. applies that rule to snapshot 783's own labels (the "ported" fix) and counts
   the cells it picks;
2. looks up the 150 cells the fix picks in 630 (13 made inhibitory + 137 whose
   chemical synapses are limited) in 783 through their supervoxel, and checks
   whether the 783 rule picks the same cells;
3. finds the stimulus and read-out cells in 783: DM1 smell neurons (by cell
   type), the paper's Ir94e and sugar taste neurons and MN9 (by ID, checked by
   supervoxel).
Only labels and the two connection lists are loaded (well under 1 GB).
Output: results/labels_783.txt, results/fix_cells_630_in_783.csv,
results/fix_cells_783.csv, results/input_sets_783.json
"""

import gc
import json

import numpy as np
import pandas as pd

import common783 as C
from sim import sign_fixes as S

OUT = C.RESULTS
lines = []


def say(s=""):
    print(s, flush=True)
    lines.append(s)


C.wait_for_ram(1.5)
# ---- 783: labels, model signs, the rule applied ---------------------------
rid783, pre, post, signed = S.load_reference_arrays("783")
sign783 = C.neuron_signs(rid783.size, pre, signed)
lab783 = C.labels("783", rid783)
say(f"783 model neurons {rid783.size:,}; with a row in the 783 annotation: {int(lab783.matched.sum()):,}")
al783 = lab783.cell_class.to_numpy() == "ALLN"
say(f"783 ALLN (antennal-lobe local neurons): {int(al783.sum())}; model sign +1: "
    f"{int((al783 & (sign783 == 1)).sum())}, -1: {int((al783 & (sign783 == -1)).sum())}, "
    f"0 (no outputs): {int((al783 & (sign783 == 0)).sum())}")
_, _, _, info783 = C.fix_al_ln_literature(pre, post, signed, al783, lab783.known_sign.to_numpy())
say(f"783 port of al_ln_literature: {info783['to_inhibitory']} made inhibitory, "
    f"{info783['excitatory_lns']} excitatory LNs limited; removed {info783['removed_connections']:,} "
    f"connections ({info783['removed_synapses']:,} synapses) of {pre.size:,}; flipped "
    f"{info783['flipped_connections']:,} connections ({info783['flipped_synapses']:,} synapses)")
eln783 = C.eln_mask(lab783)
say(f"783 eLNs (ALLN, literature acetylcholine citing Shang et al. 2007): {int(eln783.sum())}")
fix783 = pd.DataFrame(dict(root_id_783=rid783[np.r_[info783['to_inh_idx'], info783['exc_ln_idx']]]))
fix783["role_783"] = ["to_inhibitory"] * info783["to_inhibitory"] + ["excitatory_ln"] * info783["excitatory_lns"]
sub = lab783.set_index("root_id").loc[fix783.root_id_783]
for c in ("cell_type", "hemibrain_type", "side", "top_nt", "known_nt"):
    fix783[c] = sub[c].to_numpy()
fix783["is_eln"] = eln783[np.r_[info783['to_inh_idx'], info783['exc_ln_idx']]]
del pre, post, signed
gc.collect()

# ---- 630: the fix's own cells ----------------------------------------------
rid630, pre, post, signed = S.load_reference_arrays("630")
lab630 = S.neuron_table(rid630)
al630 = lab630.cell_class.to_numpy() == "ALLN"
_, _, _, info630 = C.fix_al_ln_literature(pre, post, signed, al630, lab630.known_sign.to_numpy())
del pre, post, signed
gc.collect()
say(f"630 fix: {info630['to_inhibitory']} made inhibitory, {info630['excitatory_lns']} excitatory LNs "
    f"limited; removed {info630['removed_connections']:,} connections")
say(f"630 ALLN: {int(al630.sum())}; 630 eLNs: {int(S.eln_mask(lab630).sum())}")

roles630 = np.r_[["to_inhibitory"] * info630["to_inhibitory"], ["excitatory_ln"] * info630["excitatory_lns"]]
idx630 = np.r_[info630["to_inh_idx"], info630["exc_ln_idx"]]
f630 = pd.DataFrame(dict(root_id_630=rid630[idx630], role_630=roles630,
                         cell_type_630=lab630.cell_type.to_numpy()[idx630],
                         hemibrain_type_630=lab630.hemibrain_type.to_numpy()[idx630],
                         side_630=lab630.side.to_numpy()[idx630],
                         is_eln_630=S.eln_mask(lab630)[idx630]))
m = C.map_630_to_783(f630.root_id_630.to_numpy())
f630["root_id_783"] = [m[int(i)][0] for i in f630.root_id_630]
f630["found_by"] = [m[int(i)][1] for i in f630.root_id_630]
role783 = dict(zip(fix783.root_id_783, fix783.role_783))
f630["role_783"] = [role783.get(int(r), "not_in_783_fix") if r > 0 else "not_found" for r in f630.root_id_783]
l783 = lab783.set_index("root_id")
row783 = {int(r): i for i, r in enumerate(rid783)}
f630["cell_class_783"] = [l783.cell_class.get(int(r), "") if r > 0 else "" for r in f630.root_id_783]
f630["cell_type_783"] = [l783.cell_type.get(int(r), "") if r > 0 else "" for r in f630.root_id_783]
f630["known_nt_783"] = [l783.known_nt.get(int(r), "") if r > 0 else "" for r in f630.root_id_783]
f630["model_sign_783"] = [int(sign783[row783[int(r)]]) if r > 0 else 0 for r in f630.root_id_783]
f630.to_csv(OUT / "fix_cells_630_in_783.csv", index=False)
found = f630.root_id_783 > 0
say(f"630 fix cells found in 783: {int(found.sum())} of {len(f630)} "
    f"(by supervoxel {int((f630.found_by == 'supervoxel').sum())}, by same root ID "
    f"{int((f630.found_by == 'same_root_id').sum())}); same root ID in both: "
    f"{int((f630.root_id_630 == f630.root_id_783).sum())}")
say("  role in 630 vs role given by the 783 rule:")
for (a, b), k in f630.groupby(["role_630", "role_783"]).size().items():
    say(f"    {a:14s} -> {b:16s} {k}")
odd = f630[f630.role_630 != f630.role_783]
for _, r in odd.iterrows():
    say(f"    differs: 630 {r.root_id_630} ({r.hemibrain_type_630 or r.cell_type_630}, {r.role_630}) -> "
        f"783 {r.root_id_783} class={r.cell_class_783} type={r.cell_type_783} sign={r.model_sign_783} "
        f"known_nt={r.known_nt_783} role={r.role_783}")
back = set(f630.root_id_783[found].astype(np.int64).tolist())
fix783["from_630_fix"] = fix783.root_id_783.isin(back)
fix783.to_csv(OUT / "fix_cells_783.csv", index=False)
extra = fix783[~fix783.from_630_fix]
say(f"783 rule picks {len(fix783)} cells; {int(fix783.from_630_fix.sum())} are the 630 fix cells, "
    f"{len(extra)} are extra")
for (role, ct), k in extra.groupby(["role_783", "cell_type"]).size().items():
    say(f"    extra in 783: {role:14s} {ct or '(no type)'}: {k}")

# ---- eLNs ------------------------------------------------------------------
eln630 = rid630[S.eln_mask(lab630)]
me = C.map_630_to_783(eln630)
eln630_in783 = np.array([me[int(i)][0] for i in eln630], np.int64)
say(f"630 eLNs found in 783: {int((eln630_in783 > 0).sum())} of {eln630.size}; "
    f"also eLNs by the 783 rule: {int(np.isin(eln630_in783, rid783[eln783]).sum())}")

# ---- stimulus and read-out cells ---------------------------------------------
P = C.paper_ids()
sets = {}
t783 = lab783.cell_type.to_numpy()
dm1_783 = rid783[(t783 == "ORN_DM1")]
side783 = lab783.set_index("root_id").side
sets["dm1"] = dm1_783.tolist()
sets["dm1_left"] = [int(i) for i in dm1_783 if side783[i] == "left"]
sets["dm1_right"] = [int(i) for i in dm1_783 if side783[i] == "right"]
say(f"783 DM1 smell neurons (cell_type ORN_DM1): {dm1_783.size} (left {len(sets['dm1_left'])}, "
    f"right {len(sets['dm1_right'])}); cell classes: "
    f"{lab783.cell_class.to_numpy()[t783 == 'ORN_DM1'].tolist().count('olfactory')} olfactory")
dm1_630 = rid630[lab630.hemibrain_type.to_numpy() == "ORN_DM1"]
md = C.map_630_to_783(dm1_630)
dm1_630_in783 = np.array([md[int(i)][0] for i in dm1_630], np.int64)
say(f"630 DM1 (68) found in 783: {int((dm1_630_in783 > 0).sum())}; of those typed ORN_DM1 in 783: "
    f"{int(np.isin(dm1_630_in783, dm1_783).sum())}")

for name in ("IR94E", "SUGAR"):
    ids = [int(i) for i in P[name]]
    mm = C.map_630_to_783(ids)
    phase3 = [int(P["MAP"].get(i, i)) for i in ids]
    agree = sum(int(mm[i][0] == j) for i, j in zip(ids, phase3))
    present = sum(int(j in row783) for j in phase3)
    say(f"{name}: {len(ids)} paper IDs; Phase 3 map -> 783 IDs present in 783: {present}; "
        f"supervoxel lookup agrees with the Phase 3 map for {agree}")
    for i, j in zip(ids, phase3):
        if i != j or mm[i][0] != j:
            say(f"    630 {i} -> Phase 3 map {j}; supervoxel lookup {mm[i]}")
    sets[name.lower()] = phase3
mm = C.map_630_to_783([P["MN9"]])
say(f"MN9 {P['MN9']}: in 783 model: {P['MN9'] in row783}; supervoxel lookup {mm[P['MN9']]}")
(OUT / "input_sets_783.json").write_text(json.dumps(sets, indent=1))
(OUT / "labels_783.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

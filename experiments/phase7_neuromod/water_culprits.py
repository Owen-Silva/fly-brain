"""Which removed dopamine cells carry the water -> MN9 drop? (diagnostic, no simulation)

Plain English: for the water 200 Hz trials of al_ln_literature (stored spike counts,
experiments/phase7_signs), list the cells that the da_modulatory fix silences-at-output,
ranked by how much fast excitation they sent per trial (spikes x synapses) onto the cells
whose firing fell most in the variant. Writes results/water_culprits.csv.
"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT))
from sim import sign_fixes as S
P7 = ROOT / "experiments" / "phase7_signs" / "results" / "counts"
rid, pre, post, signed = S.load_reference_arrays()
lab = S.neuron_table(rid)
p0, q0, s0, _ = S.apply_fix("al_ln_literature", rid, pre, post, signed, lab)
del pre, post, signed
sign0 = S.neuron_signs(len(rid), p0, s0)
amine, ev = S.monoamine_of(lab)
mod = S.modulatory_mask(lab, sign0, ("dopamine",))
def rate(folder, cfg, cond):
    tot = np.zeros(rid.size)
    for k in (0, 1, 2):
        z = np.load(folder / f"{cfg}__{cond}__s{k}.npz"); tot[z["nz_idx"]] += z["nz_count"]
    return tot / 90.0
a = rate(P7, "al_ln_literature", "water_200Hz")
b = rate(HERE / "results" / "counts", "da_modulatory", "water_200Hz")
dropped = (a - b) > 1.0                       # cells that fell by > 1 Hz
name = np.where(lab.hemibrain_type != "", lab.hemibrain_type, lab.cell_type)
m = mod[p0] & dropped[q0]
d = pd.DataFrame(dict(src=p0[m], syn=s0[m]))
d["drive"] = a[d.src] * d.syn
g = d.groupby("src").agg(syn_onto_dropped=("syn", "sum"), drive_per_trial=("drive", "sum")).reset_index()
g["cell_type"] = name[g.src]; g["rate_hz"] = a[g.src]; g["top_nt"] = lab.top_nt.to_numpy()[g.src]
g["conf"] = pd.to_numeric(lab.top_nt_conf, errors="coerce").to_numpy()[g.src]
g["evidence"] = ev[g.src]; g["known_nt"] = lab.known_nt.to_numpy()[g.src]
g["root_id"] = rid[g.src]
g = g.sort_values("drive_per_trial", ascending=False).drop(columns="src")
g.to_csv(HERE / "results" / "water_culprits.csv", index=False)
print(f"cells dropping >1 Hz: {int(dropped.sum())}; removed-output cells feeding them: {len(g)}")
print(g.head(10).to_string(index=False))
mn9 = np.flatnonzero(name == "CB0701")
print("MN9 candidates (CB0701) rates:", a[mn9].round(1), b[mn9].round(1))
